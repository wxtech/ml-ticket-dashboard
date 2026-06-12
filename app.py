"""工单数据分析系统 - Web应用入口"""
import sys
import os
import shutil
import threading
import time
import uuid
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import pandas as pd

from logging_config import setup_logger, get_logger
from utils import load_config
from auth import (
    UserCreate, UserLogin,
    create_user, authenticate_user, create_access_token,
    init_default_users, decode_token,
)

# 初始化日志
setup_logger("ticket_analysis", level="INFO", log_file="output/logs/app.log")
log = get_logger("app")

app = FastAPI(title="工单数据分析系统")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 模板
templates = Jinja2Templates(directory="templates")

# 挂载静态目录
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

config = load_config()

# ===== 全局状态 =====
tasks = {}
upload_dir = Path("data/uploads")
upload_dir.mkdir(parents=True, exist_ok=True)


def _get_user_from_request(request: Request) -> Optional[dict]:
    """从请求中获取用户信息"""
    token = request.query_params.get("token") or request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_token(token)
        return {"username": payload["sub"], "role": payload.get("role", "user")}
    except Exception:
        return None


# ===== 页面路由 =====

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    user = _get_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login")

    results = _load_latest_results()
    token = request.query_params.get("token") or request.cookies.get("access_token", "")
    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user, "results": results, "token": token,
    })


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    user = _get_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login")

    token = request.query_params.get("token") or request.cookies.get("access_token", "")
    return templates.TemplateResponse(request, "upload.html", {
        "user": user, "token": token,
    })


@app.get("/analysis")
async def analysis_dashboard(request: Request):
    """跳转到详细的分析仪表盘"""
    return FileResponse("output/dashboard.html", media_type="text/html")


# ===== 认证 API =====

@app.post("/api/auth/login")
async def api_login(creds: UserLogin):
    user = authenticate_user(creds.username, creds.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user["username"], user["role"])
    log.info(f"用户登录 | {user['username']}")
    return {"access_token": token, "username": user["username"], "role": user["role"]}


@app.post("/api/auth/register")
async def api_register(user: UserCreate):
    create_user(user.username, user.password, user.role)
    token = create_access_token(user.username, user.role)
    return {"access_token": token, "username": user.username, "role": user.role}


# ===== 文件上传 API =====

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    ticket_type: str = Form("ticket_main"),
    token: str = Form(...),
):
    """上传CSV文件并触发后台分析"""
    try:
        payload = decode_token(token)
        user = payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Token 无效")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")

    # 保存文件
    file_id = str(uuid.uuid4())[:8]
    save_path = upload_dir / f"{ticket_type}_{file_id}.csv"
    content = await file.read()
    save_path.write_bytes(content)

    # 验证CSV
    try:
        df = pd.read_csv(save_path)
    except Exception as e:
        save_path.unlink()
        raise HTTPException(status_code=400, detail=f"CSV 格式错误: {str(e)}")

    log.info(f"文件上传 | {file.filename} | {len(df)}行 | type={ticket_type} | user={user}")

    # 启动后台任务
    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        "task_id": task_id,
        "status": "running",
        "progress": 0,
        "message": "正在分析数据...",
        "file": file.filename,
        "ticket_type": ticket_type,
        "created_at": datetime.now().isoformat(),
        "user": user,
        "rows": len(df),
    }

    thread = threading.Thread(target=_run_analysis_task, args=(task_id, save_path, ticket_type))
    thread.daemon = True
    thread.start()

    return {"task_id": task_id, "status": "running", "rows": len(df)}


# ===== 任务状态 API =====

@app.get("/api/tasks")
async def list_tasks():
    return {"tasks": list(tasks.values())[-10:]}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


# ===== 结果 API =====

@app.get("/api/results/latest")
async def get_latest_results():
    return _load_latest_results()


# ===== 后台分析 =====

def _run_analysis_task(task_id: str, data_path: Path, ticket_type: str):
    try:
        tasks[task_id]["progress"] = 10
        tasks[task_id]["message"] = "正在合并数据..."

        # 加载并合并数据
        df = pd.read_csv(data_path)
        main_path = Path(config["data"]["raw_dir"]) / f"{ticket_type}.csv"

        if main_path.exists():
            existing = pd.read_csv(main_path)
            if ticket_type == "inventory_daily":
                keys = ["date", "material_id", "site_id"]
            elif ticket_type == "ticket_materials":
                keys = ["ticket_id", "material_id"]
            else:
                keys = ["ticket_id"]
            df = pd.concat([existing, df], ignore_index=True).drop_duplicates(subset=keys, keep="last")

        df.to_csv(main_path, index=False)
        tasks[task_id]["progress"] = 20
        tasks[task_id]["message"] = f"数据已合并 ({len(df)}行)，开始异常检测..."

        # 异常检测
        from anomaly_detection import run as run_anomaly
        run_anomaly(config)
        tasks[task_id]["progress"] = 40
        tasks[task_id]["message"] = "异常检测完成，开始风险评分..."

        # 风险评分
        from risk_scoring import run as run_risk
        run_risk(config)
        tasks[task_id]["progress"] = 60
        tasks[task_id]["message"] = "风险评分完成，开始库存预测..."

        # 库存预测
        from inventory_forecast import run as run_forecast
        run_forecast(config)
        tasks[task_id]["progress"] = 80
        tasks[task_id]["message"] = "库存预测完成，正在生成仪表盘..."

        # 生成仪表盘
        from dashboard import main as run_dashboard
        run_dashboard()
        tasks[task_id]["progress"] = 95
        tasks[task_id]["message"] = "仪表盘已更新，正在生成图表..."

        # 生成图表
        try:
            from visualize import main as run_visualize
            run_visualize()
        except Exception:
            pass

        tasks[task_id]["progress"] = 100
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["message"] = f"分析完成! 共处理 {len(df)} 行数据"
        tasks[task_id]["completed_at"] = datetime.now().isoformat()
        log.info(f"分析完成 | task={task_id} | rows={len(df)}")

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["message"] = f"分析失败: {str(e)}"
        log.error(f"分析失败 | task={task_id} | {traceback.format_exc()}")


def _load_latest_results() -> dict:
    output_dir = Path(config["data"]["output_dir"])
    results = {}

    try:
        f = output_dir / "anomaly_detection_results.csv"
        if f.exists():
            df = pd.read_csv(f)
            results["anomaly"] = {
                "total": len(df),
                "anomaly_count": int(df["anomaly_label"].sum()),
                "anomaly_rate": round(float(df["anomaly_label"].mean() * 100), 1),
                "avg_score": round(float(df["anomaly_score"].mean()), 3),
            }
    except Exception as e:
        log.error(f"加载异常检测结果失败: {e}")

    try:
        f = output_dir / "risk_scoring_results.csv"
        if f.exists():
            df = pd.read_csv(f)
            results["risk"] = {
                "total": len(df),
                "high": int(df["is_risk_high"].sum()),
                "medium": int(df["is_risk_medium"].sum()),
                "low": int(df["is_risk_low"].sum()),
                "avg_score": round(float(df["risk_score"].mean()), 3),
            }
    except Exception as e:
        log.error(f"加载风险评分结果失败: {e}")

    try:
        f = output_dir / "inventory_forecast_results.csv"
        if f.exists():
            df = pd.read_csv(f)
            results["forecast"] = {
                "combos": len(df.groupby(["material_id", "site_id"])),
                "total_demand": round(float(df["forecast"].sum()), 1),
            }
    except Exception as e:
        log.error(f"加载库存预测结果失败: {e}")

    try:
        f = output_dir / "inventory_plan_results.csv"
        if f.exists():
            df = pd.read_csv(f)
            results["plan"] = {
                "total": len(df),
                "need_reorder": int(df["need_reorder"].sum()),
            }
    except Exception as e:
        log.error(f"加载库存计划结果失败: {e}")

    try:
        csv_files = list(output_dir.glob("*.csv"))
        if csv_files:
            latest = max(f.stat().st_mtime for f in csv_files)
            results["last_updated"] = datetime.fromtimestamp(latest).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    return results


@app.on_event("startup")
async def startup():
    log.info("=" * 50)
    log.info("工单数据分析系统 Web 应用启动")
    log.info("=" * 50)
    init_default_users()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)

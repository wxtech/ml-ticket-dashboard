"""工单数据分析系统 - Web应用入口"""
import sys
import os
import threading
import time
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import pandas as pd

from logging_config import setup_logger, get_logger
from utils import load_config
from auth import (
    UserCreate, UserLogin, TokenResponse, ACCESS_TOKEN_EXPIRE_MINUTES,
    create_user, authenticate_user, create_access_token,
    get_current_user, require_admin, init_default_users, decode_token,
)
import jwt

# 初始化日志
setup_logger("ticket_analysis", level="INFO", log_file="output/logs/app.log")
log = get_logger("app")

app = FastAPI(title="工单数据分析系统")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 模板和静态文件
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

config = load_config()
SECRET_KEY = "ticket-analysis-secret-key-change-in-production-2025"

# ===== 全局状态 =====

tasks = {}  # task_id -> {status, progress, message, result_file, created_at}
upload_dir = Path("data/uploads")
upload_dir.mkdir(parents=True, exist_ok=True)


# ===== 路由：页面 =====

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, token: Optional[str] = None):
    # 从 cookie 获取 token
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")

    try:
        payload = decode_token(token)
        user = {"username": payload["sub"], "role": payload.get("role", "user")}
    except Exception:
        return RedirectResponse(url="/login")

    # 加载最新分析结果
    results = _load_latest_results()
    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user,
        "results": results,
        "token": token,
    })


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, token: Optional[str] = None):
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")

    try:
        payload = decode_token(token)
        user = {"username": payload["sub"], "role": payload.get("role", "user")}
    except Exception:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(request, "upload.html", {
        "user": user,
        "token": token,
    })


# ===== 路由：认证 API =====

@app.post("/api/auth/login")
async def api_login(creds: UserLogin):
    user = authenticate_user(creds.username, creds.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user["username"], user["role"])
    log.info(f"用户登录 | {user['username']}")
    return {"access_token": token, "token_type": "bearer", "username": user["username"], "role": user["role"]}


@app.post("/api/auth/register")
async def api_register(user: UserCreate):
    create_user(user.username, user.password, user.role)
    token = create_access_token(user.username, user.role)
    return {"access_token": token, "username": user.username, "role": user.role}


@app.get("/api/auth/me")
async def api_me(token: Optional[str] = None):
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = decode_token(token)
        return {"username": payload["sub"], "role": payload.get("role", "user")}
    except Exception:
        raise HTTPException(status_code=401, detail="Token 无效")


# ===== 路由：文件上传 =====

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    ticket_type: str = Form("ticket_main"),
    token: str = Form(...),
):
    """上传CSV文件并触发后台分析"""
    # 验证token
    try:
        payload = decode_token(token)
        user = payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Token 无效")

    # 验证文件类型
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")

    # 保存文件
    file_id = str(uuid.uuid4())[:8]
    save_path = upload_dir / f"{ticket_type}_{file_id}.csv"
    content = await file.read()
    save_path.write_bytes(content)

    # 验证CSV格式
    try:
        df = pd.read_csv(save_path)
        log.info(f"文件上传成功 | {file.filename} | {len(df)}行 | user={user}")
    except Exception as e:
        save_path.unlink()
        raise HTTPException(status_code=400, detail=f"CSV 格式错误: {str(e)}")

    # 启动后台分析任务
    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
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

    return {"task_id": task_id, "status": "running", "message": f"已上传 {len(df)} 行数据，开始分析..."}


# ===== 路由：任务状态 =====

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str, token: Optional[str] = None):
    if token:
        try:
            decode_token(token)
        except Exception:
            raise HTTPException(status_code=401, detail="Token 无效")

    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.get("/api/tasks")
async def list_tasks(token: Optional[str] = None):
    if token:
        try:
            decode_token(token)
        except Exception:
            raise HTTPException(status_code=401, detail="Token 无效")
    return {"tasks": list(tasks.values())[-10:]}  # 最近10个任务


# ===== 路由：最新结果 =====

@app.get("/api/results/latest")
async def get_latest_results(token: Optional[str] = None):
    if token:
        try:
            decode_token(token)
        except Exception:
            raise HTTPException(status_code=401, detail="Token 无效")
    return _load_latest_results()


# ===== 后台分析任务 =====

def _run_analysis_task(task_id: str, data_path: Path, ticket_type: str):
    """后台运行分析任务"""
    try:
        tasks[task_id]["progress"] = 10
        tasks[task_id]["message"] = "正在加载数据..."

        # 加载上传的数据
        df = pd.read_csv(data_path)
        total_rows = len(df)

        # 合并到主数据
        main_path = Path(config["data"]["raw_dir"]) / f"{ticket_type}.csv"
        if main_path.exists():
            existing = pd.read_csv(main_path)
            # 根据表类型选择去重键
            if ticket_type == "inventory_daily":
                dedup_keys = ["date", "material_id", "site_id"]
            elif ticket_type == "ticket_materials":
                dedup_keys = ["ticket_id", "material_id"]
            else:
                dedup_keys = ["ticket_id"]
            df = pd.concat([existing, df], ignore_index=True).drop_duplicates(subset=dedup_keys, keep="last")

        df.to_csv(main_path, index=False)
        tasks[task_id]["progress"] = 20
        tasks[task_id]["message"] = f"数据已合并 ({len(df)}行)，开始异常检测..."

        # 运行异常检测
        from anomaly_detection import run as run_anomaly
        run_anomaly(config)
        tasks[task_id]["progress"] = 40
        tasks[task_id]["message"] = "异常检测完成，开始风险评分..."

        # 运行风险评分
        from risk_scoring import run as run_risk
        run_risk(config)
        tasks[task_id]["progress"] = 60
        tasks[task_id]["message"] = "风险评分完成，开始库存预测..."

        # 运行库存预测
        from inventory_forecast import run as run_forecast
        run_forecast(config)
        tasks[task_id]["progress"] = 80
        tasks[task_id]["message"] = "库存预测完成，正在生成仪表盘..."

        # 重新生成仪表盘
        from dashboard import main as run_dashboard
        run_dashboard()
        tasks[task_id]["progress"] = 95
        tasks[task_id]["message"] = "仪表盘已更新，正在生成图表..."

        # 生成图表
        try:
            from visualize import main as run_visualize
            run_visualize()
        except Exception:
            pass  # 图表生成失败不影响主流程

        tasks[task_id]["progress"] = 100
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["message"] = f"分析完成! 共处理 {len(df)} 行数据"
        tasks[task_id]["completed_at"] = datetime.now().isoformat()
        log.info(f"分析任务完成 | task={task_id} | rows={len(df)}")

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["message"] = f"分析失败: {str(e)}"
        log.error(f"分析任务失败 | task={task_id} | error={str(e)}")


def _load_latest_results() -> dict:
    """加载最新的分析结果"""
    output_dir = Path(config["data"]["output_dir"])
    results = {}

    # 异常检测结果
    anomaly_file = output_dir / "anomaly_detection_results.csv"
    if anomaly_file.exists():
        df = pd.read_csv(anomaly_file)
        results["anomaly"] = {
            "total": len(df),
            "anomaly_count": int(df["anomaly_label"].sum()),
            "anomaly_rate": round(float(df["anomaly_label"].mean() * 100), 1),
            "avg_score": round(float(df["anomaly_score"].mean()), 3),
        }

    # 风险评分结果
    risk_file = output_dir / "risk_scoring_results.csv"
    if risk_file.exists():
        df = pd.read_csv(risk_file)
        results["risk"] = {
            "total": len(df),
            "high": int(df["is_risk_high"].sum()),
            "medium": int(df["is_risk_medium"].sum()),
            "low": int(df["is_risk_low"].sum()),
            "avg_score": round(float(df["risk_score"].mean()), 3),
        }

    # 库存预测结果
    forecast_file = output_dir / "inventory_forecast_results.csv"
    plan_file = output_dir / "inventory_plan_results.csv"
    if forecast_file.exists():
        df = pd.read_csv(forecast_file)
        results["forecast"] = {
            "combos": len(df.groupby(["material_id", "site_id"])),
            "total_demand": round(float(df["forecast"].sum()), 1),
        }
    if plan_file.exists():
        df = pd.read_csv(plan_file)
        results["plan"] = {
            "total": len(df),
            "need_reorder": int(df["need_reorder"].sum()),
        }

    # 最后更新时间
    csv_files = list(output_dir.glob("*.csv"))
    if csv_files:
        latest = max(f.stat().st_mtime for f in csv_files)
        results["last_updated"] = datetime.fromtimestamp(latest).strftime("%Y-%m-%d %H:%M:%S")

    return results


# ===== 启动事件 =====

@app.on_event("startup")
async def startup():
    log.info("=" * 50)
    log.info("工单数据分析系统 Web 应用启动")
    log.info("=" * 50)
    init_default_users()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)

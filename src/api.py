"""工单分析 API 服务"""
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Annotated
from contextlib import asynccontextmanager

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import uvicorn

from logging_config import setup_logger, get_logger
from utils import load_config, compute_time_features
from anomaly_detection import prepare_features, ensemble_detect, analyze_anomaly_reasons
from risk_scoring import rule_based_score, compute_composite_score, build_lr_features
from auth import (
    UserCreate, UserLogin, TokenResponse, ACCESS_TOKEN_EXPIRE_MINUTES,
    create_user, authenticate_user, create_access_token,
    get_current_user, require_admin, init_default_users,
)
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder

# 初始化日志
setup_logger("ticket_analysis", level="INFO", log_file="output/logs/api.log")
log = get_logger("api")

config = load_config()


# ===== 生命周期管理 =====

@asynccontextmanager
async def lifespan(app):
    log.info("=" * 50)
    log.info("工单数据分析 API 启动")
    log.info("=" * 50)
    init_default_users()
    _load_models()
    yield
    log.info("工单数据分析 API 关闭")


app = FastAPI(title="工单数据分析 API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ===== 请求日志中间件 =====

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有API请求的输入输出"""
    start = time.time()
    body = None
    if request.method in ("POST", "PUT"):
        try:
            body_bytes = await request.body()
            body = body_bytes.decode("utf-8")[:500]
        except Exception:
            body = "<unreadable>"

    response = await call_next(request)

    elapsed = round((time.time() - start) * 1000, 1)
    status = response.status_code
    level = "WARNING" if status >= 400 else "INFO"
    log.log(getattr(logging, level), f"{request.method} {request.url.path} | {status} | {elapsed}ms" + (f" | body={body[:200]}" if body else ""))

    return response


# ===== 数据模型 =====

class TicketInput(BaseModel):
    ticket_id: str = "API-001"
    created_at: str = Field(default="2025-06-01 10:00:00", description="创建时间")
    ticket_type: str = Field(default="抢修", description="工单类型: 抢修/巡检/保养/改造")
    priority: str = Field(default="高", description="优先级: 紧急/高/中/低")
    sla_minutes: int = Field(default=240, description="SLA时限(分钟)")
    region: str = Field(default="华东", description="区域")
    site_id: str = Field(default="SITE0001", description="站点编号")
    equipment_id: str = Field(default="EQ00001", description="设备编号")
    equipment_type: str = Field(default="变压器", description="设备类型")
    fault_category: str = Field(default="过热", description="故障类型")
    severity: str = Field(default="一般", description="严重程度: 严重/一般/轻微")
    equipment_age_months: int = Field(default=36, description="设备使用月数")
    total_cost: float = Field(default=2000.0, description="总成本")
    budget_limit: float = Field(default=3000.0, description="预算上限")
    is_warranty: bool = Field(default=False, description="是否在保修期")
    photo_count: int = Field(default=5, description="照片数")
    report_uploaded: bool = Field(default=True, description="报告是否上传")
    customer_signature: bool = Field(default=True, description="客户是否签字")
    attachment_count: int = Field(default=3, description="附件数")
    is_reopened: bool = Field(default=False, description="是否重开")
    reopen_within_days: Optional[int] = Field(default=None, description="重开天数")
    customer_complaint: bool = Field(default=False, description="是否投诉")
    customer_satisfaction: Optional[int] = Field(default=4, description="客户满意度1-5")
    qc_audit_result: Optional[str] = Field(default="合规", description="质检结果")
    technician_level: str = Field(default="中", description="技术员等级: 初/中/高/持证")
    technician_workload_today: int = Field(default=3, description="技术员当日工作量")
    dispatched_at: str = Field(default="2025-06-01 10:10:00")
    accepted_at: str = Field(default="2025-06-01 10:20:00")
    arrived_at: str = Field(default="2025-06-01 11:00:00")
    repair_started_at: str = Field(default="2025-06-01 11:10:00")
    repair_finished_at: str = Field(default="2025-06-01 12:30:00")
    closed_at: str = Field(default="2025-06-01 13:00:00")


class BatchTicketInput(BaseModel):
    tickets: list[TicketInput]


class InventoryForecastInput(BaseModel):
    material_id: str = Field(description="物料编号")
    site_id: str = Field(description="站点编号")
    forecast_days: int = Field(default=30, description="预测天数")


class InventoryPlanInput(BaseModel):
    material_id: str = Field(description="物料编号")
    site_id: str = Field(description="站点编号")
    current_stock: float = Field(description="当前库存")
    avg_daily_demand: float = Field(description="日均需求")
    std_daily_demand: float = Field(default=5.0, description="日需求标准差")
    lead_time_days: int = Field(default=7, description="补货周期(天)")
    service_level: float = Field(default=0.95, description="服务水平")


class AnomalyResult(BaseModel):
    ticket_id: str
    anomaly_label: int
    anomaly_score: float
    anomaly_reasons: list[dict]


class RiskResult(BaseModel):
    ticket_id: str
    risk_score: float
    risk_level: str
    final_risk_prob: float
    risk_dimensions: dict
    risk_explanation: str


# ===== 模型缓存 =====

_models = {}


def _load_models():
    """懒加载训练好的模型"""
    if _models:
        return _models

    log.info("开始加载训练数据并训练模型...")
    t0 = time.time()
    from anomaly_detection import prepare_features as af_prepare
    from risk_scoring import build_lr_features as lr_prepare

    # 加载全量数据用于训练
    anomaly_df = pd.read_csv("data/raw/ticket_main.csv", parse_dates=[
        "created_at", "dispatched_at", "accepted_at", "arrived_at",
        "repair_started_at", "repair_finished_at", "closed_at"
    ])
    risk_df = anomaly_df.copy()

    # 异常检测模型
    X_anom, feat_names, scaler_anom = af_prepare(anomaly_df)
    ad_config = config["anomaly_detection"]
    from sklearn.ensemble import IsolationForest
    from sklearn.neighbors import LocalOutlierFactor

    if_model = IsolationForest(
        contamination=ad_config["contamination"],
        n_estimators=ad_config["n_estimators"],
        random_state=42, n_jobs=-1,
    )
    if_model.fit(X_anom)

    # 风险评分模型
    X_risk, risk_feat_names = lr_prepare(risk_df)
    rs_config = config["risk_scoring"]
    thresholds = rs_config["risk_levels"]

    # 规则评分获取标签
    dim_scores_list = []
    for _, row in risk_df.iterrows():
        dim_scores_list.append(rule_based_score(row.to_dict()))
    dim_df = pd.DataFrame(dim_scores_list)
    composite = [compute_composite_score(d, rs_config["weights"]) for d in dim_scores_list]
    median_score = pd.Series(composite).median()
    high_threshold = max(median_score * 1.5, thresholds["high"] * 0.5)
    y_risk = (pd.Series(composite) >= high_threshold).astype(int)

    scaler_risk = StandardScaler()
    X_risk_scaled = scaler_risk.fit_transform(X_risk)

    lr_model = LogisticRegression(
        C=rs_config["lr_c"], max_iter=rs_config["lr_max_iter"],
        random_state=42, class_weight="balanced",
    )
    lr_model.fit(X_risk_scaled, y_risk)

    mlp_model = MLPClassifier(
        hidden_layer_sizes=(64, 32), activation="relu",
        max_iter=500, random_state=42, early_stopping=True,
        validation_fraction=0.15,
    )
    sample_weights = np.where(y_risk == 1, (len(y_risk) - y_risk.sum()) / y_risk.sum(), 1.0)
    mlp_model.fit(X_risk_scaled, y_risk, sample_weight=sample_weights)

    _models.update({
        "if_model": if_model,
        "feat_names": feat_names,
        "scaler_anom": scaler_anom,
        "lr_model": lr_model,
        "mlp_model": mlp_model,
        "risk_feat_names": risk_feat_names,
        "scaler_risk": scaler_risk,
        "thresholds": thresholds,
        "weights": rs_config["weights"],
    })
    elapsed = round(time.time() - t0, 2)
    log.info(f"模型加载完成! 耗时 {elapsed}s (异常检测+风险评分模型)")
    return _models


def _ticket_to_df(ticket: TicketInput) -> pd.DataFrame:
    """将单条工单转为DataFrame"""
    row = ticket.model_dump()
    row["dispatched_at"] = pd.to_datetime(row["dispatched_at"])
    row["accepted_at"] = pd.to_datetime(row["accepted_at"])
    row["arrived_at"] = pd.to_datetime(row["arrived_at"])
    row["repair_started_at"] = pd.to_datetime(row["repair_started_at"])
    row["repair_finished_at"] = pd.to_datetime(row["repair_finished_at"])
    row["closed_at"] = pd.to_datetime(row["closed_at"])
    row["created_at"] = pd.to_datetime(row["created_at"])
    row["reopen_within_days"] = row.get("reopen_within_days") or 0
    row["customer_satisfaction"] = row.get("customer_satisfaction") or 3
    return pd.DataFrame([row])


def _predict_anomaly(ticket: TicketInput, models: dict) -> dict:
    """预测单条工单的异常"""
    t0 = time.time()
    df = _ticket_to_df(ticket)

    # 特征工程（复用训练时的逻辑）
    df = compute_time_features(df)
    for col in ["is_reopened", "customer_complaint", "report_uploaded", "customer_signature", "is_warranty"]:
        if col in df.columns:
            df[col] = df[col].astype(int)

    cat_cols = ["ticket_type", "priority", "region", "equipment_type", "fault_category", "severity"]
    for col in cat_cols:
        if col in df.columns:
            le = LabelEncoder()
            df[f"{col}_enc"] = le.fit_transform(df[col].astype(str))

    available = [c for c in models["feat_names"] if c in df.columns]
    X = df[available].fillna(0)

    # 补齐缺失特征
    for c in models["feat_names"]:
        if c not in X.columns:
            X[c] = 0
    X = X[models["feat_names"]]

    X_scaled = models["scaler_anom"].transform(X)

    # Isolation Forest 预测
    label = models["if_model"].predict(X_scaled)[0]
    score = models["if_model"].decision_function(X_scaled)[0]
    score_norm = round(float(1 - (score - (-0.5)) / (0.5 - (-0.5))), 4)
    score_norm = max(0, min(1, score_norm))

    # 异常原因
    reasons = analyze_anomaly_reasons(df, X.values, models["feat_names"], None, top_n=3)

    elapsed = round((time.time() - t0) * 1000, 1)
    result = {
        "ticket_id": ticket.ticket_id,
        "anomaly_label": 1 if label == -1 else 0,
        "anomaly_score": score_norm,
        "anomaly_reasons": reasons[0] if reasons else [],
    }
    log.info(f"异常检测 | {ticket.ticket_id} | label={result['anomaly_label']} score={result['anomaly_score']} | {elapsed}ms")
    return result


def _predict_risk(ticket: TicketInput, models: dict) -> dict:
    """预测单条工单的风险"""
    t0 = time.time()
    df = _ticket_to_df(ticket)

    # 规则评分
    dim_scores = rule_based_score(ticket.model_dump())
    composite = compute_composite_score(dim_scores, models["weights"])

    # 逻辑回归 + 神经网络
    X_risk, _ = build_lr_features(df)
    for c in models["risk_feat_names"]:
        if c not in X_risk.columns:
            X_risk[c] = 0
    X_risk = X_risk[models["risk_feat_names"]].fillna(0)
    X_scaled = models["scaler_risk"].transform(X_risk)

    lr_prob = float(models["lr_model"].predict_proba(X_scaled)[0][1])
    nn_prob = float(models["mlp_model"].predict_proba(X_scaled)[0][1])

    # 融合
    final_prob = round(0.3 * composite + 0.35 * lr_prob + 0.35 * nn_prob, 4)

    # 风险等级
    thresholds = models["thresholds"]
    if composite >= thresholds["high"]:
        level = "high"
    elif composite >= thresholds["medium"]:
        level = "medium"
    else:
        level = "low"

    # 风险解释
    top_dims = sorted(dim_scores.items(), key=lambda x: x[1], reverse=True)[:3]
    explanation = "; ".join([f"{d}({v:.2f})" for d, v in top_dims if v > 0.1])

    elapsed = round((time.time() - t0) * 1000, 1)
    result = {
        "ticket_id": ticket.ticket_id,
        "risk_score": round(composite, 4),
        "risk_level": level,
        "final_risk_prob": final_prob,
        "risk_dimensions": {k: round(v, 4) for k, v in dim_scores.items()},
        "risk_explanation": explanation,
    }
    log.info(f"风险评分 | {ticket.ticket_id} | score={result['risk_score']} level={result['risk_level']} prob={result['final_risk_prob']} | {elapsed}ms")
    return result


def _load_inventory_data():
    """加载库存历史数据"""
    inv = pd.read_csv("data/raw/inventory_daily.csv", parse_dates=["date"])
    return inv


def _predict_inventory_forecast(req: InventoryForecastInput) -> dict:
    """库存需求预测"""
    t0 = time.time()
    from inventory_forecast import prepare_series, forecast_prophet, forecast_arima, forecast_lgbm, ensemble_forecast

    inv = _load_inventory_data()
    series = prepare_series(inv, req.material_id, req.site_id)

    if len(series) < 30:
        log.warning(f"库存预测数据不足 | {req.material_id}@{req.site_id} | 仅{len(series)}天")
        raise HTTPException(status_code=400, detail=f"数据不足: {req.material_id}@{req.site_id} 仅有{len(series)}天数据，需要至少30天")

    log.info(f"库存预测开始 | {req.material_id}@{req.site_id} | {len(series)}天历史 → {req.forecast_days}天预测")
    forecast_days = req.forecast_days
    prophet_f = forecast_prophet(series, forecast_days, config)
    arima_f = forecast_arima(series, forecast_days, config)
    lgbm_f = forecast_lgbm(series, forecast_days, config)

    ensemble_f = ensemble_forecast(prophet_f, arima_f, lgbm_f)

    avg_daily = float(series["daily_consumed"].mean())
    std_daily = float(series["daily_consumed"].std())
    current_stock = float(series["stock_on_hand"].iloc[-1])

    elapsed = round(time.time() - t0, 2)
    total = round(float(ensemble_f["forecast"].sum()), 1)
    log.info(f"库存预测完成 | {req.material_id}@{req.site_id} | 总需求={total} 日均={round(float(ensemble_f['forecast'].mean()), 2)} | {elapsed}s")

    return {
        "material_id": req.material_id,
        "site_id": req.site_id,
        "history_days": len(series),
        "current_stock": current_stock,
        "avg_daily_demand": round(avg_daily, 2),
        "std_daily_demand": round(std_daily, 2),
        "forecast": [
            {"date": str(row["date"].date()), "forecast": round(row["forecast"], 2),
             "lower": round(row["lower"], 2), "upper": round(row["upper"], 2)}
            for _, row in ensemble_f.iterrows()
        ],
        "forecast_total": total,
        "forecast_avg": round(float(ensemble_f["forecast"].mean()), 2),
    }


def _compute_inventory_plan(req: InventoryPlanInput) -> dict:
    """计算库存计划"""
    import math

    z_scores = {0.90: 1.28, 0.95: 1.65, 0.99: 2.33}
    z = z_scores.get(req.service_level, 1.65)

    safety_stock = round(z * req.std_daily_demand * math.sqrt(req.lead_time_days), 1)
    reorder_point = round(req.avg_daily_demand * req.lead_time_days + safety_stock, 1)
    days_until_stockout = round(req.current_stock / max(req.avg_daily_demand, 0.1), 1)
    need_reorder = req.current_stock < reorder_point
    recommended_qty = round(max(0, reorder_point - req.current_stock + safety_stock), 1) if need_reorder else 0

    log.info(f"库存计划 | {req.material_id}@{req.site_id} | 库存={req.current_stock} 安全库存={safety_stock} 再订货点={reorder_point} 可售={days_until_stockout}天 需补货={need_reorder}")

    return {
        "material_id": req.material_id,
        "site_id": req.site_id,
        "current_stock": req.current_stock,
        "avg_daily_demand": req.avg_daily_demand,
        "std_daily_demand": req.std_daily_demand,
        "lead_time_days": req.lead_time_days,
        "service_level": req.service_level,
        "safety_stock": safety_stock,
        "reorder_point": reorder_point,
        "days_until_stockout": days_until_stockout,
        "need_reorder": need_reorder,
        "recommended_reorder_qty": recommended_qty,
    }


# ===== API 端点 =====


@app.get("/")
def root():
    return {"message": "工单数据分析 API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "models_loaded": bool(_models)}


# ===== 鉴权端点 =====

@app.post("/auth/register", response_model=TokenResponse)
def register(user: UserCreate):
    """注册新用户"""
    create_user(user.username, user.password, user.role)
    token = create_access_token(user.username, user.role)
    return TokenResponse(
        access_token=token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        username=user.username,
        role=user.role,
    )


@app.post("/auth/login", response_model=TokenResponse)
def login(creds: UserLogin):
    """用户登录，返回 JWT Token"""
    user = authenticate_user(creds.username, creds.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user["username"], user["role"])
    return TokenResponse(
        access_token=token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        username=user["username"],
        role=user["role"],
    )


@app.get("/auth/me")
def get_me(user: Annotated[dict, Depends(get_current_user)]):
    """获取当前用户信息"""
    return {"username": user["username"], "role": user["role"]}


# ===== 业务端点（需鉴权）=====

@app.post("/api/anomaly", response_model=AnomalyResult)
def detect_anomaly(ticket: TicketInput, user: Annotated[dict, Depends(get_current_user)]):
    """异常检测：输入工单数据，返回异常标签和分数"""
    log.info(f"接口调用 | /api/anomaly | user={user['username']}")
    models = _load_models()
    return _predict_anomaly(ticket, models)


@app.post("/api/risk", response_model=RiskResult)
def score_risk(ticket: TicketInput, user: Annotated[dict, Depends(get_current_user)]):
    """风险评分：输入工单数据，返回风险概率和等级"""
    log.info(f"接口调用 | /api/risk | user={user['username']}")
    models = _load_models()
    return _predict_risk(ticket, models)


@app.post("/api/analyze")
def analyze_ticket(ticket: TicketInput, user: Annotated[dict, Depends(get_current_user)]):
    """综合分析：同时返回异常检测和风险评分"""
    log.info(f"接口调用 | /api/analyze | user={user['username']}")
    models = _load_models()
    anomaly = _predict_anomaly(ticket, models)
    risk = _predict_risk(ticket, models)
    return {"anomaly": anomaly, "risk": risk}


@app.post("/api/batch")
def batch_analyze(batch: BatchTicketInput, user: Annotated[dict, Depends(get_current_user)]):
    """批量分析：一次提交多条工单"""
    log.info(f"接口调用 | /api/batch | user={user['username']} | count={len(batch.tickets)}")
    models = _load_models()
    results = []
    for ticket in batch.tickets:
        anomaly = _predict_anomaly(ticket, models)
        risk = _predict_risk(ticket, models)
        results.append({"anomaly": anomaly, "risk": risk})
    return {"count": len(results), "results": results}


@app.post("/api/inventory/forecast")
def inventory_forecast(req: InventoryForecastInput, user: Annotated[dict, Depends(get_current_user)]):
    """库存需求预测：预测指定物料-站点的未来需求"""
    log.info(f"接口调用 | /api/inventory/forecast | user={user['username']}")
    return _predict_inventory_forecast(req)


@app.post("/api/inventory/plan")
def inventory_plan(req: InventoryPlanInput, user: Annotated[dict, Depends(get_current_user)]):
    """库存计划：计算安全库存、再订货点、是否需补货"""
    log.info(f"接口调用 | /api/inventory/plan | user={user['username']}")
    return _compute_inventory_plan(req)


@app.post("/api/inventory/batch-plan")
def inventory_batch_plan(reqs: list[InventoryPlanInput], user: Annotated[dict, Depends(get_current_user)]):
    """批量库存计划：一次计算多个物料-站点的库存计划"""
    log.info(f"接口调用 | /api/inventory/batch-plan | user={user['username']} | count={len(reqs)}")
    return {"count": len(reqs), "results": [_compute_inventory_plan(r) for r in reqs]}


@app.get("/api/inventory/materials")
def list_materials(user: Annotated[dict, Depends(get_current_user)]):
    """列出所有可用的物料-站点组合"""
    log.info(f"接口调用 | /api/inventory/materials | user={user['username']}")
    inv = _load_inventory_data()
    combos = inv.groupby(["material_id", "site_id"]).agg(
        days=("date", "count"),
        avg_stock=("stock_on_hand", "mean"),
        avg_consumed=("daily_consumed", "mean"),
    ).reset_index()
    combos["avg_stock"] = combos["avg_stock"].round(0).astype(int)
    combos["avg_consumed"] = combos["avg_consumed"].round(1)
    return {"count": len(combos), "materials": combos.to_dict("records")}


# ===== 管理员端点 =====

@app.get("/admin/users")
def list_users(user: Annotated[dict, Depends(require_admin)]):
    """列出所有用户（仅管理员）"""
    from auth import _load_users
    users = _load_users()
    return {"count": len(users), "users": [{"username": u, "role": v["role"], "created_at": v.get("created_at")} for u, v in users.items()]}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

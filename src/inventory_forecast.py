"""库存预测模块 - Prophet + ARIMA + LightGBM"""
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from pathlib import Path
import warnings

warnings.filterwarnings("ignore")

try:
    from prophet import Prophet
    HAS_PROPHET = True
except ImportError:
    HAS_PROPHET = False
    print("  [WARN] Prophet未安装，跳过Prophet预测")

try:
    from statsmodels.tsa.arima.model import ARIMA as ARIMA_MODEL
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False
    print("  [WARN] statsmodels未安装，跳过ARIMA预测")

try:
    import lightgbm as lgb
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False
    print("  [WARN] LightGBM未安装，跳过LGBM预测")

from utils import load_config, save_results, print_summary


def prepare_series(df, material_id, site_id):
    """提取单个物料-站点的时间序列"""
    mask = (df["material_id"] == material_id) & (df["site_id"] == site_id)
    sub = df[mask].sort_values("date").copy()
    sub["date"] = pd.to_datetime(sub["date"])
    sub = sub.set_index("date")
    full_idx = pd.date_range(sub.index.min(), sub.index.max(), freq="D")
    sub = sub.reindex(full_idx, fill_value=0)
    return sub


def forecast_prophet(series, forecast_days, config):
    """Prophet时序预测"""
    if not HAS_PROPHET:
        return None

    df_p = pd.DataFrame({"ds": series.index, "y": series["daily_consumed"].values})
    params = config["inventory_forecast"]["prophet_params"]

    model = Prophet(
        changepoint_prior_scale=params["changepoint_prior_scale"],
        seasonality_prior_scale=params["seasonality_prior_scale"],
        yearly_seasonality=True,
        weekly_seasonality=True,
    )
    model.fit(df_p)

    future = model.make_future_dataframe(periods=forecast_days)
    pred = model.predict(future)
    forecast = pred[pred["ds"] > series.index.max()][["ds", "yhat", "yhat_lower", "yhat_upper"]]
    forecast.columns = ["date", "forecast", "lower", "upper"]
    forecast["model"] = "prophet"
    return forecast


def forecast_arima(series, forecast_days, config):
    """ARIMA时序预测"""
    if not HAS_STATSMODELS:
        return None

    order = tuple(config["inventory_forecast"]["arima_order"])
    y = series["daily_consumed"].values

    try:
        model = ARIMA_MODEL(y, order=order)
        fitted = model.fit()
        pred = fitted.forecast(steps=forecast_days)
        pred = np.maximum(pred, 0)

        last_date = series.index.max()
        dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=forecast_days, freq="D")

        return pd.DataFrame({
            "date": dates, "forecast": pred,
            "lower": pred * 0.8, "upper": pred * 1.2,
            "model": "arima",
        })
    except Exception as e:
        print(f"  ARIMA失败: {e}")
        return None


def forecast_lgbm(series, forecast_days, config):
    """LightGBM回归预测（时序特征工程）"""
    if not HAS_LGBM:
        return None

    df = series[["daily_consumed"]].copy()
    df["dayofweek"] = df.index.dayofweek
    df["month"] = df.index.month
    df["dayofyear"] = df.index.dayofyear
    df["lag_1"] = df["daily_consumed"].shift(1)
    df["lag_7"] = df["daily_consumed"].shift(7)
    df["lag_14"] = df["daily_consumed"].shift(14)
    df["rolling_mean_7"] = df["daily_consumed"].rolling(7).mean()
    df["rolling_mean_14"] = df["daily_consumed"].rolling(14).mean()
    df = df.dropna()

    feature_cols = ["dayofweek", "month", "dayofyear", "lag_1", "lag_7", "lag_14",
                    "rolling_mean_7", "rolling_mean_14"]
    X = df[feature_cols]
    y = df["daily_consumed"]

    params = config["inventory_forecast"]["lgbm_params"]
    model = lgb.LGBMRegressor(
        n_estimators=params["n_estimators"],
        learning_rate=params["learning_rate"],
        max_depth=params["max_depth"],
        num_leaves=params["num_leaves"],
        random_state=42, verbosity=-1,
    )
    model.fit(X, y)

    # 递归预测
    last_date = series.index.max()
    dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=forecast_days, freq="D")
    forecasts = []
    hist = series["daily_consumed"].values.copy()

    for i, d in enumerate(dates):
        row = {
            "dayofweek": d.dayofweek, "month": d.month, "dayofyear": d.dayofyear,
            "lag_1": hist[-1] if len(hist) > 0 else 0,
            "lag_7": hist[-7] if len(hist) >= 7 else 0,
            "lag_14": hist[-14] if len(hist) >= 14 else 0,
            "rolling_mean_7": np.mean(hist[-7:]) if len(hist) >= 7 else np.mean(hist),
            "rolling_mean_14": np.mean(hist[-14:]) if len(hist) >= 14 else np.mean(hist),
        }
        pred = max(0, model.predict(pd.DataFrame([row])[feature_cols])[0])
        forecasts.append(pred)
        hist = np.append(hist, pred)

    forecasts = np.array(forecasts)
    return pd.DataFrame({
        "date": dates, "forecast": forecasts,
        "lower": forecasts * 0.85, "upper": forecasts * 1.15,
        "model": "lightgbm",
    })


def compute_safety_stock(avg_daily, std_daily, lead_time_days, z_score):
    """安全库存 = Z * σ * √(LT)"""
    return round(z_score * std_daily * np.sqrt(lead_time_days), 1)


def compute_reorder_point(avg_daily, lead_time_days, safety_stock):
    """再订货点 = 平均日需求 * 补货周期 + 安全库存"""
    return round(avg_daily * lead_time_days + safety_stock, 1)


def ensemble_forecast(prophet_f, arima_f, lgbm_f):
    """多模型集成：简单平均"""
    forecasts = [f for f in [prophet_f, arima_f, lgbm_f] if f is not None]
    if not forecasts:
        return None
    if len(forecasts) == 1:
        return forecasts[0]

    merged = forecasts[0][["date"]].copy()
    for i, f in enumerate(forecasts):
        merged[f"model_{i}"] = f["forecast"].values

    model_cols = [c for c in merged.columns if c.startswith("model_")]
    merged["forecast"] = merged[model_cols].mean(axis=1)
    merged["lower"] = merged[model_cols].min(axis=1)
    merged["upper"] = merged[model_cols].max(axis=1)
    merged["model"] = "ensemble"
    return merged[["date", "forecast", "lower", "upper", "model"]]


def run(config=None):
    if config is None:
        config = load_config()

    fc_config = config["inventory_forecast"]

    print("\n[库存预测] 加载数据...")
    inv_path = Path(config["data"]["raw_dir"]) / "inventory_daily.csv"
    inv = pd.read_csv(inv_path, parse_dates=["date"])

    mat_path = Path(config["data"]["raw_dir"]) / "ticket_materials.csv"
    materials = pd.read_csv(mat_path)

    # 取消耗量最大的前10个物料-站点组合
    top_combos = (
        materials.groupby(["material_id"])["qty_used"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .index.tolist()
    )

    forecast_days = fc_config["forecast_days"]
    z_score = 1.65  # 95% 服务水平
    lead_time = 7   # 默认7天补货周期

    all_forecasts = []
    all_inventory_plan = []

    for mat_id in top_combos:
        mat_sites = inv[inv["material_id"] == mat_id]["site_id"].unique()
        for site_id in mat_sites[:5]:  # 每物料最多5个站点
            series = prepare_series(inv, mat_id, site_id)
            if len(series) < 30:
                continue

            avg_daily = series["daily_consumed"].mean()
            std_daily = series["daily_consumed"].std()

            prophet_f = forecast_prophet(series, forecast_days, config)
            arima_f = forecast_arima(series, forecast_days, config)
            lgbm_f = forecast_lgbm(series, forecast_days, config)

            ensemble_f = ensemble_forecast(prophet_f, arima_f, lgbm_f)
            if ensemble_f is None:
                continue

            ensemble_f["material_id"] = mat_id
            ensemble_f["site_id"] = site_id
            all_forecasts.append(ensemble_f)

            safety_stock = compute_safety_stock(avg_daily, std_daily, lead_time, z_score)
            reorder_point = compute_reorder_point(avg_daily, lead_time, safety_stock)

            current_stock = series["stock_on_hand"].iloc[-1]
            days_until_stockout = current_stock / max(avg_daily, 0.1)

            all_inventory_plan.append({
                "material_id": mat_id,
                "site_id": site_id,
                "current_stock": current_stock,
                "avg_daily_demand": round(avg_daily, 2),
                "std_daily_demand": round(std_daily, 2),
                "safety_stock": safety_stock,
                "reorder_point": reorder_point,
                "days_until_stockout": round(days_until_stockout, 1),
                "need_reorder": current_stock < reorder_point,
                "recommended_reorder_qty": max(0, round(reorder_point - current_stock + safety_stock, 1)),
                "forecast_avg_daily": round(ensemble_f["forecast"].mean(), 2),
                "forecast_total": round(ensemble_f["forecast"].sum(), 1),
            })

    if all_forecasts:
        forecast_df = pd.concat(all_forecasts, ignore_index=True)
        save_results(forecast_df, config, "inventory_forecast_results.csv")
        print_summary(forecast_df, "库存预测结果")

    if all_inventory_plan:
        plan_df = pd.DataFrame(all_inventory_plan)
        save_results(plan_df, config, "inventory_plan_results.csv")
        print(f"\n  需要补货的物料-站点: {plan_df['need_reorder'].sum()}/{len(plan_df)}")
        print(f"  平均安全库存: {plan_df['safety_stock'].mean():.1f}")

    return all_forecasts, all_inventory_plan


if __name__ == "__main__":
    run()

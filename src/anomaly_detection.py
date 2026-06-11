"""异常检测模块 - Isolation Forest + LOF + 集成"""
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.decomposition import PCA
from pathlib import Path

from utils import load_config, load_data, compute_time_features, save_results, print_summary


FEATURE_COLS = [
    "total_cost", "budget_limit", "sla_minutes",
    "photo_count", "attachment_count", "equipment_age_months",
    "technician_workload_today", "reopen_within_days",
    "customer_satisfaction",
    "dispatch_delay", "accept_delay", "arrival_delay",
    "repair_duration", "total_duration", "response_time",
]


def prepare_features(df):
    """特征工程：编码分类变量 + 标准化"""
    df = df.copy()
    df = compute_time_features(df)

    if "reopen_within_days" in df.columns:
        df["reopen_within_days"] = df["reopen_within_days"].fillna(0)
    if "customer_satisfaction" in df.columns:
        df["customer_satisfaction"] = df["customer_satisfaction"].fillna(3)

    for col in ["is_reopened", "customer_complaint", "report_uploaded", "customer_signature", "is_warranty"]:
        if col in df.columns:
            df[col] = df[col].astype(int)

    cat_cols = ["ticket_type", "priority", "region", "equipment_type", "fault_category", "severity"]
    le_dict = {}
    for col in cat_cols:
        if col in df.columns:
            le = LabelEncoder()
            df[f"{col}_enc"] = le.fit_transform(df[col].astype(str))
            le_dict[col] = le
            if f"{col}_enc" not in FEATURE_COLS:
                FEATURE_COLS.append(f"{col}_enc")

    available = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available].fillna(0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    return X_scaled, available, scaler


def detect_isolation_forest(X, contamination=0.05, n_estimators=200):
    """Isolation Forest 异常检测"""
    model = IsolationForest(
        contamination=contamination,
        n_estimators=n_estimators,
        random_state=42,
        n_jobs=-1,
    )
    labels = model.fit_predict(X)  # 1=正常, -1=异常
    scores = model.decision_function(X)  # 越小越异常
    # 归一化到 [0,1]，1=最异常
    scores_norm = 1 - (scores - scores.min()) / (scores.max() - scores.min() + 1e-10)
    return (labels == -1).astype(int), scores_norm, model


def detect_lof(X, n_neighbors=20, contamination=0.05):
    """Local Outlier Factor 异常检测"""
    model = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=contamination)
    labels = model.fit_predict(X)
    scores = -model.negative_outlier_factor_  # 越大越异常
    scores_norm = (scores - scores.min()) / (scores.max() - scores.min() + 1e-10)
    return (labels == -1).astype(int), scores_norm, model


def ensemble_detect(X, contamination=0.05, n_estimators=200):
    """集成异常检测：多模型投票 + 分数融合"""
    if_labels, if_scores, if_model = detect_isolation_forest(X, contamination, n_estimators)
    lof_labels, lof_scores, lof_model = detect_lof(X, contamination=contamination)

    # 加权分数融合 (IF:0.6, LOF:0.4)
    ensemble_scores = 0.6 * if_scores + 0.4 * lof_scores

    # 投票：>=2个模型标记为异常才认定
    vote_matrix = np.column_stack([if_labels, lof_labels])
    vote_sum = vote_matrix.sum(axis=1)
    ensemble_labels = (vote_sum >= 1).astype(int)  # 至少1个模型认为异常

    return ensemble_labels, ensemble_scores, {
        "if_labels": if_labels, "if_scores": if_scores,
        "lof_labels": lof_labels, "lof_scores": lof_scores,
    }


def analyze_anomaly_reasons(df, X, feature_names, model, top_n=10):
    """异常原因分析：基于特征重要性和偏差"""
    reasons = []
    if hasattr(model, "feature_importances_"):
        importance = model.feature_importances_
    else:
        importance = np.ones(len(feature_names)) / len(feature_names)

    mean_vals = X.mean(axis=0)
    std_vals = X.std(axis=0) + 1e-10

    for idx in df.index:
        row = X[idx]
        z_scores = np.abs((row - mean_vals) / std_vals)
        weighted_dev = z_scores * importance
        top_indices = weighted_dev.argsort()[::-1][:top_n]
        row_reasons = [
            {"feature": feature_names[i], "deviation": round(float(z_scores[i]), 3),
             "importance": round(float(importance[i]), 4),
             "value": round(float(row[i]), 3)}
            for i in top_indices if z_scores[i] > 1.5
        ]
        reasons.append(row_reasons[:3])
    return reasons


def run(config=None):
    if config is None:
        config = load_config()

    print("\n[异常检测] 加载数据...")
    df = load_data(config, "ticket_main")

    print("[异常检测] 特征工程...")
    X, feature_names, scaler = prepare_features(df)

    print("[异常检测] 运行集成异常检测...")
    ad_config = config["anomaly_detection"]
    labels, scores, sub_models = ensemble_detect(
        X,
        contamination=ad_config["contamination"],
        n_estimators=ad_config["n_estimators"],
    )

    df["anomaly_label"] = labels
    df["anomaly_score"] = np.round(scores, 4)
    df["anomaly_model_if"] = sub_models["if_labels"]
    df["anomaly_model_lof"] = sub_models["lof_labels"]

    print("[异常检测] 分析异常原因...")
    reasons = analyze_anomaly_reasons(df, X, feature_names, None, top_n=ad_config["top_n_features"])
    df["anomaly_reasons"] = [str(r) for r in reasons]

    output_cols = [
        "ticket_id", "anomaly_label", "anomaly_score",
        "anomaly_model_if", "anomaly_model_lof", "anomaly_reasons",
        "created_at", "ticket_type", "priority", "region",
        "equipment_type", "fault_category", "total_cost",
    ]
    result = df[output_cols].copy()
    save_results(result, config, "anomaly_detection_results.csv")
    print_summary(result, "异常检测结果")

    # PCA 可视化数据
    pca = PCA(n_components=2, random_state=42)
    X_2d = pca.fit_transform(X)
    viz = pd.DataFrame({
        "ticket_id": df["ticket_id"],
        "pc1": X_2d[:, 0], "pc2": X_2d[:, 1],
        "anomaly_label": labels,
        "anomaly_score": scores,
    })
    save_results(viz, config, "anomaly_pca_visualization.csv")

    return result


if __name__ == "__main__":
    run()

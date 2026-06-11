"""风险评分模块 - 规则评分 + 逻辑回归 + 神经网络"""
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import cross_val_score
from sklearn.neural_network import MLPClassifier
from pathlib import Path

from utils import load_config, load_data, compute_time_features, save_results, print_summary


RISK_DIMENSIONS = ["compliance", "sla", "cost", "quality", "equipment"]


def rule_based_score(row):
    """基于业务规则的5维度评分，每维0-1"""
    scores = {}

    # 合规维度
    compliance_issues = 0
    if row.get("report_uploaded") == False or row.get("report_uploaded") == 0:
        compliance_issues += 1
    if row.get("customer_signature") == False or row.get("customer_signature") == 0:
        compliance_issues += 1
    if row.get("photo_count", 0) < 3:
        compliance_issues += 1
    if row.get("qc_audit_result") == "不合规":
        compliance_issues += 2
    scores["compliance"] = min(1.0, compliance_issues / 4.0)

    # SLA维度
    total_min = row.get("total_duration", 0) or 0
    sla = row.get("sla_minutes", 480) or 480
    if sla > 0:
        ratio = total_min / sla
        scores["sla"] = min(1.0, max(0, (ratio - 0.5) / 1.5))
    else:
        scores["sla"] = 0.0

    # 成本维度
    cost = row.get("total_cost", 0) or 0
    budget = row.get("budget_limit", 1) or 1
    if budget > 0:
        cost_ratio = cost / budget
        scores["cost"] = min(1.0, max(0, (cost_ratio - 0.5) / 1.0))
    else:
        scores["cost"] = 0.5

    # 质量维度
    quality_issues = 0
    if row.get("is_reopened"):
        quality_issues += 2
    if row.get("customer_complaint"):
        quality_issues += 2
    sat = row.get("customer_satisfaction")
    if sat is not None and sat <= 2:
        quality_issues += 1
    scores["quality"] = min(1.0, quality_issues / 4.0)

    # 设备维度
    equip_risk = 0
    age = row.get("equipment_age_months", 0) or 0
    if age > 84:
        equip_risk += 1
    elif age > 60:
        equip_risk += 0.5
    if row.get("fault_category") in ["老化", "机械故障"]:
        equip_risk += 0.5
    if row.get("severity") == "严重":
        equip_risk += 1
    scores["equipment"] = min(1.0, equip_risk / 2.5)

    return scores


def compute_composite_score(dim_scores, weights):
    """加权合成风险分"""
    total = sum(dim_scores.get(d, 0) * weights.get(d, 0) for d in RISK_DIMENSIONS)
    return round(total, 4)


def assign_risk_level(score, thresholds):
    if score >= thresholds["high"]:
        return "high"
    elif score >= thresholds["medium"]:
        return "medium"
    return "low"


def build_lr_features(df):
    """构建逻辑回归特征"""
    df = df.copy()
    df = compute_time_features(df)

    df["reopen_within_days"] = df["reopen_within_days"].fillna(0)
    df["customer_satisfaction"] = df["customer_satisfaction"].fillna(3)
    for col in ["is_reopened", "customer_complaint", "report_uploaded", "customer_signature", "is_warranty"]:
        if col in df.columns:
            df[col] = df[col].astype(int)

    cat_cols = ["ticket_type", "priority", "region", "equipment_type", "fault_category", "severity", "technician_level"]
    for col in cat_cols:
        if col in df.columns:
            le = LabelEncoder()
            df[f"{col}_enc"] = le.fit_transform(df[col].astype(str))

    features = [
        "total_cost", "budget_limit", "sla_minutes", "photo_count",
        "equipment_age_months", "technician_workload_today",
        "dispatch_delay", "accept_delay", "arrival_delay",
        "repair_duration", "total_duration", "response_time",
        "is_reopened", "customer_complaint", "report_uploaded",
        "customer_signature", "is_warranty", "reopen_within_days",
        "customer_satisfaction",
    ]
    enc_features = [f"{c}_enc" for c in cat_cols if f"{c}_enc" in df.columns]
    all_features = [f for f in features + enc_features if f in df.columns]

    X = df[all_features].fillna(0)
    return X, all_features


def run(config=None):
    if config is None:
        config = load_config()

    print("\n[风险评分] 加载数据...")
    df = load_data(config, "ticket_main")

    # ===== 阶段1: 规则评分 =====
    print("[风险评分] 运行规则评分...")
    rs_config = config["risk_scoring"]
    weights = rs_config["weights"]
    thresholds = rs_config["risk_levels"]

    dim_scores_list = []
    composite_scores = []
    for _, row in df.iterrows():
        dim = rule_based_score(row.to_dict())
        dim_scores_list.append(dim)
        composite_scores.append(compute_composite_score(dim, weights))

    dim_df = pd.DataFrame(dim_scores_list)
    df = pd.concat([df.reset_index(drop=True), dim_df.add_prefix("risk_dim_").reset_index(drop=True)], axis=1)
    df["risk_score"] = composite_scores
    df["risk_level"] = df["risk_score"].apply(lambda s: assign_risk_level(s, thresholds))
    df["is_risk_high"] = (df["risk_level"] == "high").astype(int)
    df["is_risk_medium"] = (df["risk_level"] == "medium").astype(int)
    df["is_risk_low"] = (df["risk_level"] == "low").astype(int)

    # ===== 阶段2: 逻辑回归 =====
    print("[风险评分] 训练逻辑回归模型...")
    X, feature_names = build_lr_features(df)
    median_score = df["risk_score"].median()
    high_threshold = max(median_score * 1.5, thresholds["high"] * 0.5)
    y = (df["risk_score"] >= high_threshold).astype(int)
    print(f"  逻辑回归标签阈值: {high_threshold:.3f} (正样本: {y.sum()}/{len(y)})")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    lr = LogisticRegression(
        C=rs_config["lr_c"], max_iter=rs_config["lr_max_iter"],
        random_state=42, class_weight="balanced",
    )
    lr.fit(X_scaled, y)

    lr_probs = lr.predict_proba(X_scaled)[:, 1]
    df["lr_risk_prob"] = np.round(lr_probs, 4)

    # 逻辑回归特征重要性
    coef = pd.Series(lr.coef_[0], index=feature_names).sort_values(key=abs, ascending=False)
    print(f"  Top风险因子(逻辑回归):")
    for feat, val in coef.head(5).items():
        print(f"    {feat}: {val:+.4f}")

    # ===== 阶段3: 神经网络 =====
    print("[风险评分] 训练神经网络模型...")
    mlp = MLPClassifier(
        hidden_layer_sizes=(64, 32), activation="relu",
        max_iter=500, random_state=42, early_stopping=True,
        validation_fraction=0.15,
    )
    sample_weights = np.where(y == 1, (len(y) - y.sum()) / y.sum(), 1.0)
    mlp.fit(X_scaled, y, sample_weight=sample_weights)
    nn_probs = mlp.predict_proba(X_scaled)[:, 1]
    df["nn_risk_prob"] = np.round(nn_probs, 4)

    # ===== 融合 =====
    df["final_risk_prob"] = np.round(
        0.3 * df["risk_score"] + 0.35 * df["lr_risk_prob"] + 0.35 * df["nn_risk_prob"], 4
    )

    # 风险因素解释
    def explain_risk(row):
        dims = {d: row[f"risk_dim_{d}"] for d in RISK_DIMENSIONS}
        top_dims = sorted(dims.items(), key=lambda x: x[1], reverse=True)[:3]
        return "; ".join([f"{d}({v:.2f})" for d, v in top_dims if v > 0.1])
    df["risk_explanation"] = df.apply(explain_risk, axis=1)

    output_cols = [
        "ticket_id", "risk_score", "risk_level", "final_risk_prob",
        "lr_risk_prob", "nn_risk_prob", "risk_explanation",
        "is_risk_high", "is_risk_medium", "is_risk_low",
        "risk_dim_compliance", "risk_dim_sla", "risk_dim_cost",
        "risk_dim_quality", "risk_dim_equipment",
        "created_at", "ticket_type", "priority", "region",
    ]
    result = df[output_cols].copy()
    save_results(result, config, "risk_scoring_results.csv")
    print_summary(result, "风险评分结果")

    # 特征重要性保存
    importance_df = pd.DataFrame({
        "feature": feature_names,
        "lr_coef": lr.coef_[0],
        "abs_coef": np.abs(lr.coef_[0]),
    }).sort_values("abs_coef", ascending=False)
    save_results(importance_df, config, "risk_feature_importance.csv")

    return result


if __name__ == "__main__":
    run()

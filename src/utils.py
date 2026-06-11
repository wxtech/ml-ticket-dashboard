"""共享工具函数"""
import pandas as pd
import numpy as np
import yaml
from pathlib import Path


def load_config(config_path="config/config.yaml"):
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_data(config, table_name):
    path = Path(config["data"]["raw_dir"]) / f"{table_name}.csv"
    df = pd.read_csv(path)
    for col in ["created_at", "dispatched_at", "accepted_at", "arrived_at",
                "repair_started_at", "repair_finished_at", "inspected_at",
                "accepted_by_customer_at", "closed_at", "last_fault_at",
                "date", "photo_taken_at"]:
        if col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception:
                pass
    return df


def compute_time_features(df):
    """计算时间差特征"""
    df = df.copy()
    time_pairs = [
        ("dispatch_delay", "created_at", "dispatched_at"),
        ("accept_delay", "dispatched_at", "accepted_at"),
        ("arrival_delay", "accepted_at", "arrived_at"),
        ("repair_duration", "repair_started_at", "repair_finished_at"),
        ("total_duration", "created_at", "closed_at"),
        ("response_time", "created_at", "arrived_at"),
    ]
    for name, start, end in time_pairs:
        if start in df.columns and end in df.columns:
            df[name] = (df[end] - df[start]).dt.total_seconds() / 60.0
    return df


def save_results(df, config, filename):
    out_dir = Path(config["data"]["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / filename, index=False)
    print(f"  -> 已保存: {out_dir / filename} ({len(df)} 行)")


def print_summary(df, title=""):
    print(f"\n{'='*60}")
    if title:
        print(f"  {title}")
        print(f"{'='*60}")
    print(f"  记录数: {len(df)}")
    if "anomaly_label" in df.columns:
        print(f"  异常数: {df['anomaly_label'].sum()} ({df['anomaly_label'].mean()*100:.1f}%)")
    if "risk_score" in df.columns:
        print(f"  平均风险分: {df['risk_score'].mean():.3f}")
        for level in ["high", "medium", "low"]:
            col = f"is_risk_{level}"
            if col in df.columns:
                print(f"  {level}风险: {df[col].sum()} ({df[col].mean()*100:.1f}%)")
    if "forecast" in df.columns:
        print(f"  预测总量: {df['forecast'].sum():.1f}")
        print(f"  预测均值: {df['forecast'].mean():.2f}/天")
    if "need_reorder" in df.columns:
        print(f"  需补货: {df['need_reorder'].sum()}/{len(df)}")
    print(f"{'='*60}")

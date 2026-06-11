"""可视化图表生成"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm

# 显式注册中文字体
_font_paths = [
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
_font_name = None
for _fp in _font_paths:
    import os
    if os.path.exists(_fp):
        fm.fontManager.addfont(_fp)
        _font_name = fm.FontProperties(fname=_fp).get_name()
        break
if _font_name:
    matplotlib.rcParams["font.sans-serif"] = [_font_name] + matplotlib.rcParams["font.sans-serif"]
else:
    matplotlib.rcParams["font.sans-serif"] = ["Noto Serif CJK SC", "Noto Sans CJK SC", "Droid Sans Fallback", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

import seaborn as sns
from pathlib import Path

OUTPUT = Path("output/charts")
OUTPUT.mkdir(parents=True, exist_ok=True)


def chart_anomaly_overview(df):
    """图1: 异常检测总览 (2x2)"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("异常检测分析", fontsize=16, fontweight="bold", y=0.98)

    # 1.1 异常分数分布
    ax = axes[0, 0]
    scores = df["anomaly_score"].astype(float)
    ax.hist(scores, bins=50, color="#4A90D9", edgecolor="white", alpha=0.85)
    ax.axvline(0.6, color="#E74C3C", linestyle="--", linewidth=2, label="阈值=0.6")
    ax.set_xlabel("异常分数")
    ax.set_ylabel("工单数")
    ax.set_title("异常分数分布")
    ax.legend()

    # 1.2 各模型异常标记对比
    ax = axes[0, 1]
    model_counts = {
        "Isolation Forest": df["anomaly_model_if"].sum(),
        "LOF": df["anomaly_model_lof"].sum(),
        "集成模型": df["anomaly_label"].sum(),
    }
    colors = ["#3498DB", "#E67E22", "#E74C3C"]
    bars = ax.bar(model_counts.keys(), model_counts.values(), color=colors, edgecolor="white", width=0.5)
    for bar, val in zip(bars, model_counts.values()):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5, str(val),
                ha="center", va="bottom", fontweight="bold", fontsize=12)
    ax.set_ylabel("异常工单数")
    ax.set_title("各模型检出异常数")

    # 1.3 异常按工单类型
    ax = axes[1, 0]
    ct = pd.crosstab(df["ticket_type"], df["anomaly_label"], normalize="index") * 100
    if 1 in ct.columns:
        ct[1].sort_values(ascending=True).plot.barh(ax=ax, color="#E74C3C", edgecolor="white")
        ax.set_xlabel("异常比例 (%)")
        ax.set_title("各工单类型异常率")
        ax.set_xlim(0, max(ct[1]) * 1.3)

    # 1.4 异常按故障类型
    ax = axes[1, 1]
    fault_anomaly = df.groupby("fault_category")["anomaly_label"].mean().sort_values(ascending=True) * 100
    fault_anomaly.plot.barh(ax=ax, color="#9B59B6", edgecolor="white")
    ax.set_xlabel("异常比例 (%)")
    ax.set_title("各故障类型异常率")
    ax.set_xlim(0, max(fault_anomaly) * 1.3)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUTPUT / "01_anomaly_overview.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  -> 01_anomaly_overview.png")


def chart_anomaly_scatter(df):
    """图2: 异常散点图 (成本 vs 修复时长)"""
    fig, ax = plt.subplots(figsize=(10, 6))
    normal = df[df["anomaly_label"] == 0]
    anomaly = df[df["anomaly_label"] == 1]

    ax.scatter(normal["total_cost"], normal.get("repair_duration", pd.Series([0]*len(normal))),
               c="#BDC3C7", alpha=0.4, s=20, label=f"正常 ({len(normal)})")
    if "repair_duration" in anomaly.columns:
        ax.scatter(anomaly["total_cost"], anomaly["repair_duration"],
                   c="#E74C3C", alpha=0.7, s=40, edgecolors="white", linewidths=0.5,
                   label=f"异常 ({len(anomaly)})")

    ax.set_xlabel("总成本 (元)")
    ax.set_ylabel("修复时长 (分钟)")
    ax.set_title("异常工单分布: 成本 vs 修复时长", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11)
    ax.set_xscale("log")
    fig.savefig(OUTPUT / "02_anomaly_scatter.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  -> 02_anomaly_scatter.png")


def chart_risk_overview(df):
    """图3: 风险评分总览 (2x2)"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("风险评分分析", fontsize=16, fontweight="bold", y=0.98)

    # 3.1 风险等级分布
    ax = axes[0, 0]
    level_counts = df["risk_level"].value_counts()
    colors_map = {"low": "#2ECC71", "medium": "#F39C12", "high": "#E74C3C"}
    order = ["low", "medium", "high"]
    vals = [level_counts.get(l, 0) for l in order]
    cols = [colors_map[l] for l in order]
    wedges, texts, autotexts = ax.pie(vals, labels=["低风险", "中风险", "高风险"],
                                       colors=cols, autopct="%1.1f%%", startangle=90,
                                       textprops={"fontsize": 11})
    ax.set_title("风险等级分布")

    # 3.2 风险分数分布
    ax = axes[0, 1]
    scores = df["risk_score"].astype(float)
    ax.hist(scores, bins=50, color="#3498DB", edgecolor="white", alpha=0.85)
    ax.axvline(0.4, color="#F39C12", linestyle="--", linewidth=2, label="中风险=0.4")
    ax.axvline(0.7, color="#E74C3C", linestyle="--", linewidth=2, label="高风险=0.7")
    ax.set_xlabel("风险分数")
    ax.set_ylabel("工单数")
    ax.set_title("风险分数分布")
    ax.legend()

    # 3.3 五维度雷达图 (Top10高风险工单平均)
    ax = axes[1, 0]
    dim_cols = ["risk_dim_compliance", "risk_dim_sla", "risk_dim_cost", "risk_dim_quality", "risk_dim_equipment"]
    labels_radar = ["合规", "SLA", "成本", "质量", "设备"]
    top10 = df.nlargest(10, "risk_score")
    avg_dims = [top10[c].mean() for c in dim_cols]
    avg_all = [df[c].mean() for c in dim_cols]

    angles = np.linspace(0, 2 * np.pi, len(labels_radar), endpoint=False).tolist()
    avg_dims += avg_dims[:1]
    avg_all += avg_all[:1]
    angles += angles[:1]

    ax = fig.add_subplot(2, 2, 3, projection="polar")
    ax.plot(angles, avg_dims, "o-", color="#E74C3C", linewidth=2, label="Top10高风险")
    ax.fill(angles, avg_dims, alpha=0.15, color="#E74C3C")
    ax.plot(angles, avg_all, "o-", color="#3498DB", linewidth=2, label="全部均值")
    ax.fill(angles, avg_all, alpha=0.1, color="#3498DB")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels_radar, fontsize=10)
    ax.set_title("风险维度雷达图", pad=20, fontsize=12, fontweight="bold")
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=9)

    # 3.4 各维度风险箱线图
    ax = axes[1, 1]
    dim_data = df[dim_cols].copy()
    dim_data.columns = labels_radar
    dim_melt = dim_data.melt(var_name="维度", value_name="分数")
    sns.boxplot(data=dim_melt, x="维度", y="分数", ax=ax,
                palette=["#3498DB", "#2ECC71", "#E74C3C", "#F39C12", "#9B59B6"])
    ax.set_title("各风险维度分数分布")
    ax.set_ylabel("风险分数")

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUTPUT / "03_risk_overview.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  -> 03_risk_overview.png")


def chart_risk_by_region(df):
    """图4: 风险按区域分布"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("风险区域分析", fontsize=14, fontweight="bold")

    # 4.1 各区域异常率+风险分
    ax = axes[0]
    region_stats = df.groupby("region").agg(
        anomaly_rate=("anomaly_label", "mean"),
        avg_risk=("risk_score", "mean"),
    ).sort_values("avg_risk", ascending=True)
    region_stats["anomaly_rate"] *= 100
    x = np.arange(len(region_stats))
    w = 0.35
    ax.barh(x - w/2, region_stats["anomaly_rate"], w, color="#E74C3C", label="异常率(%)", alpha=0.8)
    ax.barh(x + w/2, region_stats["avg_risk"] * 100, w, color="#3498DB", label="平均风险分(×100)", alpha=0.8)
    ax.set_yticks(x)
    ax.set_yticklabels(region_stats.index)
    ax.set_title("各区域异常率 vs 风险分")
    ax.legend()

    # 4.2 各区域风险等级堆叠
    ax = axes[1]
    ct = pd.crosstab(df["region"], df["risk_level"])
    for level, color in [("low", "#2ECC71"), ("medium", "#F39C12"), ("high", "#E74C3C")]:
        if level in ct.columns:
            ct[level].plot.barh(ax=ax, color=color, label={"low": "低", "medium": "中", "high": "高"}[level], alpha=0.85)
    ax.set_title("各区域风险等级分布")
    ax.legend(title="风险等级")

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(OUTPUT / "04_risk_by_region.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  -> 04_risk_by_region.png")


def chart_inventory_forecast(forecast_df):
    """图5: 库存预测趋势 (选2个典型物料)"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("库存需求预测 (30天)", fontsize=14, fontweight="bold")

    combos = forecast_df.groupby(["material_id", "site_id"]).size().reset_index().head(6)
    selected = [(combos.iloc[i]["material_id"], combos.iloc[i]["site_id"]) for i in [0, 2]]

    for idx, (mat, site) in enumerate(selected):
        ax = axes[idx]
        sub = forecast_df[(forecast_df["material_id"] == mat) & (forecast_df["site_id"] == site)].copy()
        sub["date"] = pd.to_datetime(sub["date"])
        sub = sub.sort_values("date")

        ax.fill_between(sub["date"], sub["lower"], sub["upper"], alpha=0.2, color="#3498DB", label="置信区间")
        ax.plot(sub["date"], sub["forecast"], color="#3498DB", linewidth=2, label="预测需求")
        ax.axhline(sub["forecast"].mean(), color="#E74C3C", linestyle="--", alpha=0.5, label=f"均值={sub['forecast'].mean():.1f}")
        ax.set_xlabel("日期")
        ax.set_ylabel("日需求量")
        ax.set_title(f"{mat} @ {site}")
        ax.legend(fontsize=9)
        ax.tick_params(axis="x", rotation=30)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(OUTPUT / "05_inventory_forecast.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  -> 05_inventory_forecast.png")


def chart_inventory_plan(plan_df):
    """图6: 库存计划状态"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("库存计划分析", fontsize=14, fontweight="bold")

    # 6.1 当前库存 vs 安全库存 vs 再订货点
    ax = axes[0]
    x = np.arange(len(plan_df))
    w = 0.25
    ax.bar(x - w, plan_df["current_stock"], w, color="#3498DB", label="当前库存", alpha=0.85)
    ax.bar(x, plan_df["reorder_point"], w, color="#F39C12", label="再订货点", alpha=0.85)
    ax.bar(x + w, plan_df["safety_stock"], w, color="#E74C3C", label="安全库存", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r['material_id'][-4:]}\n{r['site_id'][-4:]}" for _, r in plan_df.iterrows()],
                       fontsize=7, rotation=0)
    ax.set_ylabel("数量")
    ax.set_title("当前库存 vs 再订货点 vs 安全库存")
    ax.legend()

    # 6.2 预计可售天数
    ax = axes[1]
    colors = ["#E74C3C" if d < 90 else "#F39C12" if d < 180 else "#2ECC71" for d in plan_df["days_until_stockout"]]
    bars = ax.barh(range(len(plan_df)), plan_df["days_until_stockout"], color=colors, edgecolor="white")
    ax.set_yticks(range(len(plan_df)))
    ax.set_yticklabels([f"{r['material_id'][-4:]}@{r['site_id'][-4:]}" for _, r in plan_df.iterrows()], fontsize=8)
    ax.axvline(90, color="#E74C3C", linestyle="--", alpha=0.5, label="90天警戒线")
    ax.set_xlabel("预计可售天数")
    ax.set_title("各物料-站点库存消耗预估")
    ax.legend()

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(OUTPUT / "06_inventory_plan.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  -> 06_inventory_plan.png")


def chart_correlation(df):
    """图7: 异常分数 vs 风险分数相关性"""
    fig, ax = plt.subplots(figsize=(8, 6))
    sample = df.sample(min(500, len(df)), random_state=42)
    scatter = ax.scatter(
        sample["anomaly_score"].astype(float),
        sample["risk_score"].astype(float),
        c=sample["anomaly_label"],
        cmap="RdYlGn_r", alpha=0.5, s=30, edgecolors="white", linewidths=0.3,
    )
    ax.set_xlabel("异常分数", fontsize=12)
    ax.set_ylabel("风险分数", fontsize=12)
    ax.set_title("异常分数 vs 风险分数", fontsize=14, fontweight="bold")
    cbar = plt.colorbar(scatter, ax=ax, label="异常标签")
    cbar.set_ticks([0, 1])
    cbar.set_ticklabels(["正常", "异常"])

    corr = df["anomaly_score"].astype(float).corr(df["risk_score"].astype(float))
    ax.text(0.05, 0.95, f"相关系数: {corr:.3f}", transform=ax.transAxes,
            fontsize=11, verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    fig.savefig(OUTPUT / "07_correlation.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  -> 07_correlation.png")


def main():
    print("加载分析结果...")
    anomaly_df = pd.read_csv("output/anomaly_detection_results.csv")
    risk_df = pd.read_csv("output/risk_scoring_results.csv")
    forecast_df = pd.read_csv("output/inventory_forecast_results.csv")
    plan_df = pd.read_csv("output/inventory_plan_results.csv")

    # 合并异常+风险数据
    merged = anomaly_df.merge(risk_df[["ticket_id", "risk_score", "risk_level"]], on="ticket_id", how="left")

    print("生成图表...")
    chart_anomaly_overview(anomaly_df)
    chart_anomaly_scatter(anomaly_df)
    chart_risk_overview(risk_df)
    chart_risk_by_region(merged)
    chart_inventory_forecast(forecast_df)
    chart_inventory_plan(plan_df)
    chart_correlation(merged)

    print(f"\n全部图表已保存到 {OUTPUT}/")


if __name__ == "__main__":
    main()

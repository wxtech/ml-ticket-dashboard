"""生成交互式HTML仪表盘"""
import pandas as pd
import numpy as np
import json
from pathlib import Path


def load_results():
    base = Path("output")
    anomaly = pd.read_csv(base / "anomaly_detection_results.csv")
    risk = pd.read_csv(base / "risk_scoring_results.csv")
    pca = pd.read_csv(base / "anomaly_pca_visualization.csv")
    importance = pd.read_csv(base / "risk_feature_importance.csv")
    return anomaly, risk, pca, importance


def build_anomaly_stats(anomaly):
    total = len(anomaly)
    n_anomaly = int(anomaly["anomaly_label"].sum())
    rate = n_anomaly / total * 100
    avg_score = float(anomaly["anomaly_score"].astype(float).mean())
    max_score = float(anomaly["anomaly_score"].astype(float).max())

    by_type = anomaly.groupby("ticket_type").agg(
        total=("ticket_id", "count"),
        anomalies=("anomaly_label", "sum"),
    ).reset_index()
    by_type["rate"] = (by_type["anomalies"] / by_type["total"] * 100).round(1)

    by_fault = anomaly.groupby("fault_category").agg(
        total=("ticket_id", "count"),
        anomalies=("anomaly_label", "sum"),
    ).reset_index()
    by_fault["rate"] = (by_fault["anomalies"] / by_fault["total"] * 100).round(1)
    by_fault = by_fault.sort_values("rate", ascending=False)

    by_priority = anomaly.groupby("priority").agg(
        total=("ticket_id", "count"),
        anomalies=("anomaly_label", "sum"),
    ).reset_index()
    by_priority["rate"] = (by_priority["anomalies"] / by_priority["total"] * 100).round(1)

    score_hist, score_edges = np.histogram(anomaly["anomaly_score"].astype(float), bins=30)
    score_hist = score_hist.tolist()
    score_labels = [f"{score_edges[i]:.2f}-{score_edges[i+1]:.2f}" for i in range(len(score_edges)-1)]

    return {
        "total": total, "anomaly_count": n_anomaly, "anomaly_rate": round(rate, 1),
        "avg_score": round(avg_score, 3), "max_score": round(max_score, 3),
        "by_type": by_type.to_dict("records"),
        "by_fault": by_fault.to_dict("records"),
        "by_priority": by_priority.to_dict("records"),
        "score_hist": score_hist, "score_labels": score_labels,
    }


def build_risk_stats(risk):
    total = len(risk)
    high = int(risk["is_risk_high"].sum())
    medium = int(risk["is_risk_medium"].sum())
    low = int(risk["is_risk_low"].sum())
    avg_score = float(risk["risk_score"].astype(float).mean())
    avg_final = float(risk["final_risk_prob"].astype(float).mean())

    dim_cols = ["risk_dim_compliance", "risk_dim_sla", "risk_dim_cost", "risk_dim_quality", "risk_dim_equipment"]
    dim_labels = ["合规", "SLA", "成本", "质量", "设备"]
    dim_avgs = [float(risk[c].mean()) for c in dim_cols]

    top10 = risk.nlargest(10, "risk_score")[["ticket_id", "risk_score", "risk_level", "final_risk_prob", "lr_risk_prob", "nn_risk_prob", "risk_explanation"]].to_dict("records")

    score_hist, score_edges = np.histogram(risk["risk_score"].astype(float), bins=30)
    score_hist = score_hist.tolist()
    score_labels = [f"{score_edges[i]:.2f}-{score_edges[i+1]:.2f}" for i in range(len(score_edges)-1)]

    by_region = risk.groupby("region").agg(
        avg_risk=("risk_score", "mean"), count=("ticket_id", "count"),
        high=("is_risk_high", "sum"), medium=("is_risk_medium", "sum"),
    ).reset_index()
    by_region["avg_risk"] = by_region["avg_risk"].round(4)

    by_ticket_type = risk.groupby("ticket_type").agg(
        avg_risk=("risk_score", "mean"), count=("ticket_id", "count"),
    ).reset_index()
    by_ticket_type["avg_risk"] = by_ticket_type["avg_risk"].round(4)

    return {
        "total": total, "high": high, "medium": medium, "low": low,
        "high_rate": round(high/total*100, 2), "medium_rate": round(medium/total*100, 2),
        "avg_score": round(avg_score, 3), "avg_final": round(avg_final, 3),
        "dim_labels": dim_labels, "dim_avgs": [round(v, 3) for v in dim_avgs],
        "top10": top10,
        "score_hist": score_hist, "score_labels": score_labels,
        "by_region": by_region.to_dict("records"),
        "by_ticket_type": by_ticket_type.to_dict("records"),
    }


def build_pca_data(pca):
    normal = pca[pca["anomaly_label"] == 0].sample(min(500, (pca["anomaly_label"]==0).sum()), random_state=42)
    anomaly_pts = pca[pca["anomaly_label"] == 1]
    return {
        "normal_x": normal["pc1"].round(3).tolist(),
        "normal_y": normal["pc2"].round(3).tolist(),
        "anomaly_x": anomaly_pts["pc1"].round(3).tolist(),
        "anomaly_y": anomaly_pts["pc2"].round(3).tolist(),
    }


def build_anomaly_table_data(anomaly):
    top = anomaly.nlargest(50, "anomaly_score")
    return top[["ticket_id", "anomaly_label", "anomaly_score", "ticket_type", "priority",
                "fault_category", "region", "total_cost"]].to_dict("records")


def build_risk_table_data(risk):
    top = risk.nlargest(50, "risk_score")
    return top[["ticket_id", "risk_score", "risk_level", "final_risk_prob",
                "lr_risk_prob", "nn_risk_prob", "risk_explanation",
                "ticket_type", "priority", "region"]].to_dict("records")


def build_correlation_data(anomaly, risk):
    merged = anomaly[["ticket_id", "anomaly_score"]].merge(
        risk[["ticket_id", "risk_score"]], on="ticket_id"
    )
    sample = merged.sample(min(300, len(merged)), random_state=42)
    corr = float(merged["anomaly_score"].astype(float).corr(merged["risk_score"].astype(float)))
    return {
        "x": sample["anomaly_score"].astype(float).round(3).tolist(),
        "y": sample["risk_score"].astype(float).round(3).tolist(),
        "corr": round(corr, 3),
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>工单数据分析仪表盘</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/jquery.dataTables.min.css">
<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif; background: #f0f2f5; color: #333; }
.header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); color: white; padding: 24px 32px; }
.header h1 { font-size: 24px; font-weight: 600; }
.header p { opacity: 0.7; margin-top: 4px; font-size: 14px; }
.tabs { display: flex; gap: 0; background: white; border-bottom: 2px solid #e8e8e8; padding: 0 24px; position: sticky; top: 0; z-index: 100; }
.tab { padding: 14px 24px; cursor: pointer; border-bottom: 3px solid transparent; font-size: 15px; font-weight: 500; color: #666; transition: all 0.2s; }
.tab:hover { color: #1a1a2e; }
.tab.active { color: #0f3460; border-bottom-color: #0f3460; }
.content { padding: 24px; max-width: 1400px; margin: 0 auto; }
.page { display: none; }
.page.active { display: block; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
.card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.card-label { font-size: 13px; color: #888; margin-bottom: 8px; }
.card-value { font-size: 28px; font-weight: 700; }
.card-sub { font-size: 12px; color: #999; margin-top: 4px; }
.card-danger .card-value { color: #e74c3c; }
.card-warning .card-value { color: #f39c12; }
.card-success .card-value { color: #2ecc71; }
.card-info .card-value { color: #3498db; }
.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
.chart-box { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.chart-box h3 { font-size: 15px; color: #333; margin-bottom: 16px; font-weight: 600; }
.chart-box canvas { max-height: 300px; }
.chart-full { grid-column: 1 / -1; }
.table-box { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 20px; }
.table-box h3 { font-size: 15px; color: #333; margin-bottom: 16px; font-weight: 600; }
table.dataTable thead th { background: #f8f9fa; font-size: 13px; }
table.dataTable tbody td { font-size: 13px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.badge-danger { background: #fde8e8; color: #e74c3c; }
.badge-warning { background: #fef3cd; color: #856404; }
.badge-success { background: #d4edda; color: #155724; }
.badge-anomaly { background: #e74c3c; color: white; }
.badge-normal { background: #95a5a6; color: white; }
@media (max-width: 768px) {
  .chart-row { grid-template-columns: 1fr; }
  .cards { grid-template-columns: repeat(2, 1fr); }
}
</style>
</head>
<body>
<div class="header">
  <h1>工单数据分析仪表盘</h1>
  <p>异常检测 · 风险评分 · 数据分析可视化</p>
</div>
<div class="tabs">
  <div class="tab active" onclick="switchTab('overview')">总览</div>
  <div class="tab" onclick="switchTab('anomaly')">异常检测</div>
  <div class="tab" onclick="switchTab('risk')">风险评分</div>
  <div class="tab" onclick="switchTab('correlation')">关联分析</div>
</div>
<div class="content">
  <!-- 总览 -->
  <div class="page active" id="page-overview">
    <div class="cards" id="overview-cards"></div>
    <div class="chart-row">
      <div class="chart-box"><h3>异常分数分布</h3><canvas id="ov-anomaly-dist"></canvas></div>
      <div class="chart-box"><h3>风险等级分布</h3><canvas id="ov-risk-pie"></canvas></div>
    </div>
    <div class="chart-row">
      <div class="chart-box"><h3>各区域异常率 vs 平均风险分</h3><canvas id="ov-region"></canvas></div>
      <div class="chart-box"><h3>各工单类型异常率</h3><canvas id="ov-ticket-type"></canvas></div>
    </div>
  </div>
  <!-- 异常检测 -->
  <div class="page" id="page-anomaly">
    <div class="cards" id="anomaly-cards"></div>
    <div class="chart-row">
      <div class="chart-box"><h3>异常分数分布</h3><canvas id="an-score-dist"></canvas></div>
      <div class="chart-box"><h3>各故障类型异常率</h3><canvas id="an-fault-rate"></canvas></div>
    </div>
    <div class="chart-row">
      <div class="chart-box"><h3>各工单类型异常率</h3><canvas id="an-type-rate"></canvas></div>
      <div class="chart-box"><h3>各优先级异常率</h3><canvas id="an-priority-rate"></canvas></div>
    </div>
    <div class="chart-row">
      <div class="chart-box chart-full"><h3>PCA异常分布 (降维可视化)</h3><canvas id="an-pca"></canvas></div>
    </div>
    <div class="table-box">
      <h3>异常工单 Top50</h3>
      <table id="anomaly-table" class="display" style="width:100%"></table>
    </div>
  </div>
  <!-- 风险评分 -->
  <div class="page" id="page-risk">
    <div class="cards" id="risk-cards"></div>
    <div class="chart-row">
      <div class="chart-box"><h3>风险分数分布</h3><canvas id="rk-score-dist"></canvas></div>
      <div class="chart-box"><h3>风险等级分布</h3><canvas id="rk-level-pie"></canvas></div>
    </div>
    <div class="chart-row">
      <div class="chart-box"><h3>风险维度雷达图</h3><canvas id="rk-radar"></canvas></div>
      <div class="chart-box"><h3>各区域平均风险分</h3><canvas id="rk-region"></canvas></div>
    </div>
    <div class="chart-row">
      <div class="chart-box"><h3>各工单类型平均风险分</h3><canvas id="rk-type"></canvas></div>
      <div class="chart-box"><h3>逻辑回归 Top10 风险因子</h3><canvas id="rk-importance"></canvas></div>
    </div>
    <div class="table-box">
      <h3>高风险工单 Top10</h3>
      <table id="risk-table" class="display" style="width:100%"></table>
    </div>
  </div>
  <!-- 关联分析 -->
  <div class="page" id="page-correlation">
    <div class="chart-row">
      <div class="chart-box chart-full"><h3>异常分数 vs 风险分数 散点图</h3><canvas id="corr-scatter"></canvas></div>
    </div>
  </div>
</div>

<script>
const DATA = __DATA_PLACEHOLDER__;

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('page-' + name).classList.add('active');
}

function makeCard(label, value, sub, cls) {
  return '<div class="card ' + (cls||'') + '"><div class="card-label">' + label + '</div><div class="card-value">' + value + '</div>' + (sub ? '<div class="card-sub">' + sub + '</div>' : '') + '</div>';
}

function init() {
  const A = DATA.anomaly, R = DATA.risk;
  // Overview cards
  document.getElementById('overview-cards').innerHTML =
    makeCard('工单总数', A.total.toLocaleString(), '分析样本量', 'card-info') +
    makeCard('异常工单', A.anomaly_count.toLocaleString(), '异常率 ' + A.anomaly_rate + '%', 'card-danger') +
    makeCard('高风险工单', R.high.toLocaleString(), '高风险率 ' + R.high_rate + '%', 'card-danger') +
    makeCard('中风险工单', R.medium.toLocaleString(), '中风险率 ' + R.medium_rate + '%', 'card-warning') +
    makeCard('平均异常分数', A.avg_score, '最大 ' + A.max_score, 'card-info') +
    makeCard('平均风险分', R.avg_score, '融合概率 ' + R.avg_final, 'card-info');

  // Anomaly cards
  document.getElementById('anomaly-cards').innerHTML =
    makeCard('异常工单', A.anomaly_count, '异常率 ' + A.anomaly_rate + '%', 'card-danger') +
    makeCard('平均异常分数', A.avg_score, '', 'card-info') +
    makeCard('最高异常分数', A.max_score, '', 'card-warning') +
    makeCard('正常工单', A.total - A.anomaly_count, '', 'card-success');

  // Risk cards
  document.getElementById('risk-cards').innerHTML =
    makeCard('高风险', R.high, R.high_rate + '%', 'card-danger') +
    makeCard('中风险', R.medium, R.medium_rate + '%', 'card-warning') +
    makeCard('低风险', R.low, '', 'card-success') +
    makeCard('平均风险分', R.avg_score, '融合概率 ' + R.avg_final, 'card-info');

  // Charts
  renderCharts();
  renderTables();
}

function renderCharts() {
  const A = DATA.anomaly, R = DATA.risk, P = DATA.pca, C = DATA.corr;
  const COLORS = ['#3498db','#e74c3c','#2ecc71','#f39c12','#9b59b6','#1abc9c','#e67e22','#34495e'];

  // Overview: anomaly score distribution
  new Chart(document.getElementById('ov-anomaly-dist'), {
    type: 'bar', data: { labels: A.score_labels, datasets: [{ data: A.score_hist, backgroundColor: '#3498db', borderRadius: 2 }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { beginAtZero: true } } }
  });

  // Overview: risk level pie
  new Chart(document.getElementById('ov-risk-pie'), {
    type: 'doughnut', data: { labels: ['高风险', '中风险', '低风险'], datasets: [{ data: [R.high, R.medium, R.low], backgroundColor: ['#e74c3c', '#f39c12', '#2ecc71'] }] },
    options: { responsive: true, plugins: { legend: { position: 'right' } } }
  });

  // Overview: region comparison
  const regionLabels = A.by_type.map(d => d.ticket_type);
  new Chart(document.getElementById('ov-region'), {
    type: 'bar', data: {
      labels: R.by_region.map(d => d.region),
      datasets: [
        { label: '平均风险分(×100)', data: R.by_region.map(d => +(d.avg_risk*100).toFixed(1)), backgroundColor: '#3498db' },
        { label: '异常率(%)', data: R.by_region.map(d => 0), backgroundColor: '#e74c3c' },
      ]
    },
    options: { responsive: true, plugins: { legend: { position: 'top' } }, scales: { y: { beginAtZero: true } } }
  });

  // Overview: ticket type anomaly rate
  new Chart(document.getElementById('ov-ticket-type'), {
    type: 'bar', data: { labels: A.by_type.map(d => d.ticket_type), datasets: [{ label: '异常率(%)', data: A.by_type.map(d => d.rate), backgroundColor: '#e74c3c', borderRadius: 4 }] },
    options: { responsive: true, indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true } } }
  });

  // Anomaly: score distribution
  new Chart(document.getElementById('an-score-dist'), {
    type: 'bar', data: { labels: A.score_labels, datasets: [{ data: A.score_hist, backgroundColor: A.score_labels.map(l => parseFloat(l) > 0.6 ? '#e74c3c' : '#3498db'), borderRadius: 2 }] },
    options: { responsive: true, plugins: { legend: { display: false }, annotation: {} }, scales: { x: { display: false }, y: { beginAtZero: true } } }
  });

  // Anomaly: fault type rate
  new Chart(document.getElementById('an-fault-rate'), {
    type: 'bar', data: { labels: A.by_fault.map(d => d.fault_category), datasets: [{ label: '异常率(%)', data: A.by_fault.map(d => d.rate), backgroundColor: '#9b59b6', borderRadius: 4 }] },
    options: { responsive: true, indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true } } }
  });

  // Anomaly: ticket type rate
  new Chart(document.getElementById('an-type-rate'), {
    type: 'bar', data: { labels: A.by_type.map(d => d.ticket_type), datasets: [{ label: '异常率(%)', data: A.by_type.map(d => d.rate), backgroundColor: '#e67e22', borderRadius: 4 }] },
    options: { responsive: true, indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true } } }
  });

  // Anomaly: priority rate
  new Chart(document.getElementById('an-priority-rate'), {
    type: 'bar', data: { labels: A.by_priority.map(d => d.priority), datasets: [{ label: '异常率(%)', data: A.by_priority.map(d => d.rate), backgroundColor: ['#e74c3c','#f39c12','#3498db','#2ecc71'], borderRadius: 4 }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  });

  // Anomaly: PCA scatter
  new Chart(document.getElementById('an-pca'), {
    type: 'scatter', data: {
      datasets: [
        { label: '正常', data: P.normal_x.map((x, i) => ({x, y: P.normal_y[i]})), backgroundColor: 'rgba(52,152,219,0.3)', pointRadius: 2 },
        { label: '异常', data: P.anomaly_x.map((x, i) => ({x, y: P.anomaly_y[i]})), backgroundColor: 'rgba(231,76,60,0.7)', pointRadius: 4 },
      ]
    },
    options: { responsive: true, plugins: { legend: { position: 'top' } }, scales: { x: { title: { display: true, text: 'PC1' } }, y: { title: { display: true, text: 'PC2' } } } }
  });

  // Risk: score distribution
  new Chart(document.getElementById('rk-score-dist'), {
    type: 'bar', data: { labels: R.score_labels, datasets: [{ data: R.score_hist, backgroundColor: R.score_labels.map(l => { const v = parseFloat(l.split('-')[0]); return v >= 0.7 ? '#e74c3c' : v >= 0.4 ? '#f39c12' : '#2ecc71'; }), borderRadius: 2 }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { beginAtZero: true } } }
  });

  // Risk: level pie
  new Chart(document.getElementById('rk-level-pie'), {
    type: 'doughnut', data: { labels: ['高风险', '中风险', '低风险'], datasets: [{ data: [R.high, R.medium, R.low], backgroundColor: ['#e74c3c', '#f39c12', '#2ecc71'] }] },
    options: { responsive: true, plugins: { legend: { position: 'right' } } }
  });

  // Risk: radar
  new Chart(document.getElementById('rk-radar'), {
    type: 'radar', data: {
      labels: R.dim_labels,
      datasets: [{ label: '平均风险分', data: R.dim_avgs, backgroundColor: 'rgba(231,76,60,0.2)', borderColor: '#e74c3c', pointBackgroundColor: '#e74c3c', pointRadius: 5 }]
    },
    options: { responsive: true, scales: { r: { beginAtZero: true, max: 1, ticks: { stepSize: 0.2 } } } }
  });

  // Risk: by region
  new Chart(document.getElementById('rk-region'), {
    type: 'bar', data: { labels: R.by_region.map(d => d.region), datasets: [{ label: '平均风险分', data: R.by_region.map(d => d.avg_risk), backgroundColor: '#3498db', borderRadius: 4 }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  });

  // Risk: by ticket type
  new Chart(document.getElementById('rk-type'), {
    type: 'bar', data: { labels: R.by_ticket_type.map(d => d.ticket_type), datasets: [{ label: '平均风险分', data: R.by_ticket_type.map(d => d.avg_risk), backgroundColor: '#f39c12', borderRadius: 4 }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  });

  // Risk: feature importance (top 10)
  const imp = DATA.importance.slice(0, 10);
  new Chart(document.getElementById('rk-importance'), {
    type: 'bar', data: { labels: imp.map(d => d.feature), datasets: [{ label: '系数', data: imp.map(d => d.lr_coef), backgroundColor: imp.map(d => d.lr_coef > 0 ? '#e74c3c' : '#3498db'), borderRadius: 4 }] },
    options: { responsive: true, indexAxis: 'y', plugins: { legend: { display: false } } }
  });

  // Correlation: scatter
  new Chart(document.getElementById('corr-scatter'), {
    type: 'scatter', data: {
      datasets: [{ label: '工单 (r=' + C.corr + ')', data: C.x.map((x, i) => ({x, y: C.y[i]})), backgroundColor: 'rgba(46,204,113,0.5)', pointRadius: 4 }]
    },
    options: { responsive: true, plugins: { legend: { position: 'top' } }, scales: { x: { title: { display: true, text: '异常分数' } }, y: { title: { display: true, text: '风险分数' } } } }
  });
}

function renderTables() {
  const A = DATA.anomalyTable, R = DATA.riskTable;
  $('#anomaly-table').DataTable({
    data: A, pageLength: 15, order: [[2, 'desc']],
    columns: [
      { data: 'ticket_id', title: '工单号' },
      { data: 'anomaly_label', title: '异常', render: d => d ? '<span class="badge badge-anomaly">异常</span>' : '<span class="badge badge-normal">正常</span>' },
      { data: 'anomaly_score', title: '异常分数', render: d => d.toFixed(3) },
      { data: 'ticket_type', title: '工单类型' },
      { data: 'priority', title: '优先级' },
      { data: 'fault_category', title: '故障类型' },
      { data: 'region', title: '区域' },
      { data: 'total_cost', title: '成本(元)', render: d => d.toLocaleString() },
    ],
    language: { search: '搜索:', lengthMenu: '每页 _MENU_ 条', info: '第 _START_ - _END_ 共 _TOTAL_ 条', paginate: { previous: '上一页', next: '下一页' } }
  });

  $('#risk-table').DataTable({
    data: R, pageLength: 10, order: [[1, 'desc']],
    columns: [
      { data: 'ticket_id', title: '工单号' },
      { data: 'risk_score', title: '风险分', render: d => d.toFixed(3) },
      { data: 'risk_level', title: '等级', render: d => '<span class="badge badge-' + (d==='high'?'danger':d==='medium'?'warning':'success') + '">' + (d==='high'?'高':d==='medium'?'中':'低') + '</span>' },
      { data: 'final_risk_prob', title: '融合概率', render: d => d.toFixed(3) },
      { data: 'ticket_type', title: '工单类型' },
      { data: 'priority', title: '优先级' },
      { data: 'region', title: '区域' },
      { data: 'risk_explanation', title: '风险因素', render: d => '<span style="font-size:12px;color:#666">' + (d||'') + '</span>' },
    ],
    language: { search: '搜索:', lengthMenu: '每页 _MENU_ 条', info: '第 _START_ - _END_ 共 _TOTAL_ 条', paginate: { previous: '上一页', next: '下一页' } }
  });
}

document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>"""


def main():
    print("加载分析结果...")
    anomaly, risk, pca, importance = load_results()

    print("构建统计数据...")
    data = {
        "anomaly": build_anomaly_stats(anomaly),
        "risk": build_risk_stats(risk),
        "pca": build_pca_data(pca),
        "importance": importance.to_dict("records"),
        "anomalyTable": build_anomaly_table_data(anomaly),
        "riskTable": build_risk_table_data(risk),
        "corr": build_correlation_data(anomaly, risk),
    }

    print("生成仪表盘HTML...")
    html = HTML_TEMPLATE.replace("__DATA_PLACEHOLDER__", json.dumps(data, ensure_ascii=False, default=str))

    out = Path("output/dashboard.html")
    out.write_text(html, encoding="utf-8")
    print(f"  -> 已保存: {out} ({len(html)//1024}KB)")
    print("  -> 用浏览器打开 output/dashboard.html 即可查看")


if __name__ == "__main__":
    main()

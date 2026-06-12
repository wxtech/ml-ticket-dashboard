# 工单数据分析 API 文档

## 概述

基于 FastAPI 的 REST API，提供异常检测、风险评分和库存预测功能。

- **基础地址**: `http://localhost:8000`
- **Swagger 文档**: `http://localhost:8000/docs`
- **ReDoc 文档**: `http://localhost:8000/redoc`

## 启动

```bash
# 启动服务
python src/api.py

# 指定端口
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload

# 运行测试
python scripts/test_api.py
```

## 端点总览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/anomaly` | POST | 异常检测 |
| `/api/risk` | POST | 风险评分 |
| `/api/analyze` | POST | 综合分析（异常+风险） |
| `/api/batch` | POST | 批量工单分析 |
| `/api/inventory/forecast` | POST | 库存需求预测 |
| `/api/inventory/plan` | POST | 库存计划计算 |
| `/api/inventory/batch-plan` | POST | 批量库存计划 |
| `/api/inventory/materials` | GET | 物料列表 |

---

## 1. 健康检查

```
GET /health
```

**响应**:

```json
{
  "status": "ok",
  "models_loaded": true
}
```

---

## 2. 异常检测

```
POST /api/anomaly
```

识别工单是否异常，返回异常标签、分数和原因分析。

**请求体**:

```json
{
  "ticket_id": "TK-001",
  "ticket_type": "抢修",
  "priority": "紧急",
  "sla_minutes": 240,
  "region": "华东",
  "site_id": "SITE0001",
  "equipment_id": "EQ00001",
  "equipment_type": "变压器",
  "fault_category": "过热",
  "severity": "严重",
  "equipment_age_months": 96,
  "total_cost": 45000,
  "budget_limit": 5000,
  "is_warranty": false,
  "photo_count": 1,
  "report_uploaded": false,
  "customer_signature": false,
  "attachment_count": 3,
  "is_reopened": true,
  "reopen_within_days": 3,
  "customer_complaint": true,
  "customer_satisfaction": 1,
  "qc_audit_result": "不合规",
  "technician_level": "中",
  "technician_workload_today": 5,
  "dispatched_at": "2025-06-01 10:10:00",
  "accepted_at": "2025-06-01 10:20:00",
  "arrived_at": "2025-06-01 11:00:00",
  "repair_started_at": "2025-06-01 11:10:00",
  "repair_finished_at": "2025-06-01 15:30:00",
  "closed_at": "2025-06-01 16:00:00"
}
```

> 除 `ticket_id` 外所有字段都有默认值，最小请求只需传感兴趣的字段。

**响应**:

```json
{
  "ticket_id": "TK-001",
  "anomaly_label": 1,
  "anomaly_score": 0.82,
  "anomaly_reasons": [
    {"feature": "total_cost", "deviation": 3.5, "importance": 0.05, "value": 3.5},
    {"feature": "repair_duration", "deviation": 2.8, "importance": 0.04, "value": 2.8}
  ]
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `anomaly_label` | int | 0=正常, 1=异常 |
| `anomaly_score` | float | 异常分数 0-1，越大越异常 |
| `anomaly_reasons` | list | 异常原因，按影响度排序 |
| `anomaly_reasons[].feature` | string | 异常特征名 |
| `anomaly_reasons[].deviation` | float | 偏离程度（z-score） |
| `anomaly_reasons[].importance` | float | 特征重要性权重 |

**curl 示例**:

```bash
curl -X POST http://localhost:8000/api/anomaly \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "TK-001",
    "ticket_type": "抢修",
    "priority": "紧急",
    "total_cost": 45000,
    "budget_limit": 5000,
    "fault_category": "过热",
    "is_reopened": true,
    "customer_complaint": true
  }'
```

---

## 3. 风险评分

```
POST /api/risk
```

多维度量化风险，返回风险概率和等级。

**请求体**: 同异常检测（工单字段）。

**响应**:

```json
{
  "ticket_id": "TK-002",
  "risk_score": 0.23,
  "risk_level": "low",
  "final_risk_prob": 0.28,
  "risk_dimensions": {
    "compliance": 0.0,
    "sla": 0.0,
    "cost": 1.0,
    "quality": 0.0,
    "equipment": 0.2
  },
  "risk_explanation": "cost(1.00); equipment(0.20)"
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `risk_score` | float | 规则评分（0-1） |
| `risk_level` | string | 风险等级: high/medium/low |
| `final_risk_prob` | float | 融合概率（规则+LR+NN） |
| `risk_dimensions` | object | 5维度评分明细 |
| `risk_explanation` | string | 风险因素解释 |

**风险维度**:

| 维度 | 权重 | 说明 |
|------|------|------|
| compliance | 0.25 | 合规性（报告、签字、照片、质检） |
| sla | 0.25 | SLA 超时情况 |
| cost | 0.20 | 成本超预算情况 |
| quality | 0.15 | 质量问题（重开、投诉、满意度） |
| equipment | 0.15 | 设备风险（老化、故障类型、严重程度） |

**curl 示例**:

```bash
curl -X POST http://localhost:8000/api/risk \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "TK-002",
    "ticket_type": "保养",
    "total_cost": 8000,
    "budget_limit": 5000
  }'
```

---

## 4. 综合分析

```
POST /api/analyze
```

同时返回异常检测和风险评分结果。

**请求体**: 同异常检测。

**响应**:

```json
{
  "anomaly": {
    "ticket_id": "TK-003",
    "anomaly_label": 0,
    "anomaly_score": 0.47,
    "anomaly_reasons": []
  },
  "risk": {
    "ticket_id": "TK-003",
    "risk_score": 0.41,
    "risk_level": "medium",
    "final_risk_prob": 0.79,
    "risk_dimensions": {"compliance": 0, "sla": 0, "cost": 1.0, "quality": 1.0, "equipment": 0.4},
    "risk_explanation": "cost(1.00); quality(1.00); equipment(0.40)"
  }
}
```

**curl 示例**:

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "TK-003",
    "ticket_type": "巡检",
    "priority": "高",
    "total_cost": 12000,
    "budget_limit": 8000,
    "fault_category": "短路",
    "is_reopened": true,
    "customer_complaint": true
  }'
```

---

## 5. 批量工单分析

```
POST /api/batch
```

一次提交多条工单，同时返回异常检测和风险评分。

**请求体**:

```json
{
  "tickets": [
    {"ticket_id": "BATCH-001", "ticket_type": "抢修", "total_cost": 500, "budget_limit": 1000},
    {"ticket_id": "BATCH-002", "ticket_type": "改造", "total_cost": 20000, "budget_limit": 5000,
     "is_reopened": true, "customer_complaint": true},
    {"ticket_id": "BATCH-003", "ticket_type": "巡检", "total_cost": 800, "budget_limit": 2000}
  ]
}
```

**响应**:

```json
{
  "count": 3,
  "results": [
    {
      "anomaly": {"ticket_id": "BATCH-001", "anomaly_label": 0, "anomaly_score": 0.47, "anomaly_reasons": []},
      "risk": {"ticket_id": "BATCH-001", "risk_score": 0.0, "risk_level": "low", "final_risk_prob": 0.02, "risk_dimensions": {}, "risk_explanation": ""}
    },
    {
      "anomaly": {"ticket_id": "BATCH-002", "anomaly_label": 0, "anomaly_score": 0.48, "anomaly_reasons": []},
      "risk": {"ticket_id": "BATCH-002", "risk_score": 0.35, "risk_level": "low", "final_risk_prob": 0.45, "risk_dimensions": {}, "risk_explanation": ""}
    }
  ]
}
```

**curl 示例**:

```bash
curl -X POST http://localhost:8000/api/batch \
  -H "Content-Type: application/json" \
  -d '{
    "tickets": [
      {"ticket_id": "B-001", "total_cost": 500, "budget_limit": 1000},
      {"ticket_id": "B-002", "total_cost": 20000, "budget_limit": 5000, "is_reopened": true}
    ]
  }'
```

---

## 6. 库存需求预测

```
POST /api/inventory/forecast
```

基于历史数据预测未来需求，使用 Prophet + ARIMA + LightGBM 集成模型。

**请求体**:

```json
{
  "material_id": "MAT0020",
  "site_id": "SITE0001",
  "forecast_days": 30
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `material_id` | string | 是 | - | 物料编号 |
| `site_id` | string | 是 | - | 站点编号 |
| `forecast_days` | int | 否 | 30 | 预测天数 |

**响应**:

```json
{
  "material_id": "MAT0020",
  "site_id": "SITE0001",
  "history_days": 365,
  "current_stock": 2689.0,
  "avg_daily_demand": 9.63,
  "std_daily_demand": 5.02,
  "forecast_total": 294.8,
  "forecast_avg": 9.83,
  "forecast": [
    {"date": "2026-01-01", "forecast": 7.97, "lower": 5.78, "upper": 10.13},
    {"date": "2026-01-02", "forecast": 6.42, "lower": 3.50, "upper": 9.60}
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `history_days` | int | 历史数据天数 |
| `current_stock` | float | 当前库存量 |
| `avg_daily_demand` | float | 历史日均需求 |
| `std_daily_demand` | float | 日需求标准差 |
| `forecast_total` | float | 预测期内总需求 |
| `forecast_avg` | float | 预测日均需求 |
| `forecast` | list | 每日预测明细 |
| `forecast[].lower` | float | 置信区间下限 |
| `forecast[].upper` | float | 置信区间上限 |

**curl 示例**:

```bash
curl -X POST http://localhost:8000/api/inventory/forecast \
  -H "Content-Type: application/json" \
  -d '{"material_id": "MAT0020", "site_id": "SITE0001", "forecast_days": 7}'
```

---

## 7. 库存计划计算

```
POST /api/inventory/plan
```

计算安全库存、再订货点，判断是否需要补货。

**请求体**:

```json
{
  "material_id": "MAT0020",
  "site_id": "SITE0001",
  "current_stock": 2689,
  "avg_daily_demand": 9.63,
  "std_daily_demand": 5.02,
  "lead_time_days": 7,
  "service_level": 0.95
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `material_id` | string | 是 | - | 物料编号 |
| `site_id` | string | 是 | - | 站点编号 |
| `current_stock` | float | 是 | - | 当前库存 |
| `avg_daily_demand` | float | 是 | - | 日均需求 |
| `std_daily_demand` | float | 否 | 5.0 | 日需求标准差 |
| `lead_time_days` | int | 否 | 7 | 补货周期（天） |
| `service_level` | float | 否 | 0.95 | 服务水平（0.90/0.95/0.99） |

**响应**:

```json
{
  "material_id": "MAT0020",
  "site_id": "SITE0001",
  "current_stock": 2689.0,
  "avg_daily_demand": 9.63,
  "std_daily_demand": 5.02,
  "lead_time_days": 7,
  "service_level": 0.95,
  "safety_stock": 21.9,
  "reorder_point": 89.3,
  "days_until_stockout": 279.2,
  "need_reorder": false,
  "recommended_reorder_qty": 0
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `safety_stock` | float | 安全库存 = Z × σ × √(LT) |
| `reorder_point` | float | 再订货点 = 日均需求 × LT + 安全库存 |
| `days_until_stockout` | float | 按当前消耗速度的可售天数 |
| `need_reorder` | bool | 是否需要补货 |
| `recommended_reorder_qty` | float | 建议补货量 |

**计算公式**:

```
安全库存 = Z × σ × √(LT)
  Z = 1.28 (90%) / 1.65 (95%) / 2.33 (99%)

再订货点 = 日均需求 × LT + 安全库存

建议补货量 = 再订货点 - 当前库存 + 安全库存
```

**curl 示例**:

```bash
curl -X POST http://localhost:8000/api/inventory/plan \
  -H "Content-Type: application/json" \
  -d '{
    "material_id": "MAT0020",
    "site_id": "SITE0001",
    "current_stock": 2689,
    "avg_daily_demand": 9.63,
    "std_daily_demand": 5.02,
    "lead_time_days": 7,
    "service_level": 0.95
  }'
```

---

## 8. 批量库存计划

```
POST /api/inventory/batch-plan
```

一次计算多个物料-站点的库存计划。

**请求体**:

```json
[
  {
    "material_id": "MAT0020",
    "site_id": "SITE0001",
    "current_stock": 2689,
    "avg_daily_demand": 9.63
  },
  {
    "material_id": "MAT0020",
    "site_id": "SITE0002",
    "current_stock": 100,
    "avg_daily_demand": 9.89,
    "std_daily_demand": 5.21,
    "lead_time_days": 14
  }
]
```

**响应**:

```json
{
  "count": 2,
  "results": [
    {
      "material_id": "MAT0020",
      "site_id": "SITE0001",
      "safety_stock": 21.9,
      "reorder_point": 89.3,
      "days_until_stockout": 279.2,
      "need_reorder": false,
      "recommended_reorder_qty": 0
    },
    {
      "material_id": "MAT0020",
      "site_id": "SITE0002",
      "safety_stock": 30.3,
      "reorder_point": 168.8,
      "days_until_stockout": 10.1,
      "need_reorder": true,
      "recommended_reorder_qty": 99.1
    }
  ]
}
```

---

## 9. 物料列表

```
GET /api/inventory/materials
```

列出所有可用的物料-站点组合及其统计信息。

**响应**:

```json
{
  "count": 300,
  "materials": [
    {
      "material_id": "MAT0001",
      "site_id": "SITE0001",
      "days": 365,
      "avg_stock": 1638,
      "avg_consumed": 9.3
    },
    {
      "material_id": "MAT0001",
      "site_id": "SITE0002",
      "days": 365,
      "avg_stock": 922,
      "avg_consumed": 10.0
    }
  ]
}
```

**curl 示例**:

```bash
curl http://localhost:8000/api/inventory/materials
```

---

## 错误处理

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误（如数据不足） |
| 422 | 请求体验证失败（字段类型/必填） |
| 500 | 服务器内部错误 |

**错误响应示例**:

```json
{
  "detail": "数据不足: MAT0020@SITE0001 仅有15天数据，需要至少30天"
}
```

---

## 工单输入字段完整列表

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `ticket_id` | string | "API-001" | 工单编号 |
| `created_at` | string | "2025-06-01 10:00:00" | 创建时间 |
| `ticket_type` | string | "抢修" | 抢修/巡检/保养/改造 |
| `priority` | string | "高" | 紧急/高/中/低 |
| `sla_minutes` | int | 240 | SLA时限(分钟) |
| `region` | string | "华东" | 区域 |
| `site_id` | string | "SITE0001" | 站点编号 |
| `equipment_id` | string | "EQ00001" | 设备编号 |
| `equipment_type` | string | "变压器" | 设备类型 |
| `fault_category` | string | "过热" | 故障类型 |
| `severity` | string | "一般" | 严重/一般/轻微 |
| `equipment_age_months` | int | 36 | 设备使用月数 |
| `total_cost` | float | 2000.0 | 总成本 |
| `budget_limit` | float | 3000.0 | 预算上限 |
| `is_warranty` | bool | false | 是否在保修期 |
| `photo_count` | int | 5 | 照片数 |
| `report_uploaded` | bool | true | 报告是否上传 |
| `customer_signature` | bool | true | 客户是否签字 |
| `attachment_count` | int | 3 | 附件数 |
| `is_reopened` | bool | false | 是否重开 |
| `reopen_within_days` | int | null | 重开天数 |
| `customer_complaint` | bool | false | 是否投诉 |
| `customer_satisfaction` | int | 4 | 客户满意度 1-5 |
| `qc_audit_result` | string | "合规" | 质检结果 |
| `technician_level` | string | "中" | 初/中/高/持证 |
| `technician_workload_today` | int | 3 | 技术员当日工作量 |
| `dispatched_at` | string | "2025-06-01 10:10:00" | 派单时间 |
| `accepted_at` | string | "2025-06-01 10:20:00" | 接单时间 |
| `arrived_at` | string | "2025-06-01 11:00:00" | 到场时间 |
| `repair_started_at` | string | "2025-06-01 11:10:00" | 开始维修时间 |
| `repair_finished_at` | string | "2025-06-01 12:30:00" | 维修完成时间 |
| `closed_at` | string | "2025-06-01 13:00:00" | 关闭时间 |

---

## 快速测试

```bash
# 启动服务
python src/api.py

# 另开终端测试
python scripts/test_api.py
```

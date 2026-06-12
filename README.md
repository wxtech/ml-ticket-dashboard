# 工单数据分析系统

基于机器学习的工单数据分析系统，实现异常检测、风险评分和库存预测三大核心功能。

## 系统架构

```
├── config/
│   └── config.yaml              # 全局参数配置
├── data/
│   ├── raw/                     # 原始数据 (CSV)
│   │   ├── ticket_main.csv      # 工单主表
│   │   ├── ticket_materials.csv # 工单-物料明细
│   │   └── inventory_daily.csv  # 库存日表
│   ├── processed/               # 中间处理数据
│   ├── uploads/                 # 用户上传的文件
│   └── users.json               # 用户账户数据 (JWT鉴权)
├── src/
│   ├── anomaly_detection.py     # 异常检测模块
│   ├── risk_scoring.py          # 风险评分模块
│   ├── inventory_forecast.py    # 库存预测模块
│   ├── api.py                   # REST API 服务 (FastAPI, :8000)
│   ├── auth.py                  # JWT 鉴权模块
│   ├── logging_config.py        # 日志配置
│   └── utils.py                 # 共享工具函数
├── scripts/
│   ├── generate_data.py         # 合成数据生成器
│   ├── run_all.py               # 全量运行入口
│   ├── visualize.py             # 可视化图表生成
│   ├── dashboard.py             # 交互式仪表盘生成
│   └── test_api.py              # API 测试脚本
├── templates/                   # Web 应用页面
│   ├── login.html               # 登录页
│   ├── dashboard.html           # 仪表盘首页
│   └── upload.html              # 数据上传页
├── output/
│   ├── dashboard.html           # 独立分析仪表盘
│   ├── logs/                    # 运行日志
│   ├── anomaly_detection_results.csv
│   ├── risk_scoring_results.csv
│   ├── inventory_forecast_results.csv
│   ├── inventory_plan_results.csv
│   └── charts/                  # 7张可视化图表
├── .github/workflows/
│   └── ci.yml                   # GitHub Actions CI
├── app.py                       # Web 应用入口 (:8080)
├── index.html                   # GitHub Pages 首页
├── requirements.txt
├── API.md                       # API 接口文档
├── DEPLOY.md                    # 部署文档
├── AGENTS.md                    # Agent 指南
└── README.md
```

## 快速开始

```bash
cd /opt/devenv/ML/004

# 1. 安装依赖
pip install -r requirements.txt

# 2. 生成合成数据
python scripts/generate_data.py

# 3. 运行全部分析 + 生成仪表盘
python scripts/run_all.py

# 4. 浏览器打开仪表盘
open output/dashboard.html        # macOS
xdg-open output/dashboard.html   # Linux
```

也可以单独运行某个模块：

```bash
python src/anomaly_detection.py   # 仅异常检测
python src/risk_scoring.py        # 仅风险评分
python src/inventory_forecast.py  # 仅库存预测
```

## Web 应用

```bash
# 启动 Web 应用 (默认端口 8080)
python app.py

# 浏览器打开
open http://localhost:8080        # macOS
xdg-open http://localhost:8080   # Linux
```

### 功能页面

| 页面 | 路径 | 说明 |
|------|------|------|
| 登录 | `/login` | 用户名密码登录 |
| 仪表盘 | `/dashboard` | 最新分析结果、图表、任务状态 |
| 数据上传 | `/upload` | 拖拽上传CSV，后台自动分析 |
| 详细分析 | `/analysis` | 完整交互式仪表盘 |

### 默认账户

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | admin |
| demo | demo123 | user |

### 使用流程

```
1. 登录 → /login
2. 上传数据 → /upload (拖拽CSV，选择数据类型)
3. 后台自动分析 → 异常检测 → 风险评分 → 库存预测
4. 查看结果 → /dashboard (自动刷新)
5. 查看详细分析 → /analysis
```

## API 服务

```bash
# 启动服务 (默认端口 8000)
python src/api.py

# 查看接口文档 (Swagger UI)
open http://localhost:8000/docs

# 运行测试脚本
python scripts/test_api.py
```

### 鉴权说明

API 使用 JWT 鉴权，所有 `/api/*` 接口需要携带 Token。

**默认账户**：

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | admin |
| demo | demo123 | user |

**获取 Token**：

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

**响应**：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 86400,
  "username": "admin",
  "role": "admin"
}
```

**使用 Token 访问接口**：

```bash
curl -X POST http://localhost:8000/api/anomaly \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"ticket_id": "TK-001", "ticket_type": "抢修", "total_cost": 50000}'
```

### API 端点总览

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/health` | GET | 健康检查 | 无需 |
| `/auth/login` | POST | 登录获取 Token | 无需 |
| `/auth/register` | POST | 注册新用户 | 无需 |
| `/auth/me` | GET | 获取当前用户信息 | 需要 |
| `/api/anomaly` | POST | 异常检测 | 需要 |
| `/api/risk` | POST | 风险评分 | 需要 |
| `/api/analyze` | POST | 综合分析（异常+风险） | 需要 |
| `/api/batch` | POST | 批量工单分析 | 需要 |
| `/api/inventory/forecast` | POST | 库存需求预测 | 需要 |
| `/api/inventory/plan` | POST | 库存计划计算 | 需要 |
| `/api/inventory/batch-plan` | POST | 批量库存计划 | 需要 |
| `/api/inventory/materials` | GET | 物料列表 | 需要 |
| `/admin/users` | GET | 用户列表 | 需要 admin |

### 请求示例

> 注意：以下接口需要先登录获取 Token，详见鉴权说明。

**异常检测**：

```bash
curl -X POST http://localhost:8000/api/anomaly \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
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

**响应**：

```json
{
  "ticket_id": "TK-001",
  "anomaly_label": 1,
  "anomaly_score": 0.82,
  "anomaly_reasons": [
    {"feature": "total_cost", "deviation": 3.5, "importance": 0.05, "value": 3.5}
  ]
}
```

**风险评分**：

```bash
curl -X POST http://localhost:8000/api/risk \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "ticket_id": "TK-002",
    "ticket_type": "保养",
    "total_cost": 8000,
    "budget_limit": 5000
  }'
```

**响应**：

```json
{
  "ticket_id": "TK-002",
  "risk_score": 0.23,
  "risk_level": "low",
  "final_risk_prob": 0.28,
  "risk_dimensions": {"compliance": 0, "sla": 0, "cost": 1.0, "quality": 0, "equipment": 0.2},
  "risk_explanation": "cost(1.00); equipment(0.20)"
}
```

**库存需求预测**：

```bash
curl -X POST http://localhost:8000/api/inventory/forecast \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"material_id": "MAT0020", "site_id": "SITE0001", "forecast_days": 30}'
```

**响应**：

```json
{
  "material_id": "MAT0020",
  "site_id": "SITE0001",
  "history_days": 365,
  "current_stock": 2689.0,
  "avg_daily_demand": 9.63,
  "forecast_total": 294.8,
  "forecast": [
    {"date": "2026-01-01", "forecast": 7.97, "lower": 5.78, "upper": 10.13}
  ]
}
```

**库存计划计算**：

```bash
curl -X POST http://localhost:8000/api/inventory/plan \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
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

**响应**：

```json
{
  "material_id": "MAT0020",
  "site_id": "SITE0001",
  "current_stock": 2689.0,
  "safety_stock": 21.9,
  "reorder_point": 89.3,
  "days_until_stockout": 279.2,
  "need_reorder": false,
  "recommended_reorder_qty": 0
}
```

### 工单字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ticket_id` | string | 否 | 工单编号（默认自动生成） |
| `ticket_type` | string | 否 | 抢修/巡检/保养/改造 |
| `priority` | string | 否 | 紧急/高/中/低 |
| `total_cost` | float | 否 | 总成本 |
| `budget_limit` | float | 否 | 预算上限 |
| `fault_category` | string | 否 | 过热/短路/漏电/老化/机械故障/电气故障/环境损坏 |
| `severity` | string | 否 | 严重/一般/轻微 |
| `is_reopened` | bool | 否 | 是否重开 |
| `customer_complaint` | bool | 否 | 是否投诉 |
| `customer_satisfaction` | int | 否 | 满意度 1-5 |
| `photo_count` | int | 否 | 照片数 |
| `report_uploaded` | bool | 否 | 报告是否上传 |
| `customer_signature` | bool | 否 | 客户是否签字 |

### 库存字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `material_id` | string | 是 | 物料编号 |
| `site_id` | string | 是 | 站点编号 |
| `forecast_days` | int | 否 | 预测天数（默认30） |
| `current_stock` | float | 是 | 当前库存（计划接口） |
| `avg_daily_demand` | float | 是 | 日均需求（计划接口） |
| `std_daily_demand` | float | 否 | 日需求标准差（默认5.0） |
| `lead_time_days` | int | 否 | 补货周期天数（默认7） |
| `service_level` | float | 否 | 服务水平（默认0.95） |

## 数据模型

### 三张主表

#### `ticket_main` — 工单主表

| 分组 | 字段 | 类型 | 说明 |
|------|------|------|------|
| A-基础 | `ticket_id` | string PK | 工单编号 |
| A-基础 | `created_at` | datetime | 创建时间 |
| A-基础 | `ticket_type` | enum | 抢修/巡检/保养/改造 |
| A-基础 | `priority` | enum | 紧急/高/中/低 |
| A-基础 | `sla_minutes` | int | SLA时限(分钟) |
| A-基础 | `region` | string | 区域 |
| A-基础 | `site_id` | string | 站点编号 |
| B-设备 | `equipment_id` | string | 设备编号 |
| B-设备 | `equipment_type` | enum | 变压器/开关柜/电缆等 |
| B-设备 | `fault_category` | enum | 过热/短路/漏电/老化等 |
| B-设备 | `severity` | enum | 严重/一般/轻微 |
| B-设备 | `equipment_age_months` | int | 设备使用月数 |
| C-时间 | `dispatched_at` | datetime | 派单时间 |
| C-时间 | `accepted_at` | datetime | 接单时间 |
| C-时间 | `arrived_at` | datetime | 到场时间 |
| C-时间 | `repair_started_at` | datetime | 开始维修时间 |
| C-时间 | `repair_finished_at` | datetime | 维修完成时间 |
| C-时间 | `closed_at` | datetime | 关闭时间 |
| D-人员 | `technician_id` | string | 技术员编号 |
| D-人员 | `technician_level` | enum | 初/中/高/持证 |
| E-成本 | `total_cost` | decimal | 总成本 |
| E-成本 | `budget_limit` | decimal | 预算上限 |
| E-成本 | `is_warranty` | bool | 是否在保修期 |
| F-质量 | `photo_count` | int | 照片数 |
| F-质量 | `report_uploaded` | bool | 报告是否上传 |
| F-质量 | `customer_signature` | bool | 客户是否签字 |
| G-反馈 | `is_reopened` | bool | 是否重开 |
| G-反馈 | `customer_complaint` | bool | 是否投诉 |
| G-反馈 | `customer_satisfaction` | int 1-5 | 客户满意度 |
| G-反馈 | `qc_audit_result` | enum | 合规/不合规/待审 |

#### `ticket_materials` — 工单-物料明细

| 字段 | 类型 | 说明 |
|------|------|------|
| `ticket_id` | string FK | 关联工单 |
| `material_id` | string | 物料编号 |
| `material_category` | enum | 电气元件/绝缘材料/机械零件等 |
| `qty_used` | float | 使用数量 |
| `qty_returned` | float | 退回数量 |
| `unit_price` | decimal | 单价 |

#### `inventory_daily` — 库存日表

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | date | 日期 (PK) |
| `material_id` | string | 物料编号 (PK) |
| `site_id` | string | 站点编号 (PK) |
| `stock_on_hand` | float | 当前库存 |
| `daily_consumed` | float | 日消耗量 |
| `daily_replenished` | float | 日补货量 |

## 模块详解

### 1. 异常检测 (`src/anomaly_detection.py`)

**目标**: 无监督识别异常工单，无需标注数据

**算法**:
- **Isolation Forest**: 基于随机森林的异常隔离，适合高维数据
- **Local Outlier Factor (LOF)**: 基于密度的局部异常检测
- **集成模型**: IF(0.6) + LOF(0.4) 加权分数融合 + 投票机制

**特征** (15维):
- 数值特征: `total_cost`, `budget_limit`, `sla_minutes`, `photo_count`, `attachment_count`, `equipment_age_months`, `technician_workload_today`, `reopen_within_days`, `customer_satisfaction`
- 时间特征: `dispatch_delay`, `accept_delay`, `arrival_delay`, `repair_duration`, `total_duration`, `response_time`
- 编码特征: `ticket_type`, `priority`, `region`, `equipment_type`, `fault_category`, `severity` (LabelEncoder)

**异常原因分析**: 基于z-score × 特征重要性加权，找出偏离最大的前3个特征

**输出**:
- `anomaly_detection_results.csv`: 每工单的异常标签、异常分数、子模型标记、异常原因
- `anomaly_pca_visualization.csv`: PCA降维后的2D投影数据

### 2. 风险评分 (`src/risk_scoring.py`)

**目标**: 多维度量化风险，可解释的风险概率

**三阶段模型**:
1. **业务规则评分**: 5维度加权规则引擎
2. **逻辑回归**: 线性可解释的风险模型
3. **神经网络 (MLP)**: 捕捉非线性关系

**5个风险维度**:

| 维度 | 权重 | 评分逻辑 |
|------|------|----------|
| 合规 | 0.25 | 报告未上传、未签字、照片不足、质检不合规 |
| SLA | 0.25 | 总时长/SLA比值，超时越多风险越高 |
| 成本 | 0.20 | 总成本/预算比值，超预算越多风险越高 |
| 质量 | 0.15 | 重开、投诉、低满意度 |
| 设备 | 0.15 | 设备老化(>84月)、故障类型、严重等级 |

**融合公式**:
```
final_risk_prob = 0.3 × rule_score + 0.35 × lr_prob + 0.35 × nn_prob
```

**输出**:
- `risk_scoring_results.csv`: 每工单的规则分数、LR概率、NN概率、融合概率、5维度明细、风险解释
- `risk_feature_importance.csv`: 逻辑回归特征系数

### 3. 库存预测 (`src/inventory_forecast.py`)

**目标**: 预测物料需求，计算安全库存和再订货点

**三模型集成**:
- **Prophet**: 处理季节性和趋势，适合有周期性的时间序列
- **ARIMA**: 经典时序模型，适合平稳序列
- **LightGBM**: 时序回归，通过滞后特征和滚动统计捕捉模式

**LightGBM时序特征**:
- 日/周/月/年日特征
- 滞后特征: lag_1, lag_7, lag_14
- 滚动统计: 7天/14天移动平均
- 递归预测: 预测值作为下一步输入

**库存计算公式**:
```
安全库存 = Z × σ × √(LT)
  Z = 1.65 (95%服务水平)
  σ = 日需求标准差
  LT = 补货周期(天)

再订货点 = 日均需求 × LT + 安全库存
```

**输出**:
- `inventory_forecast_results.csv`: 每日每物料-站点的需求预测、置信区间
- `inventory_plan_results.csv`: 当前库存、安全库存、再订货点、可售天数、是否需补货

## 输出文件说明

### CSV 结果

| 文件 | 行数 | 主要字段 |
|------|------|----------|
| `anomaly_detection_results.csv` | 5000 | ticket_id, anomaly_label, anomaly_score, anomaly_reasons |
| `anomaly_pca_visualization.csv` | 5000 | ticket_id, pc1, pc2, anomaly_label, anomaly_score |
| `risk_scoring_results.csv` | 5000 | ticket_id, risk_score, risk_level, final_risk_prob, 5维度分数 |
| `risk_feature_importance.csv` | 26 | feature, lr_coef, abs_coef |
| `inventory_forecast_results.csv` | 600 | material_id, site_id, date, forecast, lower, upper |
| `inventory_plan_results.csv` | 20 | material_id, site_id, current_stock, safety_stock, reorder_point |

### 可视化图表

| 图表 | 内容 |
|------|------|
| `01_anomaly_overview.png` | 异常分数分布 + 各模型检出数 + 按工单/故障类型异常率 |
| `02_anomaly_scatter.png` | 成本(log) vs 修复时长散点图，异常点红色标注 |
| `03_risk_overview.png` | 风险等级饼图 + 分数分布 + 5维雷达图 + 维度箱线图 |
| `04_risk_by_region.png` | 各区域异常率vs风险分 + 风险等级堆叠图 |
| `05_inventory_forecast.png` | 2个典型物料的30天预测趋势+置信区间 |
| `06_inventory_plan.png` | 库存vs再订货点vs安全库存 + 可售天数(90天警戒线) |
| `07_correlation.png` | 异常分数vs风险分数相关性散点图 |

### 交互式仪表盘

`output/dashboard.html` — 自包含的交互式HTML仪表盘（5个页面）：

- **总览页**: 关键指标卡片 + 异常分数分布 + 风险等级饼图 + 区域对比 + 工单类型异常率
- **异常检测页**: 分数分布 + 故障/类型/优先级异常率 + PCA降维散点图 + 异常工单Top50表格
- **风险评分页**: 分数分布 + 风险等级饼图 + 5维雷达图 + 区域/类型风险分 + LR风险因子 + 高风险工单Top50表格
- **库存预测页**: 预测趋势图 + 库存状态对比 + 当前/再订货/安全库存对比 + 库存计划明细表格
- **关联分析页**: 异常分数 vs 风险分数散点图

## 配置说明

所有参数集中在 `config/config.yaml`:

```yaml
# 数据路径
data:
  raw_dir: data/raw
  output_dir: output

# 异常检测
anomaly_detection:
  contamination: 0.05      # 异常比例，越小越严格
  n_estimators: 200        # 树数量，越大越稳定

# 风险评分
risk_scoring:
  weights:                 # 5维度权重，总和=1
    compliance: 0.25
    sla: 0.25
    cost: 0.20
    quality: 0.15
    equipment: 0.15
  risk_levels:             # 风险等级划分阈值
    high: 0.7
    medium: 0.4

# 库存预测
inventory_forecast:
  forecast_days: 30        # 预测天数
  confidence_interval: 0.95
  safety_stock_factor: 1.65
  arima_order: [1, 1, 1]
```

## 技术栈

| 类别 | 依赖 |
|------|------|
| 数据处理 | pandas >= 2.0, numpy >= 1.24 |
| 异常检测 | scikit-learn (IsolationForest, LOF, PCA) |
| 风险模型 | scikit-learn (LogisticRegression, MLPClassifier) |
| 时序预测 | prophet >= 1.1, statsmodels (ARIMA), lightgbm >= 4.0 |
| API 服务 | fastapi, uvicorn, PyJWT |
| 鉴权 | JWT (PyJWT) + SHA256 密码哈希 |
| 可视化 | matplotlib >= 3.7, seaborn >= 0.12 |
| 配置管理 | pyyaml >= 6.0 |

## 合成数据

运行 `python scripts/generate_data.py` 生成测试数据:

| 表 | 记录数 | 说明 |
|----|--------|------|
| `ticket_main` | 5000 | 含5%注入异常(成本/时长/重开/投诉) |
| `ticket_materials` | ~12000 | 每工单0-5种物料 |
| `inventory_daily` | ~110000 | 15站点×20物料×365天 |

数据覆盖:
- 6个区域: 华东/华南/华北/华中/西南/西北
- 4种工单: 抢修/巡检/保养/改造
- 7种故障: 过热/短路/漏电/老化/机械故障/电气故障/环境损坏
- 6种设备: 变压器/开关柜/电缆/电容器/发电机/配电箱

## 部署

GitHub Pages: `index.html` 于仓库根目录。详见 `DEPLOY.md`。推送到 `main` 分支自动部署（约2分钟）。

## 自定义扩展

### 添加新的风险维度

在 `src/risk_scoring.py` 的 `rule_based_score()` 中添加新维度，更新 `RISK_DIMENSIONS` 列表和 `config.yaml` 中的权重。

### 调整集成权重

修改 `anomaly_detection.py` 中的 IF/LOF 权重，或 `risk_scoring.py` 中的 rule/lr/nn 融合比例。

### 接入真实数据

将CSV文件放入 `data/raw/` 目录，确保字段名与数据模型一致，即可直接运行分析。

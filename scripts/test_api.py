"""API 测试脚本"""
import requests
import json

BASE = "http://localhost:8000"

print("=" * 60)
print("  工单数据分析 API 测试")
print("=" * 60)

# 1. 健康检查
r = requests.get(f"{BASE}/health")
print(f"\n[Health] {r.json()}")

# 2. 异常检测 - 高风险工单
print("\n[异常检测] 成本超标 + 重开 + 投诉")
r = requests.post(f"{BASE}/api/anomaly", json={
    "ticket_id": "API-001",
    "ticket_type": "抢修",
    "priority": "紧急",
    "total_cost": 45000,
    "budget_limit": 5000,
    "fault_category": "过热",
    "severity": "严重",
    "equipment_age_months": 100,
    "is_reopened": True,
    "customer_complaint": True,
    "customer_satisfaction": 1,
    "photo_count": 0,
    "report_uploaded": False,
    "customer_signature": False,
})
print(json.dumps(r.json(), indent=2, ensure_ascii=False))

# 3. 风险评分 - 正常工单
print("\n[风险评分] 正常保养工单")
r = requests.post(f"{BASE}/api/risk", json={
    "ticket_id": "API-002",
    "ticket_type": "保养",
    "priority": "中",
    "total_cost": 1500,
    "budget_limit": 3000,
    "fault_category": "老化",
    "photo_count": 10,
    "report_uploaded": True,
    "customer_signature": True,
})
print(json.dumps(r.json(), indent=2, ensure_ascii=False))

# 4. 综合分析
print("\n[综合分析] 同时返回异常+风险")
r = requests.post(f"{BASE}/api/analyze", json={
    "ticket_id": "API-003",
    "ticket_type": "巡检",
    "priority": "高",
    "total_cost": 12000,
    "budget_limit": 8000,
    "fault_category": "短路",
    "severity": "严重",
    "is_reopened": True,
    "customer_complaint": True,
})
print(json.dumps(r.json(), indent=2, ensure_ascii=False))

# 5. 批量分析
print("\n[批量分析] 3条工单一起提交")
r = requests.post(f"{BASE}/api/batch", json={
    "tickets": [
        {"ticket_id": "BATCH-001", "ticket_type": "抢修", "total_cost": 500, "budget_limit": 1000},
        {"ticket_id": "BATCH-002", "ticket_type": "改造", "total_cost": 20000, "budget_limit": 5000,
         "is_reopened": True, "customer_complaint": True},
        {"ticket_id": "BATCH-003", "ticket_type": "巡检", "total_cost": 800, "budget_limit": 2000},
    ]
})
data = r.json()
print(f"  返回 {data['count']} 条结果")
for item in data["results"]:
    a = item["anomaly"]
    risk = item["risk"]
    print(f"  {a['ticket_id']}: 异常={a['anomaly_label']}({a['anomaly_score']:.3f}) | 风险={risk['risk_level']}({risk['risk_score']:.3f})")

print("\n" + "=" * 60)
print("  全部测试通过!")
print("=" * 60)

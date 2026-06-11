"""合成数据生成器 - 生成符合schema的工单数据"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import yaml
from pathlib import Path

random.seed(42)
np.random.seed(42)

REGIONS = ["华东", "华南", "华北", "华中", "西南", "西北"]
EQUIPMENT_TYPES = ["变压器", "开关柜", "电缆", "电容器", "发电机", "配电箱"]
FAULT_CATEGORIES = ["过热", "短路", "漏电", "老化", "机械故障", "电气故障", "环境损坏"]
TICKET_TYPES = ["抢修", "巡检", "保养", "改造"]
PRIORITIES = ["紧急", "高", "中", "低"]
TECH_LEVELS = ["初", "中", "高", "持证"]
MATERIAL_CATEGORIES = ["电气元件", "绝缘材料", "机械零件", "线缆", "工具", "辅材"]

MATERIAL_IDS = [f"MAT{i:04d}" for i in range(1, 51)]
EQUIPMENT_IDS = [f"EQ{i:05d}" for i in range(1, 201)]
SITE_IDS = [f"SITE{i:04d}" for i in range(1, 31)]
TECH_IDS = [f"TECH{i:04d}" for i in range(1, 21)]


def generate_ticket_main(n=5000):
    records = []
    base_date = datetime(2025, 1, 1)

    for i in range(n):
        ticket_id = f"TK{i+1:06d}"
        created_at = base_date + timedelta(
            days=random.randint(0, 364),
            hours=random.randint(7, 20),
            minutes=random.randint(0, 59),
        )
        ticket_type = random.choices(TICKET_TYPES, weights=[0.3, 0.35, 0.25, 0.1])[0]
        priority = random.choices(PRIORITIES, weights=[0.1, 0.25, 0.45, 0.2])[0]
        sla_minutes = {"紧急": 60, "高": 240, "中": 480, "低": 1440}[priority]
        region = random.choice(REGIONS)
        site_id = random.choice(SITE_IDS)
        equipment_id = random.choice(EQUIPMENT_IDS)
        equipment_type = random.choice(EQUIPMENT_TYPES)
        fault_category = random.choice(FAULT_CATEGORIES)
        severity = random.choices(["严重", "一般", "轻微"], weights=[0.2, 0.5, 0.3])[0]
        equipment_age = random.randint(0, 120)

        dispatched_at = created_at + timedelta(minutes=random.randint(5, 60))
        accepted_at = dispatched_at + timedelta(minutes=random.randint(5, 30))
        arrived_at = accepted_at + timedelta(minutes=random.randint(10, 120))
        repair_time = random.randint(20, 480)
        repair_started_at = arrived_at + timedelta(minutes=random.randint(5, 30))
        repair_finished_at = repair_started_at + timedelta(minutes=repair_time)
        closed_at = repair_finished_at + timedelta(minutes=random.randint(10, 120))

        is_reopened = random.random() < 0.08
        reopen_within_days = random.randint(1, 14) if is_reopened else None
        customer_complaint = random.random() < 0.12
        satisfaction = random.randint(1, 5) if random.random() < 0.7 else None

        base_cost = random.uniform(100, 5000)
        total_cost = round(base_cost * (1.5 if priority == "紧急" else 1.0), 2)
        budget_limit = round(total_cost * random.uniform(1.1, 1.8), 2)

        # 注入异常数据 (~5%)
        is_anomaly = random.random() < 0.05
        if is_anomaly:
            anomaly_type = random.choice(["cost", "time", "reopen", "complaint"])
            if anomaly_type == "cost":
                total_cost = round(total_cost * random.uniform(3, 8), 2)
            elif anomaly_type == "time":
                repair_time = repair_time * random.randint(3, 6)
                repair_finished_at = repair_started_at + timedelta(minutes=repair_time)
                closed_at = repair_finished_at + timedelta(minutes=random.randint(10, 120))
            elif anomaly_type == "reopen":
                is_reopened = True
                reopen_within_days = random.randint(1, 3)
                customer_complaint = True
            elif anomaly_type == "complaint":
                customer_complaint = True
                satisfaction = 1

        photo_count = random.randint(0, 20)
        report_uploaded = random.random() < 0.85
        customer_signature = random.random() < 0.8
        attachment_count = random.randint(0, 10)
        is_warranty = random.random() < 0.3
        last_fault_at = created_at - timedelta(days=random.randint(30, 365)) if random.random() < 0.4 else None
        qc_result = random.choices(["合规", "不合规", "待审"], weights=[0.6, 0.15, 0.25])[0]
        technician_level = random.choices(TECH_LEVELS, weights=[0.2, 0.35, 0.3, 0.15])[0]

        status_history = [
            {"ts": created_at.isoformat(), "from": "新建", "to": "已派单", "actor": "系统"},
            {"ts": dispatched_at.isoformat(), "from": "已派单", "to": "已接单", "actor": random.choice(TECH_IDS)},
            {"ts": arrived_at.isoformat(), "from": "已接单", "to": "已到场", "actor": random.choice(TECH_IDS)},
            {"ts": repair_finished_at.isoformat(), "from": "已到场", "to": "已修复", "actor": random.choice(TECH_IDS)},
            {"ts": closed_at.isoformat(), "from": "已修复", "to": "已关闭", "actor": "系统"},
        ]
        if is_reopened:
            status_history.append({"ts": (closed_at + timedelta(days=random.randint(1, 7))).isoformat(), "from": "已关闭", "to": "已重开", "actor": "客户"})

        records.append({
            "ticket_id": ticket_id, "created_at": created_at, "ticket_type": ticket_type,
            "priority": priority, "sla_minutes": sla_minutes, "region": region,
            "site_id": site_id, "equipment_id": equipment_id, "equipment_type": equipment_type,
            "equipment_model": f"Model-{random.choice('ABCDEF')}{random.randint(100,999)}",
            "fault_category": fault_category,
            "fault_subcategory": f"{fault_category}-{random.randint(1,5)}",
            "fault_description": f"{equipment_type}出现{fault_category}问题",
            "severity": severity, "equipment_age_months": equipment_age,
            "last_fault_at": last_fault_at,
            "dispatched_at": dispatched_at, "accepted_at": accepted_at,
            "arrived_at": arrived_at, "repair_started_at": repair_started_at,
            "repair_finished_at": repair_finished_at,
            "inspected_at": repair_finished_at + timedelta(minutes=random.randint(5, 30)) if random.random() < 0.6 else None,
            "accepted_by_customer_at": closed_at - timedelta(minutes=random.randint(5, 20)) if random.random() < 0.7 else None,
            "closed_at": closed_at, "status_history": str(status_history),
            "technician_id": random.choice(TECH_IDS), "team_id": f"TEAM{random.randint(1,5):02d}",
            "technician_level": technician_level,
            "technician_workload_today": random.randint(1, 8),
            "total_cost": total_cost, "budget_limit": budget_limit,
            "is_warranty": is_warranty,
            "photo_count": photo_count, "report_uploaded": report_uploaded,
            "customer_signature": customer_signature, "attachment_count": attachment_count,
            "photo_taken_at": str([created_at.isoformat()]),
            "is_reopened": is_reopened, "reopen_within_days": reopen_within_days,
            "customer_complaint": customer_complaint,
            "customer_satisfaction": satisfaction,
            "qc_audit_result": qc_result,
        })
    return pd.DataFrame(records)


def generate_ticket_materials(ticket_df):
    records = []
    for _, row in ticket_df.iterrows():
        n_materials = random.randint(0, 5)
        for _ in range(n_materials):
            records.append({
                "ticket_id": row["ticket_id"],
                "material_id": random.choice(MATERIAL_IDS),
                "material_category": random.choice(MATERIAL_CATEGORIES),
                "qty_used": round(random.uniform(0.5, 20), 1),
                "qty_returned": round(random.uniform(0, 2), 1) if random.random() < 0.2 else 0,
                "unit_price": round(random.uniform(5, 500), 2),
            })
    return pd.DataFrame(records)


def generate_inventory_daily(n_days=365):
    records = []
    base_date = datetime(2025, 1, 1)
    for site_id in SITE_IDS[:15]:
        for mat_id in MATERIAL_IDS[:20]:
            stock = random.randint(50, 500)
            for d in range(n_days):
                date = base_date + timedelta(days=d)
                consumed = max(0, int(random.gauss(10, 5)))
                replenished = random.choice([0, 0, 0, random.randint(20, 100)])
                stock = max(0, stock - consumed + replenished)
                records.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "material_id": mat_id,
                    "site_id": site_id,
                    "stock_on_hand": stock,
                    "daily_consumed": consumed,
                    "daily_replenished": replenished,
                })
    return pd.DataFrame(records)


def main():
    config = yaml.safe_load(open("config/config.yaml"))
    raw_dir = Path(config["data"]["raw_dir"])
    raw_dir.mkdir(parents=True, exist_ok=True)

    print("生成工单主表...")
    ticket_main = generate_ticket_main(5000)
    ticket_main.to_csv(raw_dir / "ticket_main.csv", index=False)
    print(f"  -> {len(ticket_main)} 条工单")

    print("生成工单物料表...")
    ticket_materials = generate_ticket_materials(ticket_main)
    ticket_materials.to_csv(raw_dir / "ticket_materials.csv", index=False)
    print(f"  -> {len(ticket_materials)} 条物料记录")

    print("生成库存日表...")
    inventory_daily = generate_inventory_daily(365)
    inventory_daily.to_csv(raw_dir / "inventory_daily.csv", index=False)
    print(f"  -> {len(inventory_daily)} 条库存记录")

    print("数据生成完成!")


if __name__ == "__main__":
    main()

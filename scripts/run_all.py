"""运行全部分析模块"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from utils import load_config
from anomaly_detection import run as run_anomaly
from risk_scoring import run as run_risk
from inventory_forecast import run as run_forecast


def main():
    config = load_config()
    print("=" * 60)
    print("  工单数据分析系统 - 全量运行")
    print("=" * 60)

    print("\n[1/3] 异常检测")
    run_anomaly(config)

    print("\n[2/3] 风险评分")
    run_risk(config)

    print("\n[3/3] 库存预测")
    run_forecast(config)

    print("\n[4/4] 生成仪表盘")
    from dashboard import main as run_dashboard
    run_dashboard()

    print("\n" + "=" * 60)
    print("  全部分析完成! 结果保存在 output/ 目录")
    print("  仪表盘: output/dashboard.html (浏览器打开)")
    print("=" * 60)


if __name__ == "__main__":
    main()

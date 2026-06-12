"""日志配置模块"""
import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(name: str = "ticket_analysis", level: str = "INFO", log_file: str = None) -> logging.Logger:
    """配置日志系统

    Args:
        name: 日志器名称
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        log_file: 日志文件路径，None 则只输出到控制台
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s.%(funcName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台输出
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # 文件输出
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


def get_logger(module: str = None) -> logging.Logger:
    """获取指定模块的日志器"""
    name = f"ticket_analysis.{module}" if module else "ticket_analysis"
    return logging.getLogger(name)

from __future__ import annotations

import logging
from pathlib import Path


def get_project_root() -> Path:
    """
    获取项目根目录。

    Returns:
        Path: 项目根目录绝对路径。
    """
    return Path(__file__).resolve().parent.parent


def get_log_dir() -> Path:
    """
    获取项目日志目录。

    Returns:
        Path: 日志目录绝对路径。
    """
    return get_project_root() / "logs"


def configure_logging() -> Path:
    """
    初始化应用日志配置。

    Returns:
        Path: 日志文件路径。
    """
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return log_path

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.logging_config import configure_logging, get_log_dir
from app.ui.main_window import MainWindow

LOGGER = logging.getLogger(__name__)


def main() -> int:
    """
    启动桌面应用。

    Returns:
        int: Qt 应用退出码。
    """
    log_path = configure_logging()
    runtime_log_path = get_log_dir() / "runtime.log"
    with runtime_log_path.open("a", encoding="utf-8") as runtime_log:
        with redirect_stdout(runtime_log), redirect_stderr(runtime_log):
            app = QApplication(sys.argv)
            try:
                window = MainWindow()
                window.show()
                LOGGER.info("应用已启动，日志文件：%s，运行日志：%s", log_path, runtime_log_path)
                return app.exec()
            except Exception as exc:
                LOGGER.exception("应用启动或主循环发生未处理错误")
                QMessageBox.critical(
                    None,
                    "程序错误",
                    f"程序发生错误：{exc}\n日志文件：{log_path}\n运行日志：{runtime_log_path}",
                )
                return 1


if __name__ == "__main__":
    raise SystemExit(main())

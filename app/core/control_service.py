from __future__ import annotations

import ctypes
import logging

import win32con
import win32gui

from app.core.win32_utils import ensure_hwnd, get_last_error
from app.models import OperationResult, WindowCommand

LOGGER = logging.getLogger(__name__)


class ControlService:
    """提供窗口显示、位置和关闭控制。"""

    _SHOW_COMMANDS: dict[WindowCommand, int] = {
        WindowCommand.HIDE: win32con.SW_HIDE,
        WindowCommand.SHOW: win32con.SW_SHOW,
        WindowCommand.MINIMIZE: win32con.SW_MINIMIZE,
        WindowCommand.MAXIMIZE: win32con.SW_MAXIMIZE,
        WindowCommand.RESTORE: win32con.SW_RESTORE,
    }

    def show_window(self, hwnd: int, command: WindowCommand) -> OperationResult:
        """
        执行窗口显示状态命令。

        Args:
            hwnd (int): 窗口句柄。
            command (WindowCommand): 显示控制命令。

        Returns:
            OperationResult: 操作结果。
        """
        try:
            ensure_hwnd(hwnd)
            previous_state = win32gui.ShowWindow(hwnd, self._SHOW_COMMANDS[command])
            return OperationResult(True, f"已执行窗口命令：{command.value}", previous_state)
        except (ValueError, RuntimeError, OSError) as exc:
            LOGGER.exception("窗口显示控制失败")
            return OperationResult(False, str(exc), None, get_last_error())

    def bring_to_front(self, hwnd: int) -> OperationResult:
        """
        将窗口置于前台。

        Args:
            hwnd (int): 窗口句柄。

        Returns:
            OperationResult: 操作结果。
        """
        try:
            ensure_hwnd(hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return OperationResult(True, "已尝试将窗口置前")
        except (ValueError, RuntimeError, OSError) as exc:
            LOGGER.exception("置前窗口失败")
            return OperationResult(False, str(exc), None, get_last_error())

    def set_focus(self, hwnd: int) -> OperationResult:
        """
        设置窗口焦点。

        Args:
            hwnd (int): 窗口句柄。

        Returns:
            OperationResult: 操作结果。
        """
        try:
            ensure_hwnd(hwnd)
            result = win32gui.SetFocus(hwnd)
            return OperationResult(True, "已尝试设置焦点", result)
        except (ValueError, RuntimeError, OSError) as exc:
            LOGGER.exception("设置窗口焦点失败")
            return OperationResult(False, str(exc), None, get_last_error())

    def move_window(self, hwnd: int, x: int, y: int, width: int, height: int) -> OperationResult:
        """
        移动并缩放窗口。

        Args:
            hwnd (int): 窗口句柄。
            x (int): 左上角 X 坐标。
            y (int): 左上角 Y 坐标。
            width (int): 窗口宽度。
            height (int): 窗口高度。

        Returns:
            OperationResult: 操作结果。
        """
        try:
            ensure_hwnd(hwnd)
            if width <= 0 or height <= 0:
                raise ValueError("窗口宽高必须大于 0")
            result = win32gui.MoveWindow(hwnd, x, y, width, height, True)
            return OperationResult(True, "已移动或缩放窗口", result)
        except (ValueError, RuntimeError, OSError) as exc:
            LOGGER.exception("移动窗口失败")
            return OperationResult(False, str(exc), None, get_last_error())

    def close_window(self, hwnd: int) -> OperationResult:
        """
        向窗口发送关闭消息。

        Args:
            hwnd (int): 窗口句柄。

        Returns:
            OperationResult: 操作结果。
        """
        try:
            ensure_hwnd(hwnd)
            result = win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            return OperationResult(True, "已发送 WM_CLOSE", result)
        except (ValueError, RuntimeError, OSError) as exc:
            LOGGER.exception("关闭窗口失败")
            return OperationResult(False, str(exc), None, get_last_error())

    def set_topmost(self, hwnd: int, enabled: bool) -> OperationResult:
        """
        设置或取消窗口置顶。

        Args:
            hwnd (int): 窗口句柄。
            enabled (bool): 是否置顶。

        Returns:
            OperationResult: 操作结果。
        """
        try:
            ensure_hwnd(hwnd)
            insert_after = win32con.HWND_TOPMOST if enabled else win32con.HWND_NOTOPMOST
            result = ctypes.windll.user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, 0x0001 | 0x0002)
            if not result:
                return OperationResult(False, "设置置顶失败", result, get_last_error())
            return OperationResult(True, "已更新窗口置顶状态", result)
        except (ValueError, RuntimeError, OSError) as exc:
            LOGGER.exception("设置置顶失败")
            return OperationResult(False, str(exc), None, get_last_error())


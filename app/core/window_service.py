from __future__ import annotations

import logging
from typing import Callable

import psutil
import win32con
import win32gui
import win32process

from app.core.win32_utils import ensure_hwnd
from app.models import Rect, WindowInfo

LOGGER = logging.getLogger(__name__)


class WindowService:
    """提供窗口枚举、拾取和信息读取能力。"""

    def enumerate_top_windows(self) -> list[WindowInfo]:
        """
        枚举当前桌面的可见顶层窗口。

        Returns:
            list[WindowInfo]: 顶层窗口信息列表。
        """
        windows: list[WindowInfo] = []

        def callback(hwnd: int, _: int) -> bool:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return True
            try:
                windows.append(self.get_window_info(hwnd))
            except (psutil.Error, OSError, RuntimeError, ValueError) as exc:
                LOGGER.warning("读取顶层窗口信息失败 hwnd=%s: %s", hwnd, exc)
            return True

        win32gui.EnumWindows(callback, 0)
        return windows

    def enumerate_child_windows(self, hwnd: int) -> list[WindowInfo]:
        """
        枚举指定窗口的所有子窗口。

        Args:
            hwnd (int): 父窗口句柄。

        Returns:
            list[WindowInfo]: 子窗口信息列表。
        """
        ensure_hwnd(hwnd)
        children: list[WindowInfo] = []

        def callback(child_hwnd: int, _: int) -> bool:
            try:
                children.append(self.get_window_info(child_hwnd))
            except (psutil.Error, OSError, RuntimeError, ValueError) as exc:
                LOGGER.warning("读取子窗口信息失败 hwnd=%s: %s", child_hwnd, exc)
            return True

        win32gui.EnumChildWindows(hwnd, callback, 0)
        return children

    def get_window_info(self, hwnd: int) -> WindowInfo:
        """
        获取指定 HWND 的窗口信息。

        Args:
            hwnd (int): 窗口句柄。

        Returns:
            WindowInfo: 窗口信息。

        Raises:
            ValueError: HWND 无效时抛出。
        """
        ensure_hwnd(hwnd)
        if not win32gui.IsWindow(hwnd):
            raise ValueError(f"无效 HWND: {hwnd}")

        tid, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_name = ""
        process_path = ""
        try:
            process = psutil.Process(pid)
            process_name = process.name()
            process_path = process.exe()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as exc:
            LOGGER.info("读取进程信息受限 pid=%s: %s", pid, exc)

        parent_hwnd = win32gui.GetParent(hwnd) or None
        owner_hwnd = win32gui.GetWindow(hwnd, win32con.GW_OWNER) or None
        return WindowInfo(
            hwnd=hwnd,
            title=win32gui.GetWindowText(hwnd),
            class_name=win32gui.GetClassName(hwnd),
            pid=pid,
            tid=tid,
            process_name=process_name,
            process_path=process_path,
            rect=Rect.from_tuple(win32gui.GetWindowRect(hwnd)),
            client_rect=Rect.from_tuple(win32gui.GetClientRect(hwnd)),
            parent_hwnd=parent_hwnd,
            owner_hwnd=owner_hwnd,
            is_visible=bool(win32gui.IsWindowVisible(hwnd)),
            is_enabled=bool(win32gui.IsWindowEnabled(hwnd)),
        )

    def window_from_point(self, x: int, y: int) -> WindowInfo:
        """
        根据屏幕坐标获取窗口信息。

        Args:
            x (int): 屏幕 X 坐标。
            y (int): 屏幕 Y 坐标。

        Returns:
            WindowInfo: 鼠标位置下的窗口信息。
        """
        hwnd = win32gui.WindowFromPoint((x, y))
        return self.get_window_info(hwnd)

    def screen_to_client(self, hwnd: int, x: int, y: int) -> tuple[int, int]:
        """
        将屏幕坐标转换为指定窗口的客户区坐标。

        Args:
            hwnd (int): 窗口句柄。
            x (int): 屏幕 X 坐标。
            y (int): 屏幕 Y 坐标。

        Returns:
            tuple[int, int]: 客户区坐标。
        """
        ensure_hwnd(hwnd)
        if not win32gui.IsWindow(hwnd):
            raise ValueError(f"无效 HWND: {hwnd}")
        return win32gui.ScreenToClient(hwnd, (x, y))

    def get_client_size(self, hwnd: int) -> tuple[int, int]:
        """
        获取窗口客户区宽高。

        Args:
            hwnd (int): 窗口句柄。

        Returns:
            tuple[int, int]: 客户区宽度和高度。
        """
        ensure_hwnd(hwnd)
        if not win32gui.IsWindow(hwnd):
            raise ValueError(f"无效 HWND: {hwnd}")
        rect = Rect.from_tuple(win32gui.GetClientRect(hwnd))
        return rect.width, rect.height

    def walk_child_tree(self, hwnd: int, visit: Callable[[WindowInfo], None]) -> None:
        """
        遍历子窗口并执行回调。

        Args:
            hwnd (int): 父窗口句柄。
            visit (Callable[[WindowInfo], None]): 访问每个子窗口时调用的函数。
        """
        for child in self.enumerate_child_windows(hwnd):
            visit(child)

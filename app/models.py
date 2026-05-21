from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class Rect:
    """
    表示 Windows 矩形区域。

    Args:
        left (int): 左边界坐标。
        top (int): 上边界坐标。
        right (int): 右边界坐标。
        bottom (int): 下边界坐标。
    """

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        """
        获取矩形宽度。

        Returns:
            int: 宽度，最小为 0。
        """
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        """
        获取矩形高度。

        Returns:
            int: 高度，最小为 0。
        """
        return max(0, self.bottom - self.top)

    @classmethod
    def from_tuple(cls, rect: tuple[int, int, int, int]) -> "Rect":
        """
        从 Win32 矩形元组创建 Rect。

        Args:
            rect (tuple[int, int, int, int]): Win32 返回的 left、top、right、bottom。

        Returns:
            Rect: 矩形对象。
        """
        left, top, right, bottom = rect
        return cls(left=left, top=top, right=right, bottom=bottom)

    def to_tuple(self) -> tuple[int, int, int, int]:
        """
        转换为 Win32 常用的矩形元组。

        Returns:
            tuple[int, int, int, int]: left、top、right、bottom。
        """
        return self.left, self.top, self.right, self.bottom


@dataclass(frozen=True)
class WindowInfo:
    """
    表示一个窗口的基础信息。

    Args:
        hwnd (int): 窗口句柄。
        title (str): 窗口标题。
        class_name (str): 窗口类名。
        pid (int): 进程 ID。
        tid (int): 线程 ID。
        process_name (str): 进程名。
        process_path (str): 进程路径。
        rect (Rect): 屏幕坐标下的窗口矩形。
        client_rect (Rect): 客户区矩形。
        parent_hwnd (int | None): 父窗口句柄。
        owner_hwnd (int | None): 所有者窗口句柄。
        is_visible (bool): 窗口是否可见。
        is_enabled (bool): 窗口是否可用。
    """

    hwnd: int
    title: str
    class_name: str
    pid: int
    tid: int
    process_name: str
    process_path: str
    rect: Rect
    client_rect: Rect
    parent_hwnd: int | None
    owner_hwnd: int | None
    is_visible: bool
    is_enabled: bool


@dataclass(frozen=True)
class OperationResult:
    """
    表示一次窗口操作的结果。

    Args:
        success (bool): 操作是否成功。
        message (str): 给用户看的结果说明。
        return_value (Any | None): Win32 API 返回值或补充信息。
        last_error (int | None): Windows LastError 错误码。
    """

    success: bool
    message: str
    return_value: Any | None = None
    last_error: int | None = None


@dataclass(frozen=True)
class ScreenshotResult:
    """
    表示一次截图操作的结果。

    Args:
        success (bool): 截图是否成功。
        image (Any | None): Pillow Image 对象。
        source (str): 截图来源。
        message (str): 结果说明。
    """

    success: bool
    image: Any | None
    source: str
    message: str


class WindowCommand(str, Enum):
    """窗口显示控制命令。"""

    HIDE = "hide"
    SHOW = "show"
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"
    RESTORE = "restore"


from __future__ import annotations

import ctypes


def ensure_hwnd(hwnd: int) -> None:
    """
    校验 HWND 是否为有效的正整数。

    Args:
        hwnd (int): 待校验窗口句柄。

    Raises:
        ValueError: HWND 不是正整数时抛出。
    """
    if hwnd <= 0:
        raise ValueError("HWND 必须是正整数")


def pack_lparam(x: int, y: int) -> int:
    """
    将客户区坐标打包为鼠标消息使用的 lParam。

    Args:
        x (int): X 坐标。
        y (int): Y 坐标。

    Returns:
        int: 打包后的 lParam。
    """
    return (y & 0xFFFF) << 16 | (x & 0xFFFF)


def get_last_error() -> int:
    """
    获取当前线程的 Windows LastError。

    Returns:
        int: LastError 错误码。
    """
    return ctypes.get_last_error()


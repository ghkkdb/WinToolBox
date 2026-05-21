from __future__ import annotations

import pytest

from app.core.win32_utils import ensure_hwnd, pack_lparam
from app.models import Rect


def test_pack_lparam_uses_low_words() -> None:
    """
    验证鼠标坐标能按 Win32 消息格式打包。
    """
    assert pack_lparam(20, 30) == (30 << 16) | 20


def test_pack_lparam_keeps_negative_coordinate_low_word() -> None:
    """
    验证负坐标会保留低 16 位，符合 Win32 消息打包方式。
    """
    assert pack_lparam(-1, -2) == (0xFFFE << 16) | 0xFFFF


def test_ensure_hwnd_rejects_invalid_value() -> None:
    """
    验证无效 HWND 会被拒绝。
    """
    with pytest.raises(ValueError):
        ensure_hwnd(0)


def test_rect_width_and_height_never_negative() -> None:
    """
    验证矩形宽高不会返回负数。
    """
    rect = Rect(left=10, top=20, right=5, bottom=15)
    assert rect.width == 0
    assert rect.height == 0


def test_rect_from_tuple_and_to_tuple() -> None:
    """
    验证 Rect 能和 Win32 元组互相转换。
    """
    rect = Rect.from_tuple((1, 2, 3, 4))
    assert rect.to_tuple() == (1, 2, 3, 4)

from __future__ import annotations

import ctypes
import logging

import mss
import win32con
import win32gui
import win32ui
from PIL import Image

from app.core.win32_utils import ensure_hwnd, get_last_error
from app.models import ScreenshotResult

LOGGER = logging.getLogger(__name__)


class ScreenshotService:
    """提供前台和后台截图能力。"""

    def capture_foreground(self, hwnd: int) -> ScreenshotResult:
        """
        使用 mss 截取窗口屏幕区域。

        Args:
            hwnd (int): 窗口句柄。

        Returns:
            ScreenshotResult: 截图结果。
        """
        try:
            ensure_hwnd(hwnd)
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = max(0, right - left)
            height = max(0, bottom - top)
            if width <= 0 or height <= 0:
                return ScreenshotResult(False, None, "foreground", "窗口尺寸无效，无法截图")
            with mss.mss() as sct:
                shot = sct.grab({"left": left, "top": top, "width": width, "height": height})
            image = Image.frombytes("RGB", shot.size, shot.rgb)
            return ScreenshotResult(True, image, "foreground", "前台截图成功")
        except (ValueError, RuntimeError, OSError, mss.ScreenShotError) as exc:
            LOGGER.exception("前台截图失败")
            return ScreenshotResult(False, None, "foreground", f"前台截图失败：{exc}")

    def capture_background(self, hwnd: int) -> ScreenshotResult:
        """
        使用 PrintWindow 尝试后台截图。

        Args:
            hwnd (int): 窗口句柄。

        Returns:
            ScreenshotResult: 截图结果。
        """
        hwnd_dc = None
        window_dc = None
        memory_dc = None
        bitmap = None
        try:
            ensure_hwnd(hwnd)
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = max(0, right - left)
            height = max(0, bottom - top)
            if width <= 0 or height <= 0:
                return ScreenshotResult(False, None, "printwindow", "窗口尺寸无效，无法后台截图")

            hwnd_dc = win32gui.GetWindowDC(hwnd)
            window_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            memory_dc = window_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(window_dc, width, height)
            memory_dc.SelectObject(bitmap)

            result = ctypes.windll.user32.PrintWindow(hwnd, memory_dc.GetSafeHdc(), 2)
            if not result:
                return ScreenshotResult(False, None, "printwindow", f"PrintWindow 失败，LastError={get_last_error()}")

            bmp_info = bitmap.GetInfo()
            bmp_bits = bitmap.GetBitmapBits(True)
            image = Image.frombuffer(
                "RGB",
                (bmp_info["bmWidth"], bmp_info["bmHeight"]),
                bmp_bits,
                "raw",
                "BGRX",
                0,
                1,
            )
            if not image.getbbox():
                return ScreenshotResult(False, None, "printwindow", "PrintWindow 返回空白图像")
            return ScreenshotResult(True, image, "printwindow", "后台截图成功")
        except (ValueError, RuntimeError, OSError) as exc:
            LOGGER.exception("后台截图失败")
            return ScreenshotResult(False, None, "printwindow", f"后台截图失败：{exc}")
        finally:
            if bitmap is not None:
                win32gui.DeleteObject(bitmap.GetHandle())
            if memory_dc is not None:
                memory_dc.DeleteDC()
            if window_dc is not None:
                window_dc.DeleteDC()
            if hwnd_dc is not None:
                win32gui.ReleaseDC(hwnd, hwnd_dc)

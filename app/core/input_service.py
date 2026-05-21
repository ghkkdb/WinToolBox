from __future__ import annotations

import logging
import time

import win32api
import win32clipboard
import win32con
import win32gui
import pywintypes

from app.core.control_service import ControlService
from app.core.win32_utils import ensure_hwnd, get_last_error, pack_lparam
from app.models import OperationResult

LOGGER = logging.getLogger(__name__)


class InputService:
    """提供前台键鼠和后台消息发送能力。"""

    _MESSAGE_MAP: dict[str, int] = {
        "WM_MOUSEMOVE": win32con.WM_MOUSEMOVE,
        "WM_LBUTTONDOWN": win32con.WM_LBUTTONDOWN,
        "WM_LBUTTONUP": win32con.WM_LBUTTONUP,
        "WM_RBUTTONDOWN": win32con.WM_RBUTTONDOWN,
        "WM_RBUTTONUP": win32con.WM_RBUTTONUP,
        "WM_KEYDOWN": win32con.WM_KEYDOWN,
        "WM_KEYUP": win32con.WM_KEYUP,
        "WM_CHAR": win32con.WM_CHAR,
    }
    _MESSAGE_DESCRIPTIONS: dict[str, str] = {
        "WM_MOUSEMOVE": "鼠标移动：把客户区 X/Y 打包进 lParam，告诉目标窗口鼠标移动到了这个位置。",
        "WM_LBUTTONDOWN": "左键按下：wParam 带 MK_LBUTTON，lParam 是客户区 X/Y。通常需要再发 WM_LBUTTONUP 才算一次完整点击。",
        "WM_LBUTTONUP": "左键释放：和 WM_LBUTTONDOWN 配合使用，表示左键在客户区指定位置松开。",
        "WM_RBUTTONDOWN": "右键按下：wParam 带 MK_RBUTTON，lParam 是客户区 X/Y。常用于触发右键菜单前半段。",
        "WM_RBUTTONUP": "右键释放：和 WM_RBUTTONDOWN 配合使用，表示右键在客户区指定位置松开。",
        "WM_KEYDOWN": "键盘按下：wParam 使用虚拟键码，例如 Enter 是 13。后台发送时不一定会被所有程序接受。",
        "WM_KEYUP": "键盘释放：和 WM_KEYDOWN 配合使用，表示某个虚拟键已经松开。",
        "WM_CHAR": "字符输入：wParam 使用字符的 Unicode 编码，适合输入普通文字，不适合模拟功能键。",
    }

    def __init__(self, control_service: ControlService | None = None) -> None:
        """
        初始化输入服务。

        Args:
            control_service (ControlService | None): 窗口控制服务。
        """
        self._control_service = control_service or ControlService()

    @classmethod
    def message_names(cls) -> list[str]:
        """
        获取可发送的后台消息名称。

        Returns:
            list[str]: 消息名称列表。
        """
        return list(cls._MESSAGE_MAP.keys())

    @classmethod
    def message_description(cls, message_name: str) -> str:
        """
        获取后台消息的中文说明。

        Args:
            message_name (str): 消息名称。

        Returns:
            str: 中文说明。
        """
        return cls._MESSAGE_DESCRIPTIONS.get(message_name, "暂无说明。")

    def client_to_screen(self, hwnd: int, x: int, y: int) -> tuple[int, int]:
        """
        将客户区坐标转换为屏幕坐标。

        Args:
            hwnd (int): 窗口句柄。
            x (int): 客户区 X 坐标。
            y (int): 客户区 Y 坐标。

        Returns:
            tuple[int, int]: 屏幕坐标。
        """
        ensure_hwnd(hwnd)
        return win32gui.ClientToScreen(hwnd, (x, y))

    def foreground_click(self, hwnd: int, x: int, y: int, double: bool = False) -> OperationResult:
        """
        对窗口客户区执行前台鼠标点击。

        Args:
            hwnd (int): 窗口句柄。
            x (int): 客户区 X 坐标。
            y (int): 客户区 Y 坐标。
            double (bool): 是否双击。

        Returns:
            OperationResult: 操作结果。
        """
        try:
            ensure_hwnd(hwnd)
            front_result = self._control_service.bring_to_front(hwnd)
            if not front_result.success:
                return front_result
            screen_x, screen_y = self.client_to_screen(hwnd, x, y)
            win32api.SetCursorPos((screen_x, screen_y))
            click_count = 2 if double else 1
            for _ in range(click_count):
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                time.sleep(0.05)
            return OperationResult(True, "前台点击已执行")
        except (ValueError, RuntimeError, OSError) as exc:
            LOGGER.exception("前台点击失败")
            return OperationResult(False, str(exc), None, get_last_error())

    def foreground_type_text(self, hwnd: int, text: str, interval: float = 0.02) -> OperationResult:
        """
        对前台窗口输入文本。

        Args:
            hwnd (int): 窗口句柄。
            text (str): 要输入的文本。
            interval (float): 字符间隔秒数。

        Returns:
            OperationResult: 操作结果。
        """
        try:
            ensure_hwnd(hwnd)
            if not text:
                return OperationResult(True, "前台文本为空，已跳过输入")
            front_result = self._control_service.bring_to_front(hwnd)
            if not front_result.success:
                return front_result
            self._paste_text_via_clipboard(text)
            time.sleep(interval)
            return OperationResult(True, "前台文本输入已执行")
        except (ValueError, RuntimeError, OSError, pywintypes.error) as exc:
            LOGGER.exception("前台文本输入失败")
            return OperationResult(False, str(exc), None, get_last_error())

    def foreground_key(self, hwnd: int, vk_code: int) -> OperationResult:
        """
        对前台窗口发送按键。

        Args:
            hwnd (int): 窗口句柄。
            vk_code (int): 虚拟键码。

        Returns:
            OperationResult: 操作结果。
        """
        try:
            ensure_hwnd(hwnd)
            front_result = self._control_service.bring_to_front(hwnd)
            if not front_result.success:
                return front_result
            win32api.keybd_event(vk_code, 0, 0, 0)
            win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
            return OperationResult(True, f"前台按键已执行：VK={vk_code}")
        except (ValueError, RuntimeError, OSError) as exc:
            LOGGER.exception("前台按键失败")
            return OperationResult(False, str(exc), None, get_last_error())

    def send_background_message(
        self,
        hwnd: int,
        message_name: str,
        x: int = 0,
        y: int = 0,
        vk_code: int = 0,
        char: str = "",
        repeat: int = 1,
        interval: float = 0.02,
    ) -> OperationResult:
        """
        向目标窗口发送后台消息。

        Args:
            hwnd (int): 消息目标窗口句柄。
            message_name (str): 消息名称。
            x (int): 客户区 X 坐标。
            y (int): 客户区 Y 坐标。
            vk_code (int): 虚拟键码。
            char (str): WM_CHAR 使用的字符。
            repeat (int): 重复次数。
            interval (float): 重复间隔秒数。

        Returns:
            OperationResult: 操作结果。
        """
        try:
            ensure_hwnd(hwnd)
            if message_name not in self._MESSAGE_MAP:
                raise ValueError(f"不支持的消息：{message_name}")
            if repeat <= 0:
                raise ValueError("重复次数必须大于 0")

            message = self._MESSAGE_MAP[message_name]
            wparam = self._build_wparam(message_name, vk_code, char)
            lparam = pack_lparam(x, y)
            last_return: int | None = None
            for _ in range(repeat):
                last_return = win32gui.SendMessage(hwnd, message, wparam, lparam)
                time.sleep(interval)
            return OperationResult(
                True,
                f"已发送 {message_name} 到 HWND={hwnd}，wParam={wparam}，lParam={lparam}",
                last_return,
            )
        except (ValueError, RuntimeError, OSError) as exc:
            LOGGER.exception("后台消息发送失败")
            return OperationResult(False, str(exc), None, get_last_error())

    def _build_wparam(self, message_name: str, vk_code: int, char: str) -> int:
        """
        根据消息类型生成 wParam。

        Args:
            message_name (str): 消息名称。
            vk_code (int): 虚拟键码。
            char (str): 字符。

        Returns:
            int: wParam。
        """
        if message_name == "WM_CHAR":
            return ord(char[0]) if char else 0
        if message_name in {"WM_KEYDOWN", "WM_KEYUP"}:
            return vk_code
        if message_name in {"WM_LBUTTONDOWN", "WM_LBUTTONUP"}:
            return win32con.MK_LBUTTON
        if message_name in {"WM_RBUTTONDOWN", "WM_RBUTTONUP"}:
            return win32con.MK_RBUTTON
        return 0

    def _paste_text_via_clipboard(self, text: str) -> None:
        """
        通过剪贴板向前台窗口粘贴 Unicode 文本。

        Args:
            text (str): 要粘贴的文本。
        """
        old_text = self._read_clipboard_text()
        self._set_clipboard_text(text)

        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        win32api.keybd_event(ord("V"), 0, 0, 0)
        win32api.keybd_event(ord("V"), 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)

        if old_text is not None:
            time.sleep(0.05)
            try:
                self._set_clipboard_text(old_text)
            except (RuntimeError, OSError, pywintypes.error):
                LOGGER.exception("恢复剪贴板文本失败")

    def _set_clipboard_text(self, text: str) -> None:
        """
        写入 Unicode 文本到剪贴板。

        Args:
            text (str): 要写入剪贴板的文本。
        """
        win32clipboard.OpenClipboard(None)
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()

    def _read_clipboard_text(self) -> str | None:
        """
        读取当前剪贴板文本，读取失败时返回 None。

        Returns:
            str | None: 剪贴板文本。
        """
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    return str(win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT))
            finally:
                win32clipboard.CloseClipboard()
        except (RuntimeError, OSError, pywintypes.error):
            LOGGER.info("读取剪贴板文本失败，输入完成后将不恢复原文本")
        return None

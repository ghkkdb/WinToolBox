import time
import win32gui
import win32con
import win32api


WINDOW_KEYWORD = "指尖无双"

# 这里是窗口客户区坐标，不是屏幕坐标
LEFT_X = 42
LEFT_Y = 306

RIGHT_X = 270
RIGHT_Y = 321

HOLD_SECONDS = 0.5
MOVE_INTERVAL = 0.03


def find_window_by_title(keyword: str):
    result = []

    def enum_callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return

        title = win32gui.GetWindowText(hwnd)
        if keyword in title:
            result.append((hwnd, title))

    win32gui.EnumWindows(enum_callback, None)

    if not result:
        return None, None

    return result[0]


def make_lparam(x: int, y: int):
    return (y << 16) | (x & 0xFFFF)


def mouse_down(hwnd: int, x: int, y: int):
    lparam = make_lparam(x, y)

    win32api.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)

    win32api.PostMessage(
        hwnd,
        win32con.WM_LBUTTONDOWN,
        win32con.MK_LBUTTON,
        lparam
    )


def mouse_move_hold(hwnd: int, x: int, y: int):
    lparam = make_lparam(x, y)

    win32api.PostMessage(
        hwnd,
        win32con.WM_MOUSEMOVE,
        win32con.MK_LBUTTON,
        lparam
    )


def mouse_up(hwnd: int, x: int, y: int):
    lparam = make_lparam(x, y)

    win32api.PostMessage(
        hwnd,
        win32con.WM_LBUTTONUP,
        0,
        lparam
    )


def hold_click(hwnd: int, x: int, y: int, seconds: float):
    mouse_down(hwnd, x, y)

    end_time = time.time() + seconds

    while time.time() < end_time:
        mouse_move_hold(hwnd, x, y)
        time.sleep(MOVE_INTERVAL)

    mouse_up(hwnd, x, y)


def loop_left_right(hwnd: int):
    print("开始后台循环：左 0.5 秒 -> 右 0.5 秒")
    print("按 Ctrl + C 停止")

    try:
        while True:
            print("左")
            hold_click(hwnd, LEFT_X, LEFT_Y, HOLD_SECONDS)

            print("右")
            hold_click(hwnd, RIGHT_X, RIGHT_Y, HOLD_SECONDS)

    except KeyboardInterrupt:
        print("\n停止，释放鼠标")
        mouse_up(hwnd, LEFT_X, LEFT_Y)
        mouse_up(hwnd, RIGHT_X, RIGHT_Y)


def main():
    hwnd, title = find_window_by_title(WINDOW_KEYWORD)

    if not hwnd:
        print(f"未找到标题包含 [{WINDOW_KEYWORD}] 的窗口")
        return

    print(f"找到窗口：{title}")
    print(f"窗口句柄：{hwnd}")

    loop_left_right(hwnd)


if __name__ == "__main__":
    main()
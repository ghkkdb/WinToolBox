# Windows HWND 交互测试工具

这是一个基于 Python 3.11+、PySide6 和 Win32 API 的 Windows 桌面工具。它用来手动验证指定窗口句柄 `HWND` 的信息读取、前后台键鼠输入、截图和窗口控制能力。

它不是自动化测试框架，也不会自动生成测试报告。它更像一个调试工作台：先绑定一个目标窗口，再逐项测试这个窗口能不能被读取、点击、输入、截图、移动、置顶或关闭。

## 功能

- 枚举当前桌面的可见顶层窗口，并绑定指定 `HWND`
- 通过鼠标拖拽拾取窗口
- 查看窗口标题、类名、PID、线程 ID、进程路径、窗口矩形和客户区矩形
- 枚举子窗口，并把子窗口设置为后台消息目标
- 执行前台点击、双击、按键和文本输入
- 后台发送 `WM_MOUSEMOVE`、鼠标按键、键盘按键和 `WM_CHAR` 消息
- 使用 `mss` 截取前台窗口区域
- 使用 `PrintWindow` 尝试后台截图
- 截图预览、缩放、拖拽裁剪和保存
- 控制窗口显示、隐藏、最小化、最大化、还原、移动、缩放、置顶和关闭
- 在界面和本地日志文件中记录操作结果

## 目录结构

```text
WinToolBox/
|-- app/
|   |-- main.py                  # 应用入口
|   |-- logging_config.py        # 日志路径和日志配置
|   |-- models.py                # 数据模型
|   |-- core/
|   |   |-- window_service.py     # 窗口枚举、拾取、信息读取
|   |   |-- input_service.py      # 前台输入和后台消息
|   |   |-- screenshot_service.py # 前台截图和 PrintWindow 截图
|   |   |-- control_service.py    # 窗口显示、置顶、移动、关闭
|   |   `-- win32_utils.py        # HWND 校验、lParam 打包等工具函数
|   `-- ui/
|       `-- main_window.py        # PySide6 主界面
|-- tests/
|   `-- test_models_and_utils.py  # 纯逻辑单元测试
|-- requirements.txt
|-- requirements-dev.txt
|-- AGENTS.md
`-- README.md
```

## 环境要求

- Windows 10/11
- Python 3.11 或更高版本
- 可以访问桌面会话的普通终端或管理员终端

运行依赖：

- PySide6
- pywin32
- psutil
- Pillow
- mss

开发测试依赖：

- pytest

## 安装和运行

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m app.main
```

如果目标窗口权限高于本工具进程，前台控制、后台消息或截图可能失败。遇到这类情况，可以用管理员身份启动终端后再运行工具。

## 基本使用流程

1. 启动程序后，在顶部窗口列表中选择目标窗口，或按住“按住拖动拾取”按钮拖到目标窗口。
2. 在“窗口信息”页确认绑定到的 `HWND`、标题、类名和进程信息。
3. 在“键鼠消息”页测试前台输入或后台消息。
4. 在“截图”页测试前台截图、后台截图、裁剪和保存。
5. 在“窗口控制”页测试置前、焦点、显示状态、移动缩放、置顶和关闭。

界面大致结构：

```text
+--------------------------------------------------+
| 工具栏：刷新窗口 / 选择窗口 / 拾取窗口 / 当前 HWND |
+--------------------------------------------------+
| 标签页                                             |
|  |-- 窗口信息                                      |
|  |-- 键鼠消息                                      |
|  |-- 截图                                          |
|  `-- 窗口控制                                      |
+--------------------------------------------------+
| 操作日志                                           |
+--------------------------------------------------+
```

## 后台消息说明

后台消息通过 Win32 `SendMessage` 发送到目标窗口或子窗口。工具内置了常用消息：

- `WM_MOUSEMOVE`
- `WM_LBUTTONDOWN`
- `WM_LBUTTONUP`
- `WM_RBUTTONDOWN`
- `WM_RBUTTONUP`
- `WM_KEYDOWN`
- `WM_KEYUP`
- `WM_CHAR`

不是所有程序都会处理后台消息。很多游戏、浏览器、UWP 应用、DirectX 应用或高权限窗口会忽略这类消息，这是目标程序或 Windows 机制决定的，不一定是工具错误。

## 截图限制

前台截图使用 `mss` 截取屏幕上的窗口矩形区域。窗口如果被遮挡，截图也可能包含遮挡内容。

后台截图优先使用 `PrintWindow`。某些 DirectX、浏览器 GPU 渲染、UWP、高权限窗口可能返回黑图、空图或失败。工具会在日志中记录失败原因。

## 日志

程序日志默认写入：

```text
logs/app.log
logs/runtime.log
```

`logs/` 是运行时目录，不建议提交到 GitHub。

## 运行测试

安装开发依赖：

```powershell
pip install -r requirements-dev.txt
```

运行测试：

```powershell
pytest
```

当前测试主要覆盖不依赖真实窗口的纯逻辑代码，例如矩形模型、`HWND` 校验和 Win32 消息参数打包。

## 打包

默认使用 PyInstaller，并建议新建干净虚拟环境：

```powershell
py -3.11 -m venv .venv-build
.\.venv-build\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --windowed --name HWNDWorkbench app\main.py
```

打包产物会生成在 `dist/` 下，构建中间文件会生成在 `build/` 下，这些目录不需要提交到 GitHub。

## 提交到 GitHub 前建议

确认不要提交虚拟环境、日志、缓存和临时截图：

```powershell
git status --short
```

建议只提交源码、测试、依赖文件和文档：

```powershell
git add app tests requirements.txt requirements-dev.txt AGENTS.md README.md .gitignore
git commit -m "docs: update project documentation"
git push
```

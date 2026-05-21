# 项目开发规则

## 语言与文档

- 默认使用简体中文交流、说明和编写文档。
- 面向用户的说明要先讲清楚“是什么、为什么、怎么改”，再补充必要技术细节。
- 涉及复杂界面、目录结构或窗口关系时，优先用简洁文字或 ASCII Art 辅助说明。

## Python 代码规范

- 项目运行目标为 Windows，主要依赖 Python 3.11+、PySide6、pywin32、psutil、Pillow 和 mss。
- 新增或修改 Python 函数必须包含完整类型提示，参数和返回值都要写清楚。
- 新增函数应提供有实际信息的 Docstring；无返回值必须标注 `-> None`。
- Docstring 优先使用 `Args`、`Returns`、`Raises` 结构；仅在函数会主动抛出或重点处理异常时写 `Raises`。
- 遵守 DRY 原则，避免重复逻辑；函数职责保持单一，复杂逻辑拆成清晰的小函数，但不要为了拆分而过度设计。

## 路径、编码与资源

- 路径处理优先使用 `pathlib` 或 `os.path.join`，禁止手动拼接路径字符串。
- 文本读写必须显式指定 `encoding="utf-8"`。
- 读取项目内文件时，应通过项目根目录或当前文件位置动态计算绝对路径，不依赖当前工作目录。
- 日志默认写入项目根目录下的 `logs/`，该目录不应提交到 Git。

## 异常处理

- 禁止使用裸捕获 `except:`。
- 禁止无理由使用宽泛捕获 `except Exception:`。
- 应优先捕获具体异常类型，并记录有效错误日志。
- 仅在程序入口、任务调度边界、线程/进程边界、GUI 主循环等兜底场景允许使用 `except Exception:`，并必须记录完整错误信息。

## 变更原则

- 遵守最小化变动原则，只修改完成目标所必需的代码。
- 不改动无关模块，不改变无关逻辑，不随意调整代码结构。
- 除非明确要求重构，否则不得大规模重写、替换框架、改变公共接口或调整原有业务流程。
- Windows API 行为差异较多，修改 HWND、消息、截图、焦点相关逻辑时要保留失败日志和用户可读提示。

## 测试与验证

- 修改纯逻辑代码后，优先运行：

```powershell
pytest
```

- 涉及真实窗口、前后台输入、截图或焦点控制时，需要在 Windows 桌面环境中手动验证。
- 后台消息和 `PrintWindow` 截图受目标程序、权限、渲染方式影响，不能假设所有窗口都支持。

## 打包规则

- 打包 Python 桌面程序默认使用 PyInstaller。
- 打包前必须新建干净虚拟环境，只安装运行所需依赖。
- 不要把 `.venv/`、`.venv-build/`、`dist/`、`build/`、日志、缓存文件提交到 Git。

推荐打包命令：

```powershell
py -3.11 -m venv .venv-build
.\.venv-build\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --windowed --name HWNDWorkbench app\main.py
```

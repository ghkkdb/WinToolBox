from __future__ import annotations

import io
import logging
from typing import Callable

import win32api
import win32con
from PIL import Image
from PySide6.QtCore import QBuffer, QByteArray, QEvent, QIODevice, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QCursor,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.control_service import ControlService
from app.core.input_service import InputService
from app.core.screenshot_service import ScreenshotService
from app.core.window_service import WindowService
from app.models import OperationResult, ScreenshotResult, WindowCommand, WindowInfo

LOGGER = logging.getLogger(__name__)


class QtLogHandler(logging.Handler):
    """把 logging 日志追加到 QTextEdit。"""

    def __init__(self, append_text: Callable[[str], None]) -> None:
        """
        初始化日志处理器。

        Args:
            append_text (Callable[[str], None]): 追加日志文本的回调。
        """
        super().__init__()
        self._append_text = append_text

    def emit(self, record: logging.LogRecord) -> None:
        """
        输出一条日志记录。

        Args:
            record (logging.LogRecord): 日志记录。
        """
        try:
            self._append_text(self.format(record))
        except RuntimeError:
            self.handleError(record)


class CropPreviewLabel(QLabel):
    """支持截图预览和拖拽裁剪框的图片控件。"""

    def __init__(self) -> None:
        """初始化截图预览控件。"""
        super().__init__("暂无截图")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(320)
        self.setMouseTracking(True)
        self._source_pixmap: QPixmap | None = None
        self._source_size: tuple[int, int] | None = None
        self._zoom_percent = 100
        self._selection: QRect | None = None
        self._drag_start: QPoint | None = None

    def set_preview_pixmap(self, pixmap: QPixmap, image_size: tuple[int, int]) -> None:
        """
        设置待预览的原始截图。

        Args:
            pixmap (QPixmap): 原始截图位图。
            image_size (tuple[int, int]): 原始图片宽高。
        """
        self._source_pixmap = pixmap
        self._source_size = image_size
        self._selection = None
        self._drag_start = None
        self.setText("")
        self._update_display_size()
        self.update()

    def set_zoom(self, zoom_percent: int) -> None:
        """
        设置截图预览缩放比例。

        Args:
            zoom_percent (int): 缩放百分比。
        """
        self._zoom_percent = max(10, zoom_percent)
        self._update_display_size()
        self.update()

    def clear_selection(self) -> None:
        """清空当前裁剪框。"""
        self._selection = None
        self._drag_start = None
        self.update()

    def set_crop_rect(self, left: int, top: int, right: int, bottom: int) -> None:
        """
        按原图坐标设置预览裁剪框。

        Args:
            left (int): 左边界。
            top (int): 上边界。
            right (int): 右边界。
            bottom (int): 下边界。
        """
        if self._source_size is None:
            return
        target = self._target_rect()
        image_width, image_height = self._source_size
        if target.width() <= 0 or target.height() <= 0 or image_width <= 0 or image_height <= 0:
            return
        x_scale = target.width() / image_width
        y_scale = target.height() / image_height
        start = QPoint(target.left() + int(left * x_scale), target.top() + int(top * y_scale))
        end = QPoint(target.left() + int(right * x_scale), target.top() + int(bottom * y_scale))
        self._selection = QRect(start, end)
        self.update()

    def crop_rect(self) -> tuple[int, int, int, int] | None:
        """
        获取当前裁剪框对应的原图坐标。

        Returns:
            tuple[int, int, int, int] | None: left、top、right、bottom；没有有效裁剪框时返回 None。
        """
        if self._selection is None or self._source_size is None:
            return None
        target = self._target_rect()
        selected = self._selection.normalized().intersected(target)
        if target.width() <= 0 or target.height() <= 0 or selected.width() < 2 or selected.height() < 2:
            return None

        image_width, image_height = self._source_size
        scale_x = image_width / target.width()
        scale_y = image_height / target.height()
        left = int((selected.left() - target.left()) * scale_x)
        top = int((selected.top() - target.top()) * scale_y)
        right = int((selected.right() - target.left() + 1) * scale_x)
        bottom = int((selected.bottom() - target.top() + 1) * scale_y)
        return (
            max(0, left),
            max(0, top),
            min(image_width, right),
            min(image_height, bottom),
        )

    def paintEvent(self, event: QEvent) -> None:
        """
        绘制截图和裁剪框。

        Args:
            event (QEvent): 绘制事件。
        """
        if self._source_pixmap is None:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111827"))
        target = self._target_rect()
        painter.drawPixmap(target, self._source_pixmap)

        if self._selection is not None:
            selected = self._selection.normalized().intersected(target)
            overlay = QColor(37, 99, 235, 45)
            painter.fillRect(selected, overlay)
            pen = QPen(QColor("#facc15"), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(selected)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        开始绘制裁剪框。

        Args:
            event (QMouseEvent): 鼠标事件。
        """
        if event.button() == Qt.MouseButton.LeftButton and self._source_pixmap is not None:
            self._drag_start = event.position().toPoint()
            self._selection = QRect(self._drag_start, self._drag_start)
            self.update()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        拖动更新裁剪框。

        Args:
            event (QMouseEvent): 鼠标事件。
        """
        if self._drag_start is not None:
            self._selection = QRect(self._drag_start, event.position().toPoint())
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        结束裁剪框拖动。

        Args:
            event (QMouseEvent): 鼠标事件。
        """
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start is not None:
            self._selection = QRect(self._drag_start, event.position().toPoint())
            self._drag_start = None
            self.update()
            return
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QEvent) -> None:
        """
        控件尺寸变化时重绘预览。

        Args:
            event (QEvent): 尺寸事件。
        """
        self.update()
        super().resizeEvent(event)

    def _target_rect(self) -> QRect:
        """
        计算图片在控件中的实际显示区域。

        Returns:
            QRect: 图片显示区域。
        """
        if self._source_size is None:
            return QRect()
        image_width, image_height = self._source_size
        if image_width <= 0 or image_height <= 0:
            return QRect()
        scale = self._zoom_percent / 100
        width = max(1, int(image_width * scale))
        height = max(1, int(image_height * scale))
        left = (self.width() - width) // 2
        top = (self.height() - height) // 2
        return QRect(left, top, width, height)

    def _update_display_size(self) -> None:
        """根据原图尺寸和缩放比例更新控件尺寸。"""
        if self._source_size is None:
            return
        image_width, image_height = self._source_size
        scale = self._zoom_percent / 100
        width = max(320, int(image_width * scale) + 20)
        height = max(260, int(image_height * scale) + 20)
        self.setMinimumSize(width, height)
        self.resize(width, height)


class MainWindow(QMainWindow):
    """HWND 交互测试工具主窗口。"""

    def __init__(self) -> None:
        """初始化主窗口和服务对象。"""
        super().__init__()
        self.setWindowTitle("Windows HWND 交互测试工具")
        self.setFixedSize(980, 760)

        self.window_service = WindowService()
        self.control_service = ControlService()
        self.input_service = InputService(self.control_service)
        self.screenshot_service = ScreenshotService()

        self.bound_hwnd: int | None = None
        self.message_target_hwnd: int | None = None
        self._current_mouse_client_pos: tuple[int, int] | None = None
        self._f8_was_down = False
        self._latest_image: Image.Image | None = None
        self._pick_timer = QTimer(self)
        self._pick_timer.setInterval(120)
        self._pick_timer.timeout.connect(self._update_pick_candidate)
        self._is_picking = False
        self._mouse_position_timer = QTimer(self)
        self._mouse_position_timer.setInterval(100)
        self._mouse_position_timer.timeout.connect(self._update_bound_mouse_position)
        self._mouse_position_timer.start()

        self._build_actions()
        self._build_ui()
        self._apply_modern_style()
        self._attach_logger()
        self.refresh_windows()

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        关闭窗口时清理日志处理器。

        Args:
            event (QCloseEvent): 关闭事件。
        """
        root = logging.getLogger()
        for handler in list(root.handlers):
            if isinstance(handler, QtLogHandler):
                root.removeHandler(handler)
        super().closeEvent(event)

    def _build_actions(self) -> None:
        """创建顶部工具栏动作。"""
        toolbar = self.addToolBar("主工具栏")
        toolbar.setMovable(False)

        refresh_action = QAction("刷新窗口", self)
        refresh_action.triggered.connect(self.refresh_windows)
        toolbar.addAction(refresh_action)

        self.window_combo = QComboBox()
        self.window_combo.setMinimumWidth(420)
        self.window_combo.setMaximumWidth(520)
        self.window_combo.setToolTip("选择一个顶层窗口后自动绑定")
        self.window_combo.activated.connect(lambda _: self.bind_selected_window())
        toolbar.addWidget(self.window_combo)

        self.pick_button = QPushButton("按住拖动拾取")
        self.pick_button.setToolTip("按住按钮拖到目标窗口，松开鼠标后绑定当前位置的 HWND")
        self.pick_button.setCursor(Qt.CursorShape.CrossCursor)
        self.pick_button.installEventFilter(self)
        toolbar.addWidget(self.pick_button)

        toolbar.addSeparator()
        self.bound_label = QLabel("当前绑定 HWND：未绑定")
        self.bound_label.setObjectName("boundLabel")
        toolbar.addWidget(self.bound_label)

    def _build_ui(self) -> None:
        """创建主界面布局。"""
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(110)
        self.log_text.setMaximumHeight(150)

        root_layout.addWidget(self._create_right_panel(), 1)
        root_layout.addWidget(self._group_box("操作日志", self.log_text))
        self.setCentralWidget(root)

    def _create_left_panel(self) -> QWidget:
        """
        创建左侧窗口选择区域。

        Returns:
            QWidget: 左侧面板。
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(10)

        self.window_tree = QTreeWidget()
        self.window_tree.setHeaderLabels(["HWND / 标题", "类名", "进程"])
        self.window_tree.itemDoubleClicked.connect(lambda item, _: self._bind_from_item(item))
        self.window_tree.setAlternatingRowColors(True)
        self.window_tree.setRootIsDecorated(False)
        self.window_tree.header().setStretchLastSection(False)
        self.window_tree.setColumnWidth(0, 170)
        self.window_tree.setColumnWidth(1, 120)

        self.child_tree = QTreeWidget()
        self.child_tree.setHeaderLabels(["子窗口 HWND / 标题", "类名", "进程"])
        self.child_tree.itemDoubleClicked.connect(lambda item, _: self._set_message_target_from_item(item))
        self.child_tree.setAlternatingRowColors(True)
        self.child_tree.setRootIsDecorated(False)
        self.child_tree.header().setStretchLastSection(False)
        self.child_tree.setColumnWidth(0, 170)
        self.child_tree.setColumnWidth(1, 120)

        layout.addWidget(self._group_box("顶层窗口（双击绑定）", self.window_tree), 2)
        layout.addWidget(self._group_box("子窗口（双击设为后台消息目标）", self.child_tree), 2)
        return panel

    def _create_right_panel(self) -> QWidget:
        """
        创建右侧功能测试区域。

        Returns:
            QWidget: 右侧面板。
        """
        tabs = QTabWidget()
        tabs.addTab(self._scroll_page([self._create_info_group(), self._create_control_group()]), "窗口信息")
        tabs.addTab(self._scroll_page([self._create_foreground_input_group(), self._create_background_message_group()]), "键鼠消息")
        tabs.addTab(self._scroll_page([self._create_screenshot_group()]), "截图")
        return tabs

    def _create_info_group(self) -> QGroupBox:
        """
        创建窗口信息分组。

        Returns:
            QGroupBox: 信息分组。
        """
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMinimumHeight(120)
        refresh_button = QPushButton("刷新绑定窗口信息")
        refresh_button.clicked.connect(self.refresh_bound_info)

        layout = QVBoxLayout()
        layout.addWidget(self.info_text)
        layout.addWidget(refresh_button)
        box = QGroupBox("窗口信息")
        box.setLayout(layout)
        return box

    def _create_foreground_input_group(self) -> QGroupBox:
        """
        创建前台键鼠分组。

        Returns:
            QGroupBox: 前台键鼠分组。
        """
        self.fg_x_spin = self._spin_box(0, 99999, 20)
        self.fg_y_spin = self._spin_box(0, 99999, 20)
        self.fg_vk_spin = self._spin_box(0, 255, 13)
        self.fg_text_input = QLineEdit()
        self.fg_text_input.setMaximumWidth(260)
        self.mouse_position_label = QLabel("鼠标相对坐标：未绑定窗口。鼠标停到目标窗口后按 F8 固定到 X/Y")
        self.mouse_position_label.setObjectName("hintLabel")

        click_button = QPushButton("前台点击")
        click_button.clicked.connect(lambda: self._run_operation(self._foreground_click))
        double_click_button = QPushButton("前台双击")
        double_click_button.clicked.connect(lambda: self._run_operation(lambda: self._foreground_click(True)))
        key_button = QPushButton("前台按键")
        key_button.clicked.connect(lambda: self._run_operation(self._foreground_key))
        type_button = QPushButton("前台输入文本")
        type_button.clicked.connect(lambda: self._run_operation(self._foreground_type_text))

        for spin_box in (self.fg_x_spin, self.fg_y_spin, self.fg_vk_spin):
            spin_box.setFixedWidth(120)

        mouse_title = QLabel("鼠标操作")
        mouse_title.setObjectName("sectionTitle")
        mouse_layout = QGridLayout()
        mouse_layout.setHorizontalSpacing(10)
        mouse_layout.setVerticalSpacing(6)
        mouse_layout.addWidget(self._form_label("客户区 X"), 0, 0)
        mouse_layout.addWidget(self.fg_x_spin, 0, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        mouse_layout.addWidget(self._form_label("客户区 Y"), 0, 2)
        mouse_layout.addWidget(self.fg_y_spin, 0, 3, alignment=Qt.AlignmentFlag.AlignLeft)
        mouse_layout.addWidget(click_button, 0, 4)
        mouse_layout.addWidget(double_click_button, 0, 5)
        mouse_layout.setColumnStretch(6, 1)

        keyboard_title = QLabel("键盘操作")
        keyboard_title.setObjectName("sectionTitle")
        keyboard_layout = QGridLayout()
        keyboard_layout.setHorizontalSpacing(10)
        keyboard_layout.setVerticalSpacing(6)
        keyboard_layout.addWidget(self._form_label("虚拟键码"), 0, 0)
        keyboard_layout.addWidget(self.fg_vk_spin, 0, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        keyboard_layout.addWidget(self._form_label("文本"), 0, 2)
        keyboard_layout.addWidget(self.fg_text_input, 0, 3, alignment=Qt.AlignmentFlag.AlignLeft)
        keyboard_layout.addWidget(key_button, 0, 4)
        keyboard_layout.addWidget(type_button, 0, 5)
        keyboard_layout.setColumnStretch(6, 1)

        layout = QVBoxLayout()
        layout.addWidget(self.mouse_position_label)
        layout.addWidget(mouse_title)
        layout.addLayout(mouse_layout)
        layout.addWidget(keyboard_title)
        layout.addLayout(keyboard_layout)
        box = QGroupBox("前台键鼠操作")
        box.setLayout(layout)
        return box

    def _create_background_message_group(self) -> QGroupBox:
        """
        创建后台消息分组。

        Returns:
            QGroupBox: 后台消息分组。
        """
        self.msg_name_combo = QComboBox()
        self.msg_name_combo.addItems(self.input_service.message_names())
        self.msg_name_combo.currentTextChanged.connect(self._update_message_description)
        self.msg_name_combo.setMaximumWidth(360)
        self.msg_x_spin = self._spin_box(0, 99999, 20)
        self.msg_y_spin = self._spin_box(0, 99999, 20)
        self.msg_vk_spin = self._spin_box(0, 255, 13)
        self.msg_char_input = QLineEdit()
        self.msg_char_input.setMaxLength(1)
        self.msg_char_input.setMaximumWidth(140)
        self.msg_repeat_spin = self._spin_box(1, 1000, 1)
        self.msg_interval_spin = self._spin_box(0, 10000, 20)
        for spin_box in (
            self.msg_x_spin,
            self.msg_y_spin,
            self.msg_vk_spin,
            self.msg_repeat_spin,
            self.msg_interval_spin,
        ):
            spin_box.setFixedWidth(120)

        send_button = QPushButton("发送当前原始消息")
        send_button.setMaximumWidth(220)
        send_button.clicked.connect(lambda: self._run_operation(self._send_background_message))

        quick_layout = QGridLayout()
        quick_layout.setHorizontalSpacing(8)
        quick_layout.setVerticalSpacing(6)
        quick_actions = [
            ("鼠标移动", ("WM_MOUSEMOVE",)),
            ("左键点击", ("WM_LBUTTONDOWN", "WM_LBUTTONUP")),
            ("右键点击", ("WM_RBUTTONDOWN", "WM_RBUTTONUP")),
            ("按键一次", ("WM_KEYDOWN", "WM_KEYUP")),
            ("发送字符", ("WM_CHAR",)),
        ]
        for index, (label, sequence) in enumerate(quick_actions):
            button = QPushButton(label)
            button.setToolTip("按当前坐标、键码或字符参数发送完整后台动作")
            button.clicked.connect(lambda _, value=sequence, text=label: self._quick_send_message(value, text))
            quick_layout.addWidget(button, index // 4, index % 4)

        self.msg_description_label = QLabel()
        self.msg_description_label.setObjectName("hintLabel")
        self.msg_description_label.setWordWrap(True)
        self._update_message_description(self.msg_name_combo.currentText())

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        form.addWidget(self._form_label("消息"), 0, 0)
        form.addWidget(self.msg_name_combo, 0, 1, 1, 5, alignment=Qt.AlignmentFlag.AlignLeft)
        form.addWidget(self._form_label("客户区 X"), 1, 0)
        form.addWidget(self.msg_x_spin, 1, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        form.addWidget(self._form_label("客户区 Y"), 1, 2)
        form.addWidget(self.msg_y_spin, 1, 3, alignment=Qt.AlignmentFlag.AlignLeft)
        form.addWidget(self._form_label("虚拟键码"), 2, 0)
        form.addWidget(self.msg_vk_spin, 2, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        form.addWidget(self._form_label("字符"), 2, 2)
        form.addWidget(self.msg_char_input, 2, 3, alignment=Qt.AlignmentFlag.AlignLeft)
        form.addWidget(self._form_label("重复次数"), 3, 0)
        form.addWidget(self.msg_repeat_spin, 3, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        form.addWidget(self._form_label("间隔毫秒"), 3, 2)
        form.addWidget(self.msg_interval_spin, 3, 3, alignment=Qt.AlignmentFlag.AlignLeft)
        form.setColumnStretch(4, 1)

        layout = QVBoxLayout()
        layout.addWidget(self.msg_description_label)
        layout.addLayout(form)
        layout.addWidget(send_button)
        layout.addLayout(quick_layout)
        box = QGroupBox("后台键鼠消息")
        box.setLayout(layout)
        return box

    def _create_screenshot_group(self) -> QGroupBox:
        """
        创建截图分组。

        Returns:
            QGroupBox: 截图分组。
        """
        self.preview_label = CropPreviewLabel()
        self.preview_label.setStyleSheet("border: 1px solid #9ca3af; background: #111827; color: #e5e7eb;")
        self.image_resolution_label = QLabel("图片分辨率：暂无截图")
        self.image_resolution_label.setObjectName("hintLabel")
        self.zoom_spin = self._spin_box(25, 400, 100)
        self.zoom_spin.setSuffix("%")
        self.zoom_spin.valueChanged.connect(self.preview_label.set_zoom)
        self.crop_left_spin = self._spin_box(0, 99999, 0)
        self.crop_top_spin = self._spin_box(0, 99999, 0)
        self.crop_right_spin = self._spin_box(0, 99999, 0)
        self.crop_bottom_spin = self._spin_box(0, 99999, 0)
        for spin_box in (
            self.zoom_spin,
            self.crop_left_spin,
            self.crop_top_spin,
            self.crop_right_spin,
            self.crop_bottom_spin,
        ):
            spin_box.setMaximumWidth(110)

        foreground_button = QPushButton("前台截图")
        foreground_button.clicked.connect(self.capture_foreground)
        background_button = QPushButton("后台截图 PrintWindow")
        background_button.clicked.connect(self.capture_background)
        crop_button = QPushButton("裁剪并保存")
        crop_button.clicked.connect(self.crop_and_save_latest_image)
        apply_crop_button = QPushButton("应用坐标框")
        apply_crop_button.clicked.connect(self.apply_crop_inputs_to_preview)
        read_crop_button = QPushButton("读取预览框坐标")
        read_crop_button.clicked.connect(self.read_preview_crop_to_inputs)
        clear_crop_button = QPushButton("清除裁剪框")
        clear_crop_button.clicked.connect(self.preview_label.clear_selection)
        save_button = QPushButton("保存截图")
        save_button.clicked.connect(self.save_latest_image)
        for button in (
            foreground_button,
            background_button,
            crop_button,
            apply_crop_button,
            read_crop_button,
            clear_crop_button,
            save_button,
        ):
            button.setMaximumWidth(150)

        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(False)
        preview_scroll.setFrameShape(QFrame.Shape.NoFrame)
        preview_scroll.setWidget(self.preview_label)

        crop_form = QGridLayout()
        crop_form.setHorizontalSpacing(10)
        crop_form.setVerticalSpacing(8)
        crop_form.addWidget(QLabel("缩放"), 0, 0)
        crop_form.addWidget(self.zoom_spin, 0, 1)
        crop_form.addWidget(QLabel("左"), 1, 0)
        crop_form.addWidget(self.crop_left_spin, 1, 1)
        crop_form.addWidget(QLabel("上"), 1, 2)
        crop_form.addWidget(self.crop_top_spin, 1, 3)
        crop_form.addWidget(QLabel("右"), 2, 0)
        crop_form.addWidget(self.crop_right_spin, 2, 1)
        crop_form.addWidget(QLabel("下"), 2, 2)
        crop_form.addWidget(self.crop_bottom_spin, 2, 3)
        crop_form.addWidget(apply_crop_button, 3, 0, 1, 2)
        crop_form.addWidget(read_crop_button, 3, 2, 1, 2)

        button_layout = QHBoxLayout()
        button_layout.addWidget(foreground_button)
        button_layout.addWidget(background_button)
        button_layout.addWidget(save_button)
        button_layout.addStretch(1)

        crop_button_layout = QHBoxLayout()
        crop_button_layout.addWidget(crop_button)
        crop_button_layout.addWidget(clear_crop_button)
        crop_button_layout.addStretch(1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(self.image_resolution_label)
        right_layout.addLayout(crop_form)
        right_layout.addLayout(button_layout)
        right_layout.addLayout(crop_button_layout)
        right_layout.addStretch(1)

        layout = QHBoxLayout()
        layout.addWidget(preview_scroll, 3)
        layout.addWidget(right_panel, 2)
        box = QGroupBox("截图")
        box.setLayout(layout)
        return box

    def _create_control_group(self) -> QGroupBox:
        """
        创建窗口控制分组。

        Returns:
            QGroupBox: 控制分组。
        """
        self.move_x_spin = self._spin_box(-99999, 99999, 100)
        self.move_y_spin = self._spin_box(-99999, 99999, 100)
        self.move_w_spin = self._spin_box(1, 99999, 800)
        self.move_h_spin = self._spin_box(1, 99999, 600)
        self.topmost_check = QCheckBox("置顶")

        command_layout = QGridLayout()
        command_layout.setHorizontalSpacing(8)
        command_layout.setVerticalSpacing(8)
        commands = [
            ("显示", WindowCommand.SHOW),
            ("隐藏", WindowCommand.HIDE),
            ("最小化", WindowCommand.MINIMIZE),
            ("最大化", WindowCommand.MAXIMIZE),
            ("还原", WindowCommand.RESTORE),
        ]
        for index, (label, command) in enumerate(commands):
            button = QPushButton(label)
            button.setMaximumWidth(110)
            button.clicked.connect(lambda _, value=command: self._run_operation(lambda: self._show_window(value)))
            command_layout.addWidget(button, 0, index)
        command_layout.setColumnStretch(len(commands), 1)

        front_button = QPushButton("置前")
        front_button.clicked.connect(lambda: self._run_operation(self._bring_to_front))
        focus_button = QPushButton("设置焦点")
        focus_button.clicked.connect(lambda: self._run_operation(self._set_focus))
        move_button = QPushButton("移动/缩放")
        move_button.clicked.connect(lambda: self._run_operation(self._move_window))
        topmost_button = QPushButton("应用置顶状态")
        topmost_button.clicked.connect(lambda: self._run_operation(self._set_topmost))
        close_button = QPushButton("关闭窗口")
        close_button.clicked.connect(self.close_bound_window)
        for button in (front_button, focus_button, move_button, topmost_button, close_button):
            button.setMaximumWidth(120)

        move_layout = QGridLayout()
        move_layout.setHorizontalSpacing(10)
        move_layout.setVerticalSpacing(8)
        move_layout.addWidget(QLabel("X"), 0, 0)
        move_layout.addWidget(self.move_x_spin, 0, 1)
        move_layout.addWidget(QLabel("Y"), 0, 2)
        move_layout.addWidget(self.move_y_spin, 0, 3)
        move_layout.addWidget(QLabel("宽"), 0, 4)
        move_layout.addWidget(self.move_w_spin, 0, 5)
        move_layout.addWidget(QLabel("高"), 0, 6)
        move_layout.addWidget(self.move_h_spin, 0, 7)
        move_layout.addWidget(self.topmost_check, 0, 8)
        move_layout.setColumnStretch(9, 1)

        button_layout = QHBoxLayout()
        button_layout.addWidget(front_button)
        button_layout.addWidget(focus_button)
        button_layout.addWidget(move_button)
        button_layout.addWidget(topmost_button)
        button_layout.addWidget(close_button)
        button_layout.addStretch(1)

        layout = QVBoxLayout()
        layout.addLayout(command_layout)
        layout.addLayout(move_layout)
        layout.addLayout(button_layout)
        box = QGroupBox("窗口控制")
        box.setLayout(layout)
        return box

    def refresh_windows(self) -> None:
        """刷新顶层窗口列表。"""
        current_hwnd = self.bound_hwnd
        self.window_combo.blockSignals(True)
        self.window_combo.clear()
        for info in self.window_service.enumerate_top_windows():
            label = f"{info.hwnd} / {info.title or '<无标题>'} / {info.class_name}"
            self.window_combo.addItem(label, info.hwnd)
            if current_hwnd == info.hwnd:
                self.window_combo.setCurrentIndex(self.window_combo.count() - 1)
        self.window_combo.blockSignals(False)
        self._log_info("已刷新顶层窗口下拉列表")

    def bind_selected_window(self) -> None:
        """绑定顶部下拉框当前选中的窗口。"""
        hwnd = self.window_combo.currentData()
        if not isinstance(hwnd, int):
            self._log_info("请先选择一个顶层窗口")
            return
        self._bind_window(hwnd)

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        """
        处理拾取按钮的拖放事件。

        Args:
            watched (object): 触发事件的对象。
            event (QEvent): Qt 事件。

        Returns:
            bool: 事件是否已处理。
        """
        if watched is self.pick_button:
            if event.type() == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._start_pick_mode()
                    return True
            if event.type() == QEvent.Type.MouseButtonRelease and isinstance(event, QMouseEvent):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._finish_pick_mode()
                    return True
        return super().eventFilter(watched, event)

    def _start_pick_mode(self) -> None:
        """开始按住拖动拾取窗口。"""
        self._is_picking = True
        self.pick_button.setText("松开绑定窗口")
        self.pick_button.setDown(True)
        self.pick_button.grabMouse()
        self._pick_timer.start()
        self._update_pick_candidate()
        self._log_info("正在拾取窗口：拖到目标窗口后松开鼠标")

    def _finish_pick_mode(self) -> None:
        """结束拾取并绑定当前鼠标位置下的窗口。"""
        if not self._is_picking:
            return
        self._pick_timer.stop()
        self.pick_button.releaseMouse()
        self.pick_button.setText("按住拖动拾取")
        self.pick_button.setDown(False)
        self._is_picking = False
        pos: QPoint = QCursor.pos()
        try:
            info = self.window_service.window_from_point(pos.x(), pos.y())
            self._bind_window(info.hwnd)
        except (ValueError, RuntimeError, OSError) as exc:
            LOGGER.exception("拾取窗口失败")
            self._log_info(f"拾取窗口失败：{exc}")

    def _cancel_pick_mode(self) -> None:
        """取消当前拾取操作。"""
        self._pick_timer.stop()
        self.pick_button.releaseMouse()
        self.pick_button.setText("按住拖动拾取")
        self.pick_button.setDown(False)
        self._is_picking = False
        self._log_info("已取消拾取窗口")

    def refresh_bound_info(self) -> None:
        """刷新当前绑定窗口信息和子窗口树。"""
        if self.bound_hwnd is None:
            self._log_info("尚未绑定窗口")
            return
        try:
            info = self.window_service.get_window_info(self.bound_hwnd)
            self._show_window_info(info)
            self._load_child_windows(self.bound_hwnd)
            self._log_info(f"已刷新绑定窗口信息 HWND={self.bound_hwnd}")
        except (ValueError, RuntimeError, OSError) as exc:
            LOGGER.exception("刷新绑定窗口信息失败")
            self._log_info(f"刷新绑定窗口信息失败：{exc}")

    def capture_foreground(self) -> None:
        """执行前台截图并预览。"""
        hwnd = self._require_bound_hwnd()
        if hwnd is None:
            return
        self._handle_screenshot_result(self.screenshot_service.capture_foreground(hwnd))

    def capture_background(self) -> None:
        """执行后台截图并预览。"""
        hwnd = self._require_bound_hwnd()
        if hwnd is None:
            return
        self._handle_screenshot_result(self.screenshot_service.capture_background(hwnd))

    def save_latest_image(self) -> None:
        """保存最近一次截图。"""
        if self._latest_image is None:
            self._log_info("没有可保存的截图")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存截图", "screenshot.png", "PNG 图片 (*.png)")
        if not path:
            return
        self._latest_image.save(path)
        self._log_info(f"截图已保存：{path}")

    def lock_current_mouse_position(self) -> None:
        """固定当前鼠标相对坐标到前台和后台键鼠参数。"""
        if self._current_mouse_client_pos is None:
            self._log_info("当前没有可固定的鼠标相对坐标")
            return
        x, y = self._current_mouse_client_pos
        self.fg_x_spin.setValue(x)
        self.fg_y_spin.setValue(y)
        self.msg_x_spin.setValue(x)
        self.msg_y_spin.setValue(y)
        self._log_info(f"已固定当前相对坐标：X={x}，Y={y}")

    def _sync_window_combo_to_bound(self, info: WindowInfo) -> None:
        """
        将顶部窗口下拉框同步到当前绑定窗口。

        Args:
            info (WindowInfo): 当前绑定窗口信息。
        """
        self.window_combo.blockSignals(True)
        for index in range(self.window_combo.count()):
            if self.window_combo.itemData(index) == info.hwnd:
                self.window_combo.setCurrentIndex(index)
                self.window_combo.blockSignals(False)
                return
        label = f"{info.hwnd} / {info.title or '<无标题>'} / {info.class_name}"
        self.window_combo.addItem(label, info.hwnd)
        self.window_combo.setCurrentIndex(self.window_combo.count() - 1)
        self.window_combo.blockSignals(False)

    def crop_and_save_latest_image(self) -> None:
        """按预览裁剪框裁剪最近一次截图并保存。"""
        if self._latest_image is None:
            self._log_info("没有可裁剪的截图")
            return
        crop_rect = self._crop_rect_from_inputs() or self.preview_label.crop_rect()
        if crop_rect is None:
            self._log_info("请先拖出有效裁剪框，或输入有效裁剪坐标")
            return
        cropped = self._latest_image.crop(crop_rect)
        path, _ = QFileDialog.getSaveFileName(self, "保存裁剪截图", "screenshot_crop.png", "PNG 图片 (*.png)")
        if not path:
            return
        cropped.save(path)
        self._log_info(f"裁剪截图已保存：{path}，裁剪区域={crop_rect}，分辨率={cropped.width}x{cropped.height}")

    def apply_crop_inputs_to_preview(self) -> None:
        """把输入的裁剪坐标应用到截图预览框。"""
        crop_rect = self._crop_rect_from_inputs()
        if crop_rect is None:
            self._log_info("裁剪坐标无效，请确认右大于左、下大于上，且没有超出图片范围")
            return
        self.preview_label.set_crop_rect(*crop_rect)
        self._log_info(f"已应用裁剪坐标：{crop_rect}")

    def read_preview_crop_to_inputs(self) -> None:
        """把预览裁剪框坐标写入坐标输入框。"""
        crop_rect = self.preview_label.crop_rect()
        if crop_rect is None:
            self._log_info("当前没有有效预览裁剪框")
            return
        left, top, right, bottom = crop_rect
        self.crop_left_spin.setValue(left)
        self.crop_top_spin.setValue(top)
        self.crop_right_spin.setValue(right)
        self.crop_bottom_spin.setValue(bottom)
        self._log_info(f"已读取预览裁剪框坐标：{crop_rect}")

    def close_bound_window(self) -> None:
        """二次确认后关闭绑定窗口。"""
        hwnd = self._require_bound_hwnd()
        if hwnd is None:
            return
        reply = QMessageBox.question(self, "确认关闭窗口", f"确定向 HWND={hwnd} 发送 WM_CLOSE 吗？")
        if reply == QMessageBox.StandardButton.Yes:
            self._run_operation(lambda: self.control_service.close_window(hwnd))

    def _bind_window(self, hwnd: int) -> None:
        """
        绑定指定 HWND。

        Args:
            hwnd (int): 窗口句柄。
        """
        try:
            info = self.window_service.get_window_info(hwnd)
            self.bound_hwnd = hwnd
            self.message_target_hwnd = hwnd
            self.bound_label.setText(f"当前绑定 HWND：{hwnd}")
            self._show_window_info(info)
            self._sync_window_combo_to_bound(info)
            self._log_info(f"已绑定窗口 HWND={hwnd}，并已自动作为后台消息目标，标题={info.title}")
        except (ValueError, RuntimeError, OSError) as exc:
            LOGGER.exception("绑定窗口失败")
            self._log_info(f"绑定窗口失败：{exc}")

    def _update_pick_candidate(self) -> None:
        """更新拾取模式下当前鼠标位置的候选窗口。"""
        pos: QPoint = QCursor.pos()
        try:
            info = self.window_service.window_from_point(pos.x(), pos.y())
            self.statusBar().showMessage(f"拾取候选 HWND={info.hwnd} 标题={info.title} 类名={info.class_name}")
        except (ValueError, RuntimeError, OSError) as exc:
            self.statusBar().showMessage(f"拾取失败：{exc}")

    def _update_bound_mouse_position(self) -> None:
        """更新鼠标在绑定窗口客户区内的相对坐标。"""
        if not hasattr(self, "mouse_position_label"):
            return
        if self.bound_hwnd is None:
            self._current_mouse_client_pos = None
            self._f8_was_down = False
            self.mouse_position_label.setText("鼠标相对坐标：未绑定窗口")
            return
        pos: QPoint = QCursor.pos()
        try:
            x, y = self.window_service.screen_to_client(self.bound_hwnd, pos.x(), pos.y())
            width, height = self.window_service.get_client_size(self.bound_hwnd)
            state = "窗口内" if 0 <= x < width and 0 <= y < height else "窗口外"
            self._current_mouse_client_pos = (x, y)
            self.mouse_position_label.setText(
                f"鼠标相对坐标：X={x}，Y={y}（{state}，客户区={width}x{height}，按 F8 固定）"
            )
            self._lock_mouse_position_when_f8_pressed()
        except (ValueError, RuntimeError, OSError) as exc:
            self._current_mouse_client_pos = None
            self.mouse_position_label.setText(f"鼠标相对坐标：读取失败，{exc}")

    def _lock_mouse_position_when_f8_pressed(self) -> None:
        """检测 F8 是否按下，按下时固定当前鼠标相对坐标。"""
        is_down = bool(win32api.GetAsyncKeyState(win32con.VK_F8) & 0x8000)
        if is_down and not self._f8_was_down:
            self.lock_current_mouse_position()
        self._f8_was_down = is_down

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        处理 Esc 取消拾取。

        Args:
            event (QKeyEvent): Qt 键盘事件。
        """
        if event.key() == Qt.Key.Key_Escape and self._is_picking:
            self._cancel_pick_mode()
            return
        super().keyPressEvent(event)

    def _foreground_click(self, double: bool = False) -> OperationResult:
        """
        执行前台点击。

        Args:
            double (bool): 是否双击。

        Returns:
            OperationResult: 操作结果。
        """
        hwnd = self._require_bound_hwnd()
        if hwnd is None:
            return OperationResult(False, "尚未绑定窗口")
        return self.input_service.foreground_click(hwnd, self.fg_x_spin.value(), self.fg_y_spin.value(), double)

    def _foreground_key(self) -> OperationResult:
        """
        执行前台按键。

        Returns:
            OperationResult: 操作结果。
        """
        hwnd = self._require_bound_hwnd()
        if hwnd is None:
            return OperationResult(False, "尚未绑定窗口")
        return self.input_service.foreground_key(hwnd, self.fg_vk_spin.value())

    def _foreground_type_text(self) -> OperationResult:
        """
        执行前台文本输入。

        Returns:
            OperationResult: 操作结果。
        """
        hwnd = self._require_bound_hwnd()
        if hwnd is None:
            return OperationResult(False, "尚未绑定窗口")
        return self.input_service.foreground_type_text(hwnd, self.fg_text_input.text())

    def _send_background_message(self) -> OperationResult:
        """
        发送后台消息。

        Returns:
            OperationResult: 操作结果。
        """
        return self._send_background_message_by_name(self.msg_name_combo.currentText())

    def _send_background_message_by_name(self, message_name: str) -> OperationResult:
        """
        发送指定后台消息。

        Args:
            message_name (str): 消息名称。

        Returns:
            OperationResult: 操作结果。
        """
        if self.message_target_hwnd is None:
            return OperationResult(False, "尚未设置后台消息目标")
        return self.input_service.send_background_message(
            hwnd=self.message_target_hwnd,
            message_name=message_name,
            x=self.msg_x_spin.value(),
            y=self.msg_y_spin.value(),
            vk_code=self.msg_vk_spin.value(),
            char=self.msg_char_input.text(),
            repeat=self.msg_repeat_spin.value(),
            interval=self.msg_interval_spin.value() / 1000,
        )

    def _quick_send_message(self, message_names: tuple[str, ...], action_label: str) -> None:
        """
        快速发送一个完整后台动作。

        Args:
            message_names (tuple[str, ...]): 消息序列。
            action_label (str): 动作名称。
        """
        if not message_names:
            self._log_info("没有可发送的后台动作")
            return
        self.msg_name_combo.setCurrentText(message_names[0])
        results = [self._send_background_message_by_name(message_name) for message_name in message_names]
        failed = next((result for result in results if not result.success), None)
        if failed is not None:
            self._log_info(f"失败：{action_label} 未完成，{failed.message}")
            return
        returns = [result.return_value for result in results if result.return_value is not None]
        detail = f"，返回值={returns[-1]}" if returns else ""
        self._log_info(f"成功：后台{action_label}已发送{detail}")

    def _show_window(self, command: WindowCommand) -> OperationResult:
        """
        执行窗口显示命令。

        Args:
            command (WindowCommand): 显示命令。

        Returns:
            OperationResult: 操作结果。
        """
        hwnd = self._require_bound_hwnd()
        if hwnd is None:
            return OperationResult(False, "尚未绑定窗口")
        return self.control_service.show_window(hwnd, command)

    def _bring_to_front(self) -> OperationResult:
        """
        置前绑定窗口。

        Returns:
            OperationResult: 操作结果。
        """
        hwnd = self._require_bound_hwnd()
        if hwnd is None:
            return OperationResult(False, "尚未绑定窗口")
        return self.control_service.bring_to_front(hwnd)

    def _set_focus(self) -> OperationResult:
        """
        设置绑定窗口焦点。

        Returns:
            OperationResult: 操作结果。
        """
        hwnd = self._require_bound_hwnd()
        if hwnd is None:
            return OperationResult(False, "尚未绑定窗口")
        return self.control_service.set_focus(hwnd)

    def _move_window(self) -> OperationResult:
        """
        移动或缩放绑定窗口。

        Returns:
            OperationResult: 操作结果。
        """
        hwnd = self._require_bound_hwnd()
        if hwnd is None:
            return OperationResult(False, "尚未绑定窗口")
        return self.control_service.move_window(
            hwnd,
            self.move_x_spin.value(),
            self.move_y_spin.value(),
            self.move_w_spin.value(),
            self.move_h_spin.value(),
        )

    def _set_topmost(self) -> OperationResult:
        """
        更新绑定窗口置顶状态。

        Returns:
            OperationResult: 操作结果。
        """
        hwnd = self._require_bound_hwnd()
        if hwnd is None:
            return OperationResult(False, "尚未绑定窗口")
        return self.control_service.set_topmost(hwnd, self.topmost_check.isChecked())

    def _run_operation(self, operation: Callable[[], OperationResult]) -> None:
        """
        运行一次用户触发的操作并写日志。

        Args:
            operation (Callable[[], OperationResult]): 操作函数。
        """
        result = operation()
        level = "成功" if result.success else "失败"
        detail = f"，返回值={result.return_value}" if result.return_value is not None else ""
        error = f"，LastError={result.last_error}" if result.last_error is not None else ""
        self._log_info(f"{level}：{result.message}{detail}{error}")

    def _handle_screenshot_result(self, result: ScreenshotResult) -> None:
        """
        处理截图结果。

        Args:
            result (ScreenshotResult): 截图结果。
        """
        self._log_info(result.message)
        if not result.success or result.image is None:
            return
        self._latest_image = result.image
        self.image_resolution_label.setText(f"图片分辨率：{result.image.width} x {result.image.height}")
        self._update_crop_input_limits(result.image.width, result.image.height)
        pixmap = self._image_to_pixmap(result.image)
        self.preview_label.set_preview_pixmap(pixmap, (result.image.width, result.image.height))

    def _load_child_windows(self, hwnd: int) -> None:
        """
        加载子窗口树。

        Args:
            hwnd (int): 父窗口句柄。
        """
        self.child_tree.clear()
        for child in self.window_service.enumerate_child_windows(hwnd):
            self.child_tree.addTopLevelItem(self._window_item(child))

    def _update_crop_input_limits(self, image_width: int, image_height: int) -> None:
        """
        更新裁剪坐标输入范围。

        Args:
            image_width (int): 图片宽度。
            image_height (int): 图片高度。
        """
        self.crop_left_spin.setRange(0, image_width)
        self.crop_right_spin.setRange(0, image_width)
        self.crop_top_spin.setRange(0, image_height)
        self.crop_bottom_spin.setRange(0, image_height)
        self.crop_left_spin.setValue(0)
        self.crop_top_spin.setValue(0)
        self.crop_right_spin.setValue(0)
        self.crop_bottom_spin.setValue(0)

    def _crop_rect_from_inputs(self) -> tuple[int, int, int, int] | None:
        """
        从坐标输入框读取有效裁剪区域。

        Returns:
            tuple[int, int, int, int] | None: 有效裁剪区域，无效时返回 None。
        """
        if self._latest_image is None:
            return None
        left = self.crop_left_spin.value()
        top = self.crop_top_spin.value()
        right = self.crop_right_spin.value()
        bottom = self.crop_bottom_spin.value()
        if right <= left or bottom <= top:
            return None
        if right > self._latest_image.width or bottom > self._latest_image.height:
            return None
        return left, top, right, bottom

    def _show_window_info(self, info: WindowInfo) -> None:
        """
        在界面显示窗口详情。

        Args:
            info (WindowInfo): 窗口信息。
        """
        lines = [
            f"HWND: {info.hwnd}",
            f"标题: {info.title}",
            f"类名: {info.class_name}",
            f"PID/TID: {info.pid}/{info.tid}",
            f"进程名: {info.process_name}",
            f"进程路径: {info.process_path}",
            f"窗口矩形: {info.rect.to_tuple()} 宽={info.rect.width} 高={info.rect.height}",
            f"客户区矩形: {info.client_rect.to_tuple()} 宽={info.client_rect.width} 高={info.client_rect.height}",
            f"父窗口: {info.parent_hwnd}",
            f"所有者窗口: {info.owner_hwnd}",
            f"可见/可用: {info.is_visible}/{info.is_enabled}",
        ]
        self.info_text.setPlainText("\n".join(lines))

    def _window_item(self, info: WindowInfo) -> QTreeWidgetItem:
        """
        创建窗口树节点。

        Args:
            info (WindowInfo): 窗口信息。

        Returns:
            QTreeWidgetItem: 树节点。
        """
        label = f"{info.hwnd} / {info.title or '<无标题>'}"
        item = QTreeWidgetItem([label, info.class_name, info.process_name])
        item.setData(0, Qt.ItemDataRole.UserRole, info.hwnd)
        return item

    def _require_bound_hwnd(self) -> int | None:
        """
        获取当前绑定 HWND。

        Returns:
            int | None: 已绑定 HWND，没有绑定时返回 None。
        """
        if self.bound_hwnd is None:
            self._log_info("尚未绑定窗口")
            return None
        return self.bound_hwnd

    def _attach_logger(self) -> None:
        """把应用日志接入界面日志框。"""
        handler = QtLogHandler(self._log_info)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logging.getLogger().addHandler(handler)

    def _log_info(self, message: str) -> None:
        """
        写入界面日志。

        Args:
            message (str): 日志文本。
        """
        if hasattr(self, "log_text"):
            self.log_text.append(message)
        self.statusBar().showMessage(message, 5000)

    def _group_box(self, title: str, widget: QWidget) -> QGroupBox:
        """
        用分组框包裹一个控件。

        Args:
            title (str): 分组标题。
            widget (QWidget): 要包裹的控件。

        Returns:
            QGroupBox: 分组框。
        """
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.addWidget(widget)
        return box

    def _scroll_page(self, widgets: list[QWidget]) -> QScrollArea:
        """
        创建标签页内的滚动页面。

        Args:
            widgets (list[QWidget]): 页面内按顺序显示的控件。

        Returns:
            QScrollArea: 滚动页面。
        """
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch(1)
        scroll.setWidget(content)
        return scroll

    def _message_button_text(self, message_name: str) -> str:
        """
        生成后台消息快捷按钮文本。

        Args:
            message_name (str): 消息名称。

        Returns:
            str: 中文按钮文本。
        """
        names = {
            "WM_MOUSEMOVE": "鼠标移动",
            "WM_LBUTTONDOWN": "左键按下",
            "WM_LBUTTONUP": "左键释放",
            "WM_RBUTTONDOWN": "右键按下",
            "WM_RBUTTONUP": "右键释放",
            "WM_KEYDOWN": "按键按下",
            "WM_KEYUP": "按键释放",
            "WM_CHAR": "发送字符",
        }
        return names.get(message_name, message_name)

    def _update_message_description(self, message_name: str) -> None:
        """
        更新后台消息中文说明。

        Args:
            message_name (str): 当前选择的消息名称。
        """
        if hasattr(self, "msg_description_label"):
            description = self.input_service.message_description(message_name)
            self.msg_description_label.setText(f"{message_name}：{description}")

    def _apply_modern_style(self) -> None:
        """应用现代化界面样式。"""
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f6f8fb;
                color: #172033;
                font-family: "Microsoft YaHei UI", "Segoe UI";
                font-size: 12px;
            }
            QToolBar {
                background: #ffffff;
                border: 0;
                border-bottom: 1px solid #d8dee9;
                spacing: 6px;
                padding: 5px;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d8dee9;
                border-radius: 8px;
                margin-top: 12px;
                padding: 8px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #344256;
            }
            QPushButton {
                background: #2563eb;
                color: #ffffff;
                border: 0;
                border-radius: 6px;
                padding: 4px 9px;
                min-height: 20px;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
            QPushButton:pressed {
                background: #1e40af;
            }
            QLineEdit, QSpinBox, QComboBox {
                background: #ffffff;
                border: 1px solid #c8d0dc;
                border-radius: 6px;
                padding: 3px 6px;
                min-height: 20px;
            }
            QTextEdit, QTreeWidget {
                background: #ffffff;
                border: 1px solid #d8dee9;
                border-radius: 8px;
                selection-background-color: #bfdbfe;
            }
            QHeaderView::section {
                background: #eef2f7;
                border: 0;
                border-right: 1px solid #d8dee9;
                padding: 6px;
                font-weight: 600;
            }
            QTabWidget::pane {
                border: 1px solid #d8dee9;
                border-radius: 8px;
                background: #ffffff;
            }
            QTabBar::tab {
                background: #e8edf5;
                color: #344256;
                padding: 6px 12px;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0f172a;
            }
            QLabel#hintLabel {
                background: #eef6ff;
                border: 1px solid #bfdbfe;
                border-radius: 8px;
                color: #1e3a8a;
                padding: 7px;
                font-weight: 400;
            }
            QLabel#boundLabel {
                color: #0f172a;
                font-weight: 600;
                padding-left: 8px;
            }
            QLabel#sectionTitle {
                color: #344256;
                font-weight: 600;
                padding-top: 4px;
            }
            QSplitter::handle {
                background: #d8dee9;
            }
            """
        )

    def _spin_box(self, minimum: int, maximum: int, value: int) -> QSpinBox:
        """
        创建整数输入框。

        Args:
            minimum (int): 最小值。
            maximum (int): 最大值。
            value (int): 默认值。

        Returns:
            QSpinBox: 整数输入框。
        """
        spin_box = QSpinBox()
        spin_box.setRange(minimum, maximum)
        spin_box.setValue(value)
        spin_box.setMaximumWidth(140)
        return spin_box

    def _form_label(self, text: str) -> QLabel:
        """
        创建表单网格中的右对齐标签。

        Args:
            text (str): 标签文本。

        Returns:
            QLabel: 右对齐的表单标签。
        """
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _image_to_pixmap(self, image: Image.Image) -> QPixmap:
        """
        将 Pillow 图像转换为 QPixmap。

        Args:
            image (Image.Image): Pillow 图像。

        Returns:
            QPixmap: Qt 位图。
        """
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        data = QByteArray(buffer.getvalue())
        q_buffer = QBuffer(data)
        q_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        q_image = QImage()
        q_image.load(q_buffer, "PNG")
        return QPixmap.fromImage(q_image)

from pathlib import Path

from PyQt6.QtCore import Qt, QSize, QTimer, QPropertyAnimation
from PyQt6.QtGui import QFont, QMovie, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

ASSETS_DIR = Path(__file__).parent / "assets"
DISPLAY_W, DISPLAY_H = 260, 280
_STATIC_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


class CatWindow(QWidget):
    def __init__(self, image_path: str = ""):
        super().__init__()
        self._image_path = image_path
        self._countdown = 20
        self._anim = None  # 防止 GC
        self._movie = None  # 防止 GC
        self._setup_window()
        self._setup_ui()
        self._start_countdown()

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(300, 360)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
        )

    def _setup_ui(self) -> None:
        # 关闭按钮行
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.25); border: none;"
            " color: white; font-size: 14px; border-radius: 14px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.45); }"
        )
        close_btn.clicked.connect(self.close)
        close_row.addWidget(close_btn)

        # 猫咪图片 / GIF
        gif_label = QLabel()
        gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gif_label.setFixedSize(DISPLAY_W, DISPLAY_H)

        custom = Path(self._image_path) if self._image_path else Path()
        if custom.exists() and custom.suffix.lower() in _STATIC_EXTS:
            px = QPixmap(str(custom)).scaled(
                DISPLAY_W, DISPLAY_H,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            gif_label.setPixmap(px)
        else:
            gif_path = (
                custom if custom.exists() and custom.suffix.lower() == ".gif"
                else ASSETS_DIR / "cat.gif"
            )
            self._movie = QMovie(str(gif_path))
            self._movie.setScaledSize(QSize(DISPLAY_W, DISPLAY_H))
            gif_label.setMovie(self._movie)
            self._movie.start()

        # 倒计时文字
        self._countdown_label = QLabel(self._countdown_text())
        self._countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_label.setFont(QFont("Microsoft YaHei", 13))
        self._countdown_label.setStyleSheet("color: white;")

        # 内容容器（圆角半透明黑底）
        inner = QWidget()
        inner_layout = QVBoxLayout()
        inner_layout.setContentsMargins(16, 12, 16, 20)
        inner_layout.setSpacing(8)
        inner_layout.addLayout(close_row)
        inner_layout.addWidget(gif_label)
        inner_layout.addWidget(self._countdown_label)
        inner.setLayout(inner_layout)
        inner.setStyleSheet(
            "background: rgba(0,0,0,0.78); border-radius: 20px;"
        )

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(inner)
        self.setLayout(outer)

    def _countdown_text(self) -> str:
        return f"看向 20 英尺外 · 还剩 {self._countdown} 秒"

    def _start_countdown(self) -> None:
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self) -> None:
        self._countdown -= 1
        self._countdown_label.setText(self._countdown_text())
        if self._countdown <= 0:
            self._timer.stop()
            self._fade_out()

    def closeEvent(self, event) -> None:
        self._timer.stop()
        super().closeEvent(event)

    def _fade_out(self) -> None:
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(500)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.close)
        self._anim.start()

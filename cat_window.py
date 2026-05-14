from pathlib import Path

from PyQt6.QtCore import (
    Qt, QSize, QTimer, QPropertyAnimation,
    QParallelAnimationGroup, QEasingCurve, QPoint,
)
from PyQt6.QtGui import QFont, QMovie, QPixmap, QPainter, QColor
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

ASSETS_DIR = Path(__file__).parent / "assets"
THUMB_SIZE  = 80
CARD_W      = 360
CARD_H      = 120
MARGIN_EDGE = 16
_STATIC_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


class _ProgressBar(QWidget):
    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self._total = total
        self._remaining = total
        self.setFixedHeight(4)

    def set_remaining(self, remaining: int) -> None:
        self._remaining = remaining
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 38))
        p.drawRoundedRect(self.rect(), 2, 2)
        ratio = self._remaining / self._total if self._total > 0 else 0
        fill_w = int(self.width() * ratio)
        if fill_w > 0:
            r = self.rect()
            r.setWidth(fill_w)
            p.setBrush(QColor(255, 255, 255, 178))
            p.drawRoundedRect(r, 2, 2)
        p.end()


class CatWindow(QWidget):
    def __init__(self, image_path: str = "", rest_duration: int = 20):
        super().__init__()
        self._image_path = image_path
        self._countdown = rest_duration
        self._anim = None
        self._movie = None
        self._entry_anim = None
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
        self.setFixedSize(CARD_W, CARD_H)
        screen = QApplication.primaryScreen().availableGeometry()
        self._target_x = screen.right() - CARD_W - MARGIN_EDGE
        self._target_y = screen.top() + MARGIN_EDGE
        self.move(self._target_x, screen.top() - CARD_H)
        self.setWindowOpacity(0.0)

    def _setup_ui(self) -> None:
        # ── 左侧：猫咪缩略图 ──────────────────────────────────
        gif_label = QLabel()
        gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gif_label.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        gif_label.setStyleSheet(
            "border-radius: 10px; background: rgba(255,255,255,0.05);"
        )

        custom = Path(self._image_path) if self._image_path else Path()
        if custom.exists() and custom.suffix.lower() in _STATIC_EXTS:
            px = QPixmap(str(custom)).scaled(
                THUMB_SIZE, THUMB_SIZE,
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
            self._movie.jumpToFrame(0)
            nat = self._movie.currentImage().size()
            if nat.isValid() and nat.width() > 0 and nat.height() > 0:
                scale = min(THUMB_SIZE / nat.width(), THUMB_SIZE / nat.height())
                scaled = QSize(int(nat.width() * scale), int(nat.height() * scale))
            else:
                scaled = QSize(THUMB_SIZE, THUMB_SIZE)
            self._movie.setScaledSize(scaled)
            gif_label.setMovie(self._movie)
            self._movie.start()

        # ── 右侧：三行内容 ────────────────────────────────────
        # 行 1：应用名 + 关闭按钮
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)

        app_label = QLabel("Purr Pause")
        app_label.setFont(QFont("Microsoft YaHei", 10))
        app_label.setStyleSheet("color: #8E8E93;")

        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.20); border: none;"
            " color: white; font-size: 12px; border-radius: 10px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.35); }"
        )
        close_btn.clicked.connect(self._fade_out)

        top_row.addWidget(app_label)
        top_row.addStretch()
        top_row.addWidget(close_btn)

        # 行 2：主文字
        msg_label = QLabel("看向 20 英尺外 · 休息一下")
        msg_label.setFont(QFont("Microsoft YaHei", 13))
        msg_label.setStyleSheet("color: white;")

        # 行 3：倒计时 + 进度条
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(8)

        self._time_label = QLabel(f"还剩 {self._countdown} 秒")
        self._time_label.setFont(QFont("Microsoft YaHei", 11))
        self._time_label.setStyleSheet("color: #8E8E93;")

        self._progress_bar = _ProgressBar(total=self._countdown)

        bottom_row.addWidget(self._time_label)
        bottom_row.addWidget(self._progress_bar, 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(6)
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.addLayout(top_row)
        right_col.addWidget(msg_label)
        right_col.addLayout(bottom_row)

        # ── 卡片容器 ──────────────────────────────────────────
        inner = QWidget()
        inner_layout = QHBoxLayout()
        inner_layout.setContentsMargins(12, 12, 12, 12)
        inner_layout.setSpacing(12)
        inner_layout.addWidget(gif_label)
        inner_layout.addLayout(right_col)
        inner.setLayout(inner_layout)
        inner.setStyleSheet(
            "background: rgba(28, 28, 30, 0.92); border-radius: 16px;"
        )

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(inner)
        self.setLayout(outer)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        start_pos = QPoint(self._target_x, screen.top() - CARD_H)
        end_pos   = QPoint(self._target_x, self._target_y)

        pos_anim = QPropertyAnimation(self, b"pos")
        pos_anim.setDuration(350)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(end_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        opacity_anim.setDuration(350)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)

        self._entry_anim = QParallelAnimationGroup()
        self._entry_anim.addAnimation(pos_anim)
        self._entry_anim.addAnimation(opacity_anim)
        self._entry_anim.start()

    def _start_countdown(self) -> None:
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self) -> None:
        self._countdown -= 1
        self._time_label.setText(f"还剩 {self._countdown} 秒")
        self._progress_bar.set_remaining(self._countdown)
        if self._countdown <= 0:
            self._timer.stop()
            self._fade_out()

    def closeEvent(self, event) -> None:
        self._timer.stop()
        if self._entry_anim is not None:
            self._entry_anim.stop()
        super().closeEvent(event)

    def _fade_out(self) -> None:
        if self._entry_anim is not None:
            self._entry_anim.stop()
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(500)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.close)
        self._anim.start()

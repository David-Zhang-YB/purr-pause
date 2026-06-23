from pathlib import Path

from paths import resource_path
from PyQt6.QtCore import (
    Qt, QSize, QTimer, QPropertyAnimation, pyqtProperty, pyqtSignal,
    QParallelAnimationGroup, QSequentialAnimationGroup,
    QEasingCurve, QPoint, QRectF,
)
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QFontDatabase, QLinearGradient,
    QMovie, QPainterPath, QPixmap, QPainter,
)
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

THUMB_SIZE    = 80
CARD_W        = 360
CARD_H        = 120
SHADOW_MARGIN = 20          # transparent border around card for shadow bleed
WIN_W         = CARD_W + 2 * SHADOW_MARGIN
WIN_H         = CARD_H + 2 * SHADOW_MARGIN
MARGIN_EDGE   = 16          # gap between card edge and screen edge
GLOW_MARGIN   = 12          # max glow spread (px); must be ≤ SHADOW_MARGIN
_STATIC_EXTS  = {".png", ".jpg", ".jpeg", ".webp"}

_CARD_FILL = QColor(0, 0, 0, 255)   # pure black — matches Mascot Cat Black.png background

_NOTO_FAMILY: str | None = None


def _make_circular_pixmap(px: QPixmap, size: int) -> QPixmap:
    """Clip pixmap to a circle."""
    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    p = QPainter(result)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0.0, 0.0, float(size), float(size))
    p.setClipPath(path)
    scaled = px.scaled(size, size,
                       Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                       Qt.TransformationMode.SmoothTransformation)
    p.drawPixmap(0, 0, scaled)
    p.end()
    return result



def _ensure_font() -> str:
    """Load Noto Sans SC variable font once; fall back to Microsoft YaHei."""
    global _NOTO_FAMILY
    if _NOTO_FAMILY is None:
        font_path = resource_path("assets/fonts/NotoSansSC[wght].ttf")
        if font_path.exists():
            fid = QFontDatabase.addApplicationFont(str(font_path))
            families = QFontDatabase.applicationFontFamilies(fid)
            if families:
                _NOTO_FAMILY = families[0]
        if _NOTO_FAMILY is None:
            _NOTO_FAMILY = "Microsoft YaHei"
    return _NOTO_FAMILY


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
        # Track
        p.setBrush(QColor(255, 255, 255, 38))
        p.drawRoundedRect(self.rect(), 2, 2)
        # Amber gradient fill
        ratio = self._remaining / self._total if self._total > 0 else 0
        fill_w = int(self.width() * ratio)
        if fill_w > 0:
            r = self.rect()
            r.setWidth(fill_w)
            grad = QLinearGradient(0, 0, fill_w, 0)
            grad.setColorAt(0.0, QColor(0xFF, 0x9F, 0x0A))  # #FF9F0A
            grad.setColorAt(1.0, QColor(0xFF, 0xCC, 0x02))  # #FFCC02
            p.setBrush(grad)
            p.drawRoundedRect(r, 2, 2)
        p.end()


class _GlowCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._glow: float = 0.4
        self._anim_group: QSequentialAnimationGroup | None = None
        self.setFixedSize(CARD_W + 2 * GLOW_MARGIN, CARD_H + 2 * GLOW_MARGIN)

    @pyqtProperty(float)
    def glow_intensity(self) -> float:
        return self._glow

    @glow_intensity.setter
    def glow_intensity(self, value: float) -> None:
        self._glow = value
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)

        card_r = QRectF(self.rect()).adjusted(
            GLOW_MARGIN, GLOW_MARGIN, -GLOW_MARGIN, -GLOW_MARGIN
        )

        # Outer glow layers (amber, alpha scales with glow_intensity)
        for spread, base_alpha in ((12, 40), (7, 65), (3, 90)):
            gr = card_r.adjusted(-spread, -spread, spread, spread)
            p.setBrush(QColor(0xFF, 0x9F, 0x0A, int(base_alpha * self._glow)))
            p.drawRoundedRect(gr, 16 + spread * 0.6, 16 + spread * 0.6)

        # Gradient border fill (amber → gold), leaves ~2px ring after fill is drawn on top
        grad = QLinearGradient(card_r.topLeft(), card_r.bottomRight())
        grad.setColorAt(0.0, QColor(0xFF, 0x9F, 0x0A))
        grad.setColorAt(1.0, QColor(0xFF, 0xCC, 0x02))
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(card_r, 16.0, 16.0)

        # Inner card fill covers border, leaving a ~2px gradient ring visible
        p.setBrush(_CARD_FILL)
        p.drawRoundedRect(card_r.adjusted(2, 2, -2, -2), 14.0, 14.0)

        p.end()

    def start_breathing(self) -> None:
        if self._anim_group is not None:
            self._anim_group.stop()
        fwd = QPropertyAnimation(self, b"glow_intensity")
        fwd.setDuration(1200)
        fwd.setStartValue(0.4)
        fwd.setEndValue(1.0)
        fwd.setEasingCurve(QEasingCurve.Type.InOutSine)

        bwd = QPropertyAnimation(self, b"glow_intensity")
        bwd.setDuration(1200)
        bwd.setStartValue(1.0)
        bwd.setEndValue(0.4)
        bwd.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._anim_group = QSequentialAnimationGroup(self)
        self._anim_group.addAnimation(fwd)
        self._anim_group.addAnimation(bwd)
        self._anim_group.setLoopCount(-1)
        self._anim_group.start()

    def stop_breathing(self) -> None:
        if self._anim_group is not None:
            self._anim_group.stop()


class CatWindow(QWidget):
    countdown_finished = pyqtSignal()

    def __init__(self, image_path: str = "", rest_duration: int = 20):
        super().__init__()
        self._image_path = image_path
        self._countdown = rest_duration
        self._anim = None
        self._movie = None
        self._entry_anim = None
        self._glow_card: _GlowCard | None = None
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
        # Delete the widget on close so rest cards don't pile up in memory; the
        # main window-tracking list relies on the destroyed signal to clean up.
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedSize(WIN_W, WIN_H)
        screen = QApplication.primaryScreen().availableGeometry()
        # card's visible right/top edges land at MARGIN_EDGE from screen edges
        self._target_x = screen.right() - CARD_W - MARGIN_EDGE - SHADOW_MARGIN
        self._target_y = screen.top() + MARGIN_EDGE - SHADOW_MARGIN
        self.move(self._target_x, screen.top() - WIN_H)
        self.setWindowOpacity(0.0)

    def _setup_ui(self) -> None:
        fam = _ensure_font()

        # ── 左侧：猫咪缩略图（圆形）──────────────────────────
        gif_label = QLabel()
        gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gif_label.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        gif_label.setStyleSheet(
            f"border-radius: {THUMB_SIZE // 2}px;"
            " background: #000000;"
        )

        _DEFAULT_STATIC = resource_path("assets/Mascot Cat Black.png")
        custom = Path(self._image_path) if self._image_path else Path()
        if custom.exists() and custom.suffix.lower() in _STATIC_EXTS:
            src = custom
        elif _DEFAULT_STATIC.exists():
            src = _DEFAULT_STATIC
        else:
            src = None

        if src is not None:
            gif_label.setPixmap(
                _make_circular_pixmap(QPixmap(str(src)), THUMB_SIZE)
            )
        else:
            gif_path = (
                custom if custom.exists() and custom.suffix.lower() == ".gif"
                else resource_path("assets/cat.gif")
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

        # ── 中列：垂直居中的倒计时 + 进度条 ──────────────────────
        f_count = QFont(fam, 26)
        f_count.setWeight(QFont.Weight.Medium)
        self._time_label = QLabel(self._fmt_countdown())
        self._time_label.setFont(f_count)
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._time_label.setStyleSheet("color: white;")

        self._progress_bar = _ProgressBar(total=self._countdown)

        center_col = QVBoxLayout()
        center_col.setSpacing(6)
        center_col.setContentsMargins(0, 0, 0, 0)
        center_col.addStretch(1)
        center_col.addWidget(self._time_label)
        center_col.addWidget(self._progress_bar)
        center_col.addStretch(1)

        # ── 右列：关闭按钮顶部对齐 ────────────────────────────────
        close_btn = QPushButton("×")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.20); border: none;"
            " color: white; font-size: 13px; border-radius: 11px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.35); }"
        )
        close_btn.clicked.connect(self._dismiss)

        close_col = QVBoxLayout()
        close_col.setContentsMargins(0, 0, 0, 0)
        close_col.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)
        close_col.addStretch()

        # ── 卡片容器（_GlowCard 包含发光边框 + 内填充） ─────────
        self._glow_card = _GlowCard()
        inner_layout = QHBoxLayout()
        inner_layout.setContentsMargins(
            GLOW_MARGIN + 12, GLOW_MARGIN + 12,
            GLOW_MARGIN + 12, GLOW_MARGIN + 12,
        )
        inner_layout.setSpacing(12)
        inner_layout.addWidget(gif_label)
        inner_layout.addLayout(center_col, 1)   # stretch=1: fills horizontal space
        inner_layout.addLayout(close_col)
        self._glow_card.setLayout(inner_layout)

        # ── 外层透明容器（为发光留白） ────────────────────────────
        outer = QVBoxLayout()
        outer.setContentsMargins(
            SHADOW_MARGIN - GLOW_MARGIN, SHADOW_MARGIN - GLOW_MARGIN,
            SHADOW_MARGIN - GLOW_MARGIN, SHADOW_MARGIN - GLOW_MARGIN,
        )
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._glow_card)
        self.setLayout(outer)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        start_pos = QPoint(self._target_x, screen.top() - WIN_H)
        end_pos   = QPoint(self._target_x, self._target_y)

        pos_anim = QPropertyAnimation(self, b"pos")
        pos_anim.setDuration(420)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(end_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutBack)  # spring bounce

        opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        opacity_anim.setDuration(280)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)

        self._entry_anim = QParallelAnimationGroup()
        self._entry_anim.addAnimation(pos_anim)
        self._entry_anim.addAnimation(opacity_anim)
        self._entry_anim.start()
        self._entry_anim.finished.connect(self._glow_card.start_breathing)

    def _fmt_countdown(self) -> str:
        m, s = divmod(self._countdown, 60)
        return f"{m:02d}:{s:02d}"

    def _start_countdown(self) -> None:
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self) -> None:
        self._countdown -= 1
        self._time_label.setText(self._fmt_countdown())
        self._progress_bar.set_remaining(self._countdown)
        if self._countdown <= 0:
            self.countdown_finished.emit()
            self._timer.stop()
            self._fade_out()

    def closeEvent(self, event) -> None:
        self._timer.stop()
        if self._entry_anim is not None:
            self._entry_anim.stop()
        if self._glow_card is not None:
            self._glow_card.stop_breathing()
        super().closeEvent(event)

    def _dismiss(self) -> None:
        self.countdown_finished.emit()
        self._fade_out()

    def _fade_out(self) -> None:
        if self._entry_anim is not None:
            self._entry_anim.stop()
        if self._glow_card is not None:
            self._glow_card.stop_breathing()
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(500)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.close)
        self._anim.start()

import numpy as np
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtMultimedia import QMediaPlayer, QVideoSink
from PyQt6.QtWidgets import QApplication, QWidget

# ── Chroma-key (pure-black background) ───────────────────────────────────────
CHROMA_COLOR = (0, 0, 0)
CHROMA_TOL   = 25

# ── Phase time-points (ms) ────────────────────────────────────────────────────
WALK_IN_END_MS    = 4_000   # cat finishes walking in and lies down
WALK_OUT_START_MS = 10_000  # cat gets up and starts leaving


class CatAnimWindow(QWidget):
    """Full-screen transparent overlay playing a single cat animation MP4.

    Phases
    ------
    WALK_IN  : 0 ms → WALK_IN_END_MS        (plays once)
    IDLE     : WALK_IN_END_MS → WALK_OUT_START_MS (loops until start_walk_out)
    WALK_OUT : WALK_OUT_START_MS → end       (plays once, then closes)
    """

    finished = pyqtSignal()

    def __init__(self, video_path: str, parent=None):
        super().__init__(parent)
        self._video_path            = video_path
        self._state: str            = "WALK_IN"
        self._current_image: QImage | None = None
        self._setup_window()
        self._create_player()
        self._player.setSource(QUrl.fromLocalFile(video_path))
        self._player.play()

    # ── window setup ──────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(QApplication.primaryScreen().geometry())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._make_click_through()

    def _make_click_through(self) -> None:
        import ctypes
        hwnd  = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)   # GWL_EXSTYLE
        ctypes.windll.user32.SetWindowLongW(
            hwnd, -20, style | 0x00000020 | 0x00080000            # WS_EX_TRANSPARENT | WS_EX_LAYERED
        )

    # ── video pipeline ────────────────────────────────────────────────────────

    def _create_player(self) -> None:
        self._sink        = QVideoSink(self)
        self._player      = QMediaPlayer(self)
        self._last_render = 0.0          # for 30 fps rate-limit
        self._player.setVideoSink(self._sink)
        # QueuedConnection ensures _on_frame runs in the GUI thread
        self._sink.videoFrameChanged.connect(
            self._on_frame, Qt.ConnectionType.QueuedConnection
        )
        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.positionChanged.connect(self._on_position)

    # ── phase transitions ─────────────────────────────────────────────────────

    def _on_position(self, pos_ms: int) -> None:
        if self._state == "WALK_IN" and pos_ms >= WALK_IN_END_MS:
            self._state = "IDLE"
        elif self._state == "IDLE" and pos_ms >= WALK_OUT_START_MS:
            self._player.setPosition(WALK_IN_END_MS)    # loop idle segment

    def _on_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self._state == "WALK_OUT":
            self.finished.emit()
            self.close()

    def start_walk_out(self) -> None:
        """Call when countdown finishes to trigger the exit animation."""
        if self._state == "WALK_OUT":
            return
        self._state = "WALK_OUT"
        self._player.setPosition(WALK_OUT_START_MS)

    # ── chroma-key frame processing ───────────────────────────────────────────

    def _on_frame(self, frame) -> None:
        import time
        now = time.monotonic()
        if now - self._last_render < 1 / 30:   # cap at 30 fps
            return
        self._last_render = now

        if not frame.isValid():
            return
        image = frame.toImage()
        if image.isNull():
            return
        image = image.convertToFormat(QImage.Format.Format_ARGB32)
        if image.isNull():
            return
        w, h = image.width(), image.height()
        if w == 0 or h == 0:
            return
        image = image.copy()   # force detach so bits() is always accessible
        bits = image.bits()
        if bits is None:
            return

        arr = np.frombuffer(bits.asarray(h * w * 4),
                            dtype=np.uint8).reshape(h, w, 4).copy()  # BGRA
        r, g, b = CHROMA_COLOR
        dist_sq = (
            (arr[:, :, 2].astype(np.int32) - r) ** 2
            + (arr[:, :, 1].astype(np.int32) - g) ** 2
            + (arr[:, :, 0].astype(np.int32) - b) ** 2
        )
        arr[dist_sq < CHROMA_TOL ** 2, 3] = 0
        self._current_image = QImage(
            arr.tobytes(), w, h, w * 4, QImage.Format.Format_ARGB32
        ).copy()
        self.update()

    # ── rendering ─────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        if self._current_image is None:
            return
        p = QPainter(self)
        p.drawImage(self.rect(), self._current_image)
        p.end()

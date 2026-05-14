from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtMultimedia import QMediaPlayer, QVideoSink
from PyQt6.QtWidgets import QApplication, QWidget

ANIM_STRIP_H = 300          # transparent strip height (px)
CHROMA_COLOR = (0, 255, 0)  # green-screen key colour (R, G, B)
CHROMA_TOL   = 40           # chroma-key Euclidean-distance tolerance


class CatAnimWindow(QWidget):
    """Full-width transparent strip that plays a 3-phase cat animation."""

    finished = pyqtSignal()

    def __init__(
        self,
        walk_in_path: str,
        idle_path: str,
        walk_out_path: str,
        parent=None,
    ):
        super().__init__(parent)
        self._walk_in_path  = walk_in_path
        self._idle_path     = idle_path
        self._walk_out_path = walk_out_path
        self._state: str               = "WALK_IN"
        self._current_image: QImage | None = None
        self._setup_window()
        self._create_player()
        self._play(walk_in_path)

    # ── window geometry ───────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        screen  = QApplication.primaryScreen().availableGeometry()
        strip_y = screen.top() + (screen.height() - ANIM_STRIP_H) // 2
        self.setGeometry(screen.left(), strip_y, screen.width(), ANIM_STRIP_H)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._make_click_through()

    def _make_click_through(self) -> None:
        import ctypes
        hwnd  = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
        ctypes.windll.user32.SetWindowLongW(
            hwnd, -20,
            style | 0x00000020 | 0x00080000,  # WS_EX_TRANSPARENT | WS_EX_LAYERED
        )

    # ── video pipeline ────────────────────────────────────────────────────

    def _create_player(self) -> None:
        self._sink   = QVideoSink(self)
        self._player = QMediaPlayer(self)
        self._player.setVideoSink(self._sink)
        self._sink.videoFrameChanged.connect(self._on_frame)
        self._player.mediaStatusChanged.connect(self._on_status)

    def _play(self, path: str) -> None:
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()

    # ── chroma-key frame processing ───────────────────────────────────────

    def _on_frame(self, frame) -> None:
        image = frame.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        w, h  = image.width(), image.height()
        raw   = image.bits().asarray(h * w * 4)
        arr   = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 4).copy()  # BGRA
        r, g, b = CHROMA_COLOR
        dist_sq = (
            (arr[:, :, 2].astype(np.int32) - r) ** 2
            + (arr[:, :, 1].astype(np.int32) - g) ** 2
            + (arr[:, :, 0].astype(np.int32) - b) ** 2
        )
        arr[dist_sq < CHROMA_TOL ** 2, 3] = 0
        self._current_image = QImage(
            arr.tobytes(), w, h, w * 4, QImage.Format.Format_ARGB32
        )
        self.update()

    # ── state machine ─────────────────────────────────────────────────────

    def _on_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status != QMediaPlayer.MediaStatus.EndOfMedia:
            return
        if self._state == "WALK_IN":
            self._state = "IDLE"
            self._player.setLoops(QMediaPlayer.Loops.Infinite)
            self._play(self._idle_path)
        elif self._state == "WALK_OUT":
            self.finished.emit()
            self.close()

    def start_walk_out(self) -> None:
        """Triggered by CatWindow.countdown_finished to begin exit animation."""
        if self._state == "WALK_OUT":
            return
        self._state = "WALK_OUT"
        self._player.setLoops(1)
        self._play(self._walk_out_path)

    # ── rendering ─────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        if self._current_image is None:
            return
        p = QPainter(self)
        p.drawImage(0, 0, self._current_image)
        p.end()

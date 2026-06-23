"""Frame-driven sprite overlay for the rest-break cat.

Owns a pure CatAnimModel (frame selection) and renders it. The whole clip plays
once, stretched to fill the rest duration, so the cat enters when the rest begins
and has walked off by the time it ends. A PreciseTimer drives repaints off a
monotonic QElapsedTimer; the frame to show is derived from elapsed time, so
playback never drifts. Because playback is strictly forward, frames are scaled to
the screen lazily — only the current frame is held scaled — instead of caching the
whole sequence at full-screen size. When the rest ends (or the card is dismissed)
the window fades to transparent and emits ``finished``.
"""
import json
import sys
from pathlib import Path

from PyQt6.QtCore import (
    QElapsedTimer, QPropertyAnimation, QRect, Qt, QTimer, pyqtSignal,
)
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget

from cat_anim_model import CatAnimModel

FADE_MS = 500
FRAME_INTERVAL_MS = 16  # ~60 Hz repaint cadence; frame shown is time-derived


class CatAnimWindow(QWidget):
    finished = pyqtSignal()

    def __init__(self, sprite_dir: Path, rest_duration_seconds: float = 20, parent=None):
        super().__init__(parent)
        # Delete the widget (and its pixmaps) on close, so each rest cycle's
        # overlay is reclaimed instead of accumulating in memory.
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._ok = False
        self._timer = None
        self._fade = None
        self._cur = None            # (scaled_pixmap, x, y) for the frame on screen
        self._cur_index = -1
        self._cur_size = None
        self._raw = None            # raw cropped pixmap for self._raw_index (lazy-loaded)
        self._raw_index = -1
        if not self._load_frames(sprite_dir):
            QTimer.singleShot(0, self._emit_finished_and_close)
            return
        self._ok = True
        duration_ms = max(1.0, float(rest_duration_seconds) * 1000.0)
        self._model = CatAnimModel([f[2] for f in self._frames], duration_ms)
        self._elapsed = QElapsedTimer()
        self._setup_window()

    # ---- loading -------------------------------------------------------

    def _load_frames(self, sprite_dir: Path) -> bool:
        """Parse the manifest and record per-frame (x, y, t) + file paths. Frames
        are loaded from disk one at a time during playback (see _load_raw), so the
        whole high-resolution sequence never sits in memory at once."""
        manifest_path = sprite_dir / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self._canvas_w, self._canvas_h = manifest["canvas"]
            self._frames = []   # list of (canvas_x, canvas_y, t)
            self._paths = []    # parallel list of frame PNG paths
            for i, f in enumerate(manifest["frames"], start=1):
                self._frames.append((int(f["x"]), int(f["y"]), float(f["t"])))
                self._paths.append(sprite_dir / f"frame_{i:03d}.png")
            if not self._frames:
                return False
            # Validate the first frame is actually readable (catches a broken or
            # half-written export early, so the fallback can fire).
            probe = QPixmap(str(self._paths[0]))
            if probe.isNull():
                raise OSError(f"failed to load {self._paths[0]}")
        except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            print(f"cat_anim: failed to load sprites from {sprite_dir}: {exc}", file=sys.stderr)
            return False
        return True

    # ---- window setup --------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        screen = QApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.geometry())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._ok:
            return
        self._make_click_through()
        self._refresh_current(0)  # scale the first frame for the initial paint
        if self._timer is None:
            self._elapsed.start()
            self._timer = QTimer(self)
            self._timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._timer.timeout.connect(self._on_frame)
            self._timer.start(FRAME_INTERVAL_MS)

    def _make_click_through(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, -20, style | 0x00000020 | 0x00080000
            )
        except Exception as exc:
            print(f"cat_anim: click-through setup failed: {exc}", file=sys.stderr)

    # ---- lazy per-frame load + scaling ---------------------------------

    def _load_raw(self, index: int) -> QPixmap:
        """Return the raw cropped pixmap for ``index``, loading it from disk if it
        is not the one already held. Only one raw frame is kept in memory."""
        if index != self._raw_index or self._raw is None:
            self._raw = QPixmap(str(self._paths[index]))
            self._raw_index = index
        return self._raw

    def _refresh_current(self, index: int) -> None:
        """Load frame ``index``, scale it to the screen, and cache just that one."""
        sw, sh = self.width(), self.height()
        if sw == 0 or sh == 0 or not self._ok:
            return
        cx, cy, _t = self._frames[index]
        pix = self._load_raw(index)
        scale = min(sw / self._canvas_w, sh / self._canvas_h)
        off_x = (sw - self._canvas_w * scale) / 2
        off_y = (sh - self._canvas_h * scale) / 2
        tw = max(1, round(pix.width() * scale))
        th = max(1, round(pix.height() * scale))
        scaled = pix.scaled(
            tw, th,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._cur = (scaled, round(off_x + cx * scale), round(off_y + cy * scale))
        self._cur_index = index
        self._cur_size = (sw, sh)

    def _cur_rect(self) -> QRect:
        if self._cur is None:
            return QRect()
        pixmap, x, y = self._cur
        return QRect(x, y, pixmap.width(), pixmap.height())

    # ---- public API ----------------------------------------------------

    def request_finish(self) -> None:
        """End the overlay now (rest countdown finished or card dismissed)."""
        if not self._ok or self._fade is not None:
            return
        if self._timer is not None:
            self._timer.stop()
        self._start_fade()

    # ---- frame loop ----------------------------------------------------

    def _on_frame(self) -> None:
        prev_rect = self._cur_rect()
        self._model.update(self._elapsed.elapsed())
        index = self._model.index
        if index != self._cur_index or (self.width(), self.height()) != self._cur_size:
            self._refresh_current(index)
            # Repaint only the union of the old and new cat rects. The window is
            # WA_TranslucentBackground, so the old position clears to transparent
            # on partial repaint. If the frame is held (still stretch), nothing
            # repaints — keeping idle CPU near zero.
            dirty = self._cur_rect()
            if not prev_rect.isNull():
                dirty = dirty.united(prev_rect)
            self.update(dirty)
        if self._model.done and self._fade is None:
            self._timer.stop()
            self._start_fade()

    def paintEvent(self, event) -> None:
        if self._cur is None:
            return
        pixmap, x, y = self._cur
        p = QPainter(self)
        p.drawPixmap(x, y, pixmap)
        p.end()

    # ---- closing fade --------------------------------------------------

    def _start_fade(self) -> None:
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(FADE_MS)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self._emit_finished_and_close)
        self._fade.start()

    def _emit_finished_and_close(self) -> None:
        self.finished.emit()
        self.close()

    def closeEvent(self, event) -> None:
        if self._timer is not None:
            self._timer.stop()
        super().closeEvent(event)

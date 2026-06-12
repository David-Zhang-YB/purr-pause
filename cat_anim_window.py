"""Frame-driven sprite overlay for the rest-break cat walk.

Owns a pure CatAnimModel (state + frame selection) and renders it. A PreciseTimer
drives repaints off a monotonic QElapsedTimer; frames are pre-scaled to the
screen once and cached; only the cat's dirty rectangle is repainted. On exit the
model finishes the idle at the upright pose, walks the cat out, then the window
fades to transparent and emits ``finished``.
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

    def __init__(self, sprite_dir: Path, parent=None):
        super().__init__(parent)
        self._ok = False
        self._timer = None
        self._fade = None
        self._cache = {}
        self._cache_size = None
        if not self._load_frames(sprite_dir):
            QTimer.singleShot(0, self._emit_finished_and_close)
            return
        self._ok = True
        self._model = CatAnimModel(
            len(self._walk_in), len(self._idle), len(self._walk_out),
            self._walk_fps, self._idle_fps,
        )
        self._elapsed = QElapsedTimer()
        self._setup_window()

    # ---- loading -------------------------------------------------------

    def _load_frames(self, sprite_dir: Path) -> bool:
        manifest_path = sprite_dir / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self._canvas_w, self._canvas_h = manifest["canvas"]
            self._walk_fps = int(manifest["walk_fps"])
            self._idle_fps = int(manifest["idle_fps"])
            self._walk_in = self._load_phase(sprite_dir, "walk_in", manifest["walk_in"])
            self._idle = self._load_phase(sprite_dir, "idle", manifest["idle"])
            self._walk_out = self._load_phase(sprite_dir, "walk_out", manifest["walk_out"])
        except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
            print(f"cat_anim: failed to load sprites from {sprite_dir}: {exc}", file=sys.stderr)
            return False
        return bool(self._walk_in and self._idle and self._walk_out)

    def _load_phase(self, sprite_dir: Path, name: str, placements: list) -> list:
        out = []
        for i, p in enumerate(placements, start=1):
            path = sprite_dir / f"{name}_{i:02d}.png"
            pix = QPixmap(str(path))
            if pix.isNull():
                raise OSError(f"failed to load {path}")
            out.append((pix, int(p["x"]), int(p["y"])))
        return out

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
        self._build_scaled_cache()
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

    # ---- pre-scaled frame cache (C2) -----------------------------------

    def _build_scaled_cache(self) -> None:
        sw, sh = self.width(), self.height()
        if sw == 0 or sh == 0:
            return
        scale = min(sw / self._canvas_w, sh / self._canvas_h)
        off_x = (sw - self._canvas_w * scale) / 2
        off_y = (sh - self._canvas_h * scale) / 2

        def scale_phase(frames):
            out = []
            for pix, cx, cy in frames:
                tw = max(1, round(pix.width() * scale))
                th = max(1, round(pix.height() * scale))
                sp = pix.scaled(
                    tw, th,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                out.append((sp, round(off_x + cx * scale), round(off_y + cy * scale)))
            return out

        self._cache = {
            "WALK_IN": scale_phase(self._walk_in),
            "IDLE": scale_phase(self._idle),
            "WALK_OUT": scale_phase(self._walk_out),
        }
        self._cache_size = (sw, sh)

    # ---- public API ----------------------------------------------------

    def start_walk_out(self) -> None:
        if self._ok:
            self._model.request_exit()

    # ---- frame loop ----------------------------------------------------

    def _on_frame(self) -> None:
        if (self.width(), self.height()) != self._cache_size:
            self._build_scaled_cache()
        prev = self._current_entry()
        self._model.update(self._elapsed.elapsed())
        cur = self._current_entry()
        if cur is not prev:
            self.update()  # full-window repaint; Task 4 narrows this to the dirty rect
        if self._model.done and self._fade is None:
            self._timer.stop()
            self._start_fade()

    def _current_entry(self):
        phase = self._model.phase
        if phase == "FINISHED":
            # model holds the last walk_out index when FINISHED, so the clamp
            # below shows the final exit frame during the closing fade.
            phase = "WALK_OUT"
        frames = self._cache.get(phase)
        if not frames:
            return None
        return frames[min(self._model.index, len(frames) - 1)]

    def paintEvent(self, event) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        pixmap, x, y = entry
        p = QPainter(self)
        p.drawPixmap(x, y, pixmap)
        p.end()

    # ---- closing fade (B4) ---------------------------------------------

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

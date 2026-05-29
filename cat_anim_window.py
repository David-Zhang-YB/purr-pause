"""Frame-driven sprite animation overlay for the rest-break cat walk.

Plays a one-shot WALK_IN entrance, loops IDLE while the rest timer counts down,
then plays a one-shot WALK_OUT and emits ``finished``. Each phase is a sequence
of PNG sprites cropped to per-frame bounding boxes; their canvas-space (x, y)
positions live in ``manifest.json`` produced by ``scripts/extract_cat_frames.py``.

This replaces an earlier MP4 + numpy chroma-key pipeline that crashed randomly
and produced black edge artifacts.
"""
import json
import sys
from pathlib import Path

from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget


class CatAnimWindow(QWidget):
    finished = pyqtSignal()

    def __init__(self, sprite_dir: Path, parent=None):
        super().__init__(parent)
        self._timer: QTimer | None = None
        if not self._load_frames(sprite_dir):
            QTimer.singleShot(0, self._emit_finished_and_close)
            return
        self._setup_window()
        self._state = "WALK_IN"
        self._idx = 0
        self._walk_out_pending = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(int(1000 / self._walk_fps))

    def start_walk_out(self) -> None:
        """Trigger the exit animation; safe to call from any state."""
        if self._state == "WALK_IN":
            self._walk_out_pending = True
        elif self._state == "IDLE":
            self._transition_to_walk_out()

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

    def _load_phase(self, sprite_dir: Path, name: str, placements: list[dict]) -> list[tuple[QPixmap, int, int]]:
        out = []
        for i, p in enumerate(placements, start=1):
            path = sprite_dir / f"{name}_{i:02d}.png"
            pix = QPixmap(str(path))
            if pix.isNull():
                raise OSError(f"failed to load {path}")
            out.append((pix, int(p["x"]), int(p["y"])))
        return out

    def _emit_finished_and_close(self) -> None:
        self.finished.emit()
        self.close()

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
        self._make_click_through()

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

    def _on_tick(self) -> None:
        if self._state == "WALK_IN":
            self._idx += 1
            if self._idx >= len(self._walk_in):
                if self._walk_out_pending:
                    self._transition_to_walk_out()
                else:
                    self._transition_to_idle()
        elif self._state == "IDLE":
            self._idx = (self._idx + 1) % len(self._idle)
        elif self._state == "WALK_OUT":
            self._idx += 1
            if self._idx >= len(self._walk_out):
                self._state = "FINISHED"
                if self._timer is not None:
                    self._timer.stop()
                self._emit_finished_and_close()
                return
        self.update()

    def _transition_to_idle(self) -> None:
        self._state = "IDLE"
        self._idx = 0
        if self._timer is not None:
            self._timer.start(int(1000 / self._idle_fps))

    def _transition_to_walk_out(self) -> None:
        self._state = "WALK_OUT"
        self._idx = 0
        if self._timer is not None:
            self._timer.start(int(1000 / self._walk_fps))

    def _current_frame(self):
        if self._state == "WALK_IN":
            return self._walk_in[min(self._idx, len(self._walk_in) - 1)]
        if self._state == "IDLE":
            return self._idle[self._idx]
        if self._state == "WALK_OUT":
            return self._walk_out[min(self._idx, len(self._walk_out) - 1)]
        return None

    def paintEvent(self, event) -> None:
        frame = self._current_frame()
        if frame is None:
            return
        pixmap, cx, cy = frame

        screen_w = self.width()
        screen_h = self.height()
        scale = min(screen_w / self._canvas_w, screen_h / self._canvas_h)
        offset_x = (screen_w - self._canvas_w * scale) / 2
        offset_y = (screen_h - self._canvas_h * scale) / 2

        target = QRectF(
            offset_x + cx * scale,
            offset_y + cy * scale,
            pixmap.width() * scale,
            pixmap.height() * scale,
        )
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
        p.end()

    def closeEvent(self, event) -> None:
        if self._timer is not None:
            self._timer.stop()
        super().closeEvent(event)

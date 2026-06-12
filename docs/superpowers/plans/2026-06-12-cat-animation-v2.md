# Cat Animation v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-source the rest-break cat overlay from a clean 4K/60fps video and rebuild its playback so the idle loops seamlessly (ping-pong), the cat exits from the correct pose at any rest duration, and motion is drift-free and jank-free.

**Architecture:** Split the overlay into a pure, Qt-free frame-selection model (`cat_anim_model.py`) and a thin Qt rendering shell (`cat_anim_window.py`). The model picks the frame to show purely from elapsed milliseconds (no per-tick drift), realizes the idle as a ping-pong triangle wave, and on exit finishes the idle at the upright pose before walking out. The shell drives the model with a `PreciseTimer` off a monotonic `QElapsedTimer`, paints from a pre-scaled frame cache, and only repaints the cat's dirty rectangle.

**Tech Stack:** Python 3, PyQt6, Pillow + OpenCV (dev-only extract script), pytest + pytest-qt.

**Design spec:** [docs/superpowers/specs/2026-06-12-cat-animation-v2-design.md](../specs/2026-06-12-cat-animation-v2-design.md)

---

## Background an implementer needs

- The rest overlay today is `cat_anim_window.py`: a `QWidget` that loads PNG sprite phases (`walk_in`, `idle`, `walk_out`) listed in `assets/cat_anim/manifest.json`, and a `QTimer` advances `self._idx` once per tick (`_on_tick`). `main.py` wires `window.countdown_finished.connect(cat_anim.start_walk_out)` so the cat exits when the rest-card countdown ends. The rest-card countdown lasts `rest_duration_seconds` (default 20, range 10–60).
- The sprites are produced offline by `scripts/extract_cat_frames.py`, which crops each video frame to its opaque bounding box and records the `(x, y)` canvas offset in `manifest.json`. The runtime scales the canvas to fill the screen.
- "Ping-pong" means play the idle frames forward then backward then forward (`0,1,…,n-1,n-2,…,1,0,1,…`). Because both turning points repeat an existing frame, the loop never jumps — unlike `(idx+1) % n`, which jumps from the last frame back to the first.
- "Time-based selection" means: instead of `idx += 1` every tick (which drifts when the timer fires irregularly), compute `idx` from how many milliseconds have elapsed since the phase began. Late or early ticks self-correct.
- The new source video `assets/British Shorthair Silver Shaded Transparent.mp4` is **already present and git-ignored** (`assets/*.mp4`). It is 60fps / 902 frames / 15.033s / 3840×2160. Visually verified motion arc: head enters from left (~0s) → walks in → lies down crouched (~6.1s) → sits up upright (~10.5s) → gets up and exits right (~15s).
- Dev-only dependency `opencv-python-headless` is installed in the `D:/Python` interpreter. Run the extract script with `D:/Python/python.exe scripts/extract_cat_frames.py`.

---

## Task 1: Re-extract sprites from the new 4K source (Part A)

**Files:**
- Modify: `scripts/extract_cat_frames.py` (constants at lines 35, 38–40, 42–43, 53)
- Regenerate: `assets/cat_anim/manifest.json` + `assets/cat_anim/*.png`

This is a one-shot asset-generation script, not unit-tested code. The "test" is running it and verifying the manifest and frame outputs.

- [ ] **Step 1: Point the script at the new source and retune phase windows / fps / scale**

In `scripts/extract_cat_frames.py`, change these constants:

```python
SRC = ROOT / "assets" / "British Shorthair Silver Shaded Transparent.mp4"
```

```python
WALK_IN = (0.0, 6.1)
IDLE = (6.1, 10.5)
WALK_OUT = (10.5, 15.0)
```

```python
WALK_FPS = 30
IDLE_FPS = 15
```

```python
SCALE = 0.25
```

(Leave `ALPHA_CUTOFF`, `ALPHA_OPAQUE`, `BBOX_ALPHA_THRESHOLD`, `WALK_DEDUP_MSE`, `IDLE_DEDUP_MSE` unchanged.)

- [ ] **Step 2: Run the extract script**

Run: `D:/Python/python.exe scripts/extract_cat_frames.py`

Expected: prints `source: British Shorthair Silver Shaded Transparent.mp4 (3840x2160)`, `scale: 0.25, canvas: 960x540`, `walk fps: 30, idle fps: 15`, three `extracting …` lines each reporting a non-zero frame count, and a final `total size: …MB` under ~13 MB.

- [ ] **Step 3: Verify the manifest matches the new parameters**

Run:
```bash
D:/Python/python.exe -c "import json; m=json.load(open('assets/cat_anim/manifest.json')); assert m['canvas']==[960,540], m['canvas']; assert m['walk_fps']==30; assert m['idle_fps']==15; assert m['walk_in_count']>10 and m['idle_count']>5 and m['walk_out_count']>10, (m['walk_in_count'],m['idle_count'],m['walk_out_count']); print('OK', m['walk_in_count'], m['idle_count'], m['walk_out_count'])"
```

Expected: `OK <wi> <id> <wo>` with all three counts in plausible ranges (walk_in/walk_out roughly 100–140, idle roughly 30–70 after dedup). No `AssertionError`.

- [ ] **Step 4: Visually spot-check the phase boundary frames**

Read these four generated PNGs and confirm the poses (boundaries are the agreed starting values; if a boundary is clearly wrong, nudge the `WALK_IN`/`IDLE`/`WALK_OUT` seconds by ≤0.3s and re-run Steps 2–4):
- The **last** `walk_in_NN.png` — cat should be **crouched / lying** (settled), not mid-stride.
- The **first** `idle_01.png` — cat **crouched / lying** (matches last walk_in).
- The **last** `idle_NN.png` — cat **sitting upright / head raised**.
- The **first** `walk_out_01.png` — cat **upright, starting to rise** (matches last idle).

Use the Read tool on each file path (e.g. `assets/cat_anim/idle_01.png`). To find NN, list the directory first.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_cat_frames.py assets/cat_anim
git commit -m "feat(anim): re-extract sprites from 4K source at 30fps walk / 15fps idle"
```

---

## Task 2: Pure frame-selection model (Part B logic + C1 time-based)

**Files:**
- Create: `cat_anim_model.py`
- Test: `tests/test_cat_anim_model.py`

The model is pure Python (no PyQt import). All timing is passed in as `now_ms` arguments, so tests are deterministic and need no clock or qtbot.

### Interface (build incrementally over the steps below)

```python
class CatAnimModel:
    def __init__(self, n_walk_in, n_idle, n_walk_out, walk_fps, idle_fps): ...
    def request_exit(self) -> None: ...
    def update(self, now_ms: float) -> None: ...
    # public read state: self.phase ("WALK_IN"|"IDLE"|"WALK_OUT"|"FINISHED"),
    #                     self.index (int), self.done (bool)
```

- [ ] **Step 1: Write the failing test for construction + walk-in time-based advance**

Create `tests/test_cat_anim_model.py`:

```python
from cat_anim_model import CatAnimModel


def make(n_wi=3, n_idle=4, n_wo=3, walk_fps=10, idle_fps=10):
    # walk_dt = idle_dt = 100ms at fps=10
    return CatAnimModel(n_wi, n_idle, n_wo, walk_fps, idle_fps)


def test_starts_in_walk_in_at_frame_zero():
    m = make()
    assert m.phase == "WALK_IN"
    assert m.index == 0
    assert m.done is False


def test_walk_in_advances_by_elapsed_time():
    m = make()
    m.update(0);   assert (m.phase, m.index) == ("WALK_IN", 0)
    m.update(150); assert (m.phase, m.index) == ("WALK_IN", 1)
    m.update(250); assert (m.phase, m.index) == ("WALK_IN", 2)


def test_walk_in_enters_idle_at_boundary():
    m = make()  # 3 walk_in frames * 100ms = 300ms boundary
    m.update(290); assert m.phase == "WALK_IN"
    m.update(300); assert m.phase == "IDLE"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_cat_anim_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cat_anim_model'`.

- [ ] **Step 3: Implement construction + walk-in + idle entry**

Create `cat_anim_model.py`:

```python
"""Pure, Qt-free frame-selection model for the rest-break cat animation.

Drives WALK_IN (one-shot) -> IDLE (ping-pong) -> WALK_OUT (one-shot) -> done,
choosing the frame to show purely from elapsed milliseconds so playback never
drifts and is decoupled from repaint cadence. Exit is requested asynchronously
(when the rest countdown ends); the model finishes the idle motion at the
upright pose before walking the cat out, so phase seams never jump.
"""


class CatAnimModel:
    def __init__(self, n_walk_in, n_idle, n_walk_out, walk_fps, idle_fps):
        self.n_walk_in = n_walk_in
        self.n_idle = n_idle
        self.n_walk_out = n_walk_out
        self._walk_dt = 1000.0 / walk_fps
        self._idle_dt = 1000.0 / idle_fps

        self.phase = "WALK_IN"
        self.index = 0
        self.done = False

        self._phase_start_ms = 0.0
        self._exit_requested = False
        self._ramp_from = None
        self._ramp_start_ms = 0.0

    def request_exit(self):
        self._exit_requested = True

    def update(self, now_ms):
        if self.phase == "WALK_IN":
            self._update_walk_in(now_ms)
        elif self.phase == "IDLE":
            self._update_idle(now_ms)
        elif self.phase == "WALK_OUT":
            self._update_walk_out(now_ms)
        # FINISHED: no-op

    def _update_walk_in(self, now_ms):
        frame = int((now_ms - self._phase_start_ms) / self._walk_dt)
        if frame >= self.n_walk_in:
            self._enter_idle(self._phase_start_ms + self.n_walk_in * self._walk_dt)
            self._update_idle(now_ms)
            return
        self.index = frame

    def _enter_idle(self, start_ms):
        self.phase = "IDLE"
        self._phase_start_ms = start_ms
        self.index = 0
        if self._exit_requested:
            self._ramp_from = 0
            self._ramp_start_ms = start_ms
        else:
            self._ramp_from = None

    def _update_idle(self, now_ms):
        if self._exit_requested:
            if self._ramp_from is None:
                self._ramp_from = self._pingpong_index(now_ms)
                self._ramp_start_ms = now_ms
            ramp_frames = int((now_ms - self._ramp_start_ms) / self._idle_dt)
            idx = self._ramp_from + ramp_frames
            if idx >= self.n_idle - 1:
                self.index = self.n_idle - 1
                self._enter_walk_out(now_ms)
                return
            self.index = idx
        else:
            self.index = self._pingpong_index(now_ms)

    def _pingpong_index(self, now_ms):
        if self.n_idle <= 1:
            return 0
        frames = int((now_ms - self._phase_start_ms) / self._idle_dt)
        period = 2 * (self.n_idle - 1)
        pos = frames % period
        return pos if pos < self.n_idle else period - pos

    def _enter_walk_out(self, start_ms):
        self.phase = "WALK_OUT"
        self._phase_start_ms = start_ms
        self.index = 0

    def _update_walk_out(self, now_ms):
        frame = int((now_ms - self._phase_start_ms) / self._walk_dt)
        if frame >= self.n_walk_out:
            self.index = self.n_walk_out - 1
            self.phase = "FINISHED"
            self.done = True
            return
        self.index = frame
```

- [ ] **Step 4: Run to verify the three tests pass**

Run: `python -m pytest tests/test_cat_anim_model.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Write the failing test for idle ping-pong**

Append to `tests/test_cat_anim_model.py`:

```python
def test_idle_pingpongs_without_jumping():
    m = make(n_idle=4, idle_fps=10)  # period = 2*(4-1) = 6
    m.phase = "IDLE"
    m._phase_start_ms = 0.0
    seq = [(m.update(t), m.index)[1] for t in (0, 100, 200, 300, 400, 500, 600, 700)]
    assert seq == [0, 1, 2, 3, 2, 1, 0, 1]
```

- [ ] **Step 6: Run to verify it passes (logic already implemented)**

Run: `python -m pytest tests/test_cat_anim_model.py::test_idle_pingpongs_without_jumping -v`
Expected: PASS. (The ping-pong logic from Step 3 already satisfies this; if it fails, fix `_pingpong_index`.)

- [ ] **Step 7: Write the failing test for the exit handshake (idle → upright → walk_out)**

Append:

```python
def test_exit_during_idle_ramps_to_upright_then_walk_out():
    m = make(n_idle=4, idle_fps=10)  # idle_dt = 100ms, upright index = 3
    m.phase = "IDLE"
    m._phase_start_ms = 0.0
    m.update(100)                 # ping-pong index 1
    assert m.phase == "IDLE"
    m.request_exit()
    m.update(150)                 # capture ramp_from at current ping-pong index
    assert m.phase == "IDLE"
    captured = m.index
    m.update(150 + 100); assert m.index == captured + 1   # ramps upward
    # keep updating until it reaches the upright end and flips to WALK_OUT
    t = 150 + 100
    while m.phase == "IDLE" and t < 2000:
        t += 100
        m.update(t)
    assert m.phase == "WALK_OUT"
    assert m.index == 0


def test_exit_during_walk_in_sweeps_idle_once_then_walk_out():
    m = make(n_wi=2, n_idle=4, n_wo=2, walk_fps=10, idle_fps=10)
    m.update(0)
    m.request_exit()
    m.update(50);  assert m.phase == "WALK_IN"
    t = 200            # walk_in boundary (2 * 100ms)
    while m.phase != "WALK_OUT" and t < 2000:
        m.update(t)
        t += 100
    assert m.phase == "WALK_OUT"
```

- [ ] **Step 8: Run to verify the handshake tests pass**

Run: `python -m pytest tests/test_cat_anim_model.py -v`
Expected: PASS (all). (Logic from Step 3 already covers it; fix `_update_idle` / `_enter_idle` if not.)

- [ ] **Step 9: Write the failing test for walk-out completion**

Append:

```python
def test_walk_out_completes_and_sets_done():
    m = make(n_wo=2, walk_fps=10)   # walk_dt = 100ms, 2 frames -> 200ms boundary
    m.phase = "WALK_OUT"
    m._phase_start_ms = 0.0
    m.update(50);  assert (m.phase, m.index, m.done) == ("WALK_OUT", 0, False)
    m.update(150); assert (m.phase, m.index) == ("WALK_OUT", 1)
    m.update(250); assert (m.phase, m.done) == ("FINISHED", True)


def test_single_idle_frame_is_stable():
    m = make(n_idle=1, idle_fps=10)
    m.phase = "IDLE"
    m._phase_start_ms = 0.0
    for t in (0, 100, 500):
        m.update(t)
        assert m.index == 0
    m.request_exit()
    m.update(600)
    assert m.phase == "WALK_OUT"   # ramp from 0 to upright(0) completes immediately
```

- [ ] **Step 10: Run the full model test suite**

Run: `python -m pytest tests/test_cat_anim_model.py -v`
Expected: PASS (all model tests).

- [ ] **Step 11: Commit**

```bash
git add cat_anim_model.py tests/test_cat_anim_model.py
git commit -m "feat(anim): pure time-based frame model with ping-pong idle and exit handshake"
```

---

## Task 3: Rewrite the widget shell — model + PreciseTimer + pre-scaled cache + fade (Part B wiring + C1 + C2 + B4)

**Files:**
- Modify (rewrite): `cat_anim_window.py`
- Test (rewrite): `tests/test_cat_anim_window.py`

The widget keeps its public surface used by `main.py`: constructor `CatAnimWindow(sprite_dir)`, signal `finished`, method `start_walk_out()`, and `.show()`. `start_walk_out()` now just forwards to `model.request_exit()` — transparent to the caller.

- [ ] **Step 1: Rewrite the widget test file to target the new shell**

Replace the entire contents of `tests/test_cat_anim_window.py`:

```python
"""Tests for the CatAnimWindow Qt shell.

Frame-selection logic lives in cat_anim_model.py (tested separately). These
tests cover wiring, the sprite-loading fallback, exit delegation, the
pre-scaled cache, and the closing fade.
"""
import json
from pathlib import Path

import pytest
from PIL import Image

from cat_anim_window import CatAnimWindow


@pytest.fixture
def sprite_dir(tmp_path: Path) -> Path:
    for name in ("walk_in_01", "walk_in_02",
                 "idle_01", "idle_02", "idle_03",
                 "walk_out_01", "walk_out_02"):
        Image.new("RGBA", (4, 4), (200, 150, 100, 255)).save(tmp_path / f"{name}.png")
    manifest = {
        "canvas": [100, 50],
        "walk_fps": 24,
        "idle_fps": 12,
        "walk_in": [{"x": 0, "y": 10}, {"x": 5, "y": 10}],
        "idle": [{"x": 10, "y": 10}, {"x": 12, "y": 10}, {"x": 14, "y": 10}],
        "walk_out": [{"x": 50, "y": 10}, {"x": 80, "y": 10}],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def test_instantiates_and_builds_model(qtbot, sprite_dir):
    w = CatAnimWindow(sprite_dir)
    qtbot.addWidget(w)
    assert w._model.phase == "WALK_IN"
    assert w._model.n_walk_in == 2
    assert w._model.n_idle == 3
    assert w._model.n_walk_out == 2


def test_missing_manifest_emits_finished_immediately(qtbot, tmp_path):
    w = CatAnimWindow(tmp_path / "does_not_exist")
    qtbot.addWidget(w)
    with qtbot.waitSignal(w.finished, timeout=500):
        pass


def test_malformed_manifest_emits_finished_immediately(qtbot, tmp_path):
    (tmp_path / "manifest.json").write_text("{ not json", encoding="utf-8")
    w = CatAnimWindow(tmp_path)
    qtbot.addWidget(w)
    with qtbot.waitSignal(w.finished, timeout=500):
        pass


def test_start_walk_out_requests_model_exit(qtbot, sprite_dir):
    w = CatAnimWindow(sprite_dir)
    qtbot.addWidget(w)
    assert w._model._exit_requested is False
    w.start_walk_out()
    assert w._model._exit_requested is True


def test_build_scaled_cache_covers_all_phases(qtbot, sprite_dir):
    from PyQt6.QtGui import QPixmap
    w = CatAnimWindow(sprite_dir)
    qtbot.addWidget(w)
    w.resize(200, 100)
    w._build_scaled_cache()
    assert set(w._cache) == {"WALK_IN", "IDLE", "WALK_OUT"}
    assert len(w._cache["IDLE"]) == 3
    pix, x, y = w._cache["IDLE"][0]
    assert isinstance(pix, QPixmap)
    assert isinstance(x, int) and isinstance(y, int)


def test_fade_emits_finished(qtbot, sprite_dir):
    w = CatAnimWindow(sprite_dir)
    qtbot.addWidget(w)
    with qtbot.waitSignal(w.finished, timeout=2000):
        w._start_fade()
```

- [ ] **Step 2: Run to verify the new tests fail against the old widget**

Run: `python -m pytest tests/test_cat_anim_window.py -v`
Expected: FAIL (old widget has no `_model`, `_build_scaled_cache`, or `_start_fade`).

- [ ] **Step 3: Rewrite `cat_anim_window.py`**

Replace the entire contents of `cat_anim_window.py`:

```python
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
        self._prev_entry = None
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
        if self._model.done:
            self._timer.stop()
            self._start_fade()

    def _current_entry(self):
        phase = self._model.phase
        if phase == "FINISHED":
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
```

- [ ] **Step 4: Run the widget tests**

Run: `python -m pytest tests/test_cat_anim_window.py -v`
Expected: PASS (all 6 tests).

- [ ] **Step 5: Run the full suite to catch regressions**

Run: `python -m pytest -q`
Expected: PASS (all existing tests still green; `test_cat_anim_model.py` + `test_cat_anim_window.py` included).

- [ ] **Step 6: Commit**

```bash
git add cat_anim_window.py tests/test_cat_anim_window.py
git commit -m "feat(anim): drive overlay from model with precise timer, pre-scaled cache, closing fade"
```

---

## Task 4: Dirty-rectangle repaint (Part C3)

**Files:**
- Modify: `cat_anim_window.py` (`_on_frame`, add `_entry_rect`)
- Test: `tests/test_cat_anim_window.py` (add `_entry_rect` test)

Currently `_on_frame` calls `self.update()` (full screen). Narrow it to the union of the previous and current frame rectangles so the translucent fullscreen window isn't recomposited in full every frame.

- [ ] **Step 1: Write the failing test for the rect helper**

Append to `tests/test_cat_anim_window.py`:

```python
def test_entry_rect_matches_pixmap_geometry(qtbot, sprite_dir):
    from PyQt6.QtCore import QRect
    w = CatAnimWindow(sprite_dir)
    qtbot.addWidget(w)
    w.resize(200, 100)
    w._build_scaled_cache()
    entry = w._cache["IDLE"][0]
    pix, x, y = entry
    assert w._entry_rect(entry) == QRect(x, y, pix.width(), pix.height())
    assert w._entry_rect(None).isNull()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_cat_anim_window.py::test_entry_rect_matches_pixmap_geometry -v`
Expected: FAIL with `AttributeError: 'CatAnimWindow' object has no attribute '_entry_rect'`.

- [ ] **Step 3: Add `_entry_rect` and narrow the repaint**

In `cat_anim_window.py`, add this method (e.g. just after `_current_entry`):

```python
    def _entry_rect(self, entry) -> QRect:
        if entry is None:
            return QRect()
        pixmap, x, y = entry
        return QRect(x, y, pixmap.width(), pixmap.height())
```

Then replace the repaint line in `_on_frame` — change:

```python
        if cur is not prev:
            self.update()  # full-window repaint; Task 4 narrows this to the dirty rect
```

to:

```python
        if cur is not prev:
            dirty = self._entry_rect(cur)
            prev_rect = self._entry_rect(prev)
            if not prev_rect.isNull():
                dirty = dirty.united(prev_rect)
            self.update(dirty)
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_cat_anim_window.py -v`
Expected: PASS (all, including the new rect test).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add cat_anim_window.py tests/test_cat_anim_window.py
git commit -m "perf(anim): repaint only the cat's dirty rectangle each frame"
```

---

## Task 5: Manual smoke verification (Windows)

**Files:** none (manual run of the real app).

This is the human-in-the-loop visual QA the unit tests can't cover. If the implementer is an agent, surface these steps to the user to run.

- [ ] **Step 1: Run with a fast interval and default rest duration**

Edit the user config to fire quickly. The config lives at `%APPDATA%\PurrPause\config.json`. Set `"interval_minutes": 0.1` and `"rest_duration_seconds": 20`. Then run `python main.py`. Wait ~6 seconds for the overlay.

- [ ] **Step 2: Confirm the visual checklist**

Watch one full cycle and confirm:
- Entrance: cat walks in with no frozen/stuck frames, horizontal motion is smooth (no visible "stair-stepping").
- Idle: the crouch↔sit ping-pong has **no jump** at the loop turn — it reads as the cat gently shifting.
- Exit: the cat rises from the **upright** pose (no snap from crouch) and walks out to the right.
- Closing: the overlay fades out softly instead of vanishing instantly.
- Overall: no stutter / no "一顿一顿".

- [ ] **Step 3: Confirm elastic duration**

Set `"rest_duration_seconds": 40`, run again. Confirm the cat does **not** exit early — it keeps ping-ponging in idle and only rises/exits when the rest-card countdown ends (~40s).

- [ ] **Step 4: Confirm CPU is reasonable**

With Task Manager open during the overlay, confirm CPU use during the animation is modest (the pre-scaled cache + dirty-rect repaint should keep it well below a full-screen-rescale baseline). Record the rough figure.

- [ ] **Step 5: Restore config**

Restore `interval_minutes` and `rest_duration_seconds` to their normal values (e.g. 20 and 20).

---

## Self-review notes (for the implementer)

- The model is the single source of truth for `(phase, index)`. The widget never mutates them — it only calls `update()` / `request_exit()` and reads. Keep it that way.
- `start_walk_out` is the unchanged public method `main.py` connects to `countdown_finished`; do not rename it.
- Phase strings are exactly `"WALK_IN"`, `"IDLE"`, `"WALK_OUT"`, `"FINISHED"` everywhere (model and widget cache keys). The widget maps `FINISHED → WALK_OUT` only for picking which cached frame to paint during the fade.
- Boundaries in Task 1 (6.1 / 10.5 / 15.0 s) are the agreed starting values; Task 1 Step 4 is the calibration gate. Everything downstream is independent of the exact counts.
- Out of scope (do not add): multi-monitor support, changes to `cat_window.py`, the `tray.py` `v1.0` about-box string, frame interpolation.

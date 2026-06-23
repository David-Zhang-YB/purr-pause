"""Tests for the CatAnimWindow Qt shell.

Frame-selection logic lives in cat_anim_model.py (tested separately). These
tests cover wiring, the sprite-loading fallback, lazy per-frame scaling, the
finish/dismiss path, and the closing fade.
"""
import json
from pathlib import Path

import pytest
from PIL import Image

from cat_anim_window import CatAnimWindow


@pytest.fixture
def sprite_dir(tmp_path: Path) -> Path:
    n = 5
    for i in range(1, n + 1):
        Image.new("RGBA", (4, 4), (200, 150, 100, 255)).save(tmp_path / f"frame_{i:03d}.png")
    manifest = {
        "canvas": [100, 50],
        "source_fps": 30,
        "arc_seconds": 5.0,
        "frame_count": n,
        "frames": [{"x": i * 5, "y": 10, "t": i / (n - 1)} for i in range(n)],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def test_instantiates_and_builds_model(qtbot, sprite_dir):
    w = CatAnimWindow(sprite_dir, rest_duration_seconds=20)
    qtbot.addWidget(w)
    assert w._ok is True
    assert len(w._frames) == 5
    assert w._model.index == 0
    assert w._model.done is False


def test_rest_duration_sets_model_duration(qtbot, sprite_dir):
    w = CatAnimWindow(sprite_dir, rest_duration_seconds=30)
    qtbot.addWidget(w)
    assert w._model._duration_ms == 30_000


def test_missing_manifest_emits_finished_immediately(qtbot, tmp_path):
    # No addWidget: WA_DeleteOnClose self-deletes on the immediate close.
    w = CatAnimWindow(tmp_path / "does_not_exist")
    with qtbot.waitSignal(w.finished, timeout=500):
        pass


def test_malformed_manifest_emits_finished_immediately(qtbot, tmp_path):
    (tmp_path / "manifest.json").write_text("{ not json", encoding="utf-8")
    w = CatAnimWindow(tmp_path)
    with qtbot.waitSignal(w.finished, timeout=500):
        pass


def test_refresh_current_scales_a_frame(qtbot, sprite_dir):
    from PyQt6.QtGui import QPixmap
    w = CatAnimWindow(sprite_dir, rest_duration_seconds=20)
    qtbot.addWidget(w)
    w.resize(200, 100)
    w._refresh_current(2)
    assert w._cur_index == 2
    assert w._cur_size == (200, 100)
    pix, x, y = w._cur
    assert isinstance(pix, QPixmap)
    assert isinstance(x, int) and isinstance(y, int)


def test_cur_rect_matches_scaled_pixmap(qtbot, sprite_dir):
    from PyQt6.QtCore import QRect
    w = CatAnimWindow(sprite_dir, rest_duration_seconds=20)
    qtbot.addWidget(w)
    w.resize(200, 100)
    w._refresh_current(0)
    pix, x, y = w._cur
    assert w._cur_rect() == QRect(x, y, pix.width(), pix.height())


def test_on_frame_advances_index_with_elapsed(qtbot, sprite_dir):
    w = CatAnimWindow(sprite_dir, rest_duration_seconds=20)
    qtbot.addWidget(w)
    w.resize(200, 100)
    w._refresh_current(0)
    w._cur_size = (200, 100)
    w._elapsed.start()
    # Force the model far enough along that the index advances past 0.
    w._model.update(10_000)            # progress 0.5 -> frame at t=0.5 (index 2)
    expected = w._model.index
    assert expected > 0
    w._refresh_current(expected)
    assert w._cur_index == expected


def test_request_finish_starts_fade_and_emits(qtbot, sprite_dir):
    # No addWidget: request_finish -> fade -> close self-deletes the widget.
    w = CatAnimWindow(sprite_dir, rest_duration_seconds=20)
    w.show()
    with qtbot.waitSignal(w.finished, timeout=2000):
        w.request_finish()


def test_fade_emits_finished(qtbot, sprite_dir):
    w = CatAnimWindow(sprite_dir, rest_duration_seconds=20)
    with qtbot.waitSignal(w.finished, timeout=2000):
        w._start_fade()


def test_window_deleted_after_close(qtbot, sprite_dir):
    """Closing must delete the widget (not just hide it), or its pixmaps leak."""
    from PyQt6 import sip

    w = CatAnimWindow(sprite_dir, rest_duration_seconds=20)
    w.close()
    qtbot.waitUntil(lambda: sip.isdeleted(w), timeout=1000)

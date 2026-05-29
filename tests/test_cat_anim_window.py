"""Tests for the PNG-sprite CatAnimWindow.

The old version of this file misnamedly tested CatWindow (the notification
card) instead of CatAnimWindow. Those signal tests live in test_cat_window.py.
This file now genuinely covers CatAnimWindow's state machine.
"""
import json
from pathlib import Path

import pytest
from PIL import Image

from cat_anim_window import CatAnimWindow


@pytest.fixture
def sprite_dir(tmp_path: Path) -> Path:
    """Minimal scaffold: 2 frames per phase, each a 4×4 RGBA PNG."""
    for name in ("walk_in_01", "walk_in_02",
                 "idle_01", "idle_02",
                 "walk_out_01", "walk_out_02"):
        Image.new("RGBA", (4, 4), (200, 150, 100, 255)).save(tmp_path / f"{name}.png")
    manifest = {
        "canvas": [100, 50],
        "walk_fps": 24,
        "idle_fps": 12,
        "walk_in": [{"x": 0, "y": 10}, {"x": 5, "y": 10}],
        "idle": [{"x": 10, "y": 10}, {"x": 12, "y": 10}],
        "walk_out": [{"x": 50, "y": 10}, {"x": 80, "y": 10}],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def test_instantiates_with_valid_sprites(qtbot, sprite_dir):
    w = CatAnimWindow(sprite_dir)
    qtbot.addWidget(w)
    assert w._state == "WALK_IN"
    assert w._idx == 0
    assert len(w._walk_in) == 2
    assert len(w._idle) == 2
    assert len(w._walk_out) == 2


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


def test_walk_in_advances_then_transitions_to_idle(qtbot, sprite_dir):
    w = CatAnimWindow(sprite_dir)
    qtbot.addWidget(w)
    assert w._state == "WALK_IN" and w._idx == 0
    w._on_tick()
    assert w._state == "WALK_IN" and w._idx == 1
    w._on_tick()
    assert w._state == "IDLE" and w._idx == 0


def test_idle_loops(qtbot, sprite_dir):
    w = CatAnimWindow(sprite_dir)
    qtbot.addWidget(w)
    w._state = "IDLE"
    w._idx = 0
    w._on_tick()
    assert w._idx == 1
    w._on_tick()
    assert w._idx == 0   # wraps


def test_start_walk_out_during_idle_transitions_immediately(qtbot, sprite_dir):
    w = CatAnimWindow(sprite_dir)
    qtbot.addWidget(w)
    w._state = "IDLE"
    w._idx = 1
    w.start_walk_out()
    assert w._state == "WALK_OUT" and w._idx == 0


def test_start_walk_out_during_walk_in_queues_until_done(qtbot, sprite_dir):
    w = CatAnimWindow(sprite_dir)
    qtbot.addWidget(w)
    assert w._state == "WALK_IN"
    w.start_walk_out()
    assert w._state == "WALK_IN"
    assert w._walk_out_pending is True
    w._on_tick()
    assert w._state == "WALK_IN"
    w._on_tick()
    assert w._state == "WALK_OUT" and w._idx == 0


def test_walk_out_completion_emits_finished(qtbot, sprite_dir):
    w = CatAnimWindow(sprite_dir)
    qtbot.addWidget(w)
    w._state = "WALK_OUT"
    w._idx = 0
    with qtbot.waitSignal(w.finished, timeout=500):
        w._on_tick()
        w._on_tick()
    assert w._state == "FINISHED"


def test_start_walk_out_during_walk_out_is_noop(qtbot, sprite_dir):
    w = CatAnimWindow(sprite_dir)
    qtbot.addWidget(w)
    w._state = "WALK_OUT"
    w._idx = 1
    w.start_walk_out()
    assert w._state == "WALK_OUT" and w._idx == 1

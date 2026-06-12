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

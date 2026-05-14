import pytest
from cat_window import CatWindow


def test_cat_window_has_countdown_finished_signal(qtbot):
    w = CatWindow(rest_duration=5)
    qtbot.addWidget(w)
    assert hasattr(w, "countdown_finished")


def test_cat_window_emits_countdown_finished(qtbot):
    w = CatWindow(rest_duration=1)
    qtbot.addWidget(w)
    w.show()
    with qtbot.waitSignal(w.countdown_finished, timeout=3000):
        pass

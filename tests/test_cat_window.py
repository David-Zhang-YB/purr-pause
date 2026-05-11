import pytest
from cat_window import CatWindow


def test_cat_window_can_be_instantiated(qtbot):
    window = CatWindow()
    qtbot.addWidget(window)
    # 不抛异常即通过


def test_cat_window_countdown_starts_at_20(qtbot):
    window = CatWindow()
    qtbot.addWidget(window)

    assert window._countdown == 20


def test_cat_window_tick_decrements_countdown(qtbot):
    window = CatWindow()
    qtbot.addWidget(window)
    window._tick()

    assert window._countdown == 19


def test_cat_window_closes_after_countdown_zero(qtbot):
    window = CatWindow()
    qtbot.addWidget(window)
    window.show()
    window._countdown = 1
    window._tick()  # 归零，触发淡出

    # 动画 500ms 后关闭，等待最多 1000ms
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=1000)


def test_cat_window_with_empty_path_uses_default(qtbot):
    window = CatWindow(image_path="")
    qtbot.addWidget(window)


def test_cat_window_with_nonexistent_path_falls_back(qtbot):
    window = CatWindow(image_path="/nonexistent/path/cat.gif")
    qtbot.addWidget(window)


def test_cat_window_countdown_starts_at_custom_duration(qtbot):
    window = CatWindow(rest_duration=15)
    qtbot.addWidget(window)

    assert window._countdown == 15

import pytest
from timer import RestTimer
from tray import TrayIcon


def test_tray_can_be_instantiated(qtbot):
    timer = RestTimer(interval_minutes=20)
    tray = TrayIcon(timer)
    assert tray is not None
    tray.hide()


def test_tray_toggle_pause_sets_paused(qtbot):
    timer = RestTimer(interval_minutes=20)
    timer._interval_ms = 60000
    timer.start()
    tray = TrayIcon(timer)

    tray._toggle_pause()
    assert timer.is_paused
    tray.hide()


def test_tray_toggle_pause_twice_resumes(qtbot):
    timer = RestTimer(interval_minutes=20)
    timer._interval_ms = 60000
    timer.start()
    tray = TrayIcon(timer)

    tray._toggle_pause()
    tray._toggle_pause()
    assert not timer.is_paused
    tray.hide()

import pytest
from timer import RestTimer


def test_rest_timer_emits_signal(qtbot):
    timer = RestTimer(interval_minutes=20)
    timer._interval_ms = 50  # 缩短为 50ms 加速测试

    with qtbot.waitSignal(timer.rest_due, timeout=500):
        timer.start()


def test_timer_is_not_paused_initially():
    timer = RestTimer(interval_minutes=20)
    assert not timer.is_paused


def test_timer_pause_sets_paused_flag(qtbot):
    timer = RestTimer(interval_minutes=20)
    timer._interval_ms = 100
    timer.start()
    timer.pause()

    assert timer.is_paused


def test_timer_resume_clears_paused_flag(qtbot):
    timer = RestTimer(interval_minutes=20)
    timer._interval_ms = 100
    timer.start()
    timer.pause()
    timer.resume()

    assert not timer.is_paused


def test_timer_reset_updates_interval():
    timer = RestTimer(interval_minutes=20)
    timer.reset(10)

    assert timer._interval_ms == 10 * 60 * 1000


def test_timer_pause_prevents_signal(qtbot):
    timer = RestTimer(interval_minutes=20)
    timer._interval_ms = 80
    timer.start()
    timer.pause()

    with qtbot.assertNotEmitted(timer.rest_due, wait=200):
        pass

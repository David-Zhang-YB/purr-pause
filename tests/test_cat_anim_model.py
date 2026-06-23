import pytest

from cat_anim_model import CatAnimModel


def make(frame_times=None, duration_ms=1000):
    if frame_times is None:
        frame_times = [0.0, 0.25, 0.5, 0.75]
    return CatAnimModel(frame_times, duration_ms)


def test_starts_at_frame_zero():
    m = make()
    assert m.index == 0
    assert m.done is False


def test_progress_zero_holds_first_frame():
    m = make()
    m.update(0)
    assert m.index == 0
    assert m.done is False


def test_picks_frame_by_progress():
    m = make([0.0, 0.25, 0.5, 0.75], duration_ms=1000)
    m.update(100);  assert m.index == 0    # progress 0.10 -> t=0.0
    m.update(300);  assert m.index == 1    # progress 0.30 -> t=0.25
    m.update(600);  assert m.index == 2    # progress 0.60 -> t=0.5
    m.update(800);  assert m.index == 3    # progress 0.80 -> t=0.75


def test_reaches_last_frame_and_done_at_duration():
    m = make([0.0, 0.5], duration_ms=1000)
    m.update(999);  assert (m.index, m.done) == (1, False)
    m.update(1000); assert (m.index, m.done) == (1, True)


def test_overshoot_past_duration_stays_done_on_last_frame():
    m = make([0.0, 0.3, 1.0], duration_ms=1000)
    m.update(5000)
    assert m.index == len(m._frame_times) - 1
    assert m.done is True


def test_holds_last_frame_through_a_still_gap():
    # A long motionless stretch: only two frames span 0.1 -> 0.9 of the clip.
    m = make([0.0, 0.1, 0.9, 1.0], duration_ms=1000)
    m.update(100);  assert m.index == 1    # progress 0.1 -> t=0.1
    m.update(500);  assert m.index == 1    # progress 0.5 still holds t=0.1
    m.update(890);  assert m.index == 1    # progress 0.89 still holds t=0.1
    m.update(900);  assert m.index == 2    # progress 0.9 -> t=0.9


def test_longer_duration_stretches_same_sequence():
    # Same frames, 4x duration: progress advances 4x slower.
    m = make([0.0, 0.5], duration_ms=4000)
    m.update(1000); assert m.index == 0    # progress 0.25 -> t=0.0
    m.update(2000); assert m.index == 1    # progress 0.50 -> t=0.5
    m.update(4000); assert m.done is True


def test_single_frame_is_stable_then_done():
    m = make([0.0], duration_ms=1000)
    m.update(0);    assert (m.index, m.done) == (0, False)
    m.update(500);  assert (m.index, m.done) == (0, False)
    m.update(1000); assert (m.index, m.done) == (0, True)


def test_rejects_empty_frames():
    with pytest.raises(ValueError):
        CatAnimModel([], 1000)


def test_rejects_nonpositive_duration():
    with pytest.raises(ValueError):
        CatAnimModel([0.0, 0.5], 0)
    with pytest.raises(ValueError):
        CatAnimModel([0.0, 0.5], -100)

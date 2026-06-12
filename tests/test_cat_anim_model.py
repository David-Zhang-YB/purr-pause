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


def test_idle_pingpongs_without_jumping():
    m = make(n_idle=4, idle_fps=10)  # period = 2*(4-1) = 6
    m.phase = "IDLE"
    m._phase_start_ms = 0.0
    seq = [(m.update(t), m.index)[1] for t in (0, 100, 200, 300, 400, 500, 600, 700)]
    assert seq == [0, 1, 2, 3, 2, 1, 0, 1]


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

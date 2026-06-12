"""Pure, Qt-free frame-selection model for the rest-break cat animation.

Drives WALK_IN (one-shot) -> IDLE (ping-pong) -> WALK_OUT (one-shot) -> done,
choosing the frame to show purely from elapsed milliseconds so playback never
drifts and is decoupled from repaint cadence. Exit is requested asynchronously
(when the rest countdown ends); the model finishes the idle motion at the
upright pose before walking the cat out, so phase seams never jump.
"""


class CatAnimModel:
    def __init__(self, n_walk_in, n_idle, n_walk_out, walk_fps, idle_fps):
        if n_walk_in < 1 or n_idle < 1 or n_walk_out < 1:
            raise ValueError("each phase needs at least one frame")
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
        # n-1 (not n): the two endpoints are shared between the forward and
        # backward passes, so the loop never repeats a frame at the turnaround.
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

"""Pure, Qt-free frame-selection model for the rest-break cat animation.

The whole source clip — enter, rest (with head turns), rise, exit — is one frame
sequence played exactly once, stretched to fill the rest duration. There is no
loop, so there are no seams. Each frame carries a normalized time position in
[0, 1]; given the elapsed milliseconds and the target duration, the model shows
the frame whose position matches the current progress. Frame choice is purely a
function of elapsed time, so playback never drifts and is decoupled from the
repaint cadence.
"""
from bisect import bisect_right


class CatAnimModel:
    def __init__(self, frame_times, duration_ms):
        if not frame_times:
            raise ValueError("need at least one frame")
        if duration_ms <= 0:
            raise ValueError("duration must be positive")
        # Normalized, ascending positions in [0, 1]; frame_times[0] is 0.0.
        self._frame_times = list(frame_times)
        self._duration_ms = float(duration_ms)

        self.index = 0
        self.done = False

    def update(self, now_ms):
        progress = now_ms / self._duration_ms
        if progress >= 1.0:
            self.index = len(self._frame_times) - 1
            self.done = True
            return
        if progress <= 0.0:
            self.index = 0
            return
        # The last frame whose normalized position has been reached. During a
        # still stretch (few frames, large time gap) this holds the same frame,
        # which is correct — the cat really was motionless there.
        self.index = max(0, bisect_right(self._frame_times, progress) - 1)

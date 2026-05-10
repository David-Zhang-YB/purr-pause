from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class RestTimer(QObject):
    rest_due = pyqtSignal()

    def __init__(self, interval_minutes: int = 20):
        super().__init__()
        self._interval_ms = interval_minutes * 60 * 1000
        self._paused = False
        self._timer = QTimer()
        self._timer.timeout.connect(self.rest_due)

    def start(self) -> None:
        self._timer.start(self._interval_ms)

    def pause(self) -> None:
        if not self._paused:
            self._timer.stop()
            self._paused = True

    def resume(self) -> None:
        if self._paused:
            self._paused = False
            self._timer.start(self._interval_ms)

    def reset(self, interval_minutes: int) -> None:
        self._interval_ms = interval_minutes * 60 * 1000
        self._timer.stop()
        self._paused = False
        self._timer.start(self._interval_ms)

    @property
    def is_paused(self) -> bool:
        return self._paused

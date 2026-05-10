import sys

from PyQt6.QtWidgets import QApplication

from cat_window import CatWindow
from settings import load_config
from timer import RestTimer
from tray import TrayIcon


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关闭弹窗不退出 app

    config = load_config()
    timer = RestTimer(interval_minutes=config["interval_minutes"])
    tray = TrayIcon(timer)  # noqa: F841  保持引用防止 GC

    _windows: list = []

    def on_rest_due() -> None:
        if any(w.isVisible() for w in _windows):
            return
        window = CatWindow()
        _windows.append(window)
        window.destroyed.connect(lambda: _windows.remove(window))
        window.show()

    timer.rest_due.connect(on_rest_due)
    timer.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

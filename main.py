import sys

from PyQt6.QtWidgets import QApplication

from cat_anim_window import CatAnimWindow
from cat_window import CatWindow
from paths import resource_path
from settings import load_config
from timer import RestTimer
from tray import TrayIcon

_ANIM_SPRITES = resource_path("assets/cat_anim")


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
        cfg = load_config()
        window = CatWindow(
            image_path=cfg.get("cat_image_path", ""),
            rest_duration=cfg.get("rest_duration_seconds", 20),
        )
        _windows.append(window)
        window.destroyed.connect(lambda: _windows.remove(window))

        if (_ANIM_SPRITES / "manifest.json").exists():
            cat_anim = CatAnimWindow(
                _ANIM_SPRITES,
                rest_duration_seconds=cfg.get("rest_duration_seconds", 20),
            )
            _windows.append(cat_anim)
            cat_anim.destroyed.connect(lambda: _windows.remove(cat_anim))
            # The cat plays its whole arc over the rest duration and finishes on
            # its own clock; this also ends it immediately on early × dismissal.
            window.countdown_finished.connect(cat_anim.request_finish)
            cat_anim.show()

        window.show()

    timer.rest_due.connect(on_rest_due)
    timer.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

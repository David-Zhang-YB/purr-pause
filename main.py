import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from cat_anim_window import CatAnimWindow
from cat_window import CatWindow
from settings import load_config
from timer import RestTimer
from tray import TrayIcon

_ASSET_DIR  = Path(__file__).parent / "assets"
_ANIM_VIDEO = _ASSET_DIR / "American Shorthair Cat Transparent.mp4"


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

        if _ANIM_VIDEO.exists():
            cat_anim = CatAnimWindow(str(_ANIM_VIDEO))
            window.countdown_finished.connect(cat_anim.start_walk_out)
            cat_anim.show()

        window.show()

    timer.rest_due.connect(on_rest_due)
    timer.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

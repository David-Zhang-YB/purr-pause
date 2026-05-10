from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon


def _make_cat_icon() -> QIcon:
    px = QPixmap(QSize(32, 32))
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setFont(QFont("Segoe UI Emoji", 20))
    painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "🐱")
    painter.end()
    return QIcon(px)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, timer, parent=None):
        super().__init__(_make_cat_icon(), parent)
        self._timer = timer

        menu = QMenu()

        self._pause_action = menu.addAction("⏸ 暂停")
        self._pause_action.triggered.connect(self._toggle_pause)

        settings_action = menu.addAction("⚙ 设置")
        settings_action.triggered.connect(self._open_settings)

        about_action = menu.addAction("ℹ 关于")
        about_action.triggered.connect(self._show_about)

        menu.addSeparator()
        quit_action = menu.addAction("✕ 退出")
        quit_action.triggered.connect(QApplication.quit)

        self.setContextMenu(menu)
        self.setToolTip("Purr Pause — 20-20-20 护眼提醒")
        self.show()

    def _toggle_pause(self) -> None:
        if self._timer.is_paused:
            self._timer.resume()
            self._pause_action.setText("⏸ 暂停")
        else:
            self._timer.pause()
            self._pause_action.setText("▶ 继续")

    def _open_settings(self) -> None:
        from settings import SettingsDialog, load_config, save_config

        config = load_config()
        dialog = SettingsDialog(current_interval=config["interval_minutes"])
        dialog.interval_changed.connect(self._on_interval_changed)
        dialog.exec()

    def _on_interval_changed(self, minutes: int) -> None:
        from settings import load_config, save_config

        config = load_config()
        config["interval_minutes"] = minutes
        save_config(config)
        self._timer.reset(minutes)

    def _show_about(self) -> None:
        QMessageBox.about(
            None,
            "关于 Purr Pause",
            "Purr Pause v1.0\n\n遵循 20-20-20 护眼法则\n"
            "每工作 20 分钟，休息 20 秒",
        )

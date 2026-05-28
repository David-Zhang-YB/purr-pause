from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMenu, QMessageBox,
    QSystemTrayIcon, QWidget, QWidgetAction,
)

from version import VERSION


def _make_cat_icon() -> QIcon:
    px = QPixmap(QSize(32, 32))
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setFont(QFont("Segoe UI Emoji", 20))
    painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "🐱")
    painter.end()
    return QIcon(px)


def _make_header_icon(size: int = 22) -> QPixmap:
    px = QPixmap(QSize(size, size))
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setFont(QFont("Segoe UI Emoji", int(size * 0.75)))
    painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "🐱")
    painter.end()
    return px


def _make_header(menu: QMenu) -> QWidgetAction:
    """Create a non-clickable app header for the top of the context menu."""
    widget = QWidget()
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    outer = QHBoxLayout(widget)
    outer.setContentsMargins(18, 10, 18, 10)
    outer.setSpacing(12)

    icon = QLabel()
    icon.setPixmap(_make_header_icon())
    icon.setStyleSheet("background: transparent;")
    outer.addWidget(icon)

    title = QLabel("Purr Pause")
    title.setStyleSheet(
        "color: #F5F5F5; font-size: 14px; font-weight: 600; background: transparent;"
    )
    outer.addWidget(title)
    outer.addStretch()

    action = QWidgetAction(menu)
    action.setDefaultWidget(widget)
    return action


class TrayIcon(QSystemTrayIcon):
    def __init__(self, timer, parent=None):
        super().__init__(_make_cat_icon(), parent)
        self._timer = timer

        menu = QMenu()
        menu.setMinimumWidth(240)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1F1F1F;
                color: #F5F5F5;
                border: 1px solid #333333;
                border-radius: 10px;
                padding: 4px 0px;
            }
            QMenu::item {
                padding: 10px 24px 10px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: rgba(255,255,255,0.08);
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #333333;
                margin: 6px 12px;
            }
        """)

        menu.addAction(_make_header(menu))
        menu.addSeparator()

        self._pause_action = menu.addAction("暂停")
        self._pause_action.triggered.connect(self._toggle_pause)

        settings_action = menu.addAction("设置")
        settings_action.triggered.connect(self._open_settings)

        menu.addSeparator()
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(QApplication.quit)

        self.setContextMenu(menu)
        self.setToolTip(f"Purr Pause v{VERSION}")
        self.show()

    def _toggle_pause(self) -> None:
        if self._timer.is_paused:
            self._timer.resume()
            self._pause_action.setText("暂停")
        else:
            self._timer.pause()
            self._pause_action.setText("继续")

    def _open_settings(self) -> None:
        from settings import SettingsDialog, load_config

        config = load_config()
        dialog = SettingsDialog(
            current_interval=config["interval_minutes"],
            current_rest_duration=config.get("rest_duration_seconds", 20),
        )
        dialog.interval_changed.connect(self._on_interval_changed)
        dialog.rest_duration_changed.connect(self._on_rest_duration_changed)
        dialog.exec()

    def _on_interval_changed(self, minutes: int) -> None:
        from settings import load_config, save_config
        config = load_config()
        config["interval_minutes"] = minutes
        save_config(config)
        self._timer.reset(minutes)

    def _on_rest_duration_changed(self, seconds: int) -> None:
        from settings import load_config, save_config
        config = load_config()
        config["rest_duration_seconds"] = seconds
        save_config(config)

    def _show_about(self) -> None:
        QMessageBox.about(
            None,
            "关于 Purr Pause",
            "Purr Pause v1.0\n\n遵循 20-20-20 护眼法则\n每工作 20 分钟，休息 20 秒",
        )

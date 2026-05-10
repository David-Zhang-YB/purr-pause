import json
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.default.json"
CONFIG_PATH = BASE_DIR / "config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        shutil.copy(DEFAULT_CONFIG_PATH, CONFIG_PATH)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_config(data: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout,
)


class SettingsDialog(QDialog):
    interval_changed = pyqtSignal(int)

    def __init__(self, current_interval: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Purr Pause 设置")
        self.setFixedSize(300, 150)

        layout = QVBoxLayout()

        row = QHBoxLayout()
        row.addWidget(QLabel("提醒间隔（分钟）："))
        self.spinbox = QSpinBox()
        self.spinbox.setRange(5, 60)
        self.spinbox.setSingleStep(5)
        self.spinbox.setValue(current_interval)
        row.addWidget(self.spinbox)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        self.setLayout(layout)

    def _save(self) -> None:
        self.interval_changed.emit(self.spinbox.value())
        self.accept()

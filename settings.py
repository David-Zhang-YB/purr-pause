import json
import shutil

from paths import resource_path, user_data_dir

DEFAULT_CONFIG_PATH = resource_path("config.default.json")
CONFIG_PATH = user_data_dir() / "config.json"


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
    QDialog, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QVBoxLayout,
)


BG_DIALOG      = "#1E1E1E"
BG_INPUT       = "#2B2B2B"
BORDER_SUBTLE  = "#333333"
TEXT_PRIMARY   = "#F5F5F5"
TEXT_SECONDARY = "#A8A8A8"
ACCENT         = "#F4B86A"
ACCENT_HOVER   = "#D99A43"


class SettingsDialog(QDialog):
    interval_changed      = pyqtSignal(int)
    rest_duration_changed = pyqtSignal(int)

    def __init__(
        self,
        current_interval: int,
        current_rest_duration: int = 20,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Purr Pause 设置")
        self.setFixedSize(400, 200)
        self.setStyleSheet(f"""
            QDialog  {{ background: {BG_DIALOG}; }}
            QLabel   {{ color: {TEXT_PRIMARY}; font-size: 13px; }}
            QLabel#subtitle {{ color: {TEXT_SECONDARY}; font-size: 12px; }}
            QLabel#unit     {{ color: {TEXT_SECONDARY}; font-size: 12px; }}
            QSpinBox {{
                background: {BG_INPUT}; color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_SUBTLE}; border-radius: 6px;
                padding: 3px 6px;
            }}
            QSpinBox:focus {{ border: 1px solid {ACCENT}; }}
            QSpinBox::up-button, QSpinBox::down-button {{ width: 14px; }}
            QPushButton {{
                background: rgba(255,255,255,0.08); color: {TEXT_PRIMARY};
                border: none; border-radius: 6px;
                padding: 6px 18px; font-size: 13px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.14); }}
            QPushButton#primary {{
                background: {ACCENT}; color: {BG_DIALOG}; font-weight: 600;
            }}
            QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
        """)

        root = QVBoxLayout()
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(10)

        subtitle = QLabel("调整护眼提醒和休息时长")
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)
        root.addSpacing(4)

        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(10)
        form.setColumnStretch(0, 1)

        form.addWidget(QLabel("提醒间隔"), 0, 0)
        self.spinbox = QSpinBox()
        self.spinbox.setRange(1, 60)
        self.spinbox.setSingleStep(1)
        self.spinbox.setValue(int(current_interval))
        self.spinbox.setFixedWidth(64)
        form.addWidget(self.spinbox, 0, 1)
        unit_min = QLabel("分钟")
        unit_min.setObjectName("unit")
        form.addWidget(unit_min, 0, 2)

        form.addWidget(QLabel("休息时长"), 1, 0)
        self.rest_spinbox = QSpinBox()
        self.rest_spinbox.setRange(10, 60)
        self.rest_spinbox.setSingleStep(5)
        self.rest_spinbox.setValue(int(current_rest_duration))
        self.rest_spinbox.setFixedWidth(64)
        form.addWidget(self.rest_spinbox, 1, 1)
        unit_sec = QLabel("秒")
        unit_sec.setObjectName("unit")
        form.addWidget(unit_sec, 1, 2)

        root.addLayout(form)

        root.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

        self.setLayout(root)

    def _save(self) -> None:
        self.interval_changed.emit(self.spinbox.value())
        self.rest_duration_changed.emit(self.rest_spinbox.value())
        self.accept()

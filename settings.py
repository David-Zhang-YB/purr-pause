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
    QDialog, QFileDialog, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout,
)


class SettingsDialog(QDialog):
    interval_changed = pyqtSignal(int)
    image_path_changed = pyqtSignal(str)

    def __init__(self, current_interval: int, current_image_path: str = "", parent=None):
        super().__init__(parent)
        self._image_path = current_image_path
        self.setWindowTitle("Purr Pause 设置")
        self.setFixedSize(360, 180)

        layout = QVBoxLayout()

        row = QHBoxLayout()
        row.addWidget(QLabel("提醒间隔（分钟）："))
        self.spinbox = QSpinBox()
        self.spinbox.setRange(5, 60)
        self.spinbox.setSingleStep(5)
        self.spinbox.setValue(current_interval)
        row.addWidget(self.spinbox)
        layout.addLayout(row)

        img_row = QHBoxLayout()
        img_row.addWidget(QLabel("猫咪图片："))
        from pathlib import Path as _Path
        self._img_label = QLabel(
            _Path(current_image_path).name if current_image_path else "（默认）"
        )
        self._img_label.setStyleSheet("color: grey;")
        img_row.addWidget(self._img_label, 1)
        pick_btn = QPushButton("选择…")
        pick_btn.clicked.connect(self._pick_image)
        img_row.addWidget(pick_btn)
        layout.addLayout(img_row)

        buttons = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        self.setLayout(layout)

    def _pick_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择猫咪图片", "",
            "图片文件 (*.gif *.png *.jpg *.jpeg *.webp)",
        )
        if path:
            from pathlib import Path as _Path
            self._image_path = path
            self._img_label.setText(_Path(path).name)

    def _save(self) -> None:
        self.interval_changed.emit(self.spinbox.value())
        self.image_path_changed.emit(self._image_path)
        self.accept()

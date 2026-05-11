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


from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QVBoxLayout,
)

_DEFAULT_CAT = BASE_DIR / "assets" / "cat.gif"


class SettingsDialog(QDialog):
    interval_changed = pyqtSignal(int)
    rest_duration_changed = pyqtSignal(int)
    image_path_changed = pyqtSignal(str)

    def __init__(
        self,
        current_interval: int,
        current_rest_duration: int = 20,
        current_image_path: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._image_path = current_image_path
        self.setWindowTitle("Purr Pause 设置")
        self.setFixedSize(400, 300)
        self.setStyleSheet("""
            QDialog  { background: #1e1e1e; }
            QLabel   { color: #e0e0e0; }
            QFrame   { background: rgba(255,255,255,0.06); border-radius: 12px; }
            QSpinBox {
                background: #2c2c2c; color: white;
                border: 1px solid #555; border-radius: 6px;
                padding: 3px 8px;
            }
            QSpinBox::up-button, QSpinBox::down-button { width: 16px; }
            QPushButton {
                background: rgba(255,255,255,0.12); color: white;
                border: none; border-radius: 8px;
                padding: 6px 20px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.22); }
        """)

        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── 参数卡片 ──────────────────────────────────────────
        params_card = QFrame()
        params_card.setContentsMargins(0, 0, 0, 0)
        params_layout = QVBoxLayout(params_card)
        params_layout.setContentsMargins(16, 12, 16, 12)
        params_layout.setSpacing(10)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("提醒间隔（分钟）："))
        self.spinbox = QSpinBox()
        self.spinbox.setRange(5, 60)
        self.spinbox.setSingleStep(5)
        self.spinbox.setValue(current_interval)
        interval_row.addWidget(self.spinbox)
        params_layout.addLayout(interval_row)

        rest_row = QHBoxLayout()
        rest_row.addWidget(QLabel("休息时长（秒）："))
        self.rest_spinbox = QSpinBox()
        self.rest_spinbox.setRange(10, 60)
        self.rest_spinbox.setSingleStep(5)
        self.rest_spinbox.setValue(current_rest_duration)
        rest_row.addWidget(self.rest_spinbox)
        params_layout.addLayout(rest_row)

        root.addWidget(params_card)

        # ── 图片卡片 ──────────────────────────────────────────
        img_card = QFrame()
        img_card.setContentsMargins(0, 0, 0, 0)
        img_layout = QHBoxLayout(img_card)
        img_layout.setContentsMargins(16, 12, 16, 12)
        img_layout.setSpacing(12)

        self._preview = QLabel()
        self._preview.setFixedSize(90, 80)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(
            "background: rgba(255,255,255,0.04); border-radius: 8px;"
        )
        self._load_preview(current_image_path)
        img_layout.addWidget(self._preview)

        img_info = QVBoxLayout()
        self._img_label = QLabel(
            Path(current_image_path).name if current_image_path else "（默认）"
        )
        self._img_label.setStyleSheet("color: #aaa;")
        img_info.addWidget(self._img_label)
        pick_btn = QPushButton("选择图片…")
        pick_btn.clicked.connect(self._pick_image)
        img_info.addWidget(pick_btn)
        img_layout.addLayout(img_info, 1)

        root.addWidget(img_card)

        # ── 按钮行 ───────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

        self.setLayout(root)

    def _load_preview(self, path: str) -> None:
        src = path if (path and Path(path).exists()) else str(_DEFAULT_CAT)
        px = QPixmap(src)
        if not px.isNull():
            self._preview.setPixmap(
                px.scaled(
                    90, 80,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def _pick_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择猫咪图片", "",
            "图片文件 (*.gif *.png *.jpg *.jpeg *.webp)",
        )
        if path:
            self._image_path = path
            self._img_label.setText(Path(path).name)
            self._load_preview(path)

    def _save(self) -> None:
        self.interval_changed.emit(self.spinbox.value())
        self.rest_duration_changed.emit(self.rest_spinbox.value())
        self.image_path_changed.emit(self._image_path)
        self.accept()

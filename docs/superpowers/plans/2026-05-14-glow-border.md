# Amber Breathing Glow Border Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `QGraphicsDropShadowEffect` in `CatWindow` with a custom `_GlowCard` widget that draws an amber gradient border with a breathing glow animation.

**Architecture:** Single-file change in `cat_window.py`. New `_GlowCard(QWidget)` class handles all card painting via `paintEvent` (glow layers + gradient border + fill) and exposes a `glow_intensity` `pyqtProperty` driven by a looping `QSequentialAnimationGroup`. The breathing animation starts only after the entry animation completes.

**Tech Stack:** Python 3.11+, PyQt6 ≥6.6.0, pytest ≥8.0.0, pytest-qt ≥4.4.0

---

## File Map

| 文件 | 改动 |
|------|------|
| `cat_window.py` | 唯一改动文件：新增常量 `GLOW_MARGIN`，新增 `_GlowCard` 类，修改 `CatWindow.__init__`、`_setup_ui`、`showEvent`、`closeEvent`、`_fade_out`，移除 `QGraphicsDropShadowEffect` |

---

## Task 1: 确认基线

**Files:** 无改动

- [ ] **Step 1: 运行全部测试，确认基线**

```bash
pytest -v
```

Expected: `26 passed, 0 failed`

---

## Task 2: 更新 imports + 新增 GLOW_MARGIN 常量

**Files:**
- Modify: `cat_window.py`

- [ ] **Step 1: 替换 QtCore import**

将：
```python
from PyQt6.QtCore import (
    Qt, QSize, QTimer, QPropertyAnimation,
    QParallelAnimationGroup, QEasingCurve, QPoint,
)
```

替换为：
```python
from PyQt6.QtCore import (
    Qt, QSize, QTimer, QPropertyAnimation, pyqtProperty,
    QParallelAnimationGroup, QSequentialAnimationGroup,
    QEasingCurve, QPoint,
)
```

- [ ] **Step 2: 替换 QtGui import**

将：
```python
from PyQt6.QtGui import (
    QColor, QFont, QFontDatabase, QLinearGradient, QMovie, QPixmap, QPainter,
)
```

替换为：
```python
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QFontDatabase, QLinearGradient,
    QMovie, QPixmap, QPainter, QRectF,
)
```

- [ ] **Step 3: 替换 QtWidgets import（移除 QGraphicsDropShadowEffect）**

将：
```python
from PyQt6.QtWidgets import (
    QApplication, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)
```

替换为：
```python
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)
```

- [ ] **Step 4: 在模块级常量中新增 GLOW_MARGIN**

在 `MARGIN_EDGE   = 16` 行下方添加：
```python
GLOW_MARGIN   = 12          # max glow spread (px); must be ≤ SHADOW_MARGIN
```

- [ ] **Step 5: 运行测试，确认 import 修改不破坏任何东西**

```bash
pytest -v
```

Expected: `26 passed, 0 failed`

---

## Task 3: 实现 `_GlowCard` 类

**Files:**
- Modify: `cat_window.py`（在 `_ProgressBar` 类之后、`CatWindow` 类之前插入）

- [ ] **Step 1: 在 `_ProgressBar` 类结束后插入完整的 `_GlowCard` 类**

在 `_ProgressBar.paintEvent` 的 `p.end()` 行之后，`class CatWindow` 行之前，插入：

```python

class _GlowCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._glow: float = 0.4
        self._anim_group: QSequentialAnimationGroup | None = None
        self.setFixedSize(CARD_W + 2 * GLOW_MARGIN, CARD_H + 2 * GLOW_MARGIN)

    @pyqtProperty(float)
    def glow_intensity(self) -> float:
        return self._glow

    @glow_intensity.setter
    def glow_intensity(self, value: float) -> None:
        self._glow = value
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)

        card_r = QRectF(self.rect()).adjusted(
            GLOW_MARGIN, GLOW_MARGIN, -GLOW_MARGIN, -GLOW_MARGIN
        )

        # Outer glow layers (amber, alpha scales with glow_intensity)
        for spread, base_alpha in ((12, 40), (7, 65), (3, 90)):
            gr = card_r.adjusted(-spread, -spread, spread, spread)
            p.setBrush(QColor(0xFF, 0x9F, 0x0A, int(base_alpha * self._glow)))
            p.drawRoundedRect(gr, 16 + spread * 0.6, 16 + spread * 0.6)

        # Gradient border fill (amber → gold), leaves ~2px ring after fill is drawn on top
        grad = QLinearGradient(card_r.topLeft(), card_r.bottomRight())
        grad.setColorAt(0.0, QColor(0xFF, 0x9F, 0x0A))
        grad.setColorAt(1.0, QColor(0xFF, 0xCC, 0x02))
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(card_r, 16.0, 16.0)

        # Inner card fill covers border, leaving a ~2px gradient ring visible
        p.setBrush(QColor(22, 22, 26, 250))
        p.drawRoundedRect(card_r.adjusted(2, 2, -2, -2), 14.0, 14.0)

        p.end()

    def start_breathing(self) -> None:
        fwd = QPropertyAnimation(self, b"glow_intensity")
        fwd.setDuration(1200)
        fwd.setStartValue(0.4)
        fwd.setEndValue(1.0)
        fwd.setEasingCurve(QEasingCurve.Type.InOutSine)

        bwd = QPropertyAnimation(self, b"glow_intensity")
        bwd.setDuration(1200)
        bwd.setStartValue(1.0)
        bwd.setEndValue(0.4)
        bwd.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._anim_group = QSequentialAnimationGroup()
        self._anim_group.addAnimation(fwd)
        self._anim_group.addAnimation(bwd)
        self._anim_group.setLoopCount(-1)
        self._anim_group.start()

    def stop_breathing(self) -> None:
        if self._anim_group is not None:
            self._anim_group.stop()
```

- [ ] **Step 2: 运行测试，确认新类不破坏任何东西**

```bash
pytest -v
```

Expected: `26 passed, 0 failed`

---

## Task 4: 修改 `CatWindow` 使用 `_GlowCard`

**Files:**
- Modify: `cat_window.py`

- [ ] **Step 1: 在 `CatWindow.__init__` 中添加 `_glow_card` GC 守护**

找到 `__init__` 中的 `self._entry_anim = None` 行，在其下方添加：
```python
        self._glow_card: _GlowCard | None = None
```

完整 `__init__` 应为：
```python
    def __init__(self, image_path: str = "", rest_duration: int = 20):
        super().__init__()
        self._image_path = image_path
        self._countdown = rest_duration
        self._anim = None
        self._movie = None
        self._entry_anim = None
        self._glow_card: _GlowCard | None = None
        self._setup_window()
        self._setup_ui()
        self._start_countdown()
```

- [ ] **Step 2: 替换 `_setup_ui` 末尾的卡片容器 + 投影阴影代码**

找到并替换以下整段（从注释 `# ── 卡片容器` 到 `self.setLayout(outer)`）：

**替换前：**
```python
        # ── 卡片容器 ──────────────────────────────────────────
        inner = QWidget()
        inner.setFixedSize(CARD_W, CARD_H)
        inner_layout = QHBoxLayout()
        inner_layout.setContentsMargins(12, 12, 12, 12)
        inner_layout.setSpacing(12)
        inner_layout.addWidget(gif_label)
        inner_layout.addLayout(right_col)
        inner.setLayout(inner_layout)
        inner.setStyleSheet(
            "background: rgba(28, 28, 30, 0.92); border-radius: 16px;"
        )

        # ── 投影阴影 ──────────────────────────────────────────
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 120))
        inner.setGraphicsEffect(shadow)

        # ── 外层透明容器（为阴影留白） ─────────────────────────
        outer = QVBoxLayout()
        outer.setContentsMargins(SHADOW_MARGIN, SHADOW_MARGIN, SHADOW_MARGIN, SHADOW_MARGIN)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(inner)
        self.setLayout(outer)
```

**替换后：**
```python
        # ── 卡片容器（_GlowCard 包含发光边框 + 内填充） ─────────
        self._glow_card = _GlowCard()
        inner_layout = QHBoxLayout()
        inner_layout.setContentsMargins(
            GLOW_MARGIN + 12, GLOW_MARGIN + 12,
            GLOW_MARGIN + 12, GLOW_MARGIN + 12,
        )
        inner_layout.setSpacing(12)
        inner_layout.addWidget(gif_label)
        inner_layout.addLayout(right_col)
        self._glow_card.setLayout(inner_layout)

        # ── 外层透明容器（为发光留白） ────────────────────────────
        outer = QVBoxLayout()
        outer.setContentsMargins(
            SHADOW_MARGIN - GLOW_MARGIN, SHADOW_MARGIN - GLOW_MARGIN,
            SHADOW_MARGIN - GLOW_MARGIN, SHADOW_MARGIN - GLOW_MARGIN,
        )
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._glow_card)
        self.setLayout(outer)
```

- [ ] **Step 3: 运行测试**

```bash
pytest -v
```

Expected: `26 passed, 0 failed`

---

## Task 5: 连接呼吸动画 + 更新 closeEvent / _fade_out

**Files:**
- Modify: `cat_window.py`

- [ ] **Step 1: 在 `showEvent` 末尾连接 `start_breathing`**

找到 `showEvent` 中 `self._entry_anim.start()` 行，在其正下方添加：
```python
        self._entry_anim.finished.connect(self._glow_card.start_breathing)
```

完整的 `showEvent` 末尾应为：
```python
        self._entry_anim = QParallelAnimationGroup()
        self._entry_anim.addAnimation(pos_anim)
        self._entry_anim.addAnimation(opacity_anim)
        self._entry_anim.start()
        self._entry_anim.finished.connect(self._glow_card.start_breathing)
```

- [ ] **Step 2: 在 `closeEvent` 中停止呼吸动画**

将 `closeEvent` 整体替换为：
```python
    def closeEvent(self, event) -> None:
        self._timer.stop()
        if self._entry_anim is not None:
            self._entry_anim.stop()
        if self._glow_card is not None:
            self._glow_card.stop_breathing()
        super().closeEvent(event)
```

- [ ] **Step 3: 在 `_fade_out` 中停止呼吸动画**

将 `_fade_out` 整体替换为：
```python
    def _fade_out(self) -> None:
        if self._entry_anim is not None:
            self._entry_anim.stop()
        if self._glow_card is not None:
            self._glow_card.stop_breathing()
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(500)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.close)
        self._anim.start()
```

- [ ] **Step 4: 运行全部测试**

```bash
pytest -v
```

Expected: `26 passed, 0 failed`

- [ ] **Step 5: Commit**

```bash
git add cat_window.py
git commit -m "feat: replace drop shadow with amber breathing glow border"
```

---

## Task 6: 手动验证端到端

- [ ] **Step 1: 运行应用**

```bash
python main.py
```

- [ ] **Step 2: 验证以下行为**

| 验证点 | 预期结果 |
|--------|----------|
| 弹窗出现 | 入场弹簧动画正常，此时边框静止（glow_intensity=0.4） |
| 入场结束后（约 420ms） | 卡片四周出现约 2px 琥珀渐变边框，外侧发光开始缓慢呼吸 |
| 呼吸节律 | 约 2.4 秒一次（1.2s 渐亮 → 1.2s 渐暗），缓入缓出，流畅自然 |
| 进度条 | 琥珀渐变进度条正常每秒更新 |
| 点击 × | 呼吸动画立即停止，淡出退场正常 |
| 倒计时归零 | 呼吸动画停止，淡出退场正常，无残影 |
| 自定义图片 | 圆形缩略图正常显示，边框不受影响 |

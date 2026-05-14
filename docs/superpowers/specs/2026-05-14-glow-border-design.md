# Purr Pause — 琥珀呼吸发光边框设计文档

**日期：** 2026-05-14
**状态：** 已批准
**影响文件：** `cat_window.py`（唯一改动文件）

---

## 背景

弹窗通知卡已完成 Apple 风格重设计（Task 13），具备投影阴影、琥珀进度条、圆形缩略图、弹簧入场动画和 Noto Sans SC 字体。本次升级将现有的 `QGraphicsDropShadowEffect` 替换为自定义"呼吸发光边框"，赋予卡片更强的生命感和品牌个性，同时保持整体视觉语言一致。

---

## 目标

- 卡片四周出现 1.5px 琥珀渐变边框（#FF9F0A → #FFCC02）
- 边框外侧有多层外发光（模拟 blur 扩散），发光强度以约 2.4 秒为周期缓慢"呼吸"
- 呼吸动画在入场动画结束后启动，不与弹入效果冲突
- 移除 `QGraphicsDropShadowEffect`，发光边框本身提供深度感

---

## 不改动的内容

以下所有功能保持不变：

- 入场动画（OutBack 弹簧，420ms 位移 + 280ms 淡入）
- 淡出退场动画（500ms）
- 圆形猫咪缩略图（80×80）
- 琥珀渐变进度条
- Noto Sans SC 字体（Light/Medium）
- 倒计时逻辑
- 窗口尺寸（WIN_W=400, WIN_H=160, SHADOW_MARGIN=20）
- 所有测试（无需新增或修改）

---

## 技术设计

### 新增常量

```python
GLOW_MARGIN = 12   # 外发光最大扩散半径（px），必须 ≤ SHADOW_MARGIN
```

### 新增：`_GlowCard(QWidget)`

替代现有的 `inner = QWidget()` + `QGraphicsDropShadowEffect` 组合。

**尺寸：** `(CARD_W + 2*GLOW_MARGIN) × (CARD_H + 2*GLOW_MARGIN)`，即 384×144px。
比原 `inner` 稍大，为外发光提供绘制空间，同时仍在 `SHADOW_MARGIN=20` 范围内。
外层 `QVBoxLayout` 的 margin 由 `SHADOW_MARGIN` 改为 `SHADOW_MARGIN - GLOW_MARGIN`（=8px），保持卡片可见位置不变。

**`paintEvent` 绘制顺序（从外到内）：**

1. **外发光层**（3 层同心圆角矩形，基准矩形为 card_rect = `rect().adjusted(GLOW_MARGIN, GLOW_MARGIN, -GLOW_MARGIN, -GLOW_MARGIN)`，alpha 随 `glow_intensity` 缩放）
   - 层 1（最外）：card_rect 向外扩 12px，alpha = `int(40 * glow_intensity)`，琥珀色
   - 层 2：card_rect 向外扩 7px，alpha = `int(65 * glow_intensity)`，琥珀色
   - 层 3：card_rect 向外扩 3px，alpha = `int(90 * glow_intensity)`，琥珀色

2. **渐变边框**（固定，不随 `glow_intensity` 变化）
   - `QPen` 宽度 1.5px
   - `QLinearGradient`：从 card_rect 左上 `#FF9F0A` 到右下 `#FFCC02`
   - 绘制 card_rect 圆角矩形（radius=16px）

3. **内填充**
   - `QBrush(QColor(22, 22, 26, 250))`，比现有的 `rgba(28,28,30,0.92)` 略深，让边框更突出
   - 绘制 card_rect 内缩 1px 的圆角矩形（radius=15px）

**`glow_intensity` 属性：**

```python
@pyqtProperty(float)
def glow_intensity(self) -> float:
    return self._glow

@glow_intensity.setter
def glow_intensity(self, value: float) -> None:
    self._glow = value
    self.update()
```

**呼吸动画：**

- `QPropertyAnimation(self._glow_card, b"glow_intensity")`
- 起始值 0.4，结束值 1.0（不从 0 开始，避免边框完全消失）
- 时长 1200ms，`QEasingCurve.Type.InOutSine`
- `setLoopCount(-1)` 无限循环
- `direction` 每次循环翻转（Forward → Backward → Forward...），实现 0.4→1.0→0.4 呼吸效果
  - 实现方式：使用 `QSequentialAnimationGroup`，包含两个 `QPropertyAnimation`（一去一回）

### 修改：`CatWindow._setup_ui`

- 将 `inner = QWidget()` 替换为 `self._glow_card = _GlowCard()`
- 将原来添加到 `inner` 的内容布局改为添加到 `_glow_card`
- 删除 `QGraphicsDropShadowEffect` 相关代码
- 删除 `inner.setStyleSheet(...)` 中的背景和圆角（移入 `_GlowCard.paintEvent`）

### 修改：`CatWindow.showEvent`

在 `_entry_anim.finished` 信号上连接 `_glow_card.start_breathing()`，确保呼吸动画在入场结束后启动：

```python
self._entry_anim.finished.connect(self._glow_card.start_breathing)
```

### 修改：`CatWindow.closeEvent` / `_fade_out`

在 `closeEvent` 中停止 `_glow_card` 的呼吸动画，防止关闭后残留计算：

```python
self._glow_card.stop_breathing()
```

### 移除的 import

```python
QGraphicsDropShadowEffect  # 从 QtWidgets import 中移除
```

---

## 动画参数总结

| 参数 | 值 |
|------|-----|
| 呼吸周期 | 2400ms（1200ms × 2，一去一回） |
| glow_intensity 范围 | 0.4 – 1.0 |
| 缓动曲线 | InOutSine |
| 循环 | 无限 |
| 启动时机 | 入场动画结束后 |

---

## 测试影响

无需新增或修改测试。现有 26 个测试均不依赖 `QGraphicsDropShadowEffect` 或 `_glow_card` 内部实现，全部应继续通过。

---

## 验收标准

| 验证点 | 预期 |
|--------|------|
| 弹窗出现时 | 入场动画（弹簧+淡入）正常，无发光效果 |
| 入场结束后 | 边框琥珀渐变清晰，外发光开始缓慢呼吸 |
| 呼吸节律 | 约每 2.4 秒一次，缓入缓出，不突兀 |
| 点击 × 或倒计时归零 | 淡出动画正常，无残影 |
| pytest -v | 26 passed，0 failed |

# Purr Pause — 猫咪走过屏幕动画重做设计文档

**日期：** 2026-05-29
**状态：** 已批准
**影响文件：** `cat_anim_window.py`（全文重写）、`scripts/extract_cat_frames.py`（新增）、`assets/cat_anim/`（新增）、`tests/test_cat_anim_window.py`（重写）、`main.py`（取消注释 + 改签名）、`scripts/build_dist.py`（资源切换）

---

## 1. 背景

`cat_anim_window.py` 实现了"猫咪从屏幕一侧走到另一侧"的休息期间动画，但 5 月底以 "pending video pipeline fix" 为由搁置（[main.py:36-42](../../../main.py#L36-L42) 整段被注释）。搁置根因：

- **稳定性**：MP4 + QMediaPlayer + QVideoSink + numpy chroma-key 的运行时管线有多处零错误处理（[cat_anim_window.py:104-120](../../../cat_anim_window.py#L104-L120)）。帧数据为 null 时直接 `np.frombuffer` 调用 → 随机崩溃，依赖系统 H.264 解码器、不能稳定重现。
- **视觉**：对 RGB=(0,0,0)±25 的硬阈值 chroma-key 导致猫咪轮廓有黑色羽化/脱色伪影。

用户决策：
- 意图保持："休息期间，猫从屏幕一边走过去"（走 → 停 → 走）
- 技术走向：放弃 MP4 运行时管道，重走 PNG 帧序列

---

## 2. 关键发现

[cat_anim_window.py:47](../../../cat_anim_window.py#L47) 用 `setGeometry(primaryScreen().geometry())` 全屏，[paintEvent:140](../../../cat_anim_window.py#L140) 画 `self.rect()`——**没有任何逐帧位移计算**。横向移动完全烘焙在 MP4 帧里。

所以**不能**采用"小 sprite + `QPropertyAnimation` 横向位移"的方案（需要逐帧定位猫的 bounding box、容易出现脚步与移动不同步的"脚步打滑"问题）。

**正确做法**：保留全屏 overlay，把烘焙后的帧逐张存为 PNG，由 `QTimer` 轮播驱动。

---

## 3. 关键决策

| 决策 | 选择 |
|---|---|
| 帧格式 | PNG（带 alpha 通道）|
| 抠图方式 | 离线，Pillow alpha 阈值 + 线性羽化 |
| Bounding box | 三段动画的 union bbox 裁剪 |
| 帧率 | 24 fps |
| 状态机 | WALK_IN → IDLE（循环）→ WALK_OUT → finished |
| 横向位移 | 不做——位移由帧本身呈现 |
| 透明窗口 | 保留 frameless + translucent + `WS_EX_TRANSPARENT` ctypes hack |
| 资源入仓 | PNG 帧入 git（约 2.3 MB），便于复制构建 |
| MP4 命运 | 保留在 `assets/` 不打包 .exe；仅作为帧提取脚本的输入 |
| 提取工具依赖 | `opencv-python-headless`（dev only，不进 requirements.txt）|

---

## 4. 不改动的内容

- `CatWindow` 通知卡的视觉、`countdown_finished` 信号
- `RestTimer` 计时逻辑
- 托盘菜单、设置窗口
- 既有测试（除 `test_cat_anim_window.py` 外）

---

## 5. 资源管线（一次性 offline）

新增 `scripts/extract_cat_frames.py`，读 `assets/American Shorthair Cat Transparent.mp4` 产出 `assets/cat_anim/`：

1. 按 24 fps 采样三段时间窗：
   - WALK_IN: 0.0–4.0 s
   - IDLE: 4.0–10.0 s（用 MSE 阈值去重，保留约 30 张代表帧）
   - WALK_OUT: 10.0–15.0 s
2. 每帧 alpha 处理：与纯黑距离 < 35 → alpha 0；距离 ∈ [35, 50] 线性羽化
3. 算三段所有帧的 union bbox，按 bbox 裁剪压缩体积
4. 输出 PNG + `manifest.json`：
   ```json
   { "bbox": [x, y, w, h], "fps": 24, "walk_in": 24, "idle": 30, "walk_out": 24 }
   ```

预算：约 78 张 PNG × 30 KB ≈ 2.3 MB。

---

## 6. 运行时架构（`cat_anim_window.py` 重写）

```python
class CatAnimWindow(QWidget):
    finished = pyqtSignal()

    def __init__(self, sprite_dir: Path, parent=None): ...
    def start_walk_out(self) -> None: ...     # 由 countdown_finished 触发
    def _load_frames(self, dir) -> bool: ...  # False → 立即 finished + close
    def _setup_window(self) -> None: ...
    def _make_click_through(self) -> None: ...# 保留 ctypes WS_EX_TRANSPARENT
    def _on_tick(self) -> None: ...           # 状态机驱动
    def paintEvent(self, e) -> None: ...
    def closeEvent(self, e) -> None: ...      # 显式 timer.stop()
```

状态机：
- `WALK_IN`：`_idx += 1` 到尾 → `IDLE`（如果 `_walk_out_pending` 直接 `WALK_OUT`）
- `IDLE`：`_idx = (_idx + 1) % len(idle)`，外部 `start_walk_out()` → `WALK_OUT`
- `WALK_OUT`：`_idx += 1` 到尾 → emit `finished()` + `close()`

错误处理（对照原痛点）：
- 缺 manifest 或 PNG load 失败 → 构造函数 schedule `finished` 后 close，**主程序看不到动画但不崩**
- 极短 rest（用户 1 秒）`start_walk_out` 在 WALK_IN 期间被调用 → 置 `_walk_out_pending = True`，WALK_IN 完成自动接 WALK_OUT
- `closeEvent` 显式 `self._timer.stop()`

复用 [paths.py](../../../paths.py) 的 `resource_path` 解析 sprite 目录路径。

---

## 7. 集成（`main.py:36-42`）

```python
_ANIM_SPRITES = resource_path("assets/cat_anim")

if (_ANIM_SPRITES / "manifest.json").exists():
    cat_anim = CatAnimWindow(_ANIM_SPRITES)
    _windows.append(cat_anim)
    cat_anim.destroyed.connect(lambda: _windows.remove(cat_anim))
    window.countdown_finished.connect(cat_anim.start_walk_out)
    cat_anim.finished.connect(cat_anim.close)
    cat_anim.show()
```

删除 `_ANIM_VIDEO`。

---

## 8. 构建脚本（`scripts/build_dist.py`）

- 删 `American Shorthair Cat Transparent.mp4` 的 `--add-data` 行
- 加 `--add-data f"{ROOT/'assets'/'cat_anim'};assets/cat_anim"`
- 预期 .exe 体积：107 MB → 约 77 MB

---

## 9. 测试（`tests/test_cat_anim_window.py` 重写）

现文件名 misleading（实际只测 CatWindow）。重写为针对 `CatAnimWindow`：

```python
@pytest.fixture
def sprite_dir(tmp_path):
    """每段 2 张 1×1 透明 PNG + manifest.json"""

def test_instantiates_with_valid_sprites
def test_missing_manifest_emits_finished_immediately
def test_walk_in_advances_through_frames
def test_state_transitions_walk_in_to_idle
def test_start_walk_out_during_idle_transitions_immediately
def test_start_walk_out_during_walk_in_queues_until_done
def test_walk_out_completion_emits_finished
```

全部 pytest-qt + tmp_path，**不依赖视频/编解码器**——这是 PNG 路线最大优势之一。

---

## 10. 验证

1. **离线提取**：`python scripts/extract_cat_frames.py` → 视觉抽查随机帧确认抠图干净
2. **单测全绿**：`pytest tests/test_cat_anim_window.py -v` + 全套 `pytest`
3. **源码模式手动**（`interval_minutes=0.1`）：猫从左 walk_in → 中间 idle 循环 → 倒计时归零 walk_out → 走完即关
4. **极短休息**（`rest_duration_seconds=1`）：`_walk_out_pending` 队列生效、不崩
5. **缺资源容错**：临时 mv `assets/cat_anim` → 主程序正常无动画无崩溃
6. **打包构建**：`python scripts/build_dist.py` → `dist/PurrPause.exe` 约 77 MB → 复制桌面双击触发休息看动画
7. **回归**：`%APPDATA%\PurrPause\config.json` 持久化沿用之前发布版的设置往返测试

---

## 11. 不在本次范围内

- 可配置猫咪外观、速度
- 多只猫场景
- 内容感知 idle
- 多显示器跨屏（明确只跑 `primaryScreen()`）

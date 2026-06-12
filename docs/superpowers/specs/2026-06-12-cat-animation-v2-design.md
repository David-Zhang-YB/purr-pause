# 过场动画 v2 设计：新素材 + 弹性时间线 + 顺滑引擎

> 状态：已与用户确认，待 spec 复审 → 转 writing-plans
> 日期：2026-06-12
> 前序：[2026-05-29-cat-anim-rebuild-design.md](2026-05-29-cat-anim-rebuild-design.md)（MP4→PNG sprite 状态机重建）

## 1. 背景与目标

休息提醒触发时，全屏播放"猫咪走过屏幕"的过场动画（`cat_anim_window.py`），配合右上角的休息卡片（`cat_window.py`）。当前实现是 `WALK_IN → IDLE循环 → WALK_OUT` 的 PNG sprite 状态机，由 `QTimer` 逐帧驱动。

**用户诉求**："过场动画更顺滑不卡顿。"

诊断把"卡顿"拆成两个独立问题：

1. **步进感（帧率低）**：walk 15fps，每帧 66ms，大屏横移肉眼可见台阶。
2. **抖动/掉帧（节奏不均）**：① `QTimer` 默认非 `PreciseTimer`，Windows 计时精度 ~15.6ms，66ms 间隔忽长忽短；② 每帧 `self.update()` 重绘整个全屏窗口且每帧从源重新 `SmoothPixmapTransform` 缩放 sprite，单帧偶尔超时预算 → 掉帧；③ `int(1000/15)=66ms` 取整漂移。

同时用户用 SeedDance/Seedance 2.0 重新生成了一段抠像更干净的素材，并希望把动画时间线从 15s 拉长到 20s（默认休息时长）。

**本设计目标**：换用新素材，重构播放状态机让中间段无缝循环并弹性适配休息时长，并从引擎层根治抖动/掉帧。

## 2. 关键事实（已实测）

**新素材** `assets/British Shorthair Silver Shaded Transparent.mp4`：
- 60fps / 902 帧 / 15.033s / **3840×2160 (4K)** / 67MB
- 黑底，靠颜色距离做 alpha 抠像（同旧管线）
- 运动弧线（源时间）：

| 源时间 | 动作 | 位置 |
|---|---|---|
| 0.0s | 头从左边缘探入 | 最左 |
| 3.0s | 大步走入（行走姿态） | 中左 |
| 6.1s | 低伏趴下（蹲卧、爪向前） | 中央偏左 |
| 10.5s | 坐直抬头（上身抬起、警觉） | 中央偏右 |
| 12.0s | 侧身起身朝右 | 偏右 |
| 14.9s | 仅余屁股/尾巴在右边缘 | 最右 |
| 15.0s | 基本走出画面 | 消失 |

**关键约束**：6.1s（低伏趴）与 10.5s（坐直）姿态不同。用户原方案"重复 6.1–10.5s 片段"在循环重启点会从坐直硬跳回趴下 → 肉眼可见跳帧。**ping-pong 往返循环解决之**（两端必为同一帧，数学保证零跳帧）。

**现有架构事实**：休息时长 `rest_duration_seconds` 可调（默认 20，范围 10–60）。`CatWindow` 倒计时结束时 emit `countdown_finished`，连到 `cat_anim.start_walk_out`。即 IDLE 段本就循环到倒计时结束才起身——动画时长本就弹性，不需要硬剪 20s 视频。用户的"20s"是默认时长下的特例。

## 3. 设计

三部分。A 与 B 紧耦合（共同交付用户的视觉目标），C 是引擎层（解耦，可独立成阶段，但本次纳入）。

### Part A — 素材管线（`scripts/extract_cat_frames.py`）

一次性离线脚本，重抽 PNG sprite 序列到 `assets/cat_anim/`。改动：

- **换源**：`SRC` 指向 `assets/British Shorthair Silver Shaded Transparent.mp4`
- **相位时间窗**（可微调常量；下为起始值，实施时按抽出帧目检校准）：
  - `WALK_IN = (0.0, 6.1)` — 探入 → 走入 → 落地趴下
  - `IDLE = (6.1, 10.5)` — 趴卧 → 坐直（供 ping-pong）
  - `WALK_OUT = (10.5, 15.1)` — 起身 → 向右走出画面
- **帧率**：`WALK_FPS = 30`（原 15，横移最吃帧率，翻倍消台阶感）；`IDLE_FPS = 15`（原 12，趴卧慢动作低帧足够，控体积）
- **缩放**：`SCALE = 0.25`（原 0.5；源从 1080p 变 4K，0.25 后画布回到 ~960×540，与现行一致，体积不爆）
- **dedup**：沿用 `WALK_DEDUP_MSE=100`、`IDLE_DEDUP_MSE=4000`；ping-pong 对 idle 端点姿态差异不敏感，无需额外约束
- **输出**：`manifest.json` + `walk_in_NN.png` / `idle_NN.png` / `walk_out_NN.png`，结构与现行完全一致（`canvas`、`walk_fps`、`idle_fps`、各相位 `[{x,y}]` 列表）。运行时无需改 manifest 读取逻辑

**体积预估**：帧数 206 → 约 300–340；sprite ~7.3MB → ~12MB；打包后 .exe 约 63MB → **~68MB**（+5MB）。用户已确认可接受。

**dev 依赖**：`opencv-python-headless`（不在 `requirements.txt`，已在 D:/Python 装好）。

### Part B — 播放状态机（`cat_anim_window.py`）

在现有 `WALK_IN / IDLE / WALK_OUT / FINISHED` 状态机上改：

**B1. IDLE 改 ping-pong 往返**
- 现：`self._idx = (self._idx + 1) % len(self._idle)`（播完跳回 0，端点跳帧）
- 改：三角波游标。维护 `self._idle_dir ∈ {+1, -1}`；每 tick `self._idx += self._idle_dir`；触界（`0` 或 `len-1`）时反向。序列 `0,1,…,n-1,n-2,…,1,0,1,…`，两端必为同帧，零跳帧。

**B2. 无缝衔接（相位边界同姿态）**
- `WALK_IN` 末帧（趴, 源6.1s）→ `IDLE` 首帧（趴, 源6.1s）：天然连续 ✓
- `IDLE` → `WALK_OUT`：`WALK_OUT` 首帧（坐直, 源10.5s）须接 `IDLE` 末帧（坐直, 源10.5s）。**退出握手**：收到退出请求后，不立即转场；强制 `_idle_dir = +1` 正向播到 `_idx == len(idle)-1`（坐直端），再转 `WALK_OUT`。保证起身总是从坐直姿态开始，无跳帧。

**B3. 弹性时长 + 退出请求路由**
- `start_walk_out()`（连到 `countdown_finished`）改为**置位 `self._exit_requested = True`**，不直接转场：
  - 当前 `IDLE`：进入 B2 的"正向播到坐直端再 WALK_OUT"流程
  - 当前 `WALK_IN`：置位 `_exit_requested`；`WALK_IN` 播完后进入 `IDLE`，立即正向单程扫到坐直端，再 `WALK_OUT`（避免 walk_in 趴姿直接跳到 walk_out 坐直姿。极端短倒计时才会触发，因为 walk_in 播放约 4s < 最短休息 10s，但仍须正确处理）
  - 当前 `WALK_OUT`/`FINISHED`：忽略（已在退出）
- IDLE 在 `_exit_requested` 为假时无限 ping-pong → 适配任意 10–60s 休息时长

**B4. 收尾淡出**
- `WALK_OUT` 播完后，不立即 `close()`；启 500ms `windowOpacity 1→0` 动画（`QPropertyAnimation`，复用 `cat_window.py` 同款淡出），结束再 emit `finished` + `close()`。对应用户方案的 19.5–20.0s 淡出，消失更柔。

### Part C — 顺滑引擎（`cat_anim_window.py`，根治抖动/掉帧）

**C1. PreciseTimer + 按时间戳选帧（time-based，自纠漂移）**
- 现：tick 时 `_idx += 1`，帧率漂移会累积。
- 改：维护 `QElapsedTimer`（相位起始时清零）+ `QTimer` 设 `Qt.TimerType.PreciseTimer`，以 ~60Hz（16ms）固定驱动重绘。每次重绘按 `elapsed_ms` 推算当前应显示帧：
  - 一次性相位（WALK_IN/WALK_OUT）：`idx = min(floor(elapsed_ms / 1000 * fps), n-1)`
  - IDLE：`period = 2*(n-1)`；`p = floor(elapsed_ms/1000*fps) % period`；`idx = p if p < n else period - p`（三角波，与 B1 等价但 time-based）
- 重绘频率与内容帧率解耦：30fps 内容在 60Hz 下每帧显示约 2 次刷新；漂移每帧重算、不累积。

**C2. 预缩放帧缓存**
- 现：每帧 `paintEvent` 用 `SmoothPixmapTransform` 从源 pixmap 重缩放到屏幕尺寸——30fps 翻倍后成本翻倍。
- 改：首次 `showEvent`（拿到屏幕几何）时，按 `paintEvent` 的 `scale`/`offset` 把每帧 sprite **一次性预缩放**成目标屏幕尺寸 `QPixmap`，连同目标 `(x,y)` 缓存。绘制时直接 `drawPixmap(point, cached)`，无每帧重缩放。
- 屏幕几何变化（极少在 20s 内发生）：检测到尺寸变化则重建缓存。

**C3. 脏矩形重绘**
- 现：每 tick `self.update()` 重绘整个全屏窗口（1440p/4K 数百万像素）。
- 改：记录当前帧 + 上一帧的屏幕包围盒，`self.update(prev_rect.united(cur_rect))` 只重绘脏区；`paintEvent` 用 `event.rect()` 裁剪。半透明窗口下脏区会被合成为透明再绘新帧。大幅降 CPU/耗电。

**作用域说明**：多屏支持（猫只在 `primaryScreen()` 走）**不在本次范围**，保持 YAGNI；本次聚焦顺滑与时间线。

## 4. 文件改动清单

| 文件 | 动作 | 责任 |
|---|---|---|
| `scripts/extract_cat_frames.py` | 改 | 换源、相位窗、`WALK_FPS=30`、`IDLE_FPS=15`、`SCALE=0.25` |
| `assets/cat_anim/*`（manifest + PNG） | 重生成 | 跑脚本产出新 sprite |
| `cat_anim_window.py` | 改 | B1–B4（ping-pong、握手、弹性退出、淡出）+ C1–C3（PreciseTimer/time-based、预缩放缓存、脏矩形） |
| `tests/test_cat_anim_window.py` | 改 | 更新状态机测试，新增 ping-pong/握手/time-based/淡出用例 |

> `.gitignore` 无需改：新源 `.mp4` 已被 `assets/*.mp4` 规则忽略（dev 输入不入库/不打包）；sprite PNG（现 206 张 + manifest）是被追踪的，重生成后照常提交并打包。

`main.py` 接线（`countdown_finished → start_walk_out`）**不变**——`start_walk_out` 语义从"立即转场"变为"置退出位"，对调用方透明。

## 5. 测试与验证

**单元测试（pytest-qt，`tests/test_cat_anim_window.py`）**
- ping-pong 游标产出三角波序列（`0..n-1..0`），不越界
- time-based 选帧：给定 `elapsed_ms` 与 fps，一次性相位与 IDLE 三角波都返回正确 idx
- 退出握手：IDLE 中置 `_exit_requested` → 正向播到坐直端 → 才进 WALK_OUT
- 退出握手：WALK_IN 中置 `_exit_requested` → 经 IDLE 单程扫到坐直端 → WALK_OUT（不从趴姿直跳）
- WALK_OUT 完成 → 触发淡出 → 淡出结束 emit `finished` 一次
- 素材缺失（manifest 不存在）→ 立即 emit `finished`（现有兜底不回归）

**素材脚本验证**
- 跑 `python scripts/extract_cat_frames.py`：输出帧数 > 0；canvas ≈ 960×540；`walk_fps==30`、`idle_fps==15`；总 sprite 体积打印 < ~13MB

**人工冒烟（Windows 实机）**
- 设 `interval_minutes=0.1`、`rest_duration_seconds=20` → 6s 后过场触发
- 目检：① 入场无僵帧、横移顺滑无台阶；② 中间趴卧 ping-pong 无跳帧、自然；③ 坐直起身无跳帧；④ 收尾淡出柔和；⑤ 全程无一顿一顿
- 改 `rest_duration_seconds=40` → 猫不提前走光，IDLE 多 ping-pong 几轮后才起身
- 任务管理器观察过场期间 CPU（脏矩形 + 预缩放缓存应明显低于全屏重绘 + 每帧重缩放的基线）

## 6. 不在本次范围

- 多屏支持（猫在所有屏幕走）
- 休息卡片（`cat_window.py`）的任何改动
- 帧插值/运动模糊（已用 30fps 真实帧，不需要伪造）
- 开机自启、全屏勿扰、卡片引导/稍后等其他体验项（早先菜单里的选项，留作后续）

## 7. 实施顺序建议

A（素材）→ B（状态机）→ C（引擎）。A 先行因为 B 的测试需要新 manifest 的相位结构。B 与 C 同改 `cat_anim_window.py`，但 B 是逻辑/状态、C 是渲染/计时，关注点分离，可分别 TDD、分别提交。

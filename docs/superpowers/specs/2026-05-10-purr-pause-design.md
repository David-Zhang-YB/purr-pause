# Purr Pause — 20-20-20 护眼提醒应用 设计规格

**日期：** 2026-05-10  
**状态：** 已批准

---

## 背景与目标

遵循 20-20-20 护眼法则：每工作 20 分钟，看向 20 英尺（约 6 米）以外的地方持续 20 秒，以缓解视疲劳。

Purr Pause 是一款运行于 Windows 桌面的提醒工具。灵感来自 Chrome 插件 Cat Gatekeeper，以弹出可爱小猫动画的方式提醒用户休息，兼顾趣味性与实用性。

---

## 技术选型

- **语言：** Python 3.11+
- **UI 框架：** PyQt6
- **动画：** QMovie（GIF 格式）
- **版本控制：** Git（后续推送至 GitHub）

---

## 项目结构

```
purr_pause/
├── .git/
├── .gitignore              # 排除 __pycache__、*.pyc、config.json
├── requirements.txt        # PyQt6 及其依赖版本
├── main.py                 # 入口：初始化 QApplication + 系统托盘
├── timer.py                # QTimer 封装，发出 rest_due 信号
├── cat_window.py           # 弹窗：GIF 动画 + 20 秒倒计时 + 关闭逻辑
├── tray.py                 # 系统托盘图标 + 右键菜单
├── settings.py             # 设置对话框 + config.json 读写
├── config.default.json     # 默认配置模板（纳入版本控制）
├── config.json             # 用户本地配置（不提交）
└── assets/
    └── cat.gif             # 默认猫咪 GIF 动画
```

---

## 核心模块设计

### timer.py — 计时器

- 封装 `QTimer`，按 `interval_minutes` 循环触发
- 对外暴露信号：`rest_due = pyqtSignal()`
- 支持 `start()` / `pause()` / `resume()` / `reset(interval)` 方法
- 修改间隔后立即重置当前计时

### cat_window.py — 弹窗

- 窗口标志：`Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`
- 不抢夺焦点：`Qt.WindowDoesNotAcceptFocus`（不打断用户正在进行的操作）
- 居中显示：基于主屏幕分辨率动态计算位置
- 内容布局：
  - 猫咪 GIF（`QLabel` + `QMovie`）
  - 提示文字："看向 20 英尺外 · 还剩 X 秒"
  - 右上角 ✕ 关闭按钮
- 20 秒倒计时由 `QTimer`（1 秒间隔）驱动，更新标签文字
- 倒计时归零后：`QPropertyAnimation` 对 `windowOpacity` 做淡出（1.0 → 0.0，约 0.5 秒）→ 关闭
- 手动关闭（点 ✕ 或点击窗口外部）立即关闭，不影响下一轮计时

### tray.py — 系统托盘

- 使用 `QSystemTrayIcon`
- 图标：从 emoji 渲染为 QPixmap（无需额外图片）
- 右键菜单：
  - ⏸ 暂停 / ▶ 继续（状态切换）
  - ⚙ 设置
  - ℹ 关于
  - ✕ 退出

### settings.py — 设置

- `QDialog`，包含：
  - SpinBox：提醒间隔（5–60 分钟，默认 20，步长 5）
- 读写 `config.json`（不存在时从 `config.default.json` 复制）
- 保存后通过信号通知 `timer.py` 重置间隔
- **扩展接口（MVP 不实现，但预留）：**
  - `cat_image_path` 字段（空字符串表示使用内置 GIF）

### config.default.json

```json
{
  "interval_minutes": 20,
  "cat_image_path": ""
}
```

---

## 运行流程

```
启动
  └─ 读取 config.json（不存在则复制 default）
  └─ 初始化系统托盘
  └─ 启动计时器（interval_minutes）
  └─ 进入事件循环（主窗口不显示）

计时器触发 rest_due
  └─ 创建并显示 CatWindow（居中、置顶）
  └─ 开始 20 秒倒计时

倒计时归零
  └─ QPropertyAnimation 淡出窗口（0.5 秒）
  └─ 关闭 CatWindow
  └─ 计时器自动开始下一轮

用户操作（任意时刻）
  ├─ 手动关闭弹窗 → 立即关闭，计时器继续
  ├─ 托盘暂停 → 计时器暂停，弹窗不再出现
  ├─ 托盘设置 → 打开设置对话框，保存后重置计时器
  └─ 托盘退出 → 退出 QApplication
```

---

## .gitignore 关键条目

```
__pycache__/
*.pyc
config.json
*.egg-info/
dist/
build/
```

---

## 验证方案

1. **单元级**：将 `interval_minutes` 改为 0.1 分钟（6 秒）验证计时器触发和弹窗弹出
2. **弹窗行为**：确认居中显示、不抢焦点、✕ 关闭正常、倒计时文字实时更新
3. **自动关闭**：等待 20 秒确认动画播放完毕后窗口消失
4. **托盘菜单**：逐一测试暂停/继续/设置/退出功能
5. **设置持久化**：修改间隔 → 退出 → 重启 → 确认间隔恢复为修改后的值
6. **Git 状态**：确认 `config.json` 不被跟踪，`config.default.json` 已提交

---

## 未来扩展（MVP 之后）

- 用户上传自定义猫咪 GIF（通过 `cat_image_path` 字段）
- 完整设置面板（休息时长、声音提示、主题）
- 开机自启动（写入 Windows 注册表）
- 统计面板（今日休息次数）

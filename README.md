# Purr Pause 🐱

遵循 20-20-20 护眼法则的 Windows 桌面提醒工具。
每工作 20 分钟，小猫会在屏幕中央弹出，提醒您看向 20 英尺外休息 20 秒。

## 快速开始

```bash
pip install -r requirements.txt
python scripts/make_placeholder_cat.py   # 生成占位猫咪 GIF（仅首次需要）
python main.py
```

## 开发

```bash
pytest -v
```

## 自定义猫咪

将您喜欢的猫咪 GIF 替换 `assets/cat.gif` 即可。

## 项目结构

| 文件 | 职责 |
|------|------|
| `main.py` | 入口：初始化 QApplication、托盘、定时器 |
| `timer.py` | RestTimer — 20 分钟循环计时器 |
| `cat_window.py` | CatWindow — 无边框弹窗，GIF + 倒计时 |
| `tray.py` | TrayIcon — 系统托盘菜单 |
| `settings.py` | 配置读写 + 设置对话框 |

## 未来计划

- 用户可上传自定义猫咪 GIF（`cat_image_path` 字段已预留）
- 完整设置面板（休息时长、声音、主题）
- 开机自启动

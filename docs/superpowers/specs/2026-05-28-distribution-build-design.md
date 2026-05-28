# Purr Pause — 试用版分发构建设计文档

**日期：** 2026-05-28
**状态：** 待批准
**影响文件：** `paths.py`（新增）、`version.py`（新增）、`scripts/build_dist.py`（新增）、`settings.py`、`cat_window.py`、`main.py`、`tray.py`、`.gitignore`

---

## 背景

当前项目功能已达到可让亲朋好友试用的成熟度。所有人都装 Python + PyQt6 不现实——需要把项目打包为单个独立可执行文件（.exe），让 Windows 用户双击即可运行、无任何额外依赖。

本次构建**不是正式发布**：开发仍在持续，本版本仅用于私下试用与早期反馈收集。因此跳过代码签名、自动更新、安装包等正式发布配套。

---

## 目标

- 产出一个 `PurrPause.exe`（单文件、约 80–120MB），可直接发送给朋友
- 用户设置在程序版本更新后**仍能保留**（不存在临时目录被清理的问题）
- .exe 在桌面/任务栏/Alt+Tab 中显示**项目品牌的猫咪图标**而非 Python 默认
- 朋友通过托盘 tooltip 可识别**当前版本号**，便于后续推送新版时区分
- 构建过程可复用：`python scripts/build_dist.py` 一行命令重打包

---

## 不改动的内容

以下所有功能与视觉保持不变：

- 托盘菜单视觉（含猫咪 header + 文本菜单项 + amber 焦点色）
- 设置窗口布局（QGridLayout 表单 + amber 主按钮）
- 呼吸光带边框、入场弹簧动画
- 倒计时逻辑、`RestTimer` 实现
- 既有测试套件
- `config.default.json` 的默认值结构

---

## 关键决策（已与用户对齐）

| 决策 | 选择 | 理由 |
|---|---|---|
| 打包工具 | **PyInstaller** | PyQt6 生态最成熟 |
| 分发形态 | **`--onefile --windowed`**（单 .exe，无控制台） | 最简单的发送/接收体验 |
| 应用图标 | **从 `assets/Mascot Cat Black.png` 生成多尺寸 .ico** | 朋友看到项目品牌而非默认图标 |
| 版本标识 | **`version.py` + 托盘 tooltip 显示** | 朋友能区分新旧版本 |
| 代码签名 | **跳过** | 证书 ~\$200/年，私下试用阶段不值得 |
| 安装包/MSI | **不做** | 用户体验上一步双击即可，安装包是冗余 |
| 自动更新 | **不做** | 早期试用，新版手动重发 |

---

## 技术设计

### 1. 路径解析模块（新增 `paths.py`）

PyInstaller `--onefile` 在每次启动时把 .exe 解压到 `%TEMP%\_MEIxxxxx`，`__file__` 指向那里。该目录在进程退出后被清理。因此需要区分两类路径：

```python
import os
import sys
from pathlib import Path


def resource_path(rel: str) -> Path:
    """Resolve a bundled read-only resource (works in source mode and PyInstaller frozen mode)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / rel


def user_data_dir() -> Path:
    """%APPDATA%\\PurrPause when frozen, project root when running from source."""
    if getattr(sys, "frozen", False):
        root = Path(os.environ.get("APPDATA", Path.home()))
        d = root / "PurrPause"
        d.mkdir(parents=True, exist_ok=True)
        return d
    return Path(__file__).parent
```

- `resource_path("assets/foo.png")` → 源码模式返回 `<project>/assets/foo.png`；冻结后返回 `<_MEIPASS>/assets/foo.png`
- `user_data_dir()` → 源码模式返回项目根（开发体验不变）；冻结后返回 `C:\Users\<name>\AppData\Roaming\PurrPause\`，并保证目录已存在

### 2. 配置持久化（`settings.py`）

```python
# 改前
BASE_DIR = Path(__file__).parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.default.json"
CONFIG_PATH = BASE_DIR / "config.json"

# 改后
from paths import resource_path, user_data_dir
DEFAULT_CONFIG_PATH = resource_path("config.default.json")
CONFIG_PATH = user_data_dir() / "config.json"
```

`load_config()` 与 `save_config()` 函数体不变——已有的"首次启动从 default 复制"逻辑能正确处理新路径。

### 3. 资源路径迁移（`cat_window.py`、`main.py`）

替换所有 `ASSETS_DIR / "..."` 为 `resource_path("assets/...")`：

- [cat_window.py:17](cat_window.py#L17) 删 `ASSETS_DIR` 常量
- [cat_window.py:55](cat_window.py#L55) 字体路径 → `resource_path("assets/fonts/NotoSansSC[wght].ttf")`
- [cat_window.py:210](cat_window.py#L210) `_DEFAULT_STATIC` → `resource_path("assets/Mascot Cat Black.png")`
- [cat_window.py:226](cat_window.py#L226) `cat.gif` fallback → `resource_path("assets/cat.gif")`
- [main.py:12-13](main.py#L12-L13) 删 `_ASSET_DIR`，`_ANIM_VIDEO = resource_path("assets/American Shorthair Cat Transparent.mp4")`

### 4. 死代码清理（`tray.py`）

`tray.py:10` 的 `_ASSET_DIR = Path(__file__).parent / "assets"` 在前几轮重构后已无引用，直接删除。

### 5. 版本标识（新增 `version.py`）

```python
VERSION = "0.1.0-trial"
```

在 [tray.py](tray.py) 顶部 `from version import VERSION`，把当前的 `self.setToolTip("Purr Pause")` 改为 `self.setToolTip(f"Purr Pause v{VERSION}")`。

### 6. 应用图标生成

构建脚本运行时用 Pillow 把 `assets/Mascot Cat Black.png` 转换为含 16/32/48/64/128/256 尺寸的 `assets/icon.ico`：

```python
from PIL import Image
img = Image.open("assets/Mascot Cat Black.png").convert("RGBA")
img.save("assets/icon.ico", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
```

`icon.ico` 加入 `.gitignore`（构建生成物）。

### 7. 构建脚本（新增 `scripts/build_dist.py`）

```python
"""Build PurrPause.exe via PyInstaller. Run: python scripts/build_dist.py"""
import subprocess
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).parent.parent

def make_icon() -> Path:
    src = ROOT / "assets" / "Mascot Cat Black.png"
    dst = ROOT / "assets" / "icon.ico"
    Image.open(src).convert("RGBA").save(
        dst, sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
    )
    return dst

def main() -> None:
    icon = make_icon()
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--windowed", "--clean", "--noconfirm",
        "--name", "PurrPause",
        f"--icon={icon}",
        "--add-data", f"{ROOT/'config.default.json'};.",
        "--add-data", f"{ROOT/'assets'/'American Shorthair Cat Transparent.mp4'};assets",
        "--add-data", f"{ROOT/'assets'/'Mascot Cat Black.png'};assets",
        "--add-data", f"{ROOT/'assets'/'Mascot Cat White.png'};assets",
        "--add-data", f"{ROOT/'assets'/'cat.gif'};assets",
        "--add-data", f"{ROOT/'assets'/'fonts'/'NotoSansSC[wght].ttf'};assets/fonts",
        str(ROOT / "main.py"),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)
    exe = ROOT / "dist" / "PurrPause.exe"
    size_mb = exe.stat().st_size / (1024*1024)
    print(f"\n✓ Built: {exe}  ({size_mb:.1f} MB)")

if __name__ == "__main__":
    main()
```

`--add-data "SRC;DEST"` 的 Windows 分隔符是 `;`（Linux/Mac 是 `:`）。`DEST` 是相对目标路径——`.` 表示打包到根、`assets` 表示打包到 `assets/` 子目录。

### 8. `.gitignore` 追加

```
PurrPause.spec
assets/icon.ico
```

`PurrPause.spec` 是 PyInstaller 自动生成的描述文件，每次构建会重新生成，不应入仓库。`icon.ico` 同样是构建产物。

---

## 体积与启动时间预期

- **.exe 体积**：80–120MB。PyQt6 本身约 80MB，Qt 插件（platforms、imageformats、styles）+ 字体 + MP4 视频是不可压缩的体量。
- **首次启动延迟**：约 2–4 秒——`--onefile` 需要先把 .exe 解压到 `%TEMP%\_MEIxxxxx` 再启动 Python 解释器。后续启动同样延迟（每次都解压）。
- **运行时内存**：与源码模式相当（~80-150MB），不会因为打包而显著上升。

如果朋友反馈启动太慢是主要问题，未来版本可切换到 `--onedir`（牺牲发送便利性换取启动速度）。

---

## 已知风险

| 风险 | 触发条件 | 缓解 |
|---|---|---|
| **SmartScreen 蓝屏警告** | 首次运行未签名 .exe | 在分发说明里告知"点更多信息→仍要运行" |
| **中文用户名路径 Qt 字体加载失败** | 朋友的 Windows 用户名含中文，`%TEMP%` 路径不是 ASCII | cat_window.py:52 已有 fallback 到 Microsoft YaHei |
| **杀毒软件误报** | 某些杀软对 PyInstaller 单文件 .exe 敏感 | 试用阶段接受，如果普遍误报再切 `--onedir` |
| **MP4 视频解码失败** | 朋友机器缺 H.264 编解码器（罕见） | 视频功能在 main.py 当前被注释屏蔽，本版本不阻塞 |

---

## 验证步骤

构建脚本完成后，按顺序验证：

1. **构建成功**：`python scripts/build_dist.py` 退出码 0，输出 `dist/PurrPause.exe`，体积在 80–120MB 区间
2. **冷启动**：把 .exe 复制到桌面，双击 → 托盘出现猫咪图标 → 无控制台窗口、无错误弹窗
3. **托盘菜单**：右键托盘 → 菜单显示新视觉（猫咪 header、文字菜单项）；hover 托盘图标显示 `Purr Pause v0.1.0-trial`
4. **设置持久化**（最关键，验证 §2）：打开设置 → 改提醒间隔为 5 分钟 → 保存 → 退出 .exe → 重启 .exe → 打开设置 → 仍是 5 分钟
5. **配置文件位置**：`%APPDATA%\PurrPause\config.json` 存在且包含修改后的值
6. **资源加载**：等待提醒触发或人工触发休息卡片 → 猫咪图片、字体、倒计时均正常显示（验证 §3 资源路径迁移）
7. **干净退出**：菜单"退出" → 进程从任务管理器消失 → 临时 `%TEMP%\_MEIxxxxx` 被清理

---

## 待实现项清单（驱动 writing-plans 阶段）

按依赖顺序排列：

1. 新增 `paths.py`（独立、无依赖）
2. 新增 `version.py`（独立、无依赖）
3. 改 `settings.py`：导入 paths，切换 DEFAULT/CONFIG 路径
4. 改 `cat_window.py`：导入 resource_path，迁移 4 处 ASSETS_DIR 引用
5. 改 `main.py`：迁移 `_ANIM_VIDEO`
6. 改 `tray.py`：删死代码 `_ASSET_DIR`、加 version tooltip
7. 把 `PyInstaller>=6.0.0` 与 `Pillow>=10.0.0`（已有）加到 `requirements.txt`
8. 写 `scripts/build_dist.py`
9. 追加 `.gitignore`：`PurrPause.spec`、`assets/icon.ico`
10. **运行源码模式**（`python main.py`）回归——确保路径改动没破坏开发环境
11. **运行打包构建**（`python scripts/build_dist.py`），按上面验证步骤逐项确认

---

## 不在本次范围内

- 代码签名（EV / OV 证书）
- 自动更新机制
- 安装包 / 卸载程序
- macOS / Linux 构建
- 发布到应用商店
- 性能优化（启动速度、体积压缩）

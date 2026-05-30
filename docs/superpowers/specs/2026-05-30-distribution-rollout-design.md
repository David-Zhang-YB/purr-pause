# Purr Pause 分发框架公开发布路线 — 设计 spec

**日期**：2026-05-30
**作者**：Yubo Zhang（brainstorm w/ Claude）
**状态**：approved, ready for plan
**版本范围**：v0.1.0（首次公开发布）、v0.2.0（应用内更新检查）

---

## 1. 背景与动机

Purr Pause 的 MVP 已完成。在最近一轮工作（commit `4a4e2ac` 及之前几个 commit）中，团队把"猫咪走过屏幕"的休息期间动画从 MP4 + chroma-key 运行时管线重做成了 PNG sprite + QTimer 状态机，[dist/PurrPause.exe](../../../dist/PurrPause.exe) 63 MB 单文件可用。

下一步的目标是**把 Purr Pause 从"只能 IM 转发给朋友的 .exe"升级成"任何人能在公开渠道发现、下载、安装并长期使用的产品"**。

主要驱动因素：

- 您（Yubo）已经明确产品策略是**公开 + 主动推广**（小红书 / 知乎 / 贴吧 为主，Reddit/HN 为远期可能），覆盖 Windows + macOS 用户
- 当前没有任何外部触达通道：仓库纯本地、没有 LICENSE、README 过时、没有 macOS 构建、没有更新提示
- 这些短板会在公开首日就劝退普通用户：SmartScreen 警告 / Gatekeeper 警告 / 看不到版本号 / 没有"为什么用这个"的解释

## 2. 关键决策

本 spec 的所有决策都在 brainstorm 阶段与用户当面对齐（见 本次 brainstorm 的 plan file（在用户 home 目录 `~/.claude/plans/ui-declarative-puddle.md`） 的第 2 节）。

| 维度 | 决策 | 理由 |
|---|---|---|
| **受众范围** | 公开 + 主动推广 | 用户的产品愿景 |
| **平台覆盖** | Windows + macOS | Linux 受众极小，工作量翻倍不值；macOS 不能跳过（很多潜在用户用 Mac） |
| **仓库可见性** | 完全公开 | 公开推广所必需，能接受 Issues 反馈 |
| **系统警告对策** | 文档说明绕过，不买证书 | 起步阶段省 $99-300/年；用户接受会损失一部分信任度低的用户作为代价 |
| **更新机制** | 启动时拉 GitHub Releases API，提示手动下载 | 完整自动更新对 PyInstaller --onefile 自替换太复杂；纯靠用户主动查 release 又抓不住推广来的用户 |
| **数据收集** | 零遥测，仅 GitHub Issues + 邮箱 | 隐私友好；中文社区对静默上报敏感 |
| **门面粒度** | 精致 README + 演示 GIF + 截图 | 不另建落地页，GitHub Markdown 渲染已足够 v0.x 阶段 |
| **README 语言** | 中文 + 英文双版 | 为未来去海外社区做准备；增加约 30% 工作量但避免日后改造 |
| **资源授权** | SeedDance 2.0 生成，README/ASSETS 标明出处 | 用户自述版权归属 SeedDance 2.0 ToS 待用户独立核对 |
| **总体节奏** | 三阶段分次发布 | 早早拿到能见人的 v0.1.0；每阶段独立验证；v0.2 的更新检查器需要 v0.1 作为对照 |

## 3. 架构

### 3.1 三阶段切分

```
┌──────────────────────────────────────────────────────────────────┐
│  Phase 1: 基础设施（不动应用代码）                                  │
│  ↓ CI 跑通、能产出双平台二进制                                       │
│                                                                  │
│  Phase 2: 门面 + v0.1.0 首发                                      │
│  ↓ README/screenshots/demo.gif → git tag v0.1.0 → CI 自动发布      │
│                                                                  │
│  Phase 3: v0.2.0 应用内更新检查                                    │
│  ↓ update_checker.py → 设置开关 → git tag v0.2.0                  │
└──────────────────────────────────────────────────────────────────┘
```

**为什么不并行**：Phase 2 的"完整下载路径回归"测试依赖 Phase 1 的 CI 二进制；Phase 3 的"新版本通知"测试需要 v0.1 release 已经存在作为对照。强行并行会让所有验证步骤都被基础设施缺失阻塞。

### 3.2 涉及组件总览

| 组件 | 类型 | 阶段 |
|---|---|---|
| `.github/workflows/release.yml` | CI 编排 | Phase 1 |
| `scripts/build_dist.py` | 跨平台构建脚本 | Phase 1 |
| `LICENSE`、`ASSETS.md`、`CHANGELOG.md` | 项目元数据 | Phase 1/2 |
| `README.md` / `README.en.md` | 用户首面文档 | Phase 2 |
| `scripts/make_demo_gif.py` | 一次性 GIF 生成器 | Phase 2 |
| `docs/screenshots/` + `docs/demo.gif` | README 视觉资源 | Phase 2 |
| `update_checker.py` | 运行时更新检查器 | Phase 3 |
| `main.py` / `settings.py` / `tray.py` 的集成 | 应用层接入 | Phase 3 |

## 4. 各阶段详细设计

### Phase 1：基础设施

**目标**：让 `git tag vX.Y.Z && git push --tags` 能自动产出 Windows .exe + macOS .dmg，挂到 GitHub Releases 页。

#### 4.1.1 CI workflow（新建 `.github/workflows/release.yml`）

- 触发：`push` tag 匹配 `v*.*.*`
- 两个并行 job：
  - `build-windows`（runs-on: windows-latest）
  - `build-macos`（runs-on: macos-latest）
- 每个 job 流程：
  1. checkout
  2. setup python 3.11
  3. install deps（`pip install -r requirements.txt`）
  4. **verify**：用 `GITHUB_REF_NAME` 取出 tag 名（如 `v0.1.0`），strip 前导 `v`，与 `version.VERSION` 比对；不一致则 fail-fast。注意 Windows job 用 PowerShell、macOS job 用 bash，verify step 需要 `shell: bash` 显式声明以保证语法一致
  5. `python scripts/build_dist.py`
  6. upload artifact（`PurrPause-{VERSION}-{platform}.{ext}`）
- 聚合 job `release`：`needs: [build-windows, build-macos]`，用 `softprops/action-gh-release@v1` 把两个 artifact 挂到同一个 release，body 走 GitHub 自动生成的 release notes

#### 4.1.2 跨平台 build 脚本（修改 `scripts/build_dist.py`）

当前脚本写死 Windows，需要改造成 platform-aware：

- 顶部加 `import platform; IS_MAC = sys.platform == "darwin"`
- `--add-data` 分隔符按平台切换（Win `;`，Mac `:`）
- 输出文件命名：`PurrPause-{VERSION}-{windows|macos}.{exe|dmg}`
- Windows 分支：保留现有逻辑（已 verified working）
- macOS 分支：
  - PyInstaller 调用改成 `--windowed` 产 `.app`
  - 新增 `make_icns()`：用 macOS 系统 "Apple Color Emoji" 字体 + Pillow `embedded_color=True` 渲染 🐱 → 多 size `.icns`
  - PyInstaller 完成后调用 `dmgbuild` 把 `.app` 包成 `.dmg`
  - `dmgbuild` 是 build-only 依赖（运行时不需要），由 CI 的 macOS job 在跑 `build_dist.py` 前 `pip install dmgbuild` 直接装；**不进 `requirements.txt`**

#### 4.1.3 LICENSE 与 .gitignore

- 新增 `LICENSE`：MIT 标准模板，`Copyright (c) 2026 Yubo Zhang`
- `.gitignore` 补：`dist/`、`build/`、`.DS_Store`、`assets/icon.icns`、`docs/demo.gif`

#### 4.1.4 版本切换

- `version.py`：`0.1.0-trial` → `0.1.0`

#### 4.1.5 GitHub 仓库建立（用户在网页执行）

- 网页新建 public repo `purr-pause`
- 本地：`git branch -M main && git remote add origin <url> && git push -u origin main`

### Phase 2：门面 + v0.1.0 首发

**目标**：第一次让 Purr Pause 见人。

#### 4.2.1 README.md 重写

Hero 区域：
- 项目名 + 🐱 logo（用已有 [assets/icon.ico](../../../assets/icon.ico) 渲染到 80×80）
- 一行 tagline："每 20 分钟，让一只猫提醒你抬头看远方"
- 双下载按钮 —— 直链 `https://github.com/<owner>/purr-pause/releases/latest/download/PurrPause-0.1.0-windows.exe` 等
- Badges：version、license、platform

主体分节：
1. **主截图** — `docs/screenshots/rest-notification.png`，最具传达力的一张
2. **演示 GIF** — `docs/demo.gif`，3-5 秒展示猫咪 walk-in → idle → walk-out
3. **为什么需要它** — 20-20-20 法则 + 软提醒理念
4. **功能列表**
5. **下载与安装** — Windows + macOS 各自步骤，含 SmartScreen / Gatekeeper 截图指引
6. **自定义** — `cat_image_path` 替换 + interval / duration 设置
7. **隐私声明** — "v0.1.0 应用零网络请求；v0.2.0 起每次启动会向 api.github.com 发起一次 HTTPS 请求检查更新；不发送任何其他数据"
8. **反馈** — GitHub Issues + 邮箱
9. **开发** — `pip install -r requirements.txt && python main.py && pytest`
10. **路线图** — v0.2 更新检查、v0.3 多猫咪皮肤、持续优化抠像
11. **致谢** — "猫咪视觉资源由 SeedDance 2.0 生成"
12. **License** — 链接 LICENSE 和 ASSETS.md

#### 4.2.2 README.en.md

与中文版结构对齐，叙述更简练（西方用户对长篇产品介绍耐心更低）。

#### 4.2.3 ASSETS.md

逐资源列出来源 / 许可：

```markdown
# Asset Provenance

| Path | Source | License |
|---|---|---|
| assets/American Shorthair Cat Transparent.mp4 | SeedDance 2.0 generation by Yubo Zhang | per SeedDance ToS (dev-only input, not shipped) |
| assets/cat_anim/*.png | Extracted from above MP4 | same as source |
| assets/Mascot Cat *.png | TBD by Yubo | TBD |
| assets/cat.gif | TBD by Yubo | TBD |
| assets/fonts/NotoSansSC[wght].ttf | Google Noto | SIL Open Font License 1.1 |
```

#### 4.2.4 CHANGELOG.md（Keep-a-Changelog 格式）

```markdown
# Changelog

## [0.1.0] - 2026-XX-XX

### Added
- First public release
- 20-20-20 rest timer with cat companion
- Windows .exe and macOS .dmg distributions
- System tray menu with settings dialog
- Configurable interval and rest duration
- Cat-walks-across-screen animation during rest break
```

#### 4.2.5 演示 GIF 生成（新建 `scripts/make_demo_gif.py`）

一次性脚本，dev 运行后 commit 产物到仓库：

- 读 `assets/cat_anim/manifest.json`
- 取 walk_in 全部帧 + idle 抽 20 帧 + walk_out 全部帧
- 用 Pillow `Image.save(format="GIF", save_all=True, append_images=...)` 拼成
- 目标：`docs/demo.gif`，≤ 2 MB（GitHub README 内嵌渲染流畅的上限）
- 帧间延迟按 manifest 的 `walk_fps` / `idle_fps` 推导

#### 4.2.6 截图

`docs/screenshots/` 4 张（实机抓图，PNG）：

1. `tray-menu.png` — 托盘菜单展开，显示猫咪图标和菜单项
2. `settings-window.png` — 设置窗口，spinbox + 保存按钮
3. `rest-notification.png` — 休息提醒通知卡 + 倒计时
4. `smartscreen-bypass.png` — SmartScreen 警告 + "更多信息 → 仍要运行" 红圈圈出

#### 4.2.7 发布

- `git tag v0.1.0 && git push origin v0.1.0`
- CI 完成后在 GitHub Releases 页面手动 polish release notes

### Phase 3：v0.2.0 应用内更新检查

**目标**：让推广来的用户能被动收到新版提醒，不需要回访仓库。

#### 4.3.1 `update_checker.py`（新建）

接口：

```python
class UpdateChecker(QObject):
    update_available = pyqtSignal(str, str)   # (new_version, release_url)
    no_update = pyqtSignal()
    check_failed = pyqtSignal(str)            # for debug logging only

    def __init__(self, current_version: str, github_repo: str): ...
    def check_async(self) -> None: ...
```

实现要点：

- 用 `QNetworkAccessManager` 异步 GET `https://api.github.com/repos/<owner>/<repo>/releases/latest`
- 解析 `tag_name`（如 `v0.2.0`）→ strip `v` 前缀 → split `.` 后 `tuple(map(int, ...))` 比较（避免引入 `packaging` 额外依赖）
- **节流 7 天**：状态持久化到 `user_data_dir() / "update_state.json"`，结构 `{"last_check_at": ISO_ts, "dismissed_version": "0.2.0" | null}`
- **静默失败**：offline、限流（403）、JSON 解析错误等任何异常仅 `emit check_failed`，不打扰用户、不写错误日志到用户能看到的地方
- **Dismiss 持久化**：用户点通知的"暂时不看"按钮（或简单地关掉通知） → 写 `dismissed_version` → 同版本再来不提醒；远端更到更新版本（语义大于 dismissed）重新提醒

#### 4.3.2 应用集成

- [main.py](../../../main.py) 在 `main()` 末尾接入 5 秒延迟启动检查（不阻塞应用启动）
- [settings.py](../../../settings.py)：`DEFAULT_CONFIG` 加 `auto_check_updates: true`；设置对话框加一个 checkbox
- [tray.py](../../../tray.py)：菜单加 "**检查更新**" 项，主动触发 `checker.check_async()`
- 通知 UI 走已经在使用的 `QSystemTrayIcon.showMessage()`（Windows 系统通知 / macOS 通知中心）；点击 → `QDesktopServices.openUrl(release_url)`

#### 4.3.3 测试

新建 `tests/test_update_checker.py`，pytest-qt + mock `QNetworkAccessManager`：

- 当前 0.1.0、远端 0.2.0 → emit `update_available` 一次
- 当前 0.2.0、远端 0.2.0 → emit `no_update`
- 远端 404 / 网络错误 → emit `check_failed`，不抛
- 7 天节流：7 天内连续启动只发一次请求
- dismiss 0.2.0 后同版本不提醒；远端 0.3.0 时重新提醒

#### 4.3.4 发布

- `version.py` bump 到 `0.2.0`
- CHANGELOG 加 0.2.0 条目
- `git tag v0.2.0 && git push --tags`

## 5. 验证

每个阶段独立验证，按顺序进行（不跳级、不并行）。完整验证列表见 本次 brainstorm 的 plan file（在用户 home 目录 `~/.claude/plans/ui-declarative-puddle.md`） 第 5 节。

## 6. 不在本次范围内

- 代码签名（Windows OV/EV 证书 + Apple Developer ID）
- 完整自动更新（自替换 .exe）
- 遥测 / 崩溃报告 / 使用统计
- 多语言 UI（应用本身的中英文切换；本次只双语 README）
- Linux 构建（AppImage / .deb）
- GitHub Pages 落地页
- 持续优化猫咪抠像（另起独立工作线）

## 7. 用户需独立完成的事项

Claude 无法代办：

- 在 GitHub 网页新建 `purr-pause` public repo（需要 GitHub 账号操作）
- 核对 SeedDance 2.0 ToS 关于"生成物商用 + 公开分发"条款
- 准备社区推广文案
- 准备 macOS 测试环境（手头无 Mac 的话，需要协调朋友帮跑首发 .dmg 验证）
- 决定首次"按发布按钮"的时机

## 8. 后续步骤

本 spec approved 后：

1. 用 `superpowers:writing-plans` 把 Phase 1 拆成 ~7 个独立任务的 implementation plan，落到 `docs/superpowers/plans/2026-05-30-phase1-infrastructure.md`
2. 执行 Phase 1，commit + 验证
3. 重复 1-2 for Phase 2、Phase 3

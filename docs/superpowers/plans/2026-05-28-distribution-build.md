# Distribution Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package Purr Pause as a single Windows .exe (PyInstaller `--onefile`) suitable for sending to friends/family for trial, with user settings persisting across launches via `%APPDATA%`.

**Architecture:** Introduce two tiny modules (`paths.py`, `version.py`) that abstract the "read-only bundled resource" vs "writable user data" path split. Migrate all existing `Path(__file__).parent / "assets"` and `BASE_DIR / "config.json"` usages to call these helpers. Add a build script (`scripts/build_dist.py`) that generates a multi-size `.ico` from `Mascot Cat Black.png` and drives PyInstaller with explicit `--add-data` for each bundled file.

**Tech Stack:** Python 3, PyQt6, PyInstaller `--onefile --windowed`, Pillow (for .ico generation), pytest + pytest-qt (existing test suite).

---

## File Inventory

**New files:**
- `paths.py` — `resource_path()` and `user_data_dir()` helpers
- `version.py` — `VERSION = "0.1.0-trial"` constant
- `tests/test_paths.py` — unit tests for the helpers
- `scripts/build_dist.py` — PyInstaller invoker

**Modified files:**
- `settings.py` — switch `DEFAULT_CONFIG_PATH` / `CONFIG_PATH` to use helpers
- `cat_window.py` — replace 4 `ASSETS_DIR` references with `resource_path()`
- `main.py` — replace `_ASSET_DIR` / `_ANIM_VIDEO` with `resource_path()`
- `tray.py` — delete dead `_ASSET_DIR`, add version to tooltip
- `requirements.txt` — add `pyinstaller>=6.0.0`
- `.gitignore` — add `PurrPause.spec` and `assets/icon.ico`

---

## Task 1: Add `paths.py` Helper Module

**Files:**
- Create: `paths.py`
- Test: `tests/test_paths.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_paths.py`:

```python
import os
import sys
from pathlib import Path
import pytest


def test_resource_path_in_source_mode_returns_project_relative_path(monkeypatch):
    """In source mode (no _MEIPASS), resource_path() resolves relative to paths.py's directory."""
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    from paths import resource_path
    result = resource_path("foo/bar.txt")
    assert result.name == "bar.txt"
    assert result.parent.name == "foo"


def test_resource_path_uses_meipass_when_frozen(monkeypatch, tmp_path):
    """When sys._MEIPASS is set (PyInstaller frozen mode), resource_path() resolves against it."""
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    from paths import resource_path
    result = resource_path("assets/cat.png")
    assert result == tmp_path / "assets" / "cat.png"


def test_user_data_dir_in_source_mode_returns_project_root(monkeypatch):
    """In source mode (sys.frozen unset), user_data_dir() returns the project directory."""
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    from paths import user_data_dir
    result = user_data_dir()
    assert (result / "main.py").exists() or result.name in {"Purr_Pause", "Purr Pause"}


def test_user_data_dir_when_frozen_uses_appdata_and_creates_dir(monkeypatch, tmp_path):
    """When frozen, user_data_dir() returns %APPDATA%\\PurrPause and ensures it exists."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from paths import user_data_dir
    result = user_data_dir()
    assert result == tmp_path / "PurrPause"
    assert result.is_dir()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```
pytest tests/test_paths.py -v
```

Expected: All 4 tests fail with `ModuleNotFoundError: No module named 'paths'`.

- [ ] **Step 3: Implement `paths.py`**

Create `paths.py`:

```python
import os
import sys
from pathlib import Path


def resource_path(rel: str) -> Path:
    """Resolve a bundled read-only resource path.

    Works in source mode (returns project_root/rel) and in PyInstaller
    --onefile frozen mode (returns _MEIPASS_temp_dir/rel).
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / rel


def user_data_dir() -> Path:
    """Return the writable user-data directory.

    Frozen mode: %APPDATA%\\PurrPause (created if missing).
    Source mode: the project root (so dev experience matches existing behavior).
    """
    if getattr(sys, "frozen", False):
        root = Path(os.environ.get("APPDATA", Path.home()))
        d = root / "PurrPause"
        d.mkdir(parents=True, exist_ok=True)
        return d
    return Path(__file__).parent
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```
pytest tests/test_paths.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```
git add paths.py tests/test_paths.py
git commit -m "feat: add paths.py for bundled-resource and user-data path resolution"
```

---

## Task 2: Add `version.py`

**Files:**
- Create: `version.py`

No test needed — a single constant module.

- [ ] **Step 1: Create `version.py`**

```python
VERSION = "0.1.0-trial"
```

- [ ] **Step 2: Verify import works**

Run:
```
python -c "from version import VERSION; print(VERSION)"
```

Expected output: `0.1.0-trial`

- [ ] **Step 3: Commit**

```
git add version.py
git commit -m "feat: add version.py with VERSION constant"
```

---

## Task 3: Migrate `settings.py` Config Paths

**Files:**
- Modify: `settings.py:5-7`
- Test: `tests/test_settings.py` (existing tests should keep passing)

- [ ] **Step 1: Run existing settings tests to capture baseline**

Run:
```
pytest tests/test_settings.py -v
```

Expected: All 7 existing tests PASS. Record the count — if any fail BEFORE migration, stop and investigate (they monkey-patch the path constants; migration shouldn't change their behavior).

- [ ] **Step 2: Edit `settings.py` lines 5-7**

Current:
```python
BASE_DIR = Path(__file__).parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.default.json"
CONFIG_PATH = BASE_DIR / "config.json"
```

Replace with:
```python
from paths import resource_path, user_data_dir

DEFAULT_CONFIG_PATH = resource_path("config.default.json")
CONFIG_PATH = user_data_dir() / "config.json"
```

Also remove the now-unused `from pathlib import Path` if it's no longer referenced elsewhere in the file. (Check the rest of `settings.py` first — if `Path` is used elsewhere, keep it.)

- [ ] **Step 3: Run existing settings tests to verify they still pass**

Run:
```
pytest tests/test_settings.py -v
```

Expected: All 7 tests PASS. The tests already use `monkeypatch.setattr(settings, "CONFIG_PATH", tmp_path / "config.json")` to redirect paths — this still works since `monkeypatch.setattr` overrides the module attribute regardless of how it was computed at import time.

- [ ] **Step 4: Smoke-test in source mode**

Run:
```
python -c "import settings; print('DEFAULT:', settings.DEFAULT_CONFIG_PATH); print('USER:', settings.CONFIG_PATH); cfg = settings.load_config(); print('OK:', cfg)"
```

Expected: prints both paths (both within the project directory in source mode), then prints the loaded config dict.

- [ ] **Step 5: Commit**

```
git add settings.py
git commit -m "refactor(settings): use paths.resource_path / user_data_dir for config paths"
```

---

## Task 4: Migrate `cat_window.py` Asset Paths

**Files:**
- Modify: `cat_window.py:17, 55, 210, 226`

- [ ] **Step 1: Run existing cat_window tests to capture baseline**

Run:
```
pytest tests/test_cat_window.py -v
```

Expected: All tests PASS. Record the count.

- [ ] **Step 2: Edit `cat_window.py`**

At the top of the file, add:
```python
from paths import resource_path
```

Remove the line:
```python
ASSETS_DIR = Path(__file__).parent / "assets"
```
(around line 17)

Update line ~55 (font loading inside `_ensure_font`):
```python
# Before
font_path = ASSETS_DIR / "fonts" / "NotoSansSC[wght].ttf"

# After
font_path = resource_path("assets/fonts/NotoSansSC[wght].ttf")
```

Update line ~210 (`_DEFAULT_STATIC`):
```python
# Before
_DEFAULT_STATIC = ASSETS_DIR / "Mascot Cat Black.png"

# After
_DEFAULT_STATIC = resource_path("assets/Mascot Cat Black.png")
```

Update line ~226 (cat.gif fallback):
```python
# Before
... else ASSETS_DIR / "cat.gif"

# After
... else resource_path("assets/cat.gif")
```

If `Path` is no longer used elsewhere in the file after these edits, remove `from pathlib import Path` too — but check the whole file first.

- [ ] **Step 3: Run cat_window tests to verify they still pass**

Run:
```
pytest tests/test_cat_window.py -v
```

Expected: All tests PASS, same count as baseline.

- [ ] **Step 4: Commit**

```
git add cat_window.py
git commit -m "refactor(cat_window): use paths.resource_path for asset references"
```

---

## Task 5: Migrate `main.py` Asset Path

**Files:**
- Modify: `main.py:12-13`

- [ ] **Step 1: Edit `main.py`**

Current lines 12-13:
```python
_ASSET_DIR  = Path(__file__).parent / "assets"
_ANIM_VIDEO = _ASSET_DIR / "American Shorthair Cat Transparent.mp4"
```

Replace with:
```python
from paths import resource_path

_ANIM_VIDEO = resource_path("assets/American Shorthair Cat Transparent.mp4")
```

Remove `from pathlib import Path` at line 2 if no longer used in the file. Check the whole file first.

- [ ] **Step 2: Smoke-test import**

Run:
```
python -c "import main; print('ANIM:', main._ANIM_VIDEO); print('exists:', main._ANIM_VIDEO.exists())"
```

Expected: prints the path and `exists: True` (the MP4 is in your local assets/).

- [ ] **Step 3: Commit**

```
git add main.py
git commit -m "refactor(main): use paths.resource_path for animation video"
```

---

## Task 6: Clean Up `tray.py` and Add Version Tooltip

**Files:**
- Modify: `tray.py`

- [ ] **Step 1: Run existing tray tests to capture baseline**

Run:
```
pytest tests/test_tray.py -v
```

Expected: All tests PASS. Record the count.

- [ ] **Step 2: Edit `tray.py`**

Delete the dead constant at line ~10:
```python
_ASSET_DIR = Path(__file__).parent / "assets"
```

Add import near other top-of-file imports:
```python
from version import VERSION
```

Find the existing tooltip line (in `TrayIcon.__init__`, currently `self.setToolTip("Purr Pause")`):
```python
# Before
self.setToolTip("Purr Pause")

# After
self.setToolTip(f"Purr Pause v{VERSION}")
```

Remove `from pathlib import Path` at line 1 if no longer used. Check the whole file.

- [ ] **Step 3: Run tray tests to verify they still pass**

Run:
```
pytest tests/test_tray.py -v
```

Expected: All tests PASS, same count as baseline. (If any test asserts the exact tooltip string `"Purr Pause"`, update it to `f"Purr Pause v{VERSION}"`.)

- [ ] **Step 4: Commit**

```
git add tray.py
git commit -m "refactor(tray): drop dead _ASSET_DIR, show version in tooltip"
```

---

## Task 7: Update `requirements.txt`

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add PyInstaller to `requirements.txt`**

Append after the existing `pytest-qt>=4.4.0` line:
```
pyinstaller>=6.0.0
```

(Pillow is already in `requirements.txt` from line 3 — no change needed there.)

- [ ] **Step 2: Install PyInstaller into the active environment**

Run:
```
pip install "pyinstaller>=6.0.0"
```

Expected: installs successfully. Verify with:
```
pyinstaller --version
```

Expected: prints a version string `6.x.x` or higher.

- [ ] **Step 3: Commit**

```
git add requirements.txt
git commit -m "chore: add pyinstaller>=6.0.0 to requirements"
```

---

## Task 8: Source-Mode Regression Check

This is a verification gate before touching the build script — confirms all path migrations work end-to-end.

- [ ] **Step 1: Run the full test suite**

Run:
```
pytest -v
```

Expected: All tests PASS. If anything fails, stop and fix before continuing.

- [ ] **Step 2: Launch the app from source**

Run:
```
python main.py
```

The app should start with no errors. In the system tray, look for the cat icon.

- [ ] **Step 3: Manual smoke test (3 minutes)**

While the app is running:
1. Hover the tray icon → tooltip shows `Purr Pause v0.1.0-trial`
2. Right-click → menu opens with the new visual (cat header, text-only items)
3. Click "设置" → settings dialog opens with the QGridLayout-aligned form
4. Change the interval to a different value → Save → close dialog
5. Close the app via tray menu "退出"
6. Run `python main.py` again
7. Open settings → confirm the changed interval was persisted (in source mode, this proves `config.json` writes to the project root and reads back correctly)

- [ ] **Step 4: (No commit — verification step only)**

Move on to Task 9. If any of the manual checks failed, fix the underlying file before proceeding.

---

## Task 9: Update `.gitignore`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append two new lines to `.gitignore`**

After the existing `scripts/_check_video.py` line, append:
```
PurrPause.spec
assets/icon.ico
```

`PurrPause.spec` is autogenerated by PyInstaller on each build. `assets/icon.ico` is generated by the build script from `Mascot Cat Black.png`.

- [ ] **Step 2: Commit**

```
git add .gitignore
git commit -m "chore: ignore PyInstaller spec file and generated icon"
```

---

## Task 10: Write the Build Script

**Files:**
- Create: `scripts/build_dist.py`

- [ ] **Step 1: Create the file**

```python
"""Build PurrPause.exe via PyInstaller.

Run: python scripts/build_dist.py

Produces: dist/PurrPause.exe (~80-120 MB, single-file Windows binary)
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent.parent


def make_icon() -> Path:
    """Generate a multi-size .ico from Mascot Cat Black.png."""
    src = ROOT / "assets" / "Mascot Cat Black.png"
    dst = ROOT / "assets" / "icon.ico"
    img = Image.open(src).convert("RGBA")
    img.save(
        dst,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return dst


def main() -> None:
    icon = make_icon()
    print(f"✓ Generated icon: {icon}")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
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
    size_mb = exe.stat().st_size / (1024 * 1024)
    print(f"\n✓ Built: {exe}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
```

Important notes for the engineer reading this:
- The `--add-data "SRC;DEST"` semicolon is the **Windows** separator. On Linux/Mac it would be `:`. Build script is Windows-only by design.
- `DEST = "."` means "bundle to the root of the frozen package"; `DEST = "assets"` means "bundle into the `assets/` subdir" — this matches the layout `resource_path()` expects.
- `--clean` wipes PyInstaller's cache from previous builds (safer when assets change).
- `--noconfirm` skips the "overwrite output dir?" prompt.

- [ ] **Step 2: Run the build**

Run:
```
python scripts/build_dist.py
```

Expected: PyInstaller streams build output (~30-90 seconds). Final lines should include:
```
✓ Built: e:\Industry\Entrepreneurship\Purr_Pause\dist\PurrPause.exe  (XX.X MB)
```

Size should be between 80 and 120 MB. If significantly outside that range, something is wrong (e.g., assets failed to bundle → too small; or extra dependencies pulled in → too large).

If the build fails:
- `ModuleNotFoundError`: check `requirements.txt` is fully installed (`pip install -r requirements.txt`)
- `unable to find file` for an asset: confirm the asset exists under `assets/` (e.g., MP4 and Source Han fonts are gitignored but should exist locally)

- [ ] **Step 3: Commit the build script (NOT the dist/ artifacts)**

```
git status
```

Confirm that `dist/`, `build/`, `PurrPause.spec`, `assets/icon.ico` are all listed as ignored (not staged). Only `scripts/build_dist.py` should be untracked.

```
git add scripts/build_dist.py
git commit -m "feat: add scripts/build_dist.py — PyInstaller --onefile bundler"
```

---

## Task 11: Verify the Built `.exe`

**No code changes. This is the verification gate per the spec's "验证步骤" section.**

- [ ] **Step 1: Smoke launch from a fresh location**

Copy `dist/PurrPause.exe` to your Desktop (or any path outside the project). Double-click it.

Expected:
- No console window appears
- No error dialog
- Within 2-4 seconds, a cat icon appears in the system tray

- [ ] **Step 2: Tooltip and menu**

Hover the tray icon → tooltip reads `Purr Pause v0.1.0-trial`.

Right-click → menu appears with:
- Cat icon + "Purr Pause" header
- 暂停 (text only, no icon)
- 设置 (text only, no icon)
- 退出

- [ ] **Step 3: Settings dialog**

Click "设置". Dialog should open with:
- Subtitle "调整护眼提醒和休息时长"
- Two grid-aligned rows: `提醒间隔  [N] 分钟` and `休息时长  [N] 秒`
- Amber "保存" button on the right, gray "取消" button on the left

- [ ] **Step 4: Persistence test (most critical)**

1. Change "提醒间隔" to a non-default value (e.g., 5 minutes)
2. Click 保存
3. Close the dialog
4. Right-click tray icon → 退出
5. Wait 2 seconds (let temp dir clean up)
6. Double-click `PurrPause.exe` again
7. Open 设置
8. Confirm the new value (5) is still shown

If step 8 shows the default value instead of 5: the `%APPDATA%\PurrPause\config.json` write path is broken — go back to Task 3 / Task 1 and debug `user_data_dir()`.

- [ ] **Step 5: Verify the config file location**

Open File Explorer, paste into the address bar:
```
%APPDATA%\PurrPause
```

Expected: the folder exists and contains `config.json`. Open it — it should contain your modified value (5).

- [ ] **Step 6: Clean exit**

Right-click tray → 退出 → confirm the icon disappears and the `PurrPause.exe` process is gone from Task Manager.

- [ ] **Step 7: Document the build (no commit)**

The .exe is ready to send. You can:
- ZIP `dist/PurrPause.exe` (WeChat requires it be inside a zip)
- Or upload directly to a cloud drive

No code commit for this task — verification only.

---

## Self-Review Notes

**Spec coverage check:** Each of the 11 待实现项 from the spec maps to:
- Spec item 1 (paths.py) → Task 1
- Spec item 2 (version.py) → Task 2
- Spec item 3 (settings.py) → Task 3
- Spec item 4 (cat_window.py) → Task 4
- Spec item 5 (main.py) → Task 5
- Spec item 6 (tray.py) → Task 6
- Spec item 7 (requirements.txt) → Task 7
- Spec item 8 (scripts/build_dist.py) → Task 10
- Spec item 9 (.gitignore) → Task 9
- Spec item 10 (source-mode regression) → Task 8
- Spec item 11 (build + verify) → Tasks 10 + 11

Task 8 (regression) is intentionally placed before Tasks 9-11 — it gates the build phase. If source mode is broken, the build will be broken too.

**Type consistency:** `resource_path(rel: str) -> Path` and `user_data_dir() -> Path` are referenced with the same signatures throughout Tasks 1, 3, 4, 5. `VERSION` is referenced as a `str` constant in Tasks 2 and 6.

**No placeholders:** Every code block above is complete. Every shell command has an expected outcome. No "TBD" / "fill in later".

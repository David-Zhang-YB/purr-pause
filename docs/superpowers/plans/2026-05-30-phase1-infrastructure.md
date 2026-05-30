# Phase 1: Distribution Infrastructure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `git tag vX.Y.Z && git push --tags` automatically produce Windows .exe + macOS .dmg attached to a GitHub Release. No application-feature changes in this phase — only build infrastructure and one targeted cross-platform fix in `paths.py`.

**Architecture:** Two-job GitHub Actions workflow (windows-latest + macos-latest) drives an existing PyInstaller-based local build script. The build script is refactored to be platform-aware: separate icon generators (`.ico` vs `.icns`), platform-correct `--add-data` separator, versioned output filenames. The runtime user-data directory resolution is fixed to follow per-OS conventions.

**Tech Stack:** Python 3.11, PyInstaller 6.x, Pillow (icon rendering), pytest + pytest-qt (existing tests), GitHub Actions (`actions/checkout`, `actions/setup-python`, `softprops/action-gh-release`), `dmgbuild` (macOS .dmg, install-on-demand in CI).

**Reference spec:** [docs/superpowers/specs/2026-05-30-distribution-rollout-design.md](../specs/2026-05-30-distribution-rollout-design.md) (Phase 1 section)

---

## File Structure

| File | Action | Purpose |
|---|---|---|
| `LICENSE` | Create | MIT license, copyright 2026 Yubo Zhang |
| `.gitignore` | Modify | Add `.DS_Store`, `assets/icon.icns`, `docs/demo.gif` |
| `version.py` | Modify | `0.1.0-trial` → `0.1.0` |
| `paths.py` | Modify | Cross-platform `user_data_dir()` (Win/Mac conventions) |
| `tests/test_paths.py` | Modify | Add macOS/Linux coverage; pin existing Windows test to `sys.platform="win32"` so CI on macOS still passes |
| `scripts/build_dist.py` | Modify | Platform-aware: extract helpers, add macOS branch, version in output name |
| `tests/test_build_dist.py` | Create | Unit tests for the new helper functions |
| `.github/workflows/release.yml` | Create | CI: tagged push → build two platforms → upload to release |

The refactor of `build_dist.py` extracts three pure helpers so they can be unit-tested without invoking PyInstaller:

- `output_filename(version: str, platform: str) -> str`
- `add_data_pairs(root: Path, platform: str) -> list[str]`
- `emoji_font_path(platform: str) -> Path`

The `make_icon()` Windows function stays; a new `make_icns()` is added for macOS. `main()` becomes a thin orchestrator dispatching on `sys.platform`.

---

## Task 1: Bump version to 0.1.0

**Files:**
- Modify: `version.py`

- [ ] **Step 1: Edit `version.py`**

Change the file to:

```python
VERSION = "0.1.0"
```

- [ ] **Step 2: Run the full test suite to confirm no regression**

Run: `pytest -v`

Expected: All existing tests pass (the version string is consumed in `tray.py` as a tooltip; no test asserts the exact value).

- [ ] **Step 3: Commit**

```bash
git add version.py
git commit -m "chore: bump version to 0.1.0 for first public release"
```

---

## Task 2: Add MIT LICENSE

**Files:**
- Create: `LICENSE`

- [ ] **Step 1: Create `LICENSE`**

Write this exact content (standard MIT, with 2026 year and Yubo Zhang as copyright holder):

```
MIT License

Copyright (c) 2026 Yubo Zhang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Commit**

```bash
git add LICENSE
git commit -m "chore: add MIT LICENSE for first public release"
```

---

## Task 3: Update `.gitignore`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append new patterns**

Append these lines to the existing `.gitignore` (after the existing `assets/icon.ico` line):

```
assets/icon.icns
.DS_Store
docs/demo.gif
```

- [ ] **Step 2: Verify nothing new gets tracked**

Run: `git status`

Expected: only the modified `.gitignore` shows up — no `.DS_Store`, no `icon.icns`, no `docs/demo.gif` (they don't exist yet, but the patterns are ready for when they do).

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore macOS .DS_Store, .icns icon, and generated demo.gif"
```

---

## Task 4: Cross-platform `paths.py`

**Files:**
- Modify: `paths.py`
- Modify: `tests/test_paths.py` (4 tests already exist; pin existing Windows test to `sys.platform`, add macOS + Linux coverage)

The current `user_data_dir()` only handles Windows. On macOS frozen mode it falls back to `~/AppData/Roaming/PurrPause/` — non-crashy but ugly. We follow OS conventions:
- Windows: `%APPDATA%\PurrPause\`
- macOS: `~/Library/Application Support/PurrPause/`
- Linux: `$XDG_CONFIG_HOME/PurrPause/` (default `~/.config/PurrPause/`) — not in shipping scope but easy to handle

Existing `test_user_data_dir_when_frozen_uses_appdata_and_creates_dir` (line 33) doesn't mock `sys.platform`, so on a macOS CI runner it would break after our `paths.py` change. We pin it explicitly and add new cases.

- [ ] **Step 1: Update `tests/test_paths.py` to add the new failing tests**

Replace the entire file with:

```python
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
    import paths
    from paths import user_data_dir
    result = user_data_dir()
    assert result == Path(paths.__file__).parent


def test_user_data_dir_frozen_windows_uses_appdata(monkeypatch, tmp_path):
    """On Windows frozen, %APPDATA%\\PurrPause is created and returned."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from paths import user_data_dir
    result = user_data_dir()
    assert result == tmp_path / "PurrPause"
    assert result.is_dir()


def test_user_data_dir_frozen_windows_no_appdata_falls_back_to_home(monkeypatch, tmp_path):
    """Without APPDATA env, fall back to ~/AppData/Roaming/PurrPause."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    from paths import user_data_dir
    result = user_data_dir()
    assert result == tmp_path / "AppData" / "Roaming" / "PurrPause"
    assert result.is_dir()


def test_user_data_dir_frozen_macos_uses_application_support(monkeypatch, tmp_path):
    """On macOS frozen, ~/Library/Application Support/PurrPause is created and returned."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    from paths import user_data_dir
    result = user_data_dir()
    assert result == tmp_path / "Library" / "Application Support" / "PurrPause"
    assert result.is_dir()


def test_user_data_dir_frozen_linux_uses_xdg_config_home(monkeypatch, tmp_path):
    """On Linux frozen with XDG_CONFIG_HOME set, use $XDG_CONFIG_HOME/PurrPause."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    from paths import user_data_dir
    result = user_data_dir()
    assert result == tmp_path / "xdg" / "PurrPause"
    assert result.is_dir()


def test_user_data_dir_frozen_linux_no_xdg_falls_back_to_home_config(monkeypatch, tmp_path):
    """Without XDG_CONFIG_HOME, fall back to ~/.config/PurrPause."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    from paths import user_data_dir
    result = user_data_dir()
    assert result == tmp_path / ".config" / "PurrPause"
    assert result.is_dir()
```

- [ ] **Step 2: Run the tests to confirm new ones fail**

Run: `pytest tests/test_paths.py -v`

Expected: the 3 macOS/Linux tests fail (current code only knows Windows); the renamed/existing Windows tests still pass on Windows.

- [ ] **Step 3: Update `paths.py`**

Replace the entire file with:

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
    """Return the writable user-data directory, per-OS convention.

    Source mode: project root (matches existing dev behavior).
    Frozen mode:
      - Windows: %APPDATA%\\PurrPause (or ~/AppData/Roaming/PurrPause)
      - macOS:   ~/Library/Application Support/PurrPause
      - Linux:   $XDG_CONFIG_HOME/PurrPause (or ~/.config/PurrPause)
    """
    if not getattr(sys, "frozen", False):
        return Path(__file__).parent

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        root = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        root = Path(xdg) if xdg else Path.home() / ".config"

    d = root / "PurrPause"
    d.mkdir(parents=True, exist_ok=True)
    return d
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `pytest tests/test_paths.py -v`

Expected: all 7 tests pass.

- [ ] **Step 5: Run the full test suite to confirm no regression**

Run: `pytest -v`

Expected: all tests (existing + new) pass.

- [ ] **Step 6: Commit**

```bash
git add paths.py tests/test_paths.py
git commit -m "feat(paths): cross-platform user_data_dir for Windows/macOS/Linux"
```

---

## Task 5: Refactor `build_dist.py` — extract testable helpers

**Files:**
- Modify: `scripts/build_dist.py`
- Create: `tests/test_build_dist.py`

Refactor without behavior change first. Three pure helpers are extracted so they're unit-testable. After this task, running `python scripts/build_dist.py` on Windows must still produce the exact same output as before.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_build_dist.py`:

```python
"""Tests for build_dist.py helper functions."""
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import build_dist


class TestOutputFilename:
    def test_windows(self):
        assert build_dist.output_filename("0.1.0", "win32") == "PurrPause-0.1.0-windows.exe"

    def test_macos(self):
        assert build_dist.output_filename("0.1.0", "darwin") == "PurrPause-0.1.0-macos.dmg"

    def test_unknown_platform_raises(self):
        with pytest.raises(ValueError, match="unsupported"):
            build_dist.output_filename("0.1.0", "linux")


class TestAddDataPairs:
    """Test the separator at the END of each pair, not just `in` — on Windows the
    drive-letter colon (C:/Users/...) means `":" in pair` is trivially true."""

    WIN_ENDINGS = (";.", ";assets", ";assets/cat_anim", ";assets/fonts")
    MAC_ENDINGS = (":.", ":assets", ":assets/cat_anim", ":assets/fonts")

    def test_windows_uses_semicolon(self, tmp_path):
        pairs = build_dist.add_data_pairs(tmp_path, "win32")
        for pair in pairs:
            assert pair.endswith(self.WIN_ENDINGS), f"unexpected ending: {pair}"

    def test_macos_uses_colon(self, tmp_path):
        pairs = build_dist.add_data_pairs(tmp_path, "darwin")
        for pair in pairs:
            assert pair.endswith(self.MAC_ENDINGS), f"unexpected ending: {pair}"

    def test_includes_all_required_assets(self, tmp_path):
        pairs = build_dist.add_data_pairs(tmp_path, "win32")
        joined = " ".join(pairs)
        assert "config.default.json" in joined
        assert "cat_anim" in joined
        assert "cat.gif" in joined
        assert "NotoSansSC" in joined


class TestEmojiFontPath:
    def test_windows(self):
        p = build_dist.emoji_font_path("win32")
        assert str(p) == "C:/Windows/Fonts/seguiemj.ttf"

    def test_macos(self):
        p = build_dist.emoji_font_path("darwin")
        assert str(p) == "/System/Library/Fonts/Apple Color Emoji.ttc"

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            build_dist.emoji_font_path("linux")
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/test_build_dist.py -v`

Expected: ImportError or AttributeError on `build_dist.output_filename` / `add_data_pairs` / `emoji_font_path` (functions don't exist yet).

- [ ] **Step 3: Refactor `build_dist.py`**

Replace the entire file with:

```python
"""Build PurrPause distributable via PyInstaller.

Run: python scripts/build_dist.py

Produces (under dist/):
  - Windows: PurrPause-{VERSION}-windows.exe (single-file binary)
  - macOS:   PurrPause-{VERSION}-macos.dmg   (drag-to-Applications disk image)
"""
import subprocess
import sys
from pathlib import Path

try:
    import PyInstaller  # noqa: F401  -- fail fast if missing
except ImportError as exc:
    raise SystemExit(
        f"PyInstaller is not importable from {sys.executable}.\n"
        "Run `pip install -r requirements.txt` in the active environment, "
        "or invoke this script with the python that has PyInstaller installed."
    ) from exc

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from version import VERSION  # noqa: E402


def output_filename(version: str, platform: str) -> str:
    """Compute the release artifact filename for a given platform."""
    if platform == "win32":
        return f"PurrPause-{version}-windows.exe"
    if platform == "darwin":
        return f"PurrPause-{version}-macos.dmg"
    raise ValueError(f"unsupported platform: {platform}")


def add_data_pairs(root: Path, platform: str) -> list[str]:
    """Build the `--add-data` value list with the correct OS separator."""
    sep = ";" if platform == "win32" else ":"
    return [
        f"{root/'config.default.json'}{sep}.",
        f"{root/'assets'/'cat_anim'}{sep}assets/cat_anim",
        f"{root/'assets'/'Mascot Cat Black.png'}{sep}assets",
        f"{root/'assets'/'Mascot Cat White.png'}{sep}assets",
        f"{root/'assets'/'cat.gif'}{sep}assets",
        f"{root/'assets'/'fonts'/'NotoSansSC[wght].ttf'}{sep}assets/fonts",
    ]


def emoji_font_path(platform: str) -> Path:
    """Resolve the per-OS color-emoji font Pillow can render via embedded_color."""
    if platform == "win32":
        return Path("C:/Windows/Fonts/seguiemj.ttf")
    if platform == "darwin":
        return Path("/System/Library/Fonts/Apple Color Emoji.ttc")
    raise ValueError(f"unsupported platform: {platform}")


def make_icon() -> Path:
    """Render the 🐱 emoji to a multi-size Windows .ico."""
    dst = ROOT / "assets" / "icon.ico"
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(emoji_font_path("win32")), size=int(size * 0.75))
    text = "🐱"
    bbox = draw.textbbox((0, 0), text, font=font, embedded_color=True)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - w) // 2 - bbox[0]
    y = (size - h) // 2 - bbox[1]
    draw.text((x, y), text, font=font, embedded_color=True)
    img.save(
        dst,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return dst


def build_windows() -> Path:
    icon = make_icon()
    print(f"[OK] Generated icon: {icon}")

    add_data_args: list[str] = []
    for pair in add_data_pairs(ROOT, "win32"):
        add_data_args.extend(["--add-data", pair])

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--name", f"PurrPause-{VERSION}-windows",
        f"--icon={icon}",
        *add_data_args,
        str(ROOT / "main.py"),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)

    exe = ROOT / "dist" / output_filename(VERSION, "win32")
    return exe


def main() -> None:
    if sys.platform == "win32":
        artifact = build_windows()
    else:
        raise SystemExit(f"build_dist.py: platform '{sys.platform}' not yet supported. "
                         f"(macOS support is added in the next task.)")

    size_mb = artifact.stat().st_size / (1024 * 1024)
    print(f"\n[OK] Built: {artifact}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
```

Key changes versus the prior version:
- Three helpers extracted: `output_filename`, `add_data_pairs`, `emoji_font_path`
- `make_icon()` now sources its font from `emoji_font_path("win32")` instead of a hardcoded constant
- `--name` includes the version, so PyInstaller outputs `PurrPause-{VERSION}-windows.exe` directly
- `main()` dispatches on `sys.platform`; macOS branch (next task) plugs in here
- `version.py` is imported for `VERSION`

- [ ] **Step 4: Run the helper tests to confirm they pass**

Run: `pytest tests/test_build_dist.py -v`

Expected: all 8 tests pass.

- [ ] **Step 5: Run the full test suite to confirm no regression**

Run: `pytest -v`

Expected: all tests pass.

- [ ] **Step 6: Local Windows build smoke test**

Run: `python scripts/build_dist.py`

Expected: exit 0; `dist/PurrPause-0.1.0-windows.exe` exists with size around 63 MB; double-clicking it runs the app (tray icon appears).

Note: the `dist/` directory is gitignored so this artifact stays local.

- [ ] **Step 7: Commit**

```bash
git add scripts/build_dist.py tests/test_build_dist.py
git commit -m "refactor(build): extract platform helpers and version output filename"
```

---

## Task 6: Add macOS support to `build_dist.py`

**Files:**
- Modify: `scripts/build_dist.py`
- Modify: `tests/test_build_dist.py`

- [ ] **Step 1: Add a test for the macOS dispatcher**

Append to `tests/test_build_dist.py`:

```python
class TestMacOSBranch:
    def test_make_icns_uses_apple_color_emoji_font(self, monkeypatch):
        """Verifies make_icns reads from emoji_font_path('darwin'), not Windows path."""
        captured = []
        from PIL import ImageFont

        def fake_truetype(path, size):
            captured.append(str(path))
            # Return a real font so the rest of make_icns can proceed if reached.
            raise RuntimeError("font-not-loaded (test stub)")

        monkeypatch.setattr(ImageFont, "truetype", fake_truetype)

        with pytest.raises(RuntimeError):
            build_dist.make_icns()

        assert captured == ["/System/Library/Fonts/Apple Color Emoji.ttc"]
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `pytest tests/test_build_dist.py::TestMacOSBranch -v`

Expected: AttributeError — `make_icns` does not exist yet.

- [ ] **Step 3: Add `make_icns` and the macOS build branch to `build_dist.py`**

Add this function after `make_icon`:

```python
def make_icns() -> Path:
    """Render the 🐱 emoji to a multi-size macOS .icns icon.

    Uses Apple Color Emoji (a TrueType collection); Pillow renders glyph
    via embedded_color sbix tables.
    """
    dst = ROOT / "assets" / "icon.icns"
    sizes = [16, 32, 48, 64, 128, 256, 512]
    images = []
    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Apple Color Emoji's smallest sbix bitmap is 160px; pick the closest
        # rendered size and let PIL downscale. Using size*0.75 like make_icon
        # gives the cat ~75% of the canvas.
        font = ImageFont.truetype(str(emoji_font_path("darwin")), size=int(size * 0.75))
        text = "🐱"
        bbox = draw.textbbox((0, 0), text, font=font, embedded_color=True)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (size - w) // 2 - bbox[0]
        y = (size - h) // 2 - bbox[1]
        draw.text((x, y), text, font=font, embedded_color=True)
        images.append(img)
    images[0].save(dst, format="ICNS", append_images=images[1:])
    return dst
```

Add a `build_macos` function after `build_windows`:

```python
def build_macos() -> Path:
    icon = make_icns()
    print(f"[OK] Generated icon: {icon}")

    add_data_args: list[str] = []
    for pair in add_data_pairs(ROOT, "darwin"):
        add_data_args.extend(["--add-data", pair])

    app_name = f"PurrPause-{VERSION}-macos"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--name", app_name,
        f"--icon={icon}",
        *add_data_args,
        str(ROOT / "main.py"),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)

    app_bundle = ROOT / "dist" / f"{app_name}.app"
    dmg_path = ROOT / "dist" / output_filename(VERSION, "darwin")

    # dmgbuild is installed on demand in CI (not in requirements.txt).
    try:
        import dmgbuild  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "dmgbuild not installed. In CI it is installed in the macOS job. "
            "Locally: `pip install dmgbuild`."
        ) from exc

    settings_file = ROOT / "scripts" / "dmgbuild_settings.py"
    subprocess.run(
        ["dmgbuild", "-s", str(settings_file), app_name, str(dmg_path)],
        cwd=ROOT, check=True,
    )
    return dmg_path
```

Update `main()` to dispatch:

```python
def main() -> None:
    if sys.platform == "win32":
        artifact = build_windows()
    elif sys.platform == "darwin":
        artifact = build_macos()
    else:
        raise SystemExit(f"build_dist.py: platform '{sys.platform}' not supported")

    size_mb = artifact.stat().st_size / (1024 * 1024)
    print(f"\n[OK] Built: {artifact}  ({size_mb:.1f} MB)")
```

- [ ] **Step 4: Create the dmgbuild settings file**

Create `scripts/dmgbuild_settings.py`:

```python
"""Minimal dmgbuild settings — drag-app-to-Applications layout.

Invoked by build_dist.py on macOS via:
    dmgbuild -s scripts/dmgbuild_settings.py <volume_name> <output.dmg>

dmgbuild executes this file with `appname` set to the volume name (first
positional). We rely on the convention that the matching .app bundle sits
at dist/<appname>.app, which is what PyInstaller produces with --name <appname>.
"""
import os

application = os.path.join("dist", f"{appname}.app")  # noqa: F821 — appname injected by dmgbuild

format = "UDZO"  # compressed read-only
files = [application]
symlinks = {"Applications": "/Applications"}
icon_locations = {
    os.path.basename(application): (140, 120),
    "Applications": (500, 120),
}
window_rect = ((100, 100), (640, 280))
icon_size = 96
text_size = 14
```

- [ ] **Step 5: Run the helper test to confirm it passes**

Run: `pytest tests/test_build_dist.py::TestMacOSBranch -v`

Expected: test passes (the test stubs `ImageFont.truetype`, so this test runs on any OS — including the Windows dev machine — without needing the actual Apple Color Emoji file present).

- [ ] **Step 6: Run the full test suite to confirm no regression**

Run: `pytest -v`

Expected: all tests pass.

- [ ] **Step 7: Verify the macOS code path doesn't break the Windows build**

Run: `python scripts/build_dist.py`

Expected: still produces `dist/PurrPause-0.1.0-windows.exe` as before; macOS branch is untaken.

Note: the actual .dmg build can only be verified in the CI run (Task 8) or on a real Mac.

- [ ] **Step 8: Commit**

```bash
git add scripts/build_dist.py scripts/dmgbuild_settings.py tests/test_build_dist.py
git commit -m "feat(build): add macOS .icns icon + .dmg packaging path"
```

---

## Task 7: GitHub Actions release workflow

**Files:**
- Create: `.github/workflows/release.yml`

The workflow triggers on tag push `v*.*.*`. Two parallel jobs (Windows + macOS) each run `build_dist.py` and upload their artifact. A final aggregator job attaches both to the GitHub Release.

- [ ] **Step 1: Create the workflow file**

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags:
      - 'v*.*.*'

permissions:
  contents: write  # required for softprops/action-gh-release

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Verify version.py matches git tag
        shell: bash
        run: |
          TAG="${GITHUB_REF_NAME#v}"
          PY_VERSION=$(python -c "import version; print(version.VERSION)")
          if [ "$TAG" != "$PY_VERSION" ]; then
            echo "::error::tag '$TAG' does not match version.VERSION '$PY_VERSION'"
            exit 1
          fi

      - name: Build Windows .exe
        run: python scripts/build_dist.py

      - name: Upload Windows artifact
        uses: actions/upload-artifact@v4
        with:
          name: windows-exe
          path: dist/PurrPause-*-windows.exe
          if-no-files-found: error

  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install dmgbuild

      - name: Verify version.py matches git tag
        shell: bash
        run: |
          TAG="${GITHUB_REF_NAME#v}"
          PY_VERSION=$(python -c "import version; print(version.VERSION)")
          if [ "$TAG" != "$PY_VERSION" ]; then
            echo "::error::tag '$TAG' does not match version.VERSION '$PY_VERSION'"
            exit 1
          fi

      - name: Build macOS .dmg
        run: python scripts/build_dist.py

      - name: Upload macOS artifact
        uses: actions/upload-artifact@v4
        with:
          name: macos-dmg
          path: dist/PurrPause-*-macos.dmg
          if-no-files-found: error

  release:
    runs-on: ubuntu-latest
    needs: [build-windows, build-macos]
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: artifacts

      - name: Publish Release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            artifacts/windows-exe/*
            artifacts/macos-dmg/*
          generate_release_notes: true
          draft: false
          prerelease: false
```

- [ ] **Step 2: Validate the YAML syntax locally**

If you have `actionlint` installed: `actionlint .github/workflows/release.yml`.
Otherwise: `python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"` (yaml is a transitive dep of PyInstaller, so it should be importable).

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add release workflow building Win/Mac binaries on tag push"
```

---

## Task 8: User-side GitHub repo bootstrap (manual)

**This task is performed by the user, not Claude.**

Display this checklist to the user and wait for confirmation that each step is done before proceeding to Task 9.

- [ ] **Step 1: User creates GitHub repo**

User goes to https://github.com/new and creates a new repository:
- Owner: their account (`yubo-david-zhang` or similar)
- Repository name: `purr-pause`
- Visibility: **Public**
- Do **NOT** initialize with README, .gitignore, or LICENSE (we already have them locally)

- [ ] **Step 2: User connects local repo to GitHub remote**

In the project root:

```bash
git branch -M main
git remote add origin git@github.com:<owner>/purr-pause.git
git push -u origin main
```

(If using HTTPS instead of SSH, the URL is `https://github.com/<owner>/purr-pause.git`.)

- [ ] **Step 3: User confirms repo is live**

Visit `https://github.com/<owner>/purr-pause` and confirm:
- Code is visible
- License is detected as MIT (right sidebar)
- Latest commit message shows the most recent Task 7 commit

- [ ] **Step 4: User reports completion to Claude**

Once these steps are done, the user types something like "GitHub repo is set up, owner is xxx". Claude then proceeds to Task 9 substituting the owner name into the dry-run commands.

---

## Task 9: CI dry-run with a test tag

**Files:** none — this task validates the prior tasks end-to-end.

Strategy: the green-build test uses a throwaway branch so `main` history stays clean. The guardrail test reuses `main` (no commit needed — just an off-version tag).

- [ ] **Step 1: Test the version-tag guardrail (no commit needed)**

```bash
git tag v0.0.1-test
git push origin v0.0.1-test
```

Open `https://github.com/<owner>/purr-pause/actions`. Expected: both `build-windows` and `build-macos` fail at the "Verify version.py matches git tag" step with a message like "tag '0.0.1-test' does not match version.VERSION '0.1.0'". This proves the guardrail works.

- [ ] **Step 2: Delete the failed-run tag and Actions run records**

```bash
git push --delete origin v0.0.1-test
git tag -d v0.0.1-test
```

Optionally delete the corresponding run from the GitHub Actions UI for tidiness (not required — failed runs are auto-pruned by GitHub after 90 days).

- [ ] **Step 3: Create a disposable branch for the green-build test**

```bash
git checkout -b ci-dry-run
```

Edit `version.py` to set `VERSION = "0.0.1"`, then:

```bash
git add version.py
git commit -m "test(ci-dry-run): temporary version bump"
git tag v0.0.1
git push origin ci-dry-run v0.0.1
```

The tag points to a commit on `ci-dry-run`. CI uses the workflow file at that commit (identical to `main`'s) and checks out that commit's source for the build.

- [ ] **Step 4: Observe a green CI run**

Watch the Actions tab. Expected:
- `build-windows` succeeds, uploads `PurrPause-0.0.1-windows.exe`
- `build-macos` succeeds, uploads `PurrPause-0.0.1-macos.dmg`
- `release` job succeeds; both artifacts visible at `https://github.com/<owner>/purr-pause/releases/tag/v0.0.1`

If either build job fails, capture the failing step's log and stop here — do not proceed until the failure is understood and fixed.

- [ ] **Step 5: Download both artifacts and smoke-test them**

- Windows: download the .exe, double-click, dismiss SmartScreen (More info → Run anyway), verify tray icon appears and a rest break triggers correctly.
- macOS: download the .dmg, mount, drag .app to Applications, right-click → Open (dismiss Gatekeeper), verify tray icon appears and a rest break triggers correctly.

If no Mac is available, ask a friend to run the .dmg smoke test before declaring Phase 1 complete.

- [ ] **Step 6: Tear down the dry-run artifacts**

```bash
git checkout main
git branch -D ci-dry-run
git push --delete origin ci-dry-run v0.0.1
git tag -d v0.0.1
```

In the GitHub web UI: go to Releases, find the `v0.0.1` release, click Edit → Delete release. (Tag deletion above does NOT auto-remove the release record.)

- [ ] **Step 7: Final state check**

Run: `git log --oneline -10 && git branch -a && git tag -l && git status`

Expected:
- `git log` shows only the legitimate Phase 1 commits on `main`; no `ci-dry-run` commit reachable
- `git branch -a` shows only `main` (and its remote tracking branch); no `ci-dry-run` locally or remotely
- `git tag -l` shows no `v0.0.1*` tags
- `git status` shows working tree clean
- `version.py` says `VERSION = "0.1.0"` (was never modified on `main`)
- `https://github.com/<owner>/purr-pause/releases` shows no test releases

Phase 1 is complete. CI is proven to work end-to-end. Phase 2 (README rewrite + v0.1.0 first public release) can now begin.

---

## Phase 1 success criteria

All of the following must be true before declaring Phase 1 done:

1. `version.py` says `0.1.0`
2. `LICENSE` exists with MIT text
3. `.gitignore` covers `.DS_Store`, `assets/icon.icns`, `docs/demo.gif`
4. `paths.py` returns the per-OS convention for `user_data_dir()` in frozen mode
5. `scripts/build_dist.py` has Windows and macOS branches, both gated on `sys.platform`
6. `tests/test_paths.py` and `tests/test_build_dist.py` pass
7. `python scripts/build_dist.py` on Windows produces `dist/PurrPause-0.1.0-windows.exe` that runs
8. `.github/workflows/release.yml` exists
9. GitHub repo `purr-pause` is public, contains all local commits, license recognized
10. A test tag has demonstrably produced both `PurrPause-0.0.1-windows.exe` and `PurrPause-0.0.1-macos.dmg` artifacts on the Releases page, both smoke-tested
11. All test artifacts cleaned up; `version.py` back to `0.1.0`; working tree clean

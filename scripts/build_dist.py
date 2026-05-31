"""Build PurrPause distributable via PyInstaller.

Run: python scripts/build_dist.py

Produces (under dist/):
  - Windows: PurrPause-{VERSION}-windows.exe (single-file binary)
  - macOS:   PurrPause-{VERSION}-macos.dmg   (drag-to-Applications disk image)
"""
import subprocess
import sys
from pathlib import Path, PurePosixPath

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


def emoji_font_path(platform: str) -> PurePosixPath:
    """Resolve the per-OS color-emoji font Pillow can render via embedded_color.

    Returns a PurePosixPath so that str() yields forward-slash strings on all
    host platforms (the paths are passed to Pillow/PyInstaller as strings, not
    used for Python-level file I/O).
    """
    if platform == "win32":
        return PurePosixPath("C:/Windows/Fonts/seguiemj.ttf")
    if platform == "darwin":
        return PurePosixPath("/System/Library/Fonts/Apple Color Emoji.ttc")
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


def make_icns() -> Path:
    """Render the 🐱 emoji to a multi-size macOS .icns icon.

    Uses Apple Color Emoji (a TrueType collection); Pillow renders glyph
    via embedded_color sbix tables.

    KNOWN ISSUE (v0.1.x — macOS build disabled in CI): Apple Color Emoji is
    a bitmap font with discrete sbix sizes (20/32/40/48/64/96/128/160). The
    loop below calls ImageFont.truetype with size=int(target*0.75), which is
    12 for target=16 — below the smallest sbix bitmap, causing
    "OSError: invalid pixel size". Fix is to always load the font at a
    known sbix size (e.g. 160) then PIL-downscale the rendered RGBA image.
    Deferred until we have macOS access to verify the Pillow ICNS writer.
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


def main() -> None:
    if sys.platform == "win32":
        artifact = build_windows()
    elif sys.platform == "darwin":
        artifact = build_macos()
    else:
        raise SystemExit(f"build_dist.py: platform '{sys.platform}' not supported")

    size_mb = artifact.stat().st_size / (1024 * 1024)
    print(f"\n[OK] Built: {artifact}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()

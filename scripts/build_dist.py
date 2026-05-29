"""Build PurrPause.exe via PyInstaller.

Run: python scripts/build_dist.py

Produces: dist/PurrPause.exe (~80-120 MB, single-file Windows binary)
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

EMOJI_FONT = Path("C:/Windows/Fonts/seguiemj.ttf")


def make_icon() -> Path:
    """Render the 🐱 emoji (same glyph as the tray icon) to a multi-size .ico."""
    dst = ROOT / "assets" / "icon.ico"
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(EMOJI_FONT), size=int(size * 0.75))
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


def main() -> None:
    icon = make_icon()
    print(f"[OK] Generated icon: {icon}")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--name", "PurrPause",
        f"--icon={icon}",
        "--add-data", f"{ROOT/'config.default.json'};.",
        "--add-data", f"{ROOT/'assets'/'cat_anim'};assets/cat_anim",
        "--add-data", f"{ROOT/'assets'/'Mascot Cat Black.png'};assets",
        "--add-data", f"{ROOT/'assets'/'Mascot Cat White.png'};assets",
        "--add-data", f"{ROOT/'assets'/'cat.gif'};assets",
        "--add-data", f"{ROOT/'assets'/'fonts'/'NotoSansSC[wght].ttf'};assets/fonts",
        str(ROOT / "main.py"),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)

    exe = ROOT / "dist" / "PurrPause.exe"
    size_mb = exe.stat().st_size / (1024 * 1024)
    print(f"\n[OK] Built: {exe}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()

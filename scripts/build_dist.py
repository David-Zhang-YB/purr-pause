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
    print(f"\n[OK] Built: {exe}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()

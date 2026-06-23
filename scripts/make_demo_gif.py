"""Generate docs/demo.gif from the cat_anim PNG sprite sequence.

This is a one-off marketing-asset builder. Run once when the README GIF needs
updating; commit the resulting `docs/demo.gif` to the repository:

    python scripts/make_demo_gif.py

Output: docs/demo.gif (target <= 2 MB).

Algorithm:
  - Read `assets/cat_anim/manifest.json` for canvas size and per-frame positions.
  - Frame selection: TARGET_FRAMES evenly-spaced frames from the single animation
    sequence (enter -> rest -> exit). Even-index sampling naturally spends more
    frames on the motion (which has more frames) and skims the still rest, which
    makes for a livelier demo and keeps the GIF under the size budget.
  - Composite each RGBA sprite onto a flat-color RGB canvas at its recorded (x, y).
  - Downscale by SCALE so the GIF stays inside MAX_OUTPUT_BYTES.
  - Save as an animated GIF (loop forever) with a uniform per-frame duration
    chosen so the whole loop runs ~TOTAL_SECONDS.
"""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent.parent
ANIM_DIR = ROOT / "assets" / "cat_anim"
MANIFEST = ANIM_DIR / "manifest.json"
OUTPUT = ROOT / "docs" / "demo.gif"

BACKGROUND_RGB = (245, 245, 247)
TARGET_FRAMES = 60
TOTAL_SECONDS = 6.0
SCALE = 0.4
MAX_OUTPUT_BYTES = 2 * 1024 * 1024


def select_indices(total: int, target: int) -> list[int]:
    """Pick `target` evenly-spaced indices from range(total). Sorted, unique."""
    if total <= target:
        return list(range(total))
    step = total / target
    return sorted({int(i * step) for i in range(target)})


def _composite_and_downscale(canvas_size: tuple[int, int], sprite_path: Path, x: int, y: int) -> Image.Image:
    canvas = Image.new("RGB", canvas_size, BACKGROUND_RGB)
    sprite = Image.open(sprite_path).convert("RGBA")
    canvas.paste(sprite, (x, y), sprite)
    new_size = (int(canvas_size[0] * SCALE), int(canvas_size[1] * SCALE))
    return canvas.resize(new_size, Image.LANCZOS)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    canvas_size = (manifest["canvas"][0], manifest["canvas"][1])
    seq = manifest["frames"]

    indices = select_indices(len(seq), TARGET_FRAMES)
    per_frame_ms = max(20, int(TOTAL_SECONDS * 1000 / len(indices)))

    frames: list[Image.Image] = []
    for j in indices:
        pos = seq[j]
        frames.append(
            _composite_and_downscale(canvas_size, ANIM_DIR / f"frame_{j + 1:03d}.png", pos["x"], pos["y"])
        )
    durations = [per_frame_ms] * len(frames)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUTPUT,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )

    size_bytes = OUTPUT.stat().st_size
    size_kb = size_bytes / 1024
    total_seconds = sum(durations) / 1000
    print(f"[OK] Generated: {OUTPUT}")
    print(f"     Frames: {len(frames)}   Duration: {total_seconds:.1f}s   Size: {size_kb:.0f} KB")
    if size_bytes > MAX_OUTPUT_BYTES:
        print(f"[WARN] File exceeds 2 MB target ({size_kb:.0f} KB). Reduce TARGET_FRAMES or SCALE in scripts/make_demo_gif.py.")


if __name__ == "__main__":
    main()

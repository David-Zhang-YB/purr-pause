"""Generate docs/demo.gif from the cat_anim PNG sprite sequence.

This is a one-off marketing-asset builder. Run once when the README GIF needs
updating; commit the resulting `docs/demo.gif` to the repository:

    python scripts/make_demo_gif.py

Output: docs/demo.gif (target <= 2 MB).

Algorithm:
  - Read `assets/cat_anim/manifest.json` for canvas size, fps, frame positions.
  - Frame selection: ALL walk_in frames + evenly-spaced subset of idle frames
    (capped at IDLE_TARGET_FRAMES) + ALL walk_out frames. Idle is throttled
    because raw idle is long and repetitive, and dominates GIF file size.
  - Composite each RGBA sprite onto a flat-color RGB canvas at the position
    recorded in the manifest.
  - Downscale the composited canvas by SCALE before appending, so the final
    GIF is roughly half-size (480x270 instead of 960x540) and well under 2 MB.
  - Save as animated GIF (loop forever, optimize, per-frame durations from
    walk_fps / idle_fps).
"""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent.parent
ANIM_DIR = ROOT / "assets" / "cat_anim"
MANIFEST = ANIM_DIR / "manifest.json"
OUTPUT = ROOT / "docs" / "demo.gif"

BACKGROUND_RGB = (245, 245, 247)
IDLE_TARGET_FRAMES = 12
SCALE = 0.5
MAX_OUTPUT_BYTES = 2 * 1024 * 1024


def select_idle_indices(total: int, target: int) -> list[int]:
    """Pick `target` evenly-spaced indices from range(total). Sorted, unique."""
    if total <= target:
        return list(range(total))
    step = total / target
    return sorted({int(i * step) for i in range(target)})


def _frame_path(section: str, one_based_index: int) -> Path:
    return ANIM_DIR / f"{section}_{one_based_index:02d}.png"


def _composite_and_downscale(canvas_size: tuple[int, int], sprite_path: Path, x: int, y: int) -> Image.Image:
    canvas = Image.new("RGB", canvas_size, BACKGROUND_RGB)
    sprite = Image.open(sprite_path).convert("RGBA")
    canvas.paste(sprite, (x, y), sprite)
    new_size = (int(canvas_size[0] * SCALE), int(canvas_size[1] * SCALE))
    return canvas.resize(new_size, Image.LANCZOS)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    canvas_size = (manifest["canvas"][0], manifest["canvas"][1])
    walk_fps = manifest["walk_fps"]
    idle_fps = manifest["idle_fps"]
    walk_in = manifest["walk_in"]
    idle = manifest["idle"]
    walk_out = manifest["walk_out"]

    walk_in_ms = int(1000 / walk_fps)
    idle_ms = int(1000 / idle_fps)
    walk_out_ms = int(1000 / walk_fps)

    frames: list[Image.Image] = []
    durations: list[int] = []

    for i, pos in enumerate(walk_in, start=1):
        frames.append(_composite_and_downscale(canvas_size, _frame_path("walk_in", i), pos["x"], pos["y"]))
        durations.append(walk_in_ms)

    for j in select_idle_indices(len(idle), IDLE_TARGET_FRAMES):
        pos = idle[j]
        frames.append(_composite_and_downscale(canvas_size, _frame_path("idle", j + 1), pos["x"], pos["y"]))
        durations.append(idle_ms)

    for i, pos in enumerate(walk_out, start=1):
        frames.append(_composite_and_downscale(canvas_size, _frame_path("walk_out", i), pos["x"], pos["y"]))
        durations.append(walk_out_ms)

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
        print(f"[WARN] File exceeds 2 MB target ({size_kb:.0f} KB). Reduce IDLE_TARGET_FRAMES or SCALE in scripts/make_demo_gif.py.")


if __name__ == "__main__":
    main()

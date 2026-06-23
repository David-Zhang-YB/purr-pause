"""Extract the cat animation as one continuous sprite sequence from the source MP4.

One-shot offline script. Run after the source video changes:

    python scripts/extract_cat_frames.py

The whole clip — enter, rest (with head turns), rise, exit — becomes a single
sequence the runtime plays once, stretched to fill the rest duration (no loop, so
no seams). Each frame is cropped to its tight bounding box of opaque pixels and
stored with its (x, y) offset and a normalized time position `t` in [0, 1]; the
runtime shows the frame whose `t` matches the current progress (elapsed / rest
duration), so still stretches simply hold a frame and motion stays in step.

Outputs into ../assets/cat_anim/:
  - manifest.json
  - frame_NNN.png

Dev-only dep: opencv-python-headless (NOT in requirements.txt).
"""
import json
import shutil
import sys
from pathlib import Path

try:
    import cv2
except ImportError:
    raise SystemExit(
        "OpenCV not installed. Install with:\n"
        "    pip install opencv-python-headless"
    )

import numpy as np
from PIL import Image

ROOT = Path(__file__).parent.parent
SRC = ROOT / "assets" / "british_shorthair_interpolation.mp4"
DST = ROOT / "assets" / "cat_anim"

# Green-screen source (~21.5s, 60fps, 1920x1080). One continuous arc: the cat walks
# in from the left, lies into a loaf, turns its head to the camera a few times,
# then rises and walks out to the right by ~21s. We sample the whole thing; trailing
# frames where the cat has left the frame are empty and get skipped automatically, so
# the end bound is set safely past the exit.
ARC = (0.0, 22.0)
# Sampling rate is auto-detected from the source (see main) so every source frame
# is captured and none are doubled — feed it a 24fps or 60fps clip and it adapts.
FPS_FALLBACK = 30

# The background is a chroma-key green screen. We key on "green excess"
# = G - max(R, B), i.e. how strongly green dominates — the standard chroma metric.
# Measured on this clip: the green screen sits at +43..+79, while the silver cat
# (neutral fur, where G ~= R ~= B) sits at -48..-7, even its mid-grays. A plain
# Euclidean distance to the green *point* wrongly keyed those mid-grays out (they
# happen to be near the un-saturated green in RGB space); green-excess separates
# them cleanly. Alpha ramps from opaque at GREEN_LOW to transparent at GREEN_HIGH.
GREEN_LOW = 12.0    # green-excess <= this -> fully opaque (foreground / cat)
GREEN_HIGH = 38.0   # green-excess >= this -> fully transparent (background)

BBOX_ALPHA_THRESHOLD = 64

# Drop frames nearly identical to the last kept one, compared via a 32x32 gray
# thumbnail (DEDUP_SIG) so the test is immune to 1px bbox jitter and alpha-edge
# shimmer while the cat merely breathes. Real motion (enter, head turns, rise,
# walk) clears the threshold; a motionless cat collapses to one held frame, which
# is correct once playback is driven by per-frame timestamps.
#
# At 12, the long static "loaf" stretch (~4.5-13s) collapses to a handful of held
# frames while the enter/rise/exit motion keeps near-source density — verified by
# the per-second kept-frame histogram. This roughly halves the 60fps frame count
# (769 -> ~611) and the shipped PNG payload (73.5 -> ~57.5 MB) with no visible
# motion loss, since held still frames look identical whether stored once or 50x.
DEDUP_MSE = 12
DEDUP_SIG = 32

SCALE = 1.0  # keep native 1920x1080 detail; the runtime loads frames one at a
#              time from disk, so a high-res sequence costs disk but not memory.


def sample_times(start: float, end: float, fps: int) -> list[float]:
    step = 1.0 / fps
    out, t = [], start
    while t < end - 1e-6:
        out.append(t)
        t += step
    return out


def key_frame(bgr: np.ndarray) -> np.ndarray:
    """Green-screen key + despill -> BGRA. Alpha ramps on green excess
    (G - max(R, B)); green spill is removed by clamping green to max(red, blue)."""
    b = bgr[..., 0].astype(np.int16)
    g = bgr[..., 1].astype(np.int16)
    r = bgr[..., 2].astype(np.int16)
    green_excess = g - np.maximum(b, r)
    alpha = np.clip(
        (GREEN_HIGH - green_excess) / (GREEN_HIGH - GREEN_LOW) * 255.0, 0, 255
    )
    g_despilled = np.minimum(g, np.maximum(b, r))  # cut green where it dominates

    bgra = np.empty((bgr.shape[0], bgr.shape[1], 4), dtype=np.uint8)
    bgra[..., 0] = b.astype(np.uint8)
    bgra[..., 1] = g_despilled.astype(np.uint8)
    bgra[..., 2] = r.astype(np.uint8)
    bgra[..., 3] = alpha.astype(np.uint8)
    return bgra


def tight_bbox(bgra: np.ndarray) -> tuple[int, int, int, int] | None:
    """(x, y, w, h) of opaque region, or None if frame is empty."""
    mask = bgra[..., 3] >= BBOX_ALPHA_THRESHOLD
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


def mse(a: np.ndarray, b: np.ndarray) -> float:
    diff = a.astype(np.int32) - b.astype(np.int32)
    return float((diff ** 2).mean())


def dedup_signature(cropped: np.ndarray) -> np.ndarray:
    """A size-normalized gray thumbnail of the cat, for jitter-robust dedup."""
    gray = cv2.cvtColor(cropped[..., :3], cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (DEDUP_SIG, DEDUP_SIG), interpolation=cv2.INTER_AREA)


def extract_sequence(cap, start: float, end: float, fps: int, *, dedup_mse: float):
    """Yield (src_time, bbox, cropped) per kept non-empty frame in [start, end)."""
    last_sig = None
    for t in sample_times(start, end, fps):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, bgr = cap.read()
        if not ok:
            print(f"warn: read failed at t={t:.3f}s", file=sys.stderr)
            continue
        bgra = key_frame(bgr)
        bbox = tight_bbox(bgra)
        if bbox is None:
            continue  # cat not in frame (e.g. after it has walked off)
        x, y, w, h = bbox
        cropped = bgra[y:y + h, x:x + w]
        sig = dedup_signature(cropped)
        if dedup_mse > 0 and last_sig is not None and mse(sig, last_sig) < dedup_mse:
            continue
        yield t, bbox, cropped
        last_sig = sig


def maybe_scale(cropped: np.ndarray, bbox: tuple[int, int, int, int]):
    if SCALE == 1.0:
        return cropped, bbox
    x, y, w, h = bbox
    new_w = max(1, int(round(w * SCALE)))
    new_h = max(1, int(round(h * SCALE)))
    scaled = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_AREA)
    scaled_bbox = (int(round(x * SCALE)), int(round(y * SCALE)), new_w, new_h)
    return scaled, scaled_bbox


def write_quantized_png(bgra: np.ndarray, path: Path, colors: int = 64) -> None:
    """Write BGRA frame as a palette-quantized PNG via Pillow (5-8x smaller than full RGBA)."""
    rgba = cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGBA)
    img = Image.fromarray(rgba, mode="RGBA")
    img_p = img.quantize(colors=colors, method=Image.Quantize.FASTOCTREE)
    img_p.save(path, optimize=True)


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"source MP4 not found: {SRC}")

    if DST.exists():
        shutil.rmtree(DST)
    DST.mkdir(parents=True)

    cap = cv2.VideoCapture(str(SRC))
    if not cap.isOpened():
        raise SystemExit(f"failed to open {SRC}")

    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    canvas_w = int(round(src_w * SCALE))
    canvas_h = int(round(src_h * SCALE))

    fps = round(cap.get(cv2.CAP_PROP_FPS)) or FPS_FALLBACK

    print(f"source: {SRC.name}  ({src_w}x{src_h})")
    print(f"scale: {SCALE}, canvas: {canvas_w}x{canvas_h}")
    print(f"green-excess key low/high: {GREEN_LOW}/{GREEN_HIGH}")
    print(f"sample fps: {fps} (source), dedup mse: {DEDUP_MSE}")

    print("extracting sequence...")
    kept = list(extract_sequence(cap, *ARC, fps, dedup_mse=DEDUP_MSE))
    cap.release()
    if not kept:
        raise SystemExit("no non-empty frames extracted — check ARC / key settings")

    first_t = kept[0][0]
    last_t = kept[-1][0]
    span = (last_t - first_t) or 1.0

    frames = []
    for i, (src_t, bbox, cropped) in enumerate(kept, start=1):
        scaled, scaled_bbox = maybe_scale(cropped, bbox)
        write_quantized_png(scaled, DST / f"frame_{i:03d}.png")
        t_norm = (src_t - first_t) / span
        frames.append({"x": scaled_bbox[0], "y": scaled_bbox[1], "t": round(t_norm, 6)})

    print(f"  {len(frames)} frames kept ({first_t:.2f}s -> {last_t:.2f}s, span {span:.2f}s)")

    manifest = {
        "canvas": [canvas_w, canvas_h],
        "source_fps": fps,
        "arc_seconds": round(span, 3),
        "frame_count": len(frames),
        "frames": frames,
    }
    (DST / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    total_bytes = sum(p.stat().st_size for p in DST.glob("*.png"))
    print(f"\nwrote {len(frames)} PNGs + manifest.json to {DST}")
    print(f"total size: {total_bytes / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()

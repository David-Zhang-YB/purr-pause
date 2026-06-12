"""Extract walk_in / idle / walk_out PNG sprite sequences from the source MP4.

One-shot offline script. Run after the source video changes:

    python scripts/extract_cat_frames.py

Each frame is cropped to its own tight bounding box of opaque pixels and stored
with its (x, y) offset in `manifest.json`, so the runtime can paint a small
sprite at the original position — equivalent to the full-screen frame but a
fraction of the bytes.

Outputs into ../assets/cat_anim/:
  - manifest.json
  - walk_in_NN.png, idle_NN.png, walk_out_NN.png

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
SRC = ROOT / "assets" / "British Shorthair Silver Shaded Transparent.mp4"
DST = ROOT / "assets" / "cat_anim"

WALK_IN = (0.0, 6.1)
IDLE = (6.1, 10.5)
WALK_OUT = (10.5, 15.0)

WALK_FPS = 30
IDLE_FPS = 15

ALPHA_CUTOFF = 35
ALPHA_OPAQUE = 60

BBOX_ALPHA_THRESHOLD = 64

WALK_DEDUP_MSE = 100
IDLE_DEDUP_MSE = 4000

SCALE = 0.25


def sample_times(start: float, end: float, fps: int) -> list[float]:
    step = 1.0 / fps
    out, t = [], start
    while t < end - 1e-6:
        out.append(t)
        t += step
    return out


def bgr_to_bgra(bgr: np.ndarray) -> np.ndarray:
    b = bgr[..., 0].astype(np.int32)
    g = bgr[..., 1].astype(np.int32)
    r = bgr[..., 2].astype(np.int32)
    dist = np.sqrt(b * b + g * g + r * r)
    alpha = np.where(
        dist <= ALPHA_CUTOFF, 0.0,
        np.where(
            dist >= ALPHA_OPAQUE, 255.0,
            (dist - ALPHA_CUTOFF) / (ALPHA_OPAQUE - ALPHA_CUTOFF) * 255.0,
        ),
    )
    bgra = np.empty((bgr.shape[0], bgr.shape[1], 4), dtype=np.uint8)
    bgra[..., :3] = bgr
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
    if a.shape != b.shape:
        return float("inf")
    diff = a.astype(np.int32) - b.astype(np.int32)
    return float((diff ** 2).mean())


def extract_phase(cap, start: float, end: float, fps: int, *, dedup_mse: float = 0.0):
    """Yield (bgra_full, bbox, cropped) per kept frame in [start, end)."""
    last_kept = None
    for t in sample_times(start, end, fps):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, bgr = cap.read()
        if not ok:
            print(f"warn: read failed at t={t:.3f}s", file=sys.stderr)
            continue
        bgra = bgr_to_bgra(bgr)
        bbox = tight_bbox(bgra)
        if bbox is None:
            continue
        x, y, w, h = bbox
        cropped = bgra[y:y + h, x:x + w]
        if dedup_mse > 0 and last_kept is not None:
            if mse(cropped, last_kept) < dedup_mse:
                continue
        yield bbox, cropped
        last_kept = cropped


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


def save_phase(cap, name: str, start: float, end: float, fps: int, *, dedup_mse: float = 0.0):
    placements = []
    idx = 0
    for bbox, cropped in extract_phase(cap, start, end, fps, dedup_mse=dedup_mse):
        idx += 1
        scaled, scaled_bbox = maybe_scale(cropped, bbox)
        write_quantized_png(scaled, DST / f"{name}_{idx:02d}.png")
        placements.append({"x": scaled_bbox[0], "y": scaled_bbox[1]})
    return placements


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

    print(f"source: {SRC.name}  ({src_w}x{src_h})")
    print(f"scale: {SCALE}, canvas: {canvas_w}x{canvas_h}")
    print(f"alpha cutoff/opaque: {ALPHA_CUTOFF}/{ALPHA_OPAQUE}, bbox threshold: {BBOX_ALPHA_THRESHOLD}")
    print(f"walk fps: {WALK_FPS}, idle fps: {IDLE_FPS}, idle dedup mse: {IDLE_DEDUP_MSE}")

    print("extracting WALK_IN...")
    walk_in = save_phase(cap, "walk_in", *WALK_IN, WALK_FPS, dedup_mse=WALK_DEDUP_MSE)
    print(f"  {len(walk_in)} frames")

    print("extracting IDLE...")
    idle = save_phase(cap, "idle", *IDLE, IDLE_FPS, dedup_mse=IDLE_DEDUP_MSE)
    print(f"  {len(idle)} frames after dedup")

    print("extracting WALK_OUT...")
    walk_out = save_phase(cap, "walk_out", *WALK_OUT, WALK_FPS, dedup_mse=WALK_DEDUP_MSE)
    print(f"  {len(walk_out)} frames")

    cap.release()

    manifest = {
        "canvas": [canvas_w, canvas_h],
        "walk_fps": WALK_FPS,
        "idle_fps": IDLE_FPS,
        "walk_in": walk_in,
        "idle": idle,
        "walk_out": walk_out,
        "walk_in_count": len(walk_in),
        "idle_count": len(idle),
        "walk_out_count": len(walk_out),
    }
    (DST / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    total_bytes = sum(p.stat().st_size for p in DST.glob("*.png"))
    print(f"\nwrote {len(walk_in) + len(idle) + len(walk_out)} PNGs + manifest.json to {DST}")
    print(f"total size: {total_bytes / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()

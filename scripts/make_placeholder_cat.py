import os
import numpy as np
from PIL import Image, ImageDraw
from pathlib import Path

FUR = "#F09A3A"
FUR_DARK = "#C07820"
FUR_MID = "#E08830"
INNER_EAR = "#F4A8B8"
MUZZLE = "#FAD090"
IRIS = "#C8940A"
PUPIL = "#180C00"
NOSE = "#FF9AAA"
MOUTH = "#C07020"
WHISKER = "#B8A090"
BLUSH = (255, 155, 140, 90)

W, H = 300, 300
TRANSPARENT_IDX = 255


def _draw_eyes(d: ImageDraw.ImageDraw, blink: float) -> None:
    cx_L, cx_R, cy = 103, 197, 162
    hw = 24        # half-width  → eye width  = 48
    hh_open = 15   # half-height → eye height = 30

    hh = max(0, int(hh_open * (1.0 - blink)))

    for cx in (cx_L, cx_R):
        if blink >= 0.98:
            # Cute closed eye: slight downward arc
            d.arc([cx - hw, cy - 8, cx + hw, cy + 2], 0, 180, fill=FUR_DARK, width=3)
        else:
            ex1, ex2 = cx - hw, cx + hw
            ey1, ey2 = cy - hh, cy + hh

            # Iris (amber)
            d.ellipse([ex1, ey1, ex2, ey2], fill=IRIS)

            if hh > 5:
                # Vertical slit pupil
                pw = max(5, hh // 3 + 1)
                ph = hh - 1
                d.ellipse([cx - pw, cy - ph, cx + pw, cy + ph], fill=PUPIL)

                # Main sparkle highlight (upper-right)
                hs = max(4, hh // 4)
                d.ellipse([cx + 7, ey1 + 3, cx + 7 + hs, ey1 + 3 + hs], fill="white")
                # Tiny secondary highlight (upper-left)
                if hs > 4:
                    s2 = hs // 2 + 1
                    d.ellipse([cx - 10, ey1 + 8, cx - 10 + s2, ey1 + 8 + s2], fill="white")

            # Upper eyelid arc for definition
            d.arc([ex1 - 1, ey1 - 3, ex2 + 1, ey2], 205, 335, fill=FUR_DARK, width=2)


def _draw_cat(d: ImageDraw.ImageDraw, blink: float) -> None:
    # ── Ears (behind head) ───────────────────────────────────────
    d.polygon([(50, 95), (73, 8), (122, 73)], fill=FUR_MID, outline=FUR_DARK, width=2)
    d.polygon([(250, 95), (227, 8), (178, 73)], fill=FUR_MID, outline=FUR_DARK, width=2)
    # Inner ears (pink)
    d.polygon([(63, 87), (78, 25), (114, 73)], fill=INNER_EAR)
    d.polygon([(237, 87), (222, 25), (186, 73)], fill=INNER_EAR)

    # ── Head ─────────────────────────────────────────────────────
    d.ellipse([25, 65, 275, 288], fill=FUR, outline=FUR_DARK, width=3)

    # ── Muzzle patch (lighter oval) ───────────────────────────────
    d.ellipse([116, 193, 184, 253], fill=MUZZLE)

    # ── Forehead tabby stripes ────────────────────────────────────
    # Upper-arc portions of small ellipses (angles in Pillow: 0=right, 90=down, 270=top)
    d.arc([140, 106, 163, 133], 205, 335, fill=FUR_DARK, width=4)   # centre stripe
    d.arc([104, 112, 132, 134], 210, 335, fill=FUR_DARK, width=3)   # left stripe
    d.arc([168, 112, 196, 134], 205, 330, fill=FUR_DARK, width=3)   # right stripe

    # ── Eyes ─────────────────────────────────────────────────────
    _draw_eyes(d, blink)

    # ── Nose ─────────────────────────────────────────────────────
    d.polygon([(150, 206), (143, 218), (157, 218)], fill=NOSE, outline="#D06070", width=1)

    # ── Mouth (W-shape from two downward arcs) ────────────────────
    d.arc([134, 214, 152, 230], 0, 180, fill=MOUTH, width=2)
    d.arc([148, 214, 166, 230], 0, 180, fill=MOUTH, width=2)

    # ── Whiskers ─────────────────────────────────────────────────
    d.line([(28, 213), (128, 218)], fill=WHISKER, width=2)
    d.line([(24, 224), (127, 225)], fill=WHISKER, width=2)
    d.line([(30, 235), (128, 231)], fill=WHISKER, width=2)
    d.line([(172, 218), (272, 213)], fill=WHISKER, width=2)
    d.line([(173, 225), (276, 224)], fill=WHISKER, width=2)
    d.line([(172, 231), (270, 235)], fill=WHISKER, width=2)


def _make_frame(blink: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _draw_cat(d, blink)

    # Cheek blush via separate alpha layer for correct compositing
    blush = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blush)
    bd.ellipse([44, 192, 100, 235], fill=BLUSH)
    bd.ellipse([200, 192, 256, 235], fill=BLUSH)
    return Image.alpha_composite(img, blush)


def _to_gif_palette(img_rgba: Image.Image, frame_idx: int) -> Image.Image:
    """Convert RGBA frame to palette-mode GIF frame preserving transparency."""
    arr = np.array(img_rgba)
    transparent = arr[:, :, 3] < 128

    rgb_arr = arr[:, :, :3].copy().astype(np.uint8)
    # Unique corner pixel prevents Pillow from deduplicating visually identical frames
    rgb_arr[0, frame_idx % 10] = (
        (frame_idx * 37 + 30) % 200,
        (frame_idx * 59 + 30) % 200,
        (frame_idx * 83 + 30) % 200,
    )

    rgb = Image.fromarray(rgb_arr, "RGB")
    p = rgb.quantize(colors=TRANSPARENT_IDX, dither=Image.Dither.NONE)

    # Stamp transparent pixels with reserved index 255
    p_arr = np.array(p, dtype=np.uint8)
    p_arr[transparent] = TRANSPARENT_IDX

    palette = list(p.getpalette())
    palette[TRANSPARENT_IDX * 3: TRANSPARENT_IDX * 3 + 3] = [0, 0, 0]

    result = Image.fromarray(p_arr, "P")
    result.putpalette(palette)
    return result


def create_cat_gif() -> None:
    # 10-frame blink: 3 open frames, smooth close, closed, smooth open, 2 open frames
    sequence = [
        (0.00, 600),
        (0.00, 600),
        (0.00, 600),
        (0.25,  80),
        (0.60,  60),
        (1.00,  60),
        (0.60,  60),
        (0.25,  80),
        (0.00, 600),
        (0.00, 600),
    ]

    rgba_frames = [_make_frame(b) for b, _ in sequence]
    durations = [d for _, d in sequence]
    p_frames = [_to_gif_palette(f, i) for i, f in enumerate(rgba_frames)]

    out = Path(__file__).parent.parent / "assets" / "cat.gif"
    os.makedirs(out.parent, exist_ok=True)

    p_frames[0].save(
        out,
        save_all=True,
        append_images=p_frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
        transparency=TRANSPARENT_IDX,
        optimize=False,
    )
    print(f"Created {out}  ({len(p_frames)} frames)")


if __name__ == "__main__":
    create_cat_gif()

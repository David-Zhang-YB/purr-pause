import os
from PIL import Image, ImageDraw
from pathlib import Path

def create_cat_gif():
    frames = []
    for frame_idx, blink in enumerate((False, False, True, False)):
        img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # 头部
        d.ellipse([30, 40, 170, 170], fill="#F0A000", outline="#C07800", width=3)
        # 耳朵
        d.polygon([(38, 60), (55, 15), (80, 55)], fill="#F0A000", outline="#C07800", width=2)
        d.polygon([(120, 55), (145, 15), (162, 60)], fill="#F0A000", outline="#C07800", width=2)
        # 眼睛
        if blink:
            d.line([63, 90, 83, 90], fill="#333", width=4)
            d.line([117, 90, 137, 90], fill="#333", width=4)
        else:
            d.ellipse([63, 80, 83, 100], fill="#333")
            d.ellipse([117, 80, 137, 100], fill="#333")
            d.ellipse([70, 84, 77, 91], fill="white")
            d.ellipse([124, 84, 131, 91], fill="white")
        # 鼻子
        d.polygon([(100, 112), (94, 122), (106, 122)], fill="#FFB6C1")
        # 嘴巴
        d.arc([86, 118, 100, 132], 0, 180, fill="#C07800", width=2)
        d.arc([100, 118, 114, 132], 0, 180, fill="#C07800", width=2)
        # 胡须
        for y in [113, 124]:
            d.line([20, y, 88, y], fill="#C07800", width=2)
            d.line([112, y, 180, y], fill="#C07800", width=2)
        frames.append(img)

    out = Path(__file__).parent.parent / "assets" / "cat.gif"
    os.makedirs(out.parent, exist_ok=True)
    # Convert RGBA frames to palette mode for correct GIF encoding.
    # First convert to RGB to flatten transparency, then add a unique 1-pixel
    # marker per frame at position (0,0) so Pillow's GIF encoder does not merge
    # identical consecutive frames (it accumulates duration instead of emitting
    # a new frame when pixels are identical).
    rgb_frames = [f.convert("RGB") for f in frames]
    for i, f in enumerate(rgb_frames):
        f.putpixel((0, 0), (i, i, i))  # unique corner pixel, visually imperceptible
    p_frames = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=256) for f in rgb_frames]
    p_frames[0].save(
        out,
        save_all=True,
        append_images=p_frames[1:],
        duration=400,
        loop=0,
        disposal=2,
        optimize=False,
    )
    print(f"Created {out}")

if __name__ == "__main__":
    create_cat_gif()

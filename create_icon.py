"""
Run this script once to regenerate autocut.ico
Usage: python create_icon.py
"""
from PIL import Image, ImageDraw, ImageFont


def make_frame(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    m = max(1, size // 14)
    radius = size // 5

    draw.rounded_rectangle(
        [m, m, size - m, size - m],
        radius=radius,
        fill=(18, 18, 30, 255),
    )
    ring = max(1, size // 22)
    draw.rounded_rectangle(
        [m, m, size - m, size - m],
        radius=radius,
        outline=(139, 92, 246, 255),
        width=ring,
    )

    fs = max(6, int(size * 0.36))
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", fs)
    except Exception:
        try:
            font = ImageFont.truetype("arial.ttf", fs)
        except Exception:
            font = ImageFont.load_default()

    text = "AC"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        ((size - tw) // 2 - bbox[0], (size - th) // 2 - bbox[1]),
        text,
        fill=(255, 255, 255, 255),
        font=font,
    )
    return img


if __name__ == "__main__":
    icon_sizes = [256, 128, 64, 48, 32, 16]
    frames = [make_frame(s) for s in icon_sizes]
    frames[0].save(
        "autocut.ico",
        format="ICO",
        append_images=frames[1:],
        sizes=[(s, s) for s in icon_sizes],
    )
    import os
    print(f"autocut.ico created ({os.path.getsize('autocut.ico'):,} bytes)")

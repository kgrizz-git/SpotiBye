"""Generated, original album/playlist cover art for the screenshot fixture.

Every image is drawn with Pillow from a seeded random generator, so output is
deterministic and contains no real artwork, logos, or artist names. Fonts come
from Kivy's bundled Roboto (found by path, without importing Kivy) and fall
back to Pillow's default font.
"""

from __future__ import annotations

import importlib.util
import io
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 300

# Muted-to-bold palettes: (background, accent 1, accent 2, accent 3).
PALETTES: list[tuple[str, str, str, str]] = [
    ("#1f2a44", "#f2a65a", "#eeebdd", "#c0504d"),
    ("#e8dcc4", "#2f4858", "#d1603d", "#8a9a5b"),
    ("#0f0f10", "#f5f5f0", "#ff4f1f", "#7d7d7d"),
    ("#2d3a3a", "#9bc1bc", "#e6ebe0", "#ed6a5a"),
    ("#f4e4d4", "#b5524a", "#3b2f2f", "#e0a96d"),
    ("#14213d", "#fca311", "#e5e5e5", "#4a6fa5"),
    ("#3d2c4d", "#e3a6b4", "#f3e9dc", "#6c8ead"),
    ("#c9d6c3", "#2e4a3d", "#f1f1e6", "#d98e04"),
    ("#e63946", "#f1faee", "#1d3557", "#a8dadc"),
    ("#222831", "#00adb5", "#eeeeee", "#ffd369"),
    ("#f7ede2", "#84a59d", "#f28482", "#5e503f"),
    ("#4a4e69", "#c9ada7", "#f2e9e4", "#9a8c98"),
]


def make_rng(seed: int) -> random.Random:
    """Return the seeded generator used for all demo-fixture randomness."""
    # fmt: off
    return random.Random(seed)  # NOSONAR(S2245): deterministic demo fixture, not security-sensitive
    # fmt: on


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    spec = importlib.util.find_spec("kivy")
    if spec is not None and spec.origin:
        path = Path(spec.origin).parent / "data" / "fonts" / "Roboto-Bold.ttf"
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size)


def _stripes(rng: random.Random, pal: tuple[str, ...], _t: str, _a: str) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), pal[0])
    d = ImageDraw.Draw(img)
    width = rng.choice([20, 30, 50])
    for i, x in enumerate(range(-SIZE, SIZE * 2, width)):
        color = pal[1 + i % 3]
        d.polygon(
            [
                (x, 0),
                (x + width // 2, 0),
                (x + width // 2 + SIZE, SIZE),
                (x + SIZE, SIZE),
            ],
            fill=color,
        )
    return img


def _triangles(
    rng: random.Random, pal: tuple[str, ...], _t: str, _a: str
) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), pal[0])
    d = ImageDraw.Draw(img)
    for _ in range(9):
        cx, cy = rng.randint(0, SIZE), rng.randint(0, SIZE)
        r = rng.randint(40, 130)
        a = rng.uniform(0, math.tau)
        pts = [
            (cx + r * math.cos(a + k * 2.094), cy + r * math.sin(a + k * 2.094))
            for k in range(3)
        ]
        d.polygon(pts, fill=pal[1 + rng.randint(0, 2)])
    return img


def _grid(rng: random.Random, pal: tuple[str, ...], _t: str, _a: str) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), pal[0])
    d = ImageDraw.Draw(img)
    n = rng.choice([3, 4, 5])
    cell = SIZE // n
    round_cells = rng.random() < 0.5
    for gx in range(n):
        for gy in range(n):
            box = (
                gx * cell + 6,
                gy * cell + 6,
                (gx + 1) * cell - 6,
                (gy + 1) * cell - 6,
            )
            color = pal[1 + rng.randint(0, 2)]
            if round_cells:
                d.ellipse(box, fill=color)
            else:
                d.rectangle(box, fill=color)
    return img


def _blur_field(
    rng: random.Random, pal: tuple[str, ...], _t: str, _a: str
) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), pal[0])
    d = ImageDraw.Draw(img)
    for _ in range(6):
        r = rng.randint(60, 140)
        cx, cy = rng.randint(0, SIZE), rng.randint(0, SIZE)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=pal[1 + rng.randint(0, 2)])
    return img.filter(ImageFilter.GaussianBlur(38))


def _typographic(
    rng: random.Random, pal: tuple[str, ...], title: str, artist: str
) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), pal[0])
    d = ImageDraw.Draw(img)
    words = title.upper().split()
    px = 84
    big = _font(px)
    while px > 20 and max(d.textlength(w, font=big) for w in words) > SIZE - 32:
        px -= 4
        big = _font(px)
    y = 14
    for word in words[:3]:
        d.text((16, y), word, font=big, fill=pal[1])
        y += int(px * 0.95)
    d.rectangle((16, SIZE - 52, 16 + 90, SIZE - 46), fill=pal[2])
    d.text((16, SIZE - 38), artist.upper(), font=_font(18), fill=pal[2])
    return img


def _halftone(
    rng: random.Random, pal: tuple[str, ...], _t: str, _a: str
) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), pal[0])
    d = ImageDraw.Draw(img)
    step = 14
    cx, cy = rng.randint(60, 240), rng.randint(60, 240)
    for gx in range(0, SIZE, step):
        for gy in range(0, SIZE, step):
            dist = math.hypot(gx - cx, gy - cy) / 220
            r = max(0.0, 6.5 * (1 - dist))
            d.ellipse((gx - r, gy - r, gx + r, gy + r), fill=pal[1])
    return img


def _noise_duotone(
    rng: random.Random, pal: tuple[str, ...], _t: str, _a: str
) -> Image.Image:
    base = Image.new("RGB", (SIZE, SIZE), pal[0])
    d = ImageDraw.Draw(base)
    for _ in range(3):
        x, y = rng.randint(20, 160), rng.randint(20, 160)
        d.rectangle(
            (x, y, x + rng.randint(80, 140), y + rng.randint(80, 140)), fill=pal[1]
        )
    noise = Image.effect_noise((SIZE, SIZE), 60).convert("RGB")
    return Image.blend(base, noise, 0.22)


def _minimal(rng: random.Random, pal: tuple[str, ...], _t: str, _a: str) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), pal[0])
    d = ImageDraw.Draw(img)
    r = rng.randint(50, 90)
    cx, cy = SIZE // 2, rng.randint(110, 190)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=pal[1])
    return img


def _sunset(rng: random.Random, pal: tuple[str, ...], _t: str, _a: str) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), pal[0])
    d = ImageDraw.Draw(img)
    d.ellipse((90, 70, 210, 190), fill=pal[1])
    y = 170
    for i in range(4):
        h = rng.randint(30, 50)
        d.rectangle((0, y, SIZE, y + h), fill=pal[(i + 2) % 4])
        y += h - 6
    return img


def _rings(rng: random.Random, pal: tuple[str, ...], _t: str, _a: str) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), pal[0])
    d = ImageDraw.Draw(img)
    cx, cy = rng.randint(100, 200), rng.randint(100, 200)
    for i, r in enumerate(range(240, 0, -30)):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=pal[1 + i % 3])
    return img


STYLES = [
    _stripes, _triangles, _grid, _blur_field, _typographic,
    _halftone, _noise_duotone, _minimal, _sunset, _rings,
]  # fmt: skip


def make_album_cover(
    rng: random.Random, index: int, title: str, artist: str
) -> Image.Image:
    """Draw album cover ``index``; neighbouring indexes get different styles."""
    style = STYLES[index % len(STYLES)]
    palette = PALETTES[(index * 5 + index // len(STYLES)) % len(PALETTES)]
    return style(rng, palette, title, artist)


def mosaic(covers: list[Image.Image]) -> Image.Image:
    """Return a 2x2 mosaic of four covers, like a Spotify playlist cover."""
    half = SIZE // 2
    out = Image.new("RGB", (SIZE, SIZE))
    for i, cover in enumerate(covers[:4]):
        out.paste(
            cover.resize((half, half), Image.Resampling.LANCZOS),
            ((i % 2) * half, (i // 2) * half),
        )
    return out


def to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

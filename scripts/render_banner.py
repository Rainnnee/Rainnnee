#!/usr/bin/env python3
"""Render a coarse pixel-art LA banner and a restrained animated model pass."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/source/los-angeles-skyline-master.png"
STATIC = ROOT / "assets/banner-static.png"
ANIMATED = ROOT / "assets/banner.gif"

WIDTH, HEIGHT = 1200, 400
GRID_WIDTH, GRID_HEIGHT = 60, 20
TEXT_PIXEL_SIZE = 10
FRAME_COUNT = 8
FRAME_DURATION_MS = 360

TITLE = "#123B88"
TAGLINE = "#77305F"

PIXEL_GLYPHS = {
    "A": ("010", "101", "111", "101", "101"),
    "D": ("110", "101", "101", "101", "110"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("1", "1", "1", "1", "1"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("111", "101", "101", "101", "111"),
    "P": ("110", "101", "110", "100", "100"),
    "R": ("110", "101", "110", "101", "101"),
    "T": ("111", "010", "010", "010", "010"),
    "Σ": ("111", "100", "010", "001", "111"),
    "!": ("1", "1", "1", "0", "1"),
    "'": ("1", "1", "0", "0", "0"),
    "→": ("001", "011", "111", "011", "001"),
}

GREETING_GLYPHS = {
    "H": ("10", "10", "11", "10", "10"),
    "I": ("1", "1", "1", "1", "1"),
    "M": ("10", "11", "11", "10", "10"),
    "!": ("1", "1", "1", "0", "1"),
    "'": ("1", "1", "0", "0", "0"),
}

TAGLINE_GLYPHS = {
    "A": ("010", "101", "111"),
    "D": ("110", "101", "110"),
    "L": ("100", "100", "111"),
    "M": ("101", "111", "101"),
    "T": ("111", "010", "010"),
    "Σ": ("111", "100", "011"),
    "→": ("001", "011", "111"),
}


def draw_bitmap_line(
    image: Image.Image,
    text: str,
    y_origin: int,
    color: str,
    glyphs: dict[str, tuple[str, ...]] | None = None,
) -> None:
    """Draw centered bitmap text using square 10-pixel glyph cells."""
    glyphs = glyphs or PIXEL_GLYPHS
    spacing = 1
    widths = [1 if char == " " else len(glyphs[char][0]) for char in text]
    line_width = (sum(widths) + spacing * (len(text) - 1)) * TEXT_PIXEL_SIZE
    x = (image.width - line_width) // 2
    draw_bitmap_line_at(image, text, x, y_origin, color, glyphs)


def bitmap_width(text: str, glyphs: dict[str, tuple[str, ...]], spacing: int = 1) -> int:
    widths = [1 if char == " " else len(glyphs[char][0]) for char in text]
    return sum(widths) + spacing * (len(text) - 1)


def draw_title(image: Image.Image) -> None:
    """Add the pixel-art greeting and concise math-to-ML signature."""
    greeting = "HI! I'M"
    name = "RAIN PIAO"
    group_gap = 2
    full_width = (bitmap_width(greeting, GREETING_GLYPHS) + group_gap + bitmap_width(name, PIXEL_GLYPHS)) * TEXT_PIXEL_SIZE
    x = (image.width - full_width) // 2

    draw_bitmap_line_at(image, greeting, x, y_origin=16, color=TITLE, glyphs=GREETING_GLYPHS)
    x += (bitmap_width(greeting, GREETING_GLYPHS) + group_gap) * TEXT_PIXEL_SIZE
    draw_bitmap_line_at(image, name, x, y_origin=16, color=TITLE, glyphs=PIXEL_GLYPHS)
    draw_bitmap_line(image, "Σ DATA → ML", y_origin=76, color=TAGLINE, glyphs=TAGLINE_GLYPHS)


def draw_bitmap_line_at(
    image: Image.Image,
    text: str,
    x: int,
    y_origin: int,
    color: str,
    glyphs: dict[str, tuple[str, ...]],
) -> None:
    """Draw a bitmap text segment at an explicit grid coordinate."""
    draw = ImageDraw.Draw(image)
    spacing = 1
    widths = [1 if char == " " else len(glyphs[char][0]) for char in text]
    for char, glyph_width in zip(text, widths):
        if char == " ":
            x += (glyph_width + spacing) * TEXT_PIXEL_SIZE
            continue
        for y, row in enumerate(glyphs[char]):
            for column, pixel in enumerate(row):
                if pixel == "1":
                    x0 = x + column * TEXT_PIXEL_SIZE
                    y0 = y_origin + y * TEXT_PIXEL_SIZE
                    draw.rectangle((x0, y0, x0 + TEXT_PIXEL_SIZE - 1, y0 + TEXT_PIXEL_SIZE - 1), fill=color)
        x += (glyph_width + spacing) * TEXT_PIXEL_SIZE


def cloud_layer(source: Image.Image) -> tuple[Image.Image, list[tuple[int, int, tuple[int, int, int]]], list[list[bool]]]:
    """Separate soft cloud cells from the sky while preserving foreground silhouettes."""
    pixels = source.load()
    top_colors = [pixels[x, 0] for x in range(source.width) if pixels[x, 0][1] > 170 and pixels[x, 0][2] > 190]
    sky_fill = Counter(top_colors).most_common(1)[0][0] if top_colors else (0, 196, 239)

    def is_structure(color: tuple[int, int, int]) -> bool:
        red, green, blue = color
        return red < 110 and green < 180 and blue - green > 30

    structure_top: list[int] = []
    structure_mask = [[False] * source.width for _ in range(source.height)]
    for x in range(source.width):
        top = source.height
        for y in range(3, source.height):
            structure_mask[y][x] = is_structure(pixels[x, y])
            if structure_mask[y][x] and top == source.height:
                top = y
        structure_top.append(top)

    clouds: list[tuple[int, int, tuple[int, int, int]]] = []
    cloud_mask = [[False] * source.width for _ in range(source.height)]
    base = source.copy()
    base_pixels = base.load()
    for y in range(source.height):
        for x in range(source.width):
            red, green, blue = pixels[x, y]
            is_cloud = y < min(structure_top[x], 13) and red >= 90 and green >= 100 and blue >= 145
            if is_cloud:
                clouds.append((x, y, pixels[x, y]))
                cloud_mask[y][x] = True
                base_pixels[x, y] = sky_fill

    return base, clouds, structure_mask


def make_frames(background: Image.Image) -> list[Image.Image]:
    """Animate a slow, two-cell cloud drift while keeping city and title fixed."""
    cloud_base, clouds, structure_mask = cloud_layer(background)
    offsets = (0, 1, 2, 1, 0, -1, -2, -1)
    frames: list[Image.Image] = []

    for frame_index in range(FRAME_COUNT):
        frame = cloud_base.copy()
        frame_pixels = frame.load()
        offset = offsets[frame_index]
        for x, y, color in clouds:
            target_x = x + offset
            if 0 <= target_x < GRID_WIDTH and not structure_mask[y][target_x]:
                frame_pixels[target_x, y] = color
        frames.append(frame)

    return frames


def render() -> None:
    source = Image.open(SOURCE).convert("RGB")
    if source.width / source.height < 2.9:
        raise ValueError("The banner master must be a wide panorama (at least 2.9:1).")

    # Average the illustration into one 60 x 20 grid, then enlarge each cell
    # as a 20-pixel square. The shared grid keeps clouds, palms, and buildings
    # uniform while 32 colors retain the pink-to-cream cloud gradients.
    coarse = source.resize((GRID_WIDTH, GRID_HEIGHT), Image.Resampling.BOX)
    coarse = coarse.quantize(colors=32, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
    frames = make_frames(coarse)
    background = coarse.resize((WIDTH, HEIGHT), Image.Resampling.NEAREST)
    draw_title(background)
    enlarged_frames = [frame.resize((WIDTH, HEIGHT), Image.Resampling.NEAREST) for frame in frames]
    for frame in enlarged_frames:
        draw_title(frame)

    # A plain still gives readers a no-motion option; the GIF drifts only the
    # cloud layer. The name, skyline, Griffith Observatory, and palms stay fixed.
    background.save(STATIC, format="PNG", optimize=True)
    palette = enlarged_frames[0].quantize(colors=32, method=Image.Quantize.MEDIANCUT)
    indexed = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in enlarged_frames]
    indexed[0].save(
        ANIMATED,
        format="GIF",
        save_all=True,
        append_images=indexed[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=True,
        disposal=1,
    )


if __name__ == "__main__":
    render()

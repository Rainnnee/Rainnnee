#!/usr/bin/env python3
"""Add a restrained pixel-font greeting to the full-resolution LA banner."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/source/los-angeles-skyline-master.png"
STATIC = ROOT / "assets/banner-static.png"

INK = "#123B88"
GLYPHS: dict[str, tuple[str, ...]] = {
    # 8 × 12 bitmap glyphs keep the lettering crisp at the full 2172 px width.
    "A": ("00011000", "00100100", "01000010", "01000010", "01111110", "01000010", "01000010", "01000010", "01000010", "01000010", "01000010", "00000000"),
    "D": ("01111100", "01000010", "01000010", "01000010", "01000010", "01000010", "01000010", "01000010", "01000010", "01000010", "01111100", "00000000"),
    "H": ("01000010", "01000010", "01000010", "01000010", "01111110", "01000010", "01000010", "01000010", "01000010", "01000010", "01000010", "00000000"),
    "I": ("00111100", "00011000", "00011000", "00011000", "00011000", "00011000", "00011000", "00011000", "00011000", "00011000", "00111100", "00000000"),
    "L": ("01000000", "01000000", "01000000", "01000000", "01000000", "01000000", "01000000", "01000000", "01000000", "01000000", "01111110", "00000000"),
    "M": ("01000010", "01100110", "01011010", "01011010", "01000010", "01000010", "01000010", "01000010", "01000010", "01000010", "01000010", "00000000"),
    "N": ("01000010", "01100010", "01010010", "01010010", "01001010", "01001010", "01000110", "01000110", "01000010", "01000010", "01000010", "00000000"),
    "O": ("00011000", "00100100", "01000010", "01000010", "01000010", "01000010", "01000010", "01000010", "01000010", "00100100", "00011000", "00000000"),
    "P": ("01111100", "01000010", "01000010", "01000010", "01000010", "01111100", "01000000", "01000000", "01000000", "01000000", "01000000", "00000000"),
    "R": ("01111100", "01000010", "01000010", "01000010", "01000010", "01111100", "01010000", "01001000", "01000100", "01000010", "01000010", "00000000"),
    "T": ("01111110", "00011000", "00011000", "00011000", "00011000", "00011000", "00011000", "00011000", "00011000", "00011000", "00011000", "00000000"),
    "Σ": ("01111110", "01000000", "00100000", "00100000", "00010000", "00001000", "00000100", "00001000", "00010000", "00100000", "01111110", "00000000"),
    "!": ("00011000", "00011000", "00011000", "00011000", "00011000", "00011000", "00011000", "00000000", "00011000", "00011000", "00011000", "00000000"),
    "'": ("00011000", "00011000", "00011000", "00011000", "00011000", "00000000", "00000000", "00000000", "00000000", "00000000", "00000000", "00000000"),
    "→": ("00011000", "00001100", "00000110", "11111111", "11111111", "00000110", "00001100", "00011000", "00000000", "00000000", "00000000", "00000000"),
}


def line_width(text: str, cell: int) -> int:
    columns = sum(4 if char == " " else len(GLYPHS[char][0]) for char in text)
    return (columns + 2 * (len(text) - 1)) * cell


def draw_line(image: Image.Image, text: str, y: int, cell: int) -> None:
    x = (image.width - line_width(text, cell)) // 2
    draw = ImageDraw.Draw(image)
    for index, char in enumerate(text):
        if char == " ":
            x += 4 * cell
            if index < len(text) - 1:
                x += 2 * cell
            continue
        glyph = GLYPHS[char]
        for row, bits in enumerate(glyph):
            for column, bit in enumerate(bits):
                if bit == "1":
                    x0, y0 = x + column * cell, y + row * cell
                    draw.rectangle((x0, y0, x0 + cell - 1, y0 + cell - 1), fill=INK)
        x += len(glyph[0]) * cell
        if index < len(text) - 1:
            x += 2 * cell


def render() -> None:
    with Image.open(SOURCE) as source:
        image = source.convert("RGB")
    if image.width / image.height < 2.9:
        raise ValueError("The banner master must be a wide panorama (at least 2.9:1).")

    # Preserve the supplied high-resolution scene and keep the banner still.
    draw_line(image, "HI! I'M RAIN PIAO", y=28, cell=5)
    draw_line(image, "Σ DATA → ML", y=100, cell=4)
    image.save(STATIC, format="PNG", optimize=True)


if __name__ == "__main__":
    render()

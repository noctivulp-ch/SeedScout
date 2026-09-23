"""Mapa PNG a partir de un `WorldSample`: color de bioma con sombreado por altura."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .colors import biome_color, pretty
from .world import WorldSample

SEA_LEVEL = 63


@dataclass
class MapImage:
    image: Image.Image
    blocks_per_pixel: int
    origin: tuple[int, int]
    legend: list[tuple[str, int]]


def _font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_biomes(sample: WorldSample, blocks_per_pixel: int = 2, shade: bool = True) -> MapImage:
    if not sample.chunks:
        raise ValueError("el muestreo no tiene ningún chunk: ¿se generó el mundo?")
    min_cx, min_cz, max_cx, max_cz = sample.bounds
    step = blocks_per_pixel
    width = ((max_cx - min_cx + 1) * 16) // step
    height = ((max_cz - min_cz + 1) * 16) // step
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    heights = np.full((height, width), np.nan, dtype=np.float32)

    cache: dict[str, tuple[int, int, int]] = {}
    for (cx, cz), chunk in sample.chunks.items():
        base_x = ((cx - min_cx) * 16) // step
        base_z = ((cz - min_cz) * 16) // step
        for index in range(0, 256, 1):
            bx, bz = index % 16, index // 16
            if bx % step or bz % step:
                continue
            px, pz = base_x + bx // step, base_z + bz // step
            if px >= width or pz >= height:
                continue
            name = chunk.biomes[index]
            color = cache.get(name)
            if color is None:
                color = cache[name] = biome_color(name)
            rgb[pz, px] = color
            heights[pz, px] = chunk.heights[index]

    if shade:
        filled = ~np.isnan(heights)
        filled_heights = np.where(filled, heights, SEA_LEVEL)
        north = np.roll(filled_heights, 1, axis=0)
        west = np.roll(filled_heights, 1, axis=1)
        slope = (filled_heights - (north + west) / 2.0)
        factor = np.clip(1.0 + np.clip(slope, -12, 12) * 0.035, 0.55, 1.45)
        rgb = np.clip(rgb.astype(np.float32) * factor[:, :, None], 0, 255).astype(np.uint8)

    counts = sample.biome_counts()
    legend = sorted(counts.items(), key=lambda kv: -kv[1])
    return MapImage(
        image=Image.fromarray(rgb, "RGB"),
        blocks_per_pixel=step,
        origin=(min_cx * 16, min_cz * 16),
        legend=legend,
    )


def with_overlay(rendered: MapImage, seed: int, title: str = "") -> Image.Image:
    """La versión para compartir: el mapa y la semilla, nada más."""
    map_image = rendered.image
    scale = max(1, min(3, 900 // max(map_image.width, 1)))
    if scale > 1:
        map_image = map_image.resize((map_image.width * scale, map_image.height * scale), Image.NEAREST)

    pad, header = 16, 46
    canvas = Image.new("RGB", (map_image.width + pad * 2, map_image.height + header + pad), (22, 24, 28))
    canvas.paste(map_image, (pad, header))
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, 12), title or "DeceasedCraft", font=_font(19), fill=(236, 238, 242))
    seed_text = f"Semilla: {seed}"
    font = _font(19)
    draw.text((canvas.width - pad - draw.textlength(seed_text, font=font), 12), seed_text, font=font, fill=(255, 196, 96))
    return canvas


def _wrap(text: str, font, width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines():
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if draw.textlength(candidate, font=font) <= width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current)
    return lines

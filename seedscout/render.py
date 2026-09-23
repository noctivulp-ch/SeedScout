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


def with_overlay(
    rendered: MapImage,
    seed: int,
    notes: str = "",
    title: str = "",
    max_legend: int = 12,
) -> Image.Image:
    """La versión para compartir: mapa, semilla, leyenda de biomas y notas rotuladas."""
    map_image = rendered.image
    scale = max(1, min(3, 900 // max(map_image.width, 1)))
    if scale > 1:
        map_image = map_image.resize((map_image.width * scale, map_image.height * scale), Image.NEAREST)

    pad, side = 16, 320
    header = 64
    total = sum(count for _, count in rendered.legend) or 1
    body = max(map_image.height, 22 * min(len(rendered.legend), max_legend) + 120)
    canvas = Image.new("RGB", (map_image.width + side + pad * 3, body + header + pad * 2), (22, 24, 28))
    canvas.paste(map_image, (pad, header + pad))
    draw = ImageDraw.Draw(canvas)

    draw.text((pad, 14), title or "SeedScout — DeceasedCraft", font=_font(22), fill=(236, 238, 242))
    draw.text((pad, 40), f"Semilla: {seed}", font=_font(17), fill=(255, 196, 96))

    x = pad * 2 + map_image.width
    y = header + pad
    draw.text((x, y), "Biomas", font=_font(17), fill=(236, 238, 242))
    y += 26
    for name, count in rendered.legend[:max_legend]:
        draw.rectangle([x, y + 3, x + 14, y + 15], fill=biome_color(name))
        share = 100.0 * count / total
        draw.text((x + 22, y), f"{pretty(name)} · {share:.1f}%", font=_font(14), fill=(206, 210, 216))
        y += 21
    if len(rendered.legend) > max_legend:
        draw.text((x, y), f"y {len(rendered.legend) - max_legend} más", font=_font(13), fill=(150, 154, 160))
        y += 24

    if notes.strip():
        y += 12
        draw.text((x, y), "Notas", font=_font(17), fill=(236, 238, 242))
        y += 24
        font = _font(14)
        for line in _wrap(notes.strip(), font, side - 10, draw):
            draw.text((x, y), line, font=font, fill=(206, 210, 216))
            y += 18

    scale_blocks = rendered.blocks_per_pixel * (1.0 / scale)
    draw.text(
        (pad, canvas.height - 22),
        f"1 px = {scale_blocks:g} bloques · origen {rendered.origin[0]}, {rendered.origin[1]}",
        font=_font(13),
        fill=(150, 154, 160),
    )
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

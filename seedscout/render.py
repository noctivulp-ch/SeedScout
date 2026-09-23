"""Mapa PNG del mundo, al estilo de los mapeadores de Minecraft.

El color sale del **bloque de superficie**, no del bioma: es como lo hacen uNmINeD (que calcula los
colores desde el jar del cliente), Xaero's y JourneyMap. Encima van las tres capas que dan el
aspecto reconocible de un mapa de Minecraft: tinte de bioma en hierba y follaje, agua oscurecida
según su profundidad, y sombreado por la pendiente del terreno.

Los chunks que Chunky dejó a medias no tienen bloques, solo bioma y altura; esos se pintan con el
color del bioma para que el mapa no salga con agujeros.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .biomeinfo import BiomeLook
from .colors import biome_color, pretty
from .world import WorldSample

SEA_LEVEL = 63
GRASS_TINTED = ("grass_block", "grass", "fern", "sugar_cane", "tall_grass", "large_fern",
                "moss_block", "moss_carpet", "lily_pad")
FOLIAGE_TINTED = ("leaves", "vine")
WATER_BLOCKS = {"minecraft:water", "minecraft:flowing_water", "minecraft:bubble_column"}
SPAWN_OUTLINE = (255, 196, 96)


@dataclass
class MapImage:
    image: Image.Image
    blocks_per_pixel: int
    origin: tuple[int, int]
    legend: list[tuple[str, int]]
    # Para saber qué hay bajo el cursor sin volver a leer el mundo.
    biome_at: np.ndarray | None = None
    height_at: np.ndarray | None = None
    block_at: np.ndarray | None = None
    names: list[str] = field(default_factory=list)
    block_names: list[str] = field(default_factory=list)

    def probe(self, px: int, py: int) -> dict | None:
        """Bioma, bloque, altura y coordenadas de mundo de un píxel del mapa."""
        if self.biome_at is None or not (0 <= py < self.biome_at.shape[0] and 0 <= px < self.biome_at.shape[1]):
            return None
        index = int(self.biome_at[py, px])
        if index < 0:
            return None
        block_index = int(self.block_at[py, px]) if self.block_at is not None else -1
        return {
            "biome": pretty(self.names[index]),
            "biome_id": self.names[index],
            # En los chunks que Chunky dejó a medias no hay bloques: se calla en vez de decir "Aire".
            "block": pretty(self.block_names[block_index]) if block_index >= 0
                     and self.block_names[block_index] != "minecraft:air" else "",
            "y": int(self.height_at[py, px]) if self.height_at is not None else 0,
            "x": self.origin[0] + px * self.blocks_per_pixel,
            "z": self.origin[1] + py * self.blocks_per_pixel,
        }


def _font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _block_color(block: str, table: dict[str, tuple[int, int, int]]) -> tuple[int, int, int] | None:
    color = table.get(block)
    if color:
        return color
    # snow_block usa la textura "snow", y muchos mods nombran igual: se prueba sin el sufijo.
    if block.endswith("_block"):
        return table.get(block[: -len("_block")])
    return None


def _tint(base: tuple[int, int, int], tint: tuple[int, int, int]) -> tuple[int, int, int]:
    return (base[0] * tint[0] // 255, base[1] * tint[1] // 255, base[2] * tint[2] // 255)


def render_terrain(
    sample: WorldSample,
    block_colors: dict[str, tuple[int, int, int]],
    biome_looks: dict[str, BiomeLook],
    blocks_per_pixel: int = 2,
    shade: bool = True,
    spawn: tuple[int, int] | None = None,
) -> MapImage:
    if not sample.chunks:
        raise ValueError("el muestreo no tiene ningún chunk: ¿se generó el mundo?")
    min_cx, min_cz, max_cx, max_cz = sample.bounds
    step = blocks_per_pixel
    width = ((max_cx - min_cx + 1) * 16) // step
    height = ((max_cz - min_cz + 1) * 16) // step

    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    heights = np.full((height, width), np.nan, dtype=np.float32)
    biome_at = np.full((height, width), -1, dtype=np.int32)
    block_at = np.full((height, width), -1, dtype=np.int32)

    names: list[str] = []
    name_index: dict[str, int] = {}
    block_names: list[str] = []
    block_index: dict[str, int] = {}
    cache: dict[tuple[str, str, int], tuple[int, int, int]] = {}

    for (cx, cz), chunk in sample.chunks.items():
        base_x = ((cx - min_cx) * 16) // step
        base_z = ((cz - min_cz) * 16) // step
        for index in range(256):
            bx, bz = index % 16, index // 16
            if bx % step or bz % step:
                continue
            px, pz = base_x + bx // step, base_z + bz // step
            if px >= width or pz >= height:
                continue

            biome = chunk.biomes[index]
            block = chunk.blocks[index]
            depth = chunk.water_depth[index]
            key = (biome, block, min(depth, 24))
            color = cache.get(key)
            if color is None:
                look = biome_looks.get(biome)
                base = _block_color(block, block_colors)
                if block in WATER_BLOCKS:
                    water = look.water if look else (63, 118, 228)
                    darken = 1.0 - min(depth, 24) / 24.0 * 0.55
                    color = tuple(int(c * darken) for c in water)  # type: ignore[assignment]
                elif base is None:
                    color = biome_color(biome)
                else:
                    short = block.split(":")[-1]
                    if look and any(short.endswith(s) or short == s for s in GRASS_TINTED):
                        color = _tint(base, look.grass)
                    elif look and any(s in short for s in FOLIAGE_TINTED):
                        color = _tint(base, look.foliage)
                    else:
                        color = base
                cache[key] = color

            rgb[pz, px] = color
            heights[pz, px] = chunk.heights[index]
            if biome not in name_index:
                name_index[biome] = len(names)
                names.append(biome)
            biome_at[pz, px] = name_index[biome]
            if block not in block_index:
                block_index[block] = len(block_names)
                block_names.append(block)
            block_at[pz, px] = block_index[block]

    if shade:
        filled = ~np.isnan(heights)
        surface = np.where(filled, heights, SEA_LEVEL)
        north = np.roll(surface, 1, axis=0)
        west = np.roll(surface, 1, axis=1)
        # Como en los mapeadores del juego: una cara mira al norte y otra al oeste, y la pendiente
        # respecto a esos dos vecinos decide si el píxel se aclara o se oscurece.
        slope = (surface - north) * 0.7 + (surface - west) * 0.3
        factor = np.clip(1.0 + np.clip(slope, -8, 8) * 0.055, 0.55, 1.5)
        rgb = np.clip(rgb.astype(np.float32) * factor[:, :, None], 0, 255).astype(np.uint8)

    image = Image.fromarray(rgb, "RGB")
    counts = sample.biome_counts()
    rendered = MapImage(
        image=image,
        blocks_per_pixel=step,
        origin=(min_cx * 16, min_cz * 16),
        legend=sorted(counts.items(), key=lambda kv: -kv[1]),
        biome_at=biome_at,
        height_at=np.nan_to_num(heights).astype(np.int32),
        block_at=block_at,
        names=names,
        block_names=block_names,
    )
    if spawn is not None:
        mark_spawn(rendered, spawn)
    return rendered


def mark_spawn(rendered: MapImage, spawn: tuple[int, int]) -> None:
    """Recuadra el chunk del spawn y su vecindario inmediato, que es donde caen los jugadores."""
    draw = ImageDraw.Draw(rendered.image)
    step = rendered.blocks_per_pixel
    ox, oz = rendered.origin
    chunk_x, chunk_z = spawn[0] >> 4, spawn[1] >> 4
    for radius, colour, width in ((1, (0, 0, 0), 1), (0, SPAWN_OUTLINE, 1)):
        x0 = ((chunk_x - radius) * 16 - ox) // step
        z0 = ((chunk_z - radius) * 16 - oz) // step
        x1 = ((chunk_x + radius + 1) * 16 - ox) // step - 1
        z1 = ((chunk_z + radius + 1) * 16 - oz) // step - 1
        draw.rectangle([x0, z0, x1, z1], outline=colour, width=width)
    px = (spawn[0] - ox) // step
    pz = (spawn[1] - oz) // step
    draw.line([px - 3, pz, px + 3, pz], fill=SPAWN_OUTLINE)
    draw.line([px, pz - 3, px, pz + 3], fill=SPAWN_OUTLINE)


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


def render_biomes(sample: WorldSample, blocks_per_pixel: int = 2, shade: bool = True) -> MapImage:
    """Mapa plano de biomas: se mantiene para mundos leídos sin tabla de colores de bloques."""
    return render_terrain(sample, {}, {}, blocks_per_pixel=blocks_per_pixel, shade=shade)

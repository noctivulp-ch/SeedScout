"""Del mundo generado al mapa: bioma de superficie y altura por columna."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .nbt import RegionFile, unpack_bits


@dataclass
class ChunkMap:
    """Bioma y altura de las 16x16 columnas de un chunk, en orden z*16+x."""

    cx: int
    cz: int
    biomes: list[str]
    heights: list[int]


@dataclass
class WorldSample:
    """Muestreo de un mundo ya generado, listo para pintar."""

    chunks: dict[tuple[int, int], ChunkMap] = field(default_factory=dict)
    min_y: int = -64

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        xs = [c[0] for c in self.chunks]
        zs = [c[1] for c in self.chunks]
        return min(xs), min(zs), max(xs), max(zs)

    def biome_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for chunk in self.chunks.values():
            for biome in chunk.biomes:
                counts[biome] = counts.get(biome, 0) + 1
        return counts


def _section_biomes(section: dict) -> tuple[list[str], list[int]] | None:
    biomes = section.get("biomes")
    if not isinstance(biomes, dict):
        return None
    palette = biomes.get("palette") or []
    if not palette:
        return None
    data = biomes.get("data")
    if not data:
        return palette, [0] * 64
    bits = max(1, (len(palette) - 1).bit_length())
    return palette, unpack_bits(data, bits, 64)


def read_chunk(nbt: dict, cx: int, cz: int, min_y: int = -64) -> ChunkMap | None:
    """Altura de superficie por columna y el bioma que hay a esa altura."""
    heightmaps = nbt.get("Heightmaps") or {}
    packed = heightmaps.get("WORLD_SURFACE") or heightmaps.get("MOTION_BLOCKING")
    if not packed:
        return None
    raw_heights = unpack_bits(packed, 9, 256)
    heights = [min_y + value - 1 for value in raw_heights]

    sections: dict[int, tuple[list[str], list[int]]] = {}
    for section in nbt.get("sections") or []:
        parsed = _section_biomes(section)
        if parsed:
            sections[int(section.get("Y", 0))] = parsed
    if not sections:
        return None

    lowest = min(sections)
    biomes: list[str] = []
    for index in range(256):
        x, z = index % 16, index // 16
        y = heights[index]
        section_y = y >> 4
        entry = sections.get(section_y) or sections.get(lowest)
        palette, data = entry
        local = ((y & 15) >> 2) * 16 + (z >> 2) * 4 + (x >> 2)
        biomes.append(palette[data[local]] if data[local] < len(palette) else palette[0])
    return ChunkMap(cx=cx, cz=cz, biomes=biomes, heights=heights)


def sample_world(world_dir: Path, dimension: str = "overworld", limit_chunks: int | None = None) -> WorldSample:
    """Lee todas las regiones de una dimensión. `limit_chunks` acota el trabajo en pruebas."""
    region_dir = world_dir / "region" if dimension == "overworld" else world_dir / "dimensions" / dimension / "region"
    if not region_dir.is_dir():
        alt = world_dir / "dimensions" / "minecraft" / dimension / "region"
        region_dir = alt if alt.is_dir() else region_dir
    sample = WorldSample()
    for path in sorted(region_dir.glob("r.*.mca")):
        region = RegionFile.open(path)
        for cx, cz in region.chunk_coords():
            nbt = region.chunk(cx, cz)
            if not nbt:
                continue
            chunk = read_chunk(nbt, cx, cz)
            if chunk:
                sample.chunks[(cx, cz)] = chunk
            if limit_chunks and len(sample.chunks) >= limit_chunks:
                return sample
    return sample

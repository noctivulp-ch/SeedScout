"""Del mundo generado al mapa: bioma de superficie y altura por columna."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .nbt import RegionFile, unpack_bits


@dataclass
class ChunkMap:
    """Lo que se ve desde arriba en las 16x16 columnas de un chunk, en orden z*16+x."""

    cx: int
    cz: int
    biomes: list[str]
    heights: list[int]
    blocks: list[str]
    # Bloques de agua sobre el suelo: sirve para oscurecer el mar según su profundidad.
    water_depth: list[int]


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


def _unpack_states(section: dict) -> tuple[list[str], np.ndarray] | None:
    """Paleta y 4096 índices de los bloques de una sección (formato 1.16+, sin cruzar longs)."""
    states = section.get("block_states")
    if not isinstance(states, dict):
        return None
    palette = [entry.get("Name", "minecraft:air") for entry in states.get("palette") or []
               if isinstance(entry, dict)]
    if not palette:
        return None
    data = states.get("data")
    if not data:
        return palette, np.zeros(4096, dtype=np.int32)
    bits = max(4, (len(palette) - 1).bit_length())
    per_long = 64 // bits
    # El NBT trae longs con signo; se reinterpretan sin signo para poder desplazar bits.
    words = np.array(data, dtype=np.int64).view(np.uint64)
    shifts = (np.arange(per_long, dtype=np.uint64) * np.uint64(bits))
    values = (words[:, None] >> shifts[None, :]) & np.uint64((1 << bits) - 1)
    flat = values.astype(np.int32).reshape(-1)[:4096]
    if flat.size < 4096:
        flat = np.pad(flat, (0, 4096 - flat.size))
    return palette, flat


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


WATER_BLOCKS = {"minecraft:water", "minecraft:flowing_water", "minecraft:bubble_column"}


def read_chunk(nbt: dict, cx: int, cz: int, min_y: int = -64) -> ChunkMap | None:
    """Por columna: altura de superficie, bioma a esa altura, bloque visible y profundidad del agua."""
    heightmaps = nbt.get("Heightmaps") or {}
    packed = heightmaps.get("WORLD_SURFACE") or heightmaps.get("MOTION_BLOCKING")
    if not packed:
        return None
    raw_heights = unpack_bits(packed, 9, 256)
    heights = [min_y + value - 1 for value in raw_heights]
    floor_packed = heightmaps.get("OCEAN_FLOOR")
    floors = [min_y + v - 1 for v in unpack_bits(floor_packed, 9, 256)] if floor_packed else heights

    sections: dict[int, tuple[list[str], list[int]]] = {}
    for section in nbt.get("sections") or []:
        parsed = _section_biomes(section)
        if parsed:
            sections[int(section.get("Y", 0))] = parsed
    if not sections:
        return None

    states: dict[int, tuple[list[str], np.ndarray]] = {}
    for section in nbt.get("sections") or []:
        parsed = _unpack_states(section)
        if parsed:
            states[int(section.get("Y", 0))] = parsed

    lowest = min(sections)
    biomes: list[str] = []
    blocks: list[str] = []
    depths: list[int] = []
    for index in range(256):
        x, z = index % 16, index // 16
        y = heights[index]
        section_y = y >> 4
        palette, data = sections.get(section_y) or sections[lowest]
        local = ((y & 15) >> 2) * 16 + (z >> 2) * 4 + (x >> 2)
        biomes.append(palette[data[local]] if data[local] < len(palette) else palette[0])

        block = "minecraft:air"
        entry = states.get(section_y)
        if entry:
            block_palette, indices = entry
            slot = indices[(y & 15) * 256 + z * 16 + x]
            if slot < len(block_palette):
                block = block_palette[slot]
        blocks.append(block)
        depths.append(max(0, y - floors[index]) if block in WATER_BLOCKS else 0)
    return ChunkMap(cx=cx, cz=cz, biomes=biomes, heights=heights, blocks=blocks, water_depth=depths)


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


def read_spawn(world_dir: Path) -> tuple[int, int] | None:
    """Spawn del mundo, de `level.dat`. Es donde aparecen los jugadores nuevos."""
    level = world_dir / "level.dat"
    if not level.exists():
        return None
    from .nbt import parse_nbt

    data = parse_nbt(level.read_bytes()).get("Data") or {}
    if "SpawnX" not in data or "SpawnZ" not in data:
        return None
    return int(data["SpawnX"]), int(data["SpawnZ"])

"""Detección de las ciudades de Lost Cities sobre el mundo ya generado.

El pack corre con `generate-structures=false`, así que en el overworld no hay aldeas, templos ni
minas: **todo bloque manufacturado que aparece es de Lost Cities**. Eso permite marcar un chunk
como urbano por la presencia de bloques de construcción, sin reimplementar el ruido del mod.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .nbt import RegionFile

BUILDING_BLOCKS = {
    "minecraft:cyan_terracotta",
    "minecraft:gray_terracotta",
    "minecraft:quartz_block",
    "minecraft:quartz_bricks",
    "minecraft:smooth_quartz",
    "minecraft:stone_bricks",
    "minecraft:mossy_stone_bricks",
    "minecraft:bricks",
    "minecraft:daylight_detector",
    "quark:black_framed_glass",
    "create:framed_glass",
    "immersiveengineering:concrete",
    "immersiveengineering:slab_steel_scaffolding_standard",
}
STREET_BLOCKS = {
    "minecraft:smooth_stone",
    "minecraft:smooth_stone_slab",
    "minecraft:stone_brick_slab",
    "minecraft:stone_slab",
    "minecraft:quartz_slab",
}
LIGHT_PREFIXES = ("simplylight:", "refurbished_furniture:light_")


@dataclass
class CityChunk:
    cx: int
    cz: int
    kind: str
    top: int


def classify(nbt: dict) -> CityChunk | None:
    """`building` si hay bloques de edificio, `street` si solo de calle, None si no hay ciudad."""
    building = street = False
    top = -64
    for section in nbt.get("sections") or []:
        palette = (section.get("block_states") or {}).get("palette") or []
        names = {entry.get("Name") for entry in palette if isinstance(entry, dict)}
        hit_building = bool(names & BUILDING_BLOCKS) or any(
            name.startswith(LIGHT_PREFIXES) for name in names if name
        )
        hit_street = bool(names & STREET_BLOCKS)
        if hit_building or hit_street:
            top = max(top, int(section.get("Y", 0)) * 16 + 15)
        building = building or hit_building
        street = street or hit_street
    if not (building or street):
        return None
    return CityChunk(cx=0, cz=0, kind="building" if building else "street", top=top)


def scan(world_dir: Path, dimension: str = "overworld") -> dict[tuple[int, int], CityChunk]:
    region_dir = world_dir / "region"
    if not region_dir.is_dir():
        region_dir = world_dir / "dimensions" / "minecraft" / dimension / "region"
    found: dict[tuple[int, int], CityChunk] = {}
    for path in sorted(region_dir.glob("r.*.mca")):
        region = RegionFile.open(path)
        for cx, cz in region.chunk_coords():
            nbt = region.chunk(cx, cz)
            if not nbt or nbt.get("Status") != "minecraft:full":
                continue
            hit = classify(nbt)
            if hit:
                hit.cx, hit.cz = cx, cz
                found[(cx, cz)] = hit
    return found


def clusters(found: dict[tuple[int, int], CityChunk]) -> list[dict]:
    """Agrupa chunks urbanos contiguos: cada grupo es una ciudad, con su centro y tamaño."""
    pending = set(found)
    out: list[dict] = []
    while pending:
        seed = pending.pop()
        group = [seed]
        stack = [seed]
        while stack:
            cx, cz = stack.pop()
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    neighbour = (cx + dx, cz + dz)
                    if neighbour in pending:
                        pending.remove(neighbour)
                        group.append(neighbour)
                        stack.append(neighbour)
        xs = [c[0] for c in group]
        zs = [c[1] for c in group]
        buildings = sum(1 for c in group if found[c].kind == "building")
        out.append(
            {
                "chunks": len(group),
                "buildings": buildings,
                "center": [(min(xs) + max(xs)) * 8, (min(zs) + max(zs)) * 8],
                "bounds": [min(xs) * 16, min(zs) * 16, max(xs) * 16 + 15, max(zs) * 16 + 15],
            }
        )
    out.sort(key=lambda c: -c["chunks"])
    return out

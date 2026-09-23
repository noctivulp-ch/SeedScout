"""Por qué se prueba esto: el mapa solo vale si los bits se desempaquetan como lo hace Minecraft.

Un fallo en `unpack_bits` o en la elección de sección de bioma no rompe nada de forma visible —
sale un mapa bonito pero mentiroso, y se elegiría una semilla que no es la que se va a jugar.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seedscout.city import BUILDING_BLOCKS, classify, clusters
from seedscout.colors import biome_color
from seedscout.nbt import unpack_bits
from seedscout.world import read_chunk


def test_unpack_bits_no_cruza_longs():
    # 9 bits por valor: 7 valores por long y 1 bit sobrante que Minecraft deja sin usar.
    packed = [(3 << 0) | (5 << 9) | (7 << 18)]
    assert unpack_bits(packed, 9, 3) == [3, 5, 7]


def test_unpack_bits_rellena_si_faltan():
    assert unpack_bits([], 4, 5) == [0, 0, 0, 0, 0]


def test_color_es_estable_y_por_familia():
    assert biome_color("minecraft:plains") == biome_color("minecraft:plains")
    assert biome_color("minecraft:ocean")[2] > biome_color("minecraft:desert")[2]


def _chunk_nbt(biome: str, height: int) -> dict:
    heights = [height + 64 + 1] * 256
    packed = []
    for start in range(0, 256, 7):
        value = 0
        for offset, h in enumerate(heights[start:start + 7]):
            value |= (h & 0x1FF) << (offset * 9)
        packed.append(value)
    return {
        "Heightmaps": {"WORLD_SURFACE": packed},
        "sections": [{"Y": height >> 4, "biomes": {"palette": [biome]}}],
        "Status": "minecraft:full",
    }


def test_read_chunk_devuelve_bioma_y_altura():
    chunk = read_chunk(_chunk_nbt("biomesoplenty:rainforest", 96), 0, 0)
    assert chunk is not None
    assert set(chunk.biomes) == {"biomesoplenty:rainforest"}
    assert chunk.heights[0] == 96


def test_classify_distingue_edificio_de_calle():
    building = {"sections": [{"Y": 4, "block_states": {"palette": [{"Name": next(iter(BUILDING_BLOCKS))}]}}]}
    street = {"sections": [{"Y": 4, "block_states": {"palette": [{"Name": "minecraft:smooth_stone_slab"}]}}]}
    nothing = {"sections": [{"Y": 4, "block_states": {"palette": [{"Name": "minecraft:dirt"}]}}]}
    assert classify(building).kind == "building"
    assert classify(street).kind == "street"
    assert classify(nothing) is None


def test_clusters_agrupa_chunks_contiguos():
    from seedscout.city import CityChunk

    found = {
        (0, 0): CityChunk(0, 0, "building", 80),
        (1, 0): CityChunk(1, 0, "street", 70),
        (9, 9): CityChunk(9, 9, "building", 80),
    }
    groups = clusters(found)
    assert [g["chunks"] for g in groups] == [2, 1]

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


def test_discard_borra_el_mundo_sin_tocar_la_instalacion_base(tmp_path):
    """Por qué: `mods/` del directorio de trabajo es un symlink a la instalación real del modpack.

    Si el borrado siguiera los enlaces, una limpieza rutinaria se llevaría por delante los 1,4 GB
    de mods del usuario. Esto no se puede descubrir en producción.
    """
    from seedscout.config import Config
    from seedscout.pipeline import Pipeline

    base = tmp_path / "base"
    (base / "mods").mkdir(parents=True)
    (base / "mods" / "un-mod.jar").write_bytes(b"no me borres")

    runs = tmp_path / "runs"
    work = runs / "123"
    (work / "world").mkdir(parents=True)
    (work / "world" / "region.mca").write_bytes(b"x" * 2048)
    (work / "mods").symlink_to(base / "mods")

    pipeline = Pipeline(Config(work_dir=str(runs), base_server=str(base)), tmp_path / "cache")
    pipeline.discard(123)

    assert not work.exists()
    assert (base / "mods" / "un-mod.jar").read_bytes() == b"no me borres"


def test_discard_all_ignora_lo_que_no_sea_una_semilla(tmp_path):
    from seedscout.config import Config
    from seedscout.pipeline import Pipeline

    runs = tmp_path / "runs"
    (runs / "-456").mkdir(parents=True)
    (runs / "notas").mkdir()
    pipeline = Pipeline(Config(work_dir=str(runs)), tmp_path / "cache")
    count, _freed = pipeline.discard_all()
    assert count == 2
    assert not (runs / "-456").exists()

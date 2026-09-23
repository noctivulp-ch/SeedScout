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


def test_imagen_para_compartir_no_lleva_panel_de_notas():
    """Por qué: las notas pueden ser personales y esta imagen es la que se pega en Discord.

    Si volviera a aparecer el panel lateral, se estaría publicando texto que el usuario escribió
    para sí mismo. Se comprueba por la geometría: sin panel, el ancho es el del mapa más el margen.
    """
    from PIL import Image

    from seedscout.render import MapImage, with_overlay

    rendered = MapImage(image=Image.new("RGB", (300, 200)), blocks_per_pixel=2, origin=(0, 0),
                        legend=[("minecraft:plains", 10)])
    out = with_overlay(rendered, 123)
    assert out.width == 300 * 3 + 32, "el ancho debe ser solo mapa + márgenes, sin panel lateral"


def test_no_se_borra_un_mundo_que_el_servidor_tiene_abierto(tmp_path):
    """Por qué: borrar las regiones bajo un servidor vivo corrompe el mundo a medio escribir."""
    import pytest

    from seedscout.config import Config
    from seedscout.pipeline import Pipeline

    pipeline = Pipeline(Config(work_dir=str(tmp_path / "runs")), tmp_path / "cache")

    class VivoConSemilla:
        alive = True
        seed = 42

    pipeline.runner = VivoConSemilla()  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="párelo primero"):
        pipeline.discard(42)


def test_probe_devuelve_bioma_bloque_y_coordenadas_del_mundo():
    """Por qué: es lo que se lee al pasar el ratón; si el origen o la escala se descuadran,
    el usuario apunta a un sitio y se le nombra otro, sin que nada falle de forma visible."""
    import numpy as np
    from PIL import Image

    from seedscout.render import MapImage

    rendered = MapImage(
        image=Image.new("RGB", (4, 4)), blocks_per_pixel=2, origin=(-64, 32), legend=[],
        biome_at=np.array([[0, 0, 1, 1]] * 4, dtype=np.int32),
        height_at=np.full((4, 4), 71, dtype=np.int32),
        block_at=np.zeros((4, 4), dtype=np.int32),
        names=["minecraft:plains", "biomesoplenty:volcano"],
        block_names=["minecraft:grass_block"],
    )
    found = rendered.probe(3, 1)
    assert found["biome"] == "Volcano"
    assert found["block"] == "Grass Block"
    assert (found["x"], found["z"]) == (-64 + 3 * 2, 32 + 1 * 2)
    assert rendered.probe(99, 0) is None


def test_mark_spawn_dibuja_el_recuadro_en_el_chunk_del_spawn():
    from PIL import Image

    from seedscout.render import SPAWN_OUTLINE, MapImage, mark_spawn

    rendered = MapImage(image=Image.new("RGB", (64, 64), (0, 0, 0)), blocks_per_pixel=2,
                        origin=(0, 0), legend=[])
    mark_spawn(rendered, (40, 40))  # chunk 2,2 → píxeles 16..23
    pixels = rendered.image.load()
    assert pixels[16, 16] == SPAWN_OUTLINE, "la esquina del chunk del spawn debe quedar marcada"
    assert pixels[60, 60] == (0, 0, 0), "fuera del spawn no se pinta nada"

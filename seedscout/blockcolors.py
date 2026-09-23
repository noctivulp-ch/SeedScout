"""Color de cada bloque, sacado de sus texturas.

Es como lo resuelven los mapeadores de Minecraft (uNmINeD calcula los colores a partir del jar del
cliente; Xaero's y JourneyMap parten de la paleta de bloques y luego tiñen hierba, follaje y agua
por bioma). Aquí se hace igual: se promedia la textura del bloque ponderando por alfa, se cachea el
resultado y se tiñe en el render.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

CACHE = Path.home() / ".cache" / "seedscout" / "blockcolors.json"

# Orden de preferencia de textura: lo que se ve desde arriba manda.
SUFFIXES = ("_top", "", "_still", "_side", "_front", "_end", "_0")

# Bloques cuya textura es gris y se tiñe en el juego según el bioma.
TINTED_GRASS = {"minecraft:grass_block", "minecraft:grass", "minecraft:tall_grass", "minecraft:fern",
                "minecraft:large_fern", "minecraft:sugar_cane", "minecraft:potted_fern"}
TINTED_FOLIAGE = {"minecraft:oak_leaves", "minecraft:jungle_leaves", "minecraft:acacia_leaves",
                  "minecraft:dark_oak_leaves", "minecraft:vine", "minecraft:mangrove_leaves"}
WATER = {"minecraft:water", "minecraft:flowing_water", "minecraft:bubble_column"}


def _average(data: bytes) -> tuple[int, int, int] | None:
    with Image.open(__import__("io").BytesIO(data)) as image:
        image = image.convert("RGBA")
        # Las texturas animadas son una tira vertical de fotogramas: vale con el primero.
        if image.height > image.width and image.height % image.width == 0:
            image = image.crop((0, 0, image.width, image.width))
        pixels = np.asarray(image, dtype=np.float32)
    alpha = pixels[:, :, 3]
    if alpha.sum() < 1:
        return None
    weights = alpha / 255.0
    total = weights.sum()
    rgb = [(pixels[:, :, i] * weights).sum() / total for i in range(3)]
    return tuple(int(round(c)) for c in rgb)  # type: ignore[return-value]


def build(jars: list[Path]) -> dict[str, tuple[int, int, int]]:
    """Un color por bloque. Gana la textura de más arriba en `SUFFIXES`: lo que se ve desde el cielo."""
    textures: dict[str, bytes] = {}
    for jar in jars:
        try:
            archive = zipfile.ZipFile(jar)
        except Exception:
            continue
        for name in archive.namelist():
            if "/textures/block/" in name and name.endswith(".png"):
                parts = name.split("/")
                key = f"{parts[1]}:{parts[-1][:-4]}"
                textures.setdefault(key, archive.read(name))

    # bloque -> (prioridad del sufijo, textura). Menor prioridad gana.
    best: dict[str, tuple[int, str]] = {}
    for key in textures:
        namespace, texture = key.split(":", 1)
        for rank, suffix in enumerate(SUFFIXES):
            if suffix and texture.endswith(suffix):
                block = f"{namespace}:{texture[: -len(suffix)]}"
                break
        else:
            rank, block = SUFFIXES.index(""), f"{namespace}:{texture}"
        if block not in best or rank < best[block][0]:
            best[block] = (rank, key)

    colors: dict[str, tuple[int, int, int]] = {}
    for block, (_rank, key) in best.items():
        average = _average(textures[key])
        if average:
            colors[block] = average
    for key, data in textures.items():  # la textura exacta también sirve de nombre
        if key not in colors:
            average = _average(data)
            if average:
                colors[key] = average
    return colors


def load(jars: list[Path] | None = None, refresh: bool = False) -> dict[str, tuple[int, int, int]]:
    if CACHE.exists() and not refresh:
        return {k: tuple(v) for k, v in json.loads(CACHE.read_text()).items()}  # type: ignore[misc]
    colors = build(jars or [])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({k: list(v) for k, v in sorted(colors.items())}))
    return colors

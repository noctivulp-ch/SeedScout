"""Colores de hierba, follaje y agua por bioma.

Los mods traen sus valores en `data/<ns>/worldgen/biome/<nombre>.json` (BiomesOPlenty define los
145 suyos ahí). Los biomas de vanilla no están en datos: el juego los calcula con el colormap
`textures/colormap/grass.png` a partir de la temperatura y la humedad del bioma, y eso es lo que se
reproduce aquí con la misma fórmula que `GrassColor.get`.
"""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

# Temperatura y humedad de los biomas del overworld de 1.20 (no están en ningún json del cliente).
VANILLA_CLIMATE: dict[str, tuple[float, float]] = {
    "plains": (0.8, 0.4), "sunflower_plains": (0.8, 0.4), "meadow": (0.5, 0.8),
    "forest": (0.7, 0.8), "flower_forest": (0.7, 0.8), "birch_forest": (0.6, 0.6),
    "old_growth_birch_forest": (0.6, 0.6), "dark_forest": (0.7, 0.8),
    "taiga": (0.25, 0.8), "snowy_taiga": (-0.5, 0.4), "old_growth_pine_taiga": (0.3, 0.8),
    "old_growth_spruce_taiga": (0.25, 0.8), "grove": (-0.2, 0.8),
    "jungle": (0.95, 0.9), "sparse_jungle": (0.95, 0.8), "bamboo_jungle": (0.95, 0.9),
    "savanna": (2.0, 0.0), "savanna_plateau": (2.0, 0.0), "windswept_savanna": (2.0, 0.0),
    "desert": (2.0, 0.0), "badlands": (2.0, 0.0), "eroded_badlands": (2.0, 0.0),
    "wooded_badlands": (2.0, 0.0), "swamp": (0.8, 0.9), "mangrove_swamp": (0.8, 0.9),
    "river": (0.5, 0.5), "frozen_river": (0.0, 0.5), "beach": (0.8, 0.4),
    "snowy_beach": (0.05, 0.3), "stony_shore": (0.2, 0.3),
    "ocean": (0.5, 0.5), "deep_ocean": (0.5, 0.5), "cold_ocean": (0.5, 0.5),
    "deep_cold_ocean": (0.5, 0.5), "frozen_ocean": (0.0, 0.5), "deep_frozen_ocean": (0.5, 0.5),
    "lukewarm_ocean": (0.5, 0.5), "deep_lukewarm_ocean": (0.5, 0.5), "warm_ocean": (0.5, 0.5),
    "snowy_plains": (0.0, 0.5), "ice_spikes": (0.0, 0.5), "snowy_slopes": (-0.3, 0.9),
    "jagged_peaks": (-0.7, 0.9), "frozen_peaks": (-0.7, 0.9), "stony_peaks": (1.0, 0.3),
    "windswept_hills": (0.2, 0.3), "windswept_gravelly_hills": (0.2, 0.3),
    "windswept_forest": (0.2, 0.3), "cherry_grove": (0.5, 0.8),
    "mushroom_fields": (0.9, 1.0), "lush_caves": (0.5, 0.5), "dripstone_caves": (0.8, 0.4),
    "deep_dark": (0.8, 0.4), "the_void": (0.5, 0.5),
}
DEFAULT_WATER = (63, 118, 228)
# El pantano no pasa por el colormap: el juego le pone estos colores a mano.
SPECIAL_GRASS = {"minecraft:swamp": (106, 112, 57), "minecraft:mangrove_swamp": (106, 112, 57)}
SPECIAL_FOLIAGE = {"minecraft:swamp": (106, 112, 57), "minecraft:mangrove_swamp": (141, 177, 39)}


@dataclass
class BiomeLook:
    grass: tuple[int, int, int]
    foliage: tuple[int, int, int]
    water: tuple[int, int, int]


def _rgb(value: int) -> tuple[int, int, int]:
    return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)


def _colormap_lookup(colormap: Image.Image | None, temperature: float, downfall: float,
                     fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if colormap is None:
        return fallback
    temperature = max(0.0, min(1.0, temperature))
    downfall = max(0.0, min(1.0, downfall)) * temperature
    x = int((1.0 - temperature) * 255.0)
    y = int((1.0 - downfall) * 255.0)
    # El juego lee el píxel tal cual salvo que el índice se salga de la textura; la esquina
    # fría-seca (255, 255) sí tiene color y es la de los biomas nevados.
    return colormap.getpixel((min(x, 255), min(y, 255)))[:3]


def load(jars: list[Path], client_jar: Path | None = None) -> dict[str, BiomeLook]:
    grass_map = foliage_map = None
    if client_jar and client_jar.exists():
        with zipfile.ZipFile(client_jar) as archive:
            grass_map = Image.open(io.BytesIO(archive.read("assets/minecraft/textures/colormap/grass.png"))).convert("RGB")
            foliage_map = Image.open(io.BytesIO(archive.read("assets/minecraft/textures/colormap/foliage.png"))).convert("RGB")

    looks: dict[str, BiomeLook] = {}
    for name, (temperature, downfall) in VANILLA_CLIMATE.items():
        key = f"minecraft:{name}"
        looks[key] = BiomeLook(
            grass=SPECIAL_GRASS.get(key) or _colormap_lookup(grass_map, temperature, downfall, (121, 192, 90)),
            foliage=SPECIAL_FOLIAGE.get(key) or _colormap_lookup(foliage_map, temperature, downfall, (89, 174, 48)),
            water=DEFAULT_WATER,
        )

    for jar in jars:
        try:
            archive = zipfile.ZipFile(jar)
        except Exception:
            continue
        for entry in archive.namelist():
            if "/worldgen/biome/" not in entry or not entry.endswith(".json"):
                continue
            parts = entry.split("/")
            key = f"{parts[1]}:{parts[-1][:-5]}"
            try:
                data = json.loads(archive.read(entry))
            except Exception:
                continue
            effects = data.get("effects") or {}
            temperature = float(data.get("temperature", 0.5))
            downfall = float(data.get("downfall", 0.5))
            grass = _rgb(effects["grass_color"]) if "grass_color" in effects else \
                _colormap_lookup(grass_map, temperature, downfall, (121, 192, 90))
            foliage = _rgb(effects["foliage_color"]) if "foliage_color" in effects else \
                _colormap_lookup(foliage_map, temperature, downfall, (89, 174, 48))
            water = _rgb(effects["water_color"]) if "water_color" in effects else DEFAULT_WATER
            looks[key] = BiomeLook(grass=grass, foliage=foliage, water=water)
    return looks

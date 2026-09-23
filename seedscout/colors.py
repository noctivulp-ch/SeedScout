"""Color por bioma.

No hay tabla oficial para los biomas de mods (BiomesOPlenty trae ~90 y no publica sus colores
de mapa en datos legibles), así que el color sale de la familia a la que pertenece el nombre
más una variación determinista: dos biomas de bosque salen verdes pero distinguibles, y el mismo
bioma sale siempre igual en todos los mapas.
"""
from __future__ import annotations

import hashlib

FAMILIES: list[tuple[tuple[str, ...], tuple[int, int, int]]] = [
    (("deep_ocean", "deep_cold", "deep_frozen", "deep_lukewarm"), (24, 42, 96)),
    (("ocean", "sea", "kelp"), (38, 68, 140)),
    (("river", "stream", "waterfall"), (58, 108, 178)),
    (("beach", "shore", "dune", "gravel_beach"), (222, 206, 150)),
    (("desert", "sandy", "oasis", "dry"), (232, 202, 120)),
    (("badlands", "mesa", "canyon", "wasteland", "dead", "ashen", "crag"), (172, 108, 62)),
    (("volcan", "lava", "magma", "scorch"), (126, 48, 40)),
    (("snow", "frozen", "ice", "glacier", "frost", "tundra", "arctic"), (232, 240, 248)),
    (("peak", "mountain", "hill", "highland", "cliff", "alps", "stony"), (150, 150, 156)),
    (("jungle", "rainforest", "tropic", "bamboo"), (44, 126, 52)),
    (("swamp", "marsh", "bog", "bayou", "wetland", "fen", "mire"), (84, 106, 72)),
    (("taiga", "spruce", "conifer", "pine", "boreal", "fir"), (58, 96, 78)),
    (("birch", "forest", "grove", "woodland", "wood", "copse", "thicket"), (66, 140, 76)),
    (("savanna", "shrub", "steppe", "prairie", "scrub", "chaparral"), (178, 168, 92)),
    (("plains", "meadow", "field", "pasture", "grass", "clover", "orchard"), (126, 182, 96)),
    (("flower", "garden", "blossom", "rose", "lavender", "cherry"), (196, 148, 190)),
    (("mushroom", "fungal", "shroom"), (152, 104, 160)),
    (("cave", "lush", "dripstone", "deep_dark", "underground"), (78, 72, 88)),
    (("nether", "crimson", "warped", "soul", "basalt", "blackstone"), (124, 42, 48)),
    (("end", "void", "chorus"), (206, 200, 152)),
    (("city", "urban", "ruin", "concrete"), (118, 118, 118)),
]

FALLBACK = (110, 124, 110)


def _variation(name: str) -> tuple[int, int, int]:
    digest = hashlib.sha1(name.encode("utf-8")).digest()
    return (digest[0] % 29) - 14, (digest[1] % 29) - 14, (digest[2] % 29) - 14


def biome_color(name: str) -> tuple[int, int, int]:
    key = name.split(":")[-1].lower()
    base = FALLBACK
    for needles, color in FAMILIES:
        if any(needle in key for needle in needles):
            base = color
            break
    dr, dg, db = _variation(name)
    return (
        max(0, min(255, base[0] + dr)),
        max(0, min(255, base[1] + dg)),
        max(0, min(255, base[2] + db)),
    )


def pretty(name: str) -> str:
    return name.split(":")[-1].replace("_", " ").title()

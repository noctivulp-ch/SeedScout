#!/usr/bin/env python3
"""Arma las imágenes del README (docs/capturas/*.png) con mapas ya generados.

    python3 tools/capturas/capturas.py [--] SEMILLA_A SEMILLA_B

Generar un mapa exige el servidor del modpack, así que esto no genera nada: toma
de la caché de SeedScout (`<work_dir>/../cache`) dos semillas que ya se hayan
generado con `seedscout gen` y deja la imagen para compartir de cada una.

Conviene elegir semillas de prueba y no la de un servidor en uso: publicar el
mapa de un mundo donde se juega le ahorra la exploración a cualquiera.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from seedscout.config import Config  # noqa: E402

SALIDA = RAIZ / "docs" / "capturas"


def main() -> None:
    # Las semillas negativas parecen opciones: se admite un `--` delante.
    semillas = [x for x in sys.argv[1:] if x != "--"]
    if len(semillas) != 2:
        sys.exit(__doc__)
    a, b = semillas
    cache = Path(Config.load().work_dir).parent / "cache"
    SALIDA.mkdir(parents=True, exist_ok=True)

    for n, semilla in enumerate((a, b), 1):
        shutil.copyfile(cache / f"{semilla}-compartir.png", SALIDA / f"compartir-{n}.png")

    print("\n".join(sorted(p.name for p in SALIDA.glob("*.png"))))


if __name__ == "__main__":
    main()

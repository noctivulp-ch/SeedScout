# Del servidor al PNG

```
semilla → runner.py ─(servidor Forge + Chunky)→ world/region/*.mca
                                                      │
                                   world.py ──────────┤ bioma de superficie + altura por columna
                                   city.py  ──────────┤ chunks urbanos → ciudades agrupadas
                                                      ▼
                                   render.py → mapa.png + mapa-compartir.png
                                   store.py  → carpeta por semilla + galeria.html
```

## Directorio de trabajo por semilla

`~/.local/share/seedscout/runs/<semilla>/` con:

- symlinks a `mods/`, `libraries/`, `customnpcs/`, `media/`… — nunca se escriben.
- copias de `config/`, `defaultconfigs/`, `kubejs/` — los mods sí escriben ahí, y la instalación
  base tiene que quedar intacta.
- `server.properties` propio: la semilla, puerto 25599, `view-distance` bajo, RCON apagado,
  y el resto heredado del servidor base para no cambiar la generación sin querer.

El servidor se controla por su entrada estándar (`chunky …`, `save-all flush`, `stop`). No se usa
RCON —no hace falta abrir un puerto— y no se mata el proceso nunca: un `stop` limpio es lo único
que garantiza que las regiones queden escritas.

## Lectura del mundo

`nbt.py` implementa lo justo: NBT y el formato de región Anvil. En 1.18+ los biomas viven en cada
sección como paleta de 4×4×4 y las alturas en `Heightmaps.WORLD_SURFACE`, empaquetadas a 9 bits
sin cruzar el límite de un `long`. Para cada columna se toma la altura y el bioma **a esa altura**,
que es lo que se ve desde arriba.

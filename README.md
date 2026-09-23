# SeedScout

Explorador de semillas para modpacks pesados de Minecraft, empezando por **DeceasedCraft**
(Forge 1.20.1, ~340 mods, BiomesOPlenty + TerraBlender + Lost Cities).

Genera el mundo **de verdad** con el servidor del modpack y dibuja su mapa. No simula la
generación: la ejecuta.

## Por qué no vale Chunkbase ni Amidst

Esas herramientas reimplementan la generación de Minecraft vanilla. DeceasedCraft mete
BiomesOPlenty y TerraBlender, que reescriben la distribución de biomas entera, y Lost Cities,
que sustituye las estructuras por ciudades. El mapa que darían sería el de otro juego.

SeedScout arranca el servidor real con sus mods, le pide a **Chunky** que pregenere un radio,
y después lee los `.mca` resultantes. Lo que ves es exactamente lo que vas a jugar.

## Uso

```bash
python3 -m seedscout web            # interfaz en http://127.0.0.1:5055
python3 -m seedscout gen            # una semilla aleatoria, por consola
python3 -m seedscout gen 12345 --radius 512 --save --notes "aldea junto al río"
python3 -m seedscout render <mundo> --out mapa.png   # mapa de un mundo ya existente
python3 -m seedscout config --write # escribe ~/.config/seedscout/config.json
./check.sh                          # sintaxis + importaciones + tests
```

La interfaz da: semilla usada, mapa de biomas, lista de biomas con su porcentaje, ciudades
detectadas con su centro, un campo de notas y el botón de guardar. El botón **Generar** sin
semilla sortea una.

## Qué guarda

Una carpeta por semilla en `~/Documentos/Minecraft/SeedScout/<semilla>/`:

| Archivo | Contenido |
|---|---|
| `mapa.png` | el mapa de biomas en crudo |
| `mapa-compartir.png` | mapa + semilla + leyenda + tus notas, listo para pegar en Discord |
| `datos.json` | semilla, radio, chunks, biomas con su porcentaje y ciudades con centro y tamaño |
| `notas.md` | lo mismo en markdown, con tus notas al final |

Y `galeria.html` en la raíz de esa carpeta: todas las semillas guardadas juntas para compararlas.

## Requisitos

Python 3.11+ con Flask, Pillow y numpy. Java 17 para el servidor de Forge, y una instalación del
modpack ya montada y probada (`base_server` en la configuración). El mod **Chunky** tiene que
estar en esa instalación.

SeedScout nunca escribe en la instalación base: `mods/` y `libraries/` se enlazan por symlink y
`config/` se copia al directorio de trabajo de cada semilla. El servidor se para siempre con el
comando `stop`, nunca matando el proceso.

## Estructura

```
seedscout/
  config.py    rutas, radio, puertos, timeouts
  runner.py    arranca el servidor con la semilla y pregenera con Chunky
  nbt.py       lector de NBT y de regiones Anvil
  world.py     chunks → bioma de superficie y altura por columna
  city.py      detección de las ciudades de Lost Cities
  colors.py    color por bioma (familias + variación determinista)
  render.py    PNG del mapa y versión con datos para compartir
  store.py     carpeta por semilla y galería comparativa
  pipeline.py  une todo y expone el progreso
  web.py       interfaz local (Flask)
  cli.py       línea de comandos
docs/          arquitectura, decisiones (ADR) y funciones
tests/         qué se prueba y por qué
```

Documentación: [`docs/index.md`](docs/index.md).

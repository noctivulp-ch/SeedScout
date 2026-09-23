# 0001 — Generar el mundo de verdad en vez de simular la worldgen

**Fecha:** 2026-09-22 · **Estado:** aceptada

## Contexto

Para elegir semilla hace falta ver el mapa antes de jugar. Las herramientas habituales
(Chunkbase, Amidst, cubiomes) reimplementan la generación de Minecraft vanilla.

DeceasedCraft lleva BiomesOPlenty y TerraBlender, que sustituyen la distribución de biomas
completa, y Lost Cities, que reemplaza las estructuras por ciudades generadas con su propio ruido
Perlin (`cityChance`, `cityThreshold`, `cityPerlinScale` en los perfiles del pack). Además el
servidor corre con `generate-structures=false`.

## Decisión

Arrancar el servidor real del modpack con la semilla, pregenerar un radio con Chunky y leer los
`.mca` resultantes.

## Consecuencias

- El mapa es exacto por construcción: es el mundo que se va a jugar, con sus mods.
- Cuesta minutos y varios GB de RAM por semilla, así que no sirve para barrer cientos de semillas;
  sirve para mirar unas pocas con calma, que es el caso real.
- Cualquier cambio en la lista de mods se refleja solo: no hay nada que mantener al día.

## Alternativas descartadas

- **Reimplementar BOP + TerraBlender**: meses de trabajo y se rompe con cada actualización.
- **Simular solo Lost Cities** (existe ya en LostCitiesEditor, con `JavaRandom`/`QualityRandom`
  fieles al mod): daría las ciudades al instante, pero no los biomas ni el terreno, que es
  justo lo que se quiere mirar para elegir semilla.

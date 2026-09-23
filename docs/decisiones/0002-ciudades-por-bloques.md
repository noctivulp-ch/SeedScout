# 0002 — Detectar ciudades por bloques manufacturados

**Fecha:** 2026-09-22 · **Estado:** aceptada

## Contexto

Hay que saber dónde caen las ciudades de Lost Cities y cuántas hay. Reimplementar el ruido del mod
es posible pero depende del perfil activo (`deceasedcraft`, `deceasedcraft_onlycities`…) y de la
versión del jar.

## Decisión

Marcar un chunk como urbano si su paleta de bloques contiene material de construcción.

Es fiable **porque el pack corre con `generate-structures=false`**: sin aldeas, templos ni minas,
todo bloque manufacturado que aparece en el overworld lo ha puesto Lost Cities. Los chunks
contiguos se agrupan y cada grupo se reporta como una ciudad con su centro y su tamaño.

## Consecuencias

- Cuesta 6 segundos para 3774 chunks (medido sobre el mundo local de `dc-test`), leyendo solo las
  paletas de cada sección.
- Distingue edificio de calle mirando qué bloques aparecen.
- **Si algún día se activan las estructuras vanilla, esta detección deja de valer** y habría que
  pasar a simular el ruido del mod.

## Verificación

Sobre el mundo local: 1503 chunks urbanos, 7 grupos, el mayor de 1494 chunks con 1382 edificios,
centrado en 1224, 696 — que es la ciudad donde estaba jugando el usuario.

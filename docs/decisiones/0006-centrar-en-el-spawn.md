# 0006 — El mapa se centra donde aparece el jugador

**Fecha:** 2026-09-23 · **Estado:** aceptada

## Contexto

Se generaba siempre alrededor de 0,0. En DeceasedCraft eso es el sitio equivocado: el perfil
`deceasedcraft_onlycities.json` trae

```
forceSpawnBuildings = [16 edificios residenciales de deceasedcraft]
spawnCheckRadius    = 256
spawnRadiusIncrease = 512
spawnCheckAttempts  = 200000
```

Lost Cities planta al jugador junto a uno de esos edificios, ampliando la búsqueda de 512 en 512
bloques. Medido: en `dc-test` el spawn quedó en 1000, 1144 y en una semilla de prueba en 1656, 552.
Con radio 768 alrededor del origen, **el mapa no contenía el punto de partida**.

## Decisión

Centrar la pregeneración en el spawn, con `center = "spawn"` por defecto y `"origin"` como
alternativa.

Dos detalles que costaron dos ejecuciones fallidas:

1. **`level.dat` no está escrito cuando termina el arranque.** Leerlo ahí devuelve el spawn del
   mundo recién creado (0, 0). Hay que mandar `save-all flush`, esperar el "Saved the game" del log
   y entonces leerlo.
2. **El spawn definitivo no está fijado al arrancar.** Con la misma semilla salió 24, 24 antes de
   generar y 1656, 552 después: Lost Cities lo mueve mientras se generan los chunks. Por eso se
   relee al terminar la pasada y, si quedó fuera de lo generado, se hace una segunda centrada en él.
   Así el mapa contiene el spawn por construcción, sin depender de cuándo lo decida el mod.

## Consecuencias

- El mapa siempre incluye la ciudad donde se empieza, que es lo que se quiere mirar para elegir
  semilla.
- Si el spawn se va lejos, la semilla cuesta una segunda pasada de Chunky (~15 s por cada 1000
  chunks); el arranque no se repite, porque el servidor sigue vivo.

# 0005 — El mapa se pinta por bloque de superficie, no por bioma

**Fecha:** 2026-09-23 · **Estado:** aceptada

## Contexto

La primera versión pintaba cada columna con un color inventado para su bioma. Se leía, pero no
parecía un mapa de Minecraft: sin agua reconocible, sin lava, sin playas, sin edificios.

## Referencias consultadas

- [uNmINeD](https://unmined.net/) calcula los colores **a partir del jar del cliente** (media de la
  textura del bloque) y aplica sombreado de pendiente y oscurecimiento del agua por profundidad.
  Su [versión para mundos modded](https://unmined.net/2026/03/20/unmined-0-19-58-dev-modded-worlds/)
  hace lo mismo con los jars de los mods.
- [Xaero's Minimap](https://chocolateminecraft.com/update.php?mod_id=0) parte de la paleta de
  bloques de vanilla y tiñe hierba, follaje y agua según el bioma; su historial de versiones
  registra fallos por usar el índice de tinte equivocado.
- [JMtoXaero](https://github.com/Entropy5/JMtoXaero) documenta que el color de un píxel de
  JourneyMap depende del bloque, la altura, la transparencia y el bioma.

## Decisión

Cuatro capas, como ellos:

1. **Color del bloque de superficie**: media ponderada por alfa de su textura, sacada del jar del
   cliente y de los 339 jars del modpack (11 799 bloques). Gana la textura `_top`: es la que se ve
   desde arriba.
2. **Tinte de bioma** en hierba y follaje. Los mods traen sus colores en
   `data/<ns>/worldgen/biome/*.json` (BiomesOPlenty define 145); los de vanilla no están en datos,
   así que se calculan con `textures/colormap/grass.png` y la fórmula de `GrassColor.get` a partir
   de la temperatura y la humedad. Verificado contra los valores conocidos: Plains `#91BD59`,
   Snowy Plains `#80B497`, Desert `#BFB755`, Jungle `#59C93C`, y el pantano con su color fijo
   `#6A7039`, que en el juego tampoco pasa por el colormap.
3. **Agua por profundidad**: `WORLD_SURFACE` menos `OCEAN_FLOOR`, hasta un 55 % más oscura.
4. **Sombreado de pendiente** contra el vecino al norte y al oeste.

Los chunks que Chunky dejó a medias no tienen bloques, solo bioma y altura: esos se siguen pintando
con el color del bioma para que no queden agujeros.

## Consecuencias

- El render tarda 0,9 s para 4445 chunks y las tablas de color se construyen en 2,8 s, una sola vez
  por sesión.
- Se lee `block_states` de cada chunk además de los biomas, desempaquetado con numpy. Cuidado: los
  `long` del NBT vienen **con signo** y hay que reinterpretarlos sin signo antes de desplazar bits.
- El mapa guarda, por píxel, el bioma, el bloque y la altura, que es lo que alimenta la sonda del
  cursor sin volver a leer el mundo.

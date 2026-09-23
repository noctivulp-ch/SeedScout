# 0004 — El servidor se queda vivo entre generaciones

**Fecha:** 2026-09-22 · **Estado:** aceptada

## Contexto

Cada generación arrancaba y paraba el servidor: 83 s de arranque por semilla, aunque solo se
quisiera ampliar el radio de la que ya estaba.

## Lo que no se puede evitar

**La semilla se fija al crear el mundo.** En Forge no hay forma de cambiar la semilla del overworld
de un servidor en marcha, así que pasar a otra semilla obliga a mundo nuevo y a reiniciar. Eso no
lo arregla ningún diseño.

## Decisión

Un único `WorldRunner` mantiene el proceso vivo. `generate()` deja el servidor arriba al terminar;
si la siguiente generación es de la misma semilla, se salta el arranque y solo lanza Chunky. La
interfaz da un botón de arrancar y parar, con un indicador del estado y de qué semilla tiene
cargada. Al cambiar de semilla, el servidor se reinicia solo y se tira el mundo anterior.

## Consecuencias

- Ampliar el radio de una semilla cuesta solo lo que tarde Chunky (14 s por 1089 chunks).
- Cambiar de semilla sigue costando los 83 s del arranque.
- El mundo de trabajo ya no se borra al acabar de leerlo, sino al parar el servidor o al cambiar de
  semilla: mientras el servidor lo tiene abierto, borrarlo corrompería las regiones. `discard()`
  se niega a borrar el mundo de una semilla que esté cargada.

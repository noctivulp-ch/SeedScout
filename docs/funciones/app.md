# Qué hace cada parte

## Interfaz web (`web.py` + `templates/index.html`)

Una página: cabecera con el campo de semilla, el radio y el botón **Generar**; el mapa a la
izquierda con una barra de progreso que se actualiza cada 2 s; a la derecha los biomas con su
porcentaje, las ciudades con su centro, el campo de notas con el botón de guardar y la lista de
semillas ya guardadas.

Rutas: `POST /api/generate`, `GET /api/status`, `GET /api/map/<semilla>`, `POST /api/save`,
`POST /api/delete/<semilla>`, `GET /galeria`.

Una semilla escrita que no sea un número se convierte con la misma idea que el juego: se acepta
texto y se deriva un número de él.

## CLI (`cli.py`)

`web`, `gen [semilla] [--radius] [--save] [--notes]`, `render <mundo>`, `config [--write]`.
`render` sirve para dibujar un mundo que ya existe sin generar nada — es como se probó el
renderizador contra el mundo local de `dc-test`.

## Mapa (`render.py`)

Color de bioma por columna y sombreado por pendiente, comparando cada píxel con su vecino al norte
y al oeste. `with_overlay` añade la semilla, la leyenda con porcentajes, las notas y la escala.

## Colores (`colors.py`)

No existe tabla oficial de colores para los biomas de mods. El color sale de la familia del nombre
(océano, desierto, jungla, volcán…) más una variación determinista por hash: dos bosques salen
verdes pero distintos, y el mismo bioma sale siempre igual.

# Validación real del ASG híbrido 7.5

Fecha: 2026-09-30. Se ejecutaron dos funciones nuevas con Gemini a partir de
[La Sombra del Volcán 7.4](../Stories/Stagecraft/20260928-181908-la-sombra-del-volcan):
[control fixed](../Stories/Stagecraft/20260930-153026-la-sombra-del-volcan) y
[modo adaptive](../Stories/Stagecraft/20260930-154634-la-sombra-del-volcan).
Ambas usaron `gemini-3.5-flash-lite` para narración y `gemini-3.1-flash-lite`
para actuación, el mismo presupuesto de ocho turnos por beat y sin audio.
`request.json`, `world.json`, `characters.json`, `story_plan.json`, `script.json`
y `cast_bible.json` coinciden byte a byte en los tres directorios. Son dos
observaciones de una misma premisa, no una muestra suficiente para inferir calidad media.

| Medida | fixed | adaptive |
|---|---:|---:|
| Estado | completada | completada con cierre abierto |
| Escenas / turnos | 6 / 48 | 2 / 16 |
| Beats logrados / previstos inicialmente | 5 / 6 | 1 / 6 |
| Beats forzados | 1 | 0 |
| Intentos de actor pedidos / rechazados | 49 / 3 | 17 / 1 |
| Contextos de turnos actor guardados | 46 / 46 | 16 / 16 |
| Llamadas lógicas / tokens totales | 88 / 196 933 | 34 / 78 457 |
| Promesas originales cumplidas | 0 / 2 | 0 / 2 |
| Pensamientos por turno actor | 100 % | 100 % |
| Susurros | 0 | 0 |

Una auditoría literal de los 62 contextos de actor no encontró pensamientos
ajenos ni susurros no presenciados copiados literalmente. Es una comprobación
de cadenas, no una prueba semántica de ausencia de filtraciones.

En `fixed`, la rotura final de las cadenas sí aparece como acción
representada: Ignis exhala calor y pulveriza las cadenas. Es una mejora frente
a la ejecución 7.4, que citaba declaraciones y expectativas futuras. Sin
embargo, `event_2` no reunió la evidencia exigida para dos revelaciones,
incluso después de una intervención del mundo; el motor siguió el
control fijo y registró `[BEAT_FORCED]`. En el artefacto original 7.5 de este
run, `BeatRecord.missing` quedó vacío por un defecto de copia desde la
última comprobación. Se corrigió después de este experimento; la
fuente de las cláusulas faltantes está en
`stage/chapter_1-scene-2/director.jsonl` y no se reescribió la evidencia
histórica.

En `adaptive`, el segundo beat tampoco se demostró. El motor no fabricó
una acción del mundo y pidió revisar solo las cuatro escenas futuras.
Gemini entregó dos propuestas que no incluyeron objetivos para todos los
actores del reparto; el validador las rechazó y terminó la historia con
un cierre abierto tras la escena 2. La coda deja a Elara y Aldren buscando
dónde podrán hacer escuchar la verdad. Ese resultado es causalmente
coherente, pero no demuestra que el bucle de revisión produzca una
continuación válida con Gemini. El run conserva el diagnóstico en
`active_plan/revision-002-failed.json`; las respuestas originales del modelo
no se guardaron en esta ejecución. Después se cambió el contrato para
que los objetivos omitidos conserven su valor original y se instrumentaron
las solicitudes, respuestas y rechazos de cada revisión. Esa corrección
está cubierta por pruebas falsas, pero aún no se ha comprobado con
una tercera llamada real.

Persisten cuestiones de actuación: todos los turnos de actor incluyeron
pensamiento, no hubo susurros y las emociones privadas aparecieron en inglés
aunque la ficción es española. El esquema de emoción y el casting
pedían inglés; se corrigieron después de los dos runs. La etiqueta
`tactic`, una cesión léxica o una respuesta posterior siguen sin
probar por sí solas oposición dramática. La auditoría de promesas
marcó 0/2 en ambas historias, por lo que no conviene declarar que el
control fijo resolvió todo aunque su coda sea cerrada.

Para comparar calidad y coste haría falta repetir al menos un misterio y
una negociación con el mismo plan congelado, presupuesto y modelos por
par. Esta prueba confirma persistencia, narración y cierre abierto; deja
pendiente verificar con Gemini una revisión futura aceptada y la fidelidad
semántica de sus consecuencias.

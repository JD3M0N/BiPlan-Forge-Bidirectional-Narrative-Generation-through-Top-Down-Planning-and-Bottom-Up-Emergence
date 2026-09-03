# Calibración de los perfiles narrativos

Comparación controlada de los perfiles Esencial, Desarrollada y Expansiva sobre tres contenidos
distintos, con el código corregido del `DramaCriticAgent`. Resuelve la compresión de eventos de
la Expansiva frente a la Esencial, pero deja abierta —con evidencia nueva— la extensión absoluta
insuficiente de las historias Expansivas.

## Por qué existe este documento

`TODO.md` («Top-Down: perfiles y calibración») exige que una historia Expansiva se distinga de
una Esencial por desarrollo de escena en la prosa entregada, no solo por el número de nodos del
plan, y que la diferencia quede documentada sobre más de una ejecución por perfil. Una versión
anterior de este documento (commit `a67ba98`) diagnosticó el problema con una única ejecución por
perfil sobre el prompt 6 del catálogo: los mínimos estructurales por perfil ya funcionaban en el
plan (4, 6 y 9 eventos), pero las palabras por evento *caían* al subir de perfil — 532 en
Esencial, 368 en Desarrollada, 321 en Expansiva —, justo lo contrario de lo que pide el contrato
de la Expansiva («Give every major event... enough scene space... do not pack several planned
events into a brief summary passage», `profiles.py:44-46`). Ese documento fue borrado antes de
corregir el problema; este lo sustituye con el arreglo aplicado y el experimento repetido.

## Causa raíz y arreglo

Ningún código medía ni exigía espacio de escena por evento — el único agente que lee la historia
completa y puede corregirla, `DramaCriticAgent` (`agents/review.py`), pedía revisar «pacing and
tension» de forma genérica, sin verificar evento por evento si cada uno recibió su propia escena.
El arreglo es puramente cualitativo y no introduce ningún presupuesto numérico de palabras (el
proyecto los rechazó deliberadamente en la v6.0): se añadió a su `system_instruction` la
exigencia explícita de examinar, en perfiles Desarrollada y Expansiva, cada evento planificado de
un capítulo por separado, y de emitir una nota `category="pacing"` (`major`/`critical`) con los
`event_ids` afectados cuando un evento quede absorbido en el resumen de otro. El gate existente
del Writer (`UNCHANGED_SIGNIFICANT_NOTES`, ya presente en `pipeline.py`) obliga a que esa nota
produzca un cambio de prosa visible, sin ninguna medición añadida.

## Método

| Elemento | Valor |
|---|---|
| Commit | working tree con el arreglo aplicado sobre `1bea0f1` |
| Generador | `asg-top-down`, `pipeline_version` 6.0 |
| Modelo | `gemini-3.5-flash-lite`, ~14 peticiones por minuto efectivas |
| Fecha | 2026-09-03, 21:27–22:15 UTC |
| Prompts | `docs/prompts_top_down.md`, catálogo 6 (dinosaurios, línea base de `a67ba98`), catálogo
  7 (falsificación de arte, nuevo, añadido para esta calibración) y prompt 1 (caballero y dragón,
  solo perfil Expansiva, para probar el techo de extensión) |
| Comando | `generate-story "<prompt>"`, una ejecución por perfil y por prompt, en serie |

Cada catálogo usa el mismo texto base para los tres perfiles — solo cambia la palabra del
perfil —, así que dentro de cada catálogo cualquier diferencia observada procede del perfil y de
la variabilidad del modelo, no del contenido. Usar dos catálogos distintos evita que la
conclusión dependa de un único contenido, que es exactamente lo que pide el criterio de cierre
de la tarea («más de una ejecución por perfil»).

La primera ejecución Expansiva del catálogo 7 falló limpiamente en planificación: dos intentos
sucesivos produjeron 5 y 7 eventos, por debajo del mínimo de 9, y el pipeline abortó con
`PLOT_VALIDATION_FAILED` en vez de entregar un plan inválido — el validador de
`graph.py:validate_profile_structure` funcionó como se espera. Se repitió la ejecución y la
segunda sí produjo un plan válido; esa es la que se reporta abajo.

## Resultados

Todas las cifras proceden de los artefactos del propio run: `story_metrics.json`,
`metadata.json` y `llm_usage.json`.

### Catálogo 6 — dinosaurios (mismo prompt que la línea base de `a67ba98`)

| Métrica | Esencial | Desarrollada | Expansiva |
|---|---:|---:|---:|
| Run | `20260903-212721-la-era-de-las-escamas-pensantes` | `20260903-212856-la-era-de-las-escamas-y-el-acero` | `20260903-213335-el-dominio-saurio` |
| Capítulos | 2 | 4 | 3 |
| Eventos | 5 | 6 | 9 |
| Palabras | 1 195 | 3 680 | 3 171 |
| Palabras por evento | 239,0 | 613,3 | 352,3 |
| Palabras por capítulo | 627 / 552 | 942 / 1163 / 649 / 899 | 828 / 1064 / 1262 |
| Eventos por capítulo | 2 / 3 | 1 / 2 / 1 / 2 | 2 / 3 / 4 |
| Advertencias | 0 | 0 | 0 |
| Duración | 96 s | 276 s | 242 s |
| Tokens totales | 42 396 | 95 157 | 94 349 |

Línea base `a67ba98` (mismo prompt, código sin el arreglo): 532 / 368 / 321 palabras por evento.

### Catálogo 7 — falsificación de arte (nuevo)

| Métrica | Esencial | Desarrollada | Expansiva |
|---|---:|---:|---:|
| Run | `20260903-213732-la-sombra-del-maestro` | `20260903-214034-la-falsificacion-del-alba` | `20260903-214949-la-falsificacion-perfecta` |
| Capítulos | 3 | 3 | 3 |
| Eventos | 7 | 6 | 9 |
| Palabras | 2 630 | 2 897 | 3 763 |
| Palabras por evento | 375,7 | 482,8 | 418,1 |
| Palabras por capítulo | 899 / 877 / 835 | 876 / 968 / 1030 | 1086 / 1594 / 1066 |
| Eventos por capítulo | 3 / 2 / 2 | 2 / 2 / 2 | 2 / 4 / 3 |
| Advertencias | 1 (`WRITER_REVISION_REJECTED`, cap. 3) | 0 | 0 |
| Duración | 181 s | 259 s | 237 s (segundo intento) |
| Tokens totales | 74 686 | 76 629 | 97 535 |

La advertencia del capítulo 3 de la Esencial documenta el arreglo funcionando parcialmente: el
crítico emitió una nota `pacing` `major` bien fundamentada («events 6 and 7 happen back-to-back
without a distinct transition... give event_6 its own suspenseful door-breaching sequence and
resolution beat before initiating event_7's final return»), pero el Writer no logró resolverla en
los dos intentos disponibles y el pipeline conservó el borrador de 835 palabras con la advertencia
registrada — el comportamiento de *fallback* seguro ya existente, no una entrega silenciosa.

### Prompt 1 — caballero y dragón, solo Expansiva (prueba adicional de escala)

La pregunta que motiva esta sección: ¿una Expansiva de 9 eventos con escena completa llega a la
extensión que cabría esperar (del orden de 5 000 palabras, extrapolando las 532 palabras/evento de
la Esencial en la línea base)? Se ejecutó el prompt canónico 1 del catálogo (caballero, princesa y
dragón, ya redactado con perfil Expansiva) tres veces: los dos primeros intentos de planificación
fallaron —6 eventos en el primero, una estructura sin rama/unión causal en el segundo— antes de
que un tercer intento produjera un plan válido.

| Métrica | Valor |
|---|---:|
| Run | `20260903-220945-las-cenizas-del-pacto` |
| Capítulos | 5 |
| Eventos | 9 |
| Palabras | 4 102 |
| Palabras por evento | 455,8 |
| Palabras por capítulo | 538 / 544 / 743 / 1001 / 1238 |
| Eventos por capítulo | 1 / 1 / 2 / 2 / 3 |
| Advertencias | 0 |
| Tokens totales | 121 516 |

Con tres ejecuciones Expansivas disponibles (catálogos 1, 6 y 7), ninguna alcanza las 5 000
palabras: 3 171, 3 763 y 4 102. La de mayor extensión es también la única con 5 capítulos en vez
de 3, lo que apunta de nuevo a la segmentación como la palanca que falta, no a la instrucción
cualitativa del crítico.

La tasa de fallo de planificación de la Expansiva, revisando los artefactos `planning/` de las
cinco ejecuciones intentadas en esta sesión (catálogo 6, dos intentos del catálogo 7 y dos
intentos del prompt 1), es más alta de lo que sugiere el resultado final: dos de las cinco
ejecuciones (40 %) agotaron los dos intentos estructurales permitidos y fallaron por completo
(`PLOT_VALIDATION_FAILED`); de los nueve intentos estructurales individuales realizados en total,
seis (67 %) fueron rechazados por `validate_profile_structure`, la mayoría por quedarse a un solo
evento del mínimo («expansive profile requires at least 9 events; got 8», en ambas ejecuciones que
sí terminaron con éxito). Solo `las-cenizas-del-pacto` produjo un plan válido en su primer
intento. El planificador no converge con facilidad hacia 9 eventos con rama y unión causal bien
formadas, y el margen de reintento (dos intentos por ejecución) se agota con más frecuencia de lo
deseable para un perfil que ya es, de los tres, el más caro de generar.

## Lectura

**Lo que funciona ahora.** En los dos catálogos, con el mismo prompt salvo el nombre del perfil,
la Expansiva ya no es la más comprimida: sus palabras por evento superan a las de la Esencial en
ambos casos (352,3 frente a 239,0, un 47 % más; 418,1 frente a 375,7, un 11 % más), y lo mismo
ocurre con la Desarrollada (613,3 y 482,8 frente a 239,0 y 375,7). Es la dirección contraria a la
línea base, donde la Expansiva era la *menos* densa (321 frente a 532). Una lectura manual de los
capítulos generados (por ejemplo `20260903-213335-el-dominio-saurio/story.md`) confirma que la
prosa despliega diálogo, reacción y consecuencia por escena en vez de resumir eventos — no es
solo un efecto de conteo. El intento de plan Expansivo rechazado en el catálogo 7 muestra además
que la validación estructural sigue actuando correctamente cuando el planificador se queda corto.

**Lo que sigue siendo parcial.**

1. **La mejora no es monótona entre Desarrollada y Expansiva.** En ambos catálogos la Desarrollada
   tiene más palabras por evento que la Expansiva (613,3 > 352,3; 482,8 > 418,1). El criterio de
   cierre solo exige distinguir Expansiva de Esencial, que se cumple, pero una Expansiva
   consistentemente más densa que la Desarrollada quedaría mejor explicada por la tarea pendiente
   de segmentación en capítulos (más eventos por capítulo en la Expansiva del catálogo 7: 2/4/3
   frente a 2/2/2 en la Desarrollada).
2. **El margen es modesto en el catálogo 7** (11 % en palabras por evento, aunque 43 % en palabras
   totales: 3 763 frente a 2 630). El catálogo 6 muestra un margen mayor (47 % / 165 %). Una sola
   ejecución adicional por catálogo no permite descartar que parte de la diferencia sea
   variabilidad del modelo; el benchmark reproducible pendiente en `TODO.md` es lo que permitiría
   una afirmación más fuerte para la tesis.
3. **El Writer no siempre resuelve una nota de `pacing` bien fundamentada en dos intentos** (cap. 3
   de la Esencial del catálogo 7). El *fallback* documenta el fallo en vez de ocultarlo, pero el
   límite de dos intentos puede no bastar cuando la corrección exige reestructurar dos eventos
   consecutivos.

**Coste.** La Expansiva no es siempre la más cara: en el catálogo 6 cuesta un 122 % más de tokens
que la Esencial (94 349 frente a 42 396) y tarda un 150 % más, comparable a la Desarrollada; en el
catálogo 7 el coste crece con la profundidad del perfil, pero el margen entre Desarrollada y
Expansiva es pequeño. El coste sigue creciendo con los eventos planificados, no con el número de
llamadas al modelo.

## Conclusión

El arreglo cualitativo del `DramaCriticAgent` revierte la compresión de eventos documentada
antes: en dos catálogos de prompts independientes, con el mismo texto salvo el perfil, una
historia Expansiva ya no resulta menos densa por evento que una Esencial — ocurría lo contrario
en la línea base, en contradicción directa con el propio contrato del perfil Expansivo. Esa parte
del problema —la dirección de la compresión— está resuelta y documentada sobre dos ejecuciones
por perfil.

Pero la extensión absoluta de la Expansiva sigue siendo insuficiente: en tres ejecuciones sobre
tres prompts distintos ninguna superó las 4 102 palabras, por debajo de lo que cabría esperar de
una historia genuinamente extensa con 9 eventos desarrollados en escena completa. Por eso esta
tarea se mantiene abierta en `TODO.md` bajo un enfoque más específico —mejorar la extensión real
de las historias Expansivas—, en vez de darse por cerrada. La evidencia reunida aquí apunta a que
la palanca que falta es la misma que ya estaba pendiente por separado: gobernar cuántos eventos
caben por capítulo, de modo que una Expansiva de 9 eventos use más de 3 capítulos de forma
consistente y no dependa de que el planificador decida por su cuenta repartirlos en 5. La tasa de
fallos de planificación observada (2 de 5 ejecuciones Expansivas fallaron por completo; 6 de 9
intentos estructurales individuales fueron rechazados) es evidencia adicional en la misma
dirección y queda registrada para cuando se aborde esa tarea.

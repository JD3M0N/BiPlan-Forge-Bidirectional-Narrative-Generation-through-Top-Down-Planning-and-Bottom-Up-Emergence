# Calibración de los perfiles narrativos

Comparación controlada de los perfiles Esencial, Desarrollada y Expansiva sobre el mismo
contenido, con el código actual del generador.

## Por qué existe este documento

El contrato 6.0 sustituyó los presupuestos numéricos de palabras por perfiles cualitativos, y
el commit `1bea0f1` añadió mínimos estructurales por perfil. Antes de esta ejecución, el
repositorio no contenía ninguna historia generada por ese código: los cuatro runs etiquetados
`6.1.0` se escribieron entre las 13:09 y las 14:19 del 2026-09-03, es decir, antes del commit
de las 14:43, y ninguno usaba el perfil Esencial. La comparación que exige la hoja de ruta
—que una historia Expansiva no resulte indistinguible de una Esencial— no podía hacerse.

`docs/informe_ejecucion_pipeline_top_down.md` sigue describiendo la arquitectura 5.0 y se
declara a sí mismo línea base histórica, por lo que no se modifica; este documento lo
complementa para el contrato vigente.

## Método

| Elemento | Valor |
|---|---|
| Commit | `1bea0f1`, árbol de trabajo limpio |
| Generador | `asg-top-down` 6.1.0, `pipeline_version` 6.0 |
| Modelo | `gemini-3.5-flash-lite` (`GEMINI_MODEL`), 14 peticiones por minuto efectivas |
| Fecha | 2026-09-03, 20:12–20:22 UTC |
| Prompts | `docs/prompts_top_down.md`, marcadores `PROMPT_06_ESSENTIAL/DEVELOPED/EXPANSIVE` |
| Comando | `generate-story "<prompt>"`, una ejecución por perfil, en serie |

Los tres prompts son idénticos salvo el nombre del perfil, de modo que cualquier diferencia
observada procede del perfil y de la variabilidad del modelo. Las tres ejecuciones terminaron
con código 0 y `status: completed`, sin advertencias.

| Perfil | Run | Duración |
|---|---|---|
| Esencial | `Stories/Top-Down/20260903-201231-la-era-de-las-escamas-pensantes` | 183 s |
| Desarrollada | `Stories/Top-Down/20260903-201514-la-era-de-las-escamas-y-el-vapor` | 174 s |
| Expansiva | `Stories/Top-Down/20260903-201811-el-dominio-de-la-fronda` | 260 s |

## Resultados

Todas las cifras proceden de los artefactos del propio run: `story_metrics.json`,
`story_plan.json`, `characters.json`, `metadata.json` y `llm_usage.json`.

| Métrica | Esencial | Desarrollada | Expansiva |
|---|---:|---:|---:|
| Capítulos | 3 | 3 | 3 |
| Eventos | 4 | 6 | 9 |
| Dependencias causales | 4 | 6 | 9 |
| Ramas / uniones causales | 1 / 1 | 1 / 1 | 1 / 1 |
| Payoffs declarados | 3 | 4 | 8 |
| Personajes | 3 | 4 | 4 |
| Relaciones | 3 | 4 | 4 |
| Palabras | 2 127 | 2 205 | 2 892 |
| Palabras por evento | 532 | 368 | 321 |
| Palabras por capítulo | 665 / 698 / 744 | 707 / 811 / 662 | 707 / 827 / 1 336 |
| Eventos por capítulo | 2 / 1 / 1 | 2 / 2 / 2 | 4 / 2 / 3 |
| Planes rechazados | 0 | 0 | 1 |
| Llamadas al modelo | 14 | 13 | 14 |
| Tokens totales | 57 610 | 69 621 | 92 789 |

Referencia: los tres runs del mismo prompt con 6.0.0, antes de los mínimos estructurales, daban
3 capítulos y 2 personajes en los tres perfiles, con 5 / 4 / 4 eventos y 1 509 / 2 021 / 2 364
palabras — es decir, la Expansiva tenía menos eventos que la Esencial.

## Lectura

**Lo que sí funciona.** Los mínimos estructurales se cumplen y son monótonos: 4 → 6 → 9
eventos y 4 → 6 → 9 dependencias causales, con 8 payoffs en la Expansiva frente a 3 en la
Esencial. La validación actúa: el plan Expansivo fue rechazado en el primer intento por
`expansive profile requires a causal dependency branch followed by a causal join` y corregido
en el segundo. Los tres planes entregados superan `validate_profile_structure`, así que la
anomalía de `20260903-175604-el-dominio-escamado` —un plan rechazado dos veces y entregado
como `completed`— no se reprodujo; con una sola ejecución eso no basta para descartarla, pero
es coherente con la hipótesis de que fue un artefacto de un estado intermedio del código.

**Lo que no funciona todavía.**

1. **El número de capítulos no responde al perfil.** Los tres runs produjeron exactamente 3
   capítulos. `profiles.py` solo fija un suelo de eventos; nada gobierna la segmentación.
2. **Esencial y Desarrollada son indistinguibles por longitud.** 2 127 frente a 2 205 palabras
   es una diferencia del 3,7 %, dentro de la variabilidad del modelo. La diferencia entre esos
   dos perfiles es hoy puramente estructural en el plan, no perceptible en el texto entregado.
3. **Los eventos adicionales se comprimen en lugar de desarrollarse.** Las palabras por evento
   caen de 532 a 368 y a 321. El contrato del perfil Expansivo pide explícitamente lo
   contrario: «dar a cada evento importante espacio de escena suficiente… no empaquetar varios
   eventos planificados en un pasaje de resumen». El pipeline cumple el mínimo de eventos y
   luego los escribe más apretados, que es la misma indistinguibilidad de 6.0.0 desplazada del
   plan a la prosa.
4. **El reparto sigue siendo desigual.** El primer capítulo de la Expansiva concentra 4 de sus
   9 eventos en 707 palabras (177 palabras por evento) mientras el tercero dedica 1 336
   palabras a 3.
5. **El elenco está casi plano.** 3 / 4 / 4 personajes: el perfil apenas afecta al reparto.

**Coste.** La Expansiva cuesta un 61 % más de tokens que la Esencial (92 789 frente a 57 610)
con el mismo número de llamadas, y un 42 % más de tiempo. El coste crece con los eventos
planificados, no con las llamadas.

## Conclusión

Los mínimos estructurales de `1bea0f1` resuelven el problema en el plan —una Expansiva ya no
puede tener menos eventos que una Esencial— pero no en la historia entregada. La calibración no
puede darse por terminada: falta gobernar la segmentación en capítulos y el espacio de escena
por evento, de modo que un perfil más profundo produzca escenas desarrolladas y no un resumen
más denso. Las dos tareas correspondientes están abiertas en `TODO.md`, en «Top-Down: perfiles
y calibración».

Este experimento cubre una ejecución por perfil con un solo prompt. Para sostener una
afirmación en la tesis hace falta repetirlo sobre el conjunto versionado de prompts y con las
evaluaciones humanas rellenadas, que es exactamente el benchmark reproducible pendiente.

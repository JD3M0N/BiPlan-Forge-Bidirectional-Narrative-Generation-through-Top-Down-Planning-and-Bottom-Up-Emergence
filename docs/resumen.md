# Resumen técnico del proyecto

Resumen único que sustituye a los documentos de diseño anteriores (simulación escénica, marco
híbrido, estado del arte, mejoras, guion teatral, promesas PPP, catálogo de prompts y validación
7.5). El detalle histórico sigue en git (`git log -- docs/`). Las fuentes de la tesis son los dos
PDF de esta carpeta: la tesis de Roger Fuentes y *Sanderson Craft*.

## Tesis en tres frases

Un plan validado decide **qué** pasa. Unos personajes que solo saben lo que presenciaron deciden
**cómo** pasa. Un narrador que cura el registro de esa función decide **cómo se cuenta**.

```text
petición → plan (DAG) → guion → función (director + actores) → log → narrador → historia
           Top-Down              Bottom-Up                              discurso
```

Hipótesis: H1, representar el plan antes de narrarlo aporta algo que escribirlo directo no (formato
`simulated` frente a `narrative`); H2, la memoria propia de cada personaje mejora las escenas frente
a dársela toda (`--actor-memory own` frente a `shared`); H3, cada mecanismo se gana su complejidad.
Los experimentos están en `planning/fichas.md` (EXP-1, EXP-2, EXP-5), dentro de la fase P05 del `planning/roadmap.md`.

Contexto: la *paradoja narrativa* (la simulación pura no hace historia; la planificación pura con
LLM pierde compromisos y riqueza). La tradición híbrida (Façade, Thespian, Virtual Storyteller,
Sabre) y su versión con LLM (Generative Agents, StoryBox, WSE-bench) sostienen mezclar ambas.

## Plan validado (Top-Down)

`planning/graph.py` valida el plan como DAG (ids únicos, órdenes consecutivos, sin ciclos,
referencias existentes, `payoff_of` hacia atrás). Sus errores van en inglés porque se reinyectan al
prompt de reparación. Los perfiles (Esencial, Desarrollada, Expansiva) son cualitativos; solo el
suelo de eventos por capítulo viaja como número.

**Promesas (Promise-Progress-Payoff):** el ledger corre con el plan congelado y cada apertura,
progreso y pago cita el id de un evento existente; el modelo no puede inventar un beat. Invariantes:
apertura < progresos < pago sobre el orden topológico, pago de la promesa primaria en el último
capítulo, número de promesas dentro de la banda del perfil. Se apaga con `ASG_PROMISE_LEDGER=false`
(brazo de control); `promise_audit.json` mide el efecto.

## Guion teatral

`--format script` produce `script.json` (`PlayScript`) y un `story.md` renderizado. Dos métodos con
el mismo validador (`script/validation.py`), para compararlos a ciegas y borrar el perdedor (EXP-3):
**native** (un `PlaywrightAgent` escribe cada capítulo como acto) y **adapted** (la prosa
narrativa se adapta a actos).

## Función simulada (híbrido)

`--format simulated` añade casting, performance y narration tras el guion nativo.

- **Los actores nunca ven el guion:** solo circunstancias, objetivo, nota del director y su memoria.
  Test de contrato: `test_no_actor_ever_sees_the_plan_or_a_future_scene`.
- **Memoria propia:** turno público lo ven los presentes, susurro solo los destinatarios,
  pensamiento solo quien lo piensa. No hay almacén común. Recuperación determinista sin embeddings
  (relevancia 1,0, recencia 0,6, importancia 0,5, compañía 0,3; 6 registros y 2 reflexiones).
  Las relaciones se sustituyen, no se acumulan.
- **Compuertas de conocimiento** (`cast_bible.json`): `known_by` sabe antes de la primera escena;
  quien lo descubre en escena va en `revealed_by`. No relajar esa validación.
- **Director:** sugiere motivaciones, nunca réplicas; al agotar el presupuesto de un beat
  (`ASG_STAGE_TURNS_PER_BEAT`, 8) lo cierra con un `stage_event`.
- **Modo 7.5:** `--simulation-mode fixed` (control) o `adaptive` (un hito no representado permite
  revisar solo las escenas futuras; una propuesta y una reparación por frontera; si fallan, la
  función termina abierta). El plan original no se toca; las revisiones van en `active_plan/`.
  `--plan-from <run>` repite una función con el mismo plan, guion y casting.
- **Narrador:** cura (corta, funde, reordena) pero no inventa; manda el log. Puntos de vista
  modulares en `stage/voices.py` (`omniscient`, `limited`, `first_person`). Capítulo sin turnos
  visibles queda `absent`. Hay respaldo determinista si casting o narración fallan.
- **Qué se mide** (`simulation_metrics.json`): `script_echo` (cerca de 1 = recitan),
  `repetition_ratio` (solo habla), `action_repetition_ratio`, `unknown_mentions`,
  `dialogue_survival` (cerca de 1 = el narrador transcribió), compresión de narración.
  (El juez LLM `audit-stage-run` se retiró en 7.11: aprobaba casi todo.)
- **Comparabilidad:** las funciones 7.0 y 7.1 no son comparables con 7.2+ (el tope de recuperación
  no se aplicaba, casi no había destinatarios, la nota del director se repetía). Separar por
  `pipeline_version`.

## Inventario de objetos (7.6)

`--inventory` (o `ASG_INVENTORY=true`) añade la etapa `props` entre casting y performance, y da
objetos a los personajes. Apagado —el defecto— no cambia ningún prompt, esquema ni artefacto: un
test lo comprueba sobre los dos brazos.

- **El modelo propone, el código decide.** El actor escribe un `item_action` (verbo y el *nombre*
  del objeto) y `stage/inventory.py` lo valida contra la verdad que él mismo guarda. El
  `Inventory` de Concordia pregunta a un LLM qué cambió después de los hechos, así que no se puede
  repetir; esto es determinista como `stage/memory.py`. La lección de Intra: la verdad del mundo
  vive en código, nunca en el prompt.
- **Seis verbos, una regla cada uno.** `use`, `give`, `drop`, `hide` y `show` exigen tenerlo en la
  mano; `take` exige que esté a la vista (en el lugar, o en manos de alguien presente sin
  esconder). Los rechazos van en inglés ASCII con su código (`UNKNOWN_ITEM`, `ITEM_NOT_HELD`,
  `ITEM_OUT_OF_REACH`, `INVALID_ITEM_TARGET`) y se reinyectan como cualquier otro, igual que
  `graph.py`.
- **Un objeto solo lo percibe quien lo ve.** Los testigos de un movimiento son los del turno más
  quien entrega y quien recibe; un traspaso en susurro solo lo ven esas manos; `hide` lo percibe
  únicamente su portador. Con `--actor-memory shared` se amplía como cualquier turno, salvo
  `hide`. Por eso el inventario amplía la asimetría de la que viven las visiones: una narración
  limitada solo puede contar los traspasos que su personaje presenció.
- **Nombres, nunca ids.** Al actor se le enseña `LO QUE LLEVAS` y `LO QUE VES`; el objeto se
  resuelve por nombre completo o por una palabra que identifique uno solo, como un destinatario.
  `props.json` guarda los ids y el actor no los ve.
- **El utilero coloca, no decide consecuencias.** `PropMasterAgent` reparte los `StoryObject` del
  mundo (todos entran) y añade los personales que definan a alguien; `stage/props.py` valida y
  normaliza (coloca el objeto del mundo olvidado donde el plan lo usa primero, desesconde lo que
  nadie lleva, recorta los personales que pasan de `MAX_PERSONAL_PROPS`, que nunca viaja a un
  prompt). Si la etapa falla, `fallback_props` coloca los objetos del mundo y el run lo registra.
- **El director ve la utilería, incluida la escondida,** y puede sugerir usarla; nunca la dicta.
- **Qué se mide:** `props`, `item_actions`, `item_actions_by_verb`, `item_repairs`,
  `props_used_ratio` (cerca de 0 = los objetos fueron decorado), `hidden_item_actions`,
  `secret_handoffs` e `item_witness_share` (bajo = el tráfico de objetos fue privado, así que dos
  narradores del mismo log discrepan sobre quién tiene qué). Sin inventario son **no medidas**,
  nunca cero. Todas salen de `performance.json`, así que `asg-recompute` las
  reproduce.
- **Lo que el árbitro no cubre.** El `stage_event` del director es texto libre y no pasa por él:
  en la validación 7.6 cerró un beat diciendo que el sello «resbala de las manos de Aldren»
  cuando la verdad del inventario lo tenía en las de Elara. Tampoco se arbitra la acción de un
  actor que menciona un objeto sin declarar un movimiento (10 de 21 menciones en ese run). Las
  dos quedan en la ficha EXP-6 y en la idea del árbitro de acciones físicas.
- **Un rejuego viste el escenario otra vez.** `--plan-from` congela petición, mundo, personajes,
  plan, guion y casting, pero no la utilería: la etapa `props` vuelve a correr, porque el run de
  origen puede no tener ninguna (es el caso de todo el corpus anterior a 7.6). Son una llamada y
  un eje más que vigilar al emparejar.
- **Artefactos:** `props.json`, `stage/inventory.jsonl` (una línea por movimiento aplicado) y
  `performance.json` en contrato 4, cuyos turnos pueden traer `item_action` y que guarda la
  utilería inicial y final. El eje `inventory` de `pairing.py` lee `performance.json`, así que
  todo el corpus anterior se empareja como «sin inventario».

## Validación real 7.5 (2026-09-30)

Dos funciones desde el mismo plan de «La Sombra del Volcán» 7.4, con el mismo presupuesto:
`fixed` completó 6 escenas y 48 turnos (5 de 6 beats, 1 forzado); `adaptive` terminó con cierre
abierto tras 2 escenas y 16 turnos (1 beat logrado). Ninguna cumplió las 2 promesas originales.
La auditoría literal de 62 contextos de actor no halló pensamientos ajenos ni susurros no
presenciados. Son dos observaciones de una premisa, no muestra suficiente para inferir calidad.

## Narración simulada: resumida o por selección (2026-10-27)

Cinco funciones completas renarradas con `asg-generate --narrate-from` desde `Stories/Stagecraft/`
(`20261019-141038`, `20261020-174833`, `20261020-213446`, `20261021-192148`, `20261022-125649`),
dos brazos cada una: A con las opciones del run (`reported`) y B con
`--narration-method selected --line-editor --style-examples`. Cero capítulos `fallback`, cero
`[SELECTION_FALLBACK]` y cero `[LINE_EDIT_UNAVAILABLE]`.

| Medida (5 pares) | A `reported` | B `selected` + editor + ejemplos |
|---|---|---|
| `dialogue_survival` | 0,48–0,67 | 0,73–0,85 |
| Réplicas directas por run | 12–35 | 18–68 |
| % con verbo de habla (regex) | 30–62 | 3–22 |
| Párrafos con más de 2 indirectas (regex) | 1–6 por run | 0 en 4 pares, 2 en el par 4 |

Las dos últimas filas salen de un script con expresiones regulares, no del código del repo: son
aproximadas. Lectura a ciegas de Josue en `asg-studio` (sesión `p021-narracion`): B en los pares
2 y 5, A en los pares 3 y 4, «ninguno» en el par 1. **Empate 2–2–1.**

Lectura: B corrige lo que SIM-24 describía (actas de réplicas indirectas, verbo de habla en casi
cada línea), pero conserva más del log (`dialogue_survival` por encima de 0,6) y no gana a ciegas.
Con empate, el predeterminado no cambia: `reported`, sin editor y sin ejemplos, que gasta menos
llamadas. B queda como opción para el análisis horizontal (T4, P05). Cinco pares y un solo
lector no distinguen una preferencia pequeña.

## Brazos Top-Down: fichas, crítico con cita, editor y ejemplos (2026-10-27)

Dos planes nuevos con Flash-Lite, sin `GEMINI_PROSE_MODEL`: la cubana (prompt libre de
`20261012-163919-de-la-oscuridad-al-mundo`, `essential`) en `20261027-220217-el-giro-de-la-vieja`
y la regencia (`brief.json` de `20261012-163629-la-regencia-de-las-escamas`, `developed`) en
`20261027-220405-la-regencia-de-las-escamas`. De cada plan, dos borradores por brazo con
`--plan-from <run> --format narrative --no-audio`: A sin brazos y B con
`--scene-cards --anchored-critic --line-editor --style-examples`. Los ocho llevan `source_run.json`
con `reused: plan`. Dos corridas de la cubana fallaron por infraestructura (límite por minuto y
respuesta vacía) y se repitieron; los runs fallidos quedan en `Stories/`.

| Medida sobre la prosa final (8 runs) | A (4 runs) | B (4 runs) | Umbral |
|---|---|---|---|
| Nombres repetidos | 0,01–0,06 | 0,00–0,03 | 0,20 |
| Réplicas con coletilla emocional | 0,00–0,21 | 0,00 | 0,30 |
| Gerundio en la coletilla | 0,06–0,29 | 0,00–0,08 | 0,40 |
| Símiles por 100 palabras | 0,00–0,11 | 0,00–0,17 | 0,25 |
| Párrafos marcados | 0,25–0,68 | 0,00–0,10 | — |
| Palabras | 1.581–1.827 | 1.197–1.503 | — |

**TD-8: cumple** los cuatro umbrales de `writing/craft_evidence.py` en los ocho runs, con o sin
brazos. Las 500 palabras que pidió la cubana no se alcanzan en ninguno (mínimo 1.197), y la
legibilidad por palabras largas no tiene umbral (8,4–8,9 % en la cubana, 11,6–13,8 % en la
regencia).

**TD-3: cumple.** Ningún capítulo con nota grave sale como `draft` (los dos `draft` de la regencia
A no tenían notas) y no hay fallos de esquema en ningún intento. Cuatro capítulos salieron como
`best_candidate` con `WRITER_BEST_CANDIDATE` (tres en la cubana A, uno en la cubana B2), ninguno
copia del borrador. Intentos rechazados: A, 8 en la cubana y 0 en la regencia; B, 3 y 2. Leído a
mano solo una muestra de dos ediciones de la cubana B1: atienden las notas que citan, pero la
presentación de los personajes queda forzada («un ser humano brillante que trabajaba como
programador…»). No se leyeron las demás.

**Lectura a ciegas** de Josue en `asg-studio` (sesión `p022-topdown`, clave en
`Evaluations/estudio/claves/`): A gana en cubana 1, cubana 2 y regencia 2; B gana en regencia 1.
**A 3, B 1.**

Lectura: B arregla las cifras de legibilidad (coletillas y gerundios a casi cero) y acorta el
texto, pero un lector humano prefiere el brazo sin brazos en tres de cuatro. Las cifras de
legibilidad no predicen la preferencia. Decisión del bloque: `scene_cards`, `anchored_critic`,
`line_editor` y `style_examples` quedan **apagados** en Top-Down; no se borra ninguno y B queda
como opción para el análisis horizontal (T4, P05). Cuatro pares y un solo lector no distinguen una
preferencia pequeña. `name_choices.json` salió en los dos planes y no se evaluó aparte.

## El plan cumple el brief y la ficción va en español (2026-10-28)

Dos runs en Stagecraft 7.21 con los predeterminados, sin arreglar nada (~46 llamadas, 29 y 17):
un narrativo Expansivo con el `brief.json` de `20261019-141038-las-islas-del-cielo`
(`Stories/Stagecraft/20261028-123459-las-islas-del-cielo`) y un guion nativo del prompt 03, la
médica del faro (`Stories/Stagecraft/20261028-123833-el-secreto-del-faro`).

**TD-9, no cumple.** El plan (10 eventos, 5 capítulos) trae el ascenso (evento 2) y los seis
lugares (Nidos, Mercado, Jardines, Archivo, Hondonada, Raíz). La tripulación **no** se divide
entre quedarse, volver y sacar provecho: solo aparece el que saca provecho (Gaspar, eventos 6 y
9); quedarse o volver aparece al final, como decisión de los zefaríes. La decisión final (evento
10) es «bajar o quedarse», pero su coste queda en un «cargamento de verdades y pérdidas» sin decir
quién paga qué. `plan_review.json` lo aprobó con `notes` vacías, así que el crítico no comprueba
cada giro de la trama. Un run no distingue ruido de efecto (la ficha ya avisa: 1/6 a 4/6 de
beats entre versiones).

**TD-2, cumple.** Slug `el-secreto-del-faro`; nombres, roles, títulos de acto y descripciones del
reparto en español; la médica es «Sabela Carballo, Médica de la isla», «la médica» en el texto, y
ninguna vez «doctor». Cero palabras en inglés en `story.md`. El plan interno sigue en inglés,
como manda la frontera de idioma. Falta el mismo control en un guion con el objetivo de escena
visible al lector, que aquí no se imprime.

## Validación real de 7.22 antes de congelar (2026-10-28)

Tres runs con los predeterminados, el prompt 03 (la médica del faro), perfil Esencial y sin audio,
sin arreglar nada. Llamadas: narrativo 22, guion 18, simulado 227 (0 fallidas en los dos
primeros; 9 intentos fallidos en el simulado, 570 k tokens).

| Run | Formato | Resultado |
|---|---|---|
| `20261028-192554-el-faro-de-la-habitacion-cerrada` | narrativo | completo, 3 capítulos, 1 543 palabras |
| `20261028-192858-el-misterio-del-faro` | guion nativo | completo, 3 actos, 1 120 palabras |
| `20261028-192554-el-misterio-del-faro` | simulado | completo, 3 capítulos del narrador, 1 578 palabras |

**Comprobaciones del simulado, todas cumplen.** Ningún capítulo `fallback`
(`narration_source_fallbacks` 0; 3 de 3 `source: narrator`, uno con dos intentos) ni
`NARRATION_BEST_ATTEMPT`. 0 de 47 pensamientos en inglés en `turns.jsonl`. Todo estancamiento
(`stall`) llega después de una decisión `turn` del director en cada escena, antes del tope. Ninguna
línea fuera de la ficción en `story.md` (sin vocabulario de código). Slug `el-misterio-del-faro` y
nombres en español en los tres runs.

**Limitación conocida: beats forzados.** 3 de 6 beats se forzaron (`beats_forced` 3,
`beats_achieved` 3, `beat_completion_ratio` 0,5): son los `final` con `achieved: false` de tres
escenas. Es la misma proporción que ya se midió en 7.12 (5 de 10) y no es un defecto nuevo.

**Observaciones fuera de los criterios**, sin tocar el código por la congelación:
- Narrativo: «de el faro» sin contraer en el primer párrafo.
- Guion: el reparto pierde al meteorólogo (4 de los 5 personajes del brief) y la médica sale con el
  rol «médica de Beatriz isla».
- Simulado: los títulos de capítulo salen sin tildes («La habitacion cerrada»).

Un run por formato no distingue ruido de efecto.

## Amenazas a la validez

Los jueces LLM prefieren sus propias generaciones (Gemini juzga a Gemini) y puntúan mal escritura
creativa; dos corridas del mismo prompt difirieron hasta 16 puntos; una matriz simulada de 9 runs
no cabe en la cuota diaria gratuita. La evaluación humana decide (EXP-4).

## Prompt canónico de regresión

Usado por `test_gemini_live.py` (variante Expansiva, caso 1: caballero, princesa y dragón). Está
ahora dentro del propio test, que es su única fuente.

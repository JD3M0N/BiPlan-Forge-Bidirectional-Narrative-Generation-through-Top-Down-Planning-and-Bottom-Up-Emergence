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
Los experimentos están en `TODO.md` (EXP-1, EXP-2, EXP-5).

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
  `audit-stage-run` añade un juez LLM sobre filtraciones de conocimiento y fidelidad.
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
  nunca cero. Todas salen de `performance.json`, así que `recompute-simulation-metrics` las
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

## Amenazas a la validez

Los jueces LLM prefieren sus propias generaciones (Gemini juzga a Gemini) y puntúan mal escritura
creativa; dos corridas del mismo prompt difirieron hasta 16 puntos; una matriz simulada de 9 runs
no cabe en la cuota diaria gratuita. La evaluación humana decide (EXP-4).

## Prompt canónico de regresión

Usado por `test_gemini_live.py` (variante Expansiva, caso 1: caballero, princesa y dragón). Está
ahora dentro del propio test, que es su única fuente.

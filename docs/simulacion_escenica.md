# La función simulada: los personajes actúan el guion y la historia se narra del log

El formato `simulated` es la mitad Bottom-Up del pipeline híbrido. El plan y el guion deciden
**qué tiene que pasar**; la función decide **cómo pasa**, y la historia final se escribe a partir
del registro de lo que pasó de verdad, no de lo que estaba previsto.

```text
analysis → architecture → world → characters → planning → plan_review → promises
  → drafting · critique · revision   (el guion nativo, sin tocar)        [Top-Down]
  → casting       dossier de actor + compuertas de conocimiento          [nuevo]
  → performance   escena a escena: director → turnos → comprobación      [Bottom-Up]
  → narration     el log filtrado por el punto de vista → prosa          [nuevo]
  → story · audio
```

Se elige con `--format simulated`, con `ASG_STORY_FORMAT=simulated`, con la cuarta opción de la
consola o con el cuarto botón del bot. El formato simulado **siempre** consume el guion nativo:
adaptar prosa a guion para después volver a narrar prosa haría pasar el mismo material dos veces
por el modelo sin ganar nada.

## Por qué el guion no se le da a los actores

Un actor al que se le entrega su réplica la recita. Un actor al que se le da una razón, actúa.
Por eso el director guarda el guion y a cada intérprete le llegan solo cuatro cosas: las
circunstancias de la escena, su objetivo, la nota del director y su propia memoria.

Lo que **nunca** entra en el contexto de un actor: el plan, los ids o títulos de eventos, los
capítulos, las escenas futuras y las réplicas guionizadas. Hay un test que lo comprueba sobre un
run entero (`test_no_actor_ever_sees_the_plan_or_a_future_scene`), y
`stage/validation.strip_internal_ids` limpia el objetivo y el escenario antes de que salgan, porque
los escribió el Dramaturgo mirando el plan y pueden arrastrar un id.

La medida de si esto funciona es `script_echo`: cuánto se parece cada réplica representada a la
mejor réplica guionizada de su escena. Cerca de 1 significa que los actores recitaron y la
simulación no aportó nada.

## Memoria propia: la aportación central

Cada personaje tiene su **propio flujo de memoria**, y ahí solo entra lo que percibió.

| Qué ocurre | Quién lo percibe |
|---|---|
| Turno público | Todos los que están en escena |
| Susurro (`whisper`) | Solo quien habla y sus destinatarios |
| Pensamiento | Solo quien lo piensa |

No hay un almacén común del que filtrar nada: un hecho que un personaje no presenció **no se
escribió** en su memoria. Eso es lo que mantiene un secreto en secreto sin pedirle a un modelo
que lo guarde, y es la diferencia que mide la ablación.

La recuperación es determinista y sin embeddings, así que el mismo run puntúa igual en cualquier
máquina:

```text
puntuación = 1,0·relevancia + 0,6·recencia + 0,5·importancia + 0,3·compañía
recencia   = 1 / (1 + 0,25 · escenas de distancia)
```

`relevancia` es solapamiento léxico ponderado por rareza (sin tildes, reusando `normalize()` del
emparejador de esqueletos); `compañía` favorece los recuerdos que implican a quien está delante.
Viajan los **6** mejores registros más las **2** últimas reflexiones, pasen lo que pasen. La escena
en curso viaja entera aparte, como memoria de trabajo, y por eso se excluye de la recuperación.

Cada recuperación se guarda con su desglose en `memory/<id>/retrievals.json`.

**Consolidación, no acumulación.** La postura de un personaje hacia otro se **sustituye** en cada
reflexión, nunca se añade. Un log que guardara «aliada» y luego «me traicionó» dejaría al actor con
las dos a la vez, y jugaría mal ambas. El historial sigue en los registros; lo que el actor lee es
el estado.

### La ablación

`--actor-memory shared` reparte todo lo público a todo el reparto, dejando igual el resto del
sistema. Es el brazo de control: cualquier diferencia entre dos corpus es atribuible al modelo de
memoria y a nada más. El proxy determinista es `unknown_mentions` (un hablante nombra a alguien de
quien no tiene ningún registro); la medición seria la da la auditoría opcional con LLM.

## El bucle de una escena

```text
el director abre el beat        → elige quién empieza y da hasta 2 notas jugables
un actor mueve                  → pensamiento privado, acción visible, habla
se valida                       → se normaliza, o se repara una vez, o se salta el turno
se acepta                       → se calcula quién lo presenció y se escribe en esas memorias
cada 3 turnos, o al tope        → el director juzga si el beat ha ocurrido
el beat ocurre                  → se abre el siguiente
se agota el presupuesto         → el mundo interviene, visiblemente, y el beat se marca forzado
la escena acaba                 → cada actor reflexiona y su estado se consolida
```

`ASG_STAGE_TURNS_PER_BEAT` (8 por defecto) es el presupuesto por beat. Un beat forzado se cierra
con un `stage_event`: algo que hace el mundo y que todos ven, que entra en el log como un turno
más. Así el log sigue siendo la única fuente de la historia, y un beat forzado se representó en vez
de afirmarse.

### Qué se normaliza y qué se rechaza

Como en `script.py`: se normaliza lo que tiene una sola lectura posible y se rechaza lo que
corrompería el log. Los mensajes van en **inglés ASCII** porque se reinyectan literales.

- **Se normaliza**: comillas y rayas envolventes (en bucle, porque el modelo suele poner las dos),
  paréntesis en acción y pensamiento, destinatarios que no están en escena, y un susurro sin
  destinatario, que pasa a público.
- **Se rechaza**: el turno vacío, los identificadores internos, más de un beat por turno y la
  **repetición** (solapamiento ≥ 0,75 con una de las 3 últimas réplicas propias). El umbral es
  deliberadamente más estricto que el 0,4 que IBSEN usó y aun así encontró insuficiente.

Un turno rechazado se reintenta una vez con la corrección exacta; si vuelve a fallar se salta, y
queda en `rejected.jsonl` con su motivo.

## El narrador: curación, no transcripción

Un log no es una historia: es un registro de cosas que pasaron, en su orden y a su granularidad.
Convertirlo en prosa es seleccionar, comprimir y ordenar — el trabajo que una simulación no puede
hacerse a sí misma, y la razón por la que los generadores puramente simulacionistas producen
transcripciones.

El contrato es de una sola dirección: **el log es la única fuente de sucesos**. El narrador puede
cortar, fundir y reordenar dentro de un capítulo; no puede inventar un beat. Donde el plan y el log
no coincidan, manda el log, porque el log es lo que pasó.

### El punto de vista es modular

`stage/voices.py` define una estrategia por voz. Cada una responde a dos preguntas: quién narra y
qué turnos le llegan. Añadir un punto de vista es añadir una estrategia; el prompt solo recibe el
resultado.

| Voz | Qué ve el narrador |
|---|---|
| `omniscient` (defecto) | Todos los turnos y los pensamientos de todos |
| `focalized` | Todo lo público, más los pensamientos del personaje focal de cada escena |
| `first_person` | Solo lo que el narrador presenció, con solo sus propios pensamientos |

`--voice` o `ASG_NARRATIVE_VOICE` lo eligen. La voz **solo** cambia la narración: el plan, el guion
y la función son idénticos byte a byte entre dos runs que solo difieren en ella.

En primera persona la memoria propia paga dos veces: un capítulo solo puede escribirse con los
turnos que su narrador percibió, que son exactamente los que ya están en su flujo.

### El respaldo determinista

Si el narrador no puede correr, `stage/fallback.py` convierte el log en prosa sin interpretarlo:
habla a diálogo con raya, acciones a frases, pensamientos a interioridad referida. Es parte del
contrato, como el narrador de respaldo del escape room, y además sirve de suelo de comparación: el
mismo log, sin ninguna interpretación.

## Artefactos de un run simulado

Además de todo lo Top-Down (plan, promesas, etapas del guion):

| Artefacto | Contenido |
|---|---|
| `script.json`, `script_metrics.json`, `script.md` | El guion que sirvió de libro del director |
| `cast_bible.json` | Dossiers y compuertas de conocimiento, con `fallback: true` si se derivó |
| `stage/actors/<id>.json` | La instrucción de sistema exacta y el dossier que recibió cada actor |
| `stage/<escena>/brief.json` | Beats, reparto, lugar, compuertas y réplicas de referencia |
| `stage/<escena>/turns.jsonl` | Cada turno aceptado, con testigos, nota y memorias recuperadas |
| `stage/<escena>/contexts.jsonl` | El bloque de prompt variable exacto de cada turno |
| `stage/<escena>/rejected.jsonl` | Cada intento rechazado, con su código y su motivo |
| `stage/<escena>/transcript.md` | La escena legible, con acciones y pensamientos |
| `memory/<id>/records.json` | El flujo de memoria completo de un personaje |
| `memory/<id>/retrievals.json` | Cada recuperación con el desglose de su puntuación |
| `performance.json` | La función entera más los ajustes con los que corrió |
| `performance.md` | El transcript legible de toda la función |
| `narration/chapter-NNN.md` (+intentos) | La prosa por capítulo |
| `narration.json` | La voz, el narrador y cuántos turnos vio cada capítulo |
| `simulation_metrics.json` | Todas las cifras observadas |
| `story.md`, `story_metrics.json` | La historia final, medible contra cualquier run narrativo |

`performance.json` guarda `settings` con los pesos, el k, el decaimiento y el umbral que se usaron,
para que un lector pueda repetir o comparar sin leer el código.

## Qué se mide

Ninguna de estas cifras viaja a un prompt; hay un test que lo comprueba.

- **Cobertura**: `beats_achieved` frente a `beats_forced`, `beat_completion_ratio`,
  `turns_per_beat`, `director_checks`, `stage_events`.
- **Actuación**: turnos, palabras de habla, acción y pensamiento, susurros, `unprompted_turns`
  (iniciativa), `distinct_tactics`, turnos rechazados y saltados.
- **Repetición**: `repetition_ratio` y `mean_self_similarity`.
- **Improvisación**: `script_echo`.
- **Frontera de conocimiento**: `unknown_mentions`.
- **Memoria**: `memory_records`, `retrievals`.
- **Narración**: `dialogue_survival`, `narration_source_fallbacks`, `narrated_words`.

`report-simulations` las agrega por voz, memoria, perfil y versión, y escribe CSV con `--csv`.
`report-story-craft --format prose` junta las historias narrativas y las simuladas, que sí son
comparables entre sí porque las dos entregan prosa.

## Coste

Por escena salen unas 19 llamadas: ~12 de actor, ~4 de director y ~3 de reflexión. Una historia
Esencial de 6 a 10 escenas suma entre 150 y 220 llamadas contando las etapas previas y la
narración, frente a las ~25 de un run narrativo. A 14 RPM son unos 11 a 16 minutos. Los mandos son
`ASG_STAGE_TURNS_PER_BEAT` y el perfil narrativo.

## Degradación

| Falla | Qué pasa |
|---|---|
| El casting | Dossier derivado de `characters.json` y aviso `[CASTING_FALLBACK]` |
| La apertura de un beat | El beat se abre sin nota, `[DIRECTION_FALLBACK]` |
| La comprobación de un beat | Cuenta como «no alcanzado» hasta el tope, `[BEAT_CHECK_FALLBACK]` |
| Un turno, dos veces | Se salta, `[STAGE_TURN_SKIPPED]` |
| Una reflexión | El estado se queda como estaba, `[REFLECTION_FALLBACK]` |
| El narrador de un capítulo | Narrador de respaldo, `[NARRATION_FALLBACK]` |
| Una escena entera sin un solo turno válido | Aborta con `STAGE_PERFORMANCE_FAILED` |
| Cuota de Gemini | Aborta, como en todo el pipeline |

## Cómo comparar

- **Simulada contra narrativa**, mismos prompts: `compare-story-runs` a ciegas sobre `story.md`, y
  `report-story-craft --format prose --group format` para las cifras de artesanía.
- **Memoria propia contra compartida**: dos matrices que solo difieren en `--actor-memory`, leyendo
  `unknown_mentions` y la auditoría de frontera de conocimiento.
- **Entre voces**: `--voice` sobre los mismos prompts; el plan y la función no cambian, así que la
  comparación aísla la narración.
- **Contra el suelo**: el narrador de respaldo sobre el mismo log dice cuánto aporta el narrador
  LLM.

Como con cualquier medición de este repositorio, un n pequeño no basta: la réplica documentada en
[artesania_narrativa.md](artesania_narrativa.md) midió hasta 16 puntos de diferencia entre dos
corridas del mismo prompt y la misma versión.

## De dónde sale cada decisión

El recorrido completo, con unas cuarenta referencias, está en
[estado_del_arte_simulacion.md](estado_del_arte_simulacion.md). En corto:

- **Director que motiva, no dicta**, y comprobación con tope: IBSEN (ACL 2024).
- **Role-play y después reescritura desde el log**: Yu et al. (In2Writing 2025).
- **Memoria acotada a la perspectiva**: ReverieMem (2026), TimeChara (ACL 2024).
- **Recencia, importancia y relevancia**: Generative Agents (UIST 2023), Open-Theatre (EMNLP 2025).
- **Habla, acción y pensamiento privado**: CoSER (ICML 2025).
- **Consolidar en vez de acumular**: EvoSpark (ACL 2026).
- **Conducta antes que retrato, y cuidado con el antagonista**: Jun et al. (2026).
- **Curación: la simulación sola no hace historia**: Tale-Spin (1977), Ryan (2018).
- **La focalización es del discurso, no de la historia**: Curveship (Montfort).
- **Cada componente debe ganarse su complejidad**: WSE-bench (2026).

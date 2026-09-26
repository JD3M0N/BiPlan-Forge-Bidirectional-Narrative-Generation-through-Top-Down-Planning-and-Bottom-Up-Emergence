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

### Quién lo sabe ya no es quién lo descubrirá

Las compuertas de conocimiento (`cast_bible.json`) reparten los hechos que unos personajes saben y
otros no. Cada una dice tres cosas distintas:

| Campo | Qué significa |
|---|---|
| `known_by` | Quién lo sabe **antes de la primera escena**. Se siembra en su memoria |
| `revealed_by` | Quién lo saca a la luz en escena, o vacío si lo revela el mundo o una prueba |
| `how` | `confession`, `deduction`, `discovery`, `told` u `overheard` |

El primer run real las confundió: le dio a la detective la solución del caso como algo que ya
sabía, y todas sus «deducciones» fueron recitados. Desde 7.1, `stage/casting.py` lo rechaza con
mensajes en inglés que se reinyectan en el reintento del casting:

- Quien deduce o descubre algo (`deduction`, `discovery`) **no puede** estar en `known_by`.
- Quien confiesa **tiene que** estar en `known_by`: nadie confiesa lo que no sabe.
- Si todos los presentes en el evento revelador ya lo sabían, la revelación no le cuenta nada a
  nadie, y se rechaza.
- El `initial_knowledge` de un personaje no puede repetir un hecho que ese mismo personaje va a
  deducir o descubrir (solapamiento léxico ≥ 0,4).

`gates_known_by_discoverer` lo cuenta en `simulation_metrics.json`; es 0 por construcción en
cualquier biblia que valida, y existe para que un run lo demuestre sin tener que creérselo.

Cada dossier lleva además un `public_face`: lo que cualquiera ve del personaje de un vistazo
(género y edad aparentes, oficio si es público, un rasgo visible). El actor ve a cada persona en
escena con esa línea («Mara Vela, inspectora de unos cuarenta años…»). Con solo el nombre, un
personaje del primer run llamó «muchacho» a una mujer once veces.

`public_face`, `initial_knowledge` y el `fact` de cada compuerta van en el idioma de la ficción,
porque entran literales en la memoria y en el contexto del actor. El resto del dossier va en
inglés, como el resto de las instrucciones.

### La ablación

`--actor-memory shared` reparte todo lo público a todo el reparto, dejando igual el resto del
sistema. Es el brazo de control: cualquier diferencia entre dos corpus es atribuible al modelo de
memoria y a nada más. El proxy determinista es `unknown_mentions` (un hablante nombra a alguien de
quien no tiene ningún registro); la medición seria la da la auditoría opcional con LLM.

## El bucle de una escena

```text
el director abre el beat        → elige quién empieza y da hasta 2 notas jugables
un actor mueve                  → táctica, pensamiento privado, acción visible, habla
se valida                       → se normaliza, o se repara una vez, o se salta el turno
se acepta                       → se calcula quién lo presenció y se escribe en esas memorias
cada 3 turnos, o al tope        → el director lee el beat cláusula a cláusula
todas las cláusulas, con prueba → el beat se alcanza y se abre el siguiente
la 2.ª lectura sigue corta      → el director nombra a quién tiene que cambiar, y por qué
se agota el presupuesto         → el mundo entrega la cláusula que falta, dos actores reaccionan
                                   y una última lectura decide: «con ayuda» o «forzado»
última escena de la obra        → una coda de 2 turnos, para que la historia acabe en escena
la escena acaba                 → cada actor reflexiona y su estado se consolida
```

`ASG_STAGE_TURNS_PER_BEAT` (8 por defecto) es el presupuesto por beat.

**El `achieved` se deriva, no lo declara el modelo.** El director descompone el resultado del beat
en sus cláusulas (`parts`) y dice cuáles se han visto, citando los ids de los turnos que lo
muestran. El motor da el beat por alcanzado solo si **todas** las cláusulas están vistas y cada una
cita un turno que existe, igual que el ledger de promesas deriva el `chapter_id` del evento en vez
de dejar que el modelo lo escriba. En 7.0 era un sí o no del modelo, que en una escena fue literal
y en otra laxo: un sí laxo cerró un misterio sin su motivo.

**La escalera de escalada.** Los primeros runs reales se atascaban: las notas montaban una tabla
simétrica (uno presiona, el otro resiste), nadie tenía nunca una razón para ceder, y 4 de 12 beats
se cerraron con un trueno que no resolvía nada; uno de ellos era el desenlace. Ahora cada lectura
pide un poco más:

| Lectura | Cuándo | Qué se le pide al director |
|---|---|---|
| `check` | turno 3 | Leer las cláusulas y, si falta alguna, notas de táctica |
| `turn` | turno 6 | Además, nombrar el `turning_actor_id` —quien tiene que ceder, confesar, descubrir o decidir— y darle una razón para hacerlo ahora, a su manera. El motor le da el turno siguiente si no acaba de hablar |
| `stall` | tope | Además, un `stage_event` que **entregue** la cláusula que falta (aparece la prueba, llega alguien, cede la puerta), nunca meteorología ni un recurso ya usado |
| `final` | tras 2 turnos de reacción | Solo leer. Si ahora se ve todo, el beat queda `intervened`; si no, `forced` |

Si el director no nombra a nadie cuando debe, el motor elige a quien más ha usado tácticas de
resistencia (`deny`, `deflect`, `lie`, `stall`, `withdraw`), le da una nota genérica y lo marca
como `turning_fallback` en `director.jsonl`. El contexto del director lleva dos señales
deterministas: las últimas 3 tácticas de cada actor, para que la tabla se vea («Mara: confront,
confront, confront»), y los eventos del mundo ya usados en la obra, para que no repita el trueno.

El actor tiene el contrapeso en su instrucción: la obstrucción se juega a fondo **hasta que la
escena le dé una razón que ese personaje aceptaría**; cuando una nota dice que el suelo se ha
movido, se deja mover. «Un personaje que nunca se mueve no es fuerte, está atascado.»

Un evento del mundo entra en el log como un turno más, marcado `kind: world`, y lo presencian
todos. Así el log sigue siendo la única fuente de la historia, y una intervención se representó en
vez de afirmarse. No cuenta como turno de nadie: ni para el orden de palabra ni para las métricas
de actor.

**La coda.** Cuando se cierra el último beat de la última escena, los dos personajes más
implicados tienen un turno más cada uno para jugar lo que el desenlace les cuesta. Es la respuesta
de la función a la ficha «El desenlace sigue resumiendo» del `TODO.md`: la historia acaba en una
escena, no en mitad de un análisis.

**Las tácticas son un vocabulario cerrado**: `confront`, `accuse`, `demand`, `deflect`, `deny`,
`lie`, `stall`, `plead`, `charm`, `comfort`, `threaten`, `mock`, `command`, `test`,
`investigate`, `reveal`, `confess`, `concede`, `yield` y `withdraw`. Gemini lo impone por esquema.
En 7.0 eran texto libre y salieron en español pese al contrato, así que no se podían contar.

### Qué se normaliza y qué se rechaza

Como en `script.py`: se normaliza lo que tiene una sola lectura posible y se rechaza lo que
corrompería el log. Los mensajes van en **inglés ASCII** porque se reinyectan literales.

- **Se normaliza**: comillas y rayas envolventes (en bucle, porque el modelo suele poner las dos),
  paréntesis en acción y pensamiento, el nombre propio del actor al principio de su acción,
  destinatarios que no están en escena, un susurro sin destinatario (pasa a público) y un
  **pensamiento que solo repite el habla** (similitud ≥ 0,5), que se vacía: tiene una sola
  corrección posible, no hay nada que registrar.
- **Se rechaza**, con su código en `rejected.jsonl`:

| Código | Cuándo |
|---|---|
| `EMPTY_TURN` | Ni habla ni acción |
| `INTERNAL_IDENTIFIERS` | Un id del plan o un encabezado Markdown |
| `LONG_SPEECH` | Más de 45 palabras de habla: es un discurso, no un turno |
| `FIRST_PERSON_ACTION` | Una acotación en primera persona |
| `REPEATED_LINE` | Solapamiento ≥ 0,75 con una de las 3 últimas réplicas propias |
| `REPEATED_ACTION` | La acción **contiene** ≥ 80 % de una de las 3 últimas acciones propias |

El umbral de repetición del habla es deliberadamente más estricto que el 0,4 que IBSEN usó y aun
así encontró insuficiente. La repetición de acciones se mide por **contención** y no por
solapamiento, porque los tics reales repetían el gesto entero y le añadían una cláusula («consulta
el reloj y ajusta los puños… antes de desplegar un gráfico»).

El detector de primera persona es **conservador a propósito**: rechaza la acción que empieza por
«me» o «yo» o que contiene «mi», «mis» o «conmigo». Caza «Me arrodillo junto al hogar» y «…contra
la palma de mi mano», y deja pasar «Saco una astilla»: adivinar la conjugación de un verbo suelto
rechazaría acotaciones honestas en tercera persona. Ese punto ciego lo cubre el contrato del campo
(«tercera persona, sin tu nombre: “cruza los brazos”, nunca “cruzo los brazos”»), y la métrica
`first_person_actions` usa el mismo detector y hereda el mismo punto ciego. El tope de 45 palabras
vive en el validador y nunca viaja al prompt, como el resto de cifras.

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

El primer run real **expandió** el log en vez de curarlo (1,09 palabras de historia por palabra de
log) y le pegó un pensamiento a 25 de 38 acotaciones. Desde 7.1 el narrador recibe un criterio:

- Los turnos que el director citó como prueba de que un beat ocurrió llegan marcados `[clave]`, y
  esos van en escena. El resto —una tabla en la que los dos repiten su posición, un gesto que
  vuelve— se comprime a una frase o se corta.
- Un pensamiento solo se narra donde cambia lo que el lector entiende, nunca pegado a cada réplica.
- Lo que hace el mundo se cuenta en el tiempo verbal de la narración (en 7.0 se coló un «se apaga
  de golpe» en presente dentro de una prosa en pasado).

Los títulos de capítulo pierden el rótulo de acto («Acto I:»): es del guion, y la historia es prosa.

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
| `stage/<escena>/director.jsonl` | Cada llamada al director: modo, borrador completo, cláusulas, `achieved` derivado, `turning_actor_id`, evento y tras qué turno |
| `stage/<escena>/transcript.md` | La escena legible, con acciones y pensamientos |
| `memory/<id>/records.json` | El flujo de memoria completo de un personaje |
| `memory/<id>/retrievals.json` | Cada recuperación con el desglose de su puntuación |
| `performance.json` | La función entera más los ajustes con los que corrió |
| `performance.md` | El transcript legible de toda la función |
| `narration/chapter-NNN.md` (+intentos) | La prosa por capítulo |
| `narration.json` | La voz, el narrador y cuántos turnos vio cada capítulo |
| `simulation_metrics.json` | Todas las cifras observadas |
| `story.md`, `story_metrics.json` | La historia final, medible contra cualquier run narrativo |

`performance.json` guarda `settings` con los pesos, el k, el decaimiento, el umbral, los turnos de
reacción y los de coda que se usaron, para que un lector pueda repetir o comparar sin leer el
código. Su `contract_version` es `"2"` desde 7.1 (el `achieved` derivado, las compuertas con `how`
y `director.jsonl`); un run 7.0 se sigue leyendo como contrato `"1"`.

## Qué se mide

Ninguna de estas cifras viaja a un prompt; hay un test que lo comprueba.

- **Cobertura**: `beats_achieved` frente a `beats_forced`, `beats_intervened` (alcanzados solo
  tras el evento del mundo; cuentan también dentro de `beats_achieved`), `beat_completion_ratio`,
  `turns_per_beat`, `director_checks`, `stage_events`, `reaction_turns` y `coda_turns`.
- **Actuación**: turnos, palabras de habla, acción y pensamiento, susurros, `unprompted_turns`
  (iniciativa), `distinct_tactics`, turnos rechazados y saltados, `thought_ratio` (turnos con
  pensamiento), `long_speeches`.
- **Tablas**: `max_tactic_streak` (la racha más larga de un actor con la misma táctica dentro de
  una escena) y `yields` (turnos con `concede`, `confess`, `yield` o `reveal`). Una escena con
  racha alta y cero cesiones es una tabla que nadie cruza.
- **Repetición**: `repetition_ratio` (habla), `action_repetition_ratio` (gestos, contra **todas**
  las acciones anteriores del actor, no solo la ventana de 3 del validador), `mean_self_similarity`
  y `first_person_actions`.
- **Improvisación**: `script_echo`.
- **Frontera de conocimiento**: `unknown_mentions` y `gates_known_by_discoverer`.
- **Memoria**: `memory_records`, `retrievals`.
- **Narración**: `compression_ratio` (palabras de la historia / palabras del log), `dialogue_survival`,
  `narration_source_fallbacks`, `narrated_words`, `log_words`.

### Dos lecturas que estaban mal

Al presentar el primer run real se leyeron como buenas dos cifras que no lo eran:

- **`repetition_ratio` = 0,00 no significa «nadie se repitió».** Compara solo el **habla**, palabra a
  palabra: no ve las paráfrasis ni las acciones. En ese mismo run, 19 de 84 acciones repetían un
  gesto propio. Por eso existe `action_repetition_ratio`.
- **`dialogue_survival` = 1,00 no indica fidelidad.** Indica que el narrador **transcribió** el log
  en vez de curarlo; `compression_ratio` > 1 lo confirma. Se queda como indicador de
  transcripción, no de calidad.

`report-simulations` informa como «no medida» (celda vacía en CSV) toda cifra que un run no
registró. Leer como 0 las métricas de 7.1 en un run 7.0 haría que el corpus anterior pareciera
impecable justo en los problemas que tenía.

### La auditoría con LLM

`audit-stage-run <run>` es manual y gasta cuota real: una llamada por escena para la frontera de
conocimiento y una por capítulo para la fidelidad de la narración, puntuadas como CoSER
(100 − 5 × suma de severidades). Escribe en `<run>/audit/audit.json` y **nunca sobrescribe**: un
informe anterior se aparta como `audit-<fecha>.json`.

Su contrato 2 corrige al juez de conocimiento: en el contrato 1 archivaba como «contradicción» la
mentira deliberada de un personaje y la puntuaba como fallo, así que un mentiroso bien jugado
bajaba la nota. Una mentira es una táctica, no una fuga. Lo que el juez siga archivando con otro
tipo se guarda en `set_aside` y no puntúa.

**El juez no comprueba de verdad contra la memoria que recibe.** Al reauditar el primer run 7.0
con el contrato 2 (`gemini-3.5-flash-lite`), marcó como fuga que la detective hablara del
«pestillo retardado», y ese hecho estaba **literalmente** en su memoria inicial: lo había sembrado
la compuerta defectuosa de 7.0. Lo que el juez marca se parece más a «esto no debería saberlo» que a
«esto no está en su memoria». Es útil, porque señala justo el fallo de diseño que 7.1 corrige, pero
no es la definición de fuga del sistema. Leer `knowledge_leaks` como indicio, con n pequeño, y
nunca como medida exacta; un juez más fuerte (`--model`) es la primera prueba pendiente.

`report-simulations` las agrega por voz, memoria, perfil y versión, y escribe CSV con `--csv`.
`report-story-craft --format prose` junta las historias narrativas y las simuladas, que sí son
comparables entre sí porque las dos entregan prosa.

## Coste

Medido, no estimado: los dos primeros runs reales (prompt 03, perfil Esencial, 7.0) costaron
**100 y 119 llamadas**, **251k y 337k tokens** y **21 y 31 minutos**, frente a las ~25 llamadas de
un run narrativo. La estimación anterior (150–220 llamadas, 11–16 minutos) se hizo sin medir y
fallaba en las dos direcciones: menos llamadas, pero más lentas. Y la lentitud no era del
modelo: unos **14 y 20 minutos** se fueron esperando a llamadas de actor que agotaron el timeout de
120 s (`GEMINI_REQUEST_TIMEOUT_MS`): 5 errores 504 y 2 `ReadTimeout` en el primero, 10
`ReadTimeout` en el segundo. Sin ellos, cada run habría durado unos 7 a 10 minutos. Está en la
ficha de `failed_calls` del `TODO.md`.

La escalera de 7.1 añade como mucho una lectura del director y 2 turnos por beat que llega al
tope, y la coda 2 turnos por obra; si los beats caen antes, el coste baja. Los mandos son
`ASG_STAGE_TURNS_PER_BEAT` y el perfil narrativo.

## Degradación

| Falla | Qué pasa |
|---|---|
| El casting | Dossier derivado de `characters.json` y aviso `[CASTING_FALLBACK]` |
| La apertura de un beat | El beat se abre sin nota, `[DIRECTION_FALLBACK]` |
| La comprobación de un beat | Cuenta como «no alcanzado» hasta el tope, `[BEAT_CHECK_FALLBACK]` |
| El director no nombra a quién debe cambiar | El motor elige y lo marca `turning_fallback` |
| Ni el evento del mundo alcanza el beat | Se marca forzado, `[BEAT_FORCED]` |
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

## Lo que destapó el primer run real

Los dos primeros runs reales (7.0, prompt 03 «el misterio del faro», perfil Esencial, 2026-09-26:
`Stories/Stagecraft/20260926-023354-*` y `20260926-030440-*`) llegaron al final sin errores y
fallaban en lo esencial. 7.1.0 es la respuesta:

| Problema | Evidencia en 7.0 | Qué cambió en 7.1 |
|---|---|---|
| El clímax no se representa | 4 de 12 beats forzados; en el run 2 se forzó «el culpable es expuesto» y la historia acaba sin revelación | `achieved` derivado de cláusulas, escalera de escalada, evento que entrega la cláusula, reacciones, coda |
| El detective conoce la solución | Run 1: la compuerta con la respuesta del caso llevaba `known_by=[la detective]` | `revealed_by` + `how` y cuatro reglas de lógica en el casting |
| Los actores no saben a quién tienen delante | 11 formas masculinas dirigidas a una mujer | `public_face` en el dossier y en «CONTIGO EN ESCENA» |
| Log de baja calidad | Acciones en 1.ª persona 22/84, acciones repetidas 19/84, pensamiento en 81/84 turnos, réplicas de hasta 52 palabras, tácticas en español libre, 0 susurros | `FIRST_PERSON_ACTION`, `REPEATED_ACTION`, `LONG_SPEECH`, pensamiento-eco vaciado, tácticas cerradas |
| Una regla muerta | `MULTIPLE_BEATS` no se disparaba nunca | Retirada |
| El narrador transcribe | 1,09 palabras de historia por palabra de log en el run 1; 25 de 38 acotaciones con un pensamiento pegado | Turnos `[clave]` y criterio de curación en el prompt |
| Sin rastro del director | No había forma de saber por qué se forzó un beat | `director.jsonl` |
| Coste mal documentado | Estimado 150–220 llamadas y 11–16 min; medido 100–119 llamadas y 21–31 min | Sección «Coste» con lo medido |

La auditoría con LLM de esos dos runs (contrato 1) dio 3 fugas de conocimiento en el primero, las
tres de la detective y de severidad 4, con 86,67 de conocimiento y 100 de fidelidad; y 0 fugas en
el segundo, con 91,67 de fidelidad. El juez del contrato 1 contaba además como fallo la mentira
deliberada de un personaje, y por eso se reauditan con el contrato 2 antes de compararlos con 7.1.

### Validación de 7.1

Dos runs nuevos con el mismo prompt, perfil y modelo (`20260926-070539-*` y `20260926-072847-*`),
medidos con el mismo código que los de 7.0 (las cifras nuevas se recalcularon sobre los logs de
7.0) y auditados con el mismo juez, contrato 2. **Con n=2 por brazo son indicios, no
conclusiones.**

| Criterio | 7.0 | 7.1 | Objetivo |
|---|---|---|---|
| Beats forzados | 4/12 | **0/12** (1 alcanzado con ayuda del mundo) | ≤ 2/12 |
| Compuertas conocidas por su descubridor | la detective tenía la solución | **0** | 0 |
| Formas masculinas dirigidas a una mujer | 11 a mano (5 por expresión regular) | **0** por la misma expresión | 0 |
| Acciones en 1.ª persona | 22/84 a mano, 11/84 por el detector | **0/80** | ≤ 5 % |
| Acciones que repiten un gesto propio | 0,50 y 0,16 | **0,00 y 0,02** | ≤ 5 % |
| Réplica más larga | 52 palabras | **40** | ≤ 45 |
| `compression_ratio` | 1,09 y 0,73 | **0,70 y 0,80** | < 0,9 |
| Cesiones (`yields`) | 2 y 0 | 4 y 7 | — |
| Fugas según la auditoría | 4 y 1 | **0 y 0** | menos que 7.0 |
| `director.jsonl` | no existía | 18 y 21 líneas | una por llamada |
| Desenlace representado | 1/2 parcial | **0/2 completo** (ver abajo) | 2/2 |
| Fidelidad de la narración | 100 y 85 | **81,67 y 78,33** | — |
| Pensamiento por turno | 0,98 y 0,95 | 0,94 y 0,95 | — |
| Susurros | 0 y 0 | 0 y 0 | — |
| Llamadas / tokens / minutos | 100–119 / 251–337k / 21–31 | 98–111 / 265–289k / 17–22 | — |

Los beats **caen de verdad**: de los doce, dos en la primera lectura, siete en la de giro, dos en
la del tope sin necesitar evento y uno con evento del mundo que entregó la cláusula (un legajo que
cae al suelo). Ninguno se forzó. La frontera de conocimiento se sostiene por construcción, y el log
dejó de tener los tics de 7.0.

**Lo que no se arregló:**

- **El desenlace sigue sin representarse entero.** En los dos runs el último beat se dio por
  alcanzado sin que nadie dijera la solución del caso. En el primero, el resultado del plan era
  vago («el caso queda resuelto de forma analítica») y el director lo aceptó con la confesión del
  motivo; la compuerta que decía que la detective deduciría la huida por la ventana en ese beat
  **nunca se dijo en escena**. En el segundo, el director juzgó «se revela método, motivo y
  consecuencias» como una sola cláusula y la dio por vista con una réplica que solo probaba la
  falsificación; el narrador **inventó** la solución para tapar el hueco, y la auditoría lo
  marcó con severidad 4. La causa común: nada comprueba que una compuerta con
  `revealed_at_event_id` se revele de verdad en su beat. Ficha en el `TODO.md`.
- **La fidelidad de la narración bajó.** Una parte es el precio de curar: el juez cuenta como
  «beat eliminado» una réplica comprimida. Otra parte son falsos positivos: marca como inventada
  la tormenta de la isla, que está en la petición pero no en el log, y el juez solo ve el log.
  Y una parte es real: la solución inventada del segundo run.
- **Casi todos los turnos siguen trayendo pensamiento** (0,94–0,95) y sigue sin haber un solo
  susurro. Vaciar el pensamiento que repite el habla no basta: los que quedan repiten la
  intención («debo…»), no la réplica.
- **Los eventos del mundo siguen siendo viento.** Los tres que llegaron a ocurrir en 7.1 (dos en
  el run que cortó la cuota, uno aquí) fueron ráfagas, aunque entregaran algo. El director
  entiende «un recurso ya usado» de forma literal.
- **Los timeouts de actor siguen ahí**: 3 errores 504 en el primero, 2 `ReadTimeout` y 2 504 en el
  segundo, a unos 2 minutos cada uno.

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

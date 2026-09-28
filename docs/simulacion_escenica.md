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

Lo que el propio personaje dijo, hizo o pensó en escenas anteriores **no se recupera**
(`NOT_RECALLED`): sus reflexiones ya lo llevan en primera persona, y un actor que relee su propia
réplica literal la repite. Sigue en `memory/<id>/records.json` para la auditoría.

> **Hasta 7.1.1 el tope no se aplicaba.** `CharacterMemory.recall` devolvía toda la memoria de
> escenas anteriores: las cinco funciones 7.0 y 7.1 recibieron por turno una mediana de 18 a 29
> recuerdos, con máximos de 52 a 72, y los pesos solo ordenaban. La frontera de conocimiento no
> se vio afectada, porque lo no presenciado seguía sin estar; la selección, sí. Arreglado en
> 7.2.0 (SIM-9): no comparar esas funciones con las nuevas como si tuvieran la misma memoria.

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

**Una nota se entrega una vez.** Llega al actor al que va en su siguiente turno y caduca
(`engine._consume`). Hasta 7.1.1 seguía viva hasta la siguiente lectura del director, se le
repetía al mismo actor y producía confesiones dobles.

**Hablarle a alguien.** El actor nombra a quien se dirige como lo ve en «CONTIGO EN ESCENA», y
`normalize_turn` lo traduce a su id. Con ese dato la política de turnos le da la palabra al
interpelado, y su contexto marca la réplica que aún no ha contestado («TE ACABAN DE DECIR»); su
instrucción le pide responderla antes de seguir con lo suyo, lo que no es ceder. Hasta 7.1.1 el
esquema pedía ids que el actor nunca veía: 79 de 80 turnos 7.1 no llevaban destinatario, la escena
se volvía una ronda de monólogos y ningún susurro podía existir.

Un evento del mundo entra en el log como un turno más, marcado `kind: world`, y lo presencian
todos. Así el log sigue siendo la única fuente de la historia, y una intervención se representó en
vez de afirmarse. No cuenta como turno de nadie: ni para el orden de palabra ni para las métricas
de actor.

**La coda.** Cuando se cierra el último beat de la última escena, los dos personajes más
implicados tienen un turno más cada uno para jugar lo que el desenlace les cuesta. Es la respuesta
de la función al desenlace que resumía en vez de dramatizar (se sigue vigilando en la ficha EXP-1
del `TODO.md`): la historia acaba en una escena, no en mitad de un análisis.

**Las tácticas son un vocabulario cerrado**: `confront`, `accuse`, `demand`, `deflect`, `deny`,
`lie`, `stall`, `plead`, `charm`, `comfort`, `threaten`, `mock`, `command`, `test`,
`investigate`, `reveal`, `confess`, `concede`, `yield` y `withdraw`. Gemini lo impone por esquema.
En 7.0 eran texto libre y salieron en español pese al contrato, así que no se podían contar.

### Qué se normaliza y qué se rechaza

Como en `script/validation.py`: se normaliza lo que tiene una sola lectura posible y se rechaza lo que
corrompería el log. Los mensajes van en **inglés ASCII** porque se reinyectan literales.

- **Se normaliza**: comillas y rayas envolventes (en bucle, porque el modelo suele poner las dos),
  paréntesis en acción y pensamiento, el nombre propio del actor al principio de su acción, los
  destinatarios escritos por nombre (nombre completo, de pila o cualquier palabra que identifique
  a un solo personaje presente, que pasan a su id), los que no están en escena o son ambiguos (se
  quitan), un susurro sin destinatario (pasa a público) y un **pensamiento que solo repite el
  habla** (similitud ≥ 0,5), que se vacía: tiene una sola corrección posible, no hay nada que
  registrar.
- **Se rechaza**, con su código en `rejected.jsonl`:

| Código | Cuándo |
|---|---|
| `EMPTY_TURN` | Ni habla ni acción |
| `INTERNAL_IDENTIFIERS` | Un id del plan o un encabezado Markdown |
| `LONG_SPEECH` | Más de 45 palabras de habla: es un discurso, no un turno |
| `FIRST_PERSON_ACTION` | Una acotación en primera persona |
| `REPEATED_LINE` | Solapamiento ≥ 0,75 con cualquier réplica propia anterior de la obra |
| `REPEATED_ACTION` | La acción **contiene** ≥ 80 % de una de las 3 últimas acciones propias, también de escenas anteriores |

Hasta 7.1.1 las dos reglas miraban solo la escena en curso, y un actor repitió palabra por palabra
en `072847` un turno entero de la escena anterior.

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
| `limited` (7.3) | Lo mismo que `first_person`, contado en tercera persona |

`--voice` o `ASG_NARRATIVE_VOICE` lo eligen. La voz **solo** cambia la narración: el plan, el guion
y la función son idénticos byte a byte entre dos runs que solo difieren en ella. Desde 7.3 un test
lo comprueba también sobre el casting, la función y todos los prompts anteriores al narrador.

En primera persona la memoria propia paga dos veces: un capítulo solo puede escribirse con los
turnos que su narrador percibió, que son exactamente los que ya están en su flujo.

**Quién narra (7.3).** `first_person` y `limited` se cuentan desde un personaje:

- `--narrator` (o el personaje de la visión en StageCraft) lo nombra como lo escribió la persona, y
  `stage/names.py` lo resuelve contra el reparto: nombre completo, de pila o una palabra que
  identifique a uno solo. Sin nombre, narra el protagonista; si el nombre no existe o ese
  personaje no presenció nada, también, y el run lo avisa con `[NARRATOR_FALLBACK]`.
- Solo ven turnos de escenas en las que el personaje **estaba**, no solo de las que figura como
  testigo. Con memoria compartida los testigos de un turno público son todo el reparto; sin esta
  regla, el narrador contaría escenas en las que nunca estuvo y la ablación de memoria se
  mezclaría con la narración.
- **Un capítulo sin turnos visibles no se narra**, con ninguna voz: el narrador tendría que
  inventarlo. Queda en `narration.json` como `source: "absent"`, con `[NARRATOR_ABSENT]`, y fuera
  de `story.md`.
- `narration.json` pasa al contrato 2: guarda el nombre pedido (`requested_narrator`), cómo se
  eligió al narrador (`narrator_source`) y el tono.

**El tono del narrador (7.3).** `--tone` es un registro en texto libre («como un guerrero samurái,
con tono medieval»). Solo lo lee el narrador, en una cláusula que se añade únicamente cuando hay
tono: colorea la voz y nunca añade sucesos.

### El respaldo determinista

Si el narrador no puede correr, `stage/fallback.py` convierte el log en prosa sin interpretarlo:
habla a diálogo con raya, acciones a frases, pensamientos a interioridad referida. Es parte del
contrato, no un apaño: una función representada no se pierde porque falle la narración. Y además
sirve de suelo de comparación: el mismo log, sin ninguna interpretación.

## Artefactos de un run simulado

Además de todo lo Top-Down (plan, promesas, etapas del guion):

| Artefacto | Contenido |
|---|---|
| `script.json`, `script_metrics.json`, `script.md` | El guion que sirvió de libro del director |
| `cast_bible.json` | Dossiers y compuertas de conocimiento, con `fallback: true` si se derivó |
| `stage/actors/<id>.json` | La instrucción de sistema exacta y el dossier que recibió cada actor |
| `stage/<escena>/brief.json` | Beats, reparto, lugar, compuertas y réplicas de referencia |
| `stage/<escena>/turns.jsonl` | Cada turno aceptado, también los del mundo desde 7.2, con testigos, nota y memorias recuperadas |
| `stage/<escena>/contexts.jsonl` | El bloque de prompt variable exacto de cada turno de actor |
| `stage/<escena>/rejected.jsonl` | Cada intento rechazado, con su código y su motivo |
| `stage/<escena>/director.jsonl` | Cada llamada al director: modo, borrador completo, cláusulas, `achieved` derivado, `turning_actor_id`, evento y tras qué turno |
| `stage/<escena>/transcript.md` | La escena legible, con acciones y pensamientos |
| `memory/<id>/records.json` | El flujo de memoria completo de un personaje |
| `memory/<id>/retrievals.json` | Cada recuperación con el desglose de su puntuación |
| `performance.json` | La función entera más los ajustes con los que corrió |
| `performance.md` | El transcript legible de toda la función |
| `narration/chapter-NNN.md` (+intentos) | La prosa por capítulo |
| `narration/chapter-NNN-attempt-NNN-error.json` | La excepción de un intento de narración que falló (desde 7.2) |
| `narration.json` | La voz, el narrador y cuántos turnos vio cada capítulo |
| `simulation_metrics.json` | Todas las cifras observadas |
| `simulation_metrics.recomputed.json` | Las mismas cifras medidas de nuevo con el código actual, si se lanzó `recompute-simulation-metrics` |
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
- **Memoria**: `memory_records`, `retrievals` (antes de 7.2 contaba toda la memoria en cada turno,
  porque el tope no se aplicaba), y `emotions`, la emoción con la que cada actor salió de cada
  escena según su reflexión.
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
impecable justo en los problemas que tenía. Para medir un run antiguo con el código actual está
`recompute-simulation-metrics <run>`, que escribe `simulation_metrics.recomputed.json` sin tocar
el original; las cuatro funciones completas 7.0 y 7.1 ya lo tienen.

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
`ReadTimeout` en el segundo. Sin ellos, cada run habría durado unos 7 a 10 minutos. Están en las
fichas MED-2 (qué miden esas cifras) y SIM-4 (el timeout del actor) del `TODO.md`.

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

Como con cualquier medición de este repositorio, un n pequeño no basta: la réplica de doce
historias de 6.6.0 medida con `report-story-craft` dio hasta 16 puntos de diferencia entre dos
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
  `revealed_at_event_id` se revele de verdad en su beat. Un análisis posterior encontró dos
  causas más: la solución estaba literal en las `scripted_lines` del clímax, que solo alimentan
  `script_echo` y nunca llegan al director, y el narrador recibe las obligaciones de promesa,
  que es de donde sacó la solución que inventó. Ficha SIM-1 del `TODO.md`.
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
- **Nadie se dirige a nadie, y las notas se repiten.** Una relectura posterior de los logs encontró
  dos causas más:
  - `addressed_to` va vacío en 79 de 80 turnos, porque el esquema pide ids de personaje que el actor
    nunca ve. Por eso no hay susurros.
  - La nota del director se re-entrega al mismo actor hasta la siguiente lectura (5 de 54 turnos con
    nota), y de ahí salen confesiones dobles.

  Las dos causas, y la memoria sin tope (SIM-9), que era la otra fuente de repetición, están
  arregladas en 7.2.0, y el par de 7.2 lo confirma en real.

## Validación de 7.2

Dos runs nuevos, los dos con perfil Esencial, `gemini-3.5-flash-lite`, voz `omniscient` y memoria
`own`, auditados con el mismo juez y contrato 2:

- `20260927-163733-la-habitacion-del-faro-cerrada-por-dentro`, prompt 03, el mismo misterio del
  faro que los cuatro runs anteriores;
- `20260927-213245-la-falsificacion-de-la-aurora`, prompt 07, la primera función fuera del
  prompt 03.

```powershell
generate-story <prompt 03 Esencial> --format simulated --profile essential --no-audio
generate-story <prompt 07 Esencial> --format simulated --profile essential --no-audio
audit-stage-run Stories/Stagecraft/20260927-163733-la-habitacion-del-faro-cerrada-por-dentro
audit-stage-run Stories/Stagecraft/20260927-213245-la-falsificacion-de-la-aurora
report-simulations --group version
```

**Con n=2 por brazo son indicios, no conclusiones**, y el segundo run cambia de prompt, así que
sus cifras no se restan de las del primero.

| Criterio | 7.0 | 7.1 | 7.2 | Objetivo |
|---|---|---|---|---|
| Recuerdos por turno, mediana | 18–29 | 20,5 y 29 | **8 y 8** | ≤ 8 |
| Recuerdos por turno, máximo | 52–72 | 57 y 70 | **8 y 8** | ≤ 8 |
| Material propio recuperado | todo | 236 y 367 registros | **0 y 0** | 0 |
| Turnos con destinatario | 0 | 0/36 y 1/44 | **38/43 y 47/51** | ≥ la mitad |
| Turnos respondidos | 0 | 0 y 1 | **32 y 41** | sube |
| Notas repetidas al mismo actor | — | 1 y 4 | **0 y 0** | 0 |
| Susurros | 0 y 0 | 0 y 0 | **1 y 0** | ≥ 1 |
| Réplicas copiadas entre escenas | — | 0 y 1 | **0 y 0** | 0 |
| Fugas según la auditoría | 4 y 1 | 0 y 0 | 1 y 0 | menos que 7.0 |
| Puntuación de conocimiento | 86,67 y — | — | **95,83 y 100** | — |
| Fidelidad de la narración | 100 y 85 | 81,67 y 78,33 | **93,33 y 95,0** | — |
| Beats forzados | 4/12 | 0/12 | 1/6 y 1/6 | ≤ 2/12 |
| `compression_ratio` | 1,09 y 0,73 | 0,70 y 0,80 | 0,74 y 0,71 | < 0,9 |
| `script_echo` | — | 0,026 y 0,036 | 0,052 y 0,056 | bajo |
| Notas del director en inglés | — | 10/31 y 22/40 | 14/33 y 14/39 | 0 |
| `thought_ratio` | 0,98 y 0,95 | 0,94 y 0,95 | 0,91 y 0,92 | baja de 0,9 |
| Llamadas / tokens / minutos | 100–119 / 251–337k / 21–31 | 98–111 / 265–289k / 17–22 | 110–126 / 260–321k / **14–16** | — |

La **frontera de conocimiento se sostiene en el dato, no solo por construcción**. Una auditoría
determinista de los dos runs, sobre `contexts.jsonl`, `turns.jsonl` y `memory/*/records.json`, no
encontró:

- ni un id, título de evento, capítulo, escena futura o réplica del guion en un contexto de actor;
- ni un registro de memoria de un turno que su personaje no presenciara;
- ni un pensamiento o susurro ajeno en el contexto de nadie;
- ni una compuerta filtrada por el dossier, el objetivo de escena, el escenario, la `public_face`
  o la nota del director, medida contra el mismo umbral que usa `stage/casting.py`.

La **telemetría de MED-2 mide lo que dice**: la suma de latencias (726 y 572 s) cabe en el reloj
(951 y 825 s), `failed_calls` es 0 con 2 intentos 504 cada uno, y el reparto por agente sale del
propio `llm_calls.jsonl`: el actor se lleva 71 de 110 llamadas y 123k de 260k tokens en el
primero.

**Lo que 7.2 no arregló, y un fallo nuevo:**

- **Un actor puede salirse de la ficción y el log lo acepta.** En `chap_2-scene-1-t005`, Mara dijo
  «I am checking the import paths for `Model` in the Superset models structure», con una acción
  sobre `superset/models/core.py`. El turno pasó los seis rechazos de `stage/validation.py`, entró
  en el log, en el transcript y en la memoria de tres personajes. El juez lo marcó con severidad 5
  y es la única fuga de los dos runs. El narrador lo omitió, así que no llegó a `story.md`.
- **El director sigue escribiendo en inglés** 14 de 33 y 14 de 39 notas, y 5 estados de actor del
  segundo run mezclan idiomas (SIM-2).
- **Las cláusulas se siguen rehaciendo** en 2 y 4 beats (SIM-2).
- **Un evento del mundo revela una compuerta antes de su evento.** En el primer run, el del
  capítulo 1 hizo saltar el pestillo de la puerta interior, que es la compuerta anclada en
  `event_5`, y de paso destruyó la prueba del cuarto cerrado: Mara dedujo después que «la ráfaga
  lo forzó desde fuera» y exculpó al contrabandista. Es el rechazo que SIM-2 pide y que no existe.
- **El mundo entrega la trama.** En el segundo run, un evento hizo que un repartidor trajera un
  sobre «que detalla la quiebra simulada por Víctor Cárdenas para vengarse de la casa de
  subastas»: el motivo del caso, por correo. El juez lo archivó como `invented_event` de
  severidad 4.
- **Los recursos del mundo se repiten en el misterio del faro**: los dos eventos fueron ráfagas de
  viento (SIM-6). En el prompt 07 fueron tres recursos distintos.
- **La resolución sigue llegando por confesión**, que el prompt 03 prohíbe: la hija confesó haber
  acuñado el pasador, y el contrabandista jugó una sola táctica en toda la obra (SIM-11).
- **`REPEATED_ACTION` es ahora el único motivo de rechazo**: 7 y 10 turnos, y 2 saltados. Con la
  memoria acotada de 7.2 y la comparación contra todas las acciones anteriores del actor, la regla
  puede haberse vuelto la más caliente del validador.

## De dónde sale cada decisión

El recorrido completo, con unas cuarenta referencias, está en
[estado_del_arte_simulacion.md](estado_del_arte_simulacion.md). En corto:

- **Director que motiva, no dicta**, y comprobación con tope: IBSEN (ACL 2024).
- **Role-play y después reescritura desde el log**: Yu et al. (In2Writing 2025).
- **Memoria acotada a la perspectiva**: ReverieMem (2026), TimeChara (Findings ACL 2024).
- **Recencia, importancia y relevancia**: Generative Agents (UIST 2023), Open-Theatre (EMNLP 2025).
- **Habla, acción y pensamiento privado**: CoSER (ICML 2025).
- **Consolidar en vez de acumular**: EvoSpark (ACL 2026).
- **Conducta antes que retrato, y cuidado con el antagonista**: Jun et al. (2026).
- **Curación: la simulación sola no hace historia**: Tale-Spin (1977), Ryan (2018).
- **La focalización es del discurso, no de la historia**: Curveship (Montfort).
- **Cada componente debe ganarse su complejidad**: WSE-bench (2026).

El argumento general de la tesis, por qué mezclar Top-Down y Bottom-Up, está en
[marco_hibrido.md](marco_hibrido.md). El diagnóstico de la actuación y las mejoras propuestas, cada
una con su respaldo y su ficha, están en [mejoras_simulacion.md](mejoras_simulacion.md).

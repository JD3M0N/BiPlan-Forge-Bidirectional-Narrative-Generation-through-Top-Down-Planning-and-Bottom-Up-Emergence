# Historial de cambios

## 7.6.0

La función simulada puede dar objetos a los personajes. `--inventory` (o `ASG_INVENTORY=true`)
añade la etapa `props` entre casting y performance: el utilero reparte los `StoryObject` del
mundo, que la función ignoraba, y los personales que definan a alguien. Apagado —el defecto— no
cambia ningún prompt, esquema ni artefacto, y eso es lo que lo hace medible.

- **El modelo propone y el código decide.** Un turno puede traer un `item_action` con un verbo y
  el nombre del objeto; `stage/inventory.py` comprueba si lo lleva o lo tiene al alcance, y
  rechaza en inglés ASCII con su código, que se reinyecta como el de cualquier otro turno.
- **Un objeto solo lo percibe quien lo ve.** Un traspaso en susurro queda entre esas dos manos y
  lo que alguien esconde no lo sabe nadie más, así que las visiones limitada y en primera persona
  solo narran los objetos que su personaje presenció.
- **`props.json`, `stage/inventory.jsonl` y `performance.json` en contrato 4**, con la utilería
  inicial y final. `PIPELINE_VERSION` pasa a 7.6; las versiones 5.0 a 7.5 se siguen abriendo y se
  emparejan como «sin inventario».
- Nuevas métricas de utilería en `simulation_metrics.json` y `report-simulations`, **no medidas**
  en un run sin inventario. Diseño y medición en [resumen.md](../../docs/resumen.md).

## 7.5.1

Tras dos funciones Gemini emparejadas se conservan las cláusulas que faltan
en beats no logrados, las propuestas originales de revisión y el juicio
original del auditor de promesas. Una revisión puede cambiar objetivos de
solo algunos actores; los demás retienen los suyos. Los estados emocionales
iniciales y finales se piden en el idioma de la ficción. La validación
real y sus límites están en
[resumen.md](../../docs/resumen.md).

## 7.5.0

La función puede conservar los hitos (`fixed`) o revisar escenas pendientes (`adaptive`) cuando
los actores frustran uno. La revisión solo cambia escenas futuras, con reparto, eventos y orden
validados; si falla, el desenlace queda abierto. `generation_options.json` guarda el modo.

- `performance.json` sube al contrato 3: registra modo, cláusulas pendientes y pruebas con
  fragmento y procedencia. `director.jsonl` conserva la decisión y sus citas.
- La función guarda intentos, contextos del director, reflexiones, memoria incremental y un
  checkpoint por escena. `llm_calls.jsonl` vincula cada llamada con `decision_id`.
- `report-simulations --all-status` incluye funciones interrumpidas que dejaron turnos;
  `--cost-csv` exporta coste por agente y modelo.
- El narrador solo recibe la actuación y la premisa estable. Los susurros sin destinatario se
  reparan antes de incorporarse al log.
- `--plan-from <run>` vuelve a representar un plan, guion y reparto congelados; `source_run.json` registra sus hashes.
- `PIPELINE_VERSION` pasa a 7.5; las versiones anteriores siguen siendo legibles.

## 7.4.0

La función simulada puede ir con un modelo propio. Gemini cuenta la cuota gratuita diaria por
proyecto y por modelo, y los actores gastan casi todas las llamadas de un run simulado: con un
segundo modelo, la función tiene su propio cupo y deja el del pipeline intacto. `metadata.json`
gana `stage_model`, así que `PIPELINE_VERSION` pasa a 7.4; los runs 5.0 a 7.3 se siguen abriendo.

- **`GEMINI_STAGE_MODEL`, `GEMINI_STAGE_API_KEY` y `GEMINI_STAGE_RPM_LIMIT`.** Vacíos heredan
  `GEMINI_MODEL`, `GEMINI_API_KEY` y `GEMINI_RPM_LIMIT`, así que sin configurarlos nada cambia.
  El modelo recomendado es `gemini-3.1-flash-lite`. La clave aparte es para un proyecto con su
  propia cuota (por ejemplo, de pago), no para multiplicar la gratuita.
- **`RoutedProvider`.** `provider_from_settings` devuelve un par enrutado cuando la función
  difiere del modelo principal. Enruta por la etapa que el pipeline ya declara en cada llamada
  (`call_context`): solo `performance` (turnos, reflexiones y director de escena) va al modelo
  de la función (`STAGE_MODEL_STAGES`). El casting y la narración siguen en el principal. Los
  dos proveedores comparten la lista de uso y los callbacks del run.
- **Un limitador de RPM por modelo y clave.** `_LIMITERS` iba solo por capacidad, y dos modelos
  con el mismo RPM habrían compartido la misma ventana aunque Google los cuente aparte.
- **Registro.** `metadata.json` guarda `stage_model` en un run simulado con modelo propio, y
  `None` en el resto, que significa «el mismo que `model`». Cada línea de `llm_calls.jsonl` ya
  nombraba su modelo.
- `generate-story` gana `--stage-model`.
- Una variable numérica vacía (`GEMINI_STAGE_RPM_LIMIT=`, como la deja `.env.example`) vale su
  defecto, igual que las booleanas y las de opción. Antes abortaba con «debe ser un número entero».

## 7.3.1

No cambia ningún artefacto ni `PIPELINE_VERSION`. Sube las etiquetas y descripciones en español de
`GenerationOptions`, `OutputChoice`, los perfiles y el reparto (`options.py`, `formats.py`,
`planning/profiles.py`, `brief.py`) para que StageCraft y el bot de Telegram las lean del mismo
sitio en vez de duplicarlas.

## 7.3.0

Hace modulares las opciones de un run y añade lo que necesita StageCraft, la interfaz gráfica.
Cambia el conjunto de artefactos (`generation_options.json`, `brief.json`, `narration.json`
contrato 2), así que `PIPELINE_VERSION` pasa a 7.3; los runs 5.0 a 7.2 se siguen abriendo.

- **Un solo objeto de opciones.** `GenerationOptions` (`options.py`) reúne cada elección por run y
  se valida una vez. La fachada conserva sus kwargs explícitos (un test los obliga a coincidir
  con los campos) y gana `StoryGenerator.from_options`; `StoryPipeline` recibe solo `options=`.
  La CLI, la consola y Telegram construyen las opciones con `GenerationOptions.from_settings`.
  `load_settings(require_api_key=False)` lee la configuración sin exigir la clave.
- **Cada run registra sus opciones** en `generation_options.json`, también el ledger, la guía y
  el audio, que antes no quedaban en ningún artefacto.
- **Cancelar un run.** `generate(..., should_cancel=...)`: el pipeline lo consulta antes de cada
  llamada a un agente y lanza `RunCancelledError` (`RUN_CANCELLED`), que ninguna etapa degradable
  traga. Nunca se cancela lanzando desde un callback: el de progreso corre dentro del bucle de
  reintentos del proveedor.
- **Elegir desde quién se narra.** Nueva visión `limited` (tercera persona limitada a un
  personaje) y opción `narrator`: el personaje por su nombre, resuelto contra el reparto
  (`stage/names.py`). Si no existe o no presenció nada, narra el de siempre y el run lo avisa
  (`[NARRATOR_FALLBACK]`). En `limited` y `first_person` solo se ve lo que ocurrió en escenas
  donde el personaje estaba, también con memoria compartida.
- **Nunca se narra desde un log vacío.** Un capítulo sin turnos visibles no se manda al modelo:
  queda en `narration.json` como `absent`, con `[NARRATOR_ABSENT]`, y se omite de `story.md`;
  `story_metrics` recibe el plan recortado (`writing/assembly.narrated_plan`).
- **Tono del narrador.** `narration_tone`, texto libre que solo lee la narración simulada.
- **Obra estructurada.** `StoryBrief` y `CastMember` (`brief.py`): la trama y el reparto se
  componen en un prompt determinista que el analista lee como cualquier otro; el run guarda
  `brief.json`. Si falta un personaje declarado, el diseñador de personajes tiene un reintento
  y después avisa (`[BRIEF_CAST_MISSING]`).
- **Voz del audio.** `audio_voice`, una de las voces de `asg_core.NARRATION_VOICES`.
- **Etiquetas compartidas.** `formats.VOICE_CHOICES` y `MEMORY_CHOICES`; la consola ya no tiene
  las suyas cableadas (primera mitad de OPS-2).
- `generate-story` gana `--brief`, `--options` (el `generation_options.json` de otro run),
  `--narrator`, `--tone`, `--turns-per-beat`, `--audio-voice` y `--voice limited`.

## 7.2.0

Arregla los bugs que destapó la lectura de los logs 7.1 y los de los instrumentos. Cambia lo que
registran `turns.jsonl`, `llm_calls.jsonl`, `llm_usage.json`, `metadata.json` y
`error_report.json`, así que `PIPELINE_VERSION` pasa a 7.2; los runs 5.0 a 7.1 se siguen abriendo.

- **La memoria del actor tiene tope (SIM-9).** `CharacterMemory.recall` devolvía toda la memoria
  de escenas anteriores (medianas de 18 a 29 recuerdos por turno, máximos de 52 a 72) porque su
  condición de corte no podía cumplirse. Ahora son los 6 mejores más las 2 últimas reflexiones, y
  las réplicas y pensamientos propios no se recuperan (`NOT_RECALLED`): releerlos literales
  llevaba a repetirlos.
- **Los personajes se dirigen unos a otros (SIM-10).** `addressed_to` se escribe con los nombres
  de «CONTIGO EN ESCENA», y `normalize_turn` los resuelve a ids: nombre completo, nombre de pila o
  cualquier palabra del nombre que identifique a un solo personaje presente. El esquema pedía ids
  que el actor nunca veía, y el resto se descartaba en silencio. La nota del director se entrega
  una vez y caduca (`engine._consume`); el contexto del actor marca la última réplica que se le
  dirigió («TE ACABAN DE DECIR»), y su instrucción pide responderla antes de seguir con lo suyo.
- **El log es completo (SIM-3).** Los turnos del mundo entran en `turns.jsonl`, y
  `contexts.jsonl` solo registra turnos con prompt. El habla se compara con todo lo que el actor
  dijo en la obra, no solo en la escena, y los gestos con sus tres últimos de toda la obra. La
  acción no arrastra la mayúscula tras el nombre (`perception.stage_direction`). `emotions` se
  rellena con la emoción de cada reflexión. Un fallo del narrador deja
  `narration/chapter-NNN-attempt-NNN-error.json` con su excepción.
- **Nuevo comando `recompute-simulation-metrics <run>`.** Recalcula las métricas de una función
  desde sus logs en `simulation_metrics.recomputed.json`, sin tocar el original.
- **La cuota diaria ya no es «facturación» (MED-1).** Una cuota agotada se clasifica por
  `quota_id` y `metric`; el texto solo cuenta si no dicen nada.
- **Telemetría honesta (MED-2).** En `llm_calls.jsonl` los intentos de una llamada comparten
  `call_id`, cada uno lleva su propia latencia y la espera que lo precedió, `stage` es la etapa
  del pipeline y el campo nuevo `agent` el agente (`call_context`, que fija `_call_agent`). En
  `llm_usage.json`, `calls` y `failed_calls` cuentan llamadas lógicas, con `attempts`,
  `failed_attempts` y `auxiliary_calls` aparte.
- **Un run fallido dice dónde murió (MED-4).** `error_stage` es la etapa del pipeline; el
  componente que falló va a `details.component`, y un fallo en la función añade
  `details.scene_id`. Si falla el análisis, la carpeta se llama `peticion-sin-analizar` y el
  prompt queda en `submitted_request.json`. `metadata.json` guarda el perfil narrativo.
- **Guion (TD-6, TD-2).** El reparto no duplica el punto final, un guion en español siempre
  titula «Personajes» y cada acto toma el título localizado de la presentación.
- **Escritura incremental (ING-4).** `append_jsonl` anexa de verdad y mantiene un hash
  incremental para el manifiesto: escribir un turno ya no relee ni reescribe el archivo.
- Exige `asg-core` 0.5.1 y `asg-evaluation` 0.6.0.

## 7.1.1

Limpieza sin cambio de contrato: `PIPELINE_VERSION` sigue en 7.1 y los artefactos son los mismos.

- Retirado el código que nadie llamaba: `PerformanceEngine.full_transcript`,
  `CharacterMemory.working_memory`, `intensity_word` (con su tabla `_INTENSITY`) y
  `skeletons_for_layer`, que solo usaba un test.
- `ArtifactRepository` y `recover-story-runs` serializan con `asg_core.artifact_json`, el mismo
  formato que antes en un solo sitio; `audit-stage-run` escribe `audit.json` de forma atómica.
- Todos los comandos configuran la salida con `asg_core.use_utf8_output`; `compare-story-runs`,
  que no lo hacía, deja de imprimir mojibake en una consola de Windows. Exige `asg-core` 0.5.0.
- Los docstrings de `stage/` dejan de citar el escape room, retirado del monorepo.

## 7.1.0

Arregla lo que destapó el primer run real del formato simulado (dos historias del prompt 03,
perfil Esencial). Los formatos narrativo y guion no cambian: sus 77 artefactos de prueba siguen
idénticos byte a byte.

- **La frontera de conocimiento.** `KnowledgeGate` gana `revealed_by` y `how` (`confession`,
  `deduction`, `discovery`, `told`, `overheard`), y `stage/casting.py` rechaza que quien deduce o
  descubre un hecho lo sepa ya, que alguien confiese lo que no sabe, una revelación que no le cuenta
  nada a nadie y un `initial_knowledge` que regala una deducción. En 7.0 la detective conocía la
  solución antes de empezar. Nueva métrica `gates_known_by_discoverer`, 0 por construcción.
- **`public_face`** en cada dossier: lo que cualquiera ve de un personaje. El actor ve a cada
  persona en escena con esa línea; con solo el nombre, en 7.0 una mujer fue «muchacho» once veces.
- **`achieved` se deriva.** `BeatCheckDraft` pierde `achieved` y gana `parts`: el director juzga
  cada cláusula del resultado con los turnos que la prueban, y el motor da el beat por alcanzado
  solo si todas están vistas con un turno que existe.
- **Escalera de escalada** en `stage/engine.py`: lectura (`check`), giro con `turning_actor_id` y
  su nota (`turn`), evento del mundo que entrega la cláusula que falta (`stall`), dos turnos de
  reacción y una lectura final. Un beat alcanzado así queda `intervened`; solo si ni eso basta,
  `forced`. El director ve las últimas tácticas de cada actor y los eventos del mundo ya usados.
- **Coda** de dos turnos tras el último beat de la obra.
- **Tácticas en vocabulario cerrado** (20 valores, impuesto por esquema).
- **Validación de turnos**: `LONG_SPEECH` (más de 45 palabras), `FIRST_PERSON_ACTION` (detector
  conservador, con su punto ciego documentado) y `REPEATED_ACTION` (contención ≥ 0,8 contra las 3
  últimas acciones propias). Un pensamiento que solo repite el habla se vacía. Se retira
  `MULTIPLE_BEATS`, que nunca se disparaba. `validate_turn` lanza `TurnIssue`, un `ValueError`
  con código.
- **`stage/<escena>/director.jsonl`**: una línea por llamada al director, con el borrador, las
  cláusulas, el veredicto derivado y el turno tras el que ocurrió.
- **El narrador cura**: los turnos que prueban un beat le llegan marcados `[clave]`, y su prompt
  pide comprimir tablas y tics, no pegar un pensamiento a cada réplica y contar lo que hace el
  mundo en el tiempo de la narración. Los títulos pierden el rótulo «Acto I:».
- **Medición honesta**: `action_repetition_ratio`, `first_person_actions`, `thought_ratio`,
  `long_speeches`, `yields`, `max_tactic_streak`, `compression_ratio`, `log_words`,
  `beats_intervened`, `reaction_turns` y `coda_turns`. Los eventos del mundo ya no cuentan como
  turnos de un actor. `report-simulations` las agrega e informa como «no medida» (celda vacía) la
  cifra que un run no registró, en vez de leerla como 0.
- **`audit-stage-run`**, contrato 2: una mentira deliberada ya no es una fuga de conocimiento, lo
  que el juez archive con otro tipo va a `set_aside` sin puntuar, y un informe anterior nunca se
  sobrescribe.
- `performance.json` pasa a `contract_version` "2"; `PIPELINE_VERSION` 7.1, con 7.0 todavía
  soportada.

## 7.0.0

- **El paquete pasa a llamarse Stagecraft.** `packages/top_down` es ahora `packages/stagecraft`,
  el modulo `asg_top_down` es `asg_stagecraft` y la distribucion `asg-top-down` es
  `asg-stagecraft`. El pipeline dejo de ser solo Top-Down: planifica de arriba abajo y, en el
  formato simulado, deja que los personajes representen el guion de abajo arriba. Los comandos
  (`generate-story`, `compare-story-runs`, `recover-story-runs`) conservan su nombre.
- Las ejecuciones nuevas se escriben en `Stories/Stagecraft/`. Las 160 ejecuciones anteriores se
  quedan donde estan, en `Stories/Top-Down/`, y se siguen leyendo: `SUPPORTED_PIPELINE_VERSIONS`
  conserva 5.0 a 6.2 junto a la nueva 7.0, y `report-story-craft` las agrupa igual que antes.
- `recover-story-runs` busca por defecto en `Stories/Stagecraft`; `--stories Stories/Top-Down`
  recupera las anteriores.
- `sync-railway-stories.ps1` acepta `-Collection`, con `Stagecraft` por defecto y `Top-Down` para
  el corpus anterior.
- El bot de Telegram registra el generador como `stagecraft` y mantiene `top-down` como alias, asi
  que un `STORY_GENERATOR` ya desplegado sigue arrancando.

## 6.9.0

- Nuevo formato de salida `script`, con dos métodos para llegar a él: `native` (un Dramaturgo
  escribe cada capítulo directamente como un acto de escenas estructurado) y `adapted` (el
  pipeline narrativo corre entero y un Adaptador convierte cada capítulo final de prosa al mismo
  contrato). Ambos métodos producen exactamente el mismo contrato — `script.json` más un
  `story.md` renderizado — para poder compararlos a ciegas y quedarse con uno; ver
  [docs/resumen.md](../../docs/resumen.md).
- Nuevo `script.py`, hermano de `graph.py` y `promises.py` y con su misma regla de idioma: los
  `ValueError` van en inglés ASCII porque se reinyectan literalmente, junto al índice de anclas
  legales, en el prompt de reparación del acto. Normaliza más de lo que rechaza: solo hay una
  corrección posible para los espacios, los paréntesis, el `speaker_id` sobrante de una acotación
  o una ubicación deducible, así que esos casos se corrigen en vez de gastar un intento.
- Nueva etapa `adaptation`, entre `revision` y `story`, exclusiva del método adaptado.
- Cuatro agentes nuevos: `PlaywrightAgent`, `ScriptWriterAgent`, `ScriptAdapterAgent` y
  `ScriptCriticAgent`. Los prompts narrativos (`DrafterAgent`, `WriterAgent`,
  `DramaCriticAgent`) no se tocaron: la suite narrativa pasa sin cambiar ni un byte de sus
  artefactos.
- La orquestación de las dos etapas de guion vive en `script_stages.py`, un mixin aparte de
  `pipeline.py` a propósito: los dos métodos son un experimento abierto (ver `TODO.md`), y el
  método que pierda se borra tocando un solo archivo.
- Nuevo interruptor `ASG_STORY_FORMAT` (`narrative` por defecto) y `ASG_SCRIPT_METHOD` (`native`
  por defecto), expuestos también como `--format`/`--script-method` en `generate-story`, en el
  menú de la consola y como paso de conversación en el bot de Telegram.
- Mantenido el contrato de artefactos 6.2: el formato de salida es aditivo y conmutable, así que
  el predicado de qué trae un run es `metadata.story_format`, no la versión del pipeline.

## 6.8.0

- Nueva etapa `promises`, entre `plan_review` y `drafting`. `PromiseLedgerAgent` traza un contrato
  Promise-Progress-Payoff sobre el plan **ya congelado**: cada apertura, progreso y pago cita el id
  de un `PlotEvent` que ya existe, y el `chapter_id` se deriva del evento en vez de escribirlo el
  modelo. El ledger cambia como se escribe el plan, nunca que contiene; hay un test que compara
  `story_plan.json` con y sin ledger byte a byte.
- Nuevo `promises.py`, hermano de `graph.py` y con su misma regla de idioma: los `ValueError` van
  en ingles y ASCII porque `_record_rejected_ledger` los reinyecta literalmente, junto al indice de
  anclas legales, en el prompt de reparacion. Dos intentos por run.
- Nuevo `promise_brief.py`, analogo de `craft_evidence.py`: convierte el ledger en obligaciones por
  capitulo para el Drafter y el Writer y en una lista de verificacion para el Drama Critic.
  `promise_ledger.json` guarda esos bloques ya renderizados, asi que un run terminado se audita sin
  volver a derivar que se le dijo a cada agente.
- `StoryReview` gana `promise_checks`, y `promise_audit.json` cruza el ledger con esos veredictos.
  Una promesa que el critico no juzgo cuenta como `broken`: el silencio no es un aprobado.
- `promise_band` en `profiles.py` deriva de `PROFILE_CHAPTER_BAND` cuantas promesas caben: 2-3, 3-5
  y 4-7. Es la excepcion consciente a la regla de un solo numero por prompt, porque el techo es la
  regla de oficio misma —toda promesa hecha se paga— y no un presupuesto que compita con otro.
- Anadido el interruptor `ASG_PROMISE_LEDGER` para la ablacion con y sin contrato; apagado, la
  etapa no corre y los prompts quedan identicos a la linea base.
- La etapa es degradable como la del arquitecto: agotados los intentos, queda un aviso en
  `metadata.json` y la historia se entrega sin obligaciones.
- Mantenido el contrato de artefactos 6.2: `promise_ledger.json` y `promise_audit.json` son
  adicionales y opcionales, y las ejecuciones anteriores siguen siendo legibles.

## 6.7.0

- `BLOCK_PARAGRAPH_WORDS` de `craft_evidence.py` baja de 120 a 90 palabras por parrafo. Medido
  sobre los 90 capitulos de las 23 ejecuciones 6.6.0 terminadas, leyendo el `chapter_metrics` que
  `story_metrics.json` guarda desde 6.5.0: el maximo observado es 64,6 palabras por parrafo y el
  p99 es 55,9, asi que el techo de 120 era inalcanzable y el canal no podia avisar de prosa en
  bloque. El corpus 6.5.0, anterior a la intervencion en el prompt del Drafter, llegaba a 217.
- `LOW_DIALOGUE_RATIO` se queda en 0,20, con la medicion que lo justifica: disparo en 1 de los 90
  capitulos, y el minimo observado es 0,1765. Una red de seguridad va justo fuera de la
  distribucion sana, no en uno de sus cuartiles.
- Ninguna cifra viaja a ningun prompt: solo el veredicto, como hasta ahora.
- Las ejecuciones interrumpidas ya no quedan bloqueadas en `running`. `StoryPipeline.execute`
  captura tambien `BaseException`, de modo que un `KeyboardInterrupt` cierra el run como `failed`
  con codigo `RUN_INTERRUPTED`, y el nuevo comando `recover-story-runs` cierra o descarta los que
  ya estaban varados. El conjunto de artefactos no cambia, asi que `PIPELINE_VERSION` sigue en 6.2.

## 6.5.0

- `story_metrics.json` registra la artesania de la prosa junto al tamano: parrafos, frases y
  palabras de prosa, parrafos que abren con raya, parrafos con comillas, parrafos con alguna
  marca de dialogo, `dialogue_ratio`, `words_per_sentence` y `words_per_paragraph`. Las cuatro
  ultimas cifras tambien van capitulo a capitulo en `chapter_metrics`. Medido sobre las 65
  historias 6.x del corpus: mediana de 26 palabras por frase, 82 por parrafo y 31% de parrafos
  con dialogo, y 8 historias sin una sola marca de dialogo. Ningun prompt cambia: son cifras
  observadas, no objetivos.

- Las primitivas viven en `asg_core.craft` (`craft_metrics`, `prose_paragraphs`,
  `split_sentences`) para que el recolector de `asg_evaluation` las use sin invertir la
  direccion de dependencias, y para que el Bottom-Up las reuse cuando se equiparen sus
  artefactos.

- `story_metrics.json` declara `chapter_bodies_recovered`. Cuando los encabezados canonicos no
  sobreviven, `parse_chapter_bodies` devuelve cuerpos vacios y las cifras por capitulo quedan en
  cero: antes ese cero era indistinguible de un capitulo vacio de verdad.

- `pipeline_version` pasa a `6.1`. El conjunto de artefactos no cambia, pero el contenido de
  `story_metrics.json` si, y `pipeline_version >= 6.1` es el predicado exacto de "este run
  registro su artesania". `StoryRun` sigue abriendo 5.0, 5.1, 5.2, 5.3 y 6.0.

## 6.4.0

- El numero de eventos que se le ensena al planificador y el que se le impone son ahora
  el mismo. `validate_profile_structure` valida el extremo bajo de `profile_event_target`
  (Esencial 4, Desarrollada 8, Expansiva 10) en vez de `PROFILE_MIN_EVENTS`, que antes
  dejaba a Esencial sin ninguna red. Expuesto como `profile_event_floor`.

- `MIN_EVENTS_PER_CHAPTER` deja de ser advisory: un capitulo con un solo evento rechaza el
  plan y dispara una replanificacion. La lista de capitulos flacos que ya calculaba
  `_event_budget_repair_rules` pasa a ser la causa del rechazo y no solo informacion
  adjunta a otro fallo. Medido sobre las 25 ejecuciones de 6.3.0: 16 de los 60 capitulos
  Expansivos y 9 de los 25 Desarrollados llevaban un solo evento.

- `PROFILE_GUIDANCE` ya no lleva numeros de eventos. Viajaba dentro del prompt de todos los
  agentes, asi que el planificador recibia dos cifras contradictorias en la misma llamada:
  su `system_instruction` pedia diez eventos para Expansiva y el bloque
  `NARRATIVE PROFILE CONTRACT` pedia nueve. El modelo obedecia el nueve, y planifico
  exactamente nueve eventos en 9 de sus 12 corridas. El ejemplo trabajado de rama y union
  queda marcado como fragmento, porque sus identificadores sugerian un total de seis.

- El planificador recibe el centro de la banda como objetivo (`profile_event_aim`) y el
  suelo declarado como frontera de rechazo, no como meta. El analista conserva un
  discriminador numerico para detectar el perfil, leido de la misma fuente.

- El plan se revalida en el unico punto donde se escribe `story_plan.json`
  (`StoryPipeline._persist_plan`), no solo en las dos ramas que lo producen. Un
  plan que incumpla su contrato estructural o el minimo de eventos de su perfil
  aborta la ejecucion con `PLOT_VALIDATION_FAILED` en vez de guardarse y dejar
  el run marcado como `completed`. Los artefactos de una ejecucion valida no
  cambian.

- El feedback de reparacion del planificador es ahora especifico por clase de
  error en vez de volcar siempre la matriz de `PAYOFF_OF`. Cuando falta la rama
  causal del perfil Expansiva, el prompt lleva los grados causales actuales de
  cada evento y **una arista concreta y legal** que repara el plan; cuando una
  dependencia apunta hacia atras, nombra la arista ofensora con sus dos `order`
  y las dos reparaciones validas. Medido sobre los dos candidatos que Gemini
  rechazo en la prueba canonica: el modelo trataba el contrato como un puzle de
  conteo y perdia la restriccion de orden, primero omitiendo la rama y despues
  anadiendola en direccion prohibida.

- El planificador recibe un ejemplo trabajado de rama y reunion con ordenes
  explicitos, porque la formulacion abstracta fallo dos veces seguidas.

- Los intentos de planificacion pasan a depender del perfil
  (`PLAN_ATTEMPTS_BY_PROFILE`): Expansiva dispone de 4 y el resto de 3, frente a los 2
  fijos anteriores. Es un techo, no un coste: solo se gasta cuando hay rechazo.
  `PlotValidationError` informa del numero real de intentos, que antes estaba
  fijado a 2 en el mensaje y en `details`.

## 6.3.0

- Corregido el reintento de revision: una excepcion degradable ya no descarta el
  segundo intento permitido, sino que reintenta y solo cae al borrador cuando se
  agotan los intentos. Antes, un `ProviderError` transitorio en el intento 1
  dejaba el capitulo sin revisar.
- El writer ya no se invoca en capitulos sin notas del critico. La llamada no
  podia cambiar nada y solo anadia coste y superficie de fallo; el informe marca
  esos capitulos con `final_source: "draft"` y `warning_code: null`.
- Completada la ablacion de `ASG_NARRATIVE_GUIDANCE`: el vocabulario de roles
  funcionales tambien queda fuera del prompt del disenador de personajes cuando
  la guia esta apagada. Hasta ahora se inyectaba siempre, asi que el brazo de
  control conservaba `functional_role` y `persona` y no era una linea base
  limpia, pese a lo indicado en 6.2.0.
- Anadida `PROFILE_CHAPTER_BAND`, una banda de capitulos por perfil que el
  planificador recibe como guia junto a un reparto de eventos que evita
  capitulos de un solo evento. Es orientativa: ninguna validacion la exige
  todavia, a la espera de medir su efecto.
- `generate-story` acepta `--profile`, `--output`, `--model` y `--no-audio`.
  `--profile` manda sobre el perfil deducido del prompt, y `--no-audio` omite la
  narracion, que consumia entre el 23% y el 45% del tiempo de cada ejecucion.

## 6.2.0

- Anadida una biblioteca de 34 esqueletos de trama etiquetados por capa
  (macrotrama y subtrama), definidos por objetivo y transformacion del mundo, con
  preguntas de presion abiertas en vez de listas cerradas de beats.
- Anadido un vocabulario de roles de personaje en dos capas: rol funcional
  (Propp y Greimas) y persona superficial abierta; `CharacterProfile` gana los
  campos opcionales `functional_role` y `persona`.
- Anadida la etapa `architecture`, que escribe `narrative_blueprint.json` con la
  lectura estructural de la premisa y el ranking que la justifica.
- El emparejamiento combina puntuacion lexica TF-IDF local con una llamada
  semantica, mezcladas 70/30, y degrada a solo lexico si el proveedor falla.
- La guia se inyecta como texto explicitamente no vinculante solo en el
  disenador de personajes y el planificador; ninguna validacion penaliza
  desviarse de ella.
- Anadido el interruptor `ASG_NARRATIVE_GUIDANCE` para la ablacion con y sin
  guia; apagado, los prompts quedan identicos a la linea base.
- Mantenido el contrato de artefactos 6.0: `narrative_blueprint.json` es
  adicional y opcional, y las ejecuciones anteriores siguen siendo legibles.

## 6.1.0

- Conservado el perfil Esencial sin un mínimo adicional de eventos.
- Exigidos al menos seis eventos para Desarrollada y nueve para Expansiva; los
  planes Expansivos requieren además una bifurcación y reunión causal.
- Hechos sensibles al perfil los agentes de mundo, personajes, planificación,
  crítica y redacción para ampliar mediante cambios narrativos en vez de relleno.
- Mantenido el contrato de artefactos 6.0 y la ausencia de presupuestos de
  palabras o capítulos.

## 6.0.0

- Sustituidos los presupuestos de palabras, capítulos y eventos por los perfiles
  cualitativos Esencial, Desarrollada y Expansiva.
- El planificador decide libremente la forma del DAG y conserva únicamente sus
  invariantes objetivas de referencias, conectividad, causalidad y orden.
- Reemplazado `length_audit.json` por `story_metrics.json`, que registra
  conteos observados sin objetivos ni tolerancias.
- Eliminados `default_target_words`, `STORY_DEFAULT_WORDS` y los rechazos del
  Writer basados en longitud; el contrato de pipeline pasa a 6.0.

Las versiones nuevas deben agregarse siempre encima de las versiones anteriores.

## [5.3.0] - 2026-08-31

- Añadidos diagnósticos estructurados del Writer con códigos, conteos, límites y
  correcciones cuantificadas para el reintento.
- Archivados todos los intentos y su decisión en revision_report.json.
- Enriquecidos los fallbacks con resúmenes accionables sin perder compatibilidad
  con metadata.json.warnings.
- Publicado el contrato de artefactos 5.2 manteniendo lectura de runs 5.0 y 5.1.

## [5.2.0] - 2026-08-29

- Enriquecido el análisis de solicitudes breves con un brief inglés y direcciones
  creativas separadas de los requisitos explícitos.
- Añadidos presupuestos exactos de eventos, conectividad causal, precondiciones,
  efectos, función dramática y referencias de setup/payoff.
- Aclarado y reforzado que `payoff_of` solo acepta IDs de eventos anteriores,
  con diagnósticos y feedback de reparación que enumeran las referencias válidas.
- Incorporada una crítica acotada del plan con reemplazo único y fallback al
  primer DAG válido.
- Sustituidos los agentes finales por `Drafter → Drama Critic → Writer`, con
  contexto de ancestros del DAG, notas globales/locales y revisión por capítulos.
- Añadidos reintentos auditables de Writer, fallbacks aislados y los artefactos
  `plan_review.json`, `draft_presentation.json` y `revisions/`.
- Publicado el contrato de artefactos 5.1 manteniendo lectura de runs 5.0, sin
  avanzar a una versión 6.

## [5.1.0] - 2026-08-27

- Added `generator_version.json` to every run so generated stories retain the
  exact generator release separately from the pipeline artifact version.
- Separated the public facade, stage orchestrator, and length audits.
- Shared paths, safe names, and atomic writes through `asg-core`.
- Moved the package into the monorepo layout and normalized English docstrings.

## [5.0.0] - 2026-08-27

- Sustituida la planificación incremental por un único DAG de eventos genéricos
  con dependencias causales o temporales y orden topológico calculado localmente.
- Reducido el pipeline a solicitud, mundo, personajes, plan, capítulos, crítica
  y una edición final con fallback seguro al borrador.
- Eliminados los subsistemas de nodos tipados, memoria factual, craft,
  taxonomías, base SQLite y recuperación semántica.
- Simplificados contratos, configuración, artefactos, API pública y UIs; los
  runs nuevos usan `pipeline_version` 5.0 y no reanudan versiones anteriores.
- Reemplazadas las suites anteriores por pruebas del DAG, replanificación única,
  pipeline completo, fallback editorial e integración real opt-in.

## [4.1.0] - 2026-08-26

- Extraido el ciclo pseudo-CPN a contratos de contexto, resultado y planificador
  independientes del coordinador de STORYLINE.
- Unificada la validacion determinista antes y despues de las correcciones del
  revisor, con codigos estables y feedback estructurado para Gemini.
- Convertida la planificacion de cada capitulo en una transaccion: un fallo no
  modifica STORYLINE/NEKG y permite regenerar sus anclas una vez antes de fallar.
- Anadidas pruebas de rollback, agotamiento, errores repetidos, compatibilidad y
  una suite Gemini real opt-in con tres historias.

## [4.0.0] - 2026-08-20

- Separados físicamente los carriles factual y de craft; STORYLINE consume una
  proyección de personajes sin sliders y queda congelada antes de PPP.
- Añadidos `StoryFrame`, predicados/mutaciones tipados, estado rico de mundo,
  DAG causal real, validación determinista y presupuestos CPN adaptativos.
- Sustituido PPP 3.3 por `PromiseLedger`, arcos positivo/negativo/plano,
  directivas scene/sequel, try-fail y `CraftAlignment` posteriores a STORYLINE.
- Añadidos briefs sanitizados, estado anterior al capítulo, reparación selectiva
  y recálculo de longitud sobre la versión final.
- Añadidas escrituras atómicas, manifiesto con hashes, checkpoints por respuesta
  y registro de llamadas Gemini exitosas y fallidas.
- Eliminados obligaciones PPP→STORYLINE, catálogo legacy, auditoría diagnóstica
  duplicada y falsa recuperación automática; Telegram usa `recovery_pending`.

## [3.3.0] - 2026-08-18

- Sustituido el contenedor `CraftVariant` por planes independientes de PPP global,
  arcos de personaje, try-fail y PPP por capítulo.
- Movido el craft estructural antes de STORYLINE mediante obligaciones narrativas
  neutrales que no contaminan los contratos de nodos.
- Añadida trazabilidad de PPP locales a nodos aceptados, briefs sanitizados para el
  escritor y una única replanificación estructural ante cobertura imposible.
- Eliminadas las tres variantes, el selector, `render_variant()` y los artefactos
  `craft/variants/`; conservadas las salidas canónicas para consola y Telegram.
- Versionados el paquete y los runs como Top-Down 3.3.

## [3.2.0] - 2026-08-18

- Integrado en el analista el enriquecimiento inglés de cada prompt, conservando
  literalmente la solicitud original y separando constraints explícitos de
  decisiones creativas inferidas.
- Resuelto el idioma final por petición explícita, idioma dominante y fallback a
  español, con auditoría bloqueante y títulos de capítulo localizados.
- Separada la consulta semántica enriquecida de la evidencia taxonómica explícita
  y versionados los runs nuevos como Top-Down 3.2 sin romper requests anteriores.

## [3.1.0] - 2026-08-18

- Sustituido el catálogo fragmentario por 24 perfiles taxonómicos descriptivos
  en inglés, con fuentes, variantes, alternativas y guía anticliché.
- Añadidos `TaxonomyApplication`, `TaxonomyBrief`, shortlist híbrida auditable y
  léxico español de reconocimiento separado del contenido narrativo.
- Integrado el brief flexible en mundo, personajes, STORYTELLER, craft,
  redacción, auditoría y reescritura sin convertir convenciones en una plantilla.
- Versionados los runs nuevos como Top-Down 3.1 y conservada la lectura de
  artefactos Top-Down 3.0 terminados.

## [3.0.0] - 2026-08-16

- Eliminados `StoryOrchestrator`, el procesador DAG, los agentes y contratos del
  pipeline legado, el paquete diagnóstico `Testing` y las taxonomías JSON ya
  cubiertas por el catálogo SQLite.
- Convertido `IncrementalPlotPlanner` en un núcleo STORYTELLER sin craft, con
  CBN/CEN previos, CPN adaptativos, siete controles bloqueantes, conexión
  explícita con CEN, checkpoints y consultas STORYLINE/NEKG acotadas.
- Encapsulado NEKG detrás de una interfaz local en memoria y JSON, con prioridad
  para relaciones dirigidas sujeto→objeto y exclusión de candidatos rechazados.
- Movidos todos los prompts activos a agentes de producción y traducidas al
  inglés las instrucciones, etiquetas y reparaciones enviadas al modelo.
- Aplicada a protagonistas la regla de exactamente dos sliders altos y uno bajo,
  siendo el bajo el foco ascendente hasta un valor alto.
- Añadidas tres variantes independientes de craft posteriores a STORYLINE,
  selección auditable, PPP global/local, hitos de sliders, ciclos try-fail y
  constraints bloqueantes.
- Añadido `StoryGenerator.render_variant()` para redactar alternativas de forma
  idempotente sin replanificar ni reemplazar la selección o historia canónica.
- Reorganizados los artefactos bajo `craft/variants/variant-N/` y conservadas
  vistas raíz compatibles con CLI, consola, Telegram y comparación.
- Cambiado el escritor para consumir únicamente el craft seleccionado del
  capítulo actual y el capítulo anterior completo, manteniendo la ficción en el
  idioma solicitado aunque las instrucciones internas estén en inglés.
- Conservadas reparaciones estructuradas, cuotas, telemetría, recuperación
  segura, tolerancia de longitud y entrega del mejor borrador disponible ante
  fallos tardíos de auditoría o reescritura.
- Migrados CLI, consola y Telegram a `StoryGenerator`; los runs terminados
  anteriores siguen siendo entregables y las variantes v3 pueden compararse
  directamente con `compare-story-runs`.
- Incrementada la versión de `asg-stagecraft` a `3.0.0` y actualizado el modelo
  predeterminado preservado a `gemini-3.5-flash-lite`.
- Sustituidas las pruebas del pipeline eliminado por cobertura v3 de sliders,
  límites y reemplazos CPN, checkpoints, recencia NEKG, craft desacoplado,
  constraints bloqueantes, reescritura, variantes, idempotencia e interfaces.
  La suite completa queda en 128 pruebas aprobadas.

## [2.0.5] - 2026-08-16

- Separado el contexto narrativo del capítulo del scope autoritativo de craft
  enviado al proponente y al revisor CPN, evitando que beats `setup` o `payoff`
  reservados para CBN/CEN se interpreten como requisitos pendientes del CPN.
- Convertida la cobertura de IDs de craft en una decisión determinista: Gemini
  conserva la revisión causal y semántica, pero ya no puede rechazar un candidato
  por contradecir el scope calculado localmente.
- Añadida una prueba de regresión que reproduce el fallo real de `chap_4:1`, con
  un revisor que inventa tres beats pendientes cuando el scope permitido está
  vacío.

## [2.0.4] - 2026-08-16

- Añadida reparación semántica auditable para plan, personajes, contrato,
  outline y anclas; cada candidato inválido y su causa se conserva bajo
  `artifact_attempts/` antes de solicitar un reemplazo completo.
- Incorporado `ARTIFACT_VALIDATION_FAILED`, con etapa, cantidad de intentos y
  reglas incumplidas, y `STORY_MAX_ARTIFACT_RETRIES` para configurar las
  reparaciones sin cambiar los llamadores existentes.
- Validadas la correspondencia exacta entre capítulos y anclas, la suma de
  presupuestos, las referencias de craft y la STORYLINE final con diagnósticos
  estructurados en lugar de `ValueError` o `KeyError` genéricos.
- Restaurados los checkpoints de etapas, el progreso durante esperas de cuota y
  `llm_usage.json`/`llm_usage_summary.json` en el generador v2.
- Normalizados los títulos de capítulos y añadida una auditoría final de
  longitud de −10 % a +20 %, eligiendo la versión válida más cercana al rango.
- Conservada la mejor historia disponible cuando falla o se agota la auditoría
  o reescritura final, mediante `quality_warning.json` y
  `metadata.json.warnings` sin relajar la planificación CPN.
- Configurada la salida UTF-8 del CLI de Windows para evitar fallos al imprimir
  las barras Unicode de progreso.

## [2.0.3] - 2026-08-16

- Impedido que propuestas y revisiones CPN reclamen IDs de craft ya consumidos.
- Incorporado el alcance autoritativo de craft al revisor y a los diagnósticos.
- Diferenciadas en los checkpoints la propuesta original y la revisión evaluada.

## [2.0.2] - 2026-08-16

- Normalizadas como rechazos recuperables las revisiones CPN contradictorias.
- Añadido un reintento de respuestas estructuradas con diagnósticos sanitizados.
- Incorporados checkpoints de planificación y recuperación ante schemas inválidos.

## [2.0.1] - 2026-08-16

- Incorporado un contrato Sanderson para promesas, progreso, pagos, sliders de
  personajes principales y ciclos Yes-but/No-and.
- Añadidos un crítico estructurado, hasta dos reescrituras y la selección de la
  mejor versión con historial auditable.

## [2.0.0] - 2026-08-09

- Reimplementado el generador Top-Down mediante el flujo incremental de
  STORYTELLER: estructura de capítulos, anclas CBN/CEN y generación y revisión
  individual de cada CPN.
- Incorporadas STORYLINE y NEKG activas durante la planificación, con relaciones
  causales y seguimiento de ubicación, posesiones, conocimiento, estado y
  relaciones de las entidades.
- Sustituidas las taxonomías monolíticas por una base SQLite reproducible desde
  migraciones y semillas, separando macrotramas, situaciones dramáticas, arcos,
  beats, géneros y roles.
- Añadida recuperación híbrida mediante FTS5/BM25 y embeddings Gemini cacheados,
  con fallback léxico cuando el servicio de embeddings no está disponible.
- Añadidas las interfaces públicas `StoryGenerator`, `StoryRun`,
  `NarrativeSchemaRepository`, `IncrementalPlotPlanner` y `StorylineState`.
- Reemplazada la puntuación autorreferencial de calidad por una auditoría
  diagnóstica sin notas numéricas.
- Añadidos artefactos versionados de blueprint, trazas de recuperación, outline,
  anclas, revisiones de nodos, capítulos y estado narrativo.
- Incorporado `compare-story-runs` para revisar visualmente historias anteriores
  y nuevas lado a lado.
- Añadidas pruebas de migración, caché, fallback sin red, recuperación híbrida,
  planificación incremental, actualización del NEKG y comparación visual.

## [1.1.0] - 2026-08-09

- Añadida la configuración `STORY_DEFAULT_WORDS`, con validación y prioridad
  para la extensión indicada explícitamente por el usuario.
- Incorporada la auditoría no bloqueante de longitud, con tolerancia de ±10 %
  por capítulo y ±5 % para la historia completa.
- Mejoradas las instrucciones de construcción de mundo, planificación y
  escritura para reforzar causalidad, estructura y variedad de géneros.
- Ampliadas las pruebas de configuración, esquemas, almacenamiento y longitud.

## [1.0.0] - 2026-08-09

- Inicio formal del historial de versiones de Top-Down.

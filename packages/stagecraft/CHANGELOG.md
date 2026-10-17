# Historial de cambios

## 7.17.0

Viene del análisis de los runs de 7.10 a 7.16 contrastado con la literatura de 2023 a 2026. El
plan completo está en `TODO.md` (SIM-25, SIM-26 y TD-10). Añade artefactos y cambia los esquemas
del casting y de los personajes, así que `PIPELINE_VERSION` pasa a 7.17.

**Lo que dejó claro el análisis:**

- Flash-Lite copia lo que recibe:
  - con el log entero, transcribe;
  - con el estilo indirecto de 7.16, copia esas frases y salen párrafos de acta.
- Juzgar la calidad tampoco lo hace bien. El crítico no dio ninguna nota en 3 de 4 narrativas
  de 7.10, y la literatura sitúa su juicio de escritura cerca del azar.
- Por eso 7.17 controla lo que entra en cada agente y deja el juicio al código.
- Error de método: los cuatro runs de 7.16 se lanzaron sin `brief.json` y en perfil Esencial,
  para un brief que pide una historia extensa.

**Seis brazos, apagados por defecto.** Cada uno se activa con una opción de solo API, una
variable `ASG_*` y un flag de `asg-generate`. El predeterminado no cambia hasta la lectura
humana a ciegas.

- **`style_examples`.** El contrato de estilo lleva dos párrafos de muestra en español, sin
  trama. El editor marca la copia de cinco palabras seguidas.
- **`line_editor`.** `asg_core.craft.paragraph_flags` marca cada párrafo con lo que estorba al
  lector:
  - acotación que explica la emoción, coletilla en gerundio o nombre en la acotación;
  - nombre repetido;
  - palabras largas;
  - acta;
  - bloque;
  - frase gastada;
  - símiles;
  - apertura atmosférica.

  `writing/line_edit.py` manda al editor solo esos párrafos. Una edición se acepta solo si:
  - la marca baja;
  - no alarga más de un 10 %;
  - no inventa un nombre ni una réplica;
  - no cambia el tiempo verbal.

  Se guarda en `line_edits/chapter-NNN.json`. Con el editor, la segunda narración de 7.15 solo
  se pide por `DROPPED_EVENT`.
- **`scene_cards`.** Antes del Drafter, una llamada convierte cada evento en una o dos fichas:
  - lugar y personajes;
  - qué quiere cada uno;
  - el obstáculo;
  - el giro;
  - un detalle sensorial;
  - lo que no se dice;
  - el cierre.

  Las valida `planning/scene_cards.py`, con errores en inglés que se reinyectan, y se guardan en
  `scene_cards.json`. Con fichas, el Drafter deja de recibir `plan.ending` y los capítulos
  futuros. La etapa es degradable (`[SCENE_CARDS_FALLBACK]`).
- **`anchored_critic`.** El crítico da como mucho una nota por capítulo y cita el borrador.
  `writing/anchoring.py` busca cada cita: una restricción aprobada sin cita que exista pasa a no
  juzgada y genera una nota, y una promesa así pasa a `broken`. El registro queda en
  `review_anchors.json`.
- **`narration_method=selected`.** `NarratorAgent.select` agrupa el log en momentos, cada uno
  `scene` o `summary`, con una frase y un puente entre escenas. `stage/selection.py`:
  - devuelve los sucesos del mundo y las réplicas clave;
  - rechaza un resumen que copia;
  - limita a la mitad las líneas jugadas.

  `NarratorAgent.write` escribe desde los momentos, los lugares del mundo y la cara pública del
  reparto, nunca desde el log. Se guarda en `narration/chapter-NNN-selection.json`. Si la
  selección falla, el capítulo se narra como en 7.16 (`[SELECTION_FALLBACK]`).
- **`typed_clauses`.** El director marca cada cláusula como `decision`, `revelation` o `world`,
  con un esquema aparte (`TypedBeatCheckDraft`), así que el control no cambia.
  - Cuando lo único que falta es del mundo, el beat pasa a la lectura de estancamiento sin
    esperar al tope, y el `stage_event` puede ejecutarlo (`WORLD_CLAUSE`).
  - El casting rechaza una compuerta cuyo revelador no está en la escena de su evento.

**Siempre activo:**

- **`asg-generate --narrate-from <run>`**: vuelve a narrar una función guardada sin
  representarla, en unas 12 llamadas frente a 130. **`--plan-from`** sirve también con
  `--format narrative`.
- **Legibilidad en StageCraft.** `pairing.py` recalcula desde `story.md` siete cifras de
  legibilidad, también para los runs antiguos. No se tocó `rasgos.csv`: cambiaría la huella del
  catálogo y el juez de 27 entradas.
- **El Writer** ya no entrega una reescritura que pierde un 30 % de los párrafos, que alarga más
  de un 15 % sin nota que lo pida, o que empeora lo medido (TD-3). Los códigos son
  `MERGED_PARAGRAPHS`, `LENGTHENED_WITHOUT_CAUSE` y `WORSE_CRAFT`.
- **Nombres por candidatos (TD-7).**
  - El diseñador propone tres nombres por personaje con su tipicidad.
  - `planning/names.py` elige el menos típico que no esté en una lista que el prompt no ve.
  - Renombra en todo el reparto y vuelve a acuñar el id si salía del nombre.
  - El prompt ya no nombra los nombres vetados. Se guarda en `name_choices.json`.
- **El dossier declara la fuente de cada hecho inicial** (`knowledge_sources`). El hecho que
  viene de un evento posterior a la primera escena del personaje se descarta
  (`[CAST_FACT_DROPPED]`). Quien guarda un secreto entra con su `cover_story` (SIM-11).
- **Validadores de la función:**
  - `_ship_leftover` desempata por gravedad.
  - La primera persona conjugada de una lista cerrada se corrige: «Golpeo» pasa a «Golpea».
  - El tic ignora las rachas con palabras de lugar.
  - Una evidencia de estado sin cita conserva el turno y descarta el cambio
    (`STATE_CHANGE_DROPPED`).
  - El plan condicional («Si…, tendré que…») se vacía del pensamiento; el miedo condicional, no.
  - La tercera táctica igual seguida se rechaza (`TACTIC_RUN`).
  - El actor ve en español lo que ha probado y se le pide responder a lo que le dijeron.
  - La nota de giro que no cita nada de la escena se sustituye por la de reserva.

Sin validar en real: el protocolo y el presupuesto están en `TODO.md`. 781 tests en verde.

## 7.16.0

Lo que dejó roto la prueba de 7.15.2 (`20261015-174818-las-islas-del-cielo`, Esencial). Añade
`narration/chapter-NNN-reported.json` y cambia lo que lee el narrador y cómo acaba la obra, así
que `PIPELINE_VERSION` pasa a 7.16.

- **El narrador recibe en estilo indirecto lo que no es clave.**
  - En 7.15.1 copió las 15 de 15 réplicas de un capítulo. En 7.15.2 recibió cortadas tras la
    primera frase las que no eran `[clave]` y copió los muñones («—Celestina, mira… —dijo
    Teodoro»). Así perdió las preguntas y el tartamudeo, con `dialogue_survival` en 0,95.
  - Ahora `NarratorAgent.report` reescribe esas réplicas en estilo indirecto, una frase por
    réplica y una llamada por capítulo. El narrador solo las recibe así, sin texto que copiar.
  - `stage/narration.accept_reports` descarta la paráfrasis que comparte cuatro palabras
    seguidas con la réplica. Si la llamada falla, las réplicas van enteras con
    `[REPORT_FALLBACK]`.
  - Un beat forzado no tiene réplicas `[clave]`: el final de 7.15.2 tenía 12 y ninguna clave.
    Por eso el resumen ordena además las réplicas más memorables, y el código conserva enteras
    las primeras hasta una de cada tres del capítulo, con un mínimo de dos.
  - La primera prueba en vivo dio tres arreglos:
    - las líneas llevan ids cortos (`L1`, `L2`…), porque con ids de turno el modelo renumeró la
      segunda escena y se perdieron 12 de 16 resúmenes;
    - el ejemplo del esquema lleva tildes, porque sin ellas el modelo escribía «acuso»;
    - las réplicas conservadas salen de una lista ordenada, porque con un booleano no marcó
      ninguna.
  - El prompt pide conservar los rasgos de habla deliberados, como el tartamudeo, al corregir la
    ortografía.
- **Los sucesos del mundo son siempre clave.** La única sacudida del final de 7.15.2 no llegó a
  la prosa. `craft_findings` añade la nota `DROPPED_EVENT` cuando un capítulo no cuenta un
  suceso del mundo; activa el segundo intento, nunca un rechazo.
- **La obra acaba en escena.**
  - En 7.15 y 7.15.2 el último beat se forzó con el barco amarrado, y la historia terminó en una
    pregunta.
  - En el último beat de la obra, la lectura de estancamiento (`CLOSING_STALL`) deja que el
    mundo ejecute la consecuencia visible de una elección ya tomada en escena. Nunca elige por
    los personajes.
  - Ese beat tiene un turno de reacción más.
- **La nota de reserva dice qué falta.** `FALLBACK_TURN_NOTE` no tenía `{part}`, así que el actor
  nunca supo qué faltaba. La nota de coda abierta llegaba como «La cuesti?n sigue abierta».
- **Un dúo deja entrar a un tercero.**
  - En 7.15.2 hubo 12 parejas personaje-escena sin un turno, y Aleth, la guía, habló 3 veces en
    toda la obra.
  - `policy.next_actor` da el turno al más callado cuando los últimos cuatro son de dos
    personajes.
- **Un gesto repetido en toda la obra es un tic.**
  - En 7.15.2 Ilse apretó tres veces el pomo de su espada corta y Gaspar golpeó cuatro el
    mamparo. `REPEATED_ACTION` solo miraba los tres gestos anteriores.
  - Ahora también rechaza, solo en el primer intento, el gesto que repite tres palabras seguidas
    de cualquier gesto anterior del mismo actor (`GESTURE_RUN`). En los runs de 7.12 a 7.15
    marca uno de cada diez.
- **Un suceso del mundo copiado entre paréntesis pierde los paréntesis.** Marcado como clave, el
  narrador lo copió como párrafo en la validación (`strip_markers`).
- **Validación (2026-10-17).** Dos pares 7.15.2 / 7.16 del mismo prompt, cada par lanzado a la
  vez: `20261017-182746` / `182756` y `184650` / `184641`.
  - `dialogue_survival` bajó de 0,89 y 0,92 a 0,47 y 0,47, y las líneas de diálogo, de 36 y 49
    a 11 y 17. El árbitro descartó 7 de 26 y 3 de 41 resúmenes.
  - Sin cambio claro en beats forzados (1 y 2 frente a 1 y 3) ni en finales logrados (uno por
    brazo). El final de `184641` es el único de los cuatro en que la obra se resuelve en escena.
  - Personajes mudos: 4 de 20 y 7 de 25 frente a 4 de 19 y 1 de 19.
  - Peor en 7.16: la prosa resume de más. Encadena réplicas indirectas en párrafos largos,
    vuelve a etiquetar con «dijo» las réplicas que conserva, y en `182756` copió el suceso entre
    paréntesis y acabó sin final.
  - Con dos pares no se separa del ruido. Hace falta la lectura humana a ciegas.
- **Los nativos conocen su mundo (SIM-22).** El casting pone en el `initial_knowledge` de quien
  es de un lugar las costumbres, la moneda, las leyes y la historia que vive allí.

## 7.15.1

Lo que la primera prueba completa de 7.15 (`20261015-134855-las-islas-del-cielo`) dejó roto. Sin
artefactos ni esquemas nuevos: `PIPELINE_VERSION` sigue en 7.15.

- **El segundo intento del narrador solo se entrega si mejora.**
  - En 7.15 se entregaba siempre. El capítulo 1 pasó del pretérito al imperfecto
    («aferraba», «se acercaba»: 0 pretéritos frente a 32 imperfectos).
  - El capítulo 2 cambió «dijo» por «advirtió» y «replicó» y siguió con una acotación por
    réplica.
  - Ahora el segundo intento sustituye al primero solo si pasa la revisión y tiene menos
    observaciones medidas. Si no, se entrega el primero con `[NARRATION_CRAFT_KEPT_FIRST]`.
  - La revisión editorial bloquea como `WRONG_TENSE` un capítulo narrado en imperfecto
    (`narrative_tense`).
  - Las notas avisan de que cambiar de verbo no basta y piden conservar el pretérito.
- **Un estancamiento sin evento del mundo se pregunta otra vez.**
  - El beat final de 7.15 se cerró sin `stage_event`: los actores siguieron con la disputa de
    la escena anterior y la historia acabó antes de su desenlace.
  - El director recibe una segunda lectura `stall` que pide una presión visible, nunca el
    desenlace. Si vuelve vacía, queda `[STAGE_EVENT_MISSING]`.
  - En la escena que cierra la obra, el actor lee que lo que quiere ahí pesa más que lo que
    perseguía antes.
- **Un personaje atascado en su táctica cuenta como atasco.** Hanu amenazó en tres de sus
  cuatro turnos mientras Gaspar e Ilse le contestaban por turnos, así que el atasco de dos
  actores alternándose nunca saltaba.
- **El analista distingue el idioma de la historia del de los campos.** Dos veces dio
  `English` para el brief en español. `[LANGUAGE_OVERRIDE]` sigue como red.
- **El plan en la segunda frase de un pensamiento también se quita.**
- **Lo que no se hizo.** Comparar `RESTATED_POSITION` con lo que le dijeron al actor no detecta
  las amenazas de Hanu (0,21 frente al umbral de 0,3) y añade 4 falsos positivos en 301 líneas,
  así que no se aplica.

## 7.15.0

Lo que quedaba de la prueba 7.14 (`20261014-195514-las-islas-del-cielo`). Cambian los prompts
del narrador y el comportamiento de la función, así que `PIPELINE_VERSION` pasa a 7.15.

- **El narrador cura en vez de transcribir.**
  - En 7.13 y 7.14 cada capítulo copiaba literalmente casi todas las réplicas del log (13 de 13,
    18 de 18; `dialogue_survival` 1.0) y ponía verbo de habla en casi todas (16 de 18).
  - `stage/editorial.craft_findings` mide las dos cosas (`TRANSCRIBED`, `TAGGED`). Un primer
    intento aceptado que las cumple se narra una vez más con esas notas; si el segundo no pasa
    la revisión, se entrega el primero. Nunca es motivo de rechazo.
  - El prompt pide acotar solo cuando no se sepa quién habla y corregir la ortografía de las
    réplicas sin cambiar su sentido: el narrador copiaba las erratas de los actores de 3.1
    («Necestio», «ni un astilla»).
- **Una postura repetida con otras palabras cuesta un reintento.**
  - Hanu hizo la misma amenaza tres veces en el final, e Ilse y Gaspar se amenazaron ocho
    turnos seguidos. `REPEATED_LINE` solo ve repeticiones casi literales.
  - `RESTATED_POSITION` rechaza, solo en el primer intento, una línea cuyas palabras de
    contenido ya dijo el mismo personaje en la escena (`PARAPHRASE_CONTAINMENT`, 0,3). En los
    runs de 7.12 a 7.14 marca 6 de 140 líneas.
- **El idioma del prompt manda sobre el del analista.** En la primera prueba de 7.15
  (`20261015-132526`), el analista devolvió `language: English` para el brief en español que
  dice «Idioma español», y la historia entera salió en inglés. `writing/language.prompt_language`
  reconoce el idioma de un prompt claramente escrito en uno; si discrepa del analista, gana el
  prompt, con un aviso `[LANGUAGE_OVERRIDE]`.
- **Un pensamiento que es un plan se vacía.** Igual que el eco: «Debo…», «Tengo que…»,
  «Voy a…» (7 de 48 en 7.14).

## 7.14.0

Lo que falló en la prueba 7.13 (`20261014-180523-las-islas-del-cielo`, Esencial). Añade
`localization.json` y cambia el esquema del turno de actor, así que `PIPELINE_VERSION` pasa a
7.14.

- **El casting ya no pierde la biblia por una compuerta.**
  - El casting de 7.13 creó compuertas, pero se rechazaron en los dos intentos: la descubridora
    estaba en `known_by`, y una confesión no tenía confesor. Toda la función corrió sobre
    `fallback_bible`.
  - `_normalize_gates` corrige las dos formas que tienen una sola corrección: quien descubre o
    deduce sale de `known_by`, y una confesión con un solo poseedor lo toma como confesor.
  - El último intento descarta la compuerta que siga rota, en vez de la biblia entera, y avisa
    con `[CAST_GATE_DROPPED]`. Las reglas no cambian: una compuerta descartada nunca se relaja.
- **La frontera de idioma, vigilada en código.**
  - `writing/language.py` detecta por palabras funcionales un texto corto en el idioma
    equivocado («Arrival and Discovery» en una historia en español).
  - `LocalizerAgent` traduce solo esos campos: título, títulos de capítulo, marco del guion y
    roles. Nunca la prosa.
  - Lo traducido queda en `localization.json`, con el original al lado.
  - Si el localizador falla, el capítulo pasa a «Capítulo N», con
    `[LOCALIZATION_FALLBACK]`. Sin nada marcado, no hay llamada ni artefacto.
- **Un capítulo que copia las acotaciones del log está en presente.**
  - El capítulo 2 de 7.13 reutilizó 15 acotaciones literales, que se escriben en presente; los
    demás capítulos, una como mucho.
  - La revisión editorial lo bloquea como `WRONG_TENSE`, en cualquier idioma.
- **Pensamiento sin planes.**
  - El actor ya no relee sus pensamientos anteriores en «LA ESCENA HASTA AHORA».
  - El esquema define el pensamiento como lo que nota, teme o calla, nunca lo que planea hacer
    (SIM-6).
- **El plan lee la trama del brief.** `brief.authored_plot_block` la manda literal al
  planificador y al crítico de plan como canon (TD-9). Sin brief, el prompt no cambia.

## 7.13.0

Lo que salió del análisis de los navegantes (`20261013-180025-las-islas-del-cielo`, 7.12,
Expansiva): 2 h 55 min, de los que 98 fueron esperas; un reparto distinto del declarado y 5 de
10 beats forzados. `PIPELINE_VERSION` pasa a 7.13 porque `stage_model` cambia de significado.

- **Solo los actores van al modelo de la función, también con cadena.** Antes la función
  entera iba a `GEMINI_STAGE_MODEL` sin cadena, y con `ASG_LLM_CHAIN` ese modelo era solo la
  segunda ranura. Así, los 165 turnos de actor de los navegantes gastaron primero la cuota de
  3.5 Flash-Lite. Se agotó en la llamada 93, y el director y **toda la narración** salieron de
  3.1. Ahora `STAGE_MODEL_CALLS` (`("performance", "actor")`, turnos y reflexiones) prueba
  primero la ranura de la función. El director, el casting, la narración y los constructores
  siguen en el modelo principal. `FailoverProvider` reordena las ranuras solo para esas
  llamadas y expone `stage_model_name`, así que `metadata.json` registra `stage_model` también
  con cadena.
- **Un modelo saturado espera 10 s, y al sexto 503 cede la llamada.** Cada 5xx espera
  `GEMINI_OVERLOAD_WAIT` (10 s) y reintenta en el mismo modelo, con una cuenta aparte de
  `GEMINI_MAX_RETRIES`. Al `GEMINI_OVERLOAD_ATTEMPTS`-ésimo (6), la llamada sale como
  `ProviderOverloadedError` y pasa al siguiente modelo sin marcar la ranura. Se retiran
  `CHAINED_SERVER_RETRIES` y `server_error_retries`. El borrador 7.12.2 esperaba 60 s × 10,
  hasta 9 minutos por llamada. Pero cada 503 cuenta como petición: el 13 de octubre,
  3.5 Flash-Lite agotó sus 500 diarias con 301 fallos y 199 éxitos.
- **La cita de un director casa con lo que leyó.** La transcripción pone el nombre del actor
  delante de la acción («Aleth se desliza»), y el director acorta citas con «[...]». El log
  guarda «Se desliza», así que 20 de 42 cláusulas mostradas se rechazaban.
  `stage/causality.py` acepta ahora las dos lecturas y los trozos literales en orden alrededor
  de una elipsis, con un mínimo de tres palabras.
- **El reparto del brief llega literal al diseñador de personajes y al casting.** Solo leían el
  resumen del analista, que conservó los nombres y tiró el resto. La astrónoma volvió como
  cirujana, el grumete de 14 años como artillero de 50 y todos los secretos declarados se
  cambiaron. `brief.authored_cast_block` añade el reparto declarado como canon. Sin brief, el
  prompt no cambia.
- **Lo que el reparto descubrirá no es un secreto de partida.** El casting de los navegantes
  dio a Teodoro, como secreto inicial, la medición del hundimiento que la trama tenía que
  juntar, y dejó `knowledge_gates` vacío. El casting recibe esa regla, y un reparto sin
  compuertas en un plan de varios capítulos deja `[CAST_NO_GATES]` en `metadata.json`.

## 7.12.1

Arreglos que salieron del primer run real de 7.12 (`20261013-125004-la-ciudad-perdida`, el
prompt de los navegantes, cancelado en la escena 1) y de su repetición. Sin cambios de
artefactos.

- **Un modelo saturado ya no frena la función.** Durante minutos `gemini-3.5-flash-lite` dio
  503 y 504 a 15 de 24 llamadas de la función mientras `gemini-3.1-flash-lite`, la siguiente
  ranura de la cadena, no recibía ninguna. Un 5xx que agota los reintentos es ahora
  `ProviderOverloadedError` (`PROVIDER_OVERLOADED`): `FailoverProvider` y `RoutedProvider`
  repiten esa llamada en la ranura siguiente sin marcar la primera, y si nadie responde el
  error sigue siendo degradable, no una cuota agotada. Una ranura con otra detrás reintenta
  un 5xx una sola vez (`CHAINED_SERVER_RETRIES`) en vez de agotar `GEMINI_MAX_RETRIES` con
  espera creciente, que costaba alrededor de un minuto por llamada; la última conserva todos.
- **Un 403 suelto ya no mata el run.** La repetición de los navegantes
  (`20261013-131347`) murió en la escena 5 con `PROVIDER_DAILY_QUOTA_EXHAUSTED` y 718
  peticiones libres: en plena tormenta de 503, los dos modelos dieron un 403 cada uno y la
  cadena los dejó fuera para todo el proceso, como al Groq bloqueado por red de 7.9.1. Una
  ranura que ya respondió en este proceso no es una clave bloqueada: su 403 mueve solo esa
  llamada y, si nadie la atiende, el error es degradable. Cuando todas rechazan el acceso, el
  mensaje ya no dice «cupo agotado».
- **La espera dice por qué espera.** Cada 503 salía como «Esperando cuota (reintento
  solicitado por Gemini)»; ahora «Esperando 3s: Gemini saturado (503)», «límite por minuto» o
  «fallo transitorio». `asg-generate` muestra el orden real de la cadena en vez de un
  «función: …» que con cadena no enruta nada, y solo enseña el prompt de ejemplo cuando se va
  a escribir uno.
- **El casting se repara sobre su propio candidato.** La corrección pedía una biblia nueva sin
  enseñar la rechazada: el segundo intento arregló las compuertas, dejó vacío el
  `public_face` de los ocho dossieres y pasó el `want` al inglés, y el run cayó al reparto
  derivado, sin compuertas. Casting y utilería reciben ahora el candidato rechazado, como el
  plan, y la corrección nombra cada campo vacío por dossier.
- Los mensajes de compuertas que se reinyectan dicen «works out» y «discovers», no
  «deductions» y «discoverys».
- **La revisión editorial define los dos códigos que bloquean.** En las revisiones 7.10 de los
  navegantes, la única `CONTRADICTION` era un cambio de presente a pasado, y entre los nueve
  `INVENTED_EVENT` había el viento en las jarcias, una descripción del cielo y uno que admitía
  que las acciones estaban en el log. Ahora el prompt dice que ambiente, detalle sensorial y
  motivo evidente no son sucesos, y que tiempo verbal, redacción u orden no son contradicción.
- **Un capítulo narrado en presente se reintenta.** El capítulo 2 del misterio del tren
  (`20261013-145340`) salió como transcripción en presente («—…—dice Inés» en cada línea) junto
  a un capítulo 1 en pasado, y la revisión no dio ningún hallazgo. `editorial_verdict` bloquea
  con `WRONG_TENSE` cuando en español las acotaciones en presente dominan a los pretéritos; de
  los 59 capítulos narrados del corpus solo marca ese. Agotados los intentos, se entrega el
  mejor, como cualquier otro bloqueo.
- La revisión editorial compara citas sin tropezar con «», ‘’ ni rayas de diálogo, y el
  narrador de respaldo ya no escribe «—¿Vienes?.».
- **El actor lee español con tildes.** El contexto del turno, la reflexión, las correcciones
  y las notas de reserva estaban escritos sin tildes («LO QUE QUIERES AQUI», «COMO ESTAS»,
  «Mirala hacia atras», «que has hecho», «CORRECCION»), y la reflexión es de donde sale la
  memoria en primera persona del personaje. También los avisos `BEAT_FORCED`,
  `NARRATION_FALLBACK` y `NARRATOR_FALLBACK`. Cambia el texto de esos prompts.
- «Lo que ya decidiste sigue vigente… no repitas la misma conversación» ya no llega al actor
  que abre su primera escena: solo cuando ha movido en ella o trae un compromiso o una versión
  de escenas anteriores.
- El detector de idioma cuenta las formas acentuadas («más», «está», «él»), que antes no
  sumaban como español.
- El analista conserva entre paréntesis la palabra de la persona para cada papel que nombra:
  «la revisora Inés Robles» pasó por «conductor» y volvió como «Jefa de tren» (TD-2).
- Personajes: los títulos y rangos inventados también van en el idioma de la ficción
  («Warden» llegó al reparto y a un título de capítulo), un pueblo inventado tiene nombres
  propios y ningún personaje lleva el de una figura histórica real (salieron Rodrigo de Triana
  y Hernando de Alarcón).

## 7.12.0

Pipeline 7.12. Responde a los primeros lectores de fuera del proyecto (11 runs 7.10 de
`Stories/Stagecraft/20261011-*` y `20261012-*`): «lenguaje super rebuscado», nombres en cada
línea y un run muerto en la etapa del mundo.

- **Un capítulo narrado ya no cae al respaldo por la revisión.** En 7.10, 7 de 14 capítulos
  simulados salieron del narrador determinista, frente a 0 de 50 antes de existir la revisión;
  la historia de los navegantes, entera. Ahora una cita que no está en el texto se descarta en
  vez de lanzar, solo `INVENTED_EVENT` y `CONTRADICTION` bloquean, una revisión que no puede
  correr acepta el capítulo (`NARRATION_REVIEW_UNAVAILABLE`) y, agotados los intentos, se
  entrega el de menos hallazgos (`NARRATION_BEST_ATTEMPT`). Las marcas `[clave]` y
  `[X piensa:` se limpian en vez de rechazar. `narration.json` pasa al contrato 4.
- **El respaldo se lee como prosa:** un párrafo por turno, nombre completo solo la primera vez,
  «piensa» con el pensamiento en cursiva y sin pensamientos en otro idioma. El log que lee el
  narrador usa los nombres igual.
- **Contrato de estilo** (`agents/style.py`) para Drafter, Writer y Narrator: prosa clara, sin
  repetir nombres, sin coletillas que expliquen la emoción y sin símiles encadenados.
- **`style_request`** en `request.json`: el registro que pidió la persona, literal y sin
  traducir, llega como instrucción a quien escribe y al crítico. «Historia corta», «breve» o
  hasta 1.500 palabras pedidas fuerzan el perfil Esencial.
- **Las observaciones de oficio llegan siempre al Writer.** Nombre repetido en frases seguidas,
  coletillas y símiles (`asg_core.readability_signals`) se suman a las de diálogo y párrafos, y
  cada capítulo observado recibe una nota aunque el crítico no dé ninguna (TD-1, TD-3).
- **Mundo y personajes** escriben nombres, roles y voz en el idioma de la ficción y evitan los
  nombres de siempre (TD-2, TD-7). Los ids casi válidos («Sala Del Trono») se normalizan
  (`ModelId`), la etapa del mundo reintenta y la corrección estructurada cita el valor
  rechazado.
- **La función:** el actor piensa en el idioma de la ficción (`WRONG_LANGUAGE`); dos personajes
  que repiten táctica uno frente a otro adelantan el giro del director una vez por beat
  (`policy.is_deadlocked`), y el director orienta sus notas al género pedido.
- **`GEMINI_PROSE_MODEL`** (opcional): la prosa que lee el lector puede ir a un modelo mejor,
  con su propio tope diario, y vuelve al principal al agotarse. `RoutedProvider` ya no tumba un
  run cuando el modelo de la función rechaza el acceso o se queda sin cuota.
- El bot cierra como fallido el run que un reinicio dejó en `running`.

## 7.11.0

Pipeline 7.11, limpieza para el cierre.

- Un run nuevo ya no escribe la plantilla `evaluation.json` de la evaluación 1-10 heredada: la
  evaluación de la tesis son los pares a ciegas de `asg-evaluation` 2.0.
- Se retiran `compare-story-runs` (StageCraft ya compara runs), `audit-stage-run` (el juez LLM
  que aprobaba casi todo, TD-1) y `plan-guidance-experiment`; las solicitudes de
  `experiments/guidance/` se conservan como datos.
- `extract-story-features --study` lee el estudio nuevo y pide que la votación esté abierta.

## 7.9.1

- **La cadena salta una ranura que rechaza el acceso.** Groq contesta 403 «Access denied.
  Please check your network settings.» a las redes que bloquea, y la cadena solo saltaba ante
  un 429 diario: el run moría en Groq con Mistral sin probar. Ahora un 401 o un 403 de
  cualquier proveedor es `ProviderUnavailableError` (`PROVIDER_UNAVAILABLE`), y
  `FailoverProvider` deja esa ranura fuera durante el resto del proceso. El libro de cuotas no
  se entera, porque una red o una clave se arreglan antes de que acabe la ventana del
  proveedor. Si ninguna ranura responde, el error dice cuáles rechazaron el acceso.

## 7.9.0

Pipeline 7.9. Arregla los defectos deterministas de la función que salieron de la validación
real 7.8 (`20261009-184753` y `20261009-185923`).

- **Las compuertas obligatorias casan por clave, no por texto (SIM-17).** `_derive` compara las
  cláusulas del director con las congeladas por texto exacto, por texto normalizado y, en una
  compuerta, por su id o por su hecho sin el sufijo «(how, nombre)». Una cláusula que repite
  una compuerta se funde con ella al congelar, y una cláusula ajena ya no deja el beat abierto
  para siempre. Antes, 6 de 6 beats con compuertas se forzaban aunque el director las diera por
  mostradas.
- **El contexto del actor ya no lleva ids ni frases rotas (SIM-18).** Las relaciones de la
  reflexión se resuelven contra el reparto con `resolve_character` y sustituyen a la del
  casting. La línea de estado usa etiquetas («Te sientes: …. Cambiarías de idea si: …») en vez
  de frases con género y conectores duplicados.
- **El director escribe en el idioma de la ficción (SIM-2).** Las notas y las cláusulas dejan
  de pedirse en inglés, y `CODA_NOTE` y `FALLBACK_TURN_NOTE` pasan a español. La nota de
  reserva ya no mete el id ni el sufijo de una compuerta. Al abrir un beat, el director
  reescribe en español el objetivo de cada actor (`BeatDirection.objectives`), que el
  Dramaturgo escribe en inglés y un replay conserva.
- **Una forma con una sola corrección se repara en vez de saltar el turno (SIM-16).**
  `repair_form` recorta una réplica larga en el último final de frase que cabe y pasa
  `mi`/`mis`/`conmigo` de una acotación a tercera persona. Lo que no se puede reparar se sigue
  rechazando. `performance.json` contrato 5: cada turno guarda sus `repairs`, y
  `simulation_metrics.json` gana `form_repairs`, que vale `None` en contratos anteriores.

## 7.8.3

- **La cuota del día se comprueba antes de lanzar (cierra MED-1).** `generate-story` estima las
  llamadas y los tokens de una historia del formato pedido con la media de sus últimos runs
  completados. Si lo que queda en las ranuras con tope no alcanza, se niega a arrancar con
  código 3 y dice cuándo vuelve la cuota. `--force` la lanza igual. Sin runs de ese formato, o
  con una ranura sin tope conocido, no se niega: la API sigue siendo la autoridad.
- **Sin `ASG_LLM_CHAIN`, el libro de cuotas también cuenta.** El `GeminiProvider` principal, y
  el de la función si tiene modelo propio, apuntan cada intento en `.cache/llm_budget.sqlite3`.
  Un 429 diario deja la ranura fuera hasta su reinicio, no los ~55 s de `retry_delay` que manda
  Gemini. Así `llm-budget` y `audit-stage-run`, que antes gastaban sin dejar rastro, entran en
  el presupuesto.
- `tools/budget.slot_spending` es el estado de cada ranura que comparten el panel y la
  comprobación previa. `average_story` admite un formato.
- `_RecordingProvider` tiene constructor propio y los proveedores ya no leen su configuración
  con `getattr` por si un test se saltaba `__init__` (ING-6). `format_progress` vive en
  `asg_core` (exige `asg-core>=0.7.0`) y se reexporta.

## 7.8.2

- Preserve explicit facts and uncertainty in analyst extraction; verify the draft against the original in a second extraction call and keep inventions in optional creative directions.
- Repair retrieval constraint errors with contextual diagnostics and persist rejected structured drafts.
- Abstain without a composition call when semantic retrieval fails; lexical matches no longer decide v2 rankings.

## 7.8.1

- El esquema enviado al modelo exige `connection` no vacío en cada selección nueva. Los
  blueprints v2 anteriores siguen siendo legibles, incluso con conexión principal vacía.
- La reparación contextual incluye el borrador rechazado y localiza el campo que debe corregirse.


## 7.8.0

- Guía experimental `compositional_v2` en dos etapas: recuperación semántica validada y
  composición contextual con abstención y reparación acotada. `hybrid_v1` sigue por defecto.
- Catálogo de 34 patrones externalizado sin cambiar contenido ni orden; roles independientes.
- Artefactos `narrative_retrieval.json` y blueprint v2 con instantánea, hash y bloques exactos
  para personajes y planificación. Lectura de contratos anteriores conservada.
- CLI `--guidance-strategy` y `--no-narrative-guidance`; comparación distingue estrategias.
- `plan-guidance-experiment` prepara 9 o 36 trabajos emparejados sin llamar al proveedor.


## Sin publicar: herramientas de evaluación

- `extract-story-features` conecta el proveedor configurado con el extractor independiente;
  admite historias individuales, lotes y textos congelados del estudio, además de `--dry-run`.
- `generate-baseline` prepara una generación directa de una sola llamada, con procedencia y consumo.
- No se cambia el pipeline ni la simulación ni se genera el corpus experimental.

## 7.7.1

- `llm-budget` es un panel de cuotas: totales por proveedor (Gemini suma el cupo de sus dos
  modelos), desglose por modelo con tokens, RPM y estado, y cuántas historias caben con la media
  de los últimos runs. Lo gastado sale del libro y de los `llm_calls.jsonl` de los runs, así que
  también cuenta los runs hechos sin cadena. Funciona con o sin `ASG_LLM_CHAIN`.
- `GEMINI_DAILY_REQUESTS` vale 500 por defecto, por modelo.
- Con cadena, todas las llamadas (también las de la función) siguen un solo orden: el modelo
  principal de Gemini, después `GEMINI_STAGE_MODEL`, después Groq y Mistral.

## 7.7.0

Una cadena de proveedores para que el cupo gratuito de Gemini no corte los lotes.
`ASG_LLM_CHAIN=gemini,groq,mistral` ordena los proveedores; cuando uno agota su cupo diario o
mensual, la llamada en curso se repite en el siguiente y el run sigue. Sin la variable no cambia
nada: el mismo proveedor, los mismos prompts y ningún libro.

- **Proveedor OpenAI-compatible** (`OpenAICompatibleProvider`, sobre httpx) para Groq y Mistral:
  la salida estructurada pide `json_schema` y, si el modelo la rechaza, repite en `json_object`
  con el esquema en la instrucción de sistema. Comparte con `GeminiProvider` una base que
  reintenta, valida y registra cada llamada.
- **Libro de presupuesto** (`runtime/budget.py`): SQLite en `.cache/llm_budget.sqlite3`, seguro
  entre procesos. Cuenta peticiones y tokens por ranura (proveedor y modelo) y ventana (día del
  Pacífico para Gemini, día UTC para Groq, mes para Mistral), y recuerda la ranura que un 429
  declaró agotada hasta su reinicio, para no gastar otra petición en descubrirlo. Los topes son
  configuración. `llm-budget` lo muestra.
- **`metadata.json` añade `models_used`**: los modelos que contestaron alguna llamada. Un run que
  saltó de proveedor queda con el eje `model` compuesto en `evaluation/pairing.py` y nunca se
  empareja con uno de un solo modelo. `PIPELINE_VERSION` pasa a 7.7; las anteriores se siguen
  abriendo.
- `ProviderDailyQuotaError` (`PROVIDER_DAILY_QUOTA_EXHAUSTED`) es la cuota agotada de cualquier
  proveedor; `GeminiDailyQuotaError` hereda de él y conserva su código.

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

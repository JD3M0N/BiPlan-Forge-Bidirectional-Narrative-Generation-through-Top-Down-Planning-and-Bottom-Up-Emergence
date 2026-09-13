# Hoja de ruta

**Estado medido el 2026-09-13 sobre `98a9a1b` más el registro de la artesanía narrativa de
`asg-top-down` 6.5.0.** Puerta de calidad limpia: `ruff check .`, `ruff format --check .`
(124 archivos), 258 pruebas pasan y 2 se omiten, `pip check` sin requisitos rotos, y
`tests/test_sync_railway_stories.ps1` pasa. Las cinco corren ahora en
`.github/workflows/quality.yml` en cada push y pull request. Las mediciones que cita este documento
salen del corpus de `Stories/`, hoy 137 ejecuciones Top-Down; de las 104 historias con `story.md`,
101 tienen `evaluation.json` y una sola tiene puntuaciones reales, medido con `report-evaluations`.
Las cifras de prosa —diálogo, palabras por frase y palabras por párrafo— salen de
`report-story-craft` sobre las 74 historias de versión 6 en adelante, 72 de ellas terminadas, y
están documentadas en [docs/artesania_narrativa.md](docs/artesania_narrativa.md), que incluye la
matriz de 9 historias con Gemini real (catálogos 4, 6 y 7 por los tres perfiles) que fija la línea
base de 6.5.0.

## Cómo leer esto

Las tareas van en tres secciones según lo que hace falta para moverlas, y dentro de cada una el
orden de la lista es el orden sugerido. No hay etiquetas de prioridad.

- **Lo siguiente** — listas para empezar hoy. Nada bloquea su arranque.
- **Pendiente** — acordadas, pero no ahora. Suben a «Lo siguiente» cuando se libere hueco.
- **Ideas** — sin decidir. Hay que medir o investigar antes de comprometerse.

Cada tarea tiene el mismo esqueleto: **Síntoma** es lo que se observa y cómo se comprobó, **Qué
hacer** es la acción concreta, y **Hecho cuando** es una condición que se puede verificar. Se
citan rutas de archivo, no números de línea: las líneas se mueven y el documento envejece mal.

---

## Lo siguiente

### El gate de documentación pasa en vacío

- **Síntoma.** `PRODUCTION_ROOTS` y el glob de `tests/test_source_documentation.py` se resuelven
  contra el directorio de trabajo. Comprobado: lanzado desde `packages/` el test ve **cero
  archivos** y pasa. Su marcador `"configuraci?n"` es mojibake y no puede coincidir nunca, y el
  filtro que de verdad impone inglés es `not docstring.isascii()`. Y como solo exige que exista
  texto ASCII, aprueba **142 de 585** definiciones cuyo docstring es plantilla vacía, del tipo
  «Represent X data and behavior.» o «Mark the requested value.»; los peores son errores, esquemas
  y almacenamiento.
- **Qué hacer.** Pasar la comprobación a las reglas `D` de Ruff, que no dependen del directorio de
  trabajo, y dejar el test a mano solo para el idioma si hace falta. Luego reescribir los
  docstrings plantilla, empezando por `errors.py`, `schemas.py` y los dos `storage.py`.
- **Hecho cuando.** El gate detecta lo mismo desde cualquier directorio y no queda ningún docstring
  que se limite a repetir el nombre de la función.

### Recuperar las ejecuciones varadas en `running`

- **Síntoma.** Cuatro runs del corpus quedaron en `running` para siempre. Dos de ellos tienen
  `story.md` completo, uno con métricas de 1674 palabras y seis eventos, pero `StoryRun` se niega a
  abrir un run incompleto, así que son datos de la tesis inaccesibles. `complete_stage` escribe
  checkpoints que nadie lee para reanudar.
- **Qué hacer.** Decidir primero si merece la pena reanudar desde checkpoint. Si no, dar una
  transición explícita para cerrar o descartar un run interrumpido, y recuperar los cuatro que ya
  existen.
- **Hecho cuando.** Ningún run queda bloqueado indefinidamente, los cuatro varados están
  resueltos, y hay test de la transición.

### El pipeline resume en vez de dramatizar

- **Síntoma.** Medido con `report-story-craft` sobre las historias 6.x del corpus: mediana de
  31% de párrafos con alguna marca de diálogo, y **ocho historias sin una sola marca**. Las
  cifras ya se registran en `story_metrics.json` desde 6.5.0, pero ningún agente las ve: el
  prompt del escritor pide prosa y el del crítico dramático juzga el borrador sin ninguna
  evidencia de si hay escena o sólo sinopsis.
- **Qué hacer.** Pedir escena dramatizada en la guía de prosa del escritor, y dar al crítico
  dramático la artesanía como evidencia **cualitativa**, derivada de umbrales y sin cifras en el
  prompt: `profiles.py` documenta por qué un número dentro del prompt gana a los demás.
- **Hecho cuando.** La matriz de nueve historias de 6.5.0 (catálogos 4, 6 y 7 por los tres
  perfiles, en `docs/artesania_narrativa.md`) se repite sobre la versión nueva y la proporción
  de diálogo sube sin que caigan coherencia ni satisfacción.

---

## Pendiente

### Párrafos-bloque de hasta doscientas palabras

- **Síntoma.** Mediana de 82 palabras por párrafo en las historias 6.x, con casos de 152 y 197
  —`20260911-174447-la-sombra-del-volcan` y `20260903-172904-el-dominio-del-mesozoico`—. Un
  párrafo de doscientas palabras no es un párrafo: es un capítulo sin cortar, y coincide con las
  historias sin diálogo.
- **Qué hacer.** Acotar cualitativamente la longitud de párrafo en la guía de prosa, junto a la
  petición de escena, y comprobar si el corte de párrafo arrastra al diálogo o es independiente.
- **Hecho cuando.** `words_per_paragraph` baja de la banda de 150+ en todo el corpus nuevo y se
  sabe, con datos, si diálogo y longitud de párrafo son la misma señal o dos.

### El perfil Esencial dramatiza la mitad que Desarrollada

- **Síntoma.** 21% de párrafos con diálogo en Esencial frente al 40% de Desarrollada y el 32% de
  Expansiva, sobre 23, 16 y 26 historias. Esencial no es sólo más corta: es la que menos escena
  escribe, y su `PROFILE_GUIDANCE` pide economía sin distinguir entre resumir y condensar.
- **Qué hacer.** Revisar el contrato de Esencial para que la economía no se pague en escena, y
  medir si la diferencia sobrevive cuando el escritor recibe la petición de dramatizar.
- **Hecho cuando.** Está escrito si la brecha es del perfil o del prompt, y Esencial deja de ser
  el perfil con menos diálogo por construcción.

### Completar las variantes por perfil del catálogo de prompts

- **Síntoma.** Sólo los catálogos 4, 6 y 7 de `docs/prompts_top_down.md` tienen variantes
  Esencial/Desarrollada/Expansiva. En los otros cuatro el perfil viene escrito en el texto, así
  que una matriz por perfil obliga a forzar `--profile` contra un prompt que dice otra cosa, y el
  analista ya derivó sus `creative_directions` de la palabra equivocada.
- **Qué hacer.** Dar variantes por perfil a los prompts 1, 2, 3 y 5, con el mismo patrón de texto
  idéntico salvo la palabra del perfil.
- **Hecho cuando.** Cualquier prompt del catálogo se puede correr en los tres perfiles sin
  contradicción entre el texto y `--profile`.

### `failed_calls` y `duration_seconds` miden otra cosa de la que dicen

- **Síntoma.** `_record_failure`, en `provider.py`, emite un registro por **cada intento** fallido,
  incluidos los reintentos transitorios que después tienen éxito, así que `failed_calls` cuenta
  intentos y no llamadas perdidas. Y `started` no se reinicia entre intentos, de modo que
  `duration_seconds` incluye los intentos fallidos y las esperas de cuota: no es latencia. Un run
  del corpus aparenta 17 fallos sobre 32 llamadas sin haber perdido necesariamente ninguna.
- **Qué hacer.** Separar intentos de llamadas en el artefacto de uso, y medir la latencia del
  intento que tuvo éxito.
- **Hecho cuando.** Las dos cifras significan lo que su nombre dice, y ningún resultado de la tesis
  las cita mal.

### Trazabilidad del fallo del analista y errores de cuota tragados

- **Síntoma.** `_analyze_request` corre fuera del `try` de `execute`, y `_record_failure` empieza
  por `assert self.repository is not None`. Si la primera llamada falla no se crea directorio, no
  se escribe `error_report.json` y no queda registro de uso: es la única etapa sin trazabilidad.
  Por separado, el ranking semántico de `skeleton_match.py` tiene un `except Exception: return
  None` que anula el guardia `NON_DEGRADABLE_ERRORS`, así que un error de cuota diario se convierte
  en «sin evidencia semántica» y el run sigue gastando llamadas hasta abortar más tarde. Existe un
  fixture para probarlo que ningún test usa.
- **Qué hacer.** Crear el repositorio antes de analizar, o registrar el fallo de análisis por otra
  vía. Y dejar pasar los errores no degradables en el ranking semántico.
- **Hecho cuando.** Un fallo en la primera llamada deja un `error_report.json`, y un error de cuota
  durante el ranking aborta el run en ese punto. Con test en ambos casos.

### Equiparar los artefactos Bottom-Up con los Top-Down

- **Síntoma.** El Bottom-Up no escribe métricas de historia, ni versión del generador, ni
  manifiesto con SHA-256, ni registro de llamadas o de uso, ni taxonomía de errores, ni perfil
  narrativo. Ninguno de los ejes sobre los que está calibrado el Top-Down existe del otro lado, y
  los lotes no producen `story.md` ni `evaluation.json`, así que ninguna corrida de lote es
  evaluable. El desequilibrio se ve en los datos: 2 ejecuciones y 3 lotes, todos de julio, frente a
  121 ejecuciones Top-Down repartidas en seis versiones del generador.
- **Qué hacer.** Dar al Bottom-Up el mismo conjunto mínimo de artefactos: métricas de historia,
  versión, manifiesto y códigos de error. Reusar lo que ya existe en `asg_core` en vez de
  duplicarlo; la artesanía de la prosa sale gratis llamando a `asg_core.craft_metrics`, y
  `report-story-craft` ya mide cualquier `story.md` de los dos enfoques.
- **Hecho cuando.** Un lector común puede abrir un run de cualquiera de los dos enfoques y obtener
  las mismas cifras, y un lote produce historias evaluables.

### Dos agentes pueden acabar en la misma celda

- **Síntoma.** `_move`, en `packages/escape_room/src/asg_escape_room/actions.py`, deja entrar en
  una casilla ocupada si el ocupante propuso moverse. Si ese movimiento se rechaza después, por
  pared o por conflicto, los dos quedan superpuestos. La misma condición permite que dos agentes se
  atraviesen intercambiando posiciones. Es alcanzable porque la política planifica sobre celdas
  desconocidas y propone rutinariamente pasos contra paredes no descubiertas. No hay ningún test de
  esa invariante.
- **Qué hacer.** Resolver los movimientos de forma que liberar una celda dependa de que el
  movimiento del ocupante se haya aceptado, e impedir el intercambio directo.
- **Hecho cuando.** Ningún tick deja dos agentes en la misma posición ni permite un intercambio, y
  hay test que reproduce la traza concreta.

### Sacar las aserciones de prompt literal de los tests

- **Síntoma.** `packages/top_down/tests/test_generator_v5.py` contiene más de 60 aserciones sobre
  el texto literal de los prompts de sistema. Cualquier reescritura de un prompt rompe tests que no
  tienen nada que ver con lo que se cambió, y reescribir prompts es el trabajo central de la tesis.
  Peor, `test_the_story_plan_is_written_from_a_single_guarded_site` lee el código fuente como texto
  y lo parte por el nombre del método con su indentación exacta, así que es lo primero que se
  rompe al dividir `pipeline.py`. El doble de proveedor también parsea el prompt del escritor para
  extraer el cuerpo original.
- **Qué hacer.** Expresar cada aserción como comportamiento observable en vez de subcadena. Donde
  el contenido del prompt sea de verdad el contrato, concentrarlo en pocos tests declarados como
  tales.
- **Hecho cuando.** Reescribir un prompt de sistema solo rompe los tests que verifican ese prompt.

### Dividir `pipeline.py`

- **Síntoma.** 1149 líneas y 56 métodos en una sola clase, mezclando orquestación, reintentos,
  validación, ensamblado de Markdown, prompts de reparación y telemetría. El campo `repository`
  opcional obliga a 17 `assert self.repository is not None` repartidos por la clase.
- **Qué hacer.** Empezar por las tres extracciones de riesgo nulo, que son métodos estáticos puros
  y se mueven literalmente: los prompts de reparación, el ensamblado de Markdown y las reglas de
  aceptación del escritor. Son unas 250 líneas. Después la telemetría y la contabilidad de uso como
  colaboradores, y solo al final las etapas como clases con estado propio, que es lo que elimina
  los asertos.
- **Hecho cuando.** Plan, borrador y revisión son unidades con test propio, el estado deja de
  pasarse como parámetros posicionales, y los artefactos generados no cambian.

### Arreglar los experimentos del escape room

- **Síntoma.** `run_batch` fija a mano dos y tres agentes y treinta semillas, ignorando `--seed` y
  `--agents`: el usuario cree haber configurado el experimento y no lo hizo. `save_batch` nombra el
  directorio con resolución de segundos y `exist_ok=True`, así que dos lotes seguidos se
  sobrescriben en silencio, y revienta con `IndexError` si la lista viene vacía. Los artefactos del
  Bottom-Up además se escriben sin atomicidad, mientras `asg_core.atomic_write_text` ya existe y el
  Top-Down sí lo usa. El directorio del experimento solo guarda los dos CSV: ni mapa, ni límite de
  ticks, ni versión, así que un lote no es reproducible.
- **Qué hacer.** Respetar las banderas o rechazarlas explícitamente, usar el mismo sufijo
  anticolisión que el repositorio de runs, escribir de forma atómica, y guardar la configuración
  junto a los CSV.
- **Hecho cuando.** Dos lotes seguidos conviven, un lote declara cómo reproducirlo, y ninguna
  interrupción deja un JSON truncado.

### Persistencia real de lo desplegado y techos en las dependencias

- **Síntoma.** El `Dockerfile` no declara ningún `VOLUME` y la cola SQLite vive en `/app/Stories`,
  que se pierde en cada redeploy; `sync-railway-stories.ps1` existe solo para rescatar las
  historias antes, con 713 líneas y un único `try` de 222. Por separado, `google-genai>=1.0` y
  `pydantic>=2.7` no tienen techo, igual que `pytest` y `ruff`, y no hay lockfile: una release mayor
  rompe el pipeline sin aviso.
- **Qué hacer.** Montar un volumen para la cola y las historias, y poner techo de versión mayor a
  las cuatro dependencias abiertas.
- **Hecho cuando.** Artefactos y cola sobreviven a un redeploy sin intervención, el script queda
  como herramienta de archivado opcional, y una release mayor no entra sin que alguien lo decida.

### Resolver las abstracciones que no sostienen nada

- **Síntoma.** `ArtifactValidationError` no se lanza en ningún `src/` del monorepo; solo la usan dos
  tests de Telegram como doble genérico. Los kwargs `structured_validation_retries` y
  `generation_profiles` de `provider.py` no tienen ni un llamador. `ChapterPlan` es una subclase sin
  campos propios usada como tipo en doce sitios de producción y exportada públicamente.
  `topological_order` se serializa en cada plan y es derivable: comprobado sobre los planes del
  corpus, **en 71 de 71** coincide exactamente con ordenar los eventos por su campo `order`, que es
  lo que ya garantizan los invariantes del grafo.
- **Qué hacer.** Decidir caso por caso: eliminar con migración, o quedarse con una razón escrita.
- **Hecho cuando.** Cada caso tiene decisión tomada y, si se elimina, un test prueba que nada
  dependía de él.

### Subir a `core` lo que está duplicado

- **Síntoma.** El nombrado de directorio de run con sufijo anticolisión está copiado casi carácter
  a carácter entre los dos `storage.py`. El bloque `Settings` más `load_settings` con dotenv y
  `GEMINI_API_KEY` está en los dos `config.py`, incluido el literal del nombre del modelo. La
  consola reimplementa el cuerpo de `cli.run_one` del escape room, y ya divergen en cómo informan
  del audio. Además `find_project_root` deja que `ASG_PROJECT_ROOT` sobrescriba el argumento
  `start` en vez de usarlo como respaldo, así que los tests dependen del entorno.
- **Qué hacer.** Mover las tres utilidades a `asg_core` y que los dos paquetes las consuman.
  Arreglar la precedencia de `find_project_root`.
- **Hecho cuando.** No queda ninguna de las tres duplicaciones, y `find_project_root` respeta el
  argumento explícito.

### Las notas locales a un evento pueden inyectarse en todos los capítulos

- **Síntoma.** `_notes_for_chapter` trata como global cualquier nota sin `chapter_ids`, aunque
  tenga `event_ids`. El prompt del crítico pide precisamente citar los IDs de evento afectados al
  levantar una nota de ritmo, y le dice que deje `chapter_ids` vacío para las notas globales, así
  que la forma peligrosa es alcanzable. **Es latente, no observado:** de las 95 notas del corpus
  ninguna llegó a darse, porque el crítico siempre pone `chapter_ids` cuando pone `event_ids`.
- **Qué hacer.** Exigir que una nota global no tenga tampoco `event_ids`.
- **Hecho cuando.** Una nota con solo `event_ids` llega únicamente a los capítulos que contienen
  esos eventos, con test.

### La barra de progreso se pisa entre usuarios de Telegram

- **Síntoma.** `_refresh_queue` recorre todos los trabajos activos, incluido el que está generando,
  y reescribe su mensaje con el aviso estático de cola. Cuando otro usuario encola, quien está
  generando pierde su barra en vivo hasta la siguiente frontera de etapa, que en un run de cinco
  minutos puede tardar más de un minuto. El test que cubre el mensaje de progreso no ejerce
  concurrencia entre usuarios.
- **Qué hacer.** Saltar el trabajo en ejecución al refrescar la cola.
- **Hecho cuando.** Encolar una solicitud no altera el mensaje del trabajo que está corriendo, con
  test que use dos usuarios.

### Documentar los contratos públicos y rellenar el README

- **Síntoma.** `README.md` de la raíz está vacío, 0 bytes, y versionado. Las fachadas de los cuatro
  paquetes no tienen documentación con ejemplos que se ejecuten, y los READMEs de paquete mezclan
  español e inglés.
- **Qué hacer.** Cubrir las fachadas de `asg_core`, `asg_top_down`, `asg_evaluation` y
  `asg_escape_room` con ejemplos mínimos de entrada, salida y fallo. Escribir el README de la raíz
  en UTF-8.
- **Hecho cuando.** Los ejemplos se validan en los tests o en CI, y la documentación describe el
  contrato Top-Down 6.0 y su compatibilidad con runs anteriores.

---

## Ideas

### Probar si la taxonomía de arquetipos mejora las historias

El mecanismo está construido y es auditable: 34 esqueletos etiquetados por capa, ranking léxico
mezclado con una llamada semántica, y un `narrative_blueprint.json` por run. La ablación es limpia
desde la versión 6.3.0: con la guía apagada no se escribe artefacto y los prompts quedan idénticos
a la línea base. **El experimento sigue sin hacerse:** el único par con y sin guía es n=1 y anterior
a esa corrección. Comparar sobre los mismos prompts y medir originalidad, coherencia y satisfacción;
si hay mejora, se añade como brief opcional y auditable.

### Externalizar el catálogo de esqueletos

`skeletons.py` tiene 1490 líneas, de las que unas 1290 son las 34 entradas literales del catálogo;
la lógica real son unas 95. `PlotSkeleton` ya es un modelo Pydantic y el validador que corre al
importar ya trata el catálogo como datos externos, así que cargarlo desde JSON es casi mecánico y
permitiría editar el corpus de la tesis sin tocar Python. Se pierde el chequeo en tiempo de edición;
se gana un diff limpio al añadir esqueletos.

### Hacer que los puzzles del mapa dejen de ser decorativos

`contracts.py` valida la sección `puzzles` con detección de ciclos y referencias, pero ninguna línea
de `actions.py` la lee: los cuatro acertijos están codificados a mano, igual que los identificadores
`battery`, `flashlight` y `lever`, de modo que cualquier mapa nuevo debe reusarlos. El número de
agentes que exige un puzzle, el cierre de una feature y el rol de cada agente tampoco se leen nunca.
Mientras siga así, la simulación admite variaciones de plano pero no de contenido.

### Reescribir el narrador de respaldo y cortar el spam de comunicación

Medido sobre una corrida propia de 126 turnos con dos agentes: el `story.md` de respaldo tiene 52
líneas de contenido, de las que **46 son las dos mismas frases repetidas 23 veces cada una**, y
mezcla español con identificadores en inglés («B recogió flashlight.»). El título está fijo y miente
en cualquier mapa que no sea el de la linterna. La causa está en la política, que dispara la
comunicación en cuanto cambia el snapshot de creencias, y ese snapshot incluye las celdas conocidas,
así que cualquier movimiento lo invalida. Los mismos agentes replanifican 91 y 93 veces en 126
turnos.

### Unificar los contratos de prompt duplicados

La regla «cada evento debe cambiar conflicto, conocimiento, relaciones, recursos, riesgos o
consecuencias» está escrita casi literal cuatro veces: dos en `profiles.py`, una en `planner.py` y
una en `pipeline.py`. La de rama y reunión causal, tres veces. Y los alias de perfil están
duplicados carácter a carácter entre `agents/analyst.py` y `apps/telegram/src/asg_telegram/prompts.py`,
sin que `profiles.py` exponga ningún mapa que pudieran compartir. Cerrarlo daría además una
detección de perfil consistente entre la consola, el bot y el analista.

### Grafo explícito de lugares

Comparar el modelo actual de `locations` y `location_id` contra relaciones y transiciones
explícitas, documentando el efecto en errores de continuidad y en coste de generación. Adoptarlo
solo si mejora algo medible.

### Benchmark narrativo repetible

Los prompts canónicos ya existen y las métricas automáticas dan la parte objetiva; falta el
procedimiento y el recolector que permitan comparar dos versiones del generador bajo las mismas
condiciones, guardando lo necesario para repetir el experimento.

### Cerrar los huecos de cobertura

`policy.py` del escape room, con 283 líneas, no tiene ni un test directo: solo se ejercita de
rebote. `progress.py` del Top-Down no tiene ninguno. El `storage.py` del Top-Down tiene uno solo, y
ni los hashes del manifiesto, ni `register_existing`, ni la rama de `fail` con un error no
clasificado se comprueban. Tampoco `collect_metrics`, `result_row`, `save_batch` ni `run_batch`.


 - hacer un make test para correr los test automaticos
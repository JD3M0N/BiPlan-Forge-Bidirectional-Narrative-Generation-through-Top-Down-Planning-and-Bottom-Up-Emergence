# Hoja de ruta

**Estado medido el 2026-09-21 sobre `8232110`, con `asg-top-down` 6.7.0.** Puerta de calidad
limpia: `ruff check .`, `ruff format --check .`, 304 pruebas pasan y 2 se omiten, `pip check` sin
requisitos rotos, y `tests/test_sync_railway_stories.ps1` pasa. Las cinco corren en
`.github/workflows/quality.yml` en cada push y pull request, y en local con `.\quality.ps1` (o
`make test`). Las mediciones que cita este documento salen del corpus de `Stories/`, hoy **160
ejecuciones Top-Down** —119 `completed`, 41 `failed` y **ninguna varada en `running`**— más 6
Bottom-Up; de las 128 historias, 125 tienen `evaluation.json` y una sola tiene puntuaciones reales,
medido con `report-evaluations`. Las cifras de prosa —diálogo, palabras por frase y palabras por
párrafo— salen de `report-story-craft` sobre las 97 historias de versión 6 en adelante, 96 de ellas
terminadas, y están documentadas en [docs/artesania_narrativa.md](docs/artesania_narrativa.md), que
enfrenta la línea base 6.5.0 con la intervención 6.6.0 sobre los mismos prompts (catálogos 4, 6 y 7
por los tres perfiles) y añade una réplica de doce historias del 2026-09-17 sobre 6.6.0 sin tocar
nada: esa réplica es el suelo de ruido con el que hay que leer cualquier diferencia. **Una
diferencia de medianas menor de unos cinco puntos, con n=9, no se puede interpretar.**

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

### El desenlace sigue resumiendo

- **Síntoma.** Sobre las 21 historias de 6.6.0 —la matriz del 13-09 y su réplica de doce del
  17-09— el último capítulo dramatiza al 41% frente al 50% del primero, y es el capítulo más mudo
  de su historia en 13 de las 21. La cláusula «un desenlace es una escena» está en el prompt del
  Drafter y no basta: el modelo cierra resumiendo cómo acabaron las cosas. El decaimiento se redujo
  respecto de 6.5.0 y **replica en los dos lotes**, así que no es ruido. Medido en
  `docs/artesania_narrativa.md`.
- **Qué hacer.** Tratar el último capítulo como caso propio en vez de endurecer el contrato para
  todos: el Drafter ya sabe qué capítulo escribe y en qué posición, así que puede recibir la
  exigencia de desenlace dramatizado sólo donde hace falta.
- **Hecho cuando.** El último capítulo deja de ser el más mudo en la mayoría de las historias de una
  matriz nueva. La mediana sola no sirve de criterio: la réplica midió hasta 16 puntos de diferencia
  entre dos corridas del mismo prompt y la misma versión.

### El Writer acepta una revisión que no repara el déficit que la pidió

- **Síntoma.** El canal de `craft_evidence` se tensó por primera vez el 2026-09-20 en
  `20260920-135822-el-computo-de-la-deriva`, y lo recorrió entero: `chapter_1` salió con
  `dialogue_ratio` 0,1765, el crítico levantó las dos notas que pide su prompt —`voice_style` y
  `pacing`, sobre ese capítulo y sólo ése— y el Writer reescribió el capítulo de 424 a 589
  palabras, aceptado al primer intento. **Y el `dialogue_ratio` quedó en 0,1765, exactamente el
  mismo**, con las palabras por párrafo subiendo de 24,9 a 34,7: las 165 palabras añadidas fueron
  narración, no escena. `_writer_candidate_issue` sólo rechaza cuerpo vacío, encabezados Markdown y
  texto idéntico; nunca comprueba que el déficit que originó la nota se haya reparado. Medido en
  [docs/artesania_narrativa.md](docs/artesania_narrativa.md).
- **Qué hacer.** Pasar las observaciones del capítulo, que `_critique_and_revise` ya calcula, hasta
  `_revise_one_chapter`, y si la misma observación sobrevive al primer candidato usarla como
  `RETRY CORRECTION` del segundo. **Rechazo blando, no duro:** tras dos rechazos el método devuelve
  hoy `draft_body`, o sea el borrador degradado, así que un rechazo duro entregaría un texto peor
  que la revisión que acaba de descartar; hay que devolver el mejor candidato, nunca el borrador. El
  feedback nombra la observación, jamás una cifra: `test_no_measurement_ever_reaches_the_prompt`
  existe para eso.
- **Hecho cuando.** Una reescritura pedida por una nota de artesanía que no mueve la observación se
  reintenta, el capítulo entregado nunca es el borrador degradado, y hay test del camino. Que el
  cambio además mejore la prosa sólo se puede afirmar con una matriz nueva, que gasta cuota.

---

## Pendiente

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

### Equiparar los artefactos Bottom-Up con los Top-Down

- **Síntoma.** El Bottom-Up no escribe métricas de historia, ni versión del generador, ni
  manifiesto con SHA-256, ni registro de llamadas o de uso, ni taxonomía de errores, ni perfil
  narrativo. Ninguno de los ejes sobre los que está calibrado el Top-Down existe del otro lado, y
  los lotes no producen `story.md` ni `evaluation.json`, así que ninguna corrida de lote es
  evaluable. El desequilibrio se ve en los datos: 6 ejecuciones y 3 lotes frente a 160 ejecuciones
  Top-Down repartidas en siete versiones del generador.
- **Qué hacer.** Dar al Bottom-Up el mismo conjunto mínimo de artefactos: métricas de historia,
  versión, manifiesto y códigos de error. Reusar lo que ya existe en `asg_core` en vez de
  duplicarlo; la artesanía de la prosa sale gratis llamando a `asg_core.craft_metrics`, y
  `report-story-craft` ya mide cualquier `story.md` de los dos enfoques. La escritura atómica de
  los lotes ya pasa por `asg_core.atomic_write_text`; el resto de `storage.py` sigue sin ella.
- **Hecho cuando.** Un lector común puede abrir un run de cualquiera de los dos enfoques y obtener
  las mismas cifras, y un lote produce historias evaluables.

### Sacar las aserciones de prompt literal de los tests

- **Síntoma.** `packages/top_down/tests/test_generator_v5.py` contiene más de 60 aserciones sobre
  el texto literal de los prompts de sistema. Cualquier reescritura de un prompt rompe tests que no
  tienen nada que ver con lo que se cambió, y reescribir prompts es el trabajo central de la tesis.
  El doble de proveedor también parsea el prompt del escritor para extraer el cuerpo original,
  partiéndolo por `ORIGINAL CHAPTER BODY:` y `RETRY CORRECTION:`, que son literales de
  `agents/writer.py`. (El caso que antes citaba esta ficha,
  `test_the_story_plan_is_written_from_a_single_guarded_site`, que leía el código fuente como texto
  y lo partía por la indentación exacta del método, **ya no existe**: se borró en `cf45c1b`. Con él
  desapareció el obstáculo que esta ficha señalaba para dividir `pipeline.py`.)
- **Qué hacer.** Expresar cada aserción como comportamiento observable en vez de subcadena. Donde
  el contenido del prompt sea de verdad el contrato, concentrarlo en pocos tests declarados como
  tales.
- **Hecho cuando.** Reescribir un prompt de sistema solo rompe los tests que verifican ese prompt.

### Dividir `pipeline.py`

- **Síntoma.** 1190 líneas y 57 métodos en una sola clase, mezclando orquestación, reintentos,
  validación, ensamblado de Markdown, prompts de reparación y telemetría. El campo `repository`
  opcional obliga a 17 `assert self.repository is not None` repartidos por la clase.
- **Qué hacer.** Empezar por las tres extracciones de riesgo nulo, que se mueven literalmente
  porque no tocan `self`, `repository` ni `provider`: los prompts de reparación (`_repair_guidance`
  y sus seis hermanos, líneas contiguas), el ensamblado de Markdown (`_assemble_story`, que ya
  delega el formato en `audit.canonical_chapter` y no tiene ni una referencia externa) y las reglas
  de aceptación del escritor (`_writer_candidate_issue` y `_writer_fallback_warning`). Son unas 250
  líneas y sólo tres llamadas de test que actualizar. **El obstáculo que citaba la ficha de las
  aserciones de prompt ya no existe.** Después la telemetría y la contabilidad de uso como
  colaboradores, y solo al final las etapas como clases con estado propio, que es lo que elimina
  los asertos.
- **Hecho cuando.** Plan, borrador y revisión son unidades con test propio, el estado deja de
  pasarse como parámetros posicionales, y los artefactos generados no cambian.

### Persistencia real de lo desplegado

- **Síntoma.** El `Dockerfile` no declara ningún `VOLUME` y la cola SQLite vive en `/app/Stories`,
  que se pierde en cada redeploy; `sync-railway-stories.ps1` existe solo para rescatar las
  historias antes, con 713 líneas y un único `try` de 222.
- **Qué hacer.** Montar un volumen para la cola y las historias.
- **Hecho cuando.** Artefactos y cola sobreviven a un redeploy sin intervención y el script queda
  como herramienta de archivado opcional.

### `topological_order` se serializa y es derivable

- **Síntoma.** Se escribe en cada plan aunque se puede deducir: comprobado sobre los planes del
  corpus, **en 71 de 71** coincide exactamente con ordenar los eventos por su campo `order`, que es
  lo que ya garantizan los invariantes del grafo. Es el único de los cuatro casos de abstracción
  vacía que sigue abierto; los otros tres se cerraron. Quitarlo no es gratis: lo leen `graph.py` y
  `pipeline.py`, y está dentro de los artefactos de las 159 ejecuciones ya generadas.
- **Qué hacer.** Decidir si el campo se deriva en carga en vez de persistirse. Si se quita, sube
  `PIPELINE_VERSION` y da una lectura compatible a los runs que lo traen: son datos de la tesis.
- **Hecho cuando.** Hay decisión escrita y, si se elimina, los runs anteriores se siguen abriendo.

### Subir a `core` lo que está duplicado

- **Síntoma.** El bloque `Settings` más `load_settings` con dotenv y `GEMINI_API_KEY` está en los
  dos `config.py`, incluido el literal del nombre del modelo; comparten tres campos y divergen en
  que Top-Down exige la clave y añade ocho de cuota, así que sale una base común, no una clase
  única. La consola reimplementa el cuerpo de `cli.run_one` del escape room, y ya divergen en cómo
  informan del audio: eso es reconciliar comportamiento, no borrar una copia. El tercer caso, el
  nombrado de directorio con sufijo anticolisión, ya vive en `asg_core.create_unique_directory`.
- **Qué hacer.** Subir la configuración compartida a `asg_core` y decidir qué comportamiento de
  audio es el correcto antes de unificar la consola con `cli.run_one`.
- **Hecho cuando.** No queda ninguna de las dos duplicaciones que siguen vivas.

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
clasificado se comprueban. Tampoco `collect_metrics`, `result_row` ni `run_batch`; de esa lista
sólo `save_batch` tiene test propio.

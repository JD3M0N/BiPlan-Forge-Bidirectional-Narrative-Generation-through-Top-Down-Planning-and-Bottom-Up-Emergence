# Hoja de ruta

Las tareas se agrupan por subsistema. Cada una describe el resultado esperado, una condición
concreta para considerarla terminada y la evidencia en el código que la origina.

**Prioridades.** `P0` bloquea la línea base o produce resultados incorrectos; `P1` es necesario
para sostener la tesis y la operación; `P2` es refactorización que reduce el coste de todo lo
anterior sin cambiar el comportamiento observable.

**Orden sugerido:** primero las siete tareas `P0` (línea base de calidad, política de voz,
extensión de las historias Expansivas, plan entregado sin validar, trabajos bloqueados y fugas
de la cola); después `P1`, empezando por integración continua y el lector de evaluaciones; y por
último `P2`, empezando por la división de `pipeline.py`, que es la que abarata todas las demás.

**Estado medido el 2026-09-03 sobre `1bea0f1`:** 168 pruebas colectadas, `ruff check .` sin
errores, `ruff format --check .` reformatearía 8 archivos, una prueba fallando por docstrings
ausentes. La comparación de perfiles con este código está en `docs/calibracion_perfiles.md`.

---

## Calidad e infraestructura

- [ ] **`P0` Recuperar la línea base de calidad.** Resolver la discrepancia entre la política de
  voz española y su prueba, añadir los docstrings que exige la suite y aplicar el formato
  pendiente. **Finalizada cuando:** las 168 pruebas pasan (con las 2 pruebas de integración
  opcionales omitidas), `ruff check .` y `ruff format --check .` terminan sin errores.
  **Evidencia:** `ruff check .` ya pasa, pero `ruff format --check .` reformatearía 8 archivos;
  `tests/test_source_documentation.py:46` señala 9 docstrings ausentes (8 en
  `packages/core/src/asg_core/audio.py`, 1 en
  `packages/top_down/src/asg_top_down/provider.py:45`). Tres de ellos son closures de tres
  líneas (`audio.py:97`, `audio.py:242`, `provider.py:45`), lo que apunta a la tarea de
  sustituir el gate artesanal por reglas de linter.

- [ ] **`P1` Automatizar las comprobaciones en integración continua.** Crear un flujo que
  instale el monorepo y ejecute Ruff, la comprobación de formato, las pruebas Python,
  `pip check` y la prueba PowerShell de sincronización de Railway. **Finalizada cuando:** cada
  cambio se valida automáticamente en un entorno limpio y un fallo bloquea la comprobación
  correspondiente. **Evidencia:** no existe ningún directorio `.github/`; `pyproject.toml:3`
  solo colecta `test_*.py`, así que las 378 líneas de `tests/test_sync_railway_stories.ps1`
  nunca se ejecutan salvo a mano.

- [ ] **`P1` Hacer que el límite de longitud de línea sea real.** `pyproject.toml:8` declara
  `line-length = 100`, pero `select` no incluye `E501`, de modo que el límite no se comprueba
  nunca. **Finalizada cuando:** la regla está activa, las 82 líneas que hoy superan los 100
  caracteres están corregidas y una línea larga nueva falla la comprobación.

- [ ] **`P2` Sustituir el gate artesanal de docstrings por reglas del linter.** La prueba solo
  comprueba presencia y ASCII (`tests/test_source_documentation.py:25-27`), lo que ha producido
  decenas de docstrings tautológicas (`"Save json."`, `"Calculate details."`,
  `"Represent X data and behavior."`) y obliga a documentar closures. Además su marcador
  `"configuraci?n"` (`tests/test_source_documentation.py:9`) está corrupto y no puede coincidir
  nunca. **Finalizada cuando:** las reglas `D` de Ruff cubren el requisito, la prueba artesanal
  desaparece o queda reducida a la comprobación de idioma, y ningún docstring nuevo es
  tautológico.

- [ ] **`P2` Limpiar el entorno declarado.** `.env` conserva `GEMINI_EMBEDDING_MODEL`,
  `STORY_MAX_CPN_RETRIES` y `STORY_MAX_ARTIFACT_RETRIES`, que ya no lee ningún módulo, mientras
  que `.env.example` omite `ASG_PROJECT_ROOT` (`packages/core/src/asg_core/paths.py:13`) y
  `RUN_GEMINI_LIVE`. El entorno virtual arrastra instalaciones editables huérfanas
  (`asg_prompt_crafter`, `asg_testing`) sin paquete correspondiente en el repositorio.
  **Finalizada cuando:** toda variable presente en `.env.example` la lee alguien, toda variable
  leída está documentada, y `pip check` con una instalación limpia no menciona paquetes que no
  existen en el árbol.

## Core y audio

- [ ] **`P0` Hacer configurable y reproducible la narración de historias.** Definir voces por
  idioma y región, una selección determinista y un fallback seguro; documentar la configuración
  y conservar en `audio.json` la voz y el idioma realmente utilizados. **Finalizada cuando:** se
  pueden cambiar las voces sin editar el código y existen pruebas para detección de idioma,
  selección configurada, fallback, reintentos, limpieza de archivos parciales y fallos
  controlados. **Evidencia:** `packages/core/src/asg_core/audio.py:76-79` devuelve
  `es-ES-ElviraNeural` con un `return` temprano mientras
  `packages/core/tests/test_core.py:101-108` espera `es-MX-NovelNeural`; ese retorno deja
  inalcanzable toda la clasificación por `VoicesManager` (`audio.py:84-107`) para el español, y
  la voz alternativa está anotada como comentario (`audio.py:79`). La misma suposición `es-MX`
  sobrevive en `packages/top_down/tests/conftest.py`.

- [ ] **`P2` Endurecer las dependencias implícitas del generador de audio.** `_fallback_voice`
  (`audio.py:59-63`) deduce la voz por defecto leyendo con `inspect.signature` el valor por
  defecto de un argumento de `edge_tts.Communicate`: una actualización de la dependencia cambia
  la narración en silencio. `_VOICE_MANAGER` (`audio.py:26`) es un global mutable sin cerrojo
  que las pruebas parchean directamente, y `audio.py:91` captura toda excepción para caer al
  fallback. **Finalizada cuando:** la voz por defecto es una constante propia, la caché de
  voces no es estado global compartido con las pruebas, y solo se degradan a fallback los
  errores esperados.

## Top-Down: perfiles y calibración

- [ ] **`P0` Garantizar que el plan entregado supera su propio validador.** El run
  `Stories/Top-Down/20260903-175604-el-dominio-escamado` entrega un `story_plan.json` cuyas
  dependencias son idénticas a `planning/attempt-002.json`, rechazado con
  `expansive profile requires a causal dependency branch followed by a causal join`, y aun así
  registra `status: completed` y `warnings: []`. Según
  `packages/top_down/src/asg_top_down/pipeline.py:257-262` eso debería haber lanzado
  `PlotValidationError`. Además `plan_review.json` de ese run aprueba el plan y elogia una
  bifurcación que el grafo no contiene: el crítico no detecta la violación estructural. La
  ejecución de control del 2026-09-03 no reprodujo el fallo —el plan Expansivo fue rechazado y
  corregido en el segundo intento—, lo que apunta a un estado intermedio del código, pero una
  sola ejecución no lo descarta. **Finalizada cuando:** una prueba de regresión demuestra que
  ningún `story_plan.json` puede persistirse sin pasar `validate_profile_structure`, y una
  revalidación de todo el corpus distingue explícitamente entre runs anteriores al contrato y
  runs que lo incumplen.

- [ ] **`P0` Mejorar la extensión real de las historias Expansivas.** El arreglo cualitativo del
  `DramaCriticAgent` (verificación evento por evento, documentado en `docs/calibracion_perfiles.md`)
  revirtió la compresión de eventos frente a la Esencial: la Expansiva ya no es la menos densa por
  evento. Pero su extensión absoluta sigue por debajo de lo esperable para 9 eventos con escena
  completa: tres ejecuciones sobre tres prompts distintos del catálogo dieron 3171, 3763 y 4102
  palabras (`el-dominio-saurio`, `la-falsificacion-perfecta`, `las-cenizas-del-pacto`), ninguna
  por encima de las ~5000 palabras que cabría esperar. El propio dato correlaciona extensión con
  número de capítulos: la única ejecución con 5 capítulos (`las-cenizas-del-pacto`) alcanzó 456
  palabras por evento y el máximo de palabras total; las de 3 capítulos se quedaron en 352 y 418.
  Además, de las cinco ejecuciones Expansivas intentadas en esta sesión, dos (40 %) agotaron los
  dos intentos estructurales permitidos y fallaron por completo con `PLOT_VALIDATION_FAILED`; de
  los nueve intentos estructurales individuales realizados en total, seis (67 %) fueron
  rechazados por `validate_profile_structure`, casi siempre por quedarse a un solo evento del
  mínimo de 9 — el planificador tampoco converge con facilidad hacia un plan de 9 eventos bien
  distribuido. **Finalizada cuando:** una muestra de ejecuciones Expansivas alcanza de forma
  consistente una extensión perceptiblemente mayor —coherente con el reparto de capítulos que
  fije la tarea de segmentación siguiente— y la tasa de fallos de planificación baja de forma
  medible respecto al 40 % de ejecuciones y 67 % de intentos observados aquí.

- [ ] **`P0` Gobernar la segmentación en capítulos.**
  `packages/top_down/src/asg_top_down/profiles.py:51-55` solo fija un suelo de eventos; el
  número de capítulos, personajes y subtramas queda libre, y el resultado es que el perfil no
  afecta a la segmentación: las tres ejecuciones de control produjeron exactamente 3 capítulos.
  El reparto interno también es desigual —el primer capítulo de la Expansiva concentra 4 de sus
  9 eventos en 707 palabras (177 por evento) mientras el tercero dedica 1 336 palabras a 3— y
  en el corpus anterior una Desarrollada dio 6 capítulos y una Expansiva 4. **Finalizada
  cuando:** cada perfil impone o verifica una banda de capítulos y un reparto de eventos que
  impide concentrar la mitad de la trama en un capítulo, sin volver a los presupuestos
  numéricos de palabras que 6.0.0 eliminó.

- [ ] **`P1` Mapear la extensión solicitada por el usuario a un perfil narrativo.** Reconocer
  expresiones libres y cantidades de palabras o capítulos, dar precedencia a un perfil nombrado
  explícitamente y registrar el perfil seleccionado junto con su justificación. **Finalizada
  cuando:** casos representativos en español e inglés se asignan de forma consistente a
  Esencial, Desarrollada o Expansiva sin prometer una longitud exacta. **Evidencia:** hoy solo
  hay una expresión regular (`agents/analyst.py:13-17`) y tres mapas alias→perfil que pueden
  divergir: `analyst.py:18-25`, la instrucción del sistema en `analyst.py:50-57` y
  `apps/telegram/src/asg_telegram/prompts.py:29-40`.

- [ ] **`P1` Evaluar e integrar taxonomías o arquetipos cuando aporten calidad.** Comparar,
  sobre los mismos casos, historias generadas con y sin una guía taxonómica y medir su efecto en
  originalidad, coherencia y satisfacción. **Finalizada cuando:** el experimento y la decisión
  quedan documentados y, si existe una mejora, el pipeline incorpora un brief opcional y
  auditable sin restaurar la complejidad completa del subsistema anterior.

- [ ] **`P2` Evaluar un grafo explícito de lugares antes de añadir estado espacial dinámico.**
  Comparar el modelo actual basado en `locations` y `location_id` con relaciones y transiciones
  explícitas entre lugares. **Finalizada cuando:** se documenta el impacto en errores de
  continuidad y coste de generación, y el grafo solo se adopta si ofrece una mejora medible.

## Top-Down: pipeline y contrato

- [ ] **`P1` Dejar de degradar los errores de cuota a advertencias.** `pipeline.py:325`, `:506`
  y `:642` capturan `Exception` de forma amplia, de modo que un `GeminiDailyQuotaError` durante
  la crítica del plan, la crítica dramática o la revisión de un capítulo se convierte en una
  advertencia y el pipeline continúa hasta fallar más tarde o entregar texto sin revisar. Es
  incompatible con `_build_world`, `_build_characters` y `_build_plan`, que sí propagan.
  **Finalizada cuando:** los errores de cuota y de configuración abortan de inmediato con su
  código, solo se degradan los fallos realmente recuperables, y hay pruebas para ambos casos.

- [ ] **`P1` Corregir el registro de etapas.** `plan_review` se marca completada
  (`pipeline.py:292`) antes que `planning` (`pipeline.py:265`), de forma que
  `metadata.completed_stages` publica un orden que no ocurrió; además la etapa de progreso
  `saving` (`pipeline.py:766`) no coincide con el checkpoint `story` (`:769`) y `rate_limit`
  es una pseudoetapa con un caso especial (`:814`). **Finalizada cuando:** el orden registrado
  coincide con el de ejecución, los nombres de progreso y de checkpoint proceden de una única
  definición, y una prueba lo verifica.

- [ ] **`P1` Definir una política segura para ejecuciones interrumpidas.** Medir primero si hay
  un caso de uso que justifique reanudar desde los checkpoints existentes; mientras no exista
  reanudación segura, permitir reiniciar, notificar o descartar explícitamente los trabajos
  `recovery_pending`. **Finalizada cuando:** ningún trabajo queda indefinidamente bloqueado y la
  política elegida está documentada y cubierta por pruebas de reinicio. **Evidencia:**
  `complete_stage` (`storage.py:117-125`) escribe la lista de etapas pero nadie la lee para
  reanudar; los checkpoints hoy solo sirven de auditoría.

- [ ] **`P1` Dar al CLI las palancas que exige un experimento reproducible.** `generate-story`
  solo acepta el prompt posicional (`cli.py:25-29`): no hay `--profile`, `--output`, `--model`
  ni `--no-audio`, y `output_root` está fijo en `config.py:49`. El perfil viaja dentro del texto
  y depende de una regex, y cada ejecución gasta tiempo y red en generar el MP3 aunque el
  experimento solo mida estructura. **Finalizada cuando:** una tanda comparativa de tres
  perfiles se lanza sin editar prompts ni mover carpetas a posteriori, y el perfil efectivo
  queda determinado por el parámetro cuando se pasa.

- [ ] **`P2` Dividir `pipeline.py`.** Son 840 líneas y 26 métodos que mezclan orquestación,
  política de reintentos, validación, ensamblado de Markdown (`_assemble_story`,
  `pipeline.py:452-463`), construcción de prompts de reparación (`:335-383`), formateo de
  advertencias en español (`:739-752`) y telemetría. `_revise_one_chapter` (`:605-705`) tiene
  100 líneas y 10 parámetros, y `_critique_plan` (`:268-333`) encierra crítica, refinado,
  revalidación, fallback y tres escrituras bajo un único `try`. **Finalizada cuando:** las
  etapas de plan, borrador y revisión son unidades con estado propio y prueba propia, el estado
  compartido deja de pasarse como cadenas de parámetros posicionales, y el comportamiento
  observable de los artefactos no cambia.

- [ ] **`P2` Unificar la construcción de prompts y del proveedor.** La cabecera
  `STORY SPECIFICATION` + `NARRATIVE PROFILE CONTRACT` está copiada en siete agentes
  (`agents/world.py:26`, `characters.py:27`, `planner.py:49`, `review.py:44` y `:81`,
  `writer.py:69` y `:112`), y la construcción del `GeminiProvider` está copiada cinco veces
  (`cli.py:49-58`, `apps/console/src/asg_console/top_down.py:41-50`,
  `apps/telegram/src/asg_telegram/generators.py:49-58` y dos veces en `test_gemini_live.py`).
  **Finalizada cuando:** existe un ayudante de cabecera y una fábrica
  `provider_from_settings(settings)`, y ningún módulo repite esas construcciones.

- [ ] **`P2` Fijar la temperatura por contrato y no por heurística de texto.**
  `provider.py:207-225` clasifica la operación buscando subcadenas en el nombre del esquema y en
  la instrucción del sistema, con el diccionario de temperaturas duplicado (`:198-204` y
  `:218-224`) y una rama `elif` que nunca alcanza el caso `analyst`. Cambiar una palabra de un
  prompt altera la temperatura en silencio. **Finalizada cuando:** cada agente declara su perfil
  de generación explícitamente y una prueba fija la temperatura esperada por agente.

- [ ] **`P2` Abaratar la escritura de artefactos.** `append_llm_call` (`storage.py:106-115`) lee
  y reescribe `llm_calls.jsonl` completo en cada llamada y vuelve a calcular su SHA-256 para el
  manifiesto; `llm_usage.json` se reescribe entero por llamada (`pipeline.py:162-177`); y el
  manifiesto se regenera con cada artefacto y con cada actualización de `metadata.json`. Un run
  de nueve capítulos hace decenas de reescrituras completas. **Finalizada cuando:** añadir una
  llamada al registro es una operación de anexado, el manifiesto se consolida al cerrar cada
  etapa, y los hashes publicados siguen coincidiendo con los archivos.

- [ ] **`P2` Eliminar abstracciones inertes y código muerto.** `PipelineEvent.chapter_id`
  (`progress.py:33`) no lo rellena ningún llamador; `ArtifactValidationError`
  (`errors.py:62-71`) no se lanza nunca; `generation_profiles` y
  `structured_validation_retries` (`provider.py:172-173`) no los pasa nadie; `ChapterPlan`
  (`schemas.py:135-137`) es una subclase vacía; `generator.run()` (`generator.py:77-90`) es un
  alias literal de `generate()`; y `topological_order` es redundante porque
  `_validate_dependency_directions` (`graph.py:257-263`) ya garantiza que el orden de Kahn
  (`graph.py:232-254`) coincide siempre con el campo `order`. **Finalizada cuando:** cada
  eliminación va acompañada de la prueba que demuestra que nada dependía de ella, y el contrato
  de artefactos documenta si `topological_order` se conserva por compatibilidad.

- [ ] **`P2` Aclarar la frontera de idiomas en los mensajes de error.** Los mensajes de error
  estructural en inglés (`graph.py:114`, `:172`, `:229`; `pipeline.py:450`, `:529`) se reinyectan
  en el prompt de reparación (`pipeline.py:361`), así que forman parte del contrato con el
  modelo y no pueden traducirse; esa regla («mensajes de usuario en español, mensajes que
  alimentan al modelo en inglés») solo está anotada como comentario junto a
  `_record_rejected_plan` (`pipeline.py:359-361`), no en los puntos de origen ni comprobada por
  una prueba. **Finalizada cuando:** la regla está documentada en todos los puntos relevantes
  (origen y reinyección) y una prueba comprueba que los mensajes que alimentan al modelo
  permanecen en inglés mientras los de cara al usuario están en español.
  **Evidencia:** los dos bytes corruptos que originaron esta tarea (`pipeline.py:778`, `:783`,
  `"Generando narraci?n"` y `"story.md permanece v?lido"`) ya están corregidos.

- [ ] **`P2` Hacer que el proveedor no dependa de estado mutable compartido.** El pipeline muta
  `wait_callback` y `usage_callback` del proveedor y los limpia en un `finally`
  (`pipeline.py:102-103`), lee `usage_records` por `getattr` en siete puntos, y el limitador de
  peticiones es un singleton de proceso cacheado en `provider.py:32-33`. Dos ejecuciones
  concurrentes sobre el mismo proveedor se pisarían. Además el `Protocol
  LanguageModelProvider` (`provider.py:144-155`) no anota los parámetros de `StoryGenerator` ni
  de `StoryPipeline`. **Finalizada cuando:** los callbacks se pasan por llamada, la telemetría
  se obtiene por una interfaz declarada, y el tipo del proveedor está anotado en las fachadas.

- [ ] **`P2` Evitar que `StoryRun` lance excepciones que el CLI no captura.** `generator.py:22`
  y `:28` pueden lanzar `FileNotFoundError`, `JSONDecodeError` o `ValueError`, mientras que
  `cli.py:81` solo captura `ASGError` y `KeyboardInterrupt`: el usuario recibe una traza cruda.
  **Finalizada cuando:** un `metadata.json` ausente, corrupto o con versión no soportada produce
  un `ASGError` con mensaje público y código de salida 1.

## Telegram

- [ ] **`P0` Desbloquear los trabajos irrecuperables.** `queue.py:178-199` marca los trabajos
  interrumpidos como `recovery_pending` con `error_code = RECOVERY_NOT_IMPLEMENTED`, pero
  ningún camino los saca de ese estado: `finish` (`queue.py:153`) solo acepta `completed`,
  `failed` o `cancelled`, y `cancel_user` (`queue.py:164-176`) solo actúa sobre `queued`, de
  modo que tampoco puede cancelarse un trabajo en ejecución. Cada reinicio del bot durante una
  generación deja un trabajo varado para siempre e incrementa `recovery_count`. **Finalizada
  cuando:** existe una transición explícita —reencolar, descartar o notificar— para cada
  trabajo `recovery_pending`, el operador puede cancelar un trabajo en ejecución, y hay pruebas
  de reinicio que lo demuestran.

- [ ] **`P0` Cerrar las conexiones SQLite.** Todos los métodos usan `with self._connect()`
  (`queue.py:53-57`), y el gestor de contexto de `sqlite3.Connection` confirma o revierte la
  transacción pero no cierra la conexión: cada `enqueue`, `active`, `position`, `finish` o
  `average_duration` deja una abierta hasta que la recoja el recolector de basura, y
  `_refresh_queue` (`generation.py:528-548`) llama a dos de ellos en cada transición.
  **Finalizada cuando:** las conexiones se cierran de forma determinista, la disciplina de
  cerrojos es la misma para lectores y escritores (hoy solo los escritores toman `self._lock`)
  y una prueba verifica que no quedan conexiones abiertas tras una tanda de operaciones.

- [ ] **`P1` Versionar y mantener la cola persistente.** Incorporar migraciones compatibles para
  `telegram_queue.sqlite3` y definir cuánto tiempo se conservan trabajos terminados, errores y
  prompts. **Finalizada cuando:** una base creada por una versión anterior se actualiza sin
  perder trabajos activos y los registros vencidos pueden depurarse de forma verificable.
  **Evidencia:** `queue.py:41-51` solo hace `CREATE TABLE IF NOT EXISTS`, sin versión de
  esquema, y `_job` (`queue.py:62`) construye el registro por posición de campo, así que
  cualquier columna nueva rompe toda lectura de una base antigua; la base está en `.gitignore`,
  de modo que el fallo solo aparece en producción. `average_duration` (`queue.py:208`) exige
  exactamente diez filas completadas, por lo que la estimación no aparece nunca antes.

- [ ] **`P1` Mostrar en la consola el estado operativo de la cola.** Presentar el trabajo en
  ejecución, usuario, posición, etapa, porcentaje y solicitudes pendientes, actualizando la
  vista cuando cambien la cola o el progreso. **Finalizada cuando:** el operador puede conocer
  la carga y la etapa actual sin consultar Telegram ni la base SQLite, y el estado mínimo
  necesario se conserva durante la ejecución.

- [ ] **`P1` Eliminar el bloqueo del hilo de generación.** `report_progress`
  (`generation.py:139-153`) llama a `future.result()` sin tiempo límite desde el hilo lanzado
  con `asyncio.to_thread`, en cada notificación de progreso: cualquier demora al editar el
  mensaje de Telegram (`generation.py:575-579`) detiene la generación. **Finalizada cuando:**
  el progreso se entrega sin bloquear la generación, una edición lenta o fallida no detiene el
  pipeline, y existe una prueba con una edición que nunca responde.

- [ ] **`P1` No registrar credenciales en los diagnósticos.** `_redact_diagnostic`
  (`console.py:29-37`) solo oculta claves `AIza…` y asignaciones con `key`, `token` o
  `authorization`; un token de bot de Telegram con la forma `\d+:[A-Za-z0-9_-]{35}` aparecería
  íntegro, y `console.py:69` registra trazas completas para las excepciones que no son
  `ASGError`. **Finalizada cuando:** los formatos de credencial usados por el proyecto están
  cubiertos por pruebas y ninguna traza registrada los contiene.

- [ ] **`P1` Aceptar solicitudes de historias mediante notas de voz.** Descargar y transcribir
  el audio recibido, mostrar el texto resultante para que el usuario lo confirme o corrija y
  solo entonces incorporarlo al flujo libre o guiado. **Finalizada cuando:** una nota de voz
  válida puede iniciar una solicitud y los formatos, tamaños o transcripciones no válidos
  generan mensajes claros sin añadir trabajos a la cola.

- [ ] **`P2` Hacer real la abstracción del generador.** `generators.py:15-31` declara un
  `StoryGeneratorAdapter`, pero la app importa directamente de `asg_top_down` los errores y el
  formateo de progreso (`generation.py:12-13`, `console.py:9`, `prompts.py:9`), detecta las
  capacidades del generador con `inspect.signature` (`generation.py:239-254`) —de modo que
  renombrar un parámetro desactiva el progreso en silencio— y `_revision_warning_details`
  (`generation.py:399-456`) interpreta a mano tres esquemas de artefactos de Top-Down.
  Además `TopDownGenerator.generate` reconstruye los ajustes y el proveedor en cada historia
  (`generators.py:44-72`), así que el control de cuota no se comparte entre trabajos de la cola.
  **Finalizada cuando:** el adaptador expone progreso, errores y advertencias como contrato
  propio, la app no importa nada de `asg_top_down` fuera de la fábrica, y el proveedor se
  reutiliza entre trabajos.

- [ ] **`P2` Unificar los reintentos de entrega y el estado conversacional.**
  `_send_document_with_retry` y `_send_audio_with_retry` (`delivery.py:129-237`) son la misma
  máquina de reintentos escrita dos veces, y los estados de conversación son cadenas repartidas
  entre `handlers.py:116-209` y `generation.py:87` sin una definición única. Además
  `handlers.py:271-281` reintenta indefinidamente si falla el guardado de una evaluación, y
  `enqueue` (`queue.py:75-81`) devuelve el trabajo existente sin que el llamador pueda
  distinguir «encolado» de «rechazado». **Finalizada cuando:** existe una única política de
  reintentos parametrizada, los estados son una enumeración compartida, el reintento de
  evaluación está acotado y `enqueue` comunica el rechazo.

## Evaluación y benchmark

- [ ] **`P1` Poder leer y agregar las evaluaciones humanas.** `asg_evaluation` solo escribe:
  exporta `METRICS`, `add_evaluation`, `create_evaluation_template` y `discover_stories`
  (`__init__.py:3-15`), sin ningún lector, media, varianza ni acuerdo entre evaluadores. Una
  tesis necesita analizar esas puntuaciones y hoy nada del repositorio puede cargarlas de
  vuelta. **Finalizada cuando:** existe una función de carga y agregación por historia y por
  perfil, con pruebas, y el resultado puede compararse entre versiones del generador.

- [ ] **`P1` Hacer robusto el formato de `evaluation.json`.** La plantilla pendiente se detecta
  comparando por igualdad la lista completa (`evaluation.py:78-79`), así que cualquier edición
  manual convierte el archivo en irrecuperable; `SCHEMA_VERSION = 1` (`evaluation.py:19, 73`) se
  rechaza sin migración; no hay deduplicación por evaluador; y la secuencia leer-modificar-
  escribir (`evaluation.py:88-99`) no está protegida, de modo que dos evaluaciones simultáneas
  desde Telegram pierden una. **Finalizada cuando:** el centinela no depende de una comparación
  exacta, existe una ruta de migración, y una prueba de concurrencia demuestra que no se pierden
  evaluaciones.

- [ ] **`P1` Crear un benchmark narrativo reproducible.** Mantener un conjunto versionado de
  prompts y un procedimiento común para recoger métricas automáticas y evaluaciones humanas de
  perfiles, taxonomías y cambios futuros. **Finalizada cuando:** dos versiones del generador
  pueden compararse bajo las mismas condiciones y los resultados conservan la configuración
  necesaria para repetir el experimento. **Evidencia:** los prompts canónicos ya existen en
  `docs/prompts_top_down.md`, y `story_metrics.json` más `llm_usage.json` aportan la parte
  automática; falta el procedimiento y el recolector. Ninguno de los runs con perfil registrado
  tiene todavía una evaluación humana rellenada.

- [ ] **`P2` Permitir comparar más de dos ejecuciones.** `compare-story-runs`
  (`compare.py:31-41`) solo acepta dos runs, así que una comparación de tres perfiles obliga a
  encadenar informes. El artefacto
  `Stories/Top-Down/comparacion-densidad-borrador-final-v2.0.4.html` es de agosto, compara dos
  versiones que difieren en una palabra y tiene la sección de notas vacía. **Finalizada
  cuando:** la comparación ciega acepta N ejecuciones y el informe obsoleto está sustituido o
  marcado como histórico.

## Documentación y despliegue

- [ ] **`P1` Dar persistencia real a los artefactos desplegados.** El `Dockerfile` crea
  `/app/Stories/Top-Down` sin volumen, de modo que la cola SQLite y todas las historias viven en
  el sistema de archivos efímero del contenedor; `sync-railway-stories.ps1` (713 líneas) existe
  precisamente para rescatarlas antes de que el contenedor se reemplace. Es deuda de
  arquitectura, no de scripting. **Finalizada cuando:** los artefactos y la cola sobreviven a un
  redespliegue sin intervención manual, y el script de sincronización queda reducido a una
  herramienta de archivado opcional.

- [ ] **`P2` Hacer mantenible el script de sincronización.** Todo lo que sigue a
  `sync-railway-stories.ps1:464` son sentencias de nivel superior dentro de un único `try` de
  unas 210 líneas, por lo que la orquestación no puede probarse en aislamiento y
  `tests/test_sync_railway_stories.ps1` debe cargar el archivo completo. `Test-ArchivedRun`
  (`:160-262`) convierte cualquier excepción en `State='invalid'`, así que un error de permisos
  y una corrupción real son indistinguibles, y la política de borrado depende de comparar el
  texto en inglés de un mensaje de la CLI de Railway (`:439-452`). **Finalizada cuando:** las
  funciones son un módulo importable con pruebas propias, los fallos transitorios se distinguen
  de la corrupción, y la clasificación del borrado no depende de una cadena de terceros.

- [ ] **`P1` Documentar los contratos públicos con ejemplos ejecutables.** Cubrir las fachadas
  de `asg_core`, `asg_top_down`, `asg_evaluation` y `asg_escape_room`, además de callbacks,
  errores y artefactos principales, con ejemplos mínimos de entrada, salida y fallo.
  **Finalizada cuando:** la documentación describe el contrato Top-Down 6.0, aclara la
  compatibilidad relevante con ejecuciones anteriores y los ejemplos se validan en las pruebas o
  en la integración continua.

- [ ] **`P1` Actualizar la documentación desfasada.**
  `docs/informe_ejecucion_pipeline_top_down.md` describe todavía la arquitectura 5.0, con
  `target_words`, `length_audit.json` y los agentes `ChapterWriter → StoryCritic → StoryEditor`,
  que ya no existen; el `README.md` raíz no menciona los perfiles narrativos y contiene
  caracteres corruptos. Además `.gitignore` ignora `docs/*` con una lista blanca que nombra tres
  archivos inexistentes (`como_se_crea_una_historia_top_down.md`,
  `pipeline_top_down_caso_dinosaurios.md`, `top_down_pipeline.md`) y deja fuera del control de
  versiones el informe de ejecución. **Finalizada cuando:** el informe vigente describe las diez
  etapas reales y los artefactos que se producen hoy, el histórico queda marcado como tal, el
  README raíz explica los perfiles sin texto corrupto, y la lista blanca de `docs/` corresponde
  a los archivos que existen.

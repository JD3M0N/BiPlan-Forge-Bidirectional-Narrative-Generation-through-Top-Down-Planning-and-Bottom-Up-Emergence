# Hoja de ruta

Tareas agrupadas por subsistema. Cada una tiene: qué falta, cuándo se considera cerrada
(**Cierre:**) y dónde está el problema en el código (**Evidencia:**).

**Prioridades.** `P0` bloquea la línea base o produce resultados incorrectos. `P1` hace falta
para sostener la tesis y la operación. `P2` es refactor que no cambia el comportamiento pero
abarata el resto.

**Orden sugerido:** queda un solo `P0` abierto (la banda de capítulos frente a los mínimos de
eventos), que necesita decidir la salida y re-medir con API real; luego `P1` empezando por CI y el
lector de evaluaciones; por último `P2` empezando por dividir `pipeline.py`.

**Estado medido el 2026-09-11 sobre `37a70a5`** (más el guard de persistencia del plan y el
feedback de reparación causal, todavía sin commitear): 253 pruebas (251 pasan, 2 omitidas),
`ruff check .`, `ruff format --check .` (117 archivos) y `pip check` limpios.
Comparación de perfiles en [docs/calibracion_perfiles.md](docs/calibracion_perfiles.md).

---

## Calidad e infraestructura

- [ ] **`P1` Meter las comprobaciones en CI.** No hay `.github/`. `pyproject.toml:3` fija
  `python_files = ["test_*.py"]`, así que ni `tests/test_sync_railway_stories.ps1` ni ningún otro
  `.ps1` se recogen nunca salvo a mano. **Cierre:** un pipeline instala el repo y corre Ruff,
  formato, pytest, `pip check` y el test de PowerShell en cada cambio; un fallo bloquea el merge.

- [ ] **`P2` Cambiar el gate de docstrings a reglas del linter.** El test actual
  (`tests/test_source_documentation.py:20-23` para el glob, la comprobación real en :44) solo mira
  que exista texto ASCII, lo que ha dejado pasar docstrings inútiles ("Save json.", "Calculate
  details.") y obliga a documentar closures. Su marcador de español está roto: `"configuraci?n"`
  (línea 10) no es un regex sino un literal usado con `in`, así que nunca puede coincidir — y como
  el filtro que de verdad impone inglés es `not docstring.isascii()`, el conjunto de marcadores es
  casi redundante. Además el glob `*/src/**` es relativo al directorio de trabajo, así que pasa en
  silencio si se ejecuta desde otro sitio. **Cierre:** las reglas `D` de Ruff cubren esto, el test a
  mano desaparece o se reduce a comprobar idioma, y no quedan docstrings vacíos de contenido.

## Apps

- [x] **`P0` Reparar la llamada a un método que ya no existe.** `95aa558` eliminó
  `StoryGenerator.run()` sin actualizar a ninguno de sus dos llamadores, así que la consola y el
  bot lanzaban `AttributeError` antes de generar nada. En Telegram el usuario lo veía como
  `[░░░░░░░░░░] 0% — unknown: Generación fallida` y `Código: UNEXPECTED_ERROR`, porque
  `AttributeError` no es `ASGError` y el fallo ocurría antes del primer `_notify` del pipeline.
  **Hecho (2026-09-07):** ambas apps llaman `generate(...)`; la consola pierde además la sonda
  `inspect.signature` y su rama muerta. Los dobles que lo enmascaraban se sustituyeron por
  `unittest.mock.create_autospec(StoryGenerator, ...)`, que rechaza `.run()` y toda firma
  inexistente. **Evidencia:** `apps/telegram/tests/test_generators_contract.py` (comprobado: al
  reintroducir `.run(` fallan sus dos tests de contrato), `apps/console/tests/test_app.py:66`.

## Top-Down: perfiles y calibración

- [x] **`P0` Confirmar que ningún plan inválido se guarda como válido.** El run
  `Stories/Top-Down/20260903-175604-el-dominio-escamado` quedó marcado `status: completed` pese a
  incumplir el contrato Expansiva; su `plan_review.json` aprueba una bifurcación que el grafo no
  tiene.
  **Hecho (2026-09-11):** la validación deja de vivir solo en las dos ramas que producen el plan
  (`pipeline.py:331` y :414) y pasa a la única frontera que lo escribe: `_persist_plan` (:348)
  revalida `validate_story_plan` + `validate_profile_structure` y, si falla, aborta con
  `PLOT_VALIDATION_FAILED` sin escribir `story_plan.json` ni dejar el run como `completed`. Los
  artefactos de una ejecución válida no cambian. **Evidencia:**
  `test_a_plan_breaking_its_profile_contract_is_never_persisted` (parametrizado sobre Expansiva y
  Desarrollada; simula un bug futuro en la ruta de crítica sustituyendo `_critique_plan`) y
  `test_the_story_plan_is_written_from_a_single_guarded_site`, que impide que una rama nueva vuelva
  a saltarse el guard. Comprobado: los tres fallan si se revierte `_persist_plan` a un `save_json`
  directo.
  **Revalidación del corpus (2026-09-07):** ya estaba hecha — de 39 runs `completed` con
  perfil (más 22 anteriores al contrato, sin `narrative_profile`), 4 incumplen su contrato
  estructural, todos entre el 2026-09-01 y el 09-03. Tres son `generator_version` 6.0.0, es decir
  anteriores a `1bea0f1` (2026-09-03 14:43), que fue quien introdujo la regla rama→reunión: no son
  fallos, son runs previos a la norma. El único caso genuinamente anómalo es el que nombra este
  ítem: es 6.1.0 y se generó a las 17:56, después de la regla, y aun así carece de rama causal.
  Ningún run posterior al 2026-09-04 incumple (15+ runs, incluidos los 6 del 09-07).

- [x] **`P1` Hacer que el planificador cumpla el contrato de rama causal (Expansiva).** La prueba
  live canónica murió con `PLOT_VALIDATION_FAILED` tras agotar sus dos intentos: el modelo trataba
  el contrato rama→reunión como un puzle de conteo y perdía la restricción de orden. En el intento 1
  produjo dos raíces paralelas convergentes (reunión válida en `event_5`, ninguna rama: le faltaba
  **una sola arista**); en el intento 2 la añadió como `event_4→event_3`, que satisface el conteo
  pero apunta hacia atrás. El prompt de reparación no ayudaba: decía solo "Fix this structural
  error" y volcaba la matriz de `PAYOFF_OF`, irrelevante para esa clase de fallo.
  **Hecho (2026-09-11):** `_record_rejected_plan` despacha el feedback según el error
  (`_repair_guidance`). Ante una rama faltante emite los grados causales de cada evento y **una
  arista concreta y legal** que repara el plan (`_suggested_branch_edge`); ante una dependencia
  hacia atrás nombra la arista con sus dos `order` y las dos reparaciones válidas; los fallos de
  `payoff_of` conservan su matriz. El planificador recibe además un ejemplo trabajado de rama→reunión
  con órdenes explícitos, y Expansiva dispone de un tercer intento
  (`PLAN_ATTEMPTS_BY_PROFILE`), con `PlotValidationError` informando del número real de intentos en
  vez del 2 fijo anterior. El contrato **no se relajó**.
  **Evidencia medida con Gemini real (2026-09-11, `--no-audio`):** sobre el prompt canónico
  Expansiva, la línea base completaba 0/1; tras el cambio **la planificación superó el contrato en
  5 de 5 corridas** y ninguna volvió a ser rechazada por rama→reunión (los rechazos restantes son
  del suelo de eventos: 6, 7, 7, 8 y 8 frente al mínimo de 9). Cuatro terminaron la historia
  completa (`20260911-160244`, `-161105`, `-162223`, `-170230`); la quinta (`-165056`) murió después
  de planificar por un `PROVIDER_ERROR` 503 UNAVAILABLE de Gemini, ajeno al cambio. Comprobado sobre
  los `story_plan.json` resultantes que tienen rama y reunión reales con `rama.order < reunión.order`
  (`event_1→event_7`, `event_4→event_8`, `event_3→event_6`, `event_3→event_7`). **Controles sin
  degradación:** un run Esencial (`-163523`, 3 capítulos / 6 eventos) y uno Desarrollada (`-164429`,
  4 / 7) aceptaron el plan **al primer intento**, sin rechazos ni avisos. Tests con proveedor falso en
  `packages/top_down/tests/test_generator_v5.py`
  (`test_a_join_without_a_branch_is_repaired_by_naming_the_missing_edge` replica la topología exacta
  del fallo real, `test_backwards_dependency_retry_is_told_which_edge_points_back`,
  `test_payoff_failures_still_receive_their_reference_matrix`,
  `test_only_the_expansive_profile_earns_a_third_planning_attempt`).
  **Trampa aprendida:** una arista hacia atrás sobre una cadena lineal dispara primero el detector de
  ciclos, no el de dirección; para probar el caso real hay que reproducir su topología
  (`1→4, 4→5, 4→3, 2→3, 3→5, …`), donde no hay ciclo.

- [ ] **`P0` Conciliar la banda de capítulos con los mínimos de eventos.**
  `PROFILE_CHAPTER_BAND` (`packages/top_down/src/asg_top_down/profiles.py:62-66`: Esencial 2-3,
  Desarrollada 4-5, Expansiva 5-7) llega al planificador como guía; `PROFILE_MIN_EVENTS` (:52-56:
  sin mínimo / 6 / 9) sí lo valida `validate_profile_structure`. Los dos contratos no son
  compatibles entre sí. **Cierre:** banda y mínimos son coherentes, y ningún perfil produce
  capítulos de un solo evento de forma sistemática.
  **Evidencia (2026-09-07, 6 celdas: catálogos 6 y 7 × los tres perfiles, `--no-audio`):** el
  planificador respetó la banda en 6 de 6 sin necesitar validación, así que como guía basta y
  endurecerla no aporta. El orden por longitud quedó correcto en ambos catálogos (cat. 6:
  978 < 3369 < 4981, antes invertido en 3680 > 3171; cat. 7: 1553 < 3931 < 4252) y la inversión
  Desarrollada > Expansiva bajó del 34% al 0%. Expansiva subió +57% y +13% sobre su línea base, que
  era el objetivo de alargarla.
  **Dato nuevo (2026-09-11, 3 corridas del prompt canónico Expansiva):** el planificador se queda
  corto de eventos en el **primer** intento las tres veces (7, 7 y 8 frente al mínimo de 9) y solo
  alcanza los 9 tras el rechazo. Con la banda 5-7 y 9 eventos, el reparto sigue dando capítulos de
  un solo evento. Es el mismo desajuste aritmético que describe este ítem, ahora medido sobre el
  caso canónico.
  **Pero la banda empeora el reparto de eventos:** capítulos con un solo evento pasan del 47% al
  67% en Desarrollada y del 19% al 30% en Expansiva (Esencial mejora del 16% al 0%). La causa es
  aritmética, no del modelo: con la banda 4-5 y el mínimo de 6 eventos, Desarrollada necesitaría
  8-10 eventos para tener ≥2 por capítulo; Expansiva necesitaría 10-14 frente a su mínimo de 9.
  Al elegir salida: subir los mínimos encarece la planificación (1 de 3 intentos Expansiva murió
  por `PLOT_VALIDATION_FAILED` quedándose en 8 eventos), estrechar las bandas conserva el orden ya
  logrado.

- [ ] **`P1` Traducir lo que pide el usuario a un perfil narrativo.** Hoy la detección vive
  duplicada en tres sitios que pueden divergir: el regex `EXPLICIT_PROFILE` y el dict
  `PROFILE_ALIASES` (`agents/analyst.py:13-17` y :18-25), la instrucción de sistema que repite la
  regla (`analyst.py:52-59`), y `PROFILE_CHOICES` en
  `apps/telegram/src/asg_telegram/prompts.py:28-39`. Las filas de alias de `analyst.py:19-24` y
  `prompts.py:29-34` son idénticas carácter a carácter, y `profiles.py` no expone ningún mapa de
  alias que pudieran compartir. **Cierre:** casos representativos en español e inglés mapean de
  forma consistente a Esencial/Desarrollada/Expansiva, un perfil nombrado explícitamente gana, y
  queda registrada la justificación — sin prometer una longitud exacta.

- [ ] **`P1` Probar si una taxonomía de arquetipos mejora las historias.** Comparar, sobre los
  mismos prompts, historias con y sin guía taxonómica y medir el efecto en originalidad,
  coherencia y satisfacción. **Cierre:** el experimento y la decisión quedan documentados; si hay
  mejora, se añade como brief opcional y auditable sin resucitar la complejidad del subsistema
  anterior. **Evidencia:** el mecanismo ya está construido y es auditable
  (`packages/top_down/src/asg_top_down/skeletons.py:104-1393` con 34 esqueletos etiquetados por
  capa, `skeleton_match.py` con ranking léxico TF-IDF mezclado 0.70/0.30 con una llamada semántica,
  y la etapa `architecture` que escribe `narrative_blueprint.json` por run). La guía se inyecta
  como texto explícitamente no vinculante solo en el diseñador de personajes y el planificador;
  no hay validación que penalice desviarse. Cuando la guía está apagada no se escribe artefacto,
  `architecture` no aparece en `completed_stages` y los prompts quedan idénticos a la línea base,
  que es la señal de auditoría del experimento.
  **Estado (2026-09-07):** la ablación ya es limpia — `agents/characters.py` inyectaba el
  vocabulario de roles funcionales sin condicionarlo al blueprint, así que el brazo de control
  conservaba `functional_role` y `persona`; corregido en 6.3.0 y cubierto por
  `test_disabled_guidance_also_drops_the_functional_role_vocabulary`. **El experimento sigue sin
  hacerse:** el único par con y sin guía es n=1 y anterior a esa corrección (3520 vs 3558 palabras,
  3 capítulos y 9 eventos ambos), y las 6 celdas del 09-07 corrieron todas con la guía encendida,
  así que no lo avanzan.

- [ ] **`P2` Evaluar un grafo explícito de lugares antes de complicar el estado espacial.**
  Comparar el modelo actual (`locations`/`location_id`) contra relaciones y transiciones
  explícitas. **Cierre:** se documenta el efecto en errores de continuidad y coste de generación;
  solo se adopta si mejora algo medible.

## Top-Down: pipeline y contrato

- [ ] **`P1` Decidir qué pasa con las ejecuciones interrumpidas.** `complete_stage`
  (`storage.py:117-125`) escribe checkpoints que nadie lee para reanudar — hoy solo sirven de
  auditoría. **Cierre:** primero medir si vale la pena reanudar desde checkpoint; si no, dar una
  transición explícita (reiniciar/descartar/notificar) para que ningún trabajo quede bloqueado
  para siempre, documentada y con test de reinicio.

- [ ] **`P2` Dividir `pipeline.py`.** 946 líneas y 38 métodos en una sola clase, mezclando
  orquestación, reintentos, validación, ensamblado de Markdown, prompts de reparación y telemetría.
  `_revise_one_chapter` (:716-805) tiene 90 líneas y 10 parámetros; `_critique_plan` (:343-412)
  mete crítica + refinado + revalidación + fallback + tres escrituras en un solo `try`.
  **Cierre:** plan/borrador/revisión son unidades con estado y test propios, el estado deja de
  pasarse como parámetros posicionales, y los artefactos generados no cambian.

- [ ] **`P2` Dejar de reescribir artefactos enteros por cada llamada.** `append_llm_call`
  (`storage.py:106-115`) relee y reescribe todo `llm_calls.jsonl` y recalcula su SHA-256 en cada
  llamada (`_record`, :59-67, que además regenera el manifiesto); `llm_usage.json` se reescribe
  entero también. Un run de 9 capítulos hace decenas de reescrituras completas. **Cierre:**
  registrar una llamada es un anexado, el manifiesto se consolida al cerrar cada etapa, y los
  hashes siguen siendo correctos.

- [ ] **`P2` Resolver 4 abstracciones que ya no hacen nada.** `ChapterPlan` (`schemas.py:200-201`)
  es una subclase vacía pero pública (`__init__.py:36`) y usada como tipo en 12 sitios de
  producción. `structured_validation_retries` y `generation_profiles` (`provider.py:181-182`) son
  puntos de inyección muertos confirmados: ningún llamador los pasa —`provider_from_settings`
  (:479-490) pasa siete kwargs y ninguno de estos— y lo único que escribe `generation_profiles` es
  una asignación de atributo en `test_provider.py:278`. Ya no dependen de la tarea de temperatura,
  que cerró aterrizando como un dict a nivel de módulo (`_DEFAULT_GENERATION_PROFILES`,
  `provider.py:35-41`), así que la decisión se puede tomar ya. `topological_order`
  (`schemas.py:274`) se serializa en cada `story_plan.json`. `ArtifactValidationError`
  (`errors.py:62-71`) no se lanza en ningún `src/` pero la usan dos tests de Telegram como doble
  genérico. **Cierre:** cada caso tiene decisión tomada (eliminar con migración, o quedarse
  explícitamente) y, si se elimina, hay test que prueba que nada dependía de él.

- [ ] **`P2` Quitar el estado mutable compartido del proveedor.** El pipeline muta
  `wait_callback`/`usage_callback` del proveedor en `_configure_provider_callbacks`
  (`pipeline.py:196-201`) y los limpia en `_clear_provider_callbacks` (:203-208), invocados desde
  `execute` (:117 y el `finally` de :144-145). El limitador de peticiones es un registro global por
  capacidad (`provider.py:33-34`, `_LIMITERS`, compartido en :195-196), así que dos corridas
  concurrentes con la misma capacidad se pisarían. El `Protocol LanguageModelProvider` tampoco está
  anotado donde se usa. **Cierre:** los callbacks se pasan por llamada, la telemetría sale de una
  interfaz declarada, y el tipo del proveedor está anotado en las fachadas.

## Telegram

- [x] **`P0` Sacar los trabajos varados de `recovery_pending`.** **Hecho (2026-09-07):**
  `GenerationCoordinator._apply_recovery_policy` reencola cada trabajo interrumpido mientras
  `recovery_count <= MAX_RECOVERY_ATTEMPTS` (1) y, superado el límite, lo cierra como
  `RECOVERY_EXHAUSTED` avisando al usuario. `queue.requeue` implementa la transición y
  `cancel_user` cancela ahora también `recovery_pending`. Un trabajo en ejecución se detiene por
  cancelación cooperativa: `request_cancellation` marca la intención y el callback de progreso
  lanza `GenerationCancelled` en la siguiente frontera de etapa. **Evidencia:**
  `apps/telegram/tests/test_recovery_and_conversation.py`
  (`test_interrupted_job_is_requeued_once_then_reported_as_exhausted`,
  `test_no_job_is_left_parked_in_recovery_pending`,
  `test_running_generation_stops_when_the_user_cancels`).

- [ ] **`P1` Versionar la base de la cola.** **Hecho en su mayor parte (2026-09-07):** `queue.py`
  fija `SCHEMA_VERSION = 2` y migra con `PRAGMA user_version`, añadiendo por `ALTER TABLE` las
  columnas nuevas (`narrative_profile`, `cancel_requested`) sobre bases anteriores sin perder
  trabajos activos. `average_duration` exige ahora un mínimo de 3 muestras
  (`MINIMUM_SAMPLES_FOR_ESTIMATE`) en vez de exactamente 10, y `enqueue` devuelve
  `EnqueueResult(job, created)`, de modo que el coordinador avisa al usuario cuando su solicitud
  no se encoló. **Evidencia:** `test_a_database_from_the_previous_schema_migrates_without_losing_jobs`,
  `test_a_second_request_is_refused_instead_of_silently_dropped`, `apps/telegram/tests/test_queue.py`.
  **Falta para cerrar:** una forma verificable de purgar registros viejos.

- [ ] **`P1` Mostrar el estado de la cola en la consola.** Trabajo en curso, usuario, posición,
  etapa, porcentaje y pendientes, actualizándose con la cola. **Cierre:** el operador ve la carga
  y la etapa sin mirar Telegram ni la SQLite.

- [ ] **`P1` Aceptar notas de voz como solicitud de historia.** Transcribir el audio recibido,
  mostrar el texto para que el usuario lo confirme o corrija, y solo entonces meterlo al flujo.
  **Cierre:** una nota de voz válida arranca una solicitud; formatos/tamaños/transcripciones
  inválidas dan un mensaje claro sin encolar nada.

- [x] **`P2` Hacer real el adaptador del generador.** **Hecho (2026-09-07):** el nuevo
  `apps/telegram/src/asg_telegram/contract.py` declara los tipos propios de la app
  (`GenerationProgress`, `GenerationEvent`, `GenerationFailure`, `GenerationCancelled`,
  `RunSummary`, `ProfileOption`, un `format_progress` propio y el `Protocol`
  `StoryGeneratorAdapter`, marcado `runtime_checkable`). `generators.py` es ya el **único** módulo
  que importa `asg_top_down`: traduce progreso, eventos y errores, expone el catálogo de perfiles y
  absorbe `_revision_warning_details` detrás de `summarize_run`. Desaparecen las tres sondas
  `inspect.signature`. `TopDownGenerator.__init__` resuelve ajustes y proveedor una sola vez, así
  que la cuota de Gemini se comparte entre trabajos y una configuración rota falla al arrancar
  (`app.main` devuelve 2 ante `ASGError`) en vez de en el chat de un usuario. **Evidencia:**
  `apps/telegram/tests/test_generators_contract.py`,
  `test_main_reports_broken_top_down_configuration_as_exit_code_two`.

- [x] **`P2` Unificar reintentos de entrega y estados de conversación.**
  **Hecho (2026-09-07):** `TelegramDelivery._send_with_retry` es la única máquina de reintentos,
  sobre una sola constante `RETRY_DELAYS`. **Trampa aprendida:** en python-telegram-bot
  `BadRequest` hereda de `NetworkError`, así que su `except` tiene que ir primero o un rechazo
  permanente se reintenta; el orden es funcional, está comentado en el código y lo fija
  `test_bad_request_subclasses_network_error_so_handler_order_matters`. Los estados viven en
  `states.py` como `ConversationState`, y guardar una evaluación se reintenta como mucho
  `MAX_EVALUATION_RETRIES` (3) veces, devolviendo las puntuaciones al usuario si se agota.

## Evaluación y benchmark

- [ ] **`P1` Poder leer y agregar las evaluaciones humanas, no solo escribirlas.**
  `asg_evaluation` exporta `add_evaluation`, `create_evaluation_template`, `discover_stories` — sin
  lector, media, varianza ni acuerdo entre evaluadores. **Cierre:** hay carga y agregación por
  historia y por perfil, con tests, comparable entre versiones del generador.

- [ ] **`P1` Blindar el formato de `evaluation.json`.** La plantilla pendiente se detecta
  comparando la lista completa por igualdad (`evaluation.py:78-79`), así que cualquier edición
  manual la vuelve irrecuperable; `SCHEMA_VERSION = 1` se rechaza sin migración; no hay
  deduplicación por evaluador; y el ciclo leer-modificar-escribir (:92-98) no está protegido —
  `atomic_write_json` hace atómica la escritura, pero no la secuencia cargar→añadir→escribir— así
  que dos evaluaciones simultáneas por Telegram se pisan. **Cierre:** el centinela no depende de
  comparación exacta, hay ruta de migración, y un test de concurrencia prueba que no se pierde
  ninguna evaluación.

- [ ] **`P1` `test_real_gemini_smoke_run` exige un artefacto que el pipeline puede omitir por
  diseño.** El test afirma `required_artifacts <= manifest["artifacts"]` con `plan_review.json`
  dentro (`packages/top_down/tests/test_gemini_live.py:59`), pero `_critique_plan` degrada a aviso
  cuando el crítico falla y en ese caso **no** escribe ese artefacto. Observado el 2026-09-11: el run
  `20260911-170230` terminó `completed` con historia de 23 KB, las 11 etapas y un plan válido, y aun
  así el test falló porque el crítico murió con `ProviderError` y el pipeline conservó
  correctamente el primer plan válido. El test confunde "el crítico corrió" con "la ejecución es
  válida". **Cierre:** el test tolera la degradación documentada (comprobando el aviso
  correspondiente) o distingue artefactos obligatorios de condicionales, y deja de fallar por una
  caída transitoria del proveedor.

- [ ] **`P1` Armar un benchmark narrativo repetible.** Los prompts canónicos ya existen
  (`docs/prompts_top_down.md`) y `story_metrics.json`/`llm_usage.json` dan la parte automática;
  falta el procedimiento y el recolector, y ningún run con perfil tiene aún evaluación humana.
  **Cierre:** dos versiones del generador se comparan bajo las mismas condiciones, guardando la
  configuración necesaria para repetir el experimento.

## Documentación y despliegue

- [ ] **`P1` Dar persistencia real a lo desplegado.** El `Dockerfile` crea `/app/Stories/Top-Down`
  sin volumen: la cola SQLite y las historias viven en el filesystem efímero del contenedor, y
  `sync-railway-stories.ps1` (713 líneas) existe solo para rescatarlas antes de cada redeploy —
  es deuda de arquitectura, no de scripting. **Cierre:** artefactos y cola sobreviven a un
  redeploy sin intervención manual; el script queda como herramienta de archivado opcional.

- [ ] **`P2` Hacer mantenible `sync-railway-stories.ps1`.** Tras la última función (:463) el
  script corre en top level: tres guardas de preflight (:465-486) y luego un único `try` de 222
  líneas (:488-709) con un solo `catch` (:710-713) que aplana cualquier fallo a un mensaje, así que
  no se puede probar en aislamiento y el test tiene que cargar el archivo completo.
  `Test-ArchivedRun` (:160-261) convierte cualquier excepción en `State='invalid'` — un error de
  permisos y una corrupción real se ven igual — y el borrado depende de comparar el texto en inglés
  de un mensaje de la CLI de Railway (`Invoke-RemoteRunDeletion`, :431-463; la rama load-bearing es
  el `-match "agents cannot delete files"` de :451). **Cierre:** las funciones son un módulo
  importable con tests propios, fallos transitorios se distinguen de corrupción real, y el borrado
  no depende de un string de terceros.

- [ ] **`P1` Documentar los contratos públicos con ejemplos que se ejecuten.** Cubrir las
  fachadas de `asg_core`, `asg_top_down`, `asg_evaluation`, `asg_escape_room` más callbacks,
  errores y artefactos principales, con ejemplos mínimos de entrada/salida/fallo. **Cierre:** la
  documentación describe el contrato Top-Down 6.0, aclara compatibilidad con runs anteriores, y
  los ejemplos se validan en tests o CI.

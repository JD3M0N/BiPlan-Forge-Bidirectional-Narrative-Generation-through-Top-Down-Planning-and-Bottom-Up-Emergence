# Hoja de ruta

Tareas agrupadas por subsistema. Cada una tiene: qué falta, cuándo se considera cerrada
(**Cierre:**) y dónde está el problema en el código (**Evidencia:**).

**Prioridades.** `P0` bloquea la línea base o produce resultados incorrectos. `P1` hace falta
para sostener la tesis y la operación. `P2` es refactor que no cambia el comportamiento pero
abarata el resto.

**Orden sugerido:** los cuatro `P0` primero, empezando por las apps rotas (es el único que deja
una funcionalidad de usuario inservible); luego `P1` empezando por CI y el lector de evaluaciones;
por último `P2` empezando por dividir `pipeline.py`.

**Estado medido el 2026-09-07 sobre `7b435b6`** (árbol limpio): 216 pruebas (214 pasan, 2
omitidas), `ruff check .`, `ruff format --check .` (113 archivos) y `pip check` limpios.
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

- [ ] **`P0` Reparar la llamada a un método que ya no existe.** `95aa558` eliminó
  `StoryGenerator.run()` afirmando en su mensaje que quedaba «now used directly by its two callers»,
  pero no actualizó a ninguno de los dos: `apps/console/src/asg_console/top_down.py:49` hace
  `inspect.signature(generator.run)` y lanza `AttributeError` antes de generar nada (también llama
  `.run(...)` en :59 y :65), y `apps/telegram/src/asg_telegram/generators.py:58` repite la llamada.
  Hoy `StoryGenerator` solo define `generate` (`generator.py:74`). **La consola y el bot no pueden
  generar ninguna historia Top-Down.** La suite no lo detecta porque
  `apps/console/tests/test_app.py:88` monkeypatchea `StoryGenerator` con un doble que sí define
  `run(self, prompt)` (:66), de modo que el fallo queda enmascarado y CI sigue en verde.
  **Cierre:** ambas apps llaman al método que existe, y el doble de test deja de enmascarar la
  diferencia.

## Top-Down: perfiles y calibración

- [ ] **`P0` Confirmar que ningún plan inválido se guarda como válido.** El run
  `Stories/Top-Down/20260903-175604-el-dominio-escamado` quedó marcado `status: completed` pese a
  incumplir el contrato Expansiva; su `plan_review.json` aprueba una bifurcación que el grafo no
  tiene. **Cierre:** un test de regresión prueba que ningún `story_plan.json` puede persistirse sin
  pasar `validate_profile_structure`, y una revalidación del corpus separa runs anteriores al
  contrato de incumplimientos reales.
  **Evidencia (2026-09-07):** la revalidación del corpus ya está hecha — de 39 runs `completed` con
  perfil (más 22 anteriores al contrato, sin `narrative_profile`), 4 incumplen su contrato
  estructural, todos entre el 2026-09-01 y el 09-03. Tres son `generator_version` 6.0.0, es decir
  anteriores a `1bea0f1` (2026-09-03 14:43), que fue quien introdujo la regla rama→reunión: no son
  fallos, son runs previos a la norma. El único caso genuinamente anómalo es el que nombra este
  ítem: es 6.1.0 y se generó a las 17:56, después de la regla, y aun así carece de rama causal.
  Ningún run posterior al 2026-09-04 incumple (15+ runs, incluidos los 6 del 09-07). Queda
  pendiente **solo el test de regresión**.

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

- [ ] **`P0` Sacar los trabajos varados de `recovery_pending`.** `queue.py:200-206` marca los
  trabajos interrumpidos como `recovery_pending`, pero nada los saca de ahí: `finish` (:158-169)
  solo acepta `completed`/`failed`/`cancelled`, y `cancel_user` (:171-183) solo cancela trabajos en
  cola (`status='queued'`, :175), no en ejecución. Cada reinicio del bot durante una generación deja
  un trabajo bloqueado para siempre. **Cierre:** hay una transición explícita (reencolar, descartar
  o notificar) para `recovery_pending`, se puede cancelar un trabajo en ejecución, y hay test de
  reinicio que lo prueba.

- [ ] **`P1` Versionar la base de la cola.** `queue.py:43-53` solo hace `CREATE TABLE IF NOT
  EXISTS` sobre 14 columnas, sin `schema_version` ni `PRAGMA user_version`, así que una base vieja
  con otra forma sobrevive en silencio. Como la base está en `.gitignore`, el fallo solo aparece en
  producción. `average_duration` (:208-215) además exige exactamente 10 filas completadas para dar
  una estimación —devuelve `None` con 1 a 9— y es la última lectura posicional que queda en el
  archivo (:215). `enqueue` (:72-113) tampoco distingue «encolado» de «rechazado»: ante un duplicado
  devuelve el trabajo existente sin avisar (:82-88). **Cierre:** una base creada por una versión
  anterior migra sin perder trabajos activos, hay forma verificable de purgar registros viejos, y
  `enqueue` comunica el rechazo.

- [ ] **`P1` Mostrar el estado de la cola en la consola.** Trabajo en curso, usuario, posición,
  etapa, porcentaje y pendientes, actualizándose con la cola. **Cierre:** el operador ve la carga
  y la etapa sin mirar Telegram ni la SQLite.

- [ ] **`P1` Aceptar notas de voz como solicitud de historia.** Transcribir el audio recibido,
  mostrar el texto para que el usuario lo confirme o corrija, y solo entonces meterlo al flujo.
  **Cierre:** una nota de voz válida arranca una solicitud; formatos/tamaños/transcripciones
  inválidas dan un mensaje claro sin encolar nada.

- [ ] **`P2` Hacer real el adaptador del generador.** `generators.py:15-31` declara un
  `StoryGeneratorAdapter`, pero la app importa errores y formateo directo de `asg_top_down`
  (`generation.py:12-13`, `console.py:9`, `prompts.py:9`), detecta capacidades con
  `inspect.signature` (`generation.py:245` y las tres sondas de :255-261 — renombrar un parámetro
  apaga el progreso en silencio), y `_revision_warning_details` (:403-458) interpreta a mano tres
  esquemas de artefactos. `TopDownGenerator.generate` también reconstruye ajustes y proveedor en
  cada historia, así que el control de cuota no se comparte entre trabajos. **Cierre:** el
  adaptador expone progreso/errores/advertencias como contrato propio, la app no importa nada de
  `asg_top_down` fuera de la fábrica, y el proveedor se reutiliza entre trabajos.

- [ ] **`P2` Unificar reintentos de entrega y estados de conversación.**
  `_send_audio_with_retry` (`delivery.py:129-178`) y `_send_document_with_retry` (:189-237) son la
  misma máquina de reintentos escrita dos veces, sobre dos constantes con valores idénticos
  (`DOCUMENT_RETRY_DELAYS` y `AUDIO_RETRY_DELAYS`, :17-18, ambas `(1, 2, 4)`). Los estados de
  conversación son strings sueltos repartidos entre `handlers.py` (:116, :158, :163, :210, leídos
  en :140, :152, :168, :170, :176, :178, :239) y `generation.py:89-90`, que fija el quinto valor
  desde otro módulo. `handlers.py:271-281` reintenta sin límite si falla guardar una evaluación.
  **Cierre:** una sola política de reintentos parametrizada, estados como enum compartido, y
  reintento de evaluación acotado.

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

# Hoja de ruta

Tareas agrupadas por subsistema. Cada una tiene: qué falta, cuándo se considera cerrada
(**Cierre:**) y dónde está el problema en el código (**Evidencia:**).

**Prioridades.** `P0` bloquea la línea base o produce resultados incorrectos. `P1` hace falta
para sostener la tesis y la operación. `P2` es refactor que no cambia el comportamiento pero
abarata el resto.

**Orden sugerido:** los cinco `P0` primero; luego `P1` empezando por CI y el lector de
evaluaciones; por último `P2` empezando por dividir `pipeline.py`.

**Estado medido el 2026-09-05 sobre `9a94004`** (con la dedup de prompts/proveedor, la
temperatura por contrato y la activación de `E501` de esta sesión aplicadas en el árbol de
trabajo): 186 pruebas (184 pasan, 2 omitidas), `ruff check .`, `ruff format --check .` y
`pip check` limpios. Comparación de perfiles en
[docs/calibracion_perfiles.md](docs/calibracion_perfiles.md).

---

## Calidad e infraestructura

- [ ] **`P1` Meter las comprobaciones en CI.** No hay `.github/`. `pyproject.toml:3` solo colecta
  `test_*.py`, así que `tests/test_sync_railway_stories.ps1` nunca corre salvo a mano.
  **Cierre:** un pipeline instala el repo y corre Ruff, formato, pytest, `pip check` y el test de
  PowerShell en cada cambio; un fallo bloquea el merge.

- [x] **`P1` Activar el límite de línea que ya está declarado.** `pyproject.toml:8` fija
  `line-length = 100` pero `E501` no está en `select`, así que nunca se comprueba. **Cierre:** la
  regla está activa, las ~82 líneas que hoy la superan están corregidas, y una línea larga nueva
  rompe la comprobación. **Evidencia:** `E501` se añadió a `select` en `pyproject.toml:12`; las 82
  líneas que lo violaban (concentradas en `agents/review.py`, `agents/analyst.py`,
  `agents/planner.py` y `agents/writer.py`) se reenvolvieron sin cambiar el texto final de los
  prompts. `ruff check .` termina sin errores con la regla activa.

- [ ] **`P2` Cambiar el gate de docstrings a reglas del linter.** El test actual
  (`tests/test_source_documentation.py:25-27`) solo mira que exista texto ASCII, lo que ha dejado
  pasar docstrings inútiles ("Save json.", "Calculate details.") y obliga a documentar closures.
  Su regex de español además está rota (`"configuraci?n"`, línea 9) y nunca coincide. **Cierre:**
  las reglas `D` de Ruff cubren esto, el test a mano desaparece o se reduce a comprobar idioma, y
  no quedan docstrings vacíos de contenido.

## Core y audio

- [ ] **`P0` Hacer configurable y reproducible la voz de la narración.**
  `packages/core/src/asg_core/audio.py:76-79` devuelve `es-ES-ElviraNeural` con un `return`
  temprano, así que la selección real por `VoicesManager` (líneas 84-107) nunca se ejecuta para
  español; el test (`packages/core/tests/test_core.py:101-108`) espera `es-MX-NovelNeural`. La
  voz alternativa quedó como comentario. **Cierre:** la voz se elige por configuración (no por
  código), con fallback seguro, y hay tests para detección de idioma, selección, fallback,
  reintentos y limpieza de archivos parciales.

## Top-Down: perfiles y calibración

- [ ] **`P0` Confirmar que ningún plan inválido se guarda como válido.** El run
  `Stories/Top-Down/20260903-175604-el-dominio-escamado` quedó marcado `status: completed` pese a
  tener el mismo error estructural (`expansive profile requires a causal dependency branch...`)
  que ya había sido rechazado en un intento anterior; `plan_review.json` de ese run aprueba una
  bifurcación que el grafo no tiene. Una ejecución de control no reprodujo el fallo, así que podría
  ser un estado de código ya corregido. **Cierre:** un test de regresión prueba que ningún
  `story_plan.json` puede persistirse sin pasar `validate_profile_structure`, y una revalidación
  del corpus separa runs anteriores al contrato de incumplimientos reales.

- [ ] **`P0` Alargar de verdad las historias Expansivas.** Tras arreglar el `DramaCriticAgent`
  ya no son las menos densas por evento, pero siguen cortas: 3171-4102 palabras en tres pruebas,
  por debajo de las ~5000 esperadas para 9 eventos con escena completa. La única corrida con 5
  capítulos llegó a 456 palabras/evento (la más alta); las de 3 capítulos se quedaron en 352-418.
  Además 2 de 5 corridas Expansivas fallaron del todo por `PLOT_VALIDATION_FAILED`, y 6 de 9
  intentos de plan fueron rechazados por quedarse a un evento del mínimo de 9. **Cierre:** las
  Expansivas alcanzan de forma consistente más extensión, y la tasa de fallos de planificación
  baja de forma medible frente al 40%/67% observado.

- [ ] **`P0` Hacer que el perfil controle los capítulos.**
  `packages/top_down/src/asg_top_down/profiles.py:51-55` solo fija un mínimo de eventos; capítulos,
  personajes y subtramas quedan libres. Las tres corridas de control dieron igual 3 capítulos, y
  dentro de una Expansiva el primer capítulo concentró 4 de 9 eventos en 707 palabras mientras el
  tercero usó 1336 palabras para solo 3. **Cierre:** cada perfil fija una banda de capítulos y un
  reparto de eventos que evita que un capítulo se lleve medio libro.

- [ ] **`P1` Traducir lo que pide el usuario a un perfil narrativo.** Hoy la detección vive
  duplicada en tres sitios que pueden divergir: `agents/analyst.py:13-25`, la instrucción de
  sistema en `analyst.py:50-57`, y `apps/telegram/src/asg_telegram/prompts.py:29-40`. **Cierre:**
  casos representativos en español e inglés mapean de forma consistente a Esencial/Desarrollada/
  Expansiva, un perfil nombrado explícitamente gana, y queda registrada la justificación — sin
  prometer una longitud exacta.

- [ ] **`P1` Probar si una taxonomía de arquetipos mejora las historias.** Comparar, sobre los
  mismos prompts, historias con y sin guía taxonómica y medir el efecto en originalidad,
  coherencia y satisfacción. **Cierre:** el experimento y la decisión quedan documentados; si hay
  mejora, se añade como brief opcional y auditable sin resucitar la complejidad del subsistema
  anterior.

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

- [ ] **`P1` Dar al CLI lo mínimo para experimentos reproducibles.** `generate-story` solo acepta
  el prompt (`cli.py:25-29`): no hay `--profile`, `--output`, `--model` ni `--no-audio`; el perfil
  depende de una regex sobre el texto libre, y cada corrida genera el MP3 aunque solo importe la
  estructura. **Cierre:** se puede lanzar una tanda comparativa de tres perfiles sin editar
  prompts ni mover carpetas a mano, y `--profile` manda cuando se pasa.

- [ ] **`P2` Dividir `pipeline.py`.** 840 líneas y 26 métodos mezclando orquestación, reintentos,
  validación, ensamblado de Markdown, prompts de reparación y telemetría.
  `_revise_one_chapter` (:605-705) tiene 100 líneas y 10 parámetros; `_critique_plan` (:268-333)
  mete crítica + refinado + revalidación + fallback + tres escrituras en un solo `try`.
  **Cierre:** plan/borrador/revisión son unidades con estado y test propios, el estado deja de
  pasarse como parámetros posicionales, y los artefactos generados no cambian.

- [x] **`P2` Dejar de copiar la construcción de prompts y del proveedor.** La cabecera `STORY
  SPECIFICATION` + `NARRATIVE PROFILE CONTRACT` está pegada en 7 sitios (world.py, characters.py,
  planner.py, review.py x2, writer.py x2) y la construcción de `GeminiProvider` en 5 (cli.py,
  console/top_down.py, telegram/generators.py, test_gemini_live.py x2). **Cierre:** existe un
  helper de cabecera y una fábrica `provider_from_settings(settings)`, y nadie repite la
  construcción a mano. **Evidencia:** `story_specification_header` vive en `agents/base.py` y lo
  usan los 7 sitios; `provider_from_settings(settings)` vive en `provider.py` y lo usan los 5
  sitios de construcción, incluido el fake de `apps/console/tests/test_app.py` (que ahora
  monkeypatchea `GeminiProvider` en `asg_top_down.provider` en vez de en el módulo de la app).

- [x] **`P2` Fijar la temperatura por contrato, no por texto.** `provider.py:198-225` adivina la
  operación buscando subcadenas en el nombre del esquema, con el diccionario de temperaturas
  duplicado y una rama que nunca se alcanza para `analyst`. Cambiar una palabra del prompt cambia
  la temperatura sin avisar. **Cierre:** cada agente declara su perfil de generación de forma
  explícita, y un test fija la temperatura esperada por agente. **Evidencia:** `generate_structured`
  y `generate_text` exigen ahora un kwarg `profile` (Protocol incluido); los 9 call sites de
  agentes lo declaran explícitamente y `_temperature` solo hace un lookup contra
  `_DEFAULT_GENERATION_PROFILES` (dict único, sin duplicar). `DrafterAgent.presentation` pasó de
  caer por accidente en `"prose"` a declarar `"planning"`. Cuatro tests nuevos en
  `test_provider.py` fijan la temperatura por perfil, el rechazo de perfiles desconocidos y el
  merge de overrides con los defaults.

- [ ] **`P2` Dejar de reescribir artefactos enteros por cada llamada.** `append_llm_call`
  (`storage.py:106-115`) relee y reescribe todo `llm_calls.jsonl` y recalcula su SHA-256 en cada
  llamada; `llm_usage.json` se reescribe entero también; el manifiesto se regenera con cada
  artefacto. Un run de 9 capítulos hace decenas de reescrituras completas. **Cierre:** registrar
  una llamada es un anexado, el manifiesto se consolida al cerrar cada etapa, y los hashes siguen
  siendo correctos.

- [ ] **`P2` Resolver 4 abstracciones que ya no hacen nada.** `ChapterPlan` (`schemas.py:135-137`)
  es una subclase vacía pero pública y usada como tipo en ~10 sitios. `generation_profiles` y
  `structured_validation_retries` (`provider.py:172-173`) no los pasa ningún llamador, pero
  `GeminiProvider` sí los usa internamente — tocarlos es parte de la tarea de temperatura, no de
  esta. `topological_order` (`schemas.py:209`) se serializa en cada `story_plan.json`.
  `ArtifactValidationError` (`errors.py:62-71`) no se lanza en producción pero la usan los tests
  como doble genérico. **Cierre:** cada caso tiene decisión tomada (eliminar con migración, o
  quedarse explícitamente) y, si se elimina, hay test que prueba que nada dependía de él.

- [ ] **`P2` Quitar el estado mutable compartido del proveedor.** El pipeline muta
  `wait_callback`/`usage_callback` del proveedor y los limpia en un `finally`
  (`pipeline.py:102-103`); el limitador de peticiones es un singleton de proceso
  (`provider.py:32-33`). Dos corridas concurrentes con el mismo proveedor se pisarían. El
  `Protocol LanguageModelProvider` tampoco está anotado donde se usa. **Cierre:** los callbacks se
  pasan por llamada, la telemetría sale de una interfaz declarada, y el tipo del proveedor está
  anotado en las fachadas.

## Telegram

- [ ] **`P0` Sacar los trabajos varados de `recovery_pending`.** `queue.py:178-199` marca los
  trabajos interrumpidos como `recovery_pending`, pero nada los saca de ahí: `finish`
  (`queue.py:153`) solo acepta `completed`/`failed`/`cancelled`, y `cancel_user` (:164-176) solo
  cancela trabajos en cola, no en ejecución. Cada reinicio del bot durante una generación deja un
  trabajo bloqueado para siempre. **Cierre:** hay una transición explícita (reencolar, descartar o
  notificar) para `recovery_pending`, se puede cancelar un trabajo en ejecución, y hay test de
  reinicio que lo prueba.

- [ ] **`P1` Versionar la base de la cola.** `queue.py:41-51` solo hace `CREATE TABLE IF NOT
  EXISTS`, sin versión de esquema; `_job` (:62) lee por posición de columna, así que una columna
  nueva rompe la lectura de una base vieja. Como la base está en `.gitignore`, el fallo solo
  aparece en producción. `average_duration` (:208) además exige exactamente 10 filas completadas
  para dar una estimación. **Cierre:** una base creada por una versión anterior migra sin perder
  trabajos activos, y hay forma verificable de purgar registros viejos.

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
  `inspect.signature` (`generation.py:239-254` — renombrar un parámetro apaga el progreso en
  silencio), y `_revision_warning_details` (:399-456) interpreta a mano tres esquemas de
  artefactos. `TopDownGenerator.generate` también reconstruye ajustes y proveedor en cada
  historia, así que el control de cuota no se comparte entre trabajos. **Cierre:** el adaptador
  expone progreso/errores/advertencias como contrato propio, la app no importa nada de
  `asg_top_down` fuera de la fábrica, y el proveedor se reutiliza entre trabajos.

- [ ] **`P2` Unificar reintentos de entrega y estados de conversación.**
  `_send_document_with_retry` y `_send_audio_with_retry` (`delivery.py:129-237`) son la misma
  máquina de reintentos escrita dos veces; los estados de conversación son strings repartidos
  entre `handlers.py:116-209` y `generation.py:87`. `handlers.py:271-281` reintenta sin límite si
  falla guardar una evaluación, y `enqueue` (`queue.py:75-81`) no distingue «encolado» de
  «rechazado». **Cierre:** una sola política de reintentos parametrizada, estados como enum
  compartido, reintento de evaluación acotado, y `enqueue` comunica el rechazo.

## Evaluación y benchmark

- [ ] **`P1` Poder leer y agregar las evaluaciones humanas, no solo escribirlas.**
  `asg_evaluation` exporta `add_evaluation`, `create_evaluation_template`, `discover_stories` — sin
  lector, media, varianza ni acuerdo entre evaluadores. **Cierre:** hay carga y agregación por
  historia y por perfil, con tests, comparable entre versiones del generador.

- [ ] **`P1` Blindar el formato de `evaluation.json`.** La plantilla pendiente se detecta
  comparando la lista completa por igualdad (`evaluation.py:78-79`), así que cualquier edición
  manual la vuelve irrecuperable; `SCHEMA_VERSION = 1` se rechaza sin migración; no hay
  deduplicación por evaluador; y el ciclo leer-modificar-escribir (:88-99) no está protegido, así
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

- [ ] **`P2` Hacer mantenible `sync-railway-stories.ps1`.** Todo lo que sigue a la línea 464 son
  ~210 líneas sueltas dentro de un único `try`, así que no se puede probar en aislamiento y el
  test tiene que cargar el archivo completo. `Test-ArchivedRun` (:160-262) convierte cualquier
  excepción en `State='invalid'` — un error de permisos y una corrupción real se ven igual — y el
  borrado depende de comparar el texto en inglés de un mensaje de la CLI de Railway (:439-452).
  **Cierre:** las funciones son un módulo importable con tests propios, fallos transitorios se
  distinguen de corrupción real, y el borrado no depende de un string de terceros.

- [ ] **`P1` Documentar los contratos públicos con ejemplos que se ejecuten.** Cubrir las
  fachadas de `asg_core`, `asg_top_down`, `asg_evaluation`, `asg_escape_room` más callbacks,
  errores y artefactos principales, con ejemplos mínimos de entrada/salida/fallo. **Cierre:** la
  documentación describe el contrato Top-Down 6.0, aclara compatibilidad con runs anteriores, y
  los ejemplos se validan en tests o CI.

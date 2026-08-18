# Historial de cambios

Las versiones nuevas deben agregarse siempre encima de las versiones anteriores.

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
- Incrementada la versión de `asg-top-down` a `3.0.0` y actualizado el modelo
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

# Historial de cambios

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

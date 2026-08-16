# Historial de cambios

Las versiones nuevas deben agregarse siempre encima de las versiones anteriores.

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

# Historial de cambios

Las versiones nuevas deben agregarse siempre encima de las versiones anteriores.

## [1.6.0] - 2026-08-27

- Split handlers, generation coordination, and delivery retries.
- Reduced `app.py` to assembly and startup while preserving the SQLite queue.
- Adopted shared paths and filesystem helpers from `asg-core`.

## [1.5.0] - 2026-08-27

- Adaptado el generador Top-Down al contrato 5.0 sin opciones retiradas.
- Aclarado que los trabajos interrumpidos no se reanudan automáticamente.

## [1.4.0] - 2026-08-20

- Actualizada la dependencia a ASG Top-Down 4.0.
- Los trabajos interrumpidos quedan `recovery_pending`; la cola restante continúa
  y ya no se simula una reanudación creando un run nuevo.

## [1.3.0] - 2026-08-18

- Actualizada la dependencia mínima a ASG Top-Down 3.3.0 y conservada la entrega
  de historias generadas por el pipeline PPP modular.

## [1.1.7] - 2026-08-18

- Actualizada la dependencia mínima a ASG Top-Down 3.2.0 para enriquecer prompts
  en inglés y conservar el idioma final pedido o detectado.

## [1.1.6] - 2026-08-18

- Actualizada la dependencia mínima a ASG Top-Down 3.1.0 para generar historias
  con las nuevas taxonomías flexibles sin cambiar el idioma final solicitado.

## [1.1.5] - 2026-08-16

- Actualizada la dependencia mínima a ASG Top-Down 2.0.5 para impedir falsos
  rechazos CPN cuando los beats de cierre ya están reservados para el CEN.

## [1.1.4] - 2026-08-16

- Mostradas causas estructuradas y trazas locales redactadas para errores
  inesperados de generación, incluyendo código, etapa y ejecución sin exponer
  credenciales.
- Añadidos avisos cuando se entrega una historia completada con advertencias de
  calidad, manteniendo disponible su evaluación humana.
- Conectado `STORY_MAX_ARTIFACT_RETRIES` tanto para generaciones nuevas como
  para reinicios de trabajos interrumpidos.
- Documentado que las ejecuciones parciales se reinician desde `request.json`
  en un directorio nuevo y que solo las historias terminadas se reutilizan.

## [1.1.3] - 2026-08-16

- Actualizada la dependencia mínima a ASG Top-Down 2.0.3 para impedir que las
  revisiones CPN recuperen IDs de craft ya consumidos.

## [1.1.2] - 2026-08-16

- Actualizada la dependencia mínima a ASG Top-Down 2.0.2 para que revisiones CPN
  inválidas consuman un reintento sin interrumpir inmediatamente la historia.

## [1.1.1] - 2026-08-16

- Actualizada la dependencia mínima a ASG Top-Down 2.0.1 para probar el contrato
  de craft y el ciclo crítico-reescritor desde Telegram.

## [1.1.0] - 2026-08-09

- Migrado el generador Top-Down de Telegram a ASG Top-Down 2.0 y sus artefactos
  incrementales.
- Conectadas la configuración del modelo de embeddings y la cantidad máxima de
  reintentos por CPN.

## [1.0.1] - 2026-08-09

- Conectada la extensión predeterminada configurable con el generador
  Top-Down.
- Renombrada la prueba principal de Telegram para evitar colisiones al ejecutar
  la suite completa del repositorio.

## [1.0.0] - 2026-08-09

- Inicio formal del historial de versiones de Telegram.

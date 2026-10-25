# Historial de cambios

## [0.2.1] - 2026-10-24

- Cotas internas al día: `asg-core>=0.8.0`, `asg-evaluation>=2.0.0` y `asg-stagecraft>=7.21.0`.
  Declaraba `asg-evaluation>=0.8.0`, que cruza un cambio incompatible como si no lo fuera.
- Sin cambios de endpoints, de interfaz ni de comportamiento.

## [0.2.0] - 2026-09-28

- `/api/health` devuelve `stage_model`, el modelo propio de la función (`GEMINI_STAGE_MODEL`) o
  `null`, y la barra de estado lo muestra junto al modelo principal.
- La comparación gana el eje «Modelo de la función», que llega de `asg-evaluation`. Exige
  `asg-stagecraft>=7.4.0`.

## [0.1.0] - 2026-09-27

- Primera versión de StageCraft, la interfaz gráfica local de Stagecraft (`asg-studio`): vistas
  Crear, Funciones y Comparar; cola de generación con progreso en vivo y cancelación; opciones
  pintadas desde un catálogo, con las pendientes deshabilitadas; modo `--demo`.

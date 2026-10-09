# Historial de cambios

## [3.2.1] - 2026-10-09

- «Evaluar historia» ya no ofrece los runs de `Stories/Bottom-Up/`: son registros de acciones
  del escape room retirado, no historias. Los datos se conservan y los informes los siguen
  leyendo.

## [3.2.0] - 2026-09-28

- Al generar una historia simulada cuya función tiene modelo propio (`GEMINI_STAGE_MODEL`),
  anuncia los dos: «Generando con X (función: Y)». Exige `asg-stagecraft>=7.4.0`.

## [3.1.0] - 2026-09-27

- Construye las opciones con `GenerationOptions` y usa las etiquetas de voz de
  `formats.VOICE_CHOICES`, que incluyen la tercera persona limitada. Con una visión atada a un
  personaje, pregunta cuál (Enter deja al protagonista).

## [3.0.1] - 2026-09-26

- Cotas internas al mínimo real: `asg-stagecraft` 7.2.0, `asg-evaluation` 0.6.0 y `asg-core`
  0.5.1. Pedía `asg-stagecraft>=6.0.0` aunque importa API 7.x.

## [3.0.0] - 2026-09-26

- Retirado el menú Bottom-Up junto con el paquete `asg-escape-room`: la consola queda con
  Stagecraft y la evaluación humana.
- Eliminadas de la API pública `ConsoleRenderer`, `EscapeRoomVisualizer` y `VisualOutcome`, y el
  parámetro `bottom_up` de `ConsoleApp`.
- Retirado el caso que aceptaba una ruta como resultado de `generate()`: siempre devuelve un
  `StoryRun`.
- La salida se configura en UTF-8 con `asg_core.use_utf8_output`, así que los acentos del menú
  llegan intactos también a una tubería o a una consola heredada de Windows.

## 2.0.0

- Adoptada la API Top-Down 6.0 basada en perfiles narrativos y eliminada la
  configuración `default_target_words`.

Las versiones nuevas deben agregarse siempre encima de las versiones anteriores.

## [1.6.0] - 2026-08-27

- Split Top-Down, Bottom-Up, and evaluation menus from `ConsoleApp`.
- Updated dependencies and paths for the standard monorepo layout.

## [1.5.0] - 2026-08-27

- Adaptada la generación Top-Down al constructor y configuración mínimos de 5.0.
- Retiradas opciones sin uso del pipeline anterior.

## [1.4.0] - 2026-08-20

- Actualizada la dependencia a ASG Top-Down 4.0 y mantenida la interfaz pública
  `StoryGenerator.generate/run` y la lectura de `story.md` históricos.

## [1.3.0] - 2026-08-18

- Actualizada la dependencia mínima a ASG Top-Down 3.3.0 y conservada la salida
  canónica de historias del nuevo pipeline PPP modular.

## [1.2.0] - 2026-08-18

- Eliminado el modo de tres alternativas y la dependencia de Prompt-crafter.
- Simplificada la generación Top-Down a un único prompt, enriquecido internamente
  por ASG Top-Down 3.2.

## [1.1.6] - 2026-08-18

- Actualizada la dependencia mínima a ASG Top-Down 3.1.0 para usar las nuevas
  taxonomías narrativas flexibles y sus artefactos de planificación auditables.

## [1.1.5] - 2026-08-16

- Actualizada la dependencia mínima a ASG Top-Down 2.0.5 para usar la
  adjudicación determinista del scope de craft durante la planificación CPN.

## [1.1.4] - 2026-08-16

- Actualizada la dependencia mínima a ASG Top-Down 2.0.4 para consumir la
  generación reparable y los artefactos de diagnóstico nuevos.

## [1.1.3] - 2026-08-16

- Actualizada la dependencia mínima a ASG Top-Down 2.0.3 para impedir que las
  revisiones CPN recuperen IDs de craft ya consumidos.

## [1.1.2] - 2026-08-16

- Actualizada la dependencia mínima a ASG Top-Down 2.0.2 para recuperar
  revisiones CPN inválidas y conservar checkpoints de planificación.

## [1.1.1] - 2026-08-16

- Actualizada la dependencia mínima a ASG Top-Down 2.0.1 para probar el contrato
  de craft y el ciclo crítico-reescritor desde la consola unificada.

## [1.1.0] - 2026-08-09

- Migrada la generación Top-Down de la consola al nuevo `StoryGenerator`
  incremental de ASG Top-Down 2.0.
- Adaptado el manejo del resultado `StoryRun` conservando la presentación de la
  ruta final de `story.md`.

## [1.0.1] - 2026-08-09

- Conectada la extensión predeterminada configurable con el orquestador
  Top-Down.

## [1.0.0] - 2026-08-09

- Inicio formal del historial de versiones de Console.

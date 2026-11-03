# Fichas heredadas

Las fichas abiertas del antiguo `TODO.md`, copiadas íntegras y agrupadas por la fase que las
absorbe. Son material de partida para `/phase cards Pxx`: al escribir las tarjetas de una fase,
lo que entra en una tarjeta se borra de aquí y lo que se aplaza pasa a
[idea-bank](future/idea-bank.md). El original sigue en
`git show planning-before-phase:TODO.md`.

Las cifras y fechas son las de su medición; no se han vuelto a comprobar.

## P05 · Análisis horizontal

### EXP-1 · Medir la historia simulada contra la narrativa

*Área:* experimento · *Cuota:* ~1.150 llamadas para 3 prompts × 3 repeticiones, varios días de
cuota gratuita · *Depende de:* SIM-1, SIM-2, SIM-14, MED-3; mejor con MED-5

- **Síntoma.** El formato simulado existe desde 7.0, y sigue sin saberse si una historia narrada
  desde una función es mejor, peor o solo distinta de una escrita directamente.
  - **Hoy hay un solo par**, y con planes distintos: la corrida de control narrativa contra
    `070539` y `072847`, todos del prompt 03 Esencial.
  - **Lo que ya se ve en ese par.** La narrativa tiene 0,75 de diálogo y 2.476 palabras, y las
    simuladas 0,52 y 0,49 de diálogo con 1.219 y 1.955 palabras.
  - **El clímax sale corto en los dos formatos.** En los cuatro runs 7.x del prompt 03 que
    terminaron, el último capítulo es el más corto de su historia; en el corpus lo es en 31 de
    112, cerca del azar.
  - **Se cerró la ficha «El desenlace sigue resumiendo».** El último capítulo era el más mudo en
    13 de 21 historias de 6.6.0, y desde el 20-09 lo es en 2 de 12 (3 contando empates). Se sigue
    vigilando aquí.
- **Qué hacer.**
  - Una matriz con los mismos prompts canónicos en `narrative` y en `simulated`, mismo perfil e,
    idealmente, mismo plan (MED-5), siguiendo el protocolo.
  - Leer la comparación a ciegas y las cifras de `asg-report-features` (capas T y P):
    `script_echo` (si sale alto, los actores recitaron y la simulación no aporta) y
    `beat_completion_ratio`.
  - Leer también el coste por agente (capa K), y si el último capítulo es el más mudo o el más
    corto.
- **Hecho cuando.** Hay una decisión escrita, con cifras, en `docs/resumen.md`.

## P06 · Estudio humano

### EXP-4 · Evaluación humana por pares a ciegas

*Área:* experimento · *Cuota:* votar no consume cuota; generar y extraer sí · *Depende de:*
MED-8 y la revisión de MED-9

- **Síntoma.** El instrumento está listo (2026-10-12): el bot `asg-telegram` 5.0.0 recoge
  historias de los participantes (Top-Down o híbrido, libre o guiada, con audio) y, cuando el
  investigador abre la votación, presenta pares a ciegas con una pregunta cada vez. La base de
  `Evaluations/estudio` (75 votos sobre 15 historias de 7.21) es sintética: votaron 5 agentes
  Claude Opus, no lectores, y no cuenta (`decisions.md` §2). Falta el estudio real sobre 7.22,
  diseñado en P06.1.
- **Qué hacer.**
  - Arrancar el bot en la PC del investigador (`asg-telegram`) y pedir a los participantes
    que creen historias, una por una.
  - Añadir dos líneas base de un solo prompt (`asg-baseline` y `asg-study add`) y
    excluir lo que no deba entrar.
  - `asg-study open` cuando haya bastantes historias; votar hasta el tope de 15 preguntas
    por lector; `close` y `export`. Guía en [apps/telegram/README.md](../apps/telegram/README.md).
  - `asg-preferences`: cobertura, abstenciones, acuerdo e intervalos por lector, con y sin el
    autor. No inventar un ranking global si el grafo queda desconectado.
- **Hecho cuando.** El estudio real publica las tres preferencias con su cobertura y
  limitaciones.
- **Ojo.** Prompts y enfoques libres permiten asociaciones, no aislar causalmente un parámetro.
  Las bases de los estudios anteriores (`Evaluations/pack-prueba`, `Evaluations/telegram-rolling`)
  quedan como datos y el estudio nuevo no las abre.

## P09 · Resultados reproducibles

### ING-8 · Documentar los contratos públicos y rellenar el README

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* el cierre del proyecto

- **Síntoma.**
  - `README.md` de la raíz ya es una portada corta (estructura y puesta en marcha); falta el
    contrato de artefactos.
  - Las fachadas no tienen ejemplos que se ejecuten.
  - `packages/core/README.md` sigue en inglés y los demás están en español; lo mismo
    pasa con los changelogs de `core` y `evaluation` frente a los otros tres.
- **Qué hacer.** Al cerrar:
  - ejemplos mínimos de entrada, salida y fallo para `asg_core`, `asg_stagecraft` y
    `asg_evaluation`;
  - el contrato de artefactos en el README de la raíz, en UTF-8.
- **Hecho cuando.** Los ejemplos se validan en los tests o en CI, y la documentación describe el
  contrato de artefactos vigente y su compatibilidad con los runs anteriores.

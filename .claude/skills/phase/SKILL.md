---
name: phase
description: Ejecuta una tarea del roadmap de la tesis (planning/roadmap.md) en una sesión y un commit, o escribe las tarjetas de una fase. Usar cuando el usuario escribe /phase, /phase P04.2 o /phase cards P04, o pide «la siguiente tarea» o «las tarjetas de la fase».
---

# /phase

Trabajo por fases de la tesis. La guía para Josue está en `planning/phase.md`; aquí están las
reglas que sigues tú. Escribe todo en español (los docstrings, en inglés ASCII, como manda
`AGENTS.md`).

## Usos

| Invocación | Qué haces |
|---|---|
| `/phase` | La siguiente tarea: la que dice «Siguiente» en «Estado actual» de `planning/roadmap.md`. |
| `/phase P04.2` | Esa tarea concreta, si tiene tarjeta. |
| `/phase cards P04` | Escribir las tarjetas de la fase P04. No implementa nada. |

Si la tarea pedida no tiene tarjeta, para y dilo: propone `/phase cards Pxx`.

## Ejecutar una tarea

1. **Árbol.** `git status --short`. Si hay cambios sin commit, enséñalos y pregunta qué hacer
   (seguir con ellos, guardarlos aparte o descartarlos); no los toques sin respuesta. Se trabaja
   en `main`.
2. **Leer poco.** Lee `AGENTS.md`, el «Estado actual» del roadmap y la tarjeta. Después lee
   **solo** lo que dice **Lee**. Si `graphify-out/graph.json` existe, oriéntate con
   `graphify query "<pregunta>"` antes de abrir archivos que la tarjeta no nombra.
3. **Reglas del tutor.** Si la tarea toca evaluación, rasgos, extractor, estudio humano, juez,
   ranking, análisis o tesis, lee `planning/decisions.md` §1 (T1–T11) y comprueba la tarjeta
   contra ellas. Si la tarjeta o tu solución chocan con una regla (una escala 1–10, un LLM que
   juzga calidad, el juez como función objetivo dentro de la tesis, más de tres criterios,
   validar el juez solo dentro de muestra…), **para y avisa**. Lee también `decisions.md` §2–§3
   si la tarea toca método o el generador congelado.
4. **Modo.**
   - `S`: sigue.
   - `S+P`: enseña un plan corto (archivos, pasos, riesgos) y espera el «ok».
   - `O`: enseña 2–4 opciones con pros, contras y tu recomendación, y espera. Sugiere Opus si
     la decisión es difícil.
5. **Cuota.** Si la tarjeta gasta llamadas reales, enseña antes el coste (`--dry-run` o la
   estimación del protocolo de `decisions.md` §4) y espera. Nunca `RUN_GEMINI_LIVE=1` ni una
   llamada real que la tarjeta no pida. No imprimas claves.
6. **Implementar** solo lo que dice **Haz**, respetando **No hagas** y `AGENTS.md` (límites,
   compatibilidad, idioma). Nunca borres `Stories/`, `Evaluations/`, `redaccion/` ni datos de
   investigación. No edites `packages/evaluation/planilla/rasgos.csv` salvo que la tarjeta lo
   diga: cambia la huella del catálogo.
7. **Probar.**
   - `.\run-tests.ps1` (suite completa; nunca `pytest` directo) y `.\quality.ps1`.
   - Si cambió una versión: `python -m pip install --no-deps -e <paquete>` antes de probar.
   - En la tesis: `latexmk` en `redaccion/` compila sin errores.
   - Lo que pida **Prueba**.
   - Si falla una prueba ajena a la tarea: anótala en la tarjeta que corresponda y sigue; si
     bloquea el commit, para y avisa.
8. **Cerrar.**
   - Borra la tarjeta del roadmap y añade a «Hechas» una línea: `P04.2 · <qué quedó>`.
   - Pon al día «Siguiente» y, si cambian, las versiones del «Estado actual».
   - Si absorbiste una ficha de `planning/fichas.md`, bórrala de allí.
   - Si tocaste código de un paquete: sube su parche y escribe su `CHANGELOG.md` (con la ID de
     la tarea). Las tareas solo de docs, planning o tesis no suben versión. `PIPELINE_VERSION`
     solo cambia si la tarjeta lo dice.
   - Commit en `main` con mensaje `P04.2: <resumen en español>`. **Sin** `Co-Authored-By`.
     **Sin** push.
9. **Parar y resumir:** qué cambió (archivos y por qué), qué probaste y con qué resultado, y
   cuál es la siguiente tarea. Si era la última de la fase, dilo y recuerda
   `/clear`, `/model opus`, `/phase cards P<siguiente>`. Si cierra un hito (H0–H6), dilo y
   recuerda qué hace Josue en él (`planning/phase.md`).

**Una tarea por sesión.** Si al leer ves que no cabe en una sesión, para antes de implementar y
propone partir la tarjeta en dos; con el «ok», reescríbelas y haz solo la primera.

## Escribir las tarjetas de una fase (`/phase cards P04`)

No implementes nada.

1. Lee el bloque de la fase en el roadmap, sus fichas en `planning/fichas.md`,
   `planning/decisions.md` entero, el contrato del subsistema (`docs/architecture/*.md`,
   `packages/evaluation/METODOLOGIA.md` para evaluación) y el código real que la fase va a tocar
   (usa el grafo para encontrarlo).
2. Parte la fase en tareas de **una sesión** cada una (P04.1, P04.2…). Una decisión de diseño es
   su propia tarea en modo `O`, al principio.
3. Escribe cada tarjeta con el formato del roadmap: **Modo · Cuota · Paquete**, **Lee**, **Haz**,
   **No hagas**, **Prueba**, **Hecho cuando**. Rutas y funciones concretas, nunca números de
   línea. **Lee** corto: solo lo necesario. **Hecho cuando**, verificable.
4. Comprueba las tarjetas contra las reglas del tutor; di en el bloque de la fase qué reglas
   cubre.
5. Lee `TODO.md` (es de Josue: **solo lectura**) y propone: qué encaja ya en una tarjeta, qué va
   a `planning/future/idea-bank.md` y qué se queda. Las fichas de `fichas.md` de esta fase que no
   entren en ninguna tarjeta pasan a idea-bank con su ID.
6. Enseña las tarjetas y espera aprobación o correcciones.
7. Con el «ok»: actualiza «Siguiente» y haz un commit solo de documentación,
   `P04: tarjetas`.

## Nunca

- Escribir en `TODO.md`.
- Hacer varias tareas en una sesión, o una tarea sin tarjeta.
- Cambiar una regla del tutor o una decisión de `decisions.md` sin que Josue lo apruebe.
- Push, `--no-verify`, o commits con coautor.

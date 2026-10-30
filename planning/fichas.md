# Fichas heredadas

Las fichas abiertas del antiguo `TODO.md`, copiadas íntegras y agrupadas por la fase que las
absorbe. Son material de partida para `/phase cards Pxx`: al escribir las tarjetas de una fase,
lo que entra en una tarjeta se borra de aquí y lo que se aplaza pasa a
[idea-bank](future/idea-bank.md). El original sigue en
`git show planning-before-phase:TODO.md`.

Las cifras y fechas son las de su medición; no se han vuelto a comprobar.

## P05 · Análisis horizontal

### MED-3 · Un runner de matrices con presupuesto

*Área:* medición · *Cuota:* sin cuota (la gasta quien lo lance) · *Depende de:* —

- **Síntoma.**
  - Toda ficha `EXP` necesita una matriz, y hoy se lanzan a mano, run a run.
  - Así murió el par `054422`/`060405`: el segundo se lanzó sin saber que la cuota se había
    agotado.
  - Nada registra qué celdas de una matriz faltan ni con qué configuración corrió cada una.
- **Qué hacer.** Un comando que:
  - lea una matriz: prompts del catálogo por marcador, formatos, perfiles, brazos como
    `--actor-memory` o `--script-method`, y repeticiones;
  - estime su coste con `tools/budget.preflight` y corra en serie;
  - se pueda interrumpir y reanudar saltando las celdas completadas;
  - escriba un manifiesto con cada celda, su run y su configuración.
- **Hecho cuando.**
  - Una matriz interrumpida a mitad se completa al relanzarla, sin repetir runs.
  - Su manifiesto basta para pasar los runs a StageCraft y a `asg-report-features` por celda.

### MED-5 · Comparar formatos y métodos desde un mismo plan congelado

*Área:* medición · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.**
  - Cada run genera su propio plan. Al comparar narrativa con simulada, o guion nativo con
    adaptado, la varianza de planificación se mezcla con la de escritura.
  - Los cuatro runs 7.x del prompt 03 que terminaron resuelven el mismo misterio de cuatro formas
    distintas.
  - Era una idea solo para los métodos de guion. Es lo que hace interpretables EXP-1 y EXP-3 con
    n pequeño.
- **Qué hacer.**
  - Un `--plan-from <run>` que reutilice `request.json`, `world.json`, `characters.json`,
    `story_plan.json` y el ledger de un run terminado, y arranque en la primera etapa de escritura
    del formato pedido.
  - El run nuevo registra de qué run salió su plan.
- **Hecho cuando.**
  - Dos runs de formatos distintos con el mismo `--plan-from` tienen un `story_plan.json`
    idéntico byte a byte.
  - Los informes pueden agrupar por plan de origen.
- **Ojo.** El run de origen tiene que ser de una versión que el código aún lea
  (`SUPPORTED_PIPELINE_VERSIONS`).


**Avance 7.5:** `--plan-from` ya empareja funciones simuladas con el mismo plan, guion y casting; queda extenderlo a formatos distintos y agrupar por origen en los informes.

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
  investigador abre la votación, presenta pares a ciegas con una pregunta cada vez. Hay un
  piloto (`Evaluations/estudio`, 2026-10-28): 75 votos de 7 lectores sobre 15 historias de 7.21,
  3 de ellas líneas base. Es anterior a la congelación, así que se conserva fuera del estudio de
  la tesis (`decisions.md` §2, P03.1). Falta el estudio real sobre 7.22.
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

### OPS-3 · El audio da 403 en las dos máquinas

*Área:* despliegue · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.** 9 de 9 historias de los amigos sin audio: `WSServerHandshakeError: 403` de
  `speech.platform.bing.com` en edge-tts 7.2.8, la última publicada. Pasa igual en esta PC, y
  probando versiones de Chromium más nuevas en sus constantes también: no es el pin.
- **Qué hacer.** Probar desde otra red o con VPN para separar un bloqueo por región de un cambio
  del servicio; si es el servicio, esperar una versión nueva de edge-tts o cambiar de motor de voz
  en `asg_core/audio.py`.
- **Hecho cuando.** Un `asg-generate` con audio deja `story.mp3` en las dos máquinas.

## P07 · Juez aprendido

### EXP-7 · El juez aprendido de los pares humanos

*Área:* experimento · *Cuota:* entrenamiento sin cuota · *Depende de:* EXP-4

- **Síntoma.** `train_judge` (`packages/evaluation/src/asg_evaluation/judge.py`) ya exige un
  protocolo de extracción homogéneo y valida fuera de muestra, pero los tres jueces solo se han
  entrenado con votos ficticios: no demuestran generalización.
- **Qué hacer.**
  - Entrenar con los votos reales, manteniendo las 27 entradas textuales, L2 sin intercepto,
    preprocesamiento ajustado solo con historias de entrenamiento y validación por historias y
    por familias de premisa.
  - Publicar frente a azar y a longitud sola: pesos, versiones, cobertura de predicciones,
    acierto y concordancia fuera de muestra.
  - Informar perturbaciones sin exigir que todas empeoren los tres criterios.
- **Hecho cuando.** El informe experimental publica generalización y limitaciones con datos
  reales.
- **Ojo.** Un buen ajuste dentro de muestra no acredita calidad. Si el juez no generaliza, sigue
  siendo un resultado experimental válido y debe presentarse como tal.

## P08 · Ranking y diez mejores

### EXP-8 · Ranking del corpus y análisis de las diez mejores

*Área:* experimento · *Cuota:* ranking sin cuota con extracciones compatibles · *Depende de:*
EXP-7

- **Síntoma.** `asg-rank --study` ya ordena por los comandos públicos las once historias de
  la demo, pero las fichas de las diez mejores salen vacías y no hay corpus real extraído.
- **Qué hacer.**
  - Aplicar el juez al corpus real elegible y publicar tres rankings principales y el combinado
    auxiliar con normalización fijada al entrenar; detallar versiones, formatos y exclusiones.
  - Leer diez historias seleccionadas por el ranking y completar sus fortalezas, debilidades,
    evidencias, configuración y proceso; enlazar el análisis horizontal.
- **Hecho cuando.** Corpus real ordenado y diez análisis cualitativos cumplimentados, con
  limitaciones y exclusiones explícitas.
- **Ojo.** No usar el juez para seleccionar automáticamente qué generar: el tutor lo deja
  fuera de esta tesis [06:21–07:43].

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

# Fichas heredadas

Las fichas abiertas del antiguo `TODO.md`, copiadas íntegras y agrupadas por la fase que las
absorbe. Son material de partida para `/phase cards Pxx`: al escribir las tarjetas de una fase,
lo que entra en una tarjeta se borra de aquí y lo que se aplaza pasa a
[idea-bank](future/idea-bank.md). El original sigue en
`git show planning-before-phase:TODO.md`.

Las cifras y fechas son las de su medición; no se han vuelto a comprobar.

## P02 · Congelar el generador (absorbidas por las tarjetas P02.1–P02.5)

### TD-9 · El plan no cumple el brief

*Área:* top-down · *Cuota:* ~30 llamadas (un plan Expansivo con brief) · *Depende de:* —

- **Síntoma.** En `20261013-180025-las-islas-del-cielo` el brief pedía:
  - el ascenso por la Columna y la exploración de cada lugar (Nidos, Mercado, Jardines,
    Archivo, Hondonada, Raíz);
  - una tripulación que se divide entre quedarse, volver y sacar provecho;
  - un final abierto: quién baja, quién se queda y qué paga cada uno.

  El plan tiene 10 eventos. No hay ascenso ni Nidos, no se ve la división, y su último evento es
  «guía a Zéfara hacia un equilibrio estable», un éxito sin precio. `plan_review.json` lo aprobó.
  El planificador solo lee el `processed_prompt` del analista, que resume la trama y pierde sus
  giros.
- **Qué hacer.**
  - Con brief, mandar la trama literal (`brief.plot`) al planificador y al crítico de plan como
    canon, igual que `authored_cast_block` hace con el reparto en 7.13.
  - Que el crítico de plan compruebe cada giro de esa trama y el tipo de final pedido.
- **Hecho cuando.** Un plan Expansivo de los navegantes contiene el ascenso, la división de la
  tripulación y una decisión final con pérdida, y el crítico rechaza un plan sin ellos.
- **Implementado en 7.14** (`brief.authored_plot_block` llega al planificador y al crítico);
  falta medirlo en real.
- **7.20.** Una ficha pegada como prompt libre se lee como `--brief`
  (`StoryBrief.from_prompt`).
  - Los runs 7.19 de las islas la habían pegado así, y no recibieron ni el reparto ni la trama
    como canon.
  - «Historia extensa» elige ya Expansiva.
- **Ruido sin medir.** Beats forzados del mismo brief Esencial: 1/6 (7.14), 2/5 (7.15) y 4/6
  (7.15.1). Con un run por versión no se puede atribuir la diferencia a un cambio: hace falta
  medir 2 o 3 runs por versión.
- **Ojo.** Sin brief, el prompt no debe cambiar: el corpus de prompts libres sigue comparable.

### SIM-14 · Un actor se sale de la ficción y el log lo acepta

*Área:* función simulada · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.** En `Stagecraft/20260927-163733-*`, turno `chap_2-scene-1-t005`, Mara dijo «I am
  checking the import paths for `Model` in the Superset models structure» y su acción fue
  «Examine the imports in `superset/models/core.py`».
  - El turno pasó los seis rechazos de `stage/validation.py`: no está vacío, no lleva un id del
    plan, no pasa de 45 palabras, no está en primera persona y no repite nada.
  - Entró en `turns.jsonl`, en `transcript.md`, en `performance.json` y en la memoria de tres
    personajes, de donde se pudo recuperar en turnos posteriores.
  - Fue el segundo intento del turno: el primero se rechazó por `REPEATED_ACTION`.
  - El juez de la auditoría lo marcó con severidad 5 y es la **única** fuga de los dos runs 7.2.
  - Se salvó por el narrador, que lo omitió: no llegó a `story.md`.
- **Qué hacer.** Un rechazo determinista de lo que no pertenece a la ficción, en el idioma ASCII
  inglés de los demás, con la reinyección de siempre. Señales barajables sin tocar el plan: habla o
  acción cuyo idioma no es el de la ficción, y vocabulario de código (rutas con `/` y extensión,
  identificadores con guion bajo, comillas invertidas).
- **Hecho cuando.** Hay un test con un turno de ese tipo que se rechaza y se reintenta, y ningún
  run nuevo trae en su log una línea ajena al mundo de la ficción.
- **Ojo.** El detector va en `stage/validation.py`, donde ninguna cifra viaja al prompt. Vigilar el
  falso positivo: una réplica corta con un nombre propio extranjero no es un turno roto.

### TD-2 · La ficción se planifica en inglés y se filtra a la historia

*Área:* top-down · *Cuota:* ~17 llamadas por formato para validar · *Depende de:* —

- **Síntoma.** El plan, el mundo y los personajes se escriben en inglés, y lo que se escapa llega
  al lector:
  - **El género se pierde en la traducción.** El inglés no marca género en los oficios.
    - En la corrida de control, «la médica de la isla» del prompt 03 pasó a
      `role: "Island Doctor"` y después a «el doctor Vargas».
    - En `072847` el dossier decía «Mujer de unos 45 años» y el narrador escribió «El doctor
      Mendoza» seis veces.
  - **Slugs en inglés.** 17 slugs en inglés salieron de prompts en español (`the-oxygen-ledger`),
    porque el slug sale del working title, que está en inglés. Los títulos de acto, que en 2 de 3
    guiones nativos se imprimían en inglés, ya los resuelve `assemble_play` desde la presentación
    localizada (7.2.0).
  - **El crítico pide lo que el Writer no puede cambiar.** En `054422` pidió `fix_act_headings` y
    el Writer gastó 3 revisiones (unos 27k tokens) en un rótulo que no controla.
  - **Nombres, roles y objetivos.**
    - Aparecen «Thomas Brennan» y «Julian Vance» en historias en español, y roles como «Archivist
      and Investigator».
    - Hay objetivos de escena en inglés, uno en primera persona: «Defend my personal bag…».
    - Faltan tildes en nombres y títulos: «Tobias», «Julian», «La Anomalia Mecanica».
- **Qué hacer.**
  - Fijar el contrato. Los ids y la estructura pueden seguir en inglés, pero todo campo que pueda
    llegar al lector (nombres, roles, títulos, lugares, objetos, objetivos) va en el idioma de la
    ficción y con su género.
  - Sacar el slug del título localizado.
  - Que el crítico no levante notas sobre lo que el Writer no controla.
- **Medido en 7.2.** En el formato simulado esto sale ya bien: los dos runs tienen slug, títulos
  de capítulo, roles y `public_face` en español, y el género coincide con la petición (la médica
  del prompt 03 es «Mujer de unos cincuenta años»). Lo que queda en inglés es lo que no ve el
  lector y lo del director (SIM-2). Falta comprobarlo en `narrative` y en `script`.
- **Hecho cuando.**
  - En runs nuevos de cada formato, el slug, los nombres y los roles están en español.
  - El género de cada personaje coincide con el de la petición.
- **Ojo.**
  - Los `ValueError` de `graph.py` y compañía siguen en inglés a propósito: esto va del contenido
    de la ficción, no del contrato con el modelo.
  - Cambiar el idioma del plan cambia prompts y quizá el comportamiento del planificador. Medir la
    tasa de planes rechazados antes y después.

### SIM-21 · Validar en real que la narración no cae al respaldo

*Área:* función simulada · *Cuota:* ~120 llamadas (un run simulado) · *Depende de:* —

- **Síntoma.** En 7.10 la revisión editorial rechazaba por un tiempo verbal o por citar una
  paráfrasis, y tras dos rechazos el capítulo salía del narrador determinista: 7 de 14
  capítulos, los 4 de `20261012-000926-la-ciudad-perdida` (64 «penso», 5,4 nombres cada 100
  palabras). Además la función era un ping-pong: «suplicar» contra «ordenar» tres veces cada
  uno en el primer beat, y la mitad de los beats forzados. 7.12.0 lo arregla con dobles; el
  replay de las revisiones guardadas aceptaría o entregaría el mejor intento en los 7.
- **Medido en 7.12.1, 2026-10-13**, con 3.5 Flash-Lite dando 503 a más de la mitad de las
  llamadas:
  - Los navegantes, dos veces: `125004` se canceló en la escena 1 con el casting en respaldo
    (arreglado: la reparación ve su candidato) y `131347` murió en la escena 5 por dos 403
    sueltos (arreglado: una ranura que ya respondió no se bloquea). Ninguno llegó a narrar.
    En sus 37 turnos, ningún pensamiento en inglés; el primer beat recibe el giro del director
    en el turno 6, antes del tope de 8.
  - El misterio del tren (`145340`, par de `20261011-233750` de 7.10): 2 de 2 capítulos del
    narrador (7.10: 1 de 2), ningún `NARRATION_BEST_ATTEMPT`, revisiones sin hallazgos, 0 de 31
    pensamientos en inglés y nombre repetido en frase seguida en el 18 % de las frases (7.10:
    40 %). Los dos beats forzados coinciden con comprobaciones del director que los dos modelos
    rechazaron con 503: miden la caída de Gemini, no la función.
  - Falta el run completo de los navegantes; `125004` quedó en `running` y se puede cerrar con
    `asg-recover --discard`.
- **Medido en 7.12.2, 2026-10-13** (`20261013-180025-las-islas-del-cielo`, los navegantes
  completos, Expansiva, 2 h 55 min):
  - 5 de 5 capítulos del narrador, ninguno de respaldo, y un solo `NARRATION_BEST_ATTEMPT`.
  - Pero 5 de 10 beats forzados: el director citaba «Ilse Marvento [...] observa» y el log
    guarda «Observa». Arreglado en 7.13 (`stage/causality.py`); falta medirlo en real.
  - La narración entera salió de 3.1, porque los actores agotaron 3.5 en la llamada 93.
    Arreglado en 7.13: los actores empiezan por 3.1.
- **Qué hacer.** Repetir el prompt de los navegantes (`brief.json` de ese run) en real y leer
  `narration.json`, `narration/*-review-*.json` y `director.jsonl`.
- **Hecho cuando.** Ningún capítulo con `source: fallback` salvo que el narrador no devolviera
  texto, ningún pensamiento en inglés en `turns.jsonl`, y el primer beat en estancamiento
  recibe el giro antes de su tope.
- **Ojo.** Medir cuántos capítulos salen como `NARRATION_BEST_ATTEMPT`: si son muchos, el
  revisor sigue marcando como contradicción lo que no lo es, y hay que mirar sus códigos.
- **Medido en 7.19 y arreglado en 7.20.**
  - En `20261019-023436` fueron 3 de 3. De los 10 hallazgos bloqueantes, 7 llamaban invención
    al estilo indirecto.
  - El revisor ve ahora `retold_as`, y el código descarta lo que está en el log.
  - La renarración 7.20 (`20261019-133532`) dio 3 de 3 aceptados al primer intento.

### SIM-24 · El narrador de 7.16 resume de más

*Área:* función simulada · *Cuota:* ~260 llamadas (un par 7.16 / 7.16.x del mismo prompt) ·
*Depende de:* —

- **Síntoma.**
  - Con las réplicas no clave en estilo indirecto, `dialogue_survival` bajó de 0,89–0,92 a 0,47.
    Pero la prosa encadena esas réplicas en párrafos que leen como un acta («ordenó…,
    preguntando…, sugiriendo…»), en `20261017-182756` y `184641`.
  - Vuelve a etiquetar con «—dijo X» casi todas las réplicas que conserva.
  - En la lectura por pares (no a ciegas) quedó 1 a 1 frente a 7.15.2. Detalle en el
    CHANGELOG de 7.16.0.
- **Qué hacer.**
  - Pedir al narrador que funda varias réplicas indirectas en una frase, o que las corte.
  - Medir `TAGGED` también por debajo de 8 líneas.
- **7.20 no lo cierra.**
  - El camino `reported` ya no pega acotaciones ni réplicas dobladas.
  - Pero en `20261019-133532` siguen los párrafos de acta («exigió…, advirtió…, declaró…») y los
    epítetos en lugar del nombre («la alada», «el mecánico»).
  - El brazo `selected` (`20261019-131241`) añade otro defecto: «Pensaba: …» en primera persona
    tras casi cada réplica.
- **Respuesta en 7.17.** El brazo `narration_method=selected` (el narrador escribe desde momentos
  elegidos, nunca desde el log), más el editor por fragmentos. Se mide en SIM-25.
- **Hecho cuando.** En un par nuevo, `dialogue_survival` sigue por debajo de 0,6, ningún
  párrafo encadena más de dos réplicas indirectas y menos de la mitad de las réplicas llevan
  verbo de habla.

### SIM-25 · Validar la narración por selección y el editor sobre el mismo log

*Área:* función simulada · *Cuota:* ~140 llamadas (5 renarraciones × 2 brazos) ·
*Depende de:* —

- **Síntoma.**
  - El narrador copia lo que recibe:
    - con el log entero, `dialogue_survival` está entre 0,89 y 1,0;
    - con el estilo indirecto de 7.16, salen 32 verbos de estilo indirecto en `20261017-184641`
      y párrafos de acta.
  - Hace 12 de 12 cambios de escena sin transición.
  - No recibe el mundo, así que Zéfara casi no aparece.
  - 7.17 añade `narration_method=selected`, `line_editor` y `style_examples`, probados solo con
    dobles.
- **Qué hacer.**
  - Renarrar con `asg-generate --narrate-from` los cinco runs 7.15.2/7.16 del 17-oct dos veces:
    - una con `--options` del run;
    - otra con `--narration-method selected --line-editor --style-examples`.
  - Leer los pares a ciegas en StageCraft, que ya muestra las cifras de legibilidad.
  - Leer `narration/*-selection.json`, `line_edits/` y los avisos `[SELECTION_FALLBACK]` y
    `[LINE_EDIT_UNAVAILABLE]`.
- **Hecho cuando.**
  - Las personas prefieren un brazo o no distinguen, y queda escrito en el CHANGELOG y en
    `docs/resumen.md`.
  - Si gana `selected`, el predeterminado cambia y se borra el camino de `report` y el segundo
    intento de 7.15.
- **Ojo.** Es la comparación más limpia que permite el proyecto: el mismo log, solo cambia la
  narración. No mezclar con runs nuevos.

### TD-10 · Validar fichas de escena, crítico con cita y editor en Top-Down

*Área:* top-down · *Cuota:* ~110 llamadas (2 planes y 2 borradores por brazo con
`--plan-from`) · *Depende de:* —

- **Síntoma.**
  - En 7.10, 3 de 4 historias salieron como su primer borrador, porque el crítico no dio notas.
  - 114 de 114 réplicas acotadas.
  - 12 de 14 capítulos abren con el aire.
  - No hay capa de escena.
  - 7.17 añade `scene_cards`, `anchored_critic`, `line_editor` y `style_examples`, más la
    aceptación medida del Writer y los nombres por candidatos, probados solo con dobles.
- **Qué hacer.**
  - Generar un plan de la cubana (prompt libre) y uno de la regencia (`--brief`).
  - Desde cada plan, dos borradores con `--plan-from <run> --format narrative`: uno sin brazos y
    otro con los cuatro.
  - Comparar a ciegas y con las cifras de legibilidad de StageCraft.
  - Leer `scene_cards.json`, `review_anchors.json`, `line_edits/` y `name_choices.json`.
- **Hecho cuando.**
  - Hay una decisión escrita por brazo.
  - Se cumplen los umbrales de TD-8 en el brazo ganador.
- **Ojo.** Se puede hacer junto con TD-8, que pide los mismos dos prompts.

### TD-8 · Validar en real la prosa para un lector cualquiera

*Área:* top-down · *Cuota:* ~40 llamadas (dos narrativas, con y sin `GEMINI_PROSE_MODEL`) ·
*Depende de:* —

- **Síntoma.** En los runs 7.10 de los amigos la prosa narrativa pesa: coletillas tras la réplica
  en el 40–62 % de las líneas (`20261012-163919-de-la-oscuridad-al-mundo`), palabras de 9 letras
  o más en el 17,8 y el 20,6 % de los dos peores, y «Carmen» 45 veces en 3.052 palabras pedidas
  como «unas 500». El crítico no dio notas y ningún capítulo pasó por el Writer. 7.12.0 añade el
  contrato de estilo, `style_request`, el perfil Esencial para lo corto y las notas medidas, todo
  probado solo con dobles.
- **Qué hacer.**
  - Repetir en real el prompt de la cubana (`de-la-oscuridad-al-mundo`) y el de los dinosaurios
    que murió (`la-regencia-de-las-escamas`), los dos con el mismo modelo, y una vez más con
    `GEMINI_PROSE_MODEL` (Flash, ~20 peticiones gratis al día).
  - Llevar `readability_signals` a la capa T de `asg-report-features`, que solo lee disco, para
    comparar antes y después sin leer a mano.
- **Hecho cuando.** Los dos runs nuevos dan coletillas y nombres repetidos por debajo de los
  umbrales de `writing/craft_evidence.py`, la cubana sale Esencial y en el registro pedido, el
  título y el slug van en español, y los amigos la prefieren a ciegas frente a la de 7.10.
- **Ojo.** 3.5 Flash-Lite ignora la temperatura (ver Ideas): el modelo de prosa es el único
  mando de estilo que no pasa por el prompt.
- **Avance 7.17.** Las cifras de legibilidad ya están en la comparación de StageCraft
  (`pairing.py`), recalculadas desde `story.md`. No están en la capa T, porque tocar `rasgos.csv`
  cambia la huella del catálogo y el juez de 27 entradas: decidirlo antes del estudio.

### TD-3 · Validar en real el Writer por ediciones

*Área:* top-down · *Cuota:* ~19 llamadas (una narrativa con `--plan-from`) · *Depende de:* —

- **Síntoma.**
  - **El Writer copiaba.** En `20261018-035939-la-luz-de-los-hundidos`, el capítulo 3 volvió
    byte a byte dos veces y se entregó el borrador.
  - **El corpus repite el patrón.** 17 de 29 intentos guardados eran casi copias, y unas ocho se
    aceptaron con nota `major`.
  - **La revisión alargaba.** En 6.2, 66 de 69 capítulos salieron más largos, con una mediana de
    +82 palabras.
  - **Código hecho en 7.18.0, probado solo con dobles:**
    - ediciones por párrafo (`writing/chapter_edits.py`);
    - `NOTE_NOT_APPLIED`, también cuando sobrevive la observación de una nota de artesanía;
    - el mejor candidato en vez del borrador;
    - el bucle común (`writing/revision_loop.py`).
- **Qué hacer.**
  - `asg-generate --plan-from Stories/Stagecraft/20261018-035939-la-luz-de-los-hundidos --format narrative --no-audio`.
  - Leer `writer/*-edits.json` y `revision_report.json`, y comparar la similitud de cada capítulo
    revisado con su borrador frente al 1,0 de `035939`.
- **Hecho cuando.**
  - Ningún capítulo con nota grave sale como `draft`.
  - Las ediciones aceptadas atienden la nota que citan, leído a mano.
  - Flash-Lite responde al esquema sin fallos estructurados.
- **Ojo.** Si el esquema le cuesta a Flash-Lite, cada fallo queda como intento `failed`. Es la
  cifra que dice si hace falta `GEMINI_PROSE_MODEL` para el Writer.

## P03 · Línea base y corpus

### MED-8 · Línea base de un solo prompt

**Actualización 2026-10-04:** infraestructura implementada y demostrable sin red; consultar
[README de evaluación](../packages/evaluation/README.md). La descripción siguiente conserva
el diagnóstico inicial. Queda pendiente la ejecución con corpus definitivo y lectores reales.

*Área:* medición · *Cuota:* ~1 llamada por historia · *Depende de:* nada

- **Síntoma.** El tutor pide comparar con historias generadas «directamente por un prompt»
  (audio, [03:02]), igual que la versión monolítica de la tesis de Roger. No existe ese
  generador.
- **Qué hacer.** Un comando que pida a `GEMINI_MODEL` una historia con el mismo
  `original_prompt` en una sola llamada, sin pipeline, y escriba `Stories/Baseline/<run>/` con
  `request.json`, `story.md`, `metadata.json` (`story_format: baseline`) y `llm_usage.json`. El
  enfoque se infiere de la carpeta: «Baseline».
- **Hecho cuando.** Hay una línea base por obra de la matriz, y los informes de `evaluation` la
  leen como un enfoque más.

### MED-6 · Inventario del corpus

*Área:* medición · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.**
  - **Versiones.**
    - 18 runs no tienen `pipeline_version` (16 a 18 de agosto) y 47 no tienen
      `generator_version.json`, así que caen fuera de los informes por versión.
    - La etiqueta de pipeline es gruesa: 6.2 cubre el generador de 6.6.0 a 6.9.0.
    - `story_format` solo consta en los 9 runs más nuevos de Top-Down.
  - **Estados y restos.**
    - `Top-Down/20260911-173150-*` está `failed` (PermissionError) con `story.md` escrito.
    - Quedan `.story.mp3.*.tmp` en los dos runs cerrados a mano (`20260901-020145`,
      `20260908-020751`).
  - **Archivos que no son runs.** Hay uno en `Stories/Top-Down/`
    (`comparacion-densidad-borrador-final-v2.0.4.html`), y la cola `Stories/telegram_queue.sqlite3`.
  - **Huecos sueltos.** `20260901-023045-the-cheesecake-trial` tiene historia y no
    `evaluation.json`, y los warnings son texto libre, sin campo de código.
- **Qué hacer.**
  - Un informe de solo lectura en `evaluation` que liste esas anomalías, para que cada informe de
    la tesis diga qué excluye y por qué.
  - Nunca borrar datos. Lo que se corrija, con `asg-recover` y dejando rastro.
  - Poner código propio a los warnings de los runs nuevos, en la próxima subida de `PIPELINE_VERSION`.
- **Hecho cuando.** El inventario sale limpio, o cada anomalía tiene una decisión escrita.

## P04 · Validar el extractor

### MED-9 · Extractor de rasgos con cita verificada

*Área:* medición · *Cuota:* revisión y test-retest con presupuesto por fijar · *Depende de:*
versión definitiva del generador

- **Síntoma.** El extractor (`packages/evaluation/src/asg_evaluation/features.py`, protocolo 3)
  verifica que cada cita es literal, pero nadie ha comprobado todavía que sus interpretaciones
  sean correctas ni que sean estables: la demo ficticia no valida su calidad.
- **Qué hacer.**
  - Revisar a mano una muestra con `asg-audit-features`, incluidas contradicciones, ceros
    y fenómenos omitidos.
  - Medir la estabilidad repitiendo la extracción (`--force`, `--second`) en un subconjunto.
  - Contrastar con los logs de la función cuando describan lo mismo.
- **Hecho cuando.** La revisión humana y el test-retest publican resultados sobre la muestra
  acordada antes del estudio.
- **Ojo.** Una cita literal no garantiza una interpretación correcta. El log no es un límite
  numérico universal para la prosa.
- **Medido el 2026-10-25** sobre las 15 historias de `Evaluations/estudio`. El protocolo 2 no
  completó ninguna: unas 60 llamadas con `gemini-3.5-flash-lite` y 134 con `gemini-3.5-flash`.
  - Un solo rasgo inválido tiraba los 12 del lote.
  - Si X23 no aplicaba, X24 quedaba en `failed` para siempre.
  - El protocolo 3 (evaluación 2.1.0) aísla los fallos por rasgo y resuelve el caso de X24.

### MED-7 · Métricas de actuación leídas del log

*Área:* medición · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.** `simulation_metrics.json` no mide lo que más falla en la actuación, y las cifras de
  `docs/resumen.md` salieron de scripts de un solo uso:
  - a quién se dirige cada turno (1 de 80 con destinatario) y si alguien le responde;
  - las notas que se repiten al mismo actor (5 de 54 turnos con nota);
  - los pensamientos que son un plan (35 % y 62 %) o que repiten la nota;
  - las mentiras (0 de 80) y la variedad de tácticas por actor;
  - cuánta memoria recibe cada turno (medido a mano en el par de 7.2: mediana y máximo de 8);
  - si las voces se distinguen;
  - si el narrador cuenta un pensamiento con una compuerta antes de su evento (SIM-13);
  - lo que salió a mano en la validación 7.8: ids y texto en inglés en el contexto del actor
    (cerrado en 7.9, pero conviene vigilarlo), emociones repetidas entre escenas y cesiones
    por acto (SIM-19).
- **Qué hacer.** Calcularlas en `asg_evaluation.simulation_report` (capa P de
  `asg-report-features`), que solo lee disco, desde `turns.jsonl`,
  `contexts.jsonl`, `director.jsonl`, `cast_bible.json` y `story.md`:
  - recuerdos y caracteres por contexto de actor;
  - turnos con destinatario y turnos respondidos;
  - notas repetidas dentro de un beat;
  - pensamientos de plan y eco de la nota;
  - mentiras y entropía de tácticas por actor;
  - distinción de voces entre personajes, con una medida sin LLM como las de Šeļa et al. (2023);
  - pensamientos narrados que contienen una compuerta antes de su evento.

  Como en el resto de `evaluation`, lo que un run no registró sale como «no medido».
- **Hecho cuando.** El informe da esas cifras para las cinco funciones de `Stories/Stagecraft/` y
  reproduce las de `docs/resumen.md`.
- **Ojo.** Son indicadores deterministas y groseros: sirven para comparar versiones sobre el mismo
  plan, no como nota de calidad. Ninguno viaja a un prompt.

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

### EXP-2 · Medir la ablación de memoria propia contra memoria compartida

*Área:* experimento · *Cuota:* ~2.000 llamadas para dos brazos de 9 runs, más la auditoría ·
*Depende de:* SIM-1, MED-3

- **Síntoma.** `--actor-memory shared` existe como brazo de control y nadie lo ha corrido. Es la
  medición que sostiene la afirmación central de la tesis: que dar a cada personaje solo lo que
  presenció produce mejores escenas que darles todo lo público.
  - El proxy determinista es `unknown_mentions`; el juez `audit-stage-run` se retiró en 7.11
    (git `714f13e`) porque aprobaba casi todo.
  - Pero el juez por defecto (`gemini-3.5-flash-lite`) todavía no es fiable:
    - marcó como fuga un hecho que estaba literalmente en la memoria inicial del personaje
      (reauditoría de `023354`);
    - movió 7 puntos una cifra que no había cambiado (91,67 → 85,0);
    - no ve ni un cambio de género ni una réplica sin atribuir.
- **Qué hacer.**
  - Primero, calibrar el juez: reauditar los runs existentes con un modelo más fuerte (`--model`)
    y ver qué fugas se sostienen.
  - Después, dos matrices idénticas salvo en `--actor-memory`.
- **Hecho cuando.** Hay una cifra de fuga de frontera de conocimiento para cada brazo, medida con
  un juez calibrado, y una comparación a ciegas de las historias de cada uno.
- **Ojo.**
  - Las funciones 7.0 y 7.1 recuperaban la memoria entera: cada actor leía todo lo que había
    presenciado. La ablación corre ya sobre 7.2, que aplica el tope; no mezclar sus runs con los
    anteriores.
  - El respaldo de la hipótesis, y lo que ya dice la literatura sobre filtrar lo que un personaje
    sabe, está en `docs/resumen.md` §7.

### EXP-3 · Medir guion nativo frente a adaptado y quedarse con uno

*Área:* experimento · *Cuota:* ~300 llamadas para 9 runs por método · *Depende de:* TD-2, MED-3;
mejor con MED-5

- **Síntoma.** Hay 6 runs de guion, 3 por método (`Top-Down/20260925-16*`, pipeline 6.2), y nadie
  los ha comparado. Lo que ya se ve:
  - **Ningún intento de acto rechazado**, en ninguno de los seis.
  - **El nativo sale escaso.** Hace siempre 2 escenas por acto y 1 evento por escena; el acto I
    de `160449-la-sombra-del-faro` tiene 2 réplicas en 8 líneas.
  - **El adaptado es otra cosa.**
    - Es unas 1,5 veces más largo y cuesta 20 llamadas frente a 15.
    - Copia de su `prose.md` entre el 45 y el 49 % de sus secuencias de 6 palabras.
    - Sus acotaciones son de novela: estados interiores en 10 de 133, frente a 1 de 78 en el
      nativo («la verdad que aplasta el alma de la aldea»).
  - **Los títulos en inglés sesgan la lectura** del nativo (TD-2).
- **Qué hacer.**
  - Una matriz con los dos métodos sobre los mismos prompts, mejor desde el mismo plan (MED-5).
  - Leer `script_metrics.json`, los intentos rechazados, los avisos, la tasa de copia desde la
    prosa y el coste, y comparar a ciegas.
- **Hecho cuando.** Hay una decisión escrita, con cifras, en `docs/resumen.md`, y se ha
  borrado el método que pierda: su agente, sus prompts, sus tests y `ASG_SCRIPT_METHOD`.

### EXP-5 · Medir qué aporta cada mejora de la función

*Área:* experimento · *Cuota:* ~900 llamadas (3 prompts × 3 versiones), varios días de cuota
gratuita · *Depende de:* MED-5, MED-7

- **Síntoma.**
  - **No se sabe qué aporta cada cambio.** Cada ficha SIM se valida con un par de runs sobre un plan
    distinto, así que no se sabe qué aportó cada cambio ni si alguno empeoró otra cosa.
  - **Todo se ha medido con misterios.** Las cinco funciones son del prompt 03.
  - **El criterio existe.** WSE-bench concluye que más arquitectura no es más control: cada
    componente debe ganarse su complejidad.
- **Qué hacer.**
  - Con `--plan-from` (MED-5), representar el mismo plan en tres versiones: 7.1.1, 7.2.0 (que
    cerró SIM-9 y SIM-10), y la que cierre SIM-6 y SIM-11.
  - Usar tres prompts de géneros distintos: 03 (misterio), 04 (drama) y 01 (fantasía).
  - Añadir como brazo el presupuesto de pensamiento del actor (SIM-4).
  - Leer MED-7, `asg-report-features` (capas P y K) y la comparación a ciegas.
- **Hecho cuando.** Hay una tabla por versión en `docs/resumen.md` y una decisión
  escrita sobre qué mecanismo se queda.
- **Ojo.** En el prompt 03 el brazo base pueden ser los propios runs 7.1: con `--plan-from` sobre
  `070539` y `072847`, las versiones nuevas representan exactamente su plan. En los otros dos
  prompts, 7.1.1 solo se puede volver a correr desde git: decidir antes el checkout etiquetado.

### EXP-6 · Medir qué aporta el inventario de objetos

*Área:* experimento · *Cuota:* ~200 llamadas por par de funciones rejugadas desde un plan ·
*Depende de:* MED-5

- **Síntoma.** El inventario existe desde 7.6 con su brazo de control (`--no-inventory`) y solo
  hay un par de funciones con él. Sin medición, la afirmación de que arbitrar los objetos mejora
  la coherencia física es una opinión.
  - En `Stories/Stagecraft/20260930-153026-la-sombra-del-volcan`, sin inventario, el Sello Real
    Quebrado aparece como pergamino en manos de Elara en el capítulo 1 y en la túnica de Aldren
    en el capítulo 3, sin que nadie lo haya entregado. Eso es lo que hay que contar en los dos
    brazos.
- **Qué hacer.**
  - Dos brazos de n≥3 desde planes congelados (`--plan-from`), idénticos salvo `--inventory`.
  - Contar en los dos, con los nombres de `world.json`: menciones de un objeto en la acción de
    quien no lo lleva, y objetos que cambian de manos sin que haya un traspaso.
  - Leer `props_used_ratio` para saber si los objetos fueron decorado, y `item_witness_share`
    para saber si el tráfico fue privado.
  - Comparar además una narración limitada de la misma función: lo que el lector sabe de quién
    tiene qué debería diferir de la omnisciente.
- **Hecho cuando.** Hay una cifra de incoherencia física por brazo, con n≥3, y una comparación a
  ciegas de las historias.
- **Ojo.**
  - `--no-inventory` deja los prompts idénticos a 7.5, así que la ablación es limpia; pero el
    brazo con inventario gasta una llamada más (el utilero) y sus actores reciben un esquema
    con un campo extra. No mezclar sus runs con los de 7.5 en una misma media sin decirlo.
  - **Dos huecos que el árbitro no cierra, vistos en el par de 7.6.** El `stage_event` del
    director es texto libre y no se arbitra: uno dijo que el sello resbalaba de las manos de
    Aldren cuando lo tenía Elara. Y un actor puede mencionar un objeto en su acción sin
    declarar un movimiento (10 de 21 menciones). Contar las dos cosas en la medición, y
    decidir si se arbitran o se aceptan.

## P06 · Estudio humano

### EXP-4 · Evaluación humana por pares a ciegas

*Área:* experimento · *Cuota:* votar no consume cuota; generar y extraer sí · *Depende de:*
MED-8 y la revisión de MED-9

- **Síntoma.** El instrumento está listo (2026-10-12): el bot `asg-telegram` 5.0.0 recoge
  historias de los participantes (Top-Down o híbrido, libre o guiada, con audio) y, cuando el
  investigador abre la votación, presenta pares a ciegas con una pregunta cada vez. Todavía no
  hay ni una historia ni un voto reales.
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

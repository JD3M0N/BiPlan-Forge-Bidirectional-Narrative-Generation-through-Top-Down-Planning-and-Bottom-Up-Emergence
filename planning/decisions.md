# Decisiones

Lo decidido y duradero. Una tarjeta no puede contradecir esta página: si choca, se para y se
pregunta a Josue. Una decisión nueva entra aquí solo cuando Josue la aprueba, con su fecha.

## 1. Reglas del tutor

No son negociables. Salen del audio del 2026-10-03 (transcrito en
`docs/audio_2026-10-03_14-09-35.transcripcion.md`, fuera de git) y de la rúbrica de
`docs/sanderson-craft.pdf` §1.1 y §3.8. La lectura completa, con citas, está en
[METODOLOGIA.md §1](../packages/evaluation/METODOLOGIA.md). Toda tarea que toque evaluación,
rasgos, juez, análisis o tesis se contrasta con esta lista antes de empezar.

| # | Regla | Fuente |
|---|---|---|
| T1 | Hay **dos evaluaciones y una intermedia**: humana (el gusto), mecánica (escala) y un juez aprendido que traduce una a la otra. | [00:08–00:22] |
| T2 | **La máquina cuenta, no juzga.** Un LLM extrae recuentos «que alguien leyéndose la historia pudiera sacar la cuenta», cada uno con cita literal verificada por código. Nunca se le pregunta si una historia es buena. | [00:22–01:56] |
| T3 | Los recuentos cubren, como mínimo, los ejemplos del tutor: consistencia, % de participación por personaje, escenas con conflicto, usos de objetos, participación en diálogo y réplicas que se desvían de la personalidad, personajes que mienten, cosas complicadas, eventos aleatorios. La rúbrica *Flash Fiction* es la primera fuente de rasgos (sin el ítem 16, canon). | [00:34–01:34]; rúbrica §3.8 |
| T4 | De cada historia sale **una tablita** de rasgos, y las tablitas se comparan entre parametrizaciones: el **análisis horizontal**, «con todas las cosas activadas, cambiando diferentes niveles», por ejemplo el tono. | [02:07–02:23] |
| T5 | La evaluación humana es **por pares a ciegas**, nunca con escala («ese 8 no significa nada»). Lectores que no saben qué mecanismo generó cada historia. | [02:45–04:01] |
| T6 | Hay una **línea base de un solo prompt** entre las historias comparadas. | [02:45–03:07] |
| T7 | **Tres criterios** de muy alto nivel, uno por pregunta: creatividad, personajes mejor desarrollados, trama más interesante. No más. | [03:09–04:27] |
| T8 | El **juez** es una regresión (scikit-learn) de los 18–30 rasgos a tres números, ajustada para recuperar el ranking humano. Las unidades no importan, solo el orden. Se valida **fuera de muestra** (recuperarlo dentro de la muestra es trivial). | [04:27–05:42] |
| T9 | El juez **ordena todo el corpus** y se analizan **las 10 mejores**: qué tienen y qué no. | [05:43–05:55] |
| T10 | La aportación es **el generador más la metodología de evaluación**. | [05:55–06:21] |
| T11 | **Fuera de la tesis:** usar el juez como función objetivo (generar N y quedarse la mejor) y el algoritmo genético. Van a conclusiones como trabajo futuro, no se implementan. «Lo tuyo se queda en la evaluación.» | [06:21–07:43] |

## 2. Decisiones de método

- **2026-10-27 · Rasgos núcleo fijados antes de ver votos.** Solo los 27 rasgos `núcleo` de
  T, R y X entran al juez. La lista se cierra en P04 y no se toca después de abrir la votación.
- **2026-10-27 · `rasgos.csv` es un contrato.** Cambiarlo cambia la huella del catálogo e
  invalida extracciones y jueces. Solo se edita en una tarjeta que lo diga, y nunca de paso.
- **2026-10-27 · El juez lee solo el texto.** Las capas P, K y C sirven para el análisis
  horizontal, explicar las mejores y validar al extractor; no entran al juez
  (METODOLOGIA.md §3).
- **2026-10-27 · Un juez que no generaliza es un resultado válido**, y se presenta como tal.
- **2026-10-28 · Líneas base de la matriz (T6).** Las obras 01, 03 y 04 de M02 tienen tres
  líneas base cada una (9 llamadas), para medir el ruido de la propia línea base. Las premisas
  del estudio de P06 reciben la suya tras la recogida (EXP-4).
- **2026-10-28 · Catálogo de prompts en `packages/evaluation/planilla/prompts.md`**, restaurado
  de `baa016f^:docs/prompts_top_down.md` con sus marcadores `PROMPT_0N_*` (`docs/` no se
  versiona). La línea base recibe, literal, la variante Esencial, la de la celda base M01: el
  mismo prompt que el pipeline.
- **2026-10-28 · `Evaluations/estudio` es un piloto.** Sus 75 votos de 7 lectores sobre 15
  historias de 7.21 (3 líneas base) se conservan y se informan como piloto, fuera del estudio de
  la tesis: son anteriores a la congelación y cubren el piloto de P06. Si se usan en P07 como
  comprobación externa, se declara antes de entrenar.
- **2026-10-28 · Corpus elegible para el ranking (T9): Stagecraft 7.x y las líneas base**, en
  prosa (`narrative`, `simulated`, `baseline`), con la versión marcada en cada historia. Se
  excluye, con razón escrita: lo anterior a Stagecraft 7 (Top-Down 4.x–6.x y Bottom-Up, incluidos
  los Top-Down sin `story_format`) y los guiones. Hoy son 107 runs (unas 215–320 llamadas de
  extracción en P08), más lo que generen P03.3, P05 y P06.
- **2026-10-28 · Lista núcleo provisional (P04.2).** Se decide sobre las lagunas y los núcleo
  dudosos de `packages/evaluation/planilla/cobertura.md` §4, sin haber visto votos ni
  extracciones. «Lista núcleo» significa `prioridad = núcleo` y `uso = juez`; P, K y H no
  entran, aunque lleven `núcleo`. **28 rasgos:** T01, T06, T08, R01, R02, R03, R04, R05, R09,
  R15, R16, R17, R18, R23, R24, X02, X03, X06, X09, X10, X13, X14, X15, X16, X17, X20, X24, X29
  (personajes 9, trama 15, creatividad 3, T01 sin criterio). Se cierra en P04.9.
  **Cambios que aplica P04.4 en `rasgos.csv`:**
  - R12 pasa a `secundario`: son tres comprobaciones de la vida interior del personaje (0–3),
    no un recuento, y no hay log que lo contraste. El ítem 7 conserva su rasgo.
  - R18 pasa a `núcleo`: recuento con cita del bloque «mundo», el tercer núcleo de
    «creatividad».
  - X29 nuevo, «Reparto del diálogo»: entropía normalizada de las réplicas por hablante,
    calculada con código desde el desglose de X08 (como X03 con las escenas), en una escala
    de 0 a 1, `núcleo`, `juez`, criterio «personajes», contrastado con `turns.jsonl` (speech
    por actor). Cubre el ejemplo 5 del audio sin llamadas nuevas.
  - R15 se reformula: veces que una acción del protagonista, que el propio texto atribuye a
    un rasgo suyo (con cita de esa atribución), le causa un fracaso o una pérdida. Desaparece
    «la cara oscura de una virtud».
  - R23 se reformula en positivo, «Escenas con cambio»: proporción de escenas (sobre X05) en las
    que cambia la información, una relación o la situación, con la cita del cambio. El peso
    esperado pasa a ser positivo.
  - X09 pierde «sin que el arco lo justifique»: cuenta las réplicas que contradicen un rasgo
    que el texto afirmó antes de forma explícita, con las dos citas. El signo lo sigue
    decidiendo el juez.
  - X24 pasa de cociente a recuento de preguntas abiertas que el texto responde; T01 ya
    controla la longitud.
  **Sin cambio, con razón escrita:**
  - Lo «sorprendente» del ítem 3 queda sin rasgo: depende de lo que esperaba el lector, así
    que medirlo sería juzgar (T2). Lo valora el criterio humano «creatividad», y X15 es el
    recuento más cercano.
  - R13 y R21 siguen secundarios: son una categoría y un binario que salen de leer el arco
    interno, y con pocas historias apenas varían. Van al análisis horizontal.
  - R20 sigue secundario: obliga a decidir qué «no hace falta para la trama».
  - X11 sigue secundario: sale de las mismas mentiras que X10 (X11 ≤ X10).
  - X05 y X23 siguen secundarios, pero entran en la revisión humana (P04.3, P04.6), porque sus
    errores se arrastran a X02, X03, X06, R23 y X24.
  - Los solapes R05/X14/X15, R16/R17 y X13/X15 se mantienen. P07 usa regularización e informa
    la colinealidad.
  **Para otras tarjetas:**
  - P04.3 da más peso en la muestra de la revisión humana a los núcleo sin `validable_contra`.
  - P04.5 añade el par X29 ↔ réplicas por actor.
  - P04.9 lleva a H2 la pregunta de qué entiende el tutor por «cosas complicadas» (X14, X15).
- **2026-10-28 · Diseño de la validación del extractor (P04.3).** Fijado antes de cualquier
  extracción y sin ver cifras. Los umbrales no se cambian después de medir.
  - **Muestra (12 runs elegibles del inventario 2026-10-28, estratificada por formato y
    versión, premisas distintas):**
    - Simulados con `turns.jsonl` propio: `Stagecraft/20261028-192554-el-misterio-del-faro`
      (7.22), `20261022-125649-el-ultimo-tren` (7.21), `20261020-213446-el-pacto-roto` (7.20),
      `20261015-132526-las-islas-del-cielo` (7.15), `20261009-203308-el-legado-de-la-casa` (7.9).
      Los simulados `--narrate-from` de P02.1 no tienen log propio y quedan fuera.
    - Narrativos: `Stagecraft/20261028-192554-el-faro-de-la-habitacion-cerrada` (7.22),
      `20261027-220405-la-regencia-de-las-escamas` (7.21),
      `20261019-022533-el-precio-de-las-manecillas` (7.19), `20261009-150449-el-dato-ausente`
      (7.8).
    - Líneas base (7.22): `Baseline/01-fantasia-canonica-1`, `03-ultima-luz-del-faro-1`,
      `04-cine-de-los-domingos-1`.
    - En total, 21.471 palabras.
  - **Modelo:** `gemini-3.5-flash-lite`, el del piloto y el que extraerá el corpus en P08. En el
    piloto completó 14 de 31 extracciones frente a 1 de 25 de `gemini-3.5-flash`.
  - **Test-retest (6):** el faro 7.22 y las islas 7.15 (simulados), la regencia y el dato ausente
    (narrativos), y las líneas base 03-1 y 04-1. Coste: ~54 llamadas (12 × 3 + 6 × 3).
  - **Revisión humana (~7 h de Josue):** las 6 del test-retest, completas. En las otras 6, solo
    los núcleo sin `validable_contra` (R02, R04, R05, R09, R15, R16, R17, R18, R24, X06, X09,
    X14, X15, X20), además de X05, X23 y todo rasgo con valor cero o `not_applicable`. Los
    rasgos calculados con código (capa T, X03 y X29) no se revisan a mano.
  - **Umbrales por rasgo núcleo extraído:**
    1. Precisión humana ≥ 0,80: citas `correcto` sobre citas juzgadas, sin las `dudoso`, sumadas
       las historias.
    2. Cobertura ≥ 0,70: correctas / (correctas + ocurrencias omitidas que anote Josue).
    3. Test-retest: diferencia relativa media ≤ 0,25, con |a−b| / max(a, b, 1), y como mucho
       1 cambio de estado de 6.
    4. Techo del log: el texto no supera al log en más de un 10 % o +1, y esto ocurre en 1 de los
       5 simulados como mucho. Quedar por debajo del log no cuenta como fallo.
    5. Con menos de 5 citas juzgadas, el rasgo queda «sin evidencia suficiente»: sigue marcado y
       no cuenta como «no cumple».
  - **Regla de salida (P04.9):** un núcleo que falla un umbral se reformula si sus errores son
    de definición, del mismo tipo y con citas que lo muestren. Si no, pasa a `secundario`. Si la
    lista baja de 18, no se relajan los umbrales: se lleva al tutor en H2.
- **2026-10-30 · Lista núcleo fijada (P04.9).** No se toca tras abrir la votación (P06).
  **24 rasgos:** T01, T06, T08, R01, R02, R03, R04, R05, R09, R16, R18, R23, R24, X02, X03, X06,
  X10, X13, X14, X15, X16, X17, X20, X29 (personajes 7, trama 13, creatividad 3, T01 sin
  criterio). Dentro de la horquilla 18–30 (T8). Aplica la regla de salida a los 12 que no
  cumplieron el test-retest en la validación de P04.8:
  - **Salen a `secundario` (4):** R15, X09 y X24, sin ningún par medido en ambas pasadas y sin
    citas que muestren si el extractor los detecta (X09 y X24, ninguna en toda la muestra); y
    R17, sin citas juzgadas y con un cambio de estado. No es un error de definición con citas
    que lo muestren, así que no se reformulan. Siguen en el catálogo y se extraen solo con
    `--selection all`; la extracción por defecto (`core`) ya no los pide.
  - **Se conservan con excepción justificada (8 de los 12):** R03, R16, R23, R24, X06, X10, X13
    y X20. Donde hay pares medidos en ambas pasadas, el valor es idéntico (diferencia media
    0,00); lo que falla son cambios de estado (`measured` frente a `failed` o `not_applicable`),
    y 6 de las 12 extracciones de la muestra quedaron `incompleta`. Es evidencia indirecta, de
    1 a 3 pares por rasgo.
  - **X29 se queda:** se calcula por código desde X08; sus 2 cambios de estado vienen del
    extractor de X08, no de X29.
  - **La validación es provisional y así se declara:** la cobertura no se midió en ningún
    rasgo, los veredictos los dio Claude y Josue los aceptó, y 6 de 12 extracciones están
    incompletas. Ningún «cumple» es definitivo. Repetir la extracción de las incompletas y
    anotar omisiones queda fuera de la tesis por ahora (`planning/h2.md`, pregunta 3).
  - **Para H2:** qué entiende el tutor por «cosas complicadas» (X14, X15).
  - Cambia la huella del catálogo (evaluación 2.1.5): las extracciones de la muestra se hicieron
    con la huella anterior y habría que repetirlas para leerlas con el catálogo vigente.
- **2026-10-30 · Matriz del análisis horizontal (P05.1): matriz A.** En
  `packages/evaluation/planilla/matriz.csv`. Obras 01, 03 y 04 con su variante Esencial,
  `gemini-3.5-flash-lite` y `gemini-3.1-flash-lite` en la función, sin audio.
  - **Base (M01):** simulado desde cero con los predeterminados del generador congelado (brazos
    de 7.17 e inventario apagados, `reported`, `own`, `fixed`, 8 turnos), 2 repeticiones por obra.
    Es la lectura recomendada de «con todas las cosas activadas» (T4); la pregunta 5 de H2 sigue
    abierta y se confirma con el tutor en H4. La repetición 1 de la obra 03 es
    `Stagecraft/20261028-192554-el-misterio-del-faro`, que usó literalmente `PROMPT_03_ESSENTIAL`
    con esos predeterminados.
  - **Celdas derivadas de cada base, emparejadas por plan fuente:** narrativo con `--plan-from`
    (M03, EXP-1); tono sombrío y humorístico (M04, M05) y visión `limited` y `first_person`
    (M06, M07) con `--narrate-from`, que solo cambia la narración. Sin `--narrator`: narra el
    protagonista. Las 9 líneas base (M02) ya existen.
  - **Coste:** 35 unidades nuevas, ~1.540 llamadas principales y ~515 de función (topes de los
    rangos medidos): piloto y 4 días de cuota.
  - **Responde:** T4 (tono y visión) y EXP-1. EXP-2 (memoria) y EXP-6 (inventario) pasan a
    idea-bank como ampliación si queda cuota tras P05.8. Los runs 7.21 de P02.1 y P02.2 entran como
    datos sin coste, separados por versión.
  - **Regla de ruido, fijada antes de generar:** para cada rasgo y obra, ruido = |M01 r1 − M01 r2|.
    Una celda se interpreta para un rasgo solo si el valor absoluto de la mediana de sus
    diferencias emparejadas (derivada − su base) supera el mayor ruido de ese rasgo en las tres
    obras **y** el signo coincide en al menos 5 de los 6 pares. Si no, se escribe «dentro del
    ruido». Un rasgo `no medido` en un miembro del par deja el par fuera y baja el n. Es
    conservadora para las celdas `--narrate-from`, porque el ruido entre bases mezcla plan, función
    y narración. M02 se compara con su propio ruido (rango de sus 3 repeticiones), no con esta
    regla.

## 3. Decisiones de proyecto

- **2026-10-27 · Trabajo por fases.** El plan vive en `planning/` y se ejecuta con la skill
  `phase` ([phase.md](phase.md)). `TODO.md` es de Josue; los agentes no escriben en él. El
  antiguo `TODO.md` está en `git show planning-before-phase:TODO.md`.
- **2026-10-27 · Generador: congelar pronto.** P02 elige de 3 a 5 fichas que bloquean la calidad,
  las cierra y congela el generador. Desde ahí, ningún cambio de prompt, esquema ni
  `PIPELINE_VERSION` sin una decisión nueva aquí.
- **2026-10-28 · Generador congelado en Stagecraft 7.22.x (pipeline 7.22)**, etiqueta local
  `generator-frozen`. Predeterminados: los brazos de 7.17 apagados (`inventory`,
  `style_examples`, `line_editor`, `scene_cards`, `anchored_critic`, `typed_clauses`), narración
  `reported`, `OUT_OF_FICTION` general (SIM-14). Validado con tres runs reales del
  prompt 03 ([docs/resumen.md](../docs/resumen.md)); limitación conocida: ~la mitad de los beats
  simulados se fuerzan. Los brazos apagados quedan como opciones para el análisis horizontal (T4).
- **2026-10-27 · Tesis en LaTeX** dentro de `redaccion/`, compilada con `latexmk` (MiKTeX
  instalado). Al final se reescribe con una skill que Josue instalará; sus tarjetas se escriben
  entonces.
- **2026-10-27 · Commits.** Uno por tarea, directo a `main`, sin `Co-Authored-By`, sin push.

## 4. Protocolo de medición

Movido sin cambios del antiguo `TODO.md`.

Vale para toda ficha `EXP` y para cualquier «Hecho cuando» que pida runs reales.

- **Presupuesto antes de lanzar.** Medianas medidas con `gemini-3.5-flash-lite`:

  | Formato | Llamadas | Tokens |
  |---|---|---|
  | Narrativa | 16 | ~84k |
  | Narrativa (corrida de control) | 17 | 97k |
  | Guion nativo | 15 | ~75k |
  | Guion adaptado | 20 | ~93k |
  | Simulado | 98–126 | 250k–337k |

  El tope gratuito es diario y por modelo (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`).
  Por el run que lo agotó ronda las 500 peticiones al día, cifra inferida, no confirmada. Una
  matriz simulada de 9 runs no cabe en un día.
  - Desde 7.4, la función puede gastar el cupo de otro modelo con `GEMINI_STAGE_MODEL`
    (recomendado `gemini-3.1-flash-lite`, con unas 500 RPD propias según fuentes de septiembre de
    2026). Así el cupo de `GEMINI_MODEL` queda para plan, guion, casting y narración, unas 15–25
    llamadas por run.
  - El RPD real de cada modelo se ve en AI Studio → Rate limits: Google ya no lo publica.
- **Emparejar.** Mismo prompt del catálogo ([docs/resumen.md](../docs/resumen.md)),
  mismo perfil forzado con `--profile` y mismo modelo. En runs simulados, también el mismo modelo
  de la función (`stage_model`): `pair_runs` no da por limpio un par que lo cambie. Cuando exista
  MED-5, también el mismo plan.
- **A ciegas.** Para comparar:
  - la comparación de runs de StageCraft (`asg-studio`) sobre `story.md`;
  - `asg-report-features` para la artesanía (capa T), la función (capa P) y el coste (capa K).
- **Ruido.** La réplica de doce historias de 6.6.0 dio hasta 16 puntos de diferencia entre dos
  corridas del mismo prompt y la misma versión. Una diferencia de medianas menor de unos cinco
  puntos, con n=9, no se interpreta.
- **Los jueces LLM son indicio, no medida.** La auditoría de la función movió una fidelidad de
  91,67 a 85,0 cambiando solo el juez de conocimiento, y no ve un cambio de género. Hasta cerrar
  TD-1 y la calibración de EXP-2, ninguna cifra de juez cuenta como medida. La literatura dice lo
  mismo: un juez prefiere sus propias generaciones, y aquí Gemini juzga a Gemini; y los jueces al
  uso puntúan historias de LLM por encima de relatos del *New Yorker* (ver
  [docs/resumen.md](../docs/resumen.md), §9).
- **La calidad la deciden personas, por pares.** La evaluación de la tesis sigue
  [packages/evaluation/METODOLOGIA.md](../packages/evaluation/METODOLOGIA.md): rasgos contables con
  cita, tres criterios humanos por pares a ciegas y un juez aprendido de esos pares. Las seis
  métricas de 1 a 10 de `evaluation.json` eran un instrumento heredado y se retiraron en el
  cierre.
- **Lo que se lanza es lo que se mide (2026-10-17).** Los runs de 7.16 no traían `brief.json`, se
  hicieron en Esencial para un brief que pedía una historia extensa y eran anteriores al commit.
  Desde 7.17:
  - siempre `--brief` cuando la obra tiene ficha;
  - un perfil acorde con lo que pide el brief;
  - código ya confirmado en git;
  - dos runs por brazo como mínimo.
- **Comparar sobre la misma entrada.** Un cambio de narrador se compara con `--narrate-from`
  sobre la misma función, y uno de escritura Top-Down con `--plan-from` sobre el mismo plan. Así
  el ruido de la función y del plan queda fuera de la comparación.
- **Por escrito.** El resultado va con cifras y comandos en el doc del formato
  (`docs/resumen.md`), no aquí.

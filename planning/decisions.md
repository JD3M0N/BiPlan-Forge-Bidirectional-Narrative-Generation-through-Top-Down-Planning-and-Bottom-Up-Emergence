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
- **2026-10-28 · `Evaluations/estudio` es una base sintética** (corregida el 2026-10-30, P06.1).
  Sus 75 votos sobre 15 historias de 7.21 (3 líneas base) no son de lectores: los dieron 5 agentes
  Claude Opus con perfiles de lector (`simulacion/INFORME.md`, 2026-10-25). Son un juez LLM con
  otro nombre (§4): no cuentan como votos, ni como piloto de P06, ni como comprobación externa en
  P07. La base se cierra y se exporta sin borrarla (P06.4).
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

- **2026-10-30 · Diseño del estudio humano (P06.1).** Fijado antes de abrir y sin ver votos.
  Cubre T5 (pares a ciegas, A/B o abstención, presentación homogénea), T6 (una línea base por
  premisa), T7 (las tres preguntas de `planilla/criterios_humanos.csv`; `QUESTIONS_PER_READER`
  sigue en 15), T8 (la lista núcleo se congela al abrir; 5 familias para validar fuera de
  muestra) y T2 con §4 (ningún voto de un LLM).
  - **Conjunto: 15 historias 7.22, 5 premisas × 3 formatos** (narrativo, simulado, línea base),
    para que cada premisa dé el triángulo de mecanismos sobre la misma entrada.
    - Obras 01 y 03: M01 r1 (simulado), su M03 (narrativo `--plan-from`) y la línea base `-1`,
      ya generados.
    - Obra 04: M01 r1 y la línea base `-1`, ya generados; falta su M03 (~20 llamadas
      principales, en P06.6).
    - 2 premisas nuevas de participantes por el bot, cada una con un Top-Down narrativo, un
      híbrido y su línea base: ~315 llamadas principales y ~205 de función, un día de cuota.
    - No entran las celdas de tono y visión (M04–M07) ni M01 r2 (repetirían trama y harían del
      estudio un análisis horizontal; van al ranking en P08), ni nada anterior a 7.22.
  - **Tamaño.** Cada lector vota 5 pares × 3 criterios y lee unas 6 historias. Con S = 15 y R
    lectores, cada historia aparece 10R/S veces por criterio. Mínimo: **12 lectores sin contar al
    autor**, con sus 15 preguntas.
  - **Regla de parada.** Se cierra cuando se cumplen a la vez: ≥ 12 lectores completos sin el
    autor, cada historia con ≥ 6 comparaciones decididas por criterio y el grafo de cada criterio
    conexo. Plazo máximo: 21 días desde `open`; al vencer se cierra igualmente y se informa lo que
    haya. Hasta el cierre solo se mira `asg-study status` (recuentos), nunca las preferencias.
  - **Presentación (T5).** En `/estudio` se quitan el `# Título` y todos los encabezados markdown,
    también los de capítulo (las líneas base no los tienen), y se sustituyen por un separador
    neutro (`* * *`). **Sin audio** para ninguna historia: P06.3 se retira y OPS-3 pasa a
    idea-bank. La longitud no se iguala ni se recorta: las líneas base son más cortas, se declara
    como amenaza y P07 compara el juez con la longitud sola.
  - **Rutas.** Estudio real en `Evaluations/estudio-tesis/study.sqlite3`, que pasa a ser
    `DEFAULT_STUDY`; piloto humano en `Evaluations/estudio-piloto-722/study.sqlite3`, elegido con
    `ASG_EVALUATION_STUDY`. La base sintética de `Evaluations/estudio` se conserva cerrada.
  - **Lectores.** Amigos y compañeros hispanohablantes, mayores de edad, que no conozcan el
    sistema por dentro. Josue puede votar marcado como `author`, pero no cuenta para el mínimo y
    el resultado principal es sin autor (se informa también con él). Al entrar a `/estudio`, un
    aviso breve: se guarda un seudónimo y los votos, ningún texto personal, y se puede dejar en
    cualquier momento.
  - **`/evaluar`** (las dos historias propias) sale del recorrido recomendado mientras dure el
    estudio: no es un par a ciegas. Lo que vote ahí no se analiza.
  - **Riesgo para P07:** `train_judge` exige los 24 rasgos `measured` o `not_applicable` en cada
    historia, y en P04.7 la mitad de las extracciones quedaron `incompleta`.
- **2026-11-02 · Datos del juez (P07.1).** Aprobado por Josue. Cambia, para P07, la decisión de
  P06.1 de dejar el piloto fuera: el estudio real no se hizo (P06 cerrada el 2026-10-31) y estos
  son los únicos votos humanos. Cubre T2 y §4 (solo votos de personas; los 75 sintéticos de
  `Evaluations/estudio` no entran), T6 (las 2 líneas base están dentro), T7 (los tres criterios)
  y T8 (validación fuera de muestra, ahora con 2 familias).
  - **Protocolo real del piloto.** Los 5 lectores (30–31 de octubre; el autor no votó) votaron
    con una **hoja de orden fijo**, no con la asignación del bot: los cinco tienen los mismos 5
    pares en el mismo orden y con la misma historia como A (H1–H3, H2–H3, H4–H5, H4–H6 y H5–H6,
    cada uno con los tres criterios en ciclo); L2 paró en la 9. El bot no puede producir esa
    secuencia (`_assign` habría dado H1–H2 en la pregunta 7, compensa la posición A/B entre
    lectores y empareja obras distintas; comprobado simulando el bot sobre una copia de la base).
    Consecuencias que se declaran: sin pares entre obras, así que el grafo de cada criterio tiene
    dos componentes y no hay ranking humano global ni τ de Kendall (`bradley_terry` da
    `insufficient`); el sesgo de posición no se separa de la historia; H1–H2 nunca se comparan
    directamente; los votos se transcribieron a mano; siguen los fallos del piloto (tabla del
    bloque P06 del roadmap) y la sospecha de L4 por el diálogo. Votos decididos: creatividad 20
    (3 abstenciones), personajes 20 (3) y trama 21 (2). Si las historias se leyeron en Telegram o
    en papel, y con qué presentación, se documenta en P07.5 como amenaza a T5.
  - **(a) Sí entrenan al juez de la tesis**, que se presenta como **juez exploratorio del piloto
    (hoja de orden fijo)**, nunca como medida de calidad.
  - **(b) Entran con `asg-study import-votes CSV`** en
    `Evaluations/estudio-piloto-722/study.sqlite3`, **esquema 10 sin cambios**, con `seconds`
    nulo como marca de transcripción. La base no tiene votos del bot, así que todos sus votos
    tienen el mismo origen y no hace falta columna de origen. Junto a la base, un JSON con el
    protocolo («hoja de orden fijo»), la ruta y la huella SHA-256 del CSV. La importación no
    aplica `_assign`: crea participantes, lecturas y asignaciones con la posición y el orden A/B
    transcritos.
  - **(c) Extracciones: repetir hasta completar.** `train_judge` sigue exigiendo los 24 núcleo
    `measured` o `not_applicable`; sin imputación de fallidos y sin `MODEL_VERSION` 3. Cada
    relanzamiento usa el mismo modelo y protocolo (`gemini-3.5-flash-lite`, huella de catálogo
    vigente) y enseña su coste antes de gastar (§4); no hay tope fijo de reintentos, y parar es
    decisión de Josue.
  - **(d) Validación por familias: una sola cifra** que junta las predicciones de los 2 pliegues
    (cada uno entrena con las 3 historias de una obra y prueba con la otra), como ya hace
    `_validate`, frente a 0,5 y a la longitud sola. Se publica con el número de votos probados y
    diciendo que sale de 2 pliegues.
  - **CSV de transcripción** (`Evaluations/estudio-piloto-722/votos-transcritos.csv`, UTF-8, una
    fila por respuesta dada):

    | Columna | Valores |
    |---|---|
    | `lector` | `L1`–`L5` (seudónimo; pasa a participante) |
    | `pregunta` | `1`–`15`, orden en la hoja; único por lector |
    | `criterio` | `creatividad`, `personajes`, `trama` (H01, H02, H03) |
    | `historia_a`, `historia_b` | `H1`–`H6`, distintas; A y B tal como estaban en la hoja |
    | `eleccion` | `A`, `B`, `abstencion` (→ `abstain`) |
    | `fuente` | `papel` |

    | Código | Historia del estudio | Run |
    |---|---|---|
    | H1 | `sa4b09bb6b0dd4b75` | `20261030-221208-la-sombra-del-volcan` (simulada, obra 01) |
    | H2 | `s7e46754afd9445ac` | `20261030-234947-la-promesa-del-volcan` (simulada, obra 01) |
    | H3 | `s037b5a5c6f0949ae` | `01-fantasia-canonica-2` (línea base, obra 01) |
    | H4 | `s4ce9516cd71c4562` | `20261030-140119-el-misterio-del-faro` (simulada, obra 03) |
    | H5 | `s8bbc2c9f31a1484a` | `20261028-192554-el-faro-de-la-habitacion-cerrada` (narrativa, obra 03) |
    | H6 | `s283387af5930405f` | `03-ultima-luz-del-faro-2` (línea base, obra 03) |

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

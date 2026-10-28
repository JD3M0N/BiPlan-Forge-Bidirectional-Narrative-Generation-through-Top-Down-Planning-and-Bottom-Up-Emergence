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

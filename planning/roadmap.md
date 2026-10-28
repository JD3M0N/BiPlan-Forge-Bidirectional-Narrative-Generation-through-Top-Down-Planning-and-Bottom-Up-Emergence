# Roadmap

Del generador congelado a la tesis escrita, por fases. Cómo se trabaja: [phase.md](phase.md).
Lo decidido: [decisions.md](decisions.md), con las **reglas del tutor** (T1–T11) en su §1.
Las fichas heredadas del antiguo `TODO.md`, íntegras: [fichas.md](fichas.md).

## Estado actual

- **Siguiente:** P04.3 · diseño de la validación (`/phase`, modo `O`; mejor con Opus).
- **Versiones** (2026-10-28): Stagecraft 7.22.0 (pipeline 7.22), core 0.8.1, evaluación 2.1.1,
  Telegram 6.0.2, Studio 0.2.2.
- **Hechas:**
  - P00 · Arranque: `planning/`, skill `phase`, migración de `TODO.md` y graphify.
  - P01.1 · Inventario de código muerto: 4 candidatos aprobados por Josue (ver P01.2); sin comandos ni módulos huérfanos.
  - P01.2 · Retirado el código muerto aprobado: `output_choice()`, `output_choice_for()`, `available_keys()`, `pending_keys()` y `SET_BY_PRESET` (los tres últimos pasan a los tests).
  - P01.3 · Reescritos 39 docstrings plantilla y el gate los rechaza; 12 clases Pydantic enviadas a Gemini quedan exentas (ver ING-1 en `future/idea-bank.md`).
  - P01.4 · Docs cotejados con el código (comandos, rutas, enlaces, versiones, constantes): corregidos 3 desajustes (rango de pipeline en el README de stagecraft, `asg-recompute`, salida de `asg-rank`); cierra H0.
  - P02.1 · Narración simulada, 5 pares a ciegas: empate 2–2–1 (B `selected` + editor + ejemplos corrige las actas pero no gana); se mantiene `reported`, sin editor ni ejemplos (en `docs/resumen.md`).
  - P02.2 · Brazos Top-Down, 8 borradores sobre 2 planes: TD-8 y TD-3 cumplen; a ciegas A 3, B 1, así que `scene_cards`, `anchored_critic`, `line_editor` y `style_examples` siguen apagados (en `docs/resumen.md`).
  - P02.3 · Plan del brief de las islas y guion de la médica: TD-9 no cumple (sin división de la tripulación ni coste final), TD-2 cumple (en `docs/resumen.md`).
  - P02.4 · Predeterminados sin cambio (todos los brazos de 7.17 siguen apagados, `reported`); `OUT_OF_FICTION` general contra vocabulario de código (SIM-14); Stagecraft 7.22.
  - P02.5 · Validación real de 7.22 (narrativo, guion y simulado del prompt 03 cumplen; beats forzados 3 de 6 como limitación) y generador congelado, etiqueta `generator-frozen`; cierra P02.
  - P03.1 · Decidido (`decisions.md` §2): 3 líneas base por obra 01/03/04, catálogo en `planilla/prompts.md` (variante Esencial), `Evaluations/estudio` es piloto y el ranking cubre Stagecraft 7.x y las líneas base.
  - P03.2 · `asg-corpus` (solo lectura): 322 runs con 107 elegibles; las diferencias con el recuento de P03 son los 6 runs de `Bottom-Up/Escape-Room`, que el inventario sí cuenta (todos excluidos por generador anterior); `judge._ineligible` reutiliza `exclusion_reason`.
  - P03.3 · Catálogo restaurado en `planilla/prompts.md` y 9 líneas base (3 por obra 01, 03 y 04, Esencial, Flash-Lite, 7.22) en `Stories/Baseline/`: todas completas, `C01 = Baseline` y elegibles; 10 llamadas, una de ellas reintento de `04-…-3`. Cierra MED-8.
  - P03.4 · Decisión escrita por grupo de anomalías en `METODOLOGIA.md` §10 (inventario 2026-10-28: 331 runs, 116 elegibles); 6 runs `running` sin historia descartados con `asg-recover --discard`, `la-carta-del-faro` (7.10) queda sin cerrar y excluido. Cierra MED-6 y P03.
  - P04.1 · `planilla/cobertura.md`: los 9 ejemplos del audio y las 19 dimensiones aplicables tienen rasgo; quedan 10 lagunas parciales y 4 núcleo de riesgo alto (R12, R15, R23, X09) para P04.2.
  - P04.2 · Lista núcleo provisional de 28 en `decisions.md` §2: R12 pasa a secundario; entran R18 y X29 (reparto del diálogo, calculado con código); se reformulan R15, R23 (en positivo), X09 y X24 (recuento). P04.4 aplica esos cambios.

## Cómo leer una tarjeta

```text
#### P04.2 · Título
- **Modo:** S | S+P | O · **Cuota:** sin cuota | ~N llamadas · **Paquete:** asg-evaluation
- **Lee:** solo esto (rutas, secciones).
- **Haz:** los pasos.
- **No hagas:** lo que queda fuera aunque parezca cerca.
- **Prueba:** comandos y comprobaciones.
- **Hecho cuando:** una condición verificable.
```

`S`: Sonnet trabaja. `S+P`: Sonnet enseña un plan corto y espera «ok». `O`: decisión de diseño;
Sonnet da opciones con recomendación y espera (mejor con Opus).

Una fase sin tarjetas se prepara con `/phase cards Pxx` (Opus) justo antes de empezarla.

## Fases

| Fase | Resultado | Reglas del tutor | Hito al cerrar |
|---|---|---|---|
| P01 | Repo limpio y docs fieles al código | — | **H0** |
| P02 | Generador congelado | T10 | **H1** |
| P03 | Líneas base y corpus elegible | T6, T9 | — |
| P04 | Extractor validado y núcleo fijado | T2, T3 | **H2** |
| P05 | Análisis horizontal | T4 | — |
| P06 | Estudio humano con votos reales | T5, T6, T7 | **H3** |
| P07 | Juez aprendido y validado | T8 | — |
| P08 | Corpus ordenado y diez mejores analizadas | T9 | **H4** |
| P09 | Resultados reproducibles | — | — |
| P10 | Tesis escrita en LaTeX | T1–T11 | **H5** |
| P11 | Tesis reescrita | — | **H6** |

**Hitos.** Al cerrar uno se para: se prueba el bot en Telegram (en español) o se enseña al tutor,
y se repasan prioridades antes de seguir.

- **H0** repo limpio · **H1** generador congelado, probado en Telegram · **H2** instrumentos
  validados, al tutor · **H3** votación cerrada · **H4** juez y ranking, al tutor · **H5**
  borrador de la tesis, al tutor · **H6** entrega.

---

### P01 · Limpieza

Quitar lo que ya no se usa y dejar la documentación fiel al código antes de congelar nada.
Origen: ING-1 (hoy en [idea-bank](future/idea-bank.md)). Contrato: [AGENTS.md](../AGENTS.md) «Límites y
compatibilidad» y la referencia del subsistema que se toque.

---

### P02 · Congelar el generador

Cerrar solo lo que impide que una persona lea las historias como historias, validar en real y
congelar. Contratos: [generation.md](../docs/architecture/generation.md),
[simulation.md](../docs/architecture/simulation.md). Al cerrar: decisión «generador congelado en
Stagecraft X.Y» en `decisions.md` y etiqueta `generator-frozen`. **H1:** probar el bot en
Telegram con los dos enfoques.

Congelar es, sobre todo, fijar el predeterminado de los seis brazos de 7.17, hoy apagados, con
lecturas a ciegas sobre la misma entrada (`--narrate-from`, `--plan-from`). Elegidas (2026-10-27,
Josue): SIM-25, TD-10, TD-9, SIM-14 y SIM-21; SIM-24, TD-8, TD-3 y TD-2 se leen de los mismos
runs. El resto de fichas de la fase, SIM-26 incluida, pasó a [idea-bank](future/idea-bank.md).
Cuota total: unas 485 llamadas del modelo principal y 110 del de la función, en tres días como
mínimo.

**Reglas del tutor.** T10: el generador es la mitad de la aportación. Las lecturas a ciegas de
esta fase deciden predeterminados del generador; no son el estudio de la tesis (T5–T7, en P06).
Ningún juez LLM cuenta como medida (`decisions.md` §4). Los brazos no adoptados se conservan
como opciones para el análisis horizontal (T4, P05).

---

### P03 · Líneas base y corpus

Una línea base de un solo prompt por premisa del estudio (T6) y un inventario del corpus que
diga qué entra en el ranking (T9) y qué se excluye y por qué. Origen: MED-8, MED-6.
Contrato: [evaluation.md](../docs/architecture/evaluation.md).

La infraestructura de MED-8 ya existe (`asg-baseline`, `asg-study add`, `C01 = Baseline`):
falta generar las historias. Medido el 2026-10-28: 244 runs completos, 65 fallidos, 7 atascados
en `running`, 18 sin versión de pipeline, 47 sin `generator_version.json`, 167 de Top-Down sin
`story_format`, 4 `.tmp` y un `.html` suelto. `Evaluations/estudio` ya tiene 75 votos de
7 lectores sobre 15 historias de 7.21 (anteriores a la congelación). El catálogo de prompts
(`docs/prompts_top_down.md`) se borró en `baa016f`.

**Reglas del tutor.** T6: la línea base es una sola llamada con el mismo prompt que recibe el
pipeline, sin plan ni revisión. T9: el inventario dice qué ordenará el juez y por qué se excluye
el resto; no ordena nada. T10: el generador está congelado, así que nada aquí cambia prompts,
`baseline.py` ni `PIPELINE_VERSION`. T2 y T5: aquí nadie juzga calidad; las líneas base se
juzgan en P06.

### P04 · Validar el extractor

Que los recuentos sean los del tutor y sean fiables, antes de abrir la votación.
Origen: MED-9, MED-7. Contrato: METODOLOGIA.md §3.

- Auditoría rasgo a rasgo de `rasgos.csv` contra T3: cada ejemplo del audio y cada dimensión
  de la rúbrica tiene su rasgo, o una razón escrita para no tenerlo.
- Fijar la lista núcleo (decisions.md §2) antes de ver un solo voto.
- Revisión humana de una muestra con `asg-audit-features`, test-retest (`--second`) y contraste
  con los logs (`validable_contra`, métricas de MED-7).
- **H2:** enseñar al tutor la tablita de unas historias y la lista núcleo.

**Reglas del tutor.** T2: el extractor cuenta y cita, nunca juzga calidad; P04.1 marca los
núcleo que se lean como juicio. T3: cada ejemplo del audio y cada dimensión de la rúbrica tiene
rasgo o razón escrita. T8: la lista núcleo queda entre 18 y 30. Los umbrales se fijan antes de
medir (P04.3) y la lista se cierra al final (P04.9), antes de abrir la votación (P06). T10: nada
aquí toca el generador. Entre P04.7 y P04.8, Josue rellena la hoja de revisión.

#### P04.3 · Diseño de la validación
- **Modo:** O · **Cuota:** sin cuota · **Paquete:** asg-evaluation (decisión)
- **Lee:** `METODOLOGIA.md` §3 «El extractor» y §10; `decisions.md` §4;
  `Evaluations/corpus/inventario-2026-10-28.json`.
- **Haz:**
  1. Opciones con recomendación para: la **muestra** (10–15 historias elegibles, estratificada
     por formato: simulado con log, narrativo, línea base); el **modelo del extractor**
     (`flash-lite` o `flash`; cambiarlo cambia la identidad de la extracción, y MED-9 midió 60
     llamadas frente a 134 con el protocolo 2); el **subconjunto del test-retest**; y el tamaño de
     la **revisión humana** según las horas de Josue (unas 2600 palabras por historia).
  2. **Fija umbrales antes de medir** en `decisions.md` §2: precisión humana mínima,
     estabilidad mínima del test-retest, tolerancia frente al log (el log es un techo) y la regla
     de salida (un núcleo que no llega sale del juez o se reformula).
  3. Enseña el coste en llamadas (~3 por texto y pasada) y espera.
- **No hagas:** lanzar extracciones; elegir umbrales viendo cifras.
- **Prueba:** que cada historia de la muestra sea elegible en el inventario y, si es simulada,
  tenga `turns.jsonl`.
- **Hecho cuando:** `decisions.md` §2 tiene muestra (runs), modelo, umbrales y regla de salida,
  con fecha, antes de cualquier extracción.

#### P04.4 · Aplicar los cambios al catálogo
- **Modo:** S+P · **Cuota:** sin cuota · **Paquete:** asg-evaluation
- **Lee:** la decisión de P04.2 en `decisions.md` §2; `catalog.py`; `planilla/build_planilla.py`;
  `docs/architecture/evaluation.md`.
- **Haz:**
  1. Aplica a `planilla/rasgos.csv`, exactamente, los cambios de P04.2. Con P04.9, es la única
     tarjeta de P04 autorizada a editarlo.
  2. Corrige el estado de P35 (`por_construir`), que ya calcula `feature_report._simulation_counts`.
  3. Regenera la planilla con `python packages/evaluation/planilla/build_planilla.py`.
  4. Si un rasgo nuevo exige tocar el extractor, `features.py` solo en lo mínimo.
  5. Amplía el test de catálogo: núcleo T, R y X entre 18 y 30.
- **No hagas:** cambios que P04.2 no listó; tocar el generador; extraer.
- **Prueba:** `python -m pip install --no-deps -e packages/evaluation`; `.\run-tests.ps1`;
  `.\quality.ps1`.
- **Hecho cuando:** CSV, Excel y lista de `decisions.md` coinciden. Si P04.2 dijo «sin
  cambios», se corrige solo P35 y se regenera la planilla.

#### P04.5 · Contraste con los logs (MED-7 recortado)
- **Modo:** S · **Cuota:** sin cuota · **Paquete:** asg-evaluation
- **Lee:** `feature_audit.py`; `feature_report.py` (`_simulation_counts`); `simulation_report.py`;
  `rasgos.csv` (`validable_contra`); `docs/architecture/evaluation.md`.
- **Haz:**
  1. Calcula P37 (mentiras en el log: turnos con táctica `lie` en `turns.jsonl`) y las réplicas
     por actor para X08.
  2. Añade `compare_with_logs` a `feature_audit.py`: por historia y rasgo, valor extraído, valor
     del log y si el texto supera al log (techo). Pares: X02/X03↔P35, X08 y X29↔réplicas por actor,
     X10↔P37, X13↔P36, X16↔P21, X17↔P39, X18↔P40. Exponla como `asg-audit-features --run DIR`.
  3. Lo que el run no registró sale «no medido», nunca cero. Para cada par que no se pueda
     comparar, deja la razón escrita.
- **No hagas:** las demás métricas de MED-7 (están en el idea-bank); llamar al modelo.
- **Prueba:** tests con un run simulado de fixture (techo violado, log ausente);
  `.\run-tests.ps1`; `.\quality.ps1`.
- **Hecho cuando:** `asg-audit-features X.json --run DIR --output o.json` da la comparación por
  rasgo sobre un run simulado real de `Stories/Stagecraft`, sin llamadas al modelo.

#### P04.6 · Hoja de revisión legible y resumen del test-retest
- **Modo:** S+P · **Cuota:** sin cuota · **Paquete:** asg-evaluation
- **Lee:** `feature_audit.py` (`review_worksheet`, `compare_extractions`); `features.py`
  (`Quote`, `locate`, `measurement`); la decisión de P04.3.
- **Haz:**
  1. Una hoja de revisión en Markdown o CSV que una persona rellene: por rasgo, valor, cita con
     el párrafo que la contiene, y columnas `veredicto` (correcto / incorrecto / dudoso) y
     `ocurrencias omitidas`. Incluye los núcleo con valor cero y todos los `not_applicable`,
     donde se esconde lo omitido. Aplica el muestreo de ítems de P04.3.
  2. Un resumen del test-retest por rasgo sobre varias historias: acuerdo exacto, diferencia
     media relativa, correlación de rango y cambios de estado.
  3. Un agregado de veredictos: precisión por rasgo.
- **No hagas:** extraer; fijar umbrales (están en P04.3); editar el catálogo.
- **Prueba:** tests con extracciones de fixture; `.\run-tests.ps1`; `.\quality.ps1`.
- **Hecho cuando:** sobre una de las 15 extracciones actuales se genera la hoja y el resumen de
  dos copias, y el agregado de una hoja de ejemplo da la precisión por rasgo.

#### P04.7 · Extraer la muestra (primera y segunda pasada)
- **Modo:** S · **Cuota:** ~3 llamadas por texto y pasada; con unas 12 historias y 6 en la segunda
  pasada, ~54 (se fija en P04.3) · **Paquete:** asg-evaluation (sin código)
- **Lee:** `packages/evaluation/README.md` §3;
  `packages/stagecraft/src/asg_stagecraft/tools/extract_features.py`; la decisión de P04.3.
- **Haz:**
  1. Enseña `--dry-run` y el coste, y espera.
  2. Extrae cada historia de la muestra (`--root <run>`) y copia `features/features.json` a
     `features/primera.json`.
  3. Repite con `--force` en el subconjunto del test-retest.
  4. Con las herramientas de P04.5 y P04.6, genera el contraste con logs, la hoja de revisión y el
     resumen del test-retest en `Evaluations/validacion-extractor/` (ignorado por Git).
  5. Avisa a Josue de que le toca rellenar la hoja.
- **No hagas:** `RUN_GEMINI_LIVE=1`; extraer fuera de la muestra; borrar nada de `Stories/`.
- **Prueba:** extracciones `complete`; mismo `text_hash` en las dos pasadas.
- **Hecho cuando:** muestra extraída, contraste y resumen generados, y hoja lista para Josue.

#### P04.8 · Resultados de la validación
- **Modo:** S · **Cuota:** sin cuota · **Paquete:** asg-evaluation (docs)
- **Lee:** la hoja rellenada por Josue; los resúmenes de P04.7; `decisions.md` §2 (umbrales);
  `METODOLOGIA.md` §3 y §10.
- **Haz:**
  1. Agrega los veredictos.
  2. Escribe en `METODOLOGIA.md` la subsección «Validación del extractor», con fecha, muestra,
     modelo y, por rasgo núcleo, precisión humana, test-retest y contraste con logs.
  3. Marca qué rasgos cumplen los umbrales de P04.3, sin cambiar aún la lista, y anota los
     omitidos y los `not_applicable` dudosos.
- **No hagas:** cambiar umbrales ni la lista núcleo (es P04.9); extrapolar fuera de la muestra.
- **Prueba:** las cifras del texto coinciden con las salidas de los scripts.
- **Hecho cuando:** la subsección existe con la tabla «cumple / no cumple» por rasgo núcleo.

#### P04.9 · Lista núcleo definitiva y material para H2
- **Modo:** O · **Cuota:** sin cuota · **Paquete:** asg-evaluation
- **Lee:** `METODOLOGIA.md` «Validación del extractor»; `decisions.md` §2; `feature_cli.py` y
  `feature_report.horizontal_report`.
- **Haz:**
  1. Aplica la regla de salida de P04.3 a los que no cumplen: opciones por rasgo (sale del juez,
     se reformula, se conserva con excepción justificada) y espera.
  2. Si cambia el CSV, aplícalo aquí, regenera la planilla y sube la versión.
  3. Anota en `decisions.md` §2 «Lista núcleo fijada», con fecha, y «no se toca tras abrir la
     votación».
  4. Prepara `planning/h2.md`: la tablita (`asg-report-features`) de 4–5 historias de la muestra,
     una por formato, y la lista núcleo con su validación.
- **No hagas:** abrir la votación; tocar el generador.
- **Prueba:** `.\run-tests.ps1`; `.\quality.ps1`; núcleo entre 18 y 30.
- **Hecho cuando:** la lista está fijada en `decisions.md` y `planning/h2.md` existe. Cierra P04
  y **H2**: enseñar al tutor la tablita y la lista núcleo.

### P05 · Análisis horizontal

La tablita por historia comparada entre parametrizaciones (T4). Origen: MED-3, MED-5, EXP-1,
EXP-2, EXP-3, EXP-5, EXP-6.

- Primera tarjeta en modo `O`: qué matriz cabe en la cuota (enfoques Top-Down, híbrido y línea
  base; tono, visión, memoria…) y qué EXP se responden con ella. El resto pasa a idea-bank.
- Runner con presupuesto (MED-3), generación, `asg-report-features --horizontal` y lectura.
- Describe asociaciones; no atribuye causas con una celda por historia (protocolo §4).

### P06 · Estudio humano

Pares a ciegas con tres criterios (T5, T7) y la línea base dentro (T6). Origen: EXP-4, OPS-3.
Guía: [apps/telegram/README.md](../apps/telegram/README.md).

- Piloto con 2 o 3 lectores; arreglar lo que falle en el bot (incluido el audio, OPS-3).
- Recogida, `asg-study open`, votación, `close`, `export`.
- `asg-preferences`: cobertura, abstenciones, acuerdo con y sin el autor.
- **H3:** votación cerrada y exportada.

### P07 · Juez aprendido

Regresión de los rasgos núcleo a tres números, validada fuera de muestra (T8). Origen: EXP-7.

- Entrenar con los votos reales; validar dejando fuera historias y familias de premisa, frente
  al azar y a la longitud sola; perturbaciones; publicar pesos.

### P08 · Ranking y diez mejores

El juez ordena el corpus elegible y se leen las diez mejores (T9). Origen: EXP-8.

- Extraer rasgos del corpus elegible (cuota), `asg-rank`, fichas cualitativas de las diez.
- **H4:** enseñar al tutor juez, ranking y análisis.

### P09 · Resultados reproducibles

Un comando que regenera todas las tablas y figuras de la tesis desde `Evaluations/` hacia
`redaccion/figuras/` y `redaccion/tablas/`, con fecha y alcance. Origen: ING-8 (contratos
públicos y README), que se cierra aquí.

### P10 · Escribir la tesis

LaTeX en `redaccion/`, compilado con `latexmk`. Toda la fase se contrasta con T1–T11; T11 va a
conclusiones como trabajo futuro.

- Primera tarjeta en modo `O`: plantilla, índice y extensión, con la tesis de Roger Fuentes
  (`docs/`) como referencia de formato.
- Una tarjeta por capítulo: introducción; estado del arte (de `planilla/bibliografia.csv`,
  verificando las cifras marcadas «revisar cifras en el PDF»); el generador; la metodología de
  evaluación del tutor; experimentos y resultados (de P09); conclusiones y trabajo futuro;
  resumen y abstract.
- **H5:** borrador completo al tutor.

### P11 · Reescribir la tesis

Con la skill de reescritura que Josue instalará. Las tarjetas se escriben cuando esté
instalada: una por capítulo, sin cambiar cifras ni citas. **H6:** entrega.

# Roadmap

Del generador congelado a la tesis escrita, por fases. Cómo se trabaja: [phase.md](phase.md).
Lo decidido: [decisions.md](decisions.md), con las **reglas del tutor** (T1–T11) en su §1.
Las fichas heredadas del antiguo `TODO.md`, íntegras: [fichas.md](fichas.md).

## Estado actual

- **Siguiente:** P05.1 · elegir la matriz (modo `O`, mejor con `/model opus`). Antes, **H2**: enseñar al tutor `planning/h2.md`.
- **Versiones** (2026-10-30): Stagecraft 7.22.0 (pipeline 7.22), core 0.8.1, evaluación 2.1.5,
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
  - P04.3 · Diseño de la validación en `decisions.md` §2: 12 runs (5 simulados con log, 4 narrativos, 3 líneas base), `flash-lite`, test-retest de 6 (~54 llamadas), revisión de ~7 h y umbrales fijados antes de medir (precisión 0,80, cobertura 0,70, retest 0,25, techo del log) con su regla de salida.
  - P04.4 · `rasgos.csv` con los cambios de P04.2: núcleo de 28 (R12 sale; entran R18 y X29, entropía de X08 por código); R15, R23 («Escenas con cambio», proporción sobre X05), X09 y X24 (recuento) reformulados; P35 pasa a `existe`; planilla regenerada.
  - P04.5 · `asg-audit-features X.json --run DIR` contrasta los recuentos con el log (`compare_with_logs`; techo del log con margen 10 % o +1; «no medido» con su razón); P37 (turnos con táctica `lie`) calculado en el informe de rasgos.
  - P04.6 · `asg-audit-features` escribe la hoja de revisión en CSV (`--hoja`, una fila por ocurrencia con cita y párrafo, y una por rasgo sin ocurrencias; alcance parcial = muestra de P04.3), resume el test-retest por rasgo (`--pares`) y agrega veredictos en precisión y cobertura (`--veredictos`).
  - P04.7 · Muestra de 12 extraída con `flash-lite` (`primera.json` y `features.json` por run; segunda pasada `--force` en los 6 del test-retest, mismo `text_hash`); contraste con logs, 12 hojas CSV (6 completas, 6 parciales) y resumen del test-retest en `Evaluations/validacion-extractor/`. 6 de 12 quedan `incompleta` (`dato-ausente` sin segmentar, 31 fallos; `03-ultima-luz` 14; `04-cine` 11; `islas` 2; `misterio-del-faro` 1) y cuentan como fallos del extractor en P04.8.
  - P04.8 · Subsección «Validación del extractor» en `METODOLOGIA.md` §3 con la tabla por rasgo núcleo: 10 cumplen lo medible, 12 no cumplen el test-retest, varios sin evidencia en precisión; **cobertura sin medir** y veredictos dados por Claude (cita y párrafo) y aceptados por Josue, no revisión manual completa.
  - P04.9 · Lista núcleo fijada en `decisions.md` §2 (2026-10-30): 24 rasgos; R15, R17, X09 y X24 pasan a secundario, los otros 8 que fallan el test-retest se conservan con excepción escrita; `planning/h2.md` con la tablita de 5 historias y 4 preguntas para el tutor; cierra P04.

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

### P05 · Análisis horizontal

La tablita por historia comparada entre parametrizaciones (T4). Origen: MED-3, MED-5, EXP-1,
EXP-2, EXP-6 (EXP-3 y EXP-5 pasaron a [idea-bank](future/idea-bank.md)). Contrato:
METODOLOGIA.md §4 y [evaluation.md](../docs/architecture/evaluation.md).

Lo que ya hay (2026-10-30): `--plan-from` narrativo acepta un run simulado como fuente y escribe
`source_run.json` (C18), así que MED-5 está casi cerrado; `--narrate-from` cambia solo la
narración (voz, tono, método) sin repetir la función; las 9 líneas base de la matriz (M02) están
hechas; `horizontal_report` agrupa por un eje C y por versión, pero no empareja por plan fuente.
No existe runner de matrices. `planilla/matriz.csv` es un diseño viejo (anterior a
`--narrate-from` y a la congelación: da el inventario como encendido, y en 7.22 está apagado).

**Coste medido** (`llm_calls.jsonl`, sin `count_tokens`), que sustituye a las medianas del
protocolo para P05:

| Unidad | Principal (`gemini-3.5-flash-lite`) | Función (`gemini-3.1-flash-lite`) | Fuente |
|---|---|---|---|
| Simulado desde cero | 133 | 103 | `20261028-192554-el-misterio-del-faro` (7.22) |
| Narrativo desde cero | 24 | — | `20261028-192554-el-faro-de-la-habitacion-cerrada` (7.22) |
| `--narrate-from` | 17–30 | — | 10 runs de P02.1 (7.21) |
| `--plan-from` narrativo | 16–26 | — | 7 runs completos de P02.2 (7.21) |
| `--plan-from` simulado | sin medir (~120 + ~100, estimado) | | — |
| Extracción de rasgos | 2–3 | — | METODOLOGIA.md §11 |

Con unas 500 peticiones diarias por modelo (cifra inferida), el cuello es el modelo principal:
caben unos 3 simulados desde cero al día.

**Reglas del tutor.** T4: la fase entera; el tutor pone el tono como ejemplo de nivel. T2: los
recuentos los da el extractor con cita; ningún juez LLM ni lectura a ciegas cuenta aquí como
medida. T6: las líneas base M02 entran en la matriz. T8: la lista núcleo está fijada (24); nada
aquí toca `rasgos.csv`. T9: los runs de la matriz son prosa 7.22 y entran al corpus elegible de
P08. T10 y `decisions.md` §3: el runner y el informe no cambian prompts, esquemas, predeterminados
ni `PIPELINE_VERSION`. T11: la fase describe asociaciones; no elige «la mejor configuración» ni
genera N para quedarse una. Se describe, no se atribuyen causas (protocolo §4).

#### P05.1 · Elegir la matriz que cabe en la cuota
- **Modo:** O · **Cuota:** sin cuota · **Paquete:** — (planning y planilla)
- **Lee:** este bloque; `decisions.md` §2 (líneas base, corpus elegible, lista núcleo fijada),
  §3 (generador congelado) y §4; `packages/evaluation/planilla/matriz.csv` y `configuracion.csv`;
  `METODOLOGIA.md` §4 y §10; `docs/resumen.md` «Validación real de 7.22» y «Líneas base de la
  matriz»; en `fichas.md`, EXP-1, EXP-2 y EXP-6; las respuestas del tutor en H2, si ya las hay.
- **Haz:**
  1. Comprueba en `request.json` y `generation_options.json` si los dos runs 7.22 del prompt 03
     (`20261028-192554-el-misterio-del-faro` y `-el-faro-de-la-habitacion-cerrada`) usaron
     literalmente `PROMPT_03_ESSENTIAL` y `essential`. Si es así, son la celda base de la obra 03
     sin coste.
  2. Enseña de 2 a 4 matrices con sus celdas, obras, repeticiones, llamadas por modelo (con los
     costes de este bloque), días de cuota y qué EXP responde cada una. Punto de partida:
     - **A · Narración y formato.** Base simulada (M01) en las obras 01, 03 y 04 con 2
       repeticiones; desde ella, `--plan-from` narrativo (EXP-1), tono sombrío y humorístico, y
       visión `limited` y `first_person` con `--narrate-from`. Unas 1.500 llamadas principales y
       520 de función: unos 3 días.
     - **B · A más la función.** Añade memoria `shared` (EXP-2, leída con el proxy determinista
       P27 `unknown_mentions`, sin juez) e inventario encendido (EXP-6, P39–P42), con
       `--plan-from` simulado frente a una réplica de control del mismo plan. Entre 1.000 y 2.000
       llamadas principales más, según repeticiones.
     - **C · A con una repetición.** La mitad de coste, sin medir el ruido de la base.
     - En todas: los runs 7.21 de P02.1 (narración `selected` con editor y ejemplos) y P02.2
       (brazos Top-Down) entran como datos sin coste, separados por versión.
  3. Decide con Josue qué es «con todas las cosas activadas» (T4): los predeterminados congelados
     (brazos de 7.17 e inventario apagados) o todos los brazos encendidos. Si H2 no lo respondió,
     recomienda los congelados y déjalo como pregunta para H4.
  4. Fija, antes de generar, la regla de ruido para leer: por ejemplo, una diferencia emparejada
     menor que la que separa las dos repeticiones de la base en esa obra no se interpreta.
  5. Con el «ok»: entrada fechada en `decisions.md` §2 (matriz, regla de ruido, qué EXP se
     responden); reescribe `matriz.csv` con columnas que pueda leer el runner (celda, obras por
     marcador `PROMPT_0N_ESSENTIAL`, formato, flags de `asg-generate`, `desde` como
     `M01:plan` o `M01:narrate`, repeticiones, llamadas por modelo, nota) y regenera la planilla;
     reescribe `METODOLOGIA.md` §4 (la matriz se genera, emparejada por plan fuente); reparte las
     celdas por días y reescribe P05.5 y P05.6 con las de cada día (añade P05.6b… si hacen falta
     más); pasa a idea-bank las EXP no elegidas y borra de `fichas.md` las absorbidas.
- **No hagas:** generar nada; tocar `rasgos.csv` o la lista núcleo; contar una lectura a ciegas
  como medida (eso es P06); añadir perfiles Desarrollada o Expansiva desde cero sin poner su coste;
  decidir si las historias de la matriz entran al estudio humano (lo decide P06).
- **Prueba:** `python packages/evaluation/planilla/build_planilla.py` sin errores; el total de
  `matriz.csv` cuadra con los costes de este bloque.
- **Hecho cuando:** `decisions.md` §2 tiene la matriz con fecha y regla de ruido, `matriz.csv` la
  refleja con columnas legibles por código, y P05.5–P05.6 nombran celdas concretas.

#### P05.2 · `asg-matrix`: runner de matrices con presupuesto (MED-3)
- **Modo:** S+P · **Cuota:** sin cuota (tests con proveedor falso) · **Paquete:** asg-stagecraft
  (parche; `PIPELINE_VERSION` no cambia)
- **Lee:** MED-3 y MED-5 en `fichas.md`; `matriz.csv` (el formato que fijó P05.1);
  `tools/generate.py` (`parser`, `build_options`, `request_problem`, `main`); `tools/budget.py`
  (`preflight`, `average_story`, `slot_spending`); `tools/baseline.py` (`generate_baseline`);
  `pipeline.py` (`execute_from_plan`, `execute_from_performance`, `_save_frozen`);
  `asg_core/help.py`; `FakeProvider` en `packages/stagecraft/tests/test_generator_v5.py`.
- **Haz:**
  - `asg-matrix MATRIZ.csv [--dry-run] [--celdas M01,M03] [--obras 03] [--manifest RUTA]` en
    `asg_stagecraft/tools/matrix.py`. Lee el catálogo de prompts como hermano del CSV
    (`prompts.md`; la planilla no va en el wheel) y resuelve cada marcador.
  - Expande a unidades (celda × obra × repetición). Una unidad con `desde` usa el run de la unidad
    fuente de la misma obra y repetición, y espera a que esté `completed`.
  - `--dry-run`: llamadas por modelo (principal y función) frente a lo que queda hoy
    (`slot_spending`), con el coste por tipo de unidad de `average_story` cuando hay runs y, si
    no, del bloque P05.
  - Corre en serie y en proceso, reutilizando `build_options`, `request_problem` y `preflight`;
    la línea base con `generate_baseline`. `--no-audio` siempre. Para en cuanto `preflight`
    rechace una unidad, con el manifiesto al día.
  - Manifiesto JSON (escritura atómica tras cada unidad; por defecto en
    `Evaluations/horizontal/`): unidad, celda, obra, repetición, run, estado, opciones y unidad
    fuente. Al relanzar salta las `completed`; una fallida se repite en un run nuevo y la
    fallida se conserva.
  - Los runs van a la raíz de siempre (`Stories/Stagecraft`, `Stories/Baseline`): `C01` se
    infiere de la carpeta padre, y una carpeta `Stories/Matriz` cambiaría el enfoque.
  - Registra el comando en `pyproject.toml`, `asg_core/help.py` y el README de stagecraft;
    `CHANGELOG.md` con la ID.
- **No hagas:** cambiar prompts, esquemas, predeterminados ni `PIPELINE_VERSION`; paralelizar;
  extraer rasgos (es `asg-features`); `--force` implícito; borrar runs fallidos.
- **Prueba:** test con proveedor falso que muere a mitad de una matriz pequeña (narrativo desde
  cero, `--plan-from` narrativo y línea base): al relanzar completa sin repetir llamadas ya
  hechas; dos unidades de formatos distintos con el mismo plan fuente tienen `story_plan.json`
  idéntico byte a byte (MED-5); `--dry-run` no llama al proveedor. `.\run-tests.ps1` y
  `.\quality.ps1`.
- **Hecho cuando:** los tests pasan, `asg help` lista `asg-matrix` y
  `asg-matrix packages/evaluation/planilla/matriz.csv --dry-run` imprime el coste de la matriz de
  P05.1 sin gastar cuota.

#### P05.3 · Informe horizontal emparejado por plan fuente (cierra MED-5)
- **Modo:** S+P · **Cuota:** sin cuota · **Paquete:** asg-evaluation (parche)
- **Lee:** MED-5 en `fichas.md`; `feature_report.py` (`read_features`, `process_features`,
  `horizontal_report`, `CONFIG`); `feature_cli.py`; `pairing.py` (`read_run_config`); los tests de
  `horizontal_report` (`rg horizontal_report packages/evaluation/tests`); `METODOLOGIA.md` §4.
- **Haz:**
  - `asg-report-features ROOT --horizontal OUT --manifest MANIFIESTO`: por celda y nivel, la
    diferencia de cada rasgo entre cada unidad derivada y su fuente (C18, `source_run.json`) o su
    control, emparejada por obra; mediana, mínimo y máximo de las diferencias y n de pares.
  - Agrupa por `pipeline_version` y da `generator_version` como dato: el parche de P05.2 (7.22.x)
    no parte un grupo.
  - Los 24 núcleo primero, después P y K; lo no medido sale `no medido`, nunca cero; conserva la
    frase de interpretación (asociaciones, n por celda).
  - Salida en JSON y en una tabla CSV legible para la tesis (P09 la regenerará).
  - Sin `--manifest`, `--horizontal` y `--axis` se comportan igual que hoy.
- **No hagas:** importar stagecraft (el manifiesto se lee como JSON del disco); tocar `rasgos.csv`;
  p-valores o pruebas de hipótesis; ponderar rasgos (es el juez, P07).
- **Prueba:** amplía los tests de `horizontal_report` con runs de fixture: una fuente, dos
  derivados con `source_run.json` y versiones 7.22.0 y 7.22.1, y un rasgo sin medir.
  `.\run-tests.ps1` y `.\quality.ps1`.
- **Hecho cuando:** con ese fixture el informe da las diferencias emparejadas por celda en un solo
  grupo de pipeline 7.22, y el `--axis` de siempre devuelve lo mismo que antes.

#### P05.4 · Piloto de la matriz en una obra
- **Modo:** S+P · **Cuota:** ~150 llamadas principales y 0 de función si P05.1 reutiliza la base
  de la obra 03 (el `--dry-run` da la cifra) · **Paquete:** — (un arreglo pequeño del runner o del
  informe entra aquí con su parche; uno grande, para y propone tarjeta)
- **Lee:** la entrada de la matriz en `decisions.md` §2; `matriz.csv`; el README de stagecraft
  (`asg-matrix`).
- **Haz:** `asg-matrix packages/evaluation/planilla/matriz.csv --obras 03 --dry-run`, enseña el
  coste y espera; lanza una repetición de las celdas baratas de la obra 03 (sin simulados nuevos);
  relánzalo y comprueba que no gasta nada; `asg-features --root <run>` en cada run del piloto;
  `asg-report-features` con el manifiesto. Anota en este bloque el coste real por tipo de unidad.
- **No hagas:** lanzar otras obras; `--force`; tocar el generador.
- **Prueba:** manifiesto completo; relanzar = 0 llamadas; `C18` correcto en cada derivado; el
  informe da un solo grupo 7.22.
- **Hecho cuando:** el piloto está completo y extraído, y su informe sale con los pares de la
  obra 03.

#### P05.5 · Generar la matriz, día 1
- **Modo:** S · **Cuota:** la del día 1 que fije P05.1 (≤ ~450 principales y ≤ ~450 de función)
  · **Paquete:** —
- **Lee:** la entrada de la matriz en `decisions.md` §2 y este bloque.
- **Haz:** `asg-budget`; `asg-matrix … --celdas <las del día 1> --dry-run`, enseña el coste y
  espera; lánzalo; al acabar, `asg-budget` y el `--dry-run` de lo pendiente. P05.1 reescribe esta
  tarjeta con las celdas concretas.
- **No hagas:** `--force`; lanzar celdas de otro día; repetir una unidad a mano fuera del runner.
- **Hecho cuando:** las unidades del día 1 están `completed` en el manifiesto, o anotadas aquí con
  su fallo.

#### P05.6 · Generar la matriz, día 2
- Igual que P05.5, con las celdas del día 2. P05.1 añade P05.6b, P05.6c… si hacen falta más días.

#### P05.7 · Extraer los rasgos de la matriz
- **Modo:** S · **Cuota:** 2–3 llamadas por historia (las de la matriz más las 9 líneas base,
  cuya extracción anterior es de la huella vieja) · **Paquete:** —
- **Lee:** `decisions.md` §2 («Lista núcleo fijada»); el manifiesto; el README de evaluación
  (`asg-features`).
- **Haz:** solo después de H2: si el tutor reabrió la lista núcleo, se cierra antes de extraer.
  `asg-features --root <run> --dry-run` sobre cada run del manifiesto y las líneas base
  `Stories/Baseline/0{1,3,4}-*-{1,2,3}`; enseña el coste y espera; extrae con la selección por
  defecto (`core`). Una extracción incompleta se repite una vez; si vuelve a fallar, queda
  `incompleta` y sus rasgos, `no medido`. Anota aquí cuántas quedan incompletas.
- **No hagas:** `--selection all` salvo que P05.1 lo pida; cambiar de modelo de extracción
  (`gemini-3.5-flash-lite`, `decisions.md` §2).
- **Hecho cuando:** cada historia de la matriz y las 9 líneas base tienen `features.json`
  compatible con la huella vigente, o están anotadas como incompletas.

#### P05.8 · Leer el análisis horizontal
- **Modo:** S+P · **Cuota:** sin cuota · **Paquete:** — (docs)
- **Lee:** la entrada de la matriz y la regla de ruido en `decisions.md` §2; §4 «Ruido»;
  `METODOLOGIA.md` §4 y §10; las EXP elegidas en `fichas.md`.
- **Haz:** `asg-report-features Stories --manifest … --horizontal
  Evaluations/horizontal/horizontal-<fecha>.json` y su CSV. En `docs/resumen.md`, una sección
  fechada «Análisis horizontal» con la tablita comparada por eje (núcleo y los P y K que
  correspondan: P27 para la memoria, P39–P42 para el inventario, P33–P34 para la visión, K01–K02
  para el coste), n por celda y la lectura de cada EXP elegida. En `METODOLOGIA.md` §4, el resumen
  y el enlace. Borra de `fichas.md` las EXP cerradas.
- **No hagas:** frases causales; interpretar diferencias por debajo de la regla de ruido; contar un
  juez LLM o una lectura a ciegas como medida; recomendar una configuración «mejor» (T11) o
  cambiar predeterminados del generador.
- **Prueba:** cada cifra de la sección sale del JSON del informe; las tablas llevan fecha y
  alcance.
- **Hecho cuando:** `docs/resumen.md` tiene la tabla por eje con fecha, alcance y n, cada EXP
  elegida tiene su párrafo y ninguna frase atribuye causas. Cierra P05.

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

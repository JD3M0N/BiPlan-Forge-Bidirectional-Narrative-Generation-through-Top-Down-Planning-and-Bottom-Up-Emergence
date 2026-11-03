# Roadmap

Del generador congelado a la tesis escrita, por fases. Cómo se trabaja: [phase.md](phase.md).
Lo decidido: [decisions.md](decisions.md), con las **reglas del tutor** (T1–T11) en su §1.
Las fichas heredadas del antiguo `TODO.md`, íntegras: [fichas.md](fichas.md).

## Estado actual

- **Siguiente:** P08.3 · `asg-rank` para la tesis: las diez, las marcas y las fichas (modo `S+P`, sin cuota). **H2** cerrado por Josue el 2026-10-31 (el tutor vio `planning/h2.md`); **H3** reducido (piloto cerrado y exportado, P07.5) pendiente de que Josue lo acepte.
- **Versiones** (2026-11-03): Stagecraft 7.22.2 (pipeline 7.22), core 0.8.2, evaluación 2.1.10,
  Telegram 6.0.3, Studio 0.3.0.
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
  - P05.1 · Matriz A en `decisions.md` §2 y `matriz.csv` (M01 simulado con predeterminados congelados, 3 obras × 2 rep.; M03 narrativo `--plan-from`; M04–M07 tono y visión con `--narrate-from`): 35 unidades, ~1.540 principales y ~515 de función; la base 03-r1 es el run 7.22 del faro; regla de ruido fijada; EXP-2 y EXP-6 a idea-bank.
  - P05.2 · `asg-matrix MATRIZ.csv [--dry-run --celdas --obras --repeticiones --manifest]` (`tools/matrix.py`): corre en serie con `preflight`, manifiesto atómico en `Evaluations/horizontal/`, reanuda sin repetir llamadas y adopta runs ya hechos por `planilla/semillas.json` (M01 03-r1 y las 9 líneas base); Stagecraft 7.22.1.
  - P05.3 · `asg-report-features RAÍZ --horizontal OUT --manifest M` da las diferencias derivada − fuente por celda (C18 comprobado), un solo grupo por pipeline, núcleo primero, `no medido` y lectura «dentro del ruido» según la regla; JSON y CSV; evaluación 2.1.6. Cierra MED-5.
  - P05.4 · Piloto de la obra 03 (M03–M07, repetición 1, sobre la base 03-r1): 5 unidades completas y relanzar gasta 0; coste real 78 llamadas principales (narrativo 14, simulado derivado 16 cada uno; el tope de la tarjeta era 146) y 21 de extracción de rasgos (núcleo, `flash-lite`); extracción `incompleta` en 3 de 5 (M03, M05, M06), como en P04.7; informe con un solo grupo 7.22 y 5 pares (C18 correcto), todos «n insuficiente» con n = 1. Salida en `Evaluations/horizontal/piloto-03/`.
  - P05.5 · Bases M01 01-r1 (`la-sombra-del-volcan`), 04-r1 (`la-ultima-funcion`) y 03-r2 (`el-misterio-del-faro`) `completed` en el manifiesto, sin fallos; en dos invocaciones del runner (`--obras 01,04 --repeticiones 1` y `--obras 03 --repeticiones 2`, porque el filtro no admite uniones); coste real 287 principales y 186 de función (el tope era ~400 y ~310). Quedan 27 unidades (996 principales y 206 de función por `--dry-run`, estimación que sobreestima).
  - P05.6 · Derivadas M03–M07 de 01-r1 y base M01 01-r2 (`la-promesa-del-volcan`) `completed`; la base M01 04-r2 queda anotada como fallo (`cuota agotada en M01/04/r2`, 2026-10-30, sin generar) y pasa a P05.6c junto a sus derivadas. En PowerShell, una lista de obras va entre comillas (`--obras '01,04'`); desde la raíz hay que pasar `packages/evaluation/planilla/matriz.csv`.
  - P05.6b · Sin generar: las 15 derivadas M03–M07 de 04-r1, 03-r2 y 01-r2 no cupieron (2026-10-30, el preflight de `asg-matrix` dejó 1 llamada principal frente a ~19 por historia y no escribió el manifiesto); Josue aceptó el fallo y pasan a P05.6c.
  - P05 · Cerrada por decisión de Josue el 2026-10-30 sin ejecutar P05.6c, P05.7 ni P05.8: 14 de las 35 unidades de la matriz están hechas (bases y derivadas de P05.4–P05.6) y 21 sin generar por cuota; no hay extracción de rasgos de la matriz ni sección «Análisis horizontal» en `docs/resumen.md`.
  - P06.1 · Diseño del estudio en `decisions.md` §2: 15 historias 7.22 (5 premisas × narrativo, simulado y línea base; 3 de la matriz y 2 de participantes), ≥ 12 lectores sin el autor, parada con ≥ 6 decididas por historia y criterio, grafo conexo o 21 días; sin encabezados ni audio (P06.3 retirada, OPS-3 a idea-bank); `Evaluations/estudio-tesis/` como `DEFAULT_STUDY`; la base de `Evaluations/estudio` corregida como sintética.
  - P06.2 · `/estudio` sin encabezados ni audio (`neutral_story`, `send_story(plain=True)`) y con aviso de seudónimo; con el estudio en `evaluation`, comandos y `/start` ofrecen `/estudio` en vez de `/evaluar` (la lista se publica al arrancar: reiniciar el bot tras `open`); `DEFAULT_STUDY` = `Evaluations/estudio-tesis/`; el `.env` coincide con los predeterminados congelados (solo difieren formato, perfil y audio, que fija la petición o el bot); Telegram 6.0.3.
  - P06.4 · Base sintética `Evaluations/estudio` cerrada y exportada (`export-sintetico-2026-10-31.json`); piloto abierto en `Evaluations/estudio-piloto-722/study.sqlite3` con 6 historias 7.22 fuera del estudio (3 simuladas, 1 narrativa, 2 líneas base `-2`), huella `077eefd52b6810c342b0ad6c9e060ceeabd202b951f575d325ff323de250220c`; falta marcar al autor (`asg-study author ID`) y que Josue invite a los lectores.
  - P06 · Cerrada por decisión de Josue el 2026-10-31 sin ejecutar P06.5, P06.6 ni P06.7: piloto con 0 votos guardados y 5 lectores con notas (9 fallos anotados en el bloque de P06, sin arreglar); sin estudio real, sin votos humanos y sin **H3**.
  - P07.1 · «Datos del juez (P07.1)» en `decisions.md` §2: el piloto se votó con hoja de orden fijo (mismos 5 pares, orden y A/B para los 5 lectores; el bot no da esa secuencia) y sus 69 votos entrenan un juez exploratorio; entran con `import-votes` en esquema 10 y `seconds` nulo; extracciones repetidas hasta completar; validación por familias en una cifra de 2 pliegues; grafo partido, sin τ.
  - P07.2 · `asg-study import-votes CSV --protocolo JSON` (`StudyRepository.import_votes`): importa votos transcritos todo o nada, con el orden A/B de la hoja, `seconds` nulo y `votos-importados.json` (protocolo, SHA-256) junto a la base; sin ejecutar sobre la base real (P07.5); evaluación 2.1.7.
  - P07.3 · El informe del juez (`MODEL_VERSION` 3) da la longitud sola también por familias (`length_baseline.by_story/by_family`), la cobertura (votos probados / votos) en cada validación y la colinealidad por criterio (pares |r| ≥ 0,8, número de condición, constantes); evaluación 2.1.8.
  - P07.4 · `asg-perturb DB --out DIR [--seed N]` escribe por historia congelada `<id>-shuffled` (capítulos barajados, tercios de párrafos en las líneas base, nunca el orden original) y `<id>-no-ending` (prefijo sin el último quinto de los párrafos), con `perturbation.json`; `--casos` arma el JSON de `asg-judge --perturbations` solo con extracciones compatibles (`build_cases`); sin cambio de visión; evaluación 2.1.9, core 0.8.2.
  - P07.5 · Los 69 votos transcritos (cotejados por Josue) importados en `Evaluations/estudio-piloto-722/study.sqlite3` (copia previa `study.antes-votos.sqlite3`, CSV `af101770…`); base `closed`, `export-piloto-2026-11-02.json` coincide fila a fila con el CSV, todos con `seconds` nulo; `preferencias.json` da `insufficient` en los tres criterios (grafo en dos componentes) y acuerdo cercano al azar (α −0,14 a 0,05); subsección «Piloto 7.22 (votos transcritos)» en METODOLOGIA.md §5.
  - P07.6 · Rasgos núcleo (`gemini-3.5-flash-lite`) de las 6 historias del piloto y de sus 12 perturbaciones (`asg-perturb`): 17 de 18 extracciones completas; X15 de H3 se tomó, con aprobación de Josue, de un intento archivado del mismo protocolo (`decisions.md` §2, P07.6; las 5 versiones que lo miden dan 1), y `s037…-no-ending` (sin R03) quedó fuera de `casos.json` (11 de 12 casos, filtrado a mano: no regenerar); las 6 pasan los controles de `train_judge`; tablita en `tabla-rasgos.json`/`.csv`. **653 llamadas reales** (178 el 2026-11-02 y 475 el 2026-11-03) frente a ~54 estimadas, ~45 perdidas al rehacer una H3 casi completa.
  - P07.7 · `asg-judge` sobre el piloto (sin cuota, entrenado una vez): `juez.json` `fitted` en los tres criterios, pero **no generaliza**: fuera de muestra 0,40 / 0,40 / 0,43 por historia y 0,40 / 0,50 / 0,43 por familia, por debajo del azar o igual y de la longitud sola (0,60 / 0,70 / 0,62); sin τ (grafo partido), matriz singular, perturbaciones que bajan 4, 7 y 4 de 11 veces. «Resultado del juez (piloto 7.22)» en METODOLOGIA.md §6 y «Juez para P08» con huellas en `decisions.md` §2. Cierra P07.
  - P08.1 · «Ranking del corpus (P08.1)» en `decisions.md` §2: ranking exploratorio con el juez congelado (los tres criterios `fitted`, no generaliza) y el orden por longitud sola como control; alcance escalonado (56 por extraer en 7.20+ y líneas base, 66 en 7.0–7.19, recuento sin cuota); 3 reanudaciones, un `--force` y otras 3 por texto, sin combinar intentos; tope de 400 llamadas al día; las diez del combinado sin las 6 de entrenamiento; marcas `training`, `version-no-comparable` y `premisa-no-vista`. Tarjetas P08.2–P08.6 corregidas.
  - P08.2 · `asg-features --root Stories --elegibles [--desde X.Y] [--reusar DB] [--limite N] [--dry-run]`: solo el corpus elegible (`corpus.scan`), pipelines ≥ X.Y como versión, omite los completos del estudio y acota el lote; el `--dry-run` no crea proveedor y clasifica con la identidad completa (`extraction_identity`, nueva en evaluación; `extraction_compatible` pasa a público). Real: 56 pendientes en 7.20+ (3 se reanudan, 46 sin extraer, 7 con otra huella; ~224 a ~2.016 llamadas) y 122 sin `--desde`; Stagecraft 7.22.2, evaluación 2.1.10.


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

La tablita por historia comparada entre parametrizaciones (T4). Origen: MED-3, MED-5, EXP-1
(EXP-2, EXP-3, EXP-5 y EXP-6 pasaron a [idea-bank](future/idea-bank.md)). Contrato:
METODOLOGIA.md §4 y [evaluation.md](../docs/architecture/evaluation.md).

Lo que ya hay (2026-10-30): `--plan-from` narrativo acepta un run simulado como fuente y escribe
`source_run.json` (C18), así que MED-5 está casi cerrado; `--narrate-from` cambia solo la
narración (voz, tono, método) sin repetir la función; las 9 líneas base de la matriz (M02) están
hechas; `horizontal_report` agrupa por un eje C y por versión, pero no empareja por plan fuente.
No existe runner de matrices. La matriz elegida (P05.1, matriz A) está en `planilla/matriz.csv` y
en `decisions.md` §2, con su regla de ruido.

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

**Cerrada por decisión de Josue (2026-10-30), sin terminar.** Quedan sin ejecutar P05.6c (21 unidades de
la matriz sin generar, por cuota), P05.7 (extracción de rasgos de la matriz) y P05.8 (la sección «Análisis
horizontal» de `docs/resumen.md`). El manifiesto de `Evaluations/horizontal/` conserva lo hecho y lo anotado como
fallo; las tarjetas están en el historial de Git (commit `6c52bb6`). Mientras no se retome, T4 no tiene su
tabla horizontal completa.

### P06 · Estudio humano

Pares a ciegas con tres criterios (T5, T7) y la línea base dentro (T6). Origen: EXP-4.
Diseño fijado en `decisions.md` §2, «Diseño del estudio humano (P06.1)». Guía: [apps/telegram/README.md](../apps/telegram/README.md). Contrato: METODOLOGIA.md §5 y
[evaluation.md](../docs/architecture/evaluation.md).

Lo que hay (2026-10-30): `study.py` (esquema 10) con recogida, votación y cierre; asignación
perezosa de 15 preguntas por lector; `/estudio` funciona en el bot pero está oculto; los runs del
bot se inscriben solos mientras el estudio recoge; `asg-preferences` da Bradley–Terry por criterio,
acuerdo con y sin el autor e intervalos por bootstrap de lectores. Hallazgos al preparar la fase:

- **Los 75 votos de `Evaluations/estudio` son sintéticos:** 5 agentes Claude Opus con perfiles de
  lector (`simulacion/INFORME.md`, 2026-10-25), no 7 lectores humanos (corregido en
  `decisions.md` §2 por P06.1). Son un juez LLM con otro nombre (`decisions.md` §4): no cuentan como votos ni como comprobación
  externa en P07. Esa base sigue en `evaluation` y es la ruta por defecto del bot
  (`config.DEFAULT_STUDY`; `ASG_EVALUATION_STUDY` está vacío en el `.env`).
- **El ciego tiene fugas de presentación:** los runs del sistema empiezan con `# Título` y las
  líneas base no; las historias del bot llevan `story.mp3` y las líneas base y las de la matriz
  no. Un lector puede saber qué es una línea base sin leerla (T5).
- **El `.env` fija opciones del bot** (`ASG_NARRATIVE_VOICE`, `ASG_NARRATIVE_GUIDANCE`,
  `ASG_PROMISE_LEDGER`, `ASG_STORY_FORMAT`…): hay que comprobar que coinciden con los
  predeterminados congelados (T10).
- METODOLOGIA.md §5 dice que la votación va por `/evaluar`; en el bot es `/estudio`. `/evaluar`
  compara las dos historias propias y el autor sabe cuál pidió primero: no es un par a ciegas.

**Cuota.** Votar no gasta. Generar sí (P06.6): las 2 premisas de participantes, cada una con un
Top-Down (~24 principales) y un híbrido (~133 principales y ~103 de función), sus 2 líneas base y
el M03 de la obra 04 (~20): ~340 principales y ~205 de función, un día de cuota.

**Reglas del tutor.** T5: pares a ciegas, A/B o abstención, sin escala; nada en la presentación
delata el mecanismo (P06.2). T6: cada premisa del estudio tiene su línea base de un solo prompt
(P06.6). T7: las tres preguntas de `planilla/criterios_humanos.csv`, ni una más; P06 no añade
preguntas ni «¿por qué?» al estudio. T2 y `decisions.md` §4: ningún voto de un LLM cuenta. T8: la
lista núcleo queda congelada al abrir (P06.6 no abre sin H2 cerrado). T10: el bot genera con el
generador congelado, sin tocar prompts ni `PIPELINE_VERSION`. T11: nada aquí elige ni filtra
historias por un juez. **H3:** votación cerrada y exportada (P06.7).

**Cerrada por decisión de Josue (2026-10-31), sin terminar.** No se ejecutaron P06.5, P06.6 ni P06.7: no
hay votos humanos. El piloto (`Evaluations/estudio-piloto-722/study.sqlite3`) sigue en `evaluation` con 6
historias, 0 participantes y 0 votos; el estudio real (`Evaluations/estudio-tesis/`) no existe y no se
generaron las historias de participantes ni el M03 de la obra 04. Las tarjetas están en el historial de Git
(commit `6af9fd8`). Mientras no se retome, T5, T6 y T7 no tienen estudio, **H3** no se alcanza y P07 no tiene
votos reales con los que entrenar ni validar el juez.

Notas del piloto (`Evaluations/estudio-piloto-722/notas-piloto.md`, 5 lectores; sus elecciones no se
guardaron en ninguna base de este equipo y no se transcriben votos sin ellas). Fallos anotados, sin arreglar:

| Fallo | Lectores | Arreglo propuesto |
|---|---|---|
| No se sabe cuánto dura ni qué pasa si se deja a medias; si un voto se corrige | L1, L2, L4, L5 | Aviso inicial: 15 comparaciones, ~1 h, se sigue con `/estudio`, un voto no se cambia |
| La abstención no se entiende o parece dejar la tarea incompleta | L1, L3, L5 | «"No puedo decidir" es una respuesta válida», sin definir cuándo (METODOLOGIA §5) |
| No se ve si el voto quedó guardado | L2, L4 | Mensaje visible «✅ Guardado: Historia A (comparación n de 15)» |
| Doble toque: `vote()` devuelve `False` y el bot dice «Respuesta guardada» y reenvía la siguiente | L2 | Avisar «Ya habías respondido» y no avanzar |
| Historias ya leídas reaparecen sin explicación | L5 | «Ya leíste estas dos historias; ahora la pregunta es otra» |
| «Lee (o escucha)» con el audio retirado | — | «Lee» |
| Creatividad ambigua (idea o forma de contarla) | L1 | Aceptado: tocaría `que_mirar` de `criterios_humanos.csv` (T7) |
| Navegar entre historias largas en Telegram | L1, L2, L4, L5 | Aceptado: cambio de diseño, no arreglo pequeño |
| Los votos del piloto no se guardaron (`ASG_EVALUATION_STUDY` vacío en el `.env`) | todos | Sin investigar, por decisión de Josue |

### P07 · Juez aprendido

Regresión de los rasgos núcleo a tres números, validada fuera de muestra (T8). Origen: EXP-7
(absorbida en P07.7). Contrato: METODOLOGIA.md §6 y [evaluation.md](../docs/architecture/evaluation.md).

Lo que hay (2026-10-31): `train_judge` (`judge.py`, `MODEL_VERSION` 2) ajusta una logística L2 sin
intercepto por criterio, valida dejando fuera historias y familias, compara con la longitud sola
(solo por historias) y acepta perturbaciones **ya extraídas** (`asg-judge --perturbations`); no
informa la colinealidad que prometió P04.2 ni genera perturbaciones. Exige los 24 núcleo `measured`
o `not_applicable` en cada historia. Los únicos votos humanos son los del piloto
(`Evaluations/estudio-piloto-722/`): 6 historias 7.22 de 2 familias (obra 01: 2 simuladas y la
línea base `-2`; obra 03: 1 simulada, 1 narrativa y la línea base `-2`), 5 lectores, ~69 votos
(L2 hizo 9), votados con una hoja de orden fijo y transcritos a mano (P07.1). La asignación del bot es
perezosa y no se puede repetir: los votos se importan. El esquema 10 admite `seconds` nulo. Los
75 votos sintéticos de `Evaluations/estudio` no entran (`decisions.md` §2 y §4).

**Reglas del tutor.** T1: el juez es la evaluación intermedia. T2 y `decisions.md` §4: solo votos
humanos; las perturbaciones se hacen por código y el extractor solo cuenta. T5: votos de un piloto
ciego (A/B/abstención); sus fugas se declaran. T6: las 2 líneas base están dentro. T7: los tres
criterios, ni uno más. T8: 24 rasgos, regresión L2 de scikit-learn, validación fuera de muestra
por historia y por familia, frente al azar y a la longitud sola. T10: nada toca el generador. T11:
el juez no elige qué generar. P07.1 cambió, con el «ok» de Josue, la decisión de P06.1 de dejar
el piloto fuera.

### P08 · Ranking y diez mejores

El juez congelado de P07 ordena el corpus elegible y se leen las diez primeras (T9). Origen:
EXP-8 (absorbida en P08.3–P08.6). Contrato: METODOLOGIA.md §7 y
[evaluation.md](../docs/architecture/evaluation.md). Decidido en P08.1 («Ranking del corpus
(P08.1)» en `decisions.md` §2): ranking exploratorio con el juez congelado más el orden por
longitud sola como control, alcance escalonado (primero 7.20+ y las líneas base), tope de 400
llamadas al día y las diez del combinado sin las 6 de entrenamiento.

Lo que hay (2026-11-03, `asg-corpus Stories` sin cuota): 346 runs, **130 elegibles** (70
simulados, 48 narrativos y 12 líneas base, del 7.0 al 7.22; ~235.000 palabras, mediana 1.679).
Solo 2 tienen extracción núcleo compatible y completa, 3 compatible pero incompleta, 12 la tienen
con un catálogo anterior y 113 no tienen ninguna. Las 6 del piloto coinciden byte a byte con su
`story.md`, así que `asg-rank --study` reutiliza sus extracciones; el modelo configurado es
`gemini-3.5-flash-lite`, el del protocolo del juez. Quedan ~122 textos por extraer.

- `asg-features --root Stories` recorre todo `story.md` con `rglob`: también los 216 no elegibles
  (anteriores a 7, guiones, fallidos). Gastaría cuota en textos que `asg-rank` excluye después.
- `rank_features` saca las diez de `combined[:10]`, que solo existe si los tres criterios son
  `fitted`. Con un criterio `insufficient`, las diez salen vacías. La hoja `.md` pide
  «Fortalezas» y «Debilidades» sin decir quién las escribe, y no marca las 6 historias de
  entrenamiento, que puntúan dentro de muestra.
- **Coste de extraer.** El `--dry-run` dice «~3 llamadas por texto», pero no es lo medido. P05.4
  gastó ~4 por texto en la primera pasada y dejó 3 de 5 incompletas. P07.6 gastó ~36 por texto
  (653 en 18) hasta completarlas todas. Para ~122 textos, eso va de **~500 a ~4.400 llamadas
  principales**, de 1 a 9 días de cuota. El ledger de `asg-budget` solo guarda totales por día y
  modelo: el coste de un lote se mide con `asg-budget` antes y después.
- **Recuento de P08.1** (2026-11-03, sin cuota): 56 por extraer en 7.20+ y líneas base (~225 a
  ~2.000 llamadas) y 66 en 7.0–7.19. `corpus.scan` no filtra por versión.

**Reglas del tutor.** T9: el juez ordena todo el corpus elegible y se analizan las diez primeras.
Las exclusiones se dicen con su razón. T8: el juez queda congelado (no se reajusta, no se quitan
rasgos, la normalización es la del entrenamiento) y el ranking no es otra validación. T7: tres
rankings principales y el combinado auxiliar. T6: las líneas base se ordenan con las demás. T2 y
`decisions.md` §4: el extractor solo cuenta. Los campos de juicio de las diez (fortalezas,
debilidades) los escribe Josue, nunca Claude. T11: el ranking es posterior y no elige qué
generar. T10: nada aquí toca el generador ni `PIPELINE_VERSION`; `asg-features` es una
herramienta, no el generador. Lo del X15 de H3 (P07.6) no se extiende a P08.

**H4:** enseñar al tutor el juez, el ranking y las diez (`planning/h4.md`, P08.6).

#### P08.3 · `asg-rank` para la tesis: las diez, las marcas y las fichas
- **Modo:** S+P · **Cuota:** sin cuota · **Paquete:** asg-evaluation
- **Lee:** «Ranking del corpus (P08.1)» en `decisions.md` §2; `rank_features` y `_ineligible`
  en `judge.py`; `rank_main` en `learning_cli.py`; `read_features` y `process_features` en
  `feature_report.py`; las pruebas de ranking de `packages/evaluation/tests/test_preference_learning.py`.
- **Haz**, según P08.1:
  - Las diez: las primeras del combinado auxiliar sin las marcadas `training` (si una cae entre
    las diez, entra la siguiente); empates por ruta, como hoy. Los tres rankings por criterio y el
    combinado siguen enteros, con las de entrenamiento dentro y marcadas.
  - Orden por longitud sola (T01) como control, en una clave nueva (`length_control`), sobre las
    mismas historias ordenadas por el juez; T01 se calcula por código. No cambia el juez.
  - Marcar cada historia ordenada: `training` (su `text_hash` está en `--study`),
    `version-no-comparable` (pipeline 7.0 y 7.1) y `premisa-no-vista` (el prompt de la petición
    no es el de las obras 01 ni 03 de `planilla/prompts.md`).
  - «Qué tienen y qué no»: para cada rasgo núcleo, la mediana de las diez frente a la del resto
    de ordenadas, y el valor de cada una frente a la mediana del corpus. Es descriptivo y no
    pondera nada.
  - Hoja `.md` de las diez rellenada por código, que dice al principio que el juez no generaliza
    y que las diez describen lo que premia este ajuste: run y ruta, formato y versión, marcas,
    puestos en los tres rankings, el combinado y la longitud, rasgos con su mediana, configuración (C), proceso (P) y coste
    (K) cuando existan, y enlace al análisis horizontal solo si el run está en
    `Evaluations/horizontal/`. «Fortalezas» y «Debilidades» quedan vacías, marcadas «(Josue)».
  - Conservar las claves actuales del JSON (`rankings`, `combined_auxiliary`, `stories`,
    `excluded`, `top_ten`) y añadir las nuevas.
- **No hagas:** cambiar pesos, normalización, `MODEL_VERSION` ni `train_judge`; leer las
  historias con un LLM; escribir juicios en la hoja.
- **Prueba:** ampliar las pruebas de ranking de `test_preference_learning.py`: una historia de
  entrenamiento en cabeza del combinado queda marcada y fuera de las diez; el orden por longitud;
  las marcas de versión y premisa; la tabla de medianas; la hoja sin campos de juicio rellenados.
  Suite y `quality.ps1`.
- **Hecho cuando:** `asg-rank` sobre los datos de prueba da las diez según P08.1, con marcas y
  hoja; evaluación 2.1.11 con su CHANGELOG.

#### P08.4 · Extraer el corpus elegible, un lote por día
- **Modo:** S · **Cuota:** un lote por día, con el tope de P08.1 · **Paquete:** —
- **Tarjeta repetible:** se queda en el roadmap y cada sesión anota su lote en «Hechas» como
  `P08.4 (lote k, fecha) · …`, hasta cubrir el alcance de P08.1 o hasta que Josue pare.
- **Lee:** «Ranking del corpus (P08.1)» en `decisions.md` §2; el README de evaluación
  (`asg-features`); el último lote anotado en «Hechas».
- **Haz:**
  - Enseña `asg-budget` y `asg-features --root Stories --elegibles --desde 7.20 --reusar
    Evaluations/estudio-piloto-722/study.sqlite3 --dry-run` (pendientes, modelo y coste). El
    modelo tiene que ser `gemini-3.5-flash-lite`. Espera el «ok». Sin `--desde` (7.0–7.19) solo
    cuando 7.20+ esté cubierto y Josue lo pida.
  - Lanza el lote con `--limite N` dentro del tope de **400 llamadas principales al día** y
    aplica los reintentos de P08.1: por texto, hasta 3 reanudaciones; si sigue incompleto, un
    único `--force` desde cero y otras 3 reanudaciones; después queda «Extracción incompleta».
    Lleva la cuenta de intentos por texto en la línea del lote.
  - Después, `asg-budget` otra vez. Anota textos lanzados, completos, incompletos, los rasgos que
    fallan y las llamadas medidas.
  - **Parada:** si en el primer lote menos de la mitad de los textos lanzados queda completa,
    para y avisa antes de seguir gastando.
- **No hagas:** `--force` sobre extracciones completas ni más de un `--force` por texto;
  `--selection all`; extraer textos no elegibles; editar a mano un `features.json`; combinar
  intentos (lo de P07.6 no vale aquí); pasar del tope; cambiar de modelo.
- **Hecho cuando:** cada texto del alcance está completo o agotó sus reintentos, según el
  `--dry-run`. Entonces se borra la tarjeta y se deja una línea final con los totales.

#### P08.5 · Ordenar el corpus y publicar el ranking
- **Modo:** S · **Cuota:** sin cuota · **Paquete:** —
- **Lee:** METODOLOGIA.md §7; «Juez para P08» y «Ranking del corpus (P08.1)» en `decisions.md`
  §2; la última línea de P08.4 en «Hechas».
- **Haz:**
  - Comprueba que el `data_hash` del juez es el de «Juez para P08».
  - `asg-rank <juez.json> Stories --study Evaluations/estudio-piloto-722/study.sqlite3
    --output Evaluations/ranking/ranking-<fecha>.json`, que escribe también la hoja `.md`.
  - «Ranking del corpus (P08, fecha)» en METODOLOGIA.md §7:
    - cobertura: elegibles, ordenadas y excluidas por razón;
    - que el juez no generaliza (METODOLOGIA.md §6) y que el orden describe lo que premia este
      ajuste, no la calidad;
    - versiones y marcas;
    - las primeras de cada ranking y del combinado, y el orden por longitud al lado (cuántas
      de las diez coinciden con las diez más largas);
    - dónde caen las líneas base y las 6 de entrenamiento;
    - la tabla «qué tienen y qué no»;
    - limitaciones: juez exploratorio de 2 familias y 5 lectores, premisas no vistas, sesgo
      por extracciones incompletas o ausentes (alcance escalonado), longitud y versiones
      mezcladas.
  - Avisa a Josue de que toca leer las diez y escribir sus fortalezas y debilidades en la hoja.
- **No hagas:** reajustar o reentrenar el juez; cambiar la regla de las diez tras ver el
  ranking; llamar «calidad» al número; rellenar juicios.
- **Hecho cuando:** `ranking-<fecha>.json` y `.md` escritos y sección publicada con sus cifras.

#### P08.6 · Las diez primeras y H4
- **Modo:** S · **Cuota:** sin cuota · **Paquete:** —
- **Antes:** Josue ha escrito sus fortalezas y debilidades en la hoja de P08.5. Si no, para.
- **Lee:** la hoja `ranking-<fecha>.md`; METODOLOGIA.md §6 y §7; `planning/h2.md` (formato y
  preguntas pendientes); «Juez para P08» en `decisions.md` §2.
- **Haz:**
  - «Las diez primeras» en METODOLOGIA.md §7: qué tienen y qué no (la tabla de código), su
    configuración y su proceso, y las notas de Josue atribuidas a él. Enlaza el análisis
    horizontal, que solo existe para `piloto-03`, porque P05 se cerró sin terminar.
  - `planning/h4.md` para el tutor:
    - el juez: acierto fuera de muestra frente a 0,5 y a la longitud, y los pesos;
    - el ranking y las diez, con el orden por longitud al lado y el alcance extraído;
    - preguntas abiertas: «todas las cosas activadas» (la pregunta 5 de H2, que §2 deja para
      H4), si un juez exploratorio de 2 familias basta para la tesis, y si se retoman P05 y P06.
- **No hagas:** añadir juicios propios a los de Josue; reescribir sus notas; cambiar el ranking.
- **Hecho cuando:** sección y `planning/h4.md` publicados. Cierra P08 y **H4**.

### P09 · Resultados reproducibles

Un comando que regenera todas las tablas y figuras de la tesis desde `Evaluations/` hacia
`redaccion/figuras/` y `redaccion/tablas/`, con fecha y alcance. Origen: ING-8 (contratos
públicos y README), que se cierra aquí.

### P10 · Escribir la tesis

LaTeX en `redaccion/tesis/` (plantilla de MatCom), compilado con `latexmk`. Toda la fase se
contrasta con T1–T11; T11 va a conclusiones como trabajo futuro.

- Se escribe con la skill `write_thesis`, una parte por sesión. Las partes (R00–R12), su orden,
  presupuesto y tarjetas están en
  [redaccion/write_thesis_roadmap.md](../redaccion/write_thesis_roadmap.md), no aquí.
- Las partes que no dependen de datos nuevos (estado del arte, introducción, generador,
  metodología, implementación) pueden escribirse antes; R07 (estudio humano, juez y ranking)
  espera a P07, P08 y P09.
- **H5:** borrador completo al tutor.

### P11 · Reescribir la tesis

Con la skill de reescritura que Josue instalará. Las tarjetas se escriben cuando esté
instalada: una por capítulo, sin cambiar cifras ni citas. **H6:** entrega.

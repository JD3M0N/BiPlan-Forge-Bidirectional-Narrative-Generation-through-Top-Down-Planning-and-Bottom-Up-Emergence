# Roadmap

Del generador congelado a la tesis escrita, por fases. Cómo se trabaja: [phase.md](phase.md).
Lo decidido: [decisions.md](decisions.md), con las **reglas del tutor** (T1–T11) en su §1.
Las fichas heredadas del antiguo `TODO.md`, íntegras: [fichas.md](fichas.md).

## Estado actual

- **Siguiente:** P03.1 (qué es la línea base y qué corpus es elegible, modo `O`).
- **Versiones** (2026-10-28): Stagecraft 7.22.0 (pipeline 7.22), core 0.8.0, evaluación 2.1.0,
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

#### P03.1 · Qué es la línea base y qué corpus es elegible
- **Modo:** O · **Cuota:** sin cuota · **Paquete:** — (solo planning)
- **Lee:** `decisions.md` §1–§4; `packages/evaluation/planilla/matriz.csv` (celda M02);
  `judge._ineligible` y `pairing.read_run_config`; `git show baa016f^:docs/prompts_top_down.md`;
  `asg-study --db Evaluations/estudio/study.sqlite3 status`.
- **Haz:** opciones con recomendación, y espera, para:
  1. **Premisas con línea base:** las obras 01, 03 y 04 de la matriz, cada una con n
     repeticiones (1 llamada cada una), y las del estudio de P06 tras la recogida (ya en EXP-4).
  2. **Catálogo de prompts:** restaurar `docs/prompts_top_down.md` desde `baa016f^`, moverlo a
     la planilla, o copiar el texto de un `request.json`. Y qué variante de perfil recibe la
     línea base.
  3. **`Evaluations/estudio` y sus 3 líneas base de 7.21:** ¿piloto (datos que se conservan,
     fuera del estudio de la tesis) o estudio principal? Si es piloto, actualizar el síntoma de
     EXP-4 en `fichas.md`.
  4. **Corpus elegible para el ranking (T9):** a) todo lo completo en prosa, marcando la versión
     (lo que hace hoy `_ineligible`); b) solo Stagecraft 7.x y las líneas base; c) solo lo
     congelado (7.22) y las líneas base. Con el coste de extraer los rasgos de cada opción en P08
     (unas 2–3 llamadas por historia). Y qué hacer con los Top-Down sin `story_format` y con los
     guiones.
- **No hagas:** código, ni generar historias. Ninguna entrada en `decisions.md` sin el «sí» de
  Josue.
- **Prueba:** ninguna (solo docs).
- **Hecho cuando:** las cuatro decisiones están en `decisions.md` §2, con fecha, y las tarjetas
  P03.2–P03.4 ya las usan.

#### P03.2 · Inventario del corpus, de solo lectura
- **Modo:** S+P · **Cuota:** sin cuota · **Paquete:** asg-evaluation
- **Lee:** P03.1 en `decisions.md`; `feature_report.read_features` y `process_features`;
  `pairing.read_run_config`; `judge._ineligible`; `artifacts.py`; `asg_core/help.py`;
  `packages/evaluation/README.md` §3.
- **Haz:**
  - Un módulo `asg_evaluation/corpus.py` y un comando `asg-corpus <Stories> [--json] [--csv]`
    (registrado en `pyproject.toml` y `help.py`). Lista cada run con: carpeta, formato (y si se
    infirió), versiones, estado, `story.md` y veredicto `elegible`/`excluido` con su razón, según
    P03.1.
  - Lista también las anomalías de MED-6: falta de versión o de `generator_version.json`,
    `story_format` inferido, `failed` con `story.md`, `running` atascado, `.tmp` sueltos y
    archivos que no son runs.
  - `judge._ineligible` reutiliza la razón de corpus para lo que no depende de la extracción, y
    conserva sus mensajes actuales.
- **No hagas:** escribir en `Stories/` ni en `Evaluations/`; llamar a `asg-recover`; tocar
  `rasgos.csv`; añadir códigos a los warnings (es del generador congelado: MED-6b en idea-bank).
- **Prueba:** tests con runs ficticios en `tmp_path`, uno por anomalía (parametrizados) y uno
  por razón de exclusión; un test de `asg-rank` sigue dando los mismos `excluded`;
  `.\run-tests.ps1` y `.\quality.ps1`.
- **Hecho cuando:** `asg-corpus Stories --json` sobre el corpus real da los recuentos de arriba
  (o explica la diferencia), y `asg help` lo lista.

#### P03.3 · Líneas base de la matriz
- **Modo:** S · **Cuota:** ~1 llamada por historia (total según P03.1, unas 9) · **Paquete:** —
- **Lee:** P03.1 en `decisions.md`; `packages/evaluation/README.md` §1; el catálogo elegido en
  P03.1.
- **Haz:** enseña la lista de comandos y el número de llamadas, y espera. Después, `asg-baseline`
  con el texto exacto del catálogo hacia `Stories/Baseline/<obra>-<slug>-<n>/`, con
  `GEMINI_MODEL` en el modelo de la matriz. Comprueba `status: completed`, `pipeline_version`
  7.22 y `llm_usage.json` con 1 llamada.
- **No hagas:** cambiar `baseline.py` ni su instrucción; inscribirlas en un estudio (eso es P06);
  más llamadas que las aprobadas; `RUN_GEMINI_LIVE=1`.
- **Prueba:** `asg-report-features Stories/Baseline --json` da `C01 = Baseline` en todas, y
  `asg-corpus` las da por elegibles.
- **Hecho cuando:** hay una línea base por obra y repetición de M02, anotada con fecha en
  `docs/resumen.md`. Cierra MED-8 (se borra de `fichas.md`).

#### P03.4 · Una decisión escrita por cada anomalía
- **Modo:** S+P · **Cuota:** sin cuota · **Paquete:** — (o parche de asg-evaluation si hay que
  ajustar una razón)
- **Lee:** la salida de `asg-corpus Stories --json`; `stagecraft/tools/recovery.py` (docstring y
  `--help`); METODOLOGIA.md §10.
- **Haz:** agrupa las anomalías y propone una decisión por grupo: excluir con razón, recuperar con
  `asg-recover` (deja rastro), o aceptar como limitación. Espera el «ok». Después:
  - aplica solo lo aprobado;
  - escribe la tabla de exclusiones con fecha y alcance en METODOLOGIA.md §10;
  - guarda la salida en `Evaluations/corpus/inventario-2026-MM-DD.json`.
- **No hagas:** borrar runs, `.tmp` ni el `.html` (se excluyen, no se borran); editar
  `metadata.json` a mano.
- **Prueba:** relanzar `asg-corpus`: cada anomalía restante tiene su decisión en §10.
- **Hecho cuando:** el inventario sale limpio o cada anomalía tiene una decisión escrita. Cierra
  MED-6 (se borra de `fichas.md`).

### P04 · Validar el extractor

Que los recuentos sean los del tutor y sean fiables, antes de abrir la votación.
Origen: MED-9, MED-7. Contrato: METODOLOGIA.md §3.

- Auditoría rasgo a rasgo de `rasgos.csv` contra T3: cada ejemplo del audio y cada dimensión
  de la rúbrica tiene su rasgo, o una razón escrita para no tenerlo.
- Fijar la lista núcleo (decisions.md §2) antes de ver un solo voto.
- Revisión humana de una muestra con `asg-audit-features`, test-retest (`--second`) y contraste
  con los logs (`validable_contra`, métricas de MED-7).
- **H2:** enseñar al tutor la tablita de unas historias y la lista núcleo.

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

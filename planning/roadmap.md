# Roadmap

Del generador congelado a la tesis escrita, por fases. Cómo se trabaja: [phase.md](phase.md).
Lo decidido: [decisions.md](decisions.md), con las **reglas del tutor** (T1–T11) en su §1.
Las fichas heredadas del antiguo `TODO.md`, íntegras: [fichas.md](fichas.md).

## Estado actual

- **Siguiente:** P02.3 · El plan cumple el brief y la ficción va en español (`S`, ~45 llamadas).
- **Versiones** (2026-10-27): Stagecraft 7.21.5 (pipeline 7.21), core 0.8.0, evaluación 2.1.0,
  Telegram 6.0.2, Studio 0.2.2.
- **Hechas:**
  - P00 · Arranque: `planning/`, skill `phase`, migración de `TODO.md` y graphify.
  - P01.1 · Inventario de código muerto: 4 candidatos aprobados por Josue (ver P01.2); sin comandos ni módulos huérfanos.
  - P01.2 · Retirado el código muerto aprobado: `output_choice()`, `output_choice_for()`, `available_keys()`, `pending_keys()` y `SET_BY_PRESET` (los tres últimos pasan a los tests).
  - P01.3 · Reescritos 39 docstrings plantilla y el gate los rechaza; 12 clases Pydantic enviadas a Gemini quedan exentas (ver ING-1 en `future/idea-bank.md`).
  - P01.4 · Docs cotejados con el código (comandos, rutas, enlaces, versiones, constantes): corregidos 3 desajustes (rango de pipeline en el README de stagecraft, `asg-recompute`, salida de `asg-rank`); cierra H0.
  - P02.1 · Narración simulada, 5 pares a ciegas: empate 2–2–1 (B `selected` + editor + ejemplos corrige las actas pero no gana); se mantiene `reported`, sin editor ni ejemplos (en `docs/resumen.md`).
  - P02.2 · Brazos Top-Down, 8 borradores sobre 2 planes: TD-8 y TD-3 cumplen; a ciegas A 3, B 1, así que `scene_cards`, `anchored_critic`, `line_editor` y `style_examples` siguen apagados (en `docs/resumen.md`).

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

#### P02.3 · El plan cumple el brief y la ficción va en español (TD-9, TD-2)
- **Modo:** S · **Cuota:** ~45 llamadas (un narrativo Expansivo con brief y un guion nativo) ·
  **Paquete:** ninguno
- **Lee:** TD-9 y TD-2 en [fichas.md](fichas.md); «Idioma de la ficción» y el párrafo de
  `StoryBrief` en [generation.md](../docs/architecture/generation.md).
- **Haz:**
  - Enseñar el coste y esperar el «ok».
  - Un narrativo con `--brief` del `brief.json` de `20261019-141038-las-islas-del-cielo`.
  - Un guion nativo del prompt 03 del catálogo de `docs/resumen.md` (la médica del faro).
  - Comprobar: el plan trae el ascenso, la tripulación dividida y una decisión final con
    pérdida; slug, nombres y roles en español; el género coincide con la petición.
  - Escribir el resultado en `docs/resumen.md`, y cumple o no cumple en la lista de P02.4.
- **No hagas:** arreglar lo que falle: se anota.
- **Prueba:** `.\quality.ps1` verde.
- **Hecho cuando:** TD-9 y TD-2 tienen resultado escrito con las rutas de los runs.

#### P02.4 · Aplicar las decisiones y rechazar turnos fuera de la ficción (SIM-14) → 7.22
- **Modo:** S+P · **Cuota:** sin cuota · **Paquete:** asg-stagecraft (y asg-studio si cambia
  `catalog.py`)
- **Lee:** SIM-14 en [fichas.md](fichas.md); la lista de abajo; `GenerationOptions` en
  `options.py`; `stage/validation.py`; `writing/language.py`; `test_generation_options.py` y los
  tests de validación de turnos.
- **Decisiones** (las rellenan P02.1–P02.3):
  - `narration_method`: `reported` (empate en P02.1; sin cambio)
  - `line_editor`: apagado (P02.1)
  - `style_examples`: apagado (P02.1)
  - `scene_cards`: apagado (P02.2: A 3, B 1 a ciegas)
  - `anchored_critic`: apagado (P02.2)
  - `typed_clauses`: apagado, sin medir (SIM-26 en idea-bank; nivel de P05).
  - TD-3: cumple · TD-8: cumple (P02.2) · TD-9, TD-2: —
- **Haz:**
  - Cambiar los predeterminados en `GenerationOptions` y en los kwargs de `StoryGenerator`. Si
    un brazo gana en un formato y pierde en otro, queda apagado y se avisa: un predeterminado
    por formato sería otra decisión.
  - SIM-14: un rechazo determinista con código en inglés ASCII para los turnos con vocabulario
    de código (rutas con `/` y extensión, identificadores con guion bajo, comillas invertidas) o
    en un idioma que no es el de la ficción, con la reinyección de siempre.
  - Subir a 7.22.0 y `PIPELINE_VERSION` a 7.22: `SUPPORTED_PIPELINE_VERSIONS`, el comentario de
    `version.py`, `CHANGELOG.md`, `generation.md` y `simulation.md`. Reinstalar el editable.
  - Borrar de `fichas.md` las fichas absorbidas (SIM-25, SIM-24, TD-10, TD-8, TD-3, TD-9, TD-2,
    SIM-14).
- **No hagas:** borrar caminos ni brazos (P05 los usa); cambiar prompts; tocar `evaluation`.
- **Prueba:** `.\run-tests.ps1` y `.\quality.ps1`; un test con el turno «Superset» de SIM-14
  que se rechaza y se reintenta; uno de falso positivo: una réplica corta con un nombre propio
  extranjero pasa; `asg-generate --help` muestra los predeterminados nuevos.
- **Hecho cuando:** los predeterminados son los decididos, SIM-14 tiene sus dos tests, la
  puerta está verde y la versión es 7.22.

#### P02.5 · Validación real, congelación y H1 (SIM-21)
- **Modo:** S+P · **Cuota:** ~30 llamadas del modelo principal y ~110 del de la función ·
  **Paquete:** ninguno (docs y etiqueta)
- **Lee:** SIM-21 en [fichas.md](fichas.md); [decisions.md](decisions.md) §3 y §4.
- **Haz:**
  - Comprobar que `.env` no tiene variables `ASG_*` que contradigan los predeterminados (solo
    nombres, nunca valores).
  - Enseñar el coste y esperar el «ok».
  - Con 7.22 ya confirmado en git, el prompt 03 en los tres formatos (simulado, narrativo y
    guion), en Esencial.
  - Comprobar: ningún capítulo `fallback`, ningún pensamiento en inglés en `turns.jsonl`, el
    primer beat en estancamiento recibe el giro antes de su tope, ninguna línea fuera de la
    ficción, slug y nombres en español. Anotar los beats forzados como limitación conocida.
  - Escribir el resultado en `docs/resumen.md`.
  - Con el texto aprobado por Josue, la decisión «Generador congelado en Stagecraft 7.22.x
    (pipeline 7.22)» en `decisions.md` §3, con los predeterminados, sustituyendo el paréntesis
    «Se completa en P02».
  - `git tag generator-frozen` (local, sin push). Borrar SIM-21 de `fichas.md`.
- **No hagas:** cambiar código; si algo bloquea, parar y proponer P02.4b.
- **Prueba:** `.\quality.ps1` verde; `git tag -l generator-frozen`.
- **Hecho cuando:** los tres runs cumplen, la decisión está en `decisions.md`, la etiqueta
  existe y se anuncia **H1**: Josue prueba el bot en Telegram con los dos enfoques.

---

### P03 · Líneas base y corpus

Una línea base de un solo prompt por premisa del estudio (T6) y un inventario del corpus que
diga qué entra en el ranking (T9) y qué se excluye y por qué. Origen: MED-8, MED-6.
Contrato: [evaluation.md](../docs/architecture/evaluation.md).

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

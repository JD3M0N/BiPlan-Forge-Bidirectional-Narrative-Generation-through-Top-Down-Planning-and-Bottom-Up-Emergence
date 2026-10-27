# Roadmap

Del generador congelado a la tesis escrita, por fases. Cómo se trabaja: [phase.md](phase.md).
Lo decidido: [decisions.md](decisions.md), con las **reglas del tutor** (T1–T11) en su §1.
Las fichas heredadas del antiguo `TODO.md`, íntegras: [fichas.md](fichas.md).

## Estado actual

- **Siguiente:** P01.3 · Docstrings plantilla (ING-1) (`S+P`).
- **Versiones** (2026-10-27): Stagecraft 7.21.4 (pipeline 7.21), core 0.8.0, evaluación 2.1.0,
  Telegram 6.0.2, Studio 0.2.2.
- **Hechas:**
  - P00 · Arranque: `planning/`, skill `phase`, migración de `TODO.md` y graphify.
  - P01.1 · Inventario de código muerto: 4 candidatos aprobados por Josue (ver P01.2); sin comandos ni módulos huérfanos.
  - P01.2 · Retirado el código muerto aprobado: `output_choice()`, `output_choice_for()`, `available_keys()`, `pending_keys()` y `SET_BY_PRESET` (los tres últimos pasan a los tests).

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
Origen: ING-1 en [fichas.md](fichas.md). Contrato: [AGENTS.md](../AGENTS.md) «Límites y
compatibilidad» y la referencia del subsistema que se toque.

#### P01.3 · Docstrings plantilla (ING-1)
- **Modo:** S+P · **Cuota:** sin cuota · **Paquete:** asg-stagecraft
- **Lee:** ING-1 en [fichas.md](fichas.md); `tests/test_source_documentation.py`;
  `pyproject.toml` raíz (`[tool.ruff]`).
- **Haz:**
  - Plan corto: activar o no las reglas `D` de Ruff (y cuáles), y en qué orden reescribir.
  - Reescribir los 42 docstrings plantilla (`schemas/`, `runtime/errors.py`, `agents/base.py`,
    `runtime/quota.py`, `runtime/storage.py`): inglés ASCII, breves, que digan algo que el
    nombre no dice.
  - Borrar ING-1 de `fichas.md`.
- **No hagas:** cambiar código ni firmas; tocar docstrings que ya son útiles.
- **Prueba:** `.\quality.ps1`; `rg` de las plantillas («Represent .* data and behavior», «Run the
  .*Agent workflow») sin resultados.
- **Hecho cuando:** ningún docstring se limita a repetir el nombre y la puerta está verde.

#### P01.4 · Documentación fiel al código y cierre de H0
- **Modo:** S · **Cuota:** sin cuota · **Paquete:** ninguno (solo docs)
- **Lee:** `README.md`, `docs/resumen.md`, `docs/architecture/*.md`, los README de los cinco
  paquetes; `version.py` y los `pyproject.toml` para las versiones.
- **Haz:**
  - Cotejar cada afirmación verificable (versiones, comandos, nombres de artefactos, rutas,
    tests citados) con el código, y corregir lo que no coincida.
  - Quitar lo que ya no exista y lo que repita otra página (una fuente por contrato).
  - Comprobar que `.gitignore` no ignora ningún doc nuevo.
  - `/graphify . --update` para que el grafo refleje la limpieza.
- **No hagas:** reescribir el diseño ni cambiar el estilo de las páginas; tocar `METODOLOGIA.md`
  salvo enlaces rotos; tocar `rasgos.csv`.
- **Prueba:** `.\quality.ps1`; cada comando citado aparece en `asg help`; enlaces relativos
  resueltos (un script rápido que compruebe que existen).
- **Hecho cuando:** los docs describen el código actual y se cierra **H0**.

---

### P02 · Congelar el generador

Cerrar solo lo que impide que una persona lea las historias como historias, validar en real y
congelar. Origen: la sección P02 de [fichas.md](fichas.md) (32 fichas SIM/TD/ING/EXP-9).
Contratos: [generation.md](../docs/architecture/generation.md),
[simulation.md](../docs/architecture/simulation.md). Al cerrar: decisión «generador congelado en
Stagecraft X.Y» en `decisions.md`, etiqueta `generator-frozen`, y las fichas no elegidas pasan a
idea-bank. **H1:** probar el bot en Telegram con los dos enfoques.

#### P02.1 · Elegir qué bloquea
- **Modo:** O (mejor con Opus) · **Cuota:** sin cuota · **Paquete:** ninguno (solo docs)
- **Lee:** sección P02 de [fichas.md](fichas.md); [decisions.md](decisions.md) §1 y §3; las
  cabeceras de `packages/stagecraft/CHANGELOG.md` desde 7.17 (qué se hizo después de cada
  medición).
- **Haz:**
  - Clasificar cada ficha: **bloquea** (un lector humano notaría el defecto en casi toda
    historia: plan que no cumple el brief, final que no llega, actor fuera de la ficción,
    inglés filtrado, narración de respaldo, resumen en vez de escena); **mejora** (no bloquea);
    **solo falta medir** (implementado, sin validar en real).
  - Proponer de 3 a 5 con su cuota estimada (ver el protocolo de medición de
    `decisions.md` §4) y una recomendación. Candidatas de partida: TD-9, SIM-1, SIM-14, TD-2,
    SIM-21, SIM-24, TD-1.
  - Esperar la decisión de Josue. Después: escribir una tarjeta por ficha elegida y una última
    de validación real y congelación; mover las demás a
    [idea-bank](future/idea-bank.md) con su ID.
- **No hagas:** tocar código; elegir más de 5; contar como medida un juez LLM (protocolo §4).
- **Prueba:** cada ficha de P02 de `fichas.md` está en una tarjeta o en idea-bank.
- **Hecho cuando:** Josue aprueba la lista y las tarjetas de P02 están escritas.

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

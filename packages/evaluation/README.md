# ASG Evaluation

La evaluación de la tesis, tal como la pidió el tutor ([METODOLOGIA.md](METODOLOGIA.md)):

1. **Humana, por pares a ciegas.** Las personas comparan dos historias y eligen la que tiene más
   creatividad, mejores personajes o la trama más interesante.
2. **Mecánica, por rasgos con cita.** Un modelo cuenta cosas de cada historia (conflictos,
   mentiras, objetos usados…) y cita el pasaje; el código comprueba la cita.
3. **Intermedia, un juez aprendido.** Una regresión aprende de los pares humanos qué combinación
   de rasgos predice la preferencia, y ordena todo el corpus.

El paquete lee solo JSON, Markdown y SQLite: nunca importa el generador. Lo que se mide está en
[planilla/](planilla/) (`rasgos.csv`, `criterios_humanos.csv` y `planilla_evaluacion.xlsx`).

## Paso a paso

### 1. Recoger historias

El bot de Telegram ([apps/telegram](../../apps/telegram/README.md)) inscribe cada historia que
genera mientras el estudio está en recogida. Las líneas base de un solo prompt se generan y se
inscriben a mano; cualquier otro run completo en prosa también:

```powershell
$db = "Evaluations/estudio/study.sqlite3"
asg-baseline "PREMISA" --output Stories/Baseline/01   # consume cuota
asg-study --db $db add Stories/Baseline/01
asg-study --db $db status
asg-study --db $db exclude ID      # fuera del conjunto; include lo devuelve
asg-study --db $db author ID_DE_TELEGRAM_DEL_INVESTIGADOR
```

La base se crea sola la primera vez que se abre. Solo admite runs completos en prosa
(`narrative`, `simulated` o `baseline`).

### 2. Votar

```powershell
asg-study --db $db open    # congela el conjunto (huella sha256) y abre /evaluar
asg-study --db $db close
asg-study --db $db export Evaluations/estudio/datos.json
```

Los votos de una hoja en papel se importan con `import-votes` (sin cuota), en la fase de
votación y una sola vez por lector (todo o nada):

```powershell
asg-study --db $db import-votes votos-transcritos.csv --protocolo protocolo.json
```

El CSV tiene `lector, pregunta, criterio, historia_a, historia_b, eleccion, fuente`
(`criterio` en español, `eleccion` = `A`, `B` o `abstencion`). El protocolo es un JSON con
`protocolo` (p. ej. «hoja de orden fijo») e `historias` (código de la hoja → ID de historia del
conjunto congelado). Se crean participantes, lecturas y asignaciones con el orden A/B transcrito,
y los votos quedan con `seconds` nulo (marca de transcripción). Junto a la base se escribe
`votos-importados.json` con el protocolo, el SHA-256 del CSV y los recuentos. No usa la
asignación del bot.

Las preguntas se asignan de una en una cuando el lector las pide, sin lista previa de lectores:

- el criterio va en ciclo (creatividad, personajes, trama);
- nunca su propia historia ni una que marcó como conocida;
- nunca repite par y criterio; prefiere historias que ya leyó y los pares menos comparados;
- tope de 15 preguntas por lector (unas 5 historias por 3 criterios);
- se responde A, B o «No puedo decidir»; la abstención no es empate ni victoria.

La exportación es seudónima: sin IDs de Telegram ni rutas locales.

### 3. Rasgos

```powershell
asg-features --study $db --dry-run   # cuántas llamadas costará
asg-features --study $db             # consume cuota; reanudable
asg-audit-features Evaluations/estudio/features/ID.json --output revision.json
asg-report-features Stories --study $db --json tabla.json --csv tabla.csv --horizontal horizontal.json
asg-corpus Stories --json inventario.json --csv inventario.csv   # qué runs entran al ranking
```

- `asg-corpus` solo lee: lista cada run con formato, versiones, estado y veredicto
  `elegible`/`excluido` con su razón (no completado, sin `story.md`, guion, generador anterior a
  Stagecraft 7), y las anomalías (sin versión, formato inferido, `failed` con historia,
  `running` de más de 24 h, `.tmp` sueltos, archivos que no son runs). No ordena nada.

- Solo los 24 rasgos `núcleo` de las capas T, R y X entran al juez; T01 (palabras) controla la
  longitud. Los de proceso (P), coste (K) y configuración (C) van a los informes.
- Cada medida guarda valor, unidad, evidencias y estado: `measured` (incluido cero),
  `not_applicable`, `missing` o `failed`. Cada rasgo se valida por separado: una cita que no
  está en el texto hace repetir solo ese rasgo, una vez, y si sigue mal queda como fallo, nunca
  como cero, sin tirar los demás del lote. Volver a lanzar `asg-features` reintenta solo los
  fallidos. X24 (preguntas respondidas) no aplica si X23 no abrió ninguna.
- `asg-audit-features X.json --texto story.md --hoja hoja.csv [--alcance parcial]` escribe la
  hoja de revisión humana (una fila por ocurrencia con su cita y párrafo, y una por rasgo sin
  ocurrencias, donde se anotan las omitidas; `veredicto` = correcto / incorrecto / dudoso).
  `--pares A1 B1 A2 B2 …` resume el test-retest por rasgo sobre varias historias y
  `--veredictos hoja1.csv …` da la precisión y la cobertura por rasgo (umbrales en `decisions.md` §2).
- `asg-audit-features --second OTRA.json` compara dos extracciones del mismo texto
  (test-retest); `--run DIR` contrasta los recuentos con el log del run simulado (techo del
  log; lo que el run no registró sale «no medido»). `asg-features --root RUTA` mide un corpus fuera del estudio.
- Para el ranking, `asg-features --root Stories --elegibles [--desde 7.20] [--reusar $db]
  [--limite N] --dry-run` mide solo lo que `asg-rank` ordenará: `--elegibles` aplica la regla de
  `asg-corpus`, `--desde` se queda con pipelines ≥ X.Y (como versión: 7.20 > 7.9), `--reusar`
  omite los textos completos en ese estudio congelado y `--limite` acota los textos que gastan
  llamadas en una invocación. El `--dry-run` no crea proveedor: da el modelo, cuántos están
  completos, se reanudan, faltan o tienen otra huella (se rehacen desde cero) y el coste medido,
  de ~4 a ~36 llamadas por texto.

### 4. Preferencias, juez y ranking

```powershell
asg-preferences $db --output preferencias.json --bootstrap 1000
asg-judge $db --output juez.json
asg-rank juez.json Stories --study $db --output ranking.json
asg-perturb $db --out perturbaciones            # textos rotos por código, sin cuota
asg-features --root perturbaciones              # consume cuota
asg-perturb $db --out perturbaciones --casos casos.json
asg-judge $db --output juez.json --perturbations casos.json
```

- Bradley–Terry regularizado por criterio, con intervalos remuestreando lectores, y el acuerdo
  sobre los mismos pares, con y sin el investigador. Sin grafo conectado no hay orden global.
- Tres regresiones logísticas L2 sobre diferencias de rasgos, validadas dejando fuera historias
  y familias de premisa, frente al azar y a la longitud sola (también por familias). Cada
  validación da su cobertura (votos probados / votos) y cada criterio su colinealidad (pares con
  |r| ≥ 0,8, número de condición y rasgos constantes).
- `asg-rank` ordena el corpus con el juez congelado y escribe, junto a los tres rankings y el
  combinado auxiliar, el orden por longitud sola (`length_control`, T01, más largas primero) y
  los puestos de cada historia. Marca cada historia ordenada con `training` (su texto está en
  `--study`; sin él no se marca y el informe lo dice), `version-no-comparable` (pipeline 7.0 y
  7.1) y `premisa-no-vista` (su prompt no es el de las obras 01 ni 03 de `planilla/prompts.md`).
  Las diez (`top_ten`) son las primeras del combinado sin las de entrenamiento;
  `top_ten_profile` compara la mediana de cada rasgo núcleo en las diez, en el resto y en todo
  el corpus ordenado. La hoja `.md` junto al `--output` la rellena el código (marcas, puestos,
  rasgos, C/P/K y el enlace a la matriz si el run está en un manifiesto de
  `Evaluations/horizontal/`, o de `--horizontal DIR`) y deja vacías «Fortalezas (Josue)» y
  «Debilidades (Josue)».
- `asg-perturb` escribe, por historia congelada, `<id>-shuffled` (capítulos barajados, o tercios de
  párrafos en las líneas base) y `<id>-no-ending` (prefijo sin el último quinto de los párrafos),
  con `perturbation.json`; `--casos` arma los pares original/perturbado con extracciones
  compatibles y nombra las que faltan.
- Un juez que no generaliza es un resultado válido: se marca exploratorio.

## Módulos

| Módulo | Qué hace |
|---|---|
| `study.py`, `study_cli.py` | el estudio por pares y `asg-study` |
| `features.py`, `voice_attribution.py` | el extractor de rasgos con cita |
| `feature_report.py`, `feature_cli.py`, `feature_audit.py` | tabla de rasgos, análisis horizontal y auditoría |
| `preferences.py` | Bradley–Terry, acuerdo e intervalos |
| `judge.py`, `learning_cli.py` | el juez aprendido y el ranking |
| `corpus.py` | inventario de solo lectura del corpus y `asg-corpus` |
| `catalog.py` | lee la planilla y fija su huella |
| `pairing.py`, `simulation_report.py`, `artifacts.py` | lectores tolerantes de runs, también para StageCraft |

Los estudios `fixed`, `rolling` y `pack` y la evaluación 1–10 (`evaluation.json`) se retiraron
en 2.0.0. Sus bases y archivos quedan como datos en `Evaluations/` y `Stories/`.

### 5. Tablas y figuras de la tesis

```powershell
asg-results [--evaluations Evaluations] [--tablas redaccion/tablas] [--figuras redaccion/figuras]
            [--ranking ranking/ranking-AAAA-MM-DD.json] [--fecha AAAA-MM-DD]
```

Sin cuota. Lee los artefactos de `Evaluations/` y escribe, por tabla, un `tabular` con `booktabs`
(para `\input{../tablas/x.tex}`) y un CSV con los valores sin formato; la figura del juez es TikZ
(`redaccion/figuras/juez.tex`, sin dependencias nuevas). `manifiesto.json` guarda la fecha, el
SHA-256 de cada entrada y de cada salida, y las tablas que se mantienen a mano. Si falta una
entrada, esa tabla sale como «No disponible», las demás se escriben y el código de salida es 1.
Los números se escriben con coma decimal y signos matemáticos, y las tablas anchas pueden
necesitar `\small` o `\resizebox` en el capítulo.

| Tabla | Entrada |
|---|---|
| `juez`, `perturbaciones` | `estudio-piloto-722/juez.json` (y `protocolo.json`) |
| `preferencias` | `estudio-piloto-722/preferencias.json` |
| `piloto` | `horizontal/piloto-03/horizontal.csv` |
| `matriz` | `horizontal/manifiesto-matriz.json` |
| `ranking_cobertura`, `ranking_puestos`, `ranking_perfil` | el último `ranking/ranking-*.json` (o `--ranking`) |

`tab:lecturas`, `tab:extractor` y `tab:coste` no se regeneran: salen de lecturas con medidas por
expresión regular, de una tabla de este documento (§3) y de los `llm_calls.jsonl` de cada run, y el
manifiesto lo declara en `a_mano`. `Evaluations/` está ignorado por Git: quien clone el repositorio
conserva las tablas ya generadas, no sus entradas.

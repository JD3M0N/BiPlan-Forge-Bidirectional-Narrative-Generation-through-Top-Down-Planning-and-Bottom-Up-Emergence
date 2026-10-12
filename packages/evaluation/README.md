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
generate-baseline "PREMISA" --output Stories/Baseline/01   # consume cuota
evaluation-study --db $db add Stories/Baseline/01
evaluation-study --db $db status
evaluation-study --db $db exclude ID      # fuera del conjunto; include lo devuelve
evaluation-study --db $db author ID_DE_TELEGRAM_DEL_INVESTIGADOR
```

La base se crea sola la primera vez que se abre. Solo admite runs completos en prosa
(`narrative`, `simulated` o `baseline`).

### 2. Votar

```powershell
evaluation-study --db $db open    # congela el conjunto (huella sha256) y abre /evaluar
evaluation-study --db $db close
evaluation-study --db $db export Evaluations/estudio/datos.json
```

Las preguntas se asignan de una en una cuando el lector las pide, sin lista previa de lectores:

- el criterio va en ciclo (creatividad, personajes, trama);
- nunca su propia historia ni una que marcó como conocida;
- nunca repite par y criterio; prefiere historias que ya leyó y los pares menos comparados;
- tope de 15 preguntas por lector (unas 5 historias por 3 criterios);
- se responde A, B o «No puedo decidir»; la abstención no es empate ni victoria.

La exportación es seudónima: sin IDs de Telegram ni rutas locales.

### 3. Rasgos

```powershell
extract-story-features --study $db --dry-run   # cuántas llamadas costará
extract-story-features --study $db             # consume cuota; reanudable
audit-feature-extraction Evaluations/estudio/features/ID.json --output revision.json
report-features Stories --study $db --json tabla.json --csv tabla.csv --horizontal horizontal.json
```

- Solo los 27 rasgos `núcleo` de las capas T, R y X entran al juez; T01 (palabras) controla la
  longitud. Los de proceso (P), coste (K) y configuración (C) van a los informes.
- Cada medida guarda valor, unidad, evidencias y estado: `measured` (incluido cero),
  `not_applicable`, `missing` o `failed`. Una cita que no está en el texto se repara una vez y,
  si sigue mal, queda como fallo, nunca como cero.
- `audit-feature-extraction --second OTRA.json` compara dos extracciones del mismo texto
  (test-retest). `extract-story-features --root RUTA` mide un corpus fuera del estudio.

### 4. Preferencias, juez y ranking

```powershell
report-preferences $db --output preferencias.json --bootstrap 1000
fit-preference-judge $db --output juez.json
rank-stories juez.json Stories --study $db --output ranking.json
```

- Bradley–Terry regularizado por criterio, con intervalos remuestreando lectores, y el acuerdo
  sobre los mismos pares, con y sin el investigador. Sin grafo conectado no hay orden global.
- Tres regresiones logísticas L2 sobre diferencias de rasgos, validadas dejando fuera historias
  y familias de premisa, frente al azar y a la longitud sola.
- `rank-stories` ordena el corpus y prepara las fichas de las diez primeras (`ranking.md`).
- Un juez que no generaliza es un resultado válido: se marca exploratorio.

## Módulos

| Módulo | Qué hace |
|---|---|
| `study.py`, `study_cli.py` | el estudio por pares y `evaluation-study` |
| `features.py`, `voice_attribution.py` | el extractor de rasgos con cita |
| `feature_report.py`, `feature_cli.py`, `feature_audit.py` | tabla de rasgos, análisis horizontal y auditoría |
| `preferences.py` | Bradley–Terry, acuerdo e intervalos |
| `judge.py`, `learning_cli.py` | el juez aprendido y el ranking |
| `catalog.py` | lee la planilla y fija su huella |
| `pairing.py`, `simulation_report.py`, `artifacts.py` | lectores tolerantes de runs, también para StageCraft |

Los estudios `fixed`, `rolling` y `pack` y la evaluación 1–10 (`evaluation.json`) se retiraron
en 2.0.0. Sus bases y archivos quedan como datos en `Evaluations/` y `Stories/`.

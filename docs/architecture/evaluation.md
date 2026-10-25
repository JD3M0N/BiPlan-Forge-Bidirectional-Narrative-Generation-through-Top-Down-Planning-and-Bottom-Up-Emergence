# Evaluación y compatibilidad del corpus

Referencia de contratos vigentes. Lee solo las secciones del subsistema que vayas a cambiar.
Las reglas generales están en [AGENTS.md](../../AGENTS.md).

## evaluation: el método del tutor

- **La metodología está en [packages/evaluation/METODOLOGIA.md](../../packages/evaluation/METODOLOGIA.md)**,
  fiel al audio del tutor: pares humanos a ciegas en tres criterios, rasgos contables con cita
  (la planilla `packages/evaluation/planilla/`) y un juez aprendido. Los comandos, paso a paso,
  en [packages/evaluation/README.md](../../packages/evaluation/README.md). Los CSV de la planilla son
  la fuente: tras editarlos, regenerar el Excel con
  `python packages/evaluation/planilla/build_planilla.py`. Cambiar `rasgos.csv` cambia la huella
  del catálogo e invalida extracciones y jueces ya hechos.
- **`study.py` tiene un solo modo:** recogida, votación (`open` congela el conjunto con huella) y
  cerrado. Las preguntas se asignan **de una en una** cuando el lector las pide
  (`next_question`), sin lista previa de lectores: criterio en ciclo, nunca la historia propia ni
  una conocida, nunca repite par y criterio, prefiere lo ya leído y lo menos comparado, tope
  `QUESTIONS_PER_READER` (15). La base se crea sola (esquema 10) y rechaza las de los estudios
  retirados (esquemas 1-4), que quedan en `Evaluations/` como datos.
- `export()` es el contrato con `preferences.py`, `judge.py`, `feature_report.py` y
  `tools/extract_features.py`: seudónimo, sin IDs de Telegram ni rutas.
- Los lectores tolerantes (`artifacts.py`, `pairing.py`, `simulation_report.py`) tratan un
  artefacto ausente, roto o de otro tipo como ausente, nunca como fallo. Una cifra que un run no
  registró es **no medida**, nunca cero. StageCraft usa `pairing.py`.

## Precauciones

- **Dos cifras de `simulation_metrics.json` que se leyeron al revés una vez.**
  - `repetition_ratio` solo mira el **habla**, palabra a palabra. No ve paráfrasis ni gestos;
    para eso está `action_repetition_ratio`.
  - `dialogue_survival` cerca de 1 significa que el narrador **transcribió**, no que fuera fiel.
- **Las funciones 7.0 y 7.1 no son comparables sin más con las de 7.2.**
  - Hasta 7.1.1 `CharacterMemory.recall` no aplicaba su tope: cada actor leía toda su memoria
    anterior, y su `retrievals.json` no filtra nada.
  - El esquema pedía `addressed_to` por ids que el actor nunca veía, así que casi no hay
    destinatarios ni susurros.
  - La nota del director se repetía hasta la siguiente lectura.

  Los tres están arreglados en 7.2.0 (SIM-9 y SIM-10). Al comparar versiones, sepáralas por
  `pipeline_version`.

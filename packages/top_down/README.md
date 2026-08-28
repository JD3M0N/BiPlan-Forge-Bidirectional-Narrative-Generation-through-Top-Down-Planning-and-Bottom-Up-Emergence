# ASG Top-Down 5.1

Top-Down 5.0 genera historias mediante un pipeline pequeño de artefactos
independientes:

```text
Solicitud → Mundo → Personajes → DAG de eventos → Capítulos
→ Crítica → Edición → story.md
```

La trama usa eventos genéricos y dependencias `causal` o `temporal`. Gemini
propone el contenido, mientras Python calcula presupuestos, valida referencias,
comprueba la aciclicidad con el algoritmo de Kahn y fija el orden topológico.
Las reglas bloqueantes son exclusivamente estructurales.

```python
from asg_top_down import StoryGenerator

run = StoryGenerator(provider, output_root).run(prompt)
print(run.story_path)
```

`generate()` y `run()` aceptan también un `StoryRequest` y conservan los
callbacks `on_progress`, `on_run_created` y `on_event` usados por consola y
Telegram.

## Artefactos

Cada ejecución nueva guarda únicamente:

```text
request.json
world.json
characters.json
story_plan.json
planning/attempt-*.json       # solo cuando un plan es rechazado
chapters/chapter-*.md
draft.md
review.json                   # si la pasada de calidad se completa
length_audit.json
llm_calls.jsonl
llm_usage.json
pipeline_manifest.json
story.md
```

El primer plan estructuralmente inválido se conserva con su diagnóstico y se
reemplaza una sola vez. Si ambos intentos fallan, el run termina con
`PLOT_VALIDATION_FAILED`. Si falla únicamente la crítica o edición después de
haber escrito todos los capítulos, se entrega `draft.md` como historia final y
la incidencia queda registrada en `metadata.json.warnings`.

Los runs anteriores permanecen intactos y `compare-story-runs` puede comparar
cualquier par que contenga `story.md`, pero solo los runs completos 5.0 se
abren como `StoryRun`.

```powershell
python -m pytest packages/top_down/tests
$env:RUN_GEMINI_LIVE='1'; python -m pytest packages/top_down/tests/test_gemini_live.py
```

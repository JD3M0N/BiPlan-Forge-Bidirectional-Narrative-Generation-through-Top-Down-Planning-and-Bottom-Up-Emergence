# ASG Top-Down 6.0

Top-Down 6.0 genera historias con el contrato de artefactos 6.0:

```text
Analyst → World → Characters → Plot Planner → Plan Critic
→ Drafter → Drama Critic → Writer → métricas observadas
```

Todos los prompts y artefactos internos permanecen en inglés. El idioma pedido
por el usuario comienza únicamente cuando `Drafter` localiza los títulos y
redacta el primer capítulo; `Drama Critic` devuelve sus notas en inglés y
`Writer` produce la revisión final en el idioma solicitado.

```python
from asg_top_down import StoryGenerator

run = StoryGenerator(provider, output_root).run(prompt)
print(run.story_path)
print(run.audio_path)
```

`generate()` y `run()` también aceptan un `StoryRequest` interno ya
normalizado en inglés. Se conservan los callbacks `on_progress`,
`on_run_created` y `on_event` usados por consola y Telegram.

## Plan y garantías

El usuario expresa la profundidad mediante Esencial, Desarrollada o Expansiva.
El perfil reemplaza los objetivos de palabras y capítulos. Esencial conserva una
forma compacta sin un mínimo adicional; Desarrollada exige al menos seis eventos
y Expansiva al menos nueve, con una bifurcación y reunión causal. Python valida
estos mínimos junto con referencias, payoffs dirigidos hacia eventos anteriores,
conectividad, causalidad, aciclicidad y el orden topológico. Gemini decide el
contenido creativo de cada evento.
`payoff_of` admite exclusivamente IDs exactos de eventos anteriores; los
objetos pertenecen a `object_ids` y las condiciones o cambios narrativos se
expresan como texto en `preconditions` y `effects`. Cuando no existe un setup
anterior que pagar, `payoff_of` debe ser una lista vacía.

El primer DAG dispone de dos intentos estructurales. `Plan Critic` puede pedir
una única sustitución completa; si esa sustitución es inválida se conserva el
primer plan válido. Después de congelar el plan, los únicos agentes son
`Drafter`, `Drama Critic` y `Writer`.

`Writer` corrige por capítulos y dispone de un reintento cuando devuelve texto
idéntico pese a notas importantes o introduce encabezados. Ningún candidato se
rechaza por longitud. Un fallo tardío conserva el capítulo o borrador disponible, queda resumido en
`metadata.json.warnings` y detallado en `revision_report.json`.

## Artefactos

```text
generator_version.json
request.json
world.json
characters.json
plan_review.json
story_plan.json
planning/attempt-*.json
planning/refined-candidate*.json
draft_presentation.json
chapters/chapter-*.md
draft.md
review.json
writer/chapter-*-attempt-*
revision_report.json
revisions/chapter-*.md
story_metrics.json
llm_calls.jsonl
llm_usage.json
pipeline_manifest.json
story.md
story.mp3
audio.json
```

Todos los intentos del Writer quedan archivados con su validación estructurada.
`story_metrics.json` registra palabras, capítulos y eventos observados, sin
objetivos ni indicadores de cumplimiento. Los runs nuevos usan
`pipeline_version: 6.0`; `StoryRun` puede abrir runs terminados 5.0, 5.1, 5.2,
5.3 y 6.0. El MP3 se registra en el manifiesto, pero un
fallo de TTS solo añade `AUDIO_GENERATION_FAILED`: `story.md` continúa válido.
`compare-story-runs` continúa aceptando cualquier run con `story.md`.

```powershell
python -m pytest packages/top_down/tests
$env:RUN_GEMINI_LIVE='1'; python -m pytest packages/top_down/tests/test_gemini_live.py
```

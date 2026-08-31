# ASG Top-Down 5.2

Top-Down 5.2 genera historias con el contrato de artefactos 5.1:

```text
Analyst → World → Characters → Plot Planner → Plan Critic
→ Drafter → Drama Critic → Writer → auditorías locales
```

Todos los prompts y artefactos internos permanecen en inglés. El idioma pedido
por el usuario comienza únicamente cuando `Drafter` localiza los títulos y
redacta el primer capítulo; `Drama Critic` devuelve sus notas en inglés y
`Writer` produce la revisión final en el idioma solicitado.

```python
from asg_top_down import StoryGenerator

run = StoryGenerator(provider, output_root).run(prompt)
print(run.story_path)
```

`generate()` y `run()` también aceptan un `StoryRequest` interno ya
normalizado en inglés. Se conservan los callbacks `on_progress`,
`on_run_created` y `on_event` usados por consola y Telegram.

## Plan y garantías

Python calcula los presupuestos de palabras y eventos, valida referencias,
payoffs dirigidos hacia eventos anteriores, conectividad, causalidad,
aciclicidad y el orden topológico. Gemini decide el contenido creativo.
`payoff_of` admite exclusivamente IDs exactos de eventos anteriores; los
objetos pertenecen a `object_ids` y las condiciones o cambios narrativos se
expresan como texto en `preconditions` y `effects`. Cuando no existe un setup
anterior que pagar, `payoff_of` debe ser una lista vacía.

El primer DAG dispone de dos intentos estructurales. `Plan Critic` puede pedir
una única sustitución completa; si esa sustitución es inválida se conserva el
primer plan válido. Después de congelar el plan, los únicos agentes son
`Drafter`, `Drama Critic` y `Writer`.

`Writer` corrige por capítulos y dispone de un reintento cuando devuelve texto
idéntico pese a notas importantes, introduce encabezados o incumple el rango de
longitud del 90–120 %. Un fallo tardío conserva el capítulo o borrador disponible
y queda registrado en `metadata.json.warnings`.

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
revisions/chapter-*.md
length_audit.json
llm_calls.jsonl
llm_usage.json
pipeline_manifest.json
story.md
```

Los artefactos de intentos solo aparecen cuando son necesarios. Los runs nuevos
usan `pipeline_version: 5.1`; `StoryRun` puede abrir runs terminados 5.0 y
5.1. `compare-story-runs` continúa aceptando cualquier run con `story.md`.

```powershell
python -m pytest packages/top_down/tests
$env:RUN_GEMINI_LIVE='1'; python -m pytest packages/top_down/tests/test_gemini_live.py
```

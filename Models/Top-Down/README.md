# ASG Top-Down 3.3

`StoryGenerator` es la única ruta de producción. El pipeline separa la decisión
de qué ocurre, el diseño de expectativas narrativas y la redacción de prosa
mediante artefactos validados.

Todas las instrucciones internas están en inglés. El analista conserva el prompt
original, crea una especificación inglesa enriquecida y mantiene por separado el
idioma solicitado para la ficción y sus títulos.

```python
from asg_top_down import StoryGenerator

generator = StoryGenerator(provider, output_root)
run = generator.generate(prompt_or_request)
print(run.story_path)
```

## Taxonomías flexibles

El catálogo SQLite contiene 24 perfiles ingleses de géneros y story engines.
La recuperación híbrida devuelve hasta tres candidatos y el planificador elige
una taxonomía primaria y, sólo con evidencia explícita, un accent.
`taxonomy_application.json` conserva las referencias seleccionadas y
`taxonomy_brief.json` entrega descripciones naturales a los agentes. Las
convenciones no esenciales pueden fusionarse, reordenarse u omitirse.

## Craft modular previo a STORYLINE

Después de crear el outline, agentes independientes producen una única estrategia
autoritativa:

- `GlobalPPPPlan`: promesa tonal, una línea PPP principal y hasta dos secundarias.
- `CharacterArcPlan`: hitos observables del slider focal de cada protagonista.
- `TryFailPlan`: ciclos Yes-but/No-and con consecuencias persistentes.

Un adaptador puro transforma esos artefactos en obligaciones narrativas neutrales.
STORYTELLER recibe las obligaciones, pero sus contratos `ChapterPlan`, `PlotNode`,
`PlotNodeProposal` y `PlotNodeReview` no contienen campos PPP, sliders ni try-fail.

El planificador genera CBN/CEN y propone CPN incrementales. Cada candidato debe
superar causalidad, intención, conflicto, continuidad, novedad, avance hacia el
final y consistencia del mundo. Sólo eventos aceptados actualizan STORYLINE y NEKG.

## PPP por capítulo y escritura

Con STORYLINE cerrada, `ChapterPPPPlannerAgent` se ejecuta una vez por capítulo,
en orden. Cada `ChapterPPPPlan` enlaza promesa, progreso y payoff locales con IDs
de nodos aceptados y cubre todos los puntos PPP globales asignados al capítulo.

Si un PPP local no puede cubrir sus obligaciones, se repara localmente. Si los
reintentos se agotan, el sistema reconstruye anclas, STORYLINE y NEKG exactamente
una vez, invalida los enlaces locales anteriores y vuelve a generarlos. Una segunda
falta de cobertura detiene el run con un diagnóstico estructurado.

Antes de redactar, un compositor crea `ChapterWritingBrief`: conserva las
instrucciones globales y locales, los hitos y los try-fail relevantes, pero elimina
IDs de nodos y términos CBN/CPN/CEN. El escritor también recibe eventos, causalidad
y contexto de entidades sanitizados, además del capítulo anterior completo.

La auditoría convierte tono, PPP global/local, preparación del payoff, sliders,
try-fail, idioma y constraints explícitos en preguntas bloqueantes. Puede activar
hasta dos reescrituras y conserva la mejor versión disponible ante fallos tardíos.

## Artefactos

```text
craft/
  global_ppp.json
  character_arcs.json
  try_fail.json
  chapters/
    chapter-XXX.ppp.json
    chapter-XXX.brief.json
storyline_obligations.json
storyline_obligation_trace.json
chapter_anchors.json
storyline.json
nekg.json
node_reviews.json
chapters/chapter-XXX.md
draft.md
craft_audit.json
craft_revision_history.json
length_audit.json
story.md
```

`storyline_replans/` y `planning_checkpoint/` conservan los intentos y estados
intermedios. `llm_usage.json` registra llamadas, tokens, esperas y reintentos.

Top-Down 3.3 no lee contratos de craft ni variantes de versiones anteriores y ya
no expone `render_variant()`. `compare-story-runs` continúa comparando dos runs o
dos archivos `story.md` distintos:

```powershell
compare-story-runs Stories/Top-Down/run-a Stories/Top-Down/run-b `
  --output comparacion.html
```

## Desarrollo

```powershell
python -m pytest Models/Top-Down/tests
```

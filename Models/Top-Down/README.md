# ASG Top-Down 4.1

`StoryGenerator.generate/run` es la ruta pública de producción. La versión 4.1
separa hechos y craft mediante una dependencia unidireccional:

```text
Request → StoryFrame → World/Characters → Outline → CBN/CEN
→ CPN incremental validado → STORYLINE/NEKG congelados
→ PromiseLedger + arcos + try-fail → CraftAlignment
→ briefs sanitizados → capítulos → auditoría/reparación selectiva → story.md
```

`storyline/` no importa ni recibe contratos de `craft/`. Recibe una proyección
`StorylineCast` sin sliders y trabaja solo con eventos, entidades, predicados y
mutaciones factuales. Si falla una alineación de craft, se repara el ledger, el
arco, el try-fail o la alineación; nunca se regeneran CBN, CPN o CEN.

```python
from asg_top_down import StoryGenerator

run = StoryGenerator(provider, output_root).generate(prompt_or_request)
print(run.story_path)
```

## STORYTELLER factual

`StoryFrame` fija pregunta central, A-plot, necesidad/B-plot, hilo MICE, estados
inicial/final y la relación entre resolución interna y externa. El mundo usa IDs
estables, mapa de localizaciones, objetos y propietarios. `StorylineState`
mantiene dependencias múltiples y calcula un orden topológico real.

Cada CPN recibe reglas del mundo, elenco factual, estado NEKG vigente, relaciones
pertinentes y eventos recientes. `DependencyValidator` rechaza entidades o
objetos ausentes, personajes muertos, conocimiento no adquirido, movimiento
imposible, precondiciones falsas, dependencias desconocidas y efectos
contradictorios. Un reemplazo del revisor pasa exactamente las mismas reglas.

La generacion interna sigue el ciclo pseudo-CPN de STORYTELLER. `CpnContext`
congela el estado factual de cada intento, `CpnPlanner` genera y revisa el nodo,
y `CpnValidator` aplica una sola tuberia de reglas tanto al candidato como a una
correccion del revisor. Los rechazos reciben codigos y correcciones estructuradas;
si Gemini repite el mismo error, tambien recibe el SVO y los efectos que no debe
reutilizar.

Cada capitulo se construye sobre copias temporales de STORYLINE y NEKG. Solo se
compromete cuando CBN, todos sus CPN y CEN son validos. Al agotar los intentos se
descarta la copia, se regeneran una vez las anclas del capitulo y se reintenta
desde el ultimo prefijo comprometido; los intentos fallidos permanecen auditables.

Los capítulos automáticos tienen 400–900 palabras. Una cantidad explícita de
capítulos prevalece y permite presupuestos desde 200 palabras. Hay al menos un
CPN por capítulo corto y dos desde 400 palabras; el máximo es
`min(8, ceil(target_words/180))`. CBN y CEN reciben 15 % cada uno y los CPN el 70 %.

## Personajes y craft posterior

`CharacterProfile` conserva rol, asiento del elenco, competencia, want, need,
creencia equivocada, herida, fuerza/defecto/costo, regla personal, voz y foco de
percepción. Los arcos pueden ser positivos, negativos o planos. Tras congelar
STORYLINE se planifican cuatro evidencias: establecimiento, presión, elección
decisiva y consecuencia.

`PromiseLedger` contiene un contrato tonal y promesas de dirección,
personaje/conflicto y estructura de género. Cada promesa tiene apertura,
progresos `advance|complicate|reframe` y un payoff único, costoso y preparado.
`ChapterCraftView` es solo una vista derivada; no obliga a ejecutar un PPP entero
por capítulo. `SceneCraftDirective` modela goal/conflict, `yes_but|no_and` o
resolución final, consecuencia, reacción, dilema y decisión.

El escritor recibe el snapshot anterior al capítulo, los cambios que debe
dramatizar, acciones del ledger pertinentes, directivas de escena y tarjetas
conductuales sin IDs internos, taxonomías ni valores de sliders. Nunca recibe
payoffs futuros innecesarios.

## Persistencia y calidad

Las escrituras son atómicas. `pipeline_manifest.json` guarda hashes y etapas;
`checkpoints/` conserva STORYLINE, NEKG y revisiones después de cada respuesta
incremental; `llm_calls.jsonl` incluye intentos exitosos y fallidos.

```text
story_frame.json
world.json
characters.json
outline.json
chapter_anchors.json
storyline.json
nekg.json
node_reviews.json
craft/promise_ledger.json
craft/character_arcs.json
craft/try_fail.json
craft/alignment.json
craft/chapters/*.view.json
craft/chapters/*.brief.json
chapters/state-before-*.json
draft.md
craft_audit.json
craft_revision_history.json
length_audit.json
pipeline_manifest.json
llm_calls.jsonl
story.md
```

El crítico identifica capítulos afectados y la reescritura es local. La
longitud se recalcula parseando la versión finalmente seleccionada.
`DiagnosticAudit` fue eliminado: `craft_audit.json` es la fuente única.

Los runs 3.x terminados continúan leyéndose y comparándose por `story.md`. Los
runs incompletos no se migran. La recuperación automática está pendiente:
Telegram los marca `recovery_pending`, conserva sus checkpoints y continúa con
la cola restante.

```powershell
compare-story-runs Stories/Top-Down/run-a Stories/Top-Down/run-b --output comparison.html
python -m pytest Models/Top-Down/tests
```

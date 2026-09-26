# ASG Stagecraft

Genera historias con un pipeline de agentes LLM sobre Gemini que planifica primero y escribe
después. Hay tres formatos de salida, que comparten el plan:

- **`narrative`** (por defecto): el pipeline Top-Down de siempre, en prosa.
- **`script`**: el mismo plan como guion teatral por actos y escenas, por dos métodos
  (`native` o `adapted`). Ver [docs/guion_teatral.md](../../docs/guion_teatral.md).
- **`simulated`**: los personajes **representan** ese guion con memoria propia, sin verlo, y la
  historia se narra del log de la función. Ver
  [docs/simulacion_escenica.md](../../docs/simulacion_escenica.md).

```text
Analyst → Architect → World → Characters → Plot Planner → Plan Critic → Promise Ledger
  narrative: Drafter → Drama Critic → Writer
  script:    Playwright → Script Critic → Script Writer   (native)
             narrativo completo → Script Adapter            (adapted)
  simulated: guion nativo → Casting → función (Director + actores) → Narrador
→ story.md → story.mp3
```

Los prompts y los artefactos internos van en inglés. El idioma de la ficción empieza cuando se
localizan los títulos y se escribe el primer capítulo, el primer acto o la primera réplica.

## Uso

```python
from asg_stagecraft import StoryGenerator
from asg_stagecraft.formats import StoryFormat
from asg_stagecraft.runtime.config import load_settings
from asg_stagecraft.runtime.provider import provider_from_settings

settings = load_settings()
generator = StoryGenerator(
    provider_from_settings(settings),
    settings.output_root,
    story_format=StoryFormat.SIMULATED,
)
run = generator.generate("Escribe en español un misterio en una isla aislada por la tormenta.")
print(run.story_path, run.audio_path)
```

`generate()` acepta el prompt del usuario o un `StoryRequest` ya normalizado, y los callbacks
`on_progress`, `on_run_created` y `on_event` que usan la consola y Telegram. Devuelve un
`StoryRun` con `run_dir`, `story_format` y las rutas `story_path`, `audio_path`, `script_path`,
`performance_path` y `narration_path`. `StoryRun` solo abre runs terminados de una versión de
pipeline soportada (`SUPPORTED_PIPELINE_VERSIONS`: de 5.0 a 7.1).

El resto de opciones de la fachada (`narrative_profile`, `promise_ledger`, `audio`,
`script_method`, `narrative_voice`, `actor_memory`, `turns_per_beat`) tienen su opción en
`generate-story` o su variable `ASG_*` en `.env.example`; ver [commands.md](../../commands.md).

## Plan y garantías

El usuario expresa la profundidad con un perfil, Esencial, Desarrollada o Expansiva, que es un
contrato cualitativo y no un presupuesto de palabras. `planning/graph.py` valida el plan como un
DAG: referencias existentes, `payoff_of` siempre hacia atrás, dependencias sin ciclos, el suelo
de eventos del perfil y, en Expansiva, una rama con reunión causal. Un plan inválido se rechaza y
se repara reinyectando el error literal. Una vez congelado, ningún agente lo toca: el ledger de
promesas lo anota con beats que citan eventos que ya existen, y se apaga con
`ASG_PROMISE_LEDGER=false`.

Un fallo de configuración o de cuota de Gemini aborta el run. El resto se degrada a un aviso en
`metadata.json` y la historia sigue. Un fallo de TTS solo añade `AUDIO_GENERATION_FAILED`:
`story.md` sigue siendo válido.

## Artefactos

Cada run va a `Stories/Stagecraft/<AAAAMMDD-HHMMSS>-<slug>/`, escrito de forma atómica, con
`pipeline_manifest.json` guardando el SHA-256 y el tamaño de cada artefacto. Comunes a los tres
formatos:

```text
metadata.json              generator_version.json     request.json
world.json                 characters.json            story_plan.json
plan_review.json           promise_ledger.json        llm_calls.jsonl
llm_usage.json             pipeline_manifest.json     story.md
story.mp3 + audio.json
```

- **Narrativo**: `chapters/`, `draft.md`, `review.json`, `writer/`, `revisions/`,
  `revision_report.json`, `promise_audit.json`, `craft_evidence.json` y `story_metrics.json`, con
  la artesanía observada de la prosa. Ninguna de esas cifras viaja a un prompt.
- **Guion**: `script.json`, el contrato que comparten los dos métodos, más `script_metrics.json`.
  La lista por método está en `docs/guion_teatral.md`.
- **Simulado**: el guion nativo más `cast_bible.json`, `stage/`, `memory/`, `performance.json`,
  `narration/`, `narration.json`, `simulation_metrics.json` y `story_metrics.json`, detallados en
  `docs/simulacion_escenica.md`.

## Tests

```powershell
python -m pytest packages/stagecraft/tests
$env:RUN_GEMINI_LIVE='1'; python -m pytest packages/stagecraft/tests/test_gemini_live.py
```

Las pruebas usan proveedores falsos. `test_gemini_live.py` llama a la API real, consume cuota y
se omite salvo con `RUN_GEMINI_LIVE=1`.

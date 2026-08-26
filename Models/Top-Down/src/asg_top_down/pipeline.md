# Pipeline Top-Down 4.1

```text
FACTUAL
Request → normalized AgentStorySpec → StoryFrame → World + Character profiles
→ StorylineCast (sin sliders) → Outline → CBN/CEN → reviewed CPN
→ deterministic dependency checks → STORYLINE DAG + NEKG → FREEZE

CRAFT (solo lectura de STORYLINE)
PromiseLedger ─┐
Character arcs ├→ CraftAlignment → ChapterCraftView → sanitized brief
Try-fail cycles┘
→ writer(state-before) → chapter audit → selective repair → final parse → story.md
```

La frontera es `CraftAlignment`. STORYLINE no importa `craft_models`, no recibe
PPP, sliders ni try-fail y no ofrece una ruta de regeneración desde craft.
Los predicados y mutaciones tipados son la autoridad del estado factual.

Los checkpoints preparan recuperación futura, pero 4.1 no simula `resume`: un
run incompleto queda explícitamente como `recovery_pending`.

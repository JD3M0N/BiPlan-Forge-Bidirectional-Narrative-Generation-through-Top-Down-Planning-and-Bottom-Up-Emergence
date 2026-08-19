# Pipeline Top-Down 3.3

```text
Prompt → Analyst → SQLite retrieval → Planner → World → Characters → Outline
       → Global PPP → Character arcs + Try-fail → neutral obligations
       → CBN/CEN anchors → incremental reviewed CPN → STORYLINE + local NEKG
       → one traceable PPP per chapter → sanitized writing briefs
       → chapter writer → blocking craft audit ↔ rewriter → story
```

`StoryGenerator` coordina el flujo; los prompts viven en agentes especializados y
los validadores puros permanecen fuera de agentes y persistencia.

El adaptador de craft es la única frontera entre PPP/arcos/try-fail y STORYTELLER.
El planificador incremental consume `StorylineObligationsArtifact`, pero sus nodos
siguen siendo contratos narrativos neutrales.

Los PPP locales se crean después de aceptar STORYLINE y enlazan sus beats con nodos
reales. El compositor elimina esas referencias antes de entregar el brief al
escritor. Si la cobertura no puede repararse localmente, se permite exactamente una
replanificación de anclas y STORYLINE antes de fallar.

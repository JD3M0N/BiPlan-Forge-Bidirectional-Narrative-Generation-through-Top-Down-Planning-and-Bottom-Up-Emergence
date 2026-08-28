# Pipeline Top-Down 5.0

```text
StoryRequest
  → WorldArtifact
  → CharactersArtifact
  → StoryPlanDraft
  → validación local + orden topológico
  → StoryPlan
  → capítulos con contexto anterior acotado
  → StoryReview
  → edición única
  → story.md
```

El grafo contiene `PlotEvent` y `EventDependency`. El contenido narrativo es
responsabilidad de los agentes; IDs, referencias, presupuestos, dirección de
dependencias y aciclicidad son responsabilidad del código determinista.

No existe reanudación de runs incompletos. La persistencia atómica, el
manifiesto, las cuotas y la telemetría se mantienen como infraestructura común.

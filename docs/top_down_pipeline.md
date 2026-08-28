# Pipeline Top-Down 5.1

```text
StoryRequest
  ? WorldArtifact
  ? CharactersArtifact
  ? StoryPlanDraft
  ? validaci?n local y orden topol?gico
  ? StoryPlan
  ? cap?tulos con contexto anterior acotado
  ? StoryReview
  ? edici?n ?nica
  ? story.md
```

El grafo contiene `PlotEvent` y `EventDependency`. Los agentes producen el
contenido narrativo; el c?digo determinista valida identificadores, referencias,
presupuestos, direcci?n de dependencias y aciclicidad.

`StoryGenerator` es la fachada p?blica. `StoryPipeline` orquesta las etapas de
an?lisis, mundo, personajes, planificaci?n, escritura, revisi?n y persistencia.
Las auditor?as de longitud viven en un m?dulo independiente.

Los runs incompletos no se reanudan. La persistencia at?mica, el manifiesto, las
cuotas y la telemetr?a se mantienen como infraestructura compartida.

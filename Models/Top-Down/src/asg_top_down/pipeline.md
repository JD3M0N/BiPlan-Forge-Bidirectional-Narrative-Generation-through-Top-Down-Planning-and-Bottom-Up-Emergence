# Pipeline Top-Down v2

```text
Prompt → Analyst → Planner + Taxonomies → World → Characters
       → Director → CPC Graph Processor → Scene Writer
       → Critic → Editor → Story
```

El Planner selecciona un arquetipo principal y hasta dos secundarios desde
`Taxonomies/`. El Director convierte el plan en escenas y beats con relaciones
causales ponderadas. El procesador CPC conserva las relaciones prioritarias que
no crean ciclos y produce un DAG auditable.

El escritor redacta cada escena por separado respetando su estado de entrada,
salida, beats y dependencias. Finalmente, el crítico revisa la cobertura del
grafo y el editor aplica una única revisión sin cambiar sus hechos.

Cada etapa persiste su artefacto en `Stories/Top-Down/<ejecución>/`; los textos
de escena quedan en `scenes/` y el grafo se guarda como JSON y Mermaid.

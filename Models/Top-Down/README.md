# ASG Top-Down v2

Pipeline modular que transforma requisitos en un plan basado en taxonomías,
un grafo causal acíclico de escenas y beats, y una historia revisada.

Los agentes viven en `src/asg_top_down/agents/`. Las taxonomías versionadas de
24 arquetipos narrativos y 12 roles de personaje están en `Taxonomies/` en la
raíz del repositorio. Cada ejecución guarda el grafo procesable en
`narrative_graph.json`, su visualización Mermaid en `narrative_graph.md` y los
borradores individuales bajo `scenes/`.

La API pública continúa siendo `StoryOrchestrator(provider, output_root).run(prompt)`.
Consulta el README de la raíz para instalación y uso.

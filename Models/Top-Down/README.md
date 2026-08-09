# ASG Top-Down STORYTELLER

Pipeline modular que transforma requisitos en capítulos y nodos SVO de tipo
CBN, CPN y CEN. La STORYLINE se acepta únicamente cuando todas sus dependencias
forman un DAG, cada CPN pertenece a un camino CBN-CEN y los capítulos están
conectados. Los CPN se pueden añadir, quitar o sustituir durante un máximo de
cinco replanificaciones transaccionales.

Los agentes viven en `src/asg_top_down/agents/`. Las taxonomías versionadas de
24 arquetipos narrativos y 12 roles de personaje están en `Taxonomies/` en la
raíz del repositorio. Cada ejecución guarda `storyline.json`, el grafo local de
entidades `nekg.json`, el historial de replanificación, las verificaciones de
Freytag y las vistas compatibles `narrative_graph.json`/`.md`. Los bloques de
capítulo se guardan bajo `scenes/`.

La API pública continúa siendo
`StoryOrchestrator(provider, output_root).run(prompt)`.

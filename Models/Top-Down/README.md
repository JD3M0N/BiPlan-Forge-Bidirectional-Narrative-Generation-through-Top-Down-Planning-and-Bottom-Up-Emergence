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

`target_words` admite una tolerancia global de −10 % a +20 %. Las cuotas de
capítulos y nodos son orientativas y nunca hacen fallar un capítulo por sí
solas. Cada redacción y auditoría se conserva en `scenes/attempts/`, y el
resumen acumulado se guarda en `chapter_compliance.json`.

Las ejecuciones fallidas incluyen `error_report.json` y los campos
`error_code`/`error_stage` en `metadata.json`. Las interfaces muestran mensajes
accionables para errores del proveedor, planificación, cobertura de capítulos,
Freytag y longitud final sin exponer credenciales ni trazas internas.

El proveedor aplica una ventana móvil de solicitudes antes de llamar a Gemini,
respeta `retryDelay` en respuestas 429 y registra `usageMetadata` en
`llm_usage.json`. Los valores se configuran con `GEMINI_RPM_LIMIT`,
`GEMINI_RPM_RESERVE`, `GEMINI_TPM_LIMIT`, `GEMINI_MAX_RETRIES` y
`GEMINI_MAX_RETRY_DELAY`. `StoryOrchestrator.resume(run_dir)` reutiliza los
checkpoints válidos y conserva el identificador de la ejecución.

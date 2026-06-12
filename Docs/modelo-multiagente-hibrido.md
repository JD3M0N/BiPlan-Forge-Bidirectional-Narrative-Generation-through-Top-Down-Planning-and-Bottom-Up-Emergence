# Modelo multiagente hibrido

## Resumen

Esta iteracion convierte Story Writers en un pipeline hibrido: primero construye una estructura
top-down con eventos, dependencias y capitulos; despues simula presiones bottom-up sobre personajes
autonomos; finalmente escribe capitulos con contexto comprimido y evalua la historia.

El objetivo es equilibrar coherencia estructural, autonomia de personajes y calidad narrativa sin
agregar dependencias nuevas ni cambiar los estados publicos de las historias.

## Fuentes y decisiones

| Fuente | Decision de arquitectura |
| --- | --- |
| Franco Hernandez Piloto (2025) | Agregar Director indirecto y Character Simulator con memoria/reflexion resumida. |
| Roger Fuentes Rodriguez (2025) | Representar la trama como DAG de eventos y validar dependencias causales, temporales y de mundo. |
| AGENTS' ROOM | Mantener una sala de agentes especializados con scratchpad persistido en `StoryPacket`. |
| STORYWRITER | Usar capitulos adaptativos y Coordinator/ReIO para comprimir contexto antes de cada capitulo. |
| STORYTELLER | Modelar eventos con tripletas SVO y un NEKG ligero como relaciones de entidades en JSON. |
| HANNA | Evaluar relevancia, coherencia, empatia, sorpresa, enganche y complejidad. |
| LitVISTA | Agregar una dimension de orquestacion narrativa para ritmo, tension y arco global. |
| StoryVerse | Traducir intencion autoral en actos abstractos e intervenciones ambientales. |
| Generative Agents / Concordia | Separar memoria/reflexion de personajes y gestion del entorno/director. |
| DOC / Re3 | Reforzar planificacion detallada, expansion por partes y revision de consistencia. |
| EvolvR | Mantener evaluacion LLM-as-judge como senal de mejora, no como metrica unica. |

## Pipeline

1. Architect genera premisa, sinopsis, beats y semillas de eventos.
2. World Builder crea personajes, lugares, objetos, reglas, estado inicial y relaciones de entidades.
3. Director define actos abstractos e intervenciones ambientales indirectas.
4. Character Simulator produce intenciones, acciones plausibles, memoria usada y cambios de mundo.
5. Plot Weaver fusiona todo en DAG, SVO, NEKG ligero y plan de capitulos.
6. Drama Coach ajusta tension, arcos, suspenso y ritmo.
7. Dependency Manager valida coherencia causal, temporal, espacial y de objetivos.
8. Coordinator/ReIO resume contexto relevante para cada capitulo.
9. Chapter Writer escribe capitulos: `short=1`, `medium=3`, `long=5`.
10. Quality Evaluator puntua la historia; si hay contradicciones bloqueantes, Quality Rewriter reescribe una vez y se evalua de nuevo.

Cada etapa se registra en `StoryAgentRun` y se persiste en `Story.story_packet`. La API publica solo expone
progreso, timeline de agentes y evaluacion; no expone prompts ni el packet completo.

## Rubrica

Las dimensiones se puntuan de 0 a 5:

- Relevance: ajuste a la premisa del usuario.
- Coherence: causalidad, temporalidad y continuidad.
- Empathy: claridad emocional de los personajes.
- Surprise: novedad y postdictibilidad de los giros.
- Engagement: capacidad de sostener interes.
- Complexity: riqueza de mundo, trama y subtramas.
- Orchestration: ritmo, tension, transiciones y arco global.
- Overall: juicio integrado de calidad narrativa.

`blocking_issues` se reserva para contradicciones graves. La evaluacion ligera no bloquea por gustos
literarios; solo activa reescritura cuando la continuidad queda rota.

## Limitaciones

- El NEKG vive como JSON, no como Neo4j.
- No hay RAG ni embeddings reales en esta iteracion.
- El Director no ejecuta una simulacion fisica completa; traduce intencion narrativa en presiones ambientales.
- La evaluacion depende del mismo proveedor LLM configurado para el backend.
- El survey "Text-to-Text Automatic Story Generation: A Survey (Ma et al., 2026)" queda pendiente hasta contar con el PDF exacto.

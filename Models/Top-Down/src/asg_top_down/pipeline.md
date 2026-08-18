# Pipeline Top-Down 3.2

```text
Prompt → Analyst → SQLite retrieval → Planner → World → Characters
       → premise/synopsis/chapters → all CBN/CEN anchors
       → incremental reviewed CPN → STORYLINE + local NEKG
       → three independent craft variants → selection
       → chapter writer → blocking craft audit ↔ rewriter → story
```

`StoryGenerator` coordina el flujo, pero los prompts viven en agentes de análisis,
planificación, mundo, personajes, craft y escritura. Los validadores puros viven
fuera de los agentes y de la persistencia.

El planificador incremental no conoce PPP, sliders ni try-fail. Acepta un evento
solo tras los siete controles semánticos, actualiza inmediatamente STORYLINE y
NEKG, y guarda un checkpoint. Un candidato rechazado nunca llega al grafo.

El craft se crea cuando STORYLINE ya es inmutable. Sus referencias son capítulos
y descripciones naturales. La selección no destruye las alternativas: cualquier
variante puede redactarse más tarde con `render_variant()` sin recalcular la
planificación ni alterar la entrega canónica.

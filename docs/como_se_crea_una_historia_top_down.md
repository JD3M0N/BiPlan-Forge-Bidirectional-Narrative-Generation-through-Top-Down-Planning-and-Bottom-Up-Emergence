# Cómo se crea una historia en Top-Down 4.0

Esta guía describe la ruta de producción implementada. La decisión estructural
central es separar la verdad factual de las técnicas destinadas a producir una
experiencia de lectura.

```text
Carril factual
Request → StoryFrame → World/Characters → Outline → CBN/CEN
→ CPN incremental → STORYLINE/NEKG congelados

Carril de craft
STORYLINE congelada → PromiseLedger + arcos + try-fail
→ CraftAlignment → briefs → prosa → auditoría/reparación
```

La dependencia solo apunta de craft hacia una STORYLINE terminada. El paquete
`storyline/` no importa contratos de craft ni puede recibir sliders. No existe
un bucle de PPP que regenere anclas o CPN.

## 1. Analizar sin propagar el prompt crudo

`AnalystAgent` conserva `original_prompt` únicamente para trazabilidad y produce
una especificación normalizada en inglés: idioma de salida, género, tono,
premisa, extensión, capítulos explícitos y constraints reales. Los agentes
posteriores consumen `AgentStorySpec`, que excluye `original_prompt`. Así se
reduce ruido y se evita volver a interpretar instrucciones incrustadas.

## 2. Recuperar una paleta taxonómica actual

`NarrativeSchemaRepository` combina reconocimiento léxico, FTS y embeddings y
devuelve hasta tres perfiles actuales. El plan elige una taxonomía primaria y
solo usa un accent si el prompt contiene evidencia explícita. La taxonomía es
una paleta flexible, no una secuencia obligatoria.

El catálogo legacy 2.x/3.x, `CatalogEntry`, sus semillas y fallbacks fueron
eliminados. Los runs históricos terminados siguen siendo útiles porque el
contrato estable para lectura y comparación es `story.md`.

## 3. Construir el StoryFrame

Antes del outline, `StoryPlanArtifact` fija un `StoryFrame` con:

- pregunta central;
- objetivo externo o A-plot;
- necesidad interna o B-plot;
- hilo MICE exterior;
- estado inicial y final;
- relación causal por la cual el cambio interno habilita o impide el externo.

Este marco evita que PPP tenga que decidir hechos más tarde. El outline recibe
su resultado factual; PPP se deriva únicamente después de congelar STORYLINE.

## 4. Mundo y personajes

El mundo declara IDs estables, reglas, localizaciones conectadas y objetos con
ubicación o propietario inicial. La ficha completa de personaje contiene rol,
asiento del elenco, dominio de competencia, want, need, creencia equivocada,
herida, fuerza, defecto relacionado, costo del defecto, regla personal, voz y
tipo de detalles que percibe.

Los sliders de simpatía, competencia y proactividad admiten tres formas:

- positivo: el foco empieza en 4 o menos y termina en 7 o más; las otras dos
  capacidades funcionales permanecen al menos en 6;
- negativo: el foco cae tres puntos o más, pero el personaje no termina bajo en
  las tres dimensiones;
- plano: cada slider varía como máximo un punto y la verdad estable del
  personaje cambia verificablemente el mundo.

No se exige una geometría universal de exactamente dos valores altos y uno bajo.
Antes de entrar en STORYLINE, `CharactersArtifact.storyline_cast()` elimina
sliders y psicología de craft y conserva solo identidad, objetivos, conflicto,
posición, estado vital y conocimiento inicial.

## 5. Outline y granularidad

Sin una cantidad explícita de capítulos, el outline distribuye el total en
capítulos de 400–900 palabras. Una cantidad solicitada por el usuario prevalece
y permite capítulos desde 200 palabras.

El mínimo de CPN es uno si el capítulo tiene menos de 400 palabras y dos en caso
contrario. El máximo es `min(8, ceil(target_words / 180))`. El 15 % de palabras
se reserva para CBN, otro 15 % para CEN y el 70 % se reparte entre CPN.

## 6. Anclas y estado factual

Cada capítulo tiene un CBN y un CEN distintos, expresados como SVO con IDs
canónicos, localización y mutaciones tipadas. El CEN también declara sus
precondiciones. CBN, CPN y CEN no pueden repetir el mismo SVO.

`NarrativeEntityGraph` mantiene:

- ubicación y estado vital de personajes;
- ubicación o propietario de objetos;
- conocimiento adquirido;
- situación y relaciones vigentes;
- relaciones SVO producidas por eventos aceptados.

El snapshot relevante incluye estado además de relaciones. El escritor recibe
el snapshot anterior al capítulo; los efectos del capítulo todavía no están
aplicados y deben dramatizarse en orden.

## 7. Proponer y revisar CPN

`IncrementalPlotPlanner` pide un candidato con dependencias explícitas hacia uno
o más nodos aceptados. El prompt incluye mundo, elenco factual, estado NEKG,
relaciones pertinentes, eventos recientes, anclas y paleta taxonómica factual.
No contiene PPP, sliders ni try-fail.

Antes de la revisión LLM, `DependencyValidator` rechaza determinísticamente:

- localizaciones o entidades inexistentes;
- personajes muertos o ausentes;
- objetos ausentes o en manos de un tercero;
- conocimiento no adquirido;
- dependencias desconocidas;
- precondiciones falsas;
- teletransportes fuera del mapa;
- efectos incompatibles sobre el mismo atributo.

`DramaticReviewer` evalúa intención, conflicto, causalidad, continuidad, novedad,
emoción y avance hacia CEN con el mismo mundo y estado. Si propone un reemplazo,
ese reemplazo repite todas las validaciones deterministas y taxonómicas. Un
candidato rechazado nunca modifica STORYLINE o NEKG.

El planificador no puede terminar antes del mínimo de CPN aunque un candidato
diga estar alineado con CEN. El último slot permitido debe dejar CEN como
consecuencia inmediata.

## 8. STORYLINE como DAG congelado

`StorylineState` comprueba que todas las dependencias apunten al pasado, que las
aristas representen exactamente esas dependencias y que el grafo sea acíclico.
El orden final se obtiene mediante ordenamiento topológico, no copiando una
cadena lineal artificial.

Después de persistir `storyline.json`, `nekg.json` y `node_reviews.json`, la etapa
`storyline_frozen` cierra el carril factual. Ningún fallo posterior abre esta
etapa de nuevo.

## 9. PromiseLedger global

Sobre la STORYLINE congelada se crea un ledger con contrato tonal y exactamente
una promesa de cada clase: dirección de historia, personaje/conflicto y
estructura de género. Cada promesa declara expectativa, pregunta dramática,
criterios, apertura, progresos y un payoff único.

Un progreso debe mostrar un cambio perceptible, elegir `advance`, `complicate` o
`reframe`, introducir costo o información y anticipar un efecto en el lector. El
payoff declara respuesta, costo, preparación reutilizada y el modo de sorprender
sin incumplir. La promesa principal termina en el último capítulo y, desde 1200
palabras, tiene al menos dos progresos.

No hay un PPP completo obligatorio en cada capítulo. `ChapterCraftView` lista
solo las promesas abiertas, progresadas o pagadas allí; alguna fase puede quedar
vacía, pero cada capítulo debe actuar sobre una promesa vigente.

## 10. Arcos y try-fail

Para cada protagonista se planifican cuatro evidencias sobre nodos aceptados:
establecimiento, presión, elección decisiva y consecuencia. El validador exige
que correspondan al tipo de arco, que el defecto produzca su costo y que la
elección enfrente want y need. El desenlace interno enlaza una promesa externa.

Los ciclos try-fail también se crean después de STORYLINE. Cada uno usa
`yes_but` o `no_and`, enseña algo y eleva o transforma el costo. Un sí o no simple
solo aparece como `final_resolution` asociado a CEN.

`SceneCraftDirective` separa el nivel de escena: goal, conflict, resultado,
consecuencia, reacción, dilema y decisión. No se mezcla con PPP ni con CPN.

## 11. CraftAlignment: la única frontera

`CraftAlignment` enlaza cada apertura, progreso, payoff, evidencia de arco y
ciclo try-fail con nodos aceptados de su capítulo. El validador exige cobertura
exacta y prohíbe nodos inexistentes o enlaces entre capítulos. Si no es posible
alinear una decisión, se regenera solamente el artefacto de craft implicado.

## 12. Briefs sanitizados y escritura

El compositor entrega por capítulo:

- eventos aceptados sin taxonomías internas;
- estado del mundo anterior al capítulo;
- cambios que deben ocurrir en escena;
- acciones de promesas pertinentes;
- directivas de escena;
- conductas de arco;
- tarjetas conductuales con voz, percepción, regla y presión del defecto.

No expone IDs internos al lector, números o nombres de sliders, CBN/CPN/CEN ni
payoffs futuros que el capítulo no necesita conocer.

## 13. Auditoría y reparación selectiva

El crítico revisa constraints, idioma, coherencia del estado y motivaciones,
progreso visible, preparación y cumplimiento de promesas, arcos y costos
try-fail. Cada fallo localizable incluye IDs de capítulos afectados.

`ChapterRewriterAgent` reescribe solo esos cuerpos y conserva encabezados,
hechos, orden causal y resultados correctos. Tras seleccionar la mejor versión,
el sistema vuelve a parsear sus encabezados y calcula las longitudes por capítulo
y global. `craft_audit.json` es la única auditoría; el duplicado
`diagnostic_audit.json` ya no existe.

La calidad narrativa se valida humanamente con las seis métricas existentes. No
se declara una mejora sin comparar lectores sobre un conjunto fijo de prompts.

## 14. Persistencia, fallos y recuperación

Todos los artefactos se escriben de forma atómica. `pipeline_manifest.json`
registra hashes SHA-256 y etapas completas. `checkpoints/` conserva STORYLINE,
NEKG y revisiones después de cada respuesta incremental. `llm_calls.jsonl`
registra llamadas exitosas y fallidas, intento, tokens y espera.

Top-Down 4.0 no migra artefactos incompletos 3.x. Los runs terminados continúan
siendo legibles y comparables mediante `story.md`. La recuperación automática de
Telegram está fuera de esta iteración: un trabajo interrumpido se marca
`recovery_pending`, conserva checkpoints y no impide procesar el resto de la
cola. El TODO exige reconstruir STORYLINE/NEKG, continuar la primera llamada
pendiente y entregar al usuario original antes de activar recuperación real.

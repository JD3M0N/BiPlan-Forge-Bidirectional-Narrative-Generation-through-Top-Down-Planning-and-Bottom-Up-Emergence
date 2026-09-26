# Marco teórico: por qué mezclar Top-Down y Bottom-Up

Este documento reúne el argumento que sostiene la tesis y las fuentes en las que se apoya. No
describe el código: la función simulada está en [simulacion_escenica.md](simulacion_escenica.md) y
el guion en [guion_teatral.md](guion_teatral.md). Tampoco repite qué se tomó de cada trabajo al
diseñar la función: eso está en [estado_del_arte_simulacion.md](estado_del_arte_simulacion.md). Lo
que se propone para mejorarla, con su respaldo, está en
[mejoras_simulacion.md](mejoras_simulacion.md).

Todas las referencias se comprobaron el 2026-09-26: la URL existe, y el título, los autores y la
afirmación que se les atribuye coinciden con la fuente. Donde una cifra no se pudo confirmar en la
fuente, no se cita.

---

## 1. La tesis en tres frases

Un plan validado decide **qué** tiene que pasar. Unos personajes que solo saben lo que han
presenciado deciden **cómo** pasa. Un narrador que cura el registro de esa función decide **cómo se
cuenta**.

```text
petición → plan (DAG validado) → guion → función (director + actores) → log → narrador → historia
           ───── Top-Down ─────           ────── Bottom-Up ──────              ─ discurso ─
           qué pasa                        cómo pasa                             cómo se cuenta
           planning/graph.py               stage/engine.py, stage/memory.py      agents/narrator.py
```

De ahí salen tres hipótesis, cada una con su experimento en el `TODO.md`:

| Hipótesis | Qué se compara | Ficha |
|---|---|---|
| H1. Representar el plan antes de narrarlo aporta algo que escribirlo directamente no aporta | formato `simulated` frente a `narrative`, mismo plan | EXP-1 |
| H2. Dar a cada personaje solo lo que presenció produce mejores escenas que darle todo lo público | `--actor-memory own` frente a `shared` | EXP-2 |
| H3. Cada mecanismo de la función se gana su complejidad | versiones sucesivas sobre el mismo plan | EXP-5 |

El formato guion (EXP-3) no entra en este argumento: compara dos maneras de llegar al mismo
contrato Top-Down, no la mezcla de enfoques.

## 2. El problema: la paradoja narrativa

Louchart y Aylett (2003) le pusieron nombre al problema que esta tesis ataca: la **paradoja
narrativa**, el choque entre una estructura narrativa preescrita, sobre todo la trama, y la libertad
de quienes actúan dentro de ella. Cuanto más se impone la trama, más títeres son los personajes;
cuanto más libres son, menos historia sale.

Mateas y Stern (2000) describieron los dos polos. En los sistemas de **historia fuerte** (*strong
story*) la trama se impone desde arriba; en los de **autonomía fuerte** (*strong autonomy*) los
personajes son agentes independientes y la historia tiene que emerger de ellos, con el riesgo de que
no cumpla lo que el autor quería. Su propuesta fue integrar los dos con el **beat** como unidad
estructural y un gestor dramático que, de vez en cuando, impone metas nuevas a personajes que por lo
demás son autónomos.

Riedl y Young (2010) lo formularon como un conflicto entre **coherencia de trama** y **credibilidad
del personaje**: un plan causalmente correcto en el que los personajes actúan sin motivo propio no
se lee como historia. Riedl y Bulitko (2013), en su repaso de veinte años de narrativa interactiva,
ordenan los sistemas en tres ejes: intención autoral, autonomía de los personajes virtuales y
modelado del jugador.

Stagecraft no tiene jugador, así que la paradoja queda en estado puro: trama contra personaje. La
respuesta de la tesis es repartir el trabajo:

- **Historia fuerte para el qué.** El plan es un grafo validado por `planning/graph.py` que nadie
  puede saltarse.
- **Autonomía fuerte para el cómo.** Los actores solo ven sus circunstancias, su objetivo, la nota
  del director y su propia memoria. Nunca el plan.
- **El director es la bisagra.** Conoce el plan, no puede dictar réplicas, y solo puede empujar con
  un motivo o con algo visible que haga el mundo.

## 3. Por qué ninguno de los dos extremos basta

### La simulación sola no hace historia

- **La lección fundacional.** TALE-SPIN (Meehan 1977): personajes que persiguen sus metas producen
  trazas de resolución de problemas, no historias (ver
  [estado_del_arte_simulacion.md](estado_del_arte_simulacion.md)).
- **La curación es un problema abierto.** Ryan (2018) sostiene que el material bruto de una
  simulación casi nunca tiene estructura de historia. Ryan, Mateas y Wardrip-Fruin (2015) cuentan el
  reconocimiento de historias (*story recognition*) entre los cuatro retos de diseño abiertos de la
  narrativa emergente, junto al contenido modular, la representación composicional y el soporte de
  historias.
- **El propio corpus lo confirma.** El enfoque Bottom-Up retirado en 7.1.1 dejó en
  `Stories/Bottom-Up/` seis runs de una sala de escape simulada. Son registros de acciones en bruto
  («A compartió sus descubrimientos con B.»), sin versión ni estructura dramática: la lección de
  TALE-SPIN, repetida con agentes deterministas.
- **Con LLM, el modelo es el prudente.** ANIMASK (Zhang et al. 2026) vuelve a representar 40
  historias de libros y guiones con 6 modelos actores, en 3.846 puntos de decisión. En tres
  decisiones de cada cuatro, lo que el modelo haría por defecto ya cae dentro de lo que el personaje
  aceptaría. Cuando divergen, el modelo es el cauto: se contiene donde el personaje presionaría. Y
  las repeticiones derivan hacia historias más planas y frías, que dejan sus tensiones abiertas.
- **Riqueza a cambio de consistencia.** WSE-bench (Chen et al. 2026) cruza arquitecturas de agentes
  en simulaciones de mundo abierto. Entre los modelos punteros, un agente por personaje sube la
  riqueza 14,6 puntos y baja la consistencia observada 2,7 frente a un narrador único.
- **Los agentes no sostienen compromisos.** NCP-Bench (Ma et al., ICML 2026) mide si un agente
  mantiene los compromisos de una historia (trayectoria, hechos iniciales, logros) ante
  intervenciones libres, en 100 entornos sacados de sinopsis de películas:
  - el mejor modelo sobrevive el 42 % de las veces tras 20 turnos;
  - los conflictos de hechos van del 40 al 68 % según el modelo;
  - la calidad lingüística no predice la preservación de compromisos.

### La planificación sola, con un LLM que escribe, tampoco

- **Historias sin tensión.** Tian et al. (EMNLP 2024): las historias humanas son tensas,
  activantes y diversas en estructura; las de LLM, homogéneamente positivas y sin tensión. Integrar
  rasgos de discurso (arcos, giros) mejora diversidad, suspense y activación más de un 40 %.
- **Poca creatividad medible.** Chakrabarty et al. (CHI 2024) proponen el TTCW, 14 pruebas binarias
  de escritura creativa: las historias de LLM pasan entre 3 y 10 veces menos pruebas que las de
  escritores profesionales.
- **El contrapunto.** Harel-Canada et al. (EMNLP 2024) miden profundidad psicológica (empatía,
  emoción, autenticidad, compromiso y complejidad narrativa), y las historias de GPT-4 igualan o
  superan a relatos humanos bien valorados de Reddit. La brecha no está en la fluidez ni en la
  emoción superficial, sino en la estructura: tensión, giros y pagos.
- **Evidencia interna.** En el corpus Top-Down el crítico aprueba 695 de 696 comprobaciones (TD-1).
  En la corrida de control la revelación descansa en pruebas que aparecen por primera vez en el
  último capítulo, y el caso se cierra con tres confesiones seguidas (TD-4). Planificar no garantiza
  que el plan se juegue con intención.

### Conclusión

Hace falta estructura desde arriba, intencionalidad desde abajo y un paso de curación entre la
función y el texto. Es la arquitectura de Stagecraft, y es la que la narrativa interactiva fue
construyendo durante veinte años antes de los LLM.

## 4. La tradición híbrida (1997–2014)

Ninguna pieza de Stagecraft es nueva por separado. Lo que es nuevo es el conjunto con actores LLM,
que traen la intencionalidad sin programarla y, con ella, sus sesgos por defecto.

| Sistema | Arriba (trama) | Abajo (personajes) | Mediación | En Stagecraft |
|---|---|---|---|---|
| Façade (Mateas y Stern 2003) | un gestor dramático secuencia beats | personajes con conducta autónoma | el beat une trama y personaje | un beat es un evento del plan; la escalera del director |
| Mediación narrativa, Mimesis (Riedl, Saretto y Young 2003) | un plan narrativo | agentes y usuario | ante una desviación, **acomodar** (replanificar) o **intervenir** | el `stage_event`: el mundo interviene, visible y dentro del log |
| Thespian (Si, Marsella y Pynadath 2005) | guiones de partida | un agente autónomo por personaje | *fitting*: ajusta las metas de cada agente hasta que reproduce su papel del guion | el casting deriva dossier y objetivos del guion, que el actor nunca ve |
| Virtual Storyteller (Theune et al. 2003; Swartjes y Theune 2006, 2008) | un agente director que elige sucesos y cambia metas | agentes personaje con conocimiento propio | la fábula como red causal; *late commitment* | director, actores con memoria propia y un narrador que lee el log |
| Cai, Miao, Tan y Shen (2007) | un agente guionista | actores virtuales | un agente director | Dramaturgo (guion), director de escena y actores |
| Cavazza, Charles y Mead (2002) | una línea argumental base | personajes que planifican con HTN | la interacción entre personajes instancia la trama | el polo *character-based* del que parte la mitad Bottom-Up |

Tres trabajos más completan el mapa:

- **Roberts e Isbell (2008)** revisaron los gestores dramáticos de esa década. Los definen como
  coordinadores que siguen el progreso narrativo y dirigen los papeles o las respuestas de objetos y
  agentes hacia una meta: es la definición exacta del director de escena.
- **Si et al. (AAMAS 2010)** evaluaron empíricamente el control directorial en un marco centrado en
  personajes.
- **MEXICA (Pérez y Pérez y Sharples 2001)** representa la historia como vínculos emocionales y
  tensiones entre personajes que cada acción modifica, y usa esa tensión para juzgar si la historia
  en curso interesa. Es el antecedente de consolidar la postura de cada personaje hacia los demás en
  `CharacterState` en vez de acumularla.

## 5. La formulación formal: intención y creencia

La planificación narrativa llegó a una formulación precisa de lo que Stagecraft hace con LLM:

- **IPOCL** (Riedl y Young 2010): cada acción del plan tiene que pertenecer a una intención de su
  personaje, no solo cuadrar causalmente.
- **CPOCL** (Ware y Young 2011) modela el **conflicto**. En vez de eliminar los vínculos causales
  amenazados, marca pasos como no ejecutados para conservar los subplanes enfrentados de todos los
  personajes sin romper la solidez causal. El conflicto es estructura, no tono.
- **Glaive** (Ware y Young 2014): un planificador que cumple las metas del autor con pasos
  claramente motivados por las metas de cada personaje, y razona sobre cooperación y conflicto con
  mundos posibles.
- **Shirvani, Farrell y Ware (2018)**: en dos estudios con personas, los planes que más sentido
  tienen son los de la intersección entre intención y creencia; y un personaje que anticipa lo que
  harán los demás resulta creíble.
- **Sabre** (Ware y Siler 2021): el planificador es un decisor centralizado y omnisciente con una
  meta de autor, pero cada acción de un agente tiene que tener sentido según **sus** intenciones y
  **sus** creencias, limitadas y quizá falsas, con teoría de la mente de cualquier profundidad.

Leído con esa lente, Stagecraft es un Sabre con LLM:

- **La meta de autor la custodian dos piezas.** El plan validado (`planning/graph.py`) y el
  director, que solo da un beat por alcanzado cuando cada cláusula cita un turno que la prueba.
- **La coherencia con las creencias no la comprueba un planificador: la garantiza la construcción de
  la memoria.** Un actor solo puede actuar desde lo que presenció, porque no tiene otra cosa.

El precio es que una acción puede no llegar: el actor no hace lo que el plan necesitaba, y para eso
existe la escalera del director. La ganancia es que una acción nunca se apoya en algo que el
personaje no podía saber, que es lo que Shirvani et al. muestran que el lector percibe como creíble.

## 6. La versión con LLM (2023–2026)

- **Dramatron** (Mirowski et al., CHI 2023): generación jerárquica por encadenamiento de prompts
  (título, personajes, beats, lugares, diálogo), evaluada con 15 profesionales de teatro y cine. La
  mitad Top-Down de Stagecraft es de esta familia.
- **StoryVerse** (Wang, Zhou y Ledo, FDG 2024): los «actos abstractos» median entre la intención del
  autor y la conducta emergente de personajes LLM. El autor escribe esquemas de alto nivel y un
  planificador LLM los convierte en secuencias concretas de acciones según el estado del mundo. Es
  el precedente más cercano en intención, pero no acota el conocimiento de cada personaje.
- **IBSEN** (Han et al., ACL 2024): director y actores con objetivos de trama. Ver
  [estado_del_arte_simulacion.md](estado_del_arte_simulacion.md).
- **Yu, Shi, Zhao y Penn (In2Writing 2025)**: representar el plan y reescribir desde lo representado
  gana a Agents' Room y a Dramatron en las cinco dimensiones de su evaluación. Es el respaldo
  empírico más directo de H1.
- **Sociedades que se narran después.** BookWorld (ACL 2025), StoryBox (AAAI 2026, que acuña
  «hybrid bottom-up»), Open-Theatre (EMNLP 2025, demo) y EvoSpark (2026).
- **AdaMARP** (Xu et al., Findings ACL 2026): un gestor de escena con acciones discretas y
  justificadas (`init_scene`, `pick_speaker`, `switch_scene`, `add_role`, `end`). Sus mensajes
  entrelazan pensamiento, acción, entorno y habla: los mismos canales que CoSER y que Stagecraft.
- **Concordia** (Vezhnevets et al. 2023): un Game Master, tomado de los juegos de rol de mesa, simula
  el entorno y resuelve las acciones de los agentes. Su evolución (Vezhnevets et al. 2025) distingue
  tres usos del Game Master: simulacionista, **dramatista** y evaluador. El director de Stagecraft
  es un Game Master dramatista: no le importa la plausibilidad física, sino que el beat llegue.
- **The Drama Machine** (Magee et al. 2024): un agente ego y otro superego por personaje, más un
  director, probados en una entrevista y en una historia de detectives.
- **El marco conceptual** (Shanahan, McDonell y Reynolds, Nature 2023): un LLM sostiene una
  superposición de simulacros compatibles con su contexto. Lo que hay en el contexto decide qué
  personaje se interpreta, y es el mejor argumento para darle al actor su memoria y nada más.

**El hueco.** Ninguno de estos sistemas construye la memoria de cada personaje solo con lo que
presenció **y** lo mide con una ablación dentro de un drama director-actor:

- ReverieMem (2026) acota la memoria por perspectiva, pero declara que no aporta un mecanismo para
  orquestar la interacción entre varios personajes.
- WSE-bench compara topologías de decisión, no la propiedad de la memoria.
- StoryVerse e IBSEN no miden fronteras de conocimiento.

Esa es la aportación que tiene que demostrar EXP-2.

## 7. Memoria propia: por qué solo lo percibido

La investigación sobre teoría de la mente (ToM) en LLM converge en tres resultados que justifican
la decisión central de la tesis.

**1. Los modelos no sostienen solos la asimetría de información.**

- FANToM (Kim et al., EMNLP 2023) prueba la ToM en conversaciones con asimetría de información, con
  personajes que entran y salen. Los modelos quedan muy por debajo de las personas, incluso con
  cadena de pensamiento o ajuste fino.
- En SOTOPIA-ToM (2026), con escenarios de 3 a 5 agentes, incluso GPT-5 se queda en el 62 % de
  gestión de la información.
- SimpleToM (Gu et al., ICLR 2026): los modelos infieren bien un estado mental cuando se les
  pregunta, pero fallan al aplicarlo para predecir o juzgar una conducta.

**2. Pedir que no sepa no funciona; no darle el dato, sí.**

- CHARM (2026): la alucinación de personaje es sobre todo un **fallo de obediencia**. El modelo
  reconoce que la pregunta excede a su personaje y responde igual.
- TimeChara (Ahn et al., Findings ACL 2024) encuentra alucinaciones significativas en modelos punteros
  cuando el personaje debe ignorar lo que en su historia aún no ha pasado.

**3. Filtrar lo que el personaje sabe mejora el razonamiento sobre él.**

- SimToM (Wilf et al., ACL 2024): filtrar el contexto a lo que el personaje conoce, antes de
  responder, mejora sustancialmente la ToM, sin entrenar nada.
- SymbolicToM (Sclar et al., ACL 2023): un grafo explícito de creencias por personaje mejora
  drásticamente la ToM de modelos sin ajustar.
- PercepToM (Jung et al., EMNLP 2024): los modelos aciertan **quién percibió qué**, pero fallan al
  pasar de la percepción a la creencia, por falta de control inhibitorio. Suplir ese paso mejora sobre
  todo con creencias falsas.
- ReverieMem (2026): la memoria acotada por perspectiva sube la fidelidad de frontera de conocimiento
  del 38,7 % de BookWorld al 73,3 %, y la negativa ante lo que el personaje no sabe, del 35,5 % al
  81,2 %.
- SOTOPIA-ToM: las intervenciones de ToM reducen las violaciones de privacidad.
- Rahmati y Zhao (2026): en un juego de detectives, un árbol de conocimiento con verificación de cada
  respuesta evita por completo las revelaciones prematuras y reduce un 64,78 % las alucinaciones
  críticas.

Stagecraft lleva esos resultados a su conclusión:

- **La percepción se calcula de forma determinista.** `stage/perception.py` fija quién percibe un
  turno público, un susurro o un pensamiento.
- **La creencia es lo que quedó escrito.** Cada personaje tiene su flujo en `stage/memory.py`, y no
  hay un almacén común del que filtrar.
- **La ablación es el brazo de control.** `--actor-memory shared` es lo que ninguno de esos trabajos
  tenía dentro de un drama.

Es SimToM y PercepToM por construcción.

**Una advertencia medida.** En 7.1.1 la recuperación de `stage/memory.py` todavía no aplica su
tope, y cada actor lee toda su memoria anterior: entre 52 y 72 recuerdos por turno como máximo en
las cinco funciones representadas (SIM-9). La frontera de conocimiento se mantiene, porque lo que un personaje
no presenció sigue sin estar. Lo que no se cumple es que solo viajen los recuerdos más relevantes.

## 8. Curar el log: el narrador como discurso

- **Historia y discurso.** Genette (1972) separa lo que pasa de cómo se cuenta: orden, duración,
  frecuencia, modo (la focalización) y voz. Llama *paralipsis* a callar algo que el foco sabe, un
  recurso legítimo del discurso. Curveship (Montfort) convirtió esos parámetros en código; ver
  [estado_del_arte_simulacion.md](estado_del_arte_simulacion.md).
- **Fibras.** Gervás (2014) narra una partida de ajedrez como historia de muchos personajes. Una
  **fibra** es la vista restringida de la fábula que percibe un personaje focal, y componer el
  discurso es partir la fábula en fibras y empalmar las elegidas en una sola línea. En Stagecraft las
  fibras existen antes de narrar: el conjunto de testigos de cada turno es una fibra, y
  `stage/voices.py` hace el reparto.
- **Cribado.** Ryan (2018) y Felt (Kreminski, Dickinson y Wardrip-Fruin 2019) formulan el
  *story sifting*: consultas sobre la simulación que reconocen patrones con valor de historia. Los
  turnos que el director cita como prueba de un beat, marcados `[clave]`, son un cribado hecho
  durante la función.
- **El orden produce el efecto.** Según Brewer y Lichtenstein (1982):
  - el suspense nace de aplazar el desenlace de algo que ya se ha planteado;
  - la curiosidad, de mostrar un resultado y callar lo que lo causó;
  - la sorpresa, de revelar tarde algo que no se esperaba.

  Todorov (1966) observa que el whodunit tiene dos historias: la del crimen, que acaba antes de que
  empiece la investigación, y la de la investigación, que cuenta cómo se descubre la primera. En
  Stagecraft la historia del crimen vive en las compuertas (`known_by`), la investigación es la
  función, y el narrador decide el orden.
- **Juego limpio.**
  - Van Dine (1928): el lector debe tener la misma oportunidad que el detective de resolver el caso.
  - Knox (1929), primera regla: el criminal no puede ser nadie cuyos pensamientos conozca el lector.
  - Wagner, Keydar y Abend (2025) formalizan el juego limpio con LLM como lectores simulados. Para un
    mismo lector, sorpresa y coherencia se compensan. Los modelos logran una u otra, pero el juego
    limpio les cuesta incluso a los fuertes. Sus métricas puntúan a Christie por encima de Conan
    Doyle en sorpresa y juego limpio.

  Consecuencia: la voz del narrador tiene que respetar el género (SIM-13 del `TODO.md`).

## 9. Qué afirma la tesis y cómo se mide

| Afirmación | Respaldo | Cómo se mide aquí | Ficha |
|---|---|---|---|
| El plan validado sostiene compromisos que los agentes solos pierden | Sabre, NCP-Bench, Façade | rechazos de plan, `beats_forced`, auditoría de fidelidad de la narración | EXP-1, SIM-1 |
| La función aporta riqueza e intención que la escritura directa no tiene | Yu et al. 2025, WSE-bench, StoryBox, Tian et al. 2024 | comparación a ciegas, `report-story-craft`, `script_echo` bajo (no recitan) | EXP-1 |
| La memoria propia protege la frontera de conocimiento y crea asimetrías que se pueden jugar | SimToM, PercepToM, SymbolicToM, ReverieMem, CHARM | `unknown_mentions`, auditoría con juez calibrado, susurros y mentiras (MED-7) | EXP-2 |
| El narrador cura: selecciona, comprime y ordena | Ryan 2018, Gervás 2014, Genette | `compression_ratio` < 1, `dialogue_survival` lejos de 1, fidelidad sin inventos | SIM-5 |
| Cada mecanismo se gana su complejidad | WSE-bench | versiones sobre el mismo plan con las cifras de MED-7 | EXP-5 |

La frase de WSE-bench sirve de criterio para toda la función: los componentes deben ganarse su
complejidad aportando información, coordinación o control que la generación pueda usar de verdad.

### Amenazas a la validez

- **Los jueces LLM no son medida.** Las tres razones las da la literatura, no la prudencia del
  protocolo del `TODO.md`:
  - Un juez prefiere sus propias generaciones (Panickssery, Bowman y Feng, NeurIPS 2024), y aquí
    Gemini juzga texto de Gemini: el crítico, la auditoría de promesas y la de la función.
  - Los jueces pequeños sin ajustar no evalúan bien escritura creativa. En LitBench (2025) el mejor
    juez sin ajuste acierta el 73 % de las preferencias humanas, y los modelos entrenados, el 78 %.
  - Los jueces al uso puntúan historias de LLM por encima de relatos del *New Yorker*. Una métrica de
    tensión por predicción de finales invierte ese orden (Sui et al. 2026).
- **Ruido.** Dos corridas del mismo prompt y la misma versión difirieron hasta 16 puntos en la
  réplica de 6.6.0.
- **n pequeño y cuota diaria.** Una matriz simulada de 9 runs no cabe en un día gratuito.
- **La evaluación humana decide** (EXP-4). Las seis métricas de
  [packages/evaluation/README.md](../packages/evaluation/README.md) se solapan con los seis criterios
  de HANNA (Chhun et al., COLING 2022: relevancia, coherencia, empatía, sorpresa, compromiso y
  complejidad):
  - relevancia, coherencia y compromiso coinciden;
  - la creatividad cubre sorpresa y complejidad;
  - el ritmo y la satisfacción son propios, más cerca del contrato de promesas;
  - falta la empatía.

  Como referencia de fiabilidad, Harel-Canada et al. (2024) obtuvieron un α de Krippendorff de 0,72
  con evaluadores formados.

---

## 10. Referencias

### Paradoja narrativa y tradición híbrida

- Louchart, S. y Aylett, R. (2003). *Solving the Narrative Paradox in VEs – Lessons from RPGs*. IVA
  2003. <https://link.springer.com/chapter/10.1007/978-3-540-39396-2_41>
- Mateas, M. y Stern, A. (2000). *Towards Integrating Plot and Character for Interactive Drama*.
  AAAI Fall Symposium. <https://users.soe.ucsc.edu/~michaelm/publications/mateas-aaai-symp-sia-2000.pdf>
- Mateas, M. y Stern, A. (2003). *Integrating Plot, Character and Natural Language Processing in the
  Interactive Drama Façade*. TIDSE 2003.
  <https://users.soe.ucsc.edu/~michaelm/publications/mateas-tidse2003.pdf>
- Cavazza, M., Charles, F. y Mead, S. J. (2002). *Character-Based Interactive Storytelling*. IEEE
  Intelligent Systems 17(4). <https://dl.acm.org/doi/abs/10.1109/MIS.2002.1024747>
- Riedl, M. O., Saretto, C. J. y Young, R. M. (2003). *Managing Interaction Between Users and Agents in
  a Multi-Agent Storytelling Environment*. AAMAS 2003.
  <https://faculty.cc.gatech.edu/~riedl/pubs/riedl-young-aamas03.pdf>
- Si, M., Marsella, S. C. y Pynadath, D. V. (2005). *Thespian: Using Multi-Agent Fitting to Craft
  Interactive Drama*. AAMAS 2005.
  <https://www.researchgate.net/publication/221456512_Thespian_using_multi-agent_fitting_to_craft_interactive_drama>
- Si, M., Marsella, S. C. y Pynadath, D. V. (2010). *Evaluating Directorial Control in a
  Character-Centric Interactive Narrative Framework*. AAMAS 2010.
  <https://ict.usc.edu/pubs/Evaluating%20Directorial%20Control%20in%20a%20Character-Centric%20Interactive%20Narrative%20Framework.pdf>
- Theune, M., Faas, S., Nijholt, A. y Heylen, D. (2003). *The Virtual Storyteller: Story Creation by
  Intelligent Agents*. TIDSE 2003.
  <https://theune.personalweb.utwente.nl/PUBS/VirtualStoryteller_TIDSE2003.pdf>
- Swartjes, I. y Theune, M. (2006). *A Fabula Model for Emergent Narrative*. TIDSE 2006.
  <https://link.springer.com/chapter/10.1007/11944577_5>
- Swartjes, I. y Theune, M. (2008). *The Virtual Storyteller: Story Generation by Simulation*. BNAIC
  2008. <https://research.utwente.nl/en/publications/the-virtual-storyteller-story-generation-by-simulation/>
- Cai, Y., Miao, C., Tan, A.-H. y Shen, Z. (2007). *A Hybrid of Plot-Based and Character-Based
  Interactive Storytelling*. Edutainment 2007.
  <https://link.springer.com/chapter/10.1007/978-3-540-73011-8_27>
- Roberts, D. L. e Isbell, C. L. (2008). *A Survey and Qualitative Analysis of Recent Advances in
  Drama Management*. ITSSA 4(2). <https://faculty.cc.gatech.edu/~isbell/papers/itssa08-survey.pdf>
- Riedl, M. O. y Bulitko, V. (2013). *Interactive Narrative: An Intelligent Systems Approach*. AI
  Magazine 34(1). <https://ojs.aaai.org/aimagazine/index.php/aimagazine/article/view/2449>
- Pérez y Pérez, R. y Sharples, M. (2001). *MEXICA: A Computer Model of a Cognitive Account of
  Creative Writing*. JETAI 13(2). <https://www.tandfonline.com/doi/abs/10.1080/09528130010029820>
- Ryan, J. O., Mateas, M. y Wardrip-Fruin, N. (2015). *Open Design Challenges for Interactive
  Emergent Narrative*. ICIDS 2015. <https://link.springer.com/chapter/10.1007/978-3-319-27036-4_2>

### Planificación con intención y creencia

- Riedl, M. O. y Young, R. M. (2010). *Narrative Planning: Balancing Plot and Character*. JAIR 39.
  <https://arxiv.org/abs/1401.3841>
- Ware, S. G. y Young, R. M. (2011). *CPOCL: A Narrative Planner Supporting Conflict*. AIIDE 2011.
  <https://ojs.aaai.org/index.php/AIIDE/article/view/12428>
- Ware, S. G. y Young, R. M. (2014). *Glaive: A State-Space Narrative Planner Supporting
  Intentionality and Conflict*. AIIDE 2014.
  <https://cdn.aaai.org/ojs/12712/12712-52-16229-1-2-20201228.pdf>
- Shirvani, A., Farrell, R. y Ware, S. G. (2018). *Combining Intentionality and Belief: Revisiting
  Believable Character Plans*. AIIDE 2018. <https://ojs.aaai.org/index.php/AIIDE/article/view/13037>
- Ware, S. G. y Siler, C. (2021). *Sabre: A Narrative Planner Supporting Intention and Deep Theory of
  Mind*. AIIDE 2021. <https://ojs.aaai.org/index.php/AIIDE/article/view/18896>

### Sistemas con LLM y evidencia empírica

- Mirowski, P., Mathewson, K. W., Pittman, J. y Evans, R. (2023). *Co-Writing Screenplays and Theatre
  Scripts with Language Models: Evaluation by Industry Professionals*. CHI 2023.
  <https://arxiv.org/abs/2209.14958>
- Wang, Y., Zhou, Q. y Ledo, D. (2024). *StoryVerse: Towards Co-authoring Dynamic Plot with LLM-based
  Character Simulation via Narrative Planning*. FDG 2024. <https://arxiv.org/abs/2405.13042>
- Yu, T., Shi, K., Zhao, Z. y Penn, G. (2025). *Multi-Agent Based Character Simulation for Story
  Writing*. In2Writing 2025. <https://aclanthology.org/2025.in2writing-1.9/>
- Xu, Z., Chen, D., Wang, S. et al. (2026). *AdaMARP: An Adaptive Multi-Agent Interaction Framework
  for General Immersive Role-Playing*. Findings ACL 2026. <https://arxiv.org/abs/2601.11007>
- Vezhnevets, A. S. et al. (2023). *Generative Agent-Based Modeling with Actions Grounded in Physical,
  Social, or Digital Space using Concordia*. <https://arxiv.org/abs/2312.03664>
- Vezhnevets, A. S. et al. (2025). *Multi-Actor Generative Artificial Intelligence as a Game Engine*.
  <https://arxiv.org/abs/2507.08892>
- Magee, L., Arora, V., Gollings, G. y Lam-Saw, N. (2024). *The Drama Machine: Simulating Character
  Development with LLM Agents*. <https://arxiv.org/abs/2408.01725>
- Shanahan, M., McDonell, K. y Reynolds, L. (2023). *Role Play with Large Language Models*. Nature
  623. <https://www.nature.com/articles/s41586-023-06647-8>
- Zhang, X., Xu, Z., Luo, H. et al. (2026). *ANIMASK: What the Model Contributes to Role Play in
  Simulated Story Worlds*. <https://arxiv.org/abs/2609.16667>
- Chen, Y., Li, S., Cai, Y. et al. (2026). *When Stories Evolve: Benchmarking LLM Storytelling Across
  Agent Architectures in Open-Ended World Simulations*. <https://arxiv.org/abs/2608.15654>
- Ma, Y., Yan, J., Shi, B. et al. (2026). *Can LLM Agents Stick to the Script? A Benchmark for
  Long-Horizon Consistency in Interactive Narratives*. ICML 2026. <https://arxiv.org/abs/2608.08160>
- Tian, Y. et al. (2024). *Are Large Language Models Capable of Generating Human-Level Narratives?*
  EMNLP 2024. <https://aclanthology.org/2024.emnlp-main.978/>
- Chakrabarty, T., Laban, P., Agarwal, D., Muresan, S. y Wu, C.-S. (2024). *Art or Artifice? Large
  Language Models and the False Promise of Creativity*. CHI 2024.
  <https://dl.acm.org/doi/10.1145/3613904.3642731>
- Harel-Canada, F. et al. (2024). *Measuring Psychological Depth in Language Models*. EMNLP 2024.
  <https://arxiv.org/abs/2406.12680>

### Teoría de la mente y memoria por perspectiva

- Kim, H., Sclar, M., Zhou, X. et al. (2023). *FANToM: A Benchmark for Stress-testing Machine Theory
  of Mind in Interactions*. EMNLP 2023. <https://aclanthology.org/2023.emnlp-main.890/>
- Sclar, M., Kumar, S., West, P., Suhr, A., Choi, Y. y Tsvetkov, Y. (2023). *Minding Language Models'
  (Lack of) Theory of Mind: A Plug-and-Play Multi-Character Belief Tracker*. ACL 2023.
  <https://aclanthology.org/2023.acl-long.780/>
- Wilf, A., Lee, S., Liang, P. P. y Morency, L.-P. (2024). *Think Twice: Perspective-Taking Improves
  Large Language Models' Theory-of-Mind Capabilities*. ACL 2024.
  <https://aclanthology.org/2024.acl-long.451/>
- Jung, C., Kim, D., Jin, J. et al. (2024). *Perceptions to Beliefs: Exploring Precursory Inferences
  for Theory of Mind in Large Language Models*. EMNLP 2024.
  <https://aclanthology.org/2024.emnlp-main.1105/>
- Gu, Y., Tafjord, O., Kim, H. et al. (2026). *SimpleToM: Exposing the Gap between Explicit ToM
  Inference and Implicit ToM Application in LLMs*. ICLR 2026. <https://arxiv.org/abs/2410.13648>
- Ahn, J. et al. (2024). *TimeChara: Evaluating Point-in-Time Character Hallucination of Role-Playing
  Large Language Models*. Findings ACL 2024. <https://arxiv.org/abs/2405.18027>
- Han, S., Park, N., Seo, G., Yoon, S. y Bak, J. (2026). *CHARM: Character Hallucination for
  Multicultural Role Play Benchmark*. <https://arxiv.org/abs/2609.01352>
- Tang, X., Zhang, J., Yang, Z. et al. (2026). *Staying In Character: Perspective-Bounded Memory for
  Book-Based Role-Playing Agents* (ReverieMem). <https://arxiv.org/abs/2606.25632>
- Yashwanth YS, Wang, R., Zeng, S. et al. (2026). *SOTOPIA-TOM: Evaluating Privacy and Information
  Management in Multi-Agent Interaction with Theory of Mind*. <https://arxiv.org/abs/2605.02307>
- Rahmati, P. y Zhao, R. (2026). *Enforcing Narrative Reliability and Epistemic Pacing in LLM-Driven
  Detective Games via Structured Knowledge Trees*. <https://arxiv.org/abs/2609.23043>

### Discurso, curación y juego limpio

- Genette, G. (1972). *Discours du récit*. Traducido como *Narrative Discourse* (1980). Libro.
- Gervás, P. (2014). *Composing Narrative Discourse for Stories of Many Characters: A Case Study over
  a Chess Game*. Literary and Linguistic Computing 29(4).
  <https://academic.oup.com/dsh/article/29/4/511/982149>
- Kreminski, M., Dickinson, M. y Wardrip-Fruin, N. (2019). *Felt: A Simple Story Sifter*. ICIDS 2019.
  <https://link.springer.com/chapter/10.1007/978-3-030-33894-7_27>
- Brewer, W. F. y Lichtenstein, E. H. (1982). *Stories Are to Entertain: A Structural-Affect Theory of
  Stories*. Journal of Pragmatics 6.
  <https://www.sciencedirect.com/science/article/abs/pii/0378216682900212>
- Todorov, T. (1966). *Typologie du roman policier*. Recogido como *The Typology of Detective
  Fiction*.
  <https://www.taylorfrancis.com/chapters/edit/10.4324/9780367809195-27/typology-detective-fiction-1966-tzvetan-todorov>
- Van Dine, S. S. (1928). *Twenty Rules for Writing Detective Stories*. The American Magazine.
- Knox, R. (1929). *Decálogo* del prólogo a *The Best Detective Stories of 1928–29*.
- Wagner, E., Keydar, R. y Abend, O. (2025). *The Challenge and Reward of Fair Play in Narrative: A
  Computational Approach*. <https://arxiv.org/abs/2507.13841>

### Evaluación

- Chhun, C., Colombo, P., Suchanek, F. M. y Clavel, C. (2022). *Of Human Criteria and Automatic
  Metrics: A Benchmark of the Evaluation of Story Generation* (HANNA). COLING 2022.
  <https://aclanthology.org/2022.coling-1.509/>
- Panickssery, A., Bowman, S. R. y Feng, S. (2024). *LLM Evaluators Recognize and Favor Their Own
  Generations*. NeurIPS 2024. <https://arxiv.org/abs/2404.13076>
- Fein, D., Russo, S., Xiang, V. et al. (2025). *LitBench: A Benchmark and Dataset for Reliable
  Evaluation of Creative Writing*. <https://arxiv.org/abs/2507.00769>
- Sui, P., Zhu, Y., Cheng, T. et al. (2026). *Spoiler Alert: Narrative Forecasting as a Metric for
  Tension in LLM Storytelling*. <https://arxiv.org/abs/2604.09854>

# Estado del arte: simulación de personajes y narración desde el log

Revisión que sostiene el diseño de [simulacion_escenica.md](simulacion_escenica.md). Cada entrada
dice qué aporta el trabajo y **qué se tomó o se descartó de él**, que es lo que hace útil una
revisión dentro de un repositorio de código.

---

## 1. El antecedente directo: simular y después reescribir

### Yu, Shi, Zhao y Penn — *Multi-Agent Based Character Simulation for Story Writing* (In2Writing 2025)
<https://aclanthology.org/2025.in2writing-1.9/>

Es el trabajo más cercano a este pipeline. Parte de un plan narrativo y lo divide en dos pasos: un
**role-play** donde un Director Agent elige `next_speaker` y `next_command` y los Character Agents
responden actualizando memoria y estado físico, y un **rewrite** donde un LLM escribe la escena
mirando el resultado. Usa la distinción *fabula* / *syuzhet*: el role-play produce la fábula en
orden cronológico, la reescritura la ordena como trama. Gana a Agents' Room y a Dramatron en las
cinco dimensiones de su evaluación.

**Tomado**: la arquitectura de dos pasos, el director que elige quién habla y con qué orden, y la
idea de que la reescritura es un paso propio y no un post-proceso.
**Descartado**: su reordenación fabula→syuzhet. Aquí el orden lo fija el plan validado antes de que
nadie actúe, así que la narración reordena dentro del capítulo pero no entre capítulos.

### Han, Chen, Lin, Xu y Yu — *IBSEN: Director-Actor Agent Collaboration* (ACL 2024)
<https://arxiv.org/abs/2407.01093>

Director que escribe objetivos de trama y **instrucciones, no réplicas**: al actor le llega el
esquema, una sinopsis breve y unas palabras clave, precisamente para que no copie. Tras cada turno
el director pregunta si el objetivo se alcanzó; si no, a los 9 turnos lo da por cumplido a la
fuerza (media real: 5,61 turnos por objetivo, 11 forzados sobre 218). La memoria del actor va en
primera persona («monólogo»), y la recuperación mezcla embeddings, TF-IDF y recencia.

Sus fallos documentados son el mapa de lo que hay que evitar: **repetición** (con un umbral de
distancia de Levenshtein de 0,4 que ellos mismos consideran insuficiente), **sobrenarración** (el
director mete narración donde debería haber diálogo), **suavizado moral** (los actores interpretan
a los villanos con más bondad de la que tienen, por las políticas de seguridad del modelo) y
**fijación con el objetivo**.

**Tomado**: dirigir por motivación, el tope de turnos por beat, la memoria en primera persona.
**Endurecido**: el umbral de repetición sube a 0,75 sobre solapamiento léxico; la regla anti-
suavizado está explícita en la instrucción del actor; el director no puede narrar, solo puede
introducir un `stage_event` que entra al log como un turno más.

---

## 2. Sociedades de agentes que generan historias

### Ran, Wang, Qiu, Liang, Xiao y Yang — *BookWorld* (ACL 2025)
<https://arxiv.org/abs/2504.14538>

Role agents con atributos **estáticos** (género, edad, personalidad) y **dinámicos** (metas,
estados, memorias), más un world agent que responde al entorno y genera eventos. Memoria corta y
larga: la corta guarda los diálogos recientes completos y la larga resúmenes condensados. Escena
como unidad narrativa mínima, citando a McKee. Tiene «script mode» donde un guion de usuario
guía las acciones. Al final convierte el registro en prosa novelística. Gana al baseline con 75,36%.

Su ablación es lo más informativo: quitar el modo escena hunde la calidad en todas las dimensiones,
y quitar la respuesta del entorno hunde la inmersión. Sus limitaciones reconocidas: los personajes
se vuelven indecisos en situaciones complejas, porque la investigación de role-play se ha centrado
en el chat de uno a uno.

**Tomado**: la escena como unidad, los atributos estáticos y dinámicos separados, la conversión
final del registro a prosa.
**Descartado**: el mapa geoespacial con grafo de distancias, que aquí ya lo fija el guion.

### Chen, Pan y Li — *StoryBox* (AAAI 2026)
<https://arxiv.org/abs/2510.11618>

De aquí sale el término «hybrid bottom-up»: un sandbox donde los agentes generan eventos y un
Storyteller Agent los convierte en capítulos, con ventana dinámica y resúmenes previos. Supera los
12.000 palabras. Mide **consistencia de comportamiento del personaje** contra sus atributos.
Reconoce que la simulación secuencial es su cuello de botella.

**Tomado**: el nombre, la narración capítulo a capítulo con lo anterior como contexto y la idea de
medir la consistencia como cifra propia.

### Chen et al. — *When Stories Evolve (WSE-bench)* (2026)
<https://arxiv.org/abs/2608.15654>

El resultado más útil de toda la revisión, porque es el único que compara **arquitecturas** en vez
de sistemas. Cruza tres topologías de decisión (sin agentes de personaje, uno centralizado, uno
por personaje) con memoria de mundo y planificación de mundo, sobre 12 modelos y 6.048
trayectorias. Mide tres cosas por separado: cobertura de generación, consistencia canónica y
riqueza.

Sus números: los agentes de personaje distribuidos suben la riqueza **+14,6** y bajan la
consistencia **−2,7** frente al narrador único. La memoria estructurada de mundo **no** da
beneficio estable de consistencia y reduce la cobertura. La frontera consistencia–riqueza **no es
cóncava**: hay configuraciones que ninguna ponderación lineal elegiría. Su conclusión: *«más
arquitectura no es más control; cada componente debe ganarse su complejidad»*.

**Tomado**: medir cobertura, consistencia y riqueza por separado en vez de una nota agregada; la
decisión de no añadir un modelo de mundo estructurado encima del plan validado, que ya hace ese
trabajo.

### Zong, Guo, Yang, Guo y Song — *EvoSpark* (ACL 2026)
<https://arxiv.org/abs/2604.12776>

Nombra dos patologías de horizonte largo. El **apilamiento de memoria social**: en una arquitectura
que solo añade, las relaciones contradictorias se acumulan y el agente sostiene «amigo» y «enemigo»
a la vez. Su respuesta es consolidar el estado en lugar de acumularlo. Y la **disonancia narrativo-
espacial**, cuando la lógica del espacio se desprende de la trama. Cuesta 63,6 minutos por cada 100
turnos frente a 25,9–41,2 de los baselines.

**Tomado**: la consolidación de relaciones, que aquí hace la reflexión al cerrar cada escena.
**Descartado**: su maquinaria de puesta en escena generativa, innecesaria porque el guion ya fija
ubicación y reparto y `script.py` ya los valida.

---

## 3. Memoria de agentes

### Park, O'Brien, Cai, Morris, Liang y Bernstein — *Generative Agents* (UIST 2023)
<https://arxiv.org/abs/2304.03442>

El flujo de memoria y su recuperación por **recencia** (decaimiento exponencial, factor 0,995 por
hora), **importancia** (1 a 10, asignada por el modelo al escribir) y **relevancia** (similitud de
embeddings). Reflexión cuando la importancia acumulada cruza un umbral (~150). Su ablación muestra
que quitar cualquiera de los tres componentes degrada la credibilidad.

**Tomado**: los tres términos de la puntuación y la reflexión periódica.
**Adaptado**: la recencia va por **escenas**, no por horas, porque la unidad de tiempo aquí es
dramática; la reflexión se dispara al cerrar escena, que es un límite natural, en vez de por umbral
acumulado; y la relevancia es léxica, no por embeddings, para que la recuperación sea determinista
y no dependa de un servicio externo.

### Wu, Wu, Xu, Zhang y Zhao — *Open-Theatre* (EMNLP 2025)
<https://arxiv.org/abs/2509.16713>

Memoria jerárquica con cuatro almacenes (global, eventos, resúmenes, archivo) y una fórmula
explícita: `S_final = P_recencia · (S_relevancia + S_importancia)`, con **penalización entre
escenas** `(1 + α·|escena_actual − escena_del_recuerdo|)^-1`, α = 0,25 por defecto. Al cambiar de
escena consolida los eventos en resúmenes. Introduce el «Director-Global Actor», un actor
centralizado que decide por todos: baja el coste a 2 llamadas por turno y da la mejor coherencia
narrativa (4,6/5).

**Tomado**: el α = 0,25 entre escenas y la consolidación al cerrar escena.
**Descartado**: el actor global centralizado. Es más barato y más coherente, pero un único agente
que decide por todos los personajes **no puede tener fronteras de conocimiento separadas**, que es
justamente lo que esta tesis mide.

### Xu, Liang, Mei, Gao, Tan y Zhang — *A-MEM* (NeurIPS 2025)
<https://arxiv.org/abs/2502.12110>

Memoria agéntica estilo Zettelkasten: cada nota nueva se enlaza con las existentes y puede
reescribirlas.

**Descartado por ahora**: el coste es una llamada por escritura de memoria, y aquí hay una
escritura por testigo y por turno. Queda como idea si la recuperación léxica resulta insuficiente.

---

## 4. Interpretación de personajes y sus fronteras

### *ReverieMem: Perspective-Bounded Memory for Book-Based Role-Playing Agents* (2026)
<https://arxiv.org/abs/2606.25632>

El trabajo que da forma a la aportación central. Nombra dos fallos: **extralimitación factual** (el
agente afirma algo canónicamente cierto pero que su personaje no podía saber) y **monotonía
estilística**. Su memoria tiene tres capas, y la semántica guarda tuplas con un **conjunto de
visibilidad por personaje**: `f = (s, p, o, κ, V)`, donde al hablar como `c` solo se puede
recuperar `F_c = {f : c ∈ V(f)}`. Introduce **KBF** (Knowledge Boundary Fidelity), media armónica
entre acertar lo que el personaje sí sabe y **negarse** ante lo que no. Su resultado: KBF 73,3%
frente al 38,7% de BookWorld, con la negativa subiendo de 35,5% a 81,2%.

Su ablación es tajante: sin la capa episódica la negativa cae a 47,0%; sin la semántica el sistema
colapsa a negarlo casi todo.

**Tomado**: la idea entera de acotar por perspectiva, y la media armónica como forma de medirla.
**Llevado más lejos**: aquí no hay filtrado en lectura. No existe un almacén común del que filtrar:
lo que un personaje no presenció **nunca se escribió** en su flujo. Es la misma garantía, obtenida
por construcción en vez de por consulta.
**Su limitación es nuestra oportunidad**: ReverieMem reconoce que *«no provee un mecanismo dedicado
para orquestar interacciones multi-personaje»*. Este pipeline es exactamente eso.

### Ahn, Kim, Kim et al. — *TimeChara* (Findings ACL 2024)
<https://arxiv.org/abs/2405.18027>

10.895 casos sobre 14 personajes de cuatro sagas. Un personaje debe reflejar su frontera de
conocimiento **en un punto del tiempo**: ni adelantar lo que aún no ha pasado ni olvidar lo que sí.
GPT-4o queda por debajo del 51% en las preguntas sobre el futuro.

**Tomado**: la frontera temporal como cosa que se mide, no que se asume. Aquí es estructural: en la
escena *n* la memoria solo contiene escenas ≤ *n*.

### *CHARM: Character Hallucination for Multicultural Role Play* (2026)
<https://arxiv.org/abs/2609.01352>

Distingue frontera **temporal** de frontera **de universo**, y observa que interpretar bien exige
*suprimir* conocimiento fuera de personaje, no solo recordar el de dentro.

### Wang, Qiu, Yang et al. — *CoSER* (ICML 2025)
<https://arxiv.org/abs/2502.09082>

17.966 personajes de 771 libros. Define **given-circumstance acting**: el LLM interpreta por turnos
a cada personaje de una escena, con un agente de entorno y una predicción de siguiente hablante,
hasta `<END>` o 20 turnos. El mensaje tiene tres canales: **habla**, **acción** y **pensamiento**,
y el pensamiento es lo que crea asimetría de información. Su evaluación es **por penalización**: el
juez busca fallos con gravedad 1–5 y puntúa `100 − 5·Σ`, con corrección por longitud. Confirma que
los pensamientos internos y las motivaciones mejoran la interpretación en tiempo de prueba.

**Tomado**: los tres canales tal cual, el tope de turnos y la puntuación por penalización para la
auditoría.

### Jun, Choi, Park, Park, Geumheon y Lee — *Identifying and Mitigating Bottlenecks in RPA* (2026)
<https://arxiv.org/abs/2601.04716>

Estudio controlado sobre 211 personajes y tres ejes: **familiaridad** (conocido o inventado),
**estructura** (esquema o narrativa libre) y **disposición** (moral o inmoral). El resultado es una
asimetría nítida: familiaridad y estructura **no importan**; la disposición **sí**, mucho y de forma
consistente. Los personajes inmorales pierden entre 5,89 y 9,22 puntos en interacción multi-turno,
con p < 0,001 en todos los modelos. El alineamiento post-SFT amplía la brecha, y la caída es mayor
en los campos de **motivación cargada de valores** que en los rasgos estables de personalidad.

**Tomado**: dos cosas. Que el esquema del dossier importa poco, así que se eligió el que hace el
prompt legible; y que el antagonista es el cuello de botella real, de donde sale la regla explícita
del actor contra el suavizado y la instrucción al director de casting de escribir qué quiere el
antagonista en vez de una etiqueta de cuán malo es.

### *Deep Persona* (2026)
<https://arxiv.org/abs/2609.22255>

Persona en tres capas: externa (conducta observable), media (creencias que afloran con
disparadores) e interna (pulsiones que guían y nunca se verbalizan).

**Tomado**: la estructura de tres capas del dossier, con `behavior_rules` y `triggers` en la capa
condicional.

### Wang et al. (2025a), citado en los dos anteriores

Las **pautas de conducta rinden más que los retratos descriptivos**.

**Tomado**: es la regla de redacción del dossier. «Siempre responde a una pregunta con otra» es
jugable; «es evasivo» no lo es.

### Li, Kenneth et al. — *Measuring and Controlling Persona Drift* (2024)
<https://arxiv.org/abs/2402.10962>

La persona se degrada más de un 30% entre los turnos 8 y 12, por decaimiento de la atención.

**Tomado**: el dossier completo se reinyecta en **cada** llamada del actor, en vez de establecerse
una vez. Es la defensa más barata contra la deriva.

---

## 5. Asimetría de información e inteligencia social

### Zhou, Zhu, Mathur et al. — *SOTOPIA* (ICLR 2024)
<https://arxiv.org/abs/2310.11667>

Evalúa interacción social con siete dimensiones, entre ellas **secreto** y **conocimiento**. Cada
agente recibe una meta social privada.

**Tomado**: la meta privada por escena, que aquí es el `objective` que el guion ya guardaba.

### *SOTOPIA-ToM* (2026)
<https://arxiv.org/abs/2605.02307>

160 escenarios de 3 a 5 agentes con conocimiento privado particionado y canales público y privado.
Incluso GPT-5 llega solo al 62% en gestión de información.

**Tomado**: el canal privado, que aquí es el susurro, y la confirmación de que la asimetría hay que
imponerla estructuralmente porque los modelos no la mantienen solos.

---

## 6. La tradición: por qué simular no basta

### Meehan — *TALE-SPIN* (IJCAI 1977)
<https://mlanthology.org/ijcai/1977/meehan1977ijcai-tale/>

La lección fundacional: si los personajes persiguen sus metas privadas, lo que sale casi nunca es
una historia, sino una traza de resolución de problemas sin estructura global. Todo el trabajo
posterior añadió conocimiento de nivel autor.

**Tomado**: es la razón de que el plan exista y de que el director tenga un beat que alcanzar. La
simulación aporta la intencionalidad; la estructura viene de arriba.

### Ryan — *Curating Simulated Storyworlds* (UCSC, 2018)
<https://escholarship.org/uc/item/1340j5h2>

Formula el **curacionismo**: simulación → cribado (*story sifting*) → narrativización. El material
bruto «casi siempre carecerá de estructura de historia», y la curación es lo que lo convierte en
artefacto. Propone encadenar hacia atrás desde el suceso más notable y catalogar los fallos
típicos: granularidad mal ajustada, falta de modularidad, causalidad difusa.

**Tomado**: que el narrador **selecciona y comprime**, que no transcribe. La contabilidad causal que
Ryan pide aquí ya la da el DAG del plan.

### Montfort — *Curveship* (2009–2011)
<https://nickm.com/if/Montfort__CALC-09.pdf>

Separa el **Simulator** del **Teller**: el mundo produce representaciones de acciones y el narrador
decide qué contar y cómo, con orden, frecuencia, velocidad y **focalización** como parámetros, según
Genette.

**Tomado**: la separación entera, y que la focalización sea un **parámetro** y no una reescritura
del prompt. `stage/voices.py` es el Teller.

### Riedl y Young — *Narrative Planning: Balancing Plot and Character* (JAIR 2010)
<https://arxiv.org/abs/1401.3841>

IPOCL: planifica razonando sobre la **intencionalidad** del personaje, no solo sobre la causalidad,
porque un plan causalmente correcto en el que los personajes actúan sin motivo no se lee como
historia.

**Tomado**: es la formulación exacta de por qué este pipeline es híbrido. `graph.py` da la
causalidad; los actores dan la intencionalidad.

### Riedl — *Automated Story Director* y «failing believably»
<https://faculty.cc.gatech.edu/~riedl/pubs/tidse06b.pdf>

Ante una desviación, o se **interviene** (se cambia algo del mundo) o se **acomoda** (se replanifica
). Y cuando el drama y la credibilidad chocan, el personaje debe fallar de forma creíble.

**Tomado**: el `stage_event` es una intervención de manual, y es visible en escena precisamente para
que la desviación se explique dentro de la ficción.

### Evans y Short — *Versu* (2013) · Swartjes y Theune — *Late Commitment* (IVA 2008)
<https://www.semanticscholar.org/paper/74c6364ae004ce58e3f15a20c1e6d22198a93e21> ·
<https://dl.acm.org/doi/10.1007/978-3-540-85483-8_80>

En Versu las prácticas sociales **nunca controlan** al agente: ofrecen posibilidades, y el agente
decide. El *late commitment* del teatro de improvisación retrasa las decisiones sobre el mundo hasta
que son útiles.

**Tomado**: la nota del director sugiere y el actor decide. Es la diferencia entre un títere y un
intérprete.

### Aylett y Louchart — *Double Appraisal* (2008)
<https://www.semanticscholar.org/paper/2124e6bb85dab3635b29eae3b31e0f041ba83d2e>

El personaje evalúa dos veces: cómo le afecta a él y qué impacto dramático tendría.

**Descartado**: duplicaría las llamadas. El director cumple esa función desde fuera, que es más
barato y mantiene al actor dentro del personaje.

### Mateas y Stern — *Façade* (2003)
<https://users.soe.ucsc.edu/~michaelm/publications/mateas-gdc2003.pdf>

Beats como unidad dramática mínima, secuenciados por un drama manager.

**Tomado**: el beat como unidad. Aquí un beat es un evento del plan, así que la unidad dramática y
la unidad causal coinciden y son auditables la una contra la otra.

---

## 7. Medición

### *ConStory-Bench: Lost in Stories* (Findings ACL 2026)
<https://arxiv.org/abs/2603.05890>

Taxonomía de 5 categorías y 19 subtipos de error de consistencia. Los errores se concentran en lo
factual y lo temporal, **hacia la mitad** del relato, en segmentos de mayor entropía.

**Tomado**: la taxonomía para la auditoría de fidelidad de la narración.

### Fein, Russo, Xiang et al. — *LitBench* (2026)
<https://arxiv.org/abs/2507.00769>

2.480 comparaciones por pares. Los jueces pequeños y abiertos **no** evalúan bien escritura
creativa; hay que permutar el orden para contrarrestar el sesgo de posición.

**Tomado**: la comparación a pares con permutación es lo que ya hace `compare-story-runs`, y la
advertencia de no fiarse de un juez pequeño.

### Huot et al. — *Agents' Room* (ICLR 2025)
<https://arxiv.org/abs/2410.02603>

Descompone la escritura en agentes de planificación y de escritura sobre un scratchpad compartido.

**Contraste útil**: es el extremo top-down puro, y es el baseline al que gana el trabajo de Yu et
al. con simulación de personajes. Justifica que el paso de función aporte algo.

---

## 8. Lo que no se tomó, y por qué

| Idea | De dónde | Por qué no |
|---|---|---|
| Actor global centralizado | Open-Theatre | Más barato y más coherente, pero imposibilita las fronteras de conocimiento separadas, que es lo que se mide |
| Memoria por embeddings | Generative Agents, BookWorld | Rompe el determinismo y añade un servicio externo; la recuperación léxica basta para escenas cortas |
| Doble evaluación | Aylett y Louchart | Duplica las llamadas; el director hace ese papel desde fuera |
| Mapa geoespacial con distancias | BookWorld | El guion ya fija ubicación y reparto, y `script.py` ya los valida |
| Memoria de mundo estructurada | WSE-bench (WMEM) | Su propia evaluación muestra que no da beneficio estable de consistencia y reduce la cobertura |
| Puesta en escena generativa | EvoSpark | El guion validado ya resuelve el problema que ataca |
| A-MEM con enlaces evolutivos | A-MEM | Una llamada por escritura de memoria, y aquí hay una por testigo y turno |
| Factor de comportamiento anómalo | StoryBox | Introduce aleatoriedad no determinista; aquí la variación la da el propio actor |

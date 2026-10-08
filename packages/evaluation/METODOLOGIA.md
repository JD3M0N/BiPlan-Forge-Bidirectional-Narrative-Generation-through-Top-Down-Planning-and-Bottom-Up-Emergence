# Metodología de evaluación

Cómo se evalúan las historias de Stagecraft en la tesis. El documento sigue las indicaciones del
tutor (audio del 2026-10-03) y su rúbrica, y las contrasta con la literatura reciente. La planilla
con todo lo que se mide está en [planilla/](planilla/). La implementación y el protocolo
operativo vigente están en [ESTUDIO_FINAL.md](ESTUDIO_FINAL.md). Las herramientas están listas;
el corpus definitivo y la ejecución experimental siguen pendientes.

## 1. De dónde sale

### Las indicaciones del tutor

El audio (`docs/audio_2026-10-03_14-09-35.ogg`, 7 min 46 s) está transcrito junto a él, en
`docs/audio_2026-10-03_14-09-35.transcripcion.md`. Los dos archivos quedan fuera de git. Lo que
pide, con sus marcas de tiempo:

1. **Dos evaluaciones y una intermedia** [00:08–00:22]. La humana da «el criterio de calidad de me
   gusta esta historia o no, que es muy difícil de cuantificar». La mecánica sirve «para poder
   evaluar historias en grande». Y «puedes hacer una cosa intermedia».
2. **La mecánica cuenta cosas** [00:22–02:23]. Un modelo de lenguaje lee los artefactos y extrae
   «métricas cuantificables, que alguien leyéndose la historia pudiera sacar la cuenta». Sus
   ejemplos:
   - la consistencia;
   - los porcentajes en que participa cada personaje;
   - las escenas con algún conflicto;
   - las veces que alguien usa un objeto;
   - las veces que alguien participa en un diálogo, y cuántas de esas réplicas se desvían de su
     personalidad;
   - los personajes que mienten;
   - las cosas complicadas;
   - los eventos aleatorios.

   Son «indicadores de bajo nivel» que dicen si una historia «tiene más cantidad de cosas
   interesantes que otra». De cada historia sale «una tablita», y las tablitas se comparan entre
   parametrizaciones del generador. Ese es el **análisis horizontal**: «con todas las cosas
   activadas, pero cambiando diferentes niveles», por ejemplo el tono.
3. **La humana compara por pares** [02:45–04:27].
   - Una persona (tú, quizá otra) lee de 5 a 10 historias, al azar y sin saber con qué mecanismo
     se generaron.
   - Algunas se generan **directamente con un prompt**, porque «tienes que tener como baseline el
     prompt».
   - No se puntúa en una escala: «en una escala del uno al 10 […] ese 8 no significa nada». Se
     pregunta «de estos dos, ¿cuál te gusta más?».
   - Hay tres criterios «de muy alto nivel», uno por pregunta:
     - «¿cuál tiene más creatividad?»;
     - «¿en cuál están los personajes mejor desarrollados?»;
     - «¿en cuál está la trama más interesante?».
4. **La intermedia es un juez aprendido** [04:27–05:42].
   - Una regresión (scikit-learn) convierte los 18–30 números de la tablita en tres números.
   - Se ajusta para que, aplicada a las historias que ordenaron los humanos, dé su mismo ranking.
   - «Yo no sé qué significa un 6 en creatividad o un 8. Ni me importa», pero si el modelo
     recupera el orden humano «estás entrenando a un juez».
5. **Se aplica al corpus** [05:43–05:55]. Se ordenan todas las historias («las 300») y se analizan
   las 10 mejores: qué tienen y qué no.
6. **La aportación** [05:55–06:21] es un generador más una metodología de evaluación. Tiene una
   parte humana, irremplazable porque mide el buen gusto, y una aproximación automática que
   escala.
7. **Queda fuera de la tesis** [06:21–07:43] usar el juez como función objetivo:
   - generar 50 historias con distintas combinaciones y devolver la mejor;
   - más adelante, un algoritmo genético sobre los parámetros.

   Es la recomendación para el trabajo siguiente. «Lo tuyo se queda en la evaluación.»

### La rúbrica del tutor

`docs/sanderson-craft.pdf` es del mismo tutor (Piad, 2026-08-04). Su §1.1 dice: «para evaluar lo
que el sistema genera, *Flash Fiction Rubric* […] empieza por ahí en vez de inventar una desde
cero».

- La rúbrica (§3.8) tiene 20 dimensiones en cinco bloques: trama, personaje, mundo, integración y
  oficio. Casi todas son de sí o no, o se pueden contar.
- Es justo el «montón de promptcitos que sean métricas cuantificables» del audio, así que es **la
  primera fuente de los rasgos**.
- Los ítems que la rúbrica puntúa de 1 a 5 se reformulan como recuentos, porque el tutor no se fía
  de las escalas.
- El ítem 16 (canon) es solo para series y no entra.

### El antecedente: la tesis de Roger Fuentes (2025)

Con los mismos tutores, Roger evaluó con 12 voluntarios desde un bot de Telegram (cap. 4,
pp. 51–56).

- Cada interacción producía dos historias: una del modelo «monolítico», con un prompt de *master
  storyteller*, y otra de su sistema.
- Se puntuaban cinco preguntas tipo UEQ de 1 a 10: facilidad de uso, creatividad, adaptabilidad,
  fiabilidad y satisfacción.
- Los dos radares «difieren ligeramente».

Es justo lo que el tutor advierte: la escala absoluta no discrimina.

- **Se conserva** la línea base monolítica.
- **Se cambian** la escala por comparaciones por pares, y los criterios de experiencia de uso por
  criterios narrativos.
- El `evaluation.json` actual, con seis métricas de 1 a 10, es heredero de ese esquema. Sigue
  funcionando, pero **no es la medida de la tesis**: es un instrumento heredado.

## 2. Principios

- **Lo humano decide el gusto.** Ninguna cifra automática sustituye a una persona que prefiere
  una historia a otra.
- **La máquina cuenta, no juzga.** Al modelo no se le pregunta si una historia es buena: se le
  pide que cuente cosas y que cite el pasaje de cada una. El código comprueba que la cita está
  literalmente en el texto, como ya hace la auditoría de promesas del formato simulado
  (`stage/promise_audit.py`).
  - Así se esquiva lo que el [Protocolo de medición](../../TODO.md) ya advierte, y la literatura
    confirma: los jueces LLM de calidad creativa no coinciden con los expertos y prefieren su
    propio texto (TTCW, Chhun 2024, Panickssery 2024).
- **El juez aprendido traduce lo uno a lo otro.** Aprende de los pares humanos qué combinación de
  recuentos predice la preferencia. LitBench (2026) da el respaldo: un modelo Bradley-Terry
  entrenado con pares humanos acierta un 78 % de los pares, y el mejor juez LLM sin entrenar, un
  73 %.
- **Por pares y no en escala.**
  - Con escalas de 1 a 5, unos profesores de inglés solo alcanzaron un α de Krippendorff de
    0,05–0,33 (Chiang y Lee 2023).
  - Ordenar es más fiable que puntuar (RankME 2018; van der Lee 2019).

## 3. Evaluación mecánica: los rasgos

El catálogo completo está en [planilla/rasgos.csv](planilla/rasgos.csv): unos 140 rasgos, cada
uno con su definición operativa, su fuente, el parámetro que debería moverlo y el criterio humano
al que debería ayudar. Se organizan en capas:

| Capa | Qué es | De dónde sale | Para qué |
|---|---|---|---|
| **T** | cifras del texto (palabras, diálogo, repetición de trigramas…) | código sobre `story.md` | juez y horizontal |
| **R** | la rúbrica del tutor hecha contable | extractor sobre `story.md` | juez y horizontal |
| **X** | los recuentos del audio y de la literatura | extractor sobre `story.md` | juez y horizontal |
| **P** | el proceso: plan, promesas, crítica, guion, función, inventario | JSON del run | horizontal y validación |
| **K** | el coste: llamadas, tokens, tiempo | `llm_usage.json`, `metadata.json` | horizontal |
| **C** | la configuración: formato, visión, tono, memoria… | `generation_options.json` | eje X del análisis horizontal |
| **H** | las tres puntuaciones humanas | pares a ciegas | objetivo del juez |
| **J** | las tres predicciones y el puesto | juez aprendido | ranking del corpus |

### Por qué el juez solo lee el texto

El tutor habla de «leerse todos los JSON». Pero el juez tiene que puntuar **todas** las historias,
y la línea base y buena parte del corpus histórico solo tienen `story.md`. Por eso los rasgos que
entran al juez (T, R, X) salen del texto. El tutor lo pide así: «que alguien leyéndose la historia
pudiera sacar la cuenta».

Los JSON del proceso (P) tienen tres usos:

- el análisis horizontal;
- explicar por qué las mejores historias son las mejores;
- **validar al extractor**. En el formato simulado, el log de la función es la verdad de
  referencia de varios recuentos del texto: participación por actor, acciones con objetos,
  eventos del mundo, susurros, compuertas reveladas y mentiras. La columna `validable_contra` dice
  cuál. Como el narrador puede cortar, el log es un techo: se espera que el texto cuente menos,
  no más.

### Rasgos núcleo

Solo entran al juez los rasgos marcados `núcleo`: 27, dentro de la horquilla del tutor («18, 20,
30 números»).

- Los demás son `secundario`: se miden y se publican, pero no se ajustan, porque con pocas
  historias humanas un modelo con muchos rasgos se sobreajusta.
- La lista núcleo se fija **antes** de ver las preferencias humanas.

### El extractor

Usa el proveedor configurado, mediante el adaptador de Stagecraft (ficha MED-9).

- **Entrada:** `story.md` y las definiciones de `rasgos.csv`.
- **Salida:** cada recuento con las citas literales que lo sustentan. Una cita que no aparece en el
  texto provoca una reparación acotada; si falla, el resultado es incompleto, nunca cero.
- **Desgloses:** la participación (X02) se publica también por personaje, y el diálogo (X08)
  por hablante, como pide el audio [00:34–00:53]. X08 y X11 se extraen siempre, como
  auxiliares fuera del juez.
- **Normalización:** los recuentos que crecen con la longitud se dan por 1000 palabras (columna
  `unidad`). Las palabras (T01) entran al juez como covariable, para que su peso quede a la vista.
- **Validación:**
  - contra los logs, en los runs simulados;
  - repitiendo la extracción en un subconjunto (test-retest), para medir su estabilidad;
  - revisando a mano una muestra de contradicciones (X20), porque los detectores LLM tienen poca
    cobertura (Ahuja et al. 2025).
- **Coste:** de 2 a 3 llamadas por historia. Las 157 historias actuales, con una mediana de 2591
  palabras, son unas 400 llamadas: uno o dos días de cuota gratuita.

## 4. Análisis horizontal

El estudio principal compara las cinco historias seleccionadas y las aportaciones de lectores
con prompts y opciones libres. Se describen asociaciones entre configuración, rasgos y costes,
separando versiones. No se atribuyen causalmente las diferencias a un parámetro.

La matriz de [planilla/matriz.csv](planilla/matriz.csv) queda como diseño posible posterior,
sujeto a presupuesto y generador definitivo. No se genera en esta implementación. Para una
comparación controlada futura se usarán las reglas de emparejamiento de `pairing.py`.

## 5. Evaluación humana

El protocolo es aproximadamente 6–8 lectores y 11–13 historias: cinco seleccionadas
(dos directas, tres del sistema) más una aportación reemplazable por lector. Primero se recoge,
después se congela el conjunto y finalmente se vota. No se evalúan historias propias o conocidas.

Cada lector recibe hasta diez historias en dos sesiones de hasta cinco, con sorteo reproducible,
cobertura equilibrada y posiciones A/B compensadas. Se busca que cada historia se compare con
otras dos por criterio en cada sesión y que existan pares compartidos entre lectores. Se presenta
una pregunta y un criterio cada vez, con las formulaciones de la planilla.

Se admite A, B o «No puedo decidir». La abstención se registra y no es empate ni victoria.
Se informa cobertura prevista, votos efectivos y abstenciones por separado. No se calcula un
ranking humano global si el grafo de comparaciones queda desconectado.

La agregación usa Bradley–Terry regularizado por criterio e intervalos por bootstrap de lectores.
El acuerdo se calcula sobre los mismos pares y criterios, mediante proporción de acuerdo y alfa
nominal, con y sin el autor. No se reconstruyen rankings individuales completos para calcular W
de Kendall a partir de comparaciones parciales. El estudio es exploratorio y no tiene potencia
para diferencias pequeñas.

El registro persistente usa SQLite fuera de los runs, con seudónimos en las exportaciones.
La guía [ESTUDIO_FINAL.md](ESTUDIO_FINAL.md) especifica estados, comandos, exclusiones y reanudación.

## 6. El juez aprendido

Por cada criterio se ajusta una regresión logística por pares (ficha EXP-7):

- Cada juicio humano «A gana a B» es un ejemplo cuya entrada es la diferencia entre los rasgos
  núcleo estandarizados de A y de B.
- Es un Bradley-Terry con covariables, o un RankNet lineal, con regularización L2.
- Los pesos resultantes dan, para cualquier historia, un número por criterio (J01–J03). La escala
  no tiene unidades, como dice el tutor: solo importa el orden.

**Cómo se valida.** El criterio del tutor es que el juez «recupere el ranking» humano.

- Con 10 historias y 27 rasgos, recuperarlo **dentro de la muestra** es trivial: cualquier modelo
  lo memoriza.
- Por eso se mide **fuera de la muestra**, dejando una historia fuera: el modelo se ajusta sin
  ella, predice sus pares y se informan:
  - la precisión por pares;
  - la τ de Kendall frente al orden Bradley-Terry humano.
- Hay además un **control con perturbaciones** (OpenMEVA): historias rotas a propósito, con
  escenas barajadas, el pago final borrado o la visión cambiada a mitad. Se publican los cambios;
  no se exige que toda perturbación empeore todos los criterios.
- Los pesos se publican. Un juez que solo premia la longitud o el diálogo se ve a simple vista.

## 7. Ranking del corpus y análisis de las mejores

El juez puntúa todas las historias completadas de `Stories/`: el corpus histórico más la matriz
(ficha EXP-8).

- Los tres rankings son principales. J04 es auxiliar: media con pesos iguales y normalización
  fijada al entrenar, nunca reajustada sobre el corpus nuevo.
- El análisis cualitativo lee las 10 mejores y mira qué tienen y qué no: sus rasgos, su
  configuración y su proceso.
- Los runs de versiones que no se comparan se marcan. Por ejemplo, las funciones 7.0 y 7.1 frente
  a las de 7.2 en adelante.

## 8. Lo que aporta y lo que queda para después

La tesis entrega el generador, con sus parámetros, y esta metodología: la parte humana y su
aproximación automática.

Lo que el tutor deja como recomendación [06:21–07:43]:

- usar el juez como función objetivo: generar N historias con distintas combinaciones de
  parámetros y devolver la mejor;
- después, buscar la configuración con un algoritmo genético.

Hoy la calidad depende de lo que el usuario elige; ese paso la automatiza. No forma parte de esta
tesis.

## 9. Estado del arte de la evaluación

La bibliografía completa, con qué aporta cada trabajo y qué se adopta, está en
[planilla/bibliografia.csv](planilla/bibliografia.csv). Lo esencial:

- **Criterios.**
  - Los tres criterios del tutor coinciden con los de Agents' Room (Huot et al., ICLR 2025):
    Plot, Creativity y Development, con pares de expertos y Bradley-Terry. Es el diseño publicado
    más cercano a Stagecraft: varios agentes, primero planifican y luego escriben.
  - HANNA (Chhun et al. 2022) es la fuente de las seis métricas heredadas.
- **Escalas y protocolo.**
  - Chiang y Lee (2023) y Amidei et al. (2019) documentan el bajo acuerdo de las escalas.
  - RankME (2018) y van der Lee et al. (2019, 2021) recomiendan ordenar, usar al menos tres
    evaluadores e informar el acuerdo.
  - Howcroft et al. (2020): publicar la pregunta exacta.
  - Card et al. (2020): potencia estadística.
  - Boubdir et al. (2023) y Chatbot Arena (2024): Bradley-Terry mejor que Elo.
- **Jueces LLM.**
  - TTCW (Chakrabarty et al. 2024): un LLM que aplica los tests correlaciona ≈0 con los
    expertos.
  - Chhun et al. (2024): los jueces sirven a nivel de sistema, no por historia.
  - Panickssery et al. (2024): autopreferencia.
  - «Style over Story» (Jung et al. 2025): los jueces premian el estilo.
  - Tutone et al. (2026): las métricas automáticas no siguen a los humanos en creatividad.
  - LitBench (2026): un juez entrenado con pares supera al juez directo.
- **Recuentos con cita**, que son el modelo del extractor:
  - ConStory-Bench (2026) para las contradicciones;
  - DramaBench (2025) para el conflicto;
  - CharacterEval (2024) y PersonaGym (2025) para las réplicas fuera de personaje;
  - TimeChara (2024) y Generative Agents (2023) para las fugas de conocimiento;
  - FANToM (2023) para la información asimétrica;
  - CFPG (2026) para la relación entre lo que se anticipa y su pago.
- **Un hueco que la tesis puede reclamar.** No hay una métrica validada de violaciones del punto
  de vista (un narrador limitado que cuenta pensamientos ajenos). Aquí es el rasgo X27, y lo
  mueve el parámetro «visión».

Las referencias marcadas «revisar cifras en el PDF» se comprueban antes de citarlas en la memoria
de la tesis.

## 10. Amenazas a la validez

- **Pocos evaluadores**, y uno es el autor, que conoce el estilo del sistema. Se informa el
  acuerdo con y sin él.
- **Gemini lee a Gemini.** El extractor solo cuenta, y cada recuento lleva una cita verificada;
  aun así, se valida contra los logs y con test-retest.
- **La longitud.** Las historias largas tienen más de todo: los recuentos se normalizan y la
  longitud entra como covariable visible.
- **Versiones mezcladas.** El corpus histórico abarca de 4.0 a 7.6, y no todo se compara. El
  ranking marca las versiones, y el análisis horizontal usa solo la matriz nueva.
- **Ruido entre corridas.** Hasta 16 puntos con el mismo prompt: una celda con una sola historia
  es un indicio, no una medida.
- **La cuota.** La matriz completa son varios días de cuota gratuita (ver `matriz.csv`).

## 11. Pasos

| Paso | Ficha | Cuota |
|---|---|---|
| Línea base de un solo prompt | MED-8 | ~1 llamada por historia |
| Extractor de rasgos con cita verificada | MED-9 | 2–3 llamadas por historia |
| Tabla de rasgos por historia | MED-10 (cerrada en `asg-evaluation` 1.1.0) | sin cuota |
| Generar la matriz horizontal | MED-3, MED-5 y las EXP de formato | ver `matriz.csv` |
| Evaluación humana por pares | EXP-4 | sin cuota |
| Juez aprendido | EXP-7 | sin cuota |
| Ranking del corpus y análisis de las 10 mejores | EXP-8 | sin cuota |

La planilla Excel ([planilla/planilla_evaluacion.xlsx](planilla/planilla_evaluacion.xlsx)) se
regenera desde los CSV con `python packages/evaluation/planilla/build_planilla.py`, que también
reescribe la cabecera de `plantilla_historia.csv` a partir de los ids de `rasgos.csv`.

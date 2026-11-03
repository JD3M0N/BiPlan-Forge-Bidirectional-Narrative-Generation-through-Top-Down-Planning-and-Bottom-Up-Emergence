# Metodología de evaluación

Cómo se evalúan las historias de Stagecraft en la tesis. El documento sigue las indicaciones del
tutor (audio del 2026-10-03) y su rúbrica, y las contrasta con la literatura reciente. La planilla
con todo lo que se mide está en [planilla/](planilla/). Los comandos, paso a paso, están en el
[README](README.md), y el bot que recoge historias y votos, en
[apps/telegram](../../apps/telegram/README.md).

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
- El `evaluation.json` de los runs antiguos, con seis métricas de 1 a 10, era heredero de ese
  esquema. Se retiró en `asg-evaluation` 2.0.0: **no es la medida de la tesis**.

## 2. Principios

- **Lo humano decide el gusto.** Ninguna cifra automática sustituye a una persona que prefiere
  una historia a otra.
- **La máquina cuenta, no juzga.** Al modelo no se le pregunta si una historia es buena: se le
  pide que cuente cosas y que cite el pasaje de cada una. El código comprueba que la cita está
  literalmente en el texto, como ya hace la auditoría de promesas del formato simulado
  (`stage/promise_audit.py`).
  - Así se esquiva lo que el [Protocolo de medición](../../planning/decisions.md) ya advierte, y la literatura
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

Solo entran al juez los rasgos marcados `núcleo`: 24, dentro de la horquilla del tutor («18, 20,
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

#### Validación del extractor (2026-10-29)

Diseño y umbrales: `planning/decisions.md` §2 (P04.3), fijados antes de medir. Este apartado
solo informa; no cambia la lista núcleo (eso es P04.9). Los datos viven en
`Evaluations/validacion-extractor/` (local, ignorado por Git).

- **Muestra:** 12 runs elegibles (21.471 palabras): 5 simulados con log, 4 narrativos y 3 líneas
  base. Modelo `gemini-3.5-flash-lite`. Test-retest en 6 de ellos.
- **Extracciones incompletas:** 6 de 12 quedaron `incompleta` (`dato-ausente`, 31 fallos, sin
  ningún rasgo; `03-ultima-luz` 14; `04-cine` 11; `islas` 2; `misterio-del-faro` 1) y cuentan como
  fallos del extractor. Buena parte de los cambios de estado del test-retest vienen de ahí.
- **Quién revisó, y un cambio respecto al diseño:** P04.3 preveía unas 7 h de revisión manual de
  Josue. Los veredictos los dio Claude leyendo solo la ocurrencia, la cita y su párrafo (no las
  historias enteras), y Josue los aceptó el 2026-10-29. Es una revisión más débil que la
  prevista: no puede detectar nada que el extractor no citara.
- **Cobertura: no medida.** Nadie anotó `ocurrencias_omitidas`, así que el umbral 2 (≥ 0,70) no
  se evalúa en ningún rasgo. Ningún «cumple» de abajo es definitivo. Pendiente: leer las
  historias y anotar las omitidas, al menos en los 6 del test-retest.
- **Precisión:** `correcto` / (`correcto` + `incorrecto`), sin las `dudoso`, como fija P04.3. Con
  tantas dudosas, la precisión sale casi siempre 1,00, así que se da también la cota inferior
  que las cuenta como error. Por debajo de 5 citas juzgadas, «sin evidencia suficiente».

| Rasgo | Precisión (correctas / juzgadas) | Si «dudosa» cuenta como error | Test-retest (dif. media; cambios de estado) | Techo del log | Resultado |
|---|---|---|---|---|---|
| R01 | 5/5 | 1,00 | 0,00; 0/6 | no aplica | cumple, sin cobertura |
| R02 | 15/15 (+3 dudosa/s) | 0,83 | 0,00; 0/6 | no aplica | cumple, sin cobertura |
| R03 | 1/1 | 1,00 | 0,00; 3/6 | no aplica | no cumple (test-retest); precisión sin evidencia |
| R04 | 5/5 (+2 dudosa/s) | 0,71 | 0,00; 1/6 | no aplica | cumple, sin cobertura |
| R05 | 5/5 | 1,00 | 0,25; 1/6 | no aplica | cumple, sin cobertura |
| R09 | 10/10 (+6 dudosa/s) | 0,62 | 0,19; 0/6 | no aplica | cumple, sin cobertura |
| R15 | 4/4 | 1,00 | —; 3/6 (sin pares medidos) | no aplica | no cumple (test-retest); precisión sin evidencia |
| R16 | 5/5 (+1 dudosa) | 0,83 | 0,00; 2/6 | no aplica | no cumple (test-retest) |
| R17 | 0/0 | — | 0,00; 1/6 | no aplica | sin evidencia suficiente |
| R18 | 6/6 (+7 dudosa/s) | 0,46 | 0,12; 1/6 | no aplica | cumple, sin cobertura |
| R23 | 7/7 (+1 dudosa) | 0,88 | 0,00; 2/6 | no aplica | no cumple (test-retest) |
| R24 | 8/8 | 1,00 | 0,00; 2/6 | no aplica | no cumple (test-retest) |
| X06 | 28/28 (+6 dudosa/s) | 0,82 | 0,00; 2/6 | no aplica | no cumple (test-retest) |
| X09 | 0/0 | — | —; 1/6 (sin pares medidos) | no aplica | no cumple (test-retest); precisión sin evidencia |
| X10 | 0/0 (+1 dudosa) | 0,00 | 0,00; 2/6 | 0/2 comparados | no cumple (test-retest); precisión sin evidencia |
| X13 | 3/3 (+1 dudosa) | 0,75 | 0,00; 2/6 | 0/4 comparados | no cumple (test-retest); precisión sin evidencia |
| X14 | 21/21 (+1 dudosa) | 0,95 | 0,00; 1/6 | no aplica | cumple, sin cobertura |
| X15 | 9/9 | 1,00 | 0,17; 1/6 | no aplica | cumple, sin cobertura |
| X16 | 6/6 | 1,00 | 0,18; 0/6 | 0/4 comparados | cumple, sin cobertura |
| X17 | 21/21 (+3 dudosa/s) | 0,88 | 0,22; 1/6 | 0/1 comparados | cumple, sin cobertura |
| X20 | 1/1 (+1 dudosa) | 0,50 | 0,00; 2/6 | no aplica | no cumple (test-retest); precisión sin evidencia |
| X24 | 0/0 | — | —; 2/6 (sin pares medidos) | no aplica | no cumple (test-retest); precisión sin evidencia |
| X02 | no se revisa (código) | no se revisa (código) | 0,04; 0/6 | no aplica | cumple (test-retest) |
| X03 | no se revisa (código) | no se revisa (código) | 0,01; 0/6 | no aplica | cumple (test-retest) |
| X29 | no se revisa (código) | no se revisa (código) | 0,01; 2/6 | no aplica | no cumple (test-retest) |

**Lectura** (cifras de las salidas de `asg-audit-features --veredictos`, `--pares` y
`--run`):

- **Cumplen lo medible, falta la cobertura (10):** R01, R02, R04, R05, R09, R18, X14, X15, X16 y
  X17. Con «dudosa» como error, R18 (0,46) y R09 (0,62) bajarían de 0,80, y R04 (0,71) también:
  son los más frágiles. Los dudosos de R18 son restricciones de trama (un plazo, una salida
  bloqueada) tomadas por reglas del mundo: un error de definición.
- **No cumplen el test-retest (12):** R03, R15, R16, R23, R24, X06, X09, X10, X13, X20, X24 y X29.
  Probablemente es por extracciones fallidas en una de las dos pasadas, no por inestabilidad del
  valor: R03, R15, R23, R24, X09 y X24 apenas tienen pares medidos en ambas.
- **Sin evidencia suficiente en precisión (< 5 citas):** R03, R15, X09, X10, X13, X20 y X24, y R17
  sin ninguna. R17, X09 y X24 no tuvieron ocurrencias citadas en toda la muestra.
- **Techo del log:** ningún rasgo con log (X10, X13, X16, X17) lo supera en ninguno de los runs
  comparados; X17 solo se pudo comparar en 1 de 5 y X10 en 2.
- **Calculados con código:** X02 y X03 cumplen el test-retest (0,04 y 0,01). X29 hereda las
  fallas del extractor de X08 (2 cambios de estado).
- **Medidos sin citas (inconsistencia a revisar):** R17 y X23 en `el-pacto-roto`, R24 en
  `la-regencia-de-las-escamas`, R17 y X23 en `el-misterio-del-faro` tienen estado `measured` sin
  ocurrencias citadas.
- **`not_applicable` dudosos:** al no haber leído las historias enteras solo consta uno:
  `04-cine-de-los-domingos-1` marca X20 como `not_applicable` mientras X13 describe versiones
  previas desmentidas. El resto de los `not_applicable` no se ha contrastado con el texto.
- **Fuera del núcleo:** X23 (preguntas abiertas) tiene 0 correctas, 1 incorrecta y 1 dudosa: el
  extractor confunde plazos con preguntas.
- **Límite:** son 12 historias; no se extrapola fuera de la muestra.
- **Matiz sobre X09:** figura como «no cumple» con 1 cambio de estado, que el umbral admite;
  falla porque no tiene ningún par medido en ambas pasadas.
- **Decisión (P04.9, 2026-10-30):** R15, R17, X09 y X24 pasan a `secundario`; los otros ocho
  que fallan el test-retest se conservan con la excepción escrita en `planning/decisions.md`
  §2. El núcleo queda en 24 y esta validación sigue siendo provisional.

## 4. Análisis horizontal

El estudio principal compara las aportaciones de los participantes, con prompts libres y los dos
enfoques, y las líneas base. Se describen asociaciones entre configuración, rasgos y costes,
separando versiones. No se atribuyen causalmente las diferencias a un parámetro.

La matriz de [planilla/matriz.csv](planilla/matriz.csv) se genera con el generador congelado
(Stagecraft 7.22) y se compara **emparejada por plan fuente**. Cada base (M01: simulado con los
predeterminados, obras 01, 03 y 04, dos repeticiones) es el plan fuente de sus derivadas:
narrativo con `--plan-from` (EXP-1) y tono y visión con `--narrate-from`, que solo cambia la
narración. Se lee la diferencia de cada rasgo entre cada derivada y su base (C18,
`source_run.json`), y las líneas base (M02) entran como celda propia (T6). Decisión, coste y regla
de ruido: `planning/decisions.md` §2 («Matriz del análisis horizontal»). Una diferencia por debajo
de esa regla no se interpreta.

`asg-report-features RAÍZ --horizontal SALIDA.json --manifest MANIFIESTO` produce esa lectura: por
celda, mediana, mínimo, máximo y n de las diferencias emparejadas, con los 24 núcleo primero y
después P y K, y escribe un CSV junto al JSON. Lo no medido sale `no medido`, nunca cero; la
etiqueta «dentro del ruido» o «interpretable» aplica la regla anterior.

## 5. Evaluación humana

El protocolo tiene tres fases, y el investigador decide cuándo pasar de una a otra:

1. **Recogida.** Cada participante crea historias desde el bot de Telegram, eligiendo el
   enfoque (Top-Down o híbrido) y la forma (prompt libre u obra guiada). Cada historia queda
   inscrita como suya. El investigador añade las líneas base de un solo prompt y puede excluir
   las que no deban entrar.
2. **Votación.** `asg-study open` congela el conjunto con su huella. Desde ahí, `/estudio`
   presenta pares a ciegas, solo texto (sin audio, sin encabezados ni título), y una pregunta cada vez, con las formulaciones de
   la planilla. Nadie compara su propia historia, y «Ya la conocía» la cambia por otra.
3. **Cierre.** `asg-study close` y la exportación seudónima.

**Asignación.** Las preguntas se asignan de una en una cuando el lector las pide, así que puede
votar cualquiera, haya aportado o no.

- El criterio va en ciclo.
- Se eligen primero las historias que el lector ya leyó, para que el esfuerzo de lectura no
  crezca con cada pregunta. Después, los pares menos comparados y las historias menos vistas.
- Cada lector responde como mucho 15 preguntas, unas cinco historias por tres criterios, y nunca
  repite par y criterio. La posición A/B se compensa.
- El sorteo es reproducible con la semilla del estudio.

Se admite A, B o «No puedo decidir». La abstención se registra y no es empate ni victoria.
Se informan votos efectivos y abstenciones por separado. No se calcula un ranking humano global
si el grafo de comparaciones queda desconectado.

La agregación usa Bradley–Terry regularizado por criterio e intervalos por bootstrap de lectores.
El acuerdo se calcula sobre los mismos pares y criterios, mediante proporción de acuerdo y alfa
nominal, con y sin el autor. No se reconstruyen rankings individuales completos para calcular W
de Kendall a partir de comparaciones parciales. El estudio es exploratorio y no tiene potencia
para diferencias pequeñas.

El registro persistente usa SQLite fuera de los runs, con seudónimos en las exportaciones.

### Piloto 7.22 (votos transcritos)

Medido el 2026-11-02 sobre `Evaluations/estudio-piloto-722/` (P07.5). Son los únicos votos humanos
de la tesis y no siguen el protocolo de arriba: los 5 lectores (30–31 de octubre; el autor no votó)
respondieron con una **hoja de orden fijo** (`decisions.md` §2, P07.1), y Josue transcribió a mano
y cotejó fila a fila sus respuestas en `votos-transcritos.csv`. `asg-study import-votes` las cargó
todas o ninguna (`votos-importados.json`: SHA-256 `af101770…9ecc2`, 69 votos, 5 lectores), con el
orden A/B de la hoja y `seconds` nulo. La base está `closed`; la exportación es
`export-piloto-2026-11-02.json` y sus 69 votos coinciden uno a uno con las filas del CSV
(lector, posición, criterio, historias A y B, elección). La copia previa es
`study.antes-votos.sqlite3`.

Historias (6, todas 7.22): obra 01, H1 y H2 simuladas y H3 línea base; obra 03, H4 simulada, H5
narrativa y H6 línea base. Cada lector vio los pares H1–H3, H2–H3, H4–H5, H4–H6 y H5–H6, en ese
orden y con la misma historia como A, cada uno con los tres criterios en ciclo; L2 paró en la
pregunta 9 (29 lecturas en total).

| Criterio | Preguntas | Votos efectivos | Abstenciones | Acuerdo | α nominal | Pares de lectores |
|---|---|---|---|---|---|---|
| Creatividad | 23 | 20 | 3 | 0,40 | −0,14 | 30 |
| Personajes | 23 | 20 | 3 | 0,52 | 0,05 | 31 |
| Trama | 23 | 21 | 2 | 0,44 | −0,09 | 36 |

Votos por par (A–B–abstenciones; A es la primera historia del par):

| Par | Creatividad | Personajes | Trama |
|---|---|---|---|
| H1–H3 | 2–2–1 | 1–4–0 | 4–1–0 |
| H2–H3 | 1–3–1 | 3–1–1 | 2–3–0 |
| H4–H5 | 2–2–1 | 1–3–1 | 3–2–0 |
| H4–H6 | 3–1–0 | 1–3–0 | 2–1–1 |
| H5–H6 | 2–2–0 | 2–1–1 | 1–2–1 |

- **Cobertura.** Por criterio, H1 y H2 entran en 4 comparaciones cada una y las otras cuatro en 8.
  H1–H2 nunca se comparan directamente.
- **Grafo.** En los tres criterios tiene dos componentes, una por obra, porque no hay pares entre
  obras. `asg-preferences --bootstrap 1000` (`preferencias.json`) da `insufficient` en los tres,
  sin puntuaciones ni intervalos (0 réplicas válidas): no hay ranking humano global ni τ de
  Kendall. Con y sin el autor sale lo mismo, porque el autor no votó.
- **Acuerdo.** Cercano al azar en los tres criterios (α entre −0,14 y 0,05) con 5 pares repetidos
  por criterio. Con estos datos no se puede afirmar que los lectores coincidan en qué historia es
  mejor en ningún criterio.

Amenazas, además de las generales del estudio:

- **Transcripción a mano.** El CSV es una copia hecha por Josue y cotejada por él mismo; no hay
  un segundo transcriptor. La huella fija el archivo importado, no su fidelidad a las hojas.
- **Orden fijo.** El sesgo de posición no se separa de la historia (en total, 30 A y 31 B), el
  cansancio cae siempre sobre los mismos pares (H5–H6 al final) y los pares no salen de la
  asignación del bot, que compensa A/B y empareja obras distintas.
- **Presentación (T5).** Las notas describen la lectura en Telegram (escritorio, Telegram Web,
  Android e iPhone) y el CSV marca todas las respuestas con fuente `papel`; no consta con qué
  presentación exacta se enviaron las historias, así que no se puede asegurar que no tuvieran las
  fugas de encabezado de antes de P06.2.
- **Fallos del piloto.** Los de la tabla del bloque P06 del roadmap, sin arreglar: duración y
  abandono sin avisar (L2 paró en la 9 por tiempo), abstención mal entendida (L1, L3, L5; L5
  necesitó que se la explicaran), confirmación del voto poco visible (L2, L4), historias que
  reaparecen sin explicación (L5) y navegación difícil entre historias largas.
- **Sospecha de L4.** Conjeturó que alguna historia venía de una simulación por los turnos de
  diálogo y acciones repetidas; no consta si acertó ni en qué votos influyó.
- **Creatividad ambigua.** L1 dudó entre una idea poco habitual y una forma original de contarla;
  L3 dudó entre personajes desarrollados y personajes que le caían bien, y entre trama y emoción
  del final. Las preguntas no se cambian (T7).
- **Tamaño.** 5 lectores, 6 historias y 2 familias: sirve para entrenar el juez exploratorio de
  P07 (`decisions.md` §2, P07.1 a), no para concluir qué enfoque prefieren los lectores.

**Rasgos del piloto (P07.6, 2026-11-02 y 2026-11-03).** Extraídos con `gemini-3.5-flash-lite`,
selección núcleo y el catálogo vigente, sobre las 6 historias congeladas y sus 12 perturbaciones
(`asg-perturb`: escenas barajadas y sin el último quinto). Costó **653 llamadas reales** (178 y
475), frente a las ~54 estimadas: la extracción sale `incompleta` a menudo y hubo que relanzarla
muchas veces, y unas 45 llamadas se perdieron al rehacer desde cero una versión de H3 casi
completa. Resultado: las 6 historias con los 24 núcleo `measured` o `not_applicable`; X15 de H3
sale de un intento archivado del mismo protocolo (`decisions.md` §2, P07.6), validado contra otra
segmentación en escenas. 11 de 12 perturbaciones completas; `s037b5a5c6f0949ae-no-ending` no
mide R03 y queda fuera de `casos.json`. La tablita de las 6 está en `tabla-rasgos.json` y `.csv`.

- **Inestabilidad del extractor.** En H3 cada extracción desde cero atascó un rasgo distinto
  (R03 y R16 por exigir dos citas, X15–X17 por citas fuera de su escena); reintentar sobre la
  misma segmentación repite casi la misma respuesta. En los textos sin desenlace el modelo se
  marca incompleto en R03 en vez de contar 0. Las 5 versiones archivadas de H3 que miden X15
  dan el mismo valor (1).

## 6. El juez aprendido

Por cada criterio se ajusta una regresión logística por pares (ficha EXP-7):

- Cada juicio humano «A gana a B» es un ejemplo cuya entrada es la diferencia entre los rasgos
  núcleo estandarizados de A y de B.
- Es un Bradley-Terry con covariables, o un RankNet lineal, con regularización L2.
- Los pesos resultantes dan, para cualquier historia, un número por criterio (J01–J03). La escala
  no tiene unidades, como dice el tutor: solo importa el orden.

**Cómo se valida.** El criterio del tutor es que el juez «recupere el ranking» humano.

- Con 10 historias y 24 rasgos, recuperarlo **dentro de la muestra** es trivial: cualquier modelo
  lo memoriza.
- Por eso se mide **fuera de la muestra**, dejando una historia fuera: el modelo se ajusta sin
  ella, predice sus pares y se informan:
  - la precisión por pares;
  - la τ de Kendall frente al orden Bradley-Terry humano.
- Hay además un **control con perturbaciones** (OpenMEVA): historias rotas a propósito, con
  escenas barajadas, el pago final borrado o la visión cambiada a mitad. Se publican los cambios;
  no se exige que toda perturbación empeore todos los criterios. `asg-perturb` hace por código
  las dos primeras: capítulos barajados (tercios de párrafos en las líneas base, nunca el orden
  original) y el texto sin el último quinto de sus párrafos. El cambio de visión necesitaría que
  un LLM reescribiera y no se hace.
- Cada validación publica su **cobertura** (votos probados / votos): al dejar fuera una historia o
  una familia se descartan todos los votos que la tocan, y una precisión con poca cobertura se lee
  con ese dato al lado.
- La longitud sola (T01) se valida con el mismo esquema por historias y por familias
  (`length_baseline.by_story`, `length_baseline.by_family`); el juez solo cuenta si supera a la
  longitud en el esquema que corresponde.
- Se informa la **colinealidad** de las historias de entrenamiento de cada criterio (`collinearity`):
  los pares de rasgos con |r| ≥ 0,8, el número de condición de la matriz estandarizada (nulo si es singular) y los rasgos
  constantes. Es un diagnóstico: no cambia la regularización (`C = 1`) ni elige rasgos.
- Los pesos se publican. Un juez que solo premia la longitud o el diálogo se ve a simple vista.

### Resultado del juez (piloto 7.22)

Medido el 2026-11-03 (P07.7), sin llamadas al modelo, con:

```powershell
asg-judge Evaluations/estudio-piloto-722/study.sqlite3 `
  --output Evaluations/estudio-piloto-722/juez.json `
  --perturbations Evaluations/estudio-piloto-722/casos.json
```

Es el **juez exploratorio del piloto (hoja de orden fijo)** (`decisions.md` §2, P07.1 a): 69 votos
de 5 lectores sobre 6 historias de 2 obras (H1–H6 de [Piloto 7.22](#piloto-722-votos-transcritos)),
los 24 rasgos núcleo de P07.6 y `casos.json` tal cual (11 casos, SHA-256 `ccedda1e…b55c976`).
`juez.json` (`schema_version` 3, `status` `exploratory`, scikit-learn 1.9.1, SHA-256
`50472656…6df3e1d93`, `data_hash` `072c1c0d…3d7690b92`) da `fitted` en los tres criterios. La base no
cambió al entrenar (misma huella antes y después). El número que da no es una medida de calidad.

**Validación fuera de muestra.** Aciertos por pares sobre los votos decididos; la cobertura es 1,0
en todos los esquemas. Por historia, cada voto se predice con la media de los pliegues que dejan
fuera una de sus dos historias; por familia, una sola cifra que junta los 2 pliegues (cada uno
entrena con las 3 historias de una obra y prueba con la otra).

| Criterio | Votos | Juez por historia | Juez por familia | Longitud por historia | Longitud por familia | Azar |
|---|---|---|---|---|---|---|
| Creatividad (H01) | 20 | 0,40 (8) | 0,40 (8) | 0,60 (12) | 0,60 (12) | 0,5 |
| Personajes (H02) | 20 | 0,40 (8) | 0,50 (10) | 0,70 (14) | 0,70 (14) | 0,5 |
| Trama (H03) | 21 | 0,43 (9) | 0,43 (9) | 0,62 (13) | 0,62 (13) | 0,5 |

- **El juez no generaliza** (`decisions.md` §2): queda por debajo del azar en los tres criterios por
  historia, y por familia por debajo en creatividad y trama e igual al azar en personajes. La
  longitud sola (T01) lo supera en los tres criterios y en los dos esquemas.
- **Ninguna cifra se separa del azar con estos datos.** Con 20 votos, 14 aciertos (la mejor
  longitud) darían p ≈ 0,12 en una binomial a dos colas, y los votos no son independientes (mismos
  lectores y mismos 5 pares).
- **Que la longitud dé lo mismo en los dos esquemas es mecánico:** con un solo rasgo, cada par se
  predice por el signo de su peso, y ese signo no cambió entre pliegues. Que el juez completo
  coincida en H01 y H03 es casualidad de estos datos.
- **Pliegues por historia.** En la obra 01 todos los votos tocan H3 (pares H1–H3 y H2–H3): dejar
  fuera H3 deja entrenar solo con la obra 03 (11–12 votos). Los pliegues entrenan con 11 a 16 votos;
  los de familia, con 8 a 12.
- **τ de Kendall: no calculable.** El grafo de cada criterio tiene dos componentes, una por obra, y
  tanto el orden humano (`asg-preferences`) como el predicho dan `insufficient` (P07.1). No se
  calcula una τ dentro de cada componente: con 3 historias no dice nada.
- **Un buen ajuste dentro de muestra no acredita nada.** Con 6 historias y 24 rasgos el modelo
  puede ajustar los votos de entrenamiento; solo cuentan las cifras de arriba.

**Pesos** (coeficientes sobre los rasgos estandarizados con las 6 historias; `C = 1`, sin
intercepto). Signo y tamaño son de este ajuste, no efectos de cada rasgo:

| Rasgo | Nombre | H01 | H02 | H03 |
|---|---|---|---|---|
| T01 | Palabras | −0,07 | +0,11 | −0,06 |
| T06 | Proporción de diálogo | −0,16 | +0,13 | −0,02 |
| T08 | Repetición de trigramas | −0,02 | −0,10 | +0,12 |
| R01 | Promesas de apertura | 0 (constante) | 0 (constante) | 0 (constante) |
| R02 | Señales de progreso | −0,03 | +0,01 | −0,01 |
| R03 | Preparación del pago final | +0,05 | −0,01 | −0,02 |
| R04 | Ciclos 'si, pero' | +0,04 | −0,01 | −0,01 |
| R05 | Ciclos 'no, y además' | −0,04 | +0,26 | −0,22 |
| R09 | Proactividad del protagonista | +0,09 | −0,19 | +0,12 |
| R16 | Soluciones preparadas | +0,05 | −0,01 | −0,02 |
| R18 | Límites del mundo | 0 (constante) | 0 (constante) | 0 (constante) |
| R23 | Escenas con cambio | +0,05 | −0,01 | −0,02 |
| R24 | Decisiones con coste | 0 (constante) | 0 (constante) | 0 (constante) |
| X02 | Cuota del personaje más presente | −0,16 | +0,25 | −0,15 |
| X03 | Reparto de la participación | +0,04 | −0,11 | +0,10 |
| X06 | Escenas con conflicto | −0,04 | +0,01 | +0,02 |
| X10 | Mentiras | −0,003 | +0,09 | −0,06 |
| X13 | Secretos revelados | −0,06 | +0,17 | −0,10 |
| X14 | Complicaciones | +0,05 | −0,04 | +0,01 |
| X15 | Giros | +0,03 | +0,05 | −0,05 |
| X16 | Eventos azarosos o externos | +0,05 | −0,10 | +0,05 |
| X17 | Usos de objetos | −0,05 | −0,05 | +0,05 |
| X20 | Contradicciones | 0 (constante) | 0 (constante) | 0 (constante) |
| X29 | Reparto del diálogo | +0,06 | −0,07 | +0,04 |

**Colinealidad** (igual en los tres criterios, porque entrenan con las mismas 6 historias):

- R01, R18, R24 y X20 son constantes en las 6 historias; su peso es 0 por construcción.
- 10 pares con |r| ≥ 0,8: R03, R16 y R23 entre sí con r = 1,0 (sus pesos iguales son el reparto de
  la L2, no tres efectos iguales); R04–X14 0,97; X10–X13 0,97; X14–X29 −0,88; R03, R16 y R23 con
  X06 0,88; R04–X29 −0,83.
- El número de condición es nulo: la matriz es singular (6 historias frente a 20 rasgos que
  varían, rango 5 como mucho). Solo la combinación de pesos está determinada; un peso suelto no se
  interpreta. Que H02 tenga casi los signos opuestos de H01 y H03 describe este ajuste, no un
  hallazgo.

**Perturbaciones.** Diferencia de la puntuación lineal (perturbada − original), sin normalizar; como
referencia, la desviación de las puntuaciones de las 6 historias (`score_scale`) es 0,47 en H01,
0,85 en H02 y 0,57 en H03.

| Caso | H01 | H02 | H03 |
|---|---|---|---|
| H1 barajada | −0,79 | +1,59 | −1,12 |
| H1 sin desenlace | −0,19 | −0,26 | +0,23 |
| H2 barajada | +0,11 | −0,40 | +0,28 |
| H2 sin desenlace | +0,07 | −0,38 | +0,28 |
| H3 barajada | −0,47 | +0,20 | −0,00 |
| H4 barajada | +0,35 | −0,42 | +0,28 |
| H4 sin desenlace | +0,10 | −0,10 | +0,09 |
| H5 barajada | −0,24 | −0,58 | +0,46 |
| H5 sin desenlace | +0,26 | −0,71 | +0,39 |
| H6 barajada | +0,64 | +0,25 | −0,37 |
| H6 sin desenlace | +0,87 | +0,22 | −0,51 |

La puntuación baja en 4 de 11 casos en creatividad, en 7 de 11 en personajes y en 4 de 11 en trama;
en ninguno bajan los tres a la vez. El descenso de H3 barajada en trama (−0,0009) es nulo en la
práctica. No se exige que toda perturbación empeore todos los criterios: se publican los cambios.

**Limitaciones**, además de las dos genéricas de `juez.json` (muestra pequeña; preferencias que
dependen de premisas y lectores):

- **Votos.** Hoja de orden fijo, transcripción a mano sin segundo transcriptor, acuerdo entre
  lectores cercano al azar y grafo partido en dos obras ([Piloto 7.22](#piloto-722-votos-transcritos)).
- **Rango.** 6 historias para 24 rasgos: pesos no identificables uno a uno y validación con 6 y 2
  pliegues de 8 a 16 votos de entrenamiento.
- **X15 de H3** sale de un intento archivado del mismo protocolo y se validó contra otra
  segmentación en escenas (`decisions.md` §2, P07.6).
- **Perturbaciones.** 11 de 12: falta H3 sin desenlace (R03 sin medir). Cada perturbación se volvió
  a extraer con `flash-lite`, y 8 de los núcleo conservados no cumplen el test-retest (P04.8 y
  P04.9): cada diferencia mezcla el efecto de la perturbación con el ruido del extractor, y aquí no
  se pueden separar.
- **Sin reajuste.** El juez se entrenó una vez, tal como dice P07.1; no se quitaron rasgos ni se
  cambió la regularización tras ver estos resultados.

## 7. Ranking del corpus y análisis de las mejores

El juez puntúa todas las historias completadas de `Stories/`: el corpus histórico más la matriz
(ficha EXP-8).

- Los tres rankings son principales. J04 es auxiliar: media con pesos iguales y normalización
  fijada al entrenar, nunca reajustada sobre el corpus nuevo.
- El análisis cualitativo lee las 10 mejores y mira qué tienen y qué no: sus rasgos, su
  configuración y su proceso.
- Los runs de versiones que no se comparan se marcan. Por ejemplo, las funciones 7.0 y 7.1 frente
  a las de 7.2 en adelante.

### Ranking del corpus (P08, 2026-11-03)

Medido el 2026-11-03 (P08.5), sin llamadas al modelo, con el juez congelado de P07.7 (`juez.json`,
SHA-256 `50472656…6df3e1d93`, `data_hash` `072c1c0d…3d7690b92`, protocolo de extracción
`gemini-3.5-flash-lite` / `evidence-2`):

```powershell
asg-rank Evaluations/estudio-piloto-722/juez.json Stories `
  --study Evaluations/estudio-piloto-722/study.sqlite3 `
  --output Evaluations/ranking/ranking-2026-11-03.json
```

Salidas (ignoradas por Git, como `Evaluations/`): `ranking-2026-11-03.json` y la hoja
`ranking-2026-11-03.md`, con «Fortalezas (Josue)» y «Debilidades (Josue)» vacías. **Es un ranking
exploratorio y no mide calidad:** el juez no generaliza ([§6](#resultado-del-juez-piloto-722): fuera de
muestra queda por debajo del azar y de la longitud sola), así que el orden describe lo que premia
este ajuste, no las mejores historias.

**Cobertura.** `asg-corpus Stories` cuenta 346 runs y 130 elegibles; los otros 216 no lo son
(135 de un generador anterior a Stagecraft 7, 73 sin completar y 8 de formato fuera de la prosa
del estudio). `asg-rank` solo ve los 277 runs que tienen `story.md`: los 69 sin completar que no
la tienen no aparecen en su informe. De esos 277, se ordenaron **9** (≈ 7 % de las 130
elegibles) y las otras 121 elegibles salieron con su razón, medidas el 2026-11-03 uniendo
`excluded` con `identity` de cada `features/features.json`:

| Razón de salida (elegibles) | Runs |
|---|---|
| Extracción ausente u obsoleta: 74 sin ninguna extracción y 5 de 3.5 con el catálogo anterior (`9de34b17…`) | 79 |
| Extracción incompleta (algún rasgo núcleo sin medir): 34 de `gemini-3.1-flash-lite` y 7 de `gemini-3.5-flash-lite` | 41 |
| Protocolo de extracción distinto: 1 completa de `gemini-3.1-flash-lite` | 1 |

`extraction_compatible` no mira el modelo, así que una extracción de 3.1 incompleta sale por
«incompleta» y solo la completa llega a la comprobación del protocolo.

Las diez primeras son **tres**, no diez: de las 9 ordenadas, 6 son las del entrenamiento del juez
(`training`, dentro de muestra, no entran en las diez) y quedan 3. La regla de las diez no se
cambió ni se completó con otras (`decisions.md` §2, «Corrección y cierre de P08.4»).

**Qué se ordenó.** Solo textos con extracción núcleo completa de `gemini-3.5-flash-lite`, todos del
generador 7.22 (pipeline 7.22): 5 simulados, 1 narrativo y 3 líneas base. No hay textos 7.0 a 7.19 ni
guiones. La extracción con `gemini-3.1-flash-lite` de 35 textos (lote 2) no entra:
el protocolo del juez fija el modelo (T8), así que esas historias salen del ranking aunque su
extracción sea completa. Marcas: `training` en 6; `version-no-comparable` en ninguna;
`premisa-no-vista` en ninguna.

**Puestos** (1 = primero; 9 ordenadas). El orden por longitud (T01, las más largas primero) va al
lado:

| Historia | Formato | Marca | H01 | H02 | H03 | Combinado | Longitud |
|---|---|---|---|---|---|---|---|
| `20261030-130819-el-misterio-del-faro` | simulado | — | 3 | 2 | 9 | 4 | 4 |
| `01-fantasia-canonica-1` | línea base | — | 5 | 6 | 3 | 6 | 9 |
| `20261030-130258-el-misterio-del-faro` | simulado | — | 8 | 5 | 4 | 7 | 3 |
| `20261030-221208-la-sombra-del-volcan` | simulado | training | 2 | 9 | 1 | 1 | 8 |
| `01-fantasia-canonica-2` | línea base | training | 1 | 7 | 5 | 2 | 7 |
| `20261030-140119-el-misterio-del-faro` | simulado | training | 4 | 8 | 2 | 3 | 5 |
| `20261028-192554-el-faro-de-la-habitacion-cerrada` | narrativo | training | 6 | 1 | 8 | 5 | 2 |
| `20261030-234947-la-promesa-del-volcan` | simulado | training | 7 | 3 | 7 | 8 | 6 |
| `03-ultima-luz-del-faro-2` | línea base | training | 9 | 4 | 6 | 9 | 1 |

- **Las tres fuera del entrenamiento** salen en este orden del combinado: `…130819-el-misterio-del-faro`
  (puesto 4 de 9), `01-fantasia-canonica-1` (6) y `…130258-el-misterio-del-faro` (7). Por longitud
  están en los puestos 4, 9 y 3. Con solo tres textos fuera del entrenamiento, comparar «las diez
  frente a las diez más largas» no tiene sentido: cualquier orden de tres coincide en los mismos
  tres.
- **Líneas base.** Hay tres entre las 9: una fuera del entrenamiento (`01-fantasia-canonica-1`,
  combinado 6, la más corta) y dos de entrenamiento (combinado 2 y 9). El orden de 9 textos no
  permite decir si las líneas base quedan por encima o por debajo de lo generado.
- **Entrenamiento.** Los 6 del piloto ocupan los puestos 1, 2, 3, 5, 8 y 9 del combinado: sus
  puntuaciones son de dentro de muestra, así que ese orden no se interpreta.
- Los tres rankings por criterio (H01, H02, H03) y el combinado salen enteros en el JSON.

**Qué tienen y qué no** (`top_ten_profile`, medianas de los 24 núcleo entre las tres, el resto de
las ordenadas y las 9). Es descriptivo y n es 1 a 3 por rasgo: sirve para leer las hojas, no para
comparar. Las medianas de las tres son mayores que las del resto en mentiras (X10: 2 frente a 0),
complicaciones (X14: 3 frente a 1) y usos de objetos (X17: 8,4 frente a 3,8). Rasgos sin medir en
alguna de las tres (R03, R04, R05, R16, X10 y X20, ver la hoja) bajan n a 1 o 2. La tabla
completa está en la hoja `.md`.

**Limitaciones.**

- **Juez exploratorio** de 2 familias y 5 lectores que no generaliza: el número no es calidad.
- **Cobertura parcial:** 9 de 130 elegibles. Lo no extraído, o extraído sin completar, sale del
  ranking: sesgo hacia los textos que el extractor mide bien (y, por la cuota, hacia los de 7.22).
  Las 35 extracciones con `gemini-3.1-flash-lite` (lote 2) quedan fuera del ranking aunque una
  esté completa: el protocolo del juez fija el modelo (T8) y 3.1 no está validado.
- **Extractor con rasgos que no pasan el test-retest** (P04.8 y P04.9): las diferencias de rasgos
  entre textos mezclan el texto con el ruido de la extracción.
- **Premisas no vistas:** ninguna de las tres sale de una obra distinta de 01 y 03.
- **Longitud y versiones:** todas son de 7.22, así que no se compara entre versiones, y la
  longitud sola le ganó al juez en P07.7.
- **N = 3 con un criterio fijo:** no se puede decir que las diez primeras sean una muestra de lo
  que premia el juez; son las tres únicas que cumplen las condiciones.

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

### Exclusiones del corpus (inventario del 2026-10-28)

Alcance: `asg-corpus Stories`, 331 runs, 116 elegibles. Salida en
`Evaluations/corpus/inventario-2026-10-28.json` (local, `Evaluations/` está ignorado por Git).
Excluidos: 135 por generador anterior a Stagecraft 7, 72 por run no completado y 8 por formato
fuera del estudio en prosa. Nada se borró ni se editó a mano.

| Grupo | Anomalías (recuento) | Decisión |
|---|---|---|
| Runs anteriores a Stagecraft 7 | `sin_version_de_pipeline`, `sin_generator_version`, `formato_inferido` y 2 `tmp_suelto` (`.story.mp3.*.tmp` en `Top-Down/20260901-020145` y `20260908-020751`) | Limitación aceptada: ya quedan fuera del ranking (P03.1); no se recuperan. |
| Runs no completados de Top-Down | Las mismas tres anomalías de versión y formato | Excluidos con la razón «Run no completado». |
| `Top-Down/20260911-173150-las-cenizas-del-juramento` | `failed_con_story` (PermissionError, pipeline 6.0) | Limitación aceptada: anterior a Stagecraft 7; no se recupera. |
| Seis runs `running` de `Stories/Stagecraft` sin `story.md` (`20261002-150119`, `20261011-234543`, `20261013-125004`, `20261016-141948`, `20261022-142004`, `20261022-205605`) | `running_atascado` | Descartados con `asg-recover --discard` (`failed`, código `RUN_INTERRUPTED`); el `.pipeline_manifest.json.*.tmp` de `20261022-142004` no se borró. |
| `Stagecraft/20261011-225020-la-carta-del-faro` (7.10) | `running_atascado` y `tmp_suelto` (`.story.mp3.*.tmp`) | Sin cerrar y excluido como «Run no completado»: lo dejó a medias el proceso. Limitación aceptada; `--close` queda como opción si se revisa su `story.md`. |
| `Bottom-Up/Escape-Room/experiments` y `Top-Down/comparacion-densidad-borrador-final-v2.0.4.html` | `no_es_run` | Fuera del inventario de runs; no se borran. |

Tras el descarte quedan 71 runs `failed` y 1 `running`; en `Stagecraft/` siguen anotadas tres
anomalías: las dos de `la-carta-del-faro` y el `.tmp` de `20261022-142004`.

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

# Cobertura del catálogo de rasgos

Auditoría de [rasgos.csv](rasgos.csv) contra T3 (`planning/decisions.md` §1): cada ejemplo del
audio del tutor y cada dimensión de su rúbrica tiene un rasgo, o una razón escrita para no
tenerlo. Hecha el 2026-10-28 (P04.1) leyendo solo el catálogo, la metodología, la rúbrica
(`docs/sanderson-craft.pdf` §3.8) y la transcripción [00:22–01:56]; no se ha leído ninguna
extracción ni historia. Este documento **no propone arreglos**: eso es P04.2.

Lectura de las columnas: «núcleo» es la prioridad del CSV; «juez» es su `uso`. Los 27 rasgos que
entran al juez son los `T`, `R` y `X` núcleo (T01, T06, T08, 12 de la capa R, 12 de la X). Otros
diez rasgos llevan también `núcleo` pero no son del juez: P02, P09, P19, P24, P26 (análisis
horizontal), K01, K02 (coste) y H01–H03 (objetivo humano).

## 1. Los 9 ejemplos del audio

| # | Ejemplo del tutor [mm:ss] | Rasgos | Estado | Observación |
|---|---|---|---|---|
| 1 | Consistencia [00:34] | X20 contradicciones; X19 objetos incoherentes; X28 fugas de conocimiento; X27 violaciones del punto de vista | X20 núcleo; X19, X27, X28 secundarios | «Consistencia» es un concepto amplio; el catálogo lo parte en cuatro recuentos. Solo X20 llega al juez. |
| 2 | Porcentaje en que participa cada personaje [00:34] | X02 cuota del más presente (desglose por personaje); X03 reparto; X04 reparto activo; X01 personajes con nombre | X02 y X03 núcleo; X01 y X04 secundarios | Fiel al audio: la participación se mide en escenas y se publica por personaje. |
| 3 | Escenas con algún conflicto [00:34] | X06 escenas con conflicto; X07 tipos de conflicto; X05 escenas (denominador) | X06 núcleo; X05 y X07 secundarios | X05 es secundario pero X02, X03, X06 y R23 dependen de su segmentación en escenas. |
| 4 | Veces que alguien usa un objeto [00:53] | X17 usos de objetos; X18 objetos con función; X19 objetos incoherentes | X17 núcleo; X18 y X19 secundarios | Directo. |
| 5 | Veces que alguien participa en un diálogo [00:53] | X08 réplicas (por hablante); T06 proporción de diálogo | Ambos fuera del juez en su parte por personaje: X08 secundario; T06 núcleo pero global | El recuento por hablante que pide el audio (X08) no entra al juez; T06 sí, pero es una proporción del texto entero, no una participación por personaje. |
| 6 | Réplicas que se desvían de la personalidad [01:03] | X09 réplicas fuera de personalidad | Núcleo | Directo. Ver §3: el rasgo depende de un juicio de coherencia. |
| 7 | Personajes que mienten [01:12] | X11 personajes que mienten; X10 mentiras; X12 mentiras descubiertas | X10 núcleo; X11 y X12 secundarios | Lo que el audio nombra literalmente (personajes que mienten) es X11, secundario; X10 cuenta mentiras, no personajes. |
| 8 | Cosas complicadas [01:12] | X14 complicaciones; X15 giros | Ambos núcleo | La transcripción es automática y «cosas complicadas» es ambiguo; el catálogo lo lee como obstáculos nuevos y cambios de sentido. Lectura no confirmada con el tutor. |
| 9 | Eventos aleatorios [01:12] | X16 eventos azarosos o externos | Núcleo | Directo; en simulado se contrasta con los `stage_events` (P21). |

## 2. Las 20 dimensiones de la rúbrica

El ítem 16 (canon) queda **fuera por ser de series/universo** (la propia rúbrica lo declara «series/universe
work only»). Las 19 restantes:

| Ítem | Dimensión | Rasgos | Estado | Observación |
|---|---|---|---|---|
| 1 | Promesas de apertura | R01 | núcleo | Se pasa de 1–5 a recuento de promesas con cita. |
| 2 | Señales de progreso | R02 | núcleo | Idem, por 1000 palabras. |
| 3 | Calidad del pago | R03; X24 preguntas pagadas; R07/R08 (hilo dominante) | R03 y X24 núcleo; R07/R08 secundarios | Cubre «responde la promesa» y «inevitable» (preparaciones). La mitad «sorprendente» no tiene rasgo propio; ver §4. |
| 4 | Ciclos intento-fracaso | R04 sí-pero; R05 no-y-además; R06 intentos planos | R04 y R05 núcleo; R06 secundario | Directo. La rúbrica lo cuenta entre los tres ítems más difíciles. |
| 5 | Claridad del hilo MICE | R07 hilo dominante; R08 hilo cerrado | Secundarios | Categoría y binario: no entran a una regresión sin codificarlos. |
| 6 | Perfil de sliders | R09 proactividad; R10 competencia; R11 simpatía | R09 núcleo; R10 y R11 secundarios | La rúbrica puntúa 1–5; aquí son tres recuentos. |
| 7 | Deseo frente a necesidad | R12 | núcleo | Suma de tres comprobaciones sí/no con cita, no un recuento de sucesos. |
| 8 | La mentira / creencia falsa | R13 | secundario | Categoría. La rúbrica lo cuenta entre los tres ítems más difíciles y no llega al juez. |
| 9 | Distinción de voces | R14 | secundario | Medida aparte (MED-7, sin LLM sobre el recuento). |
| 10 | Defecto con coste | R15 | núcleo | Directo. |
| 11 | Primera Ley (soluciones ganadas) | R16 preparadas; R17 sin preparar | Ambos núcleo | Directo. |
| 12 | Segunda Ley (límites sobre poderes) | R18 límites del mundo | secundario | Se cuentan los límites; la comparación «más interesantes que los poderes» no se mide (es juicio, T2). |
| 13 | Tercera Ley (un cambio extrapolado) | R19 alcance del elemento especulativo | secundario | «No aplica» en historias realistas; no es 0. |
| 14 | Solidez del iceberg | R20 iceberg | secundario | Se pasa de 1–5 a detalles con cita por 1000 palabras. |
| 15 | Trama A/B entrelazada | R21 | secundario | Binario. Otro de los tres ítems más difíciles, fuera del juez. |
| 16 | Integración de canon | — | **fuera** | Solo para series/universos; el generador produce obras sueltas. |
| 17 | Imagen de apertura frente a cierre | R22 | secundario | Binario con dos citas. |
| 18 | Impulso narrativo | R23 escenas sin cambio | núcleo | Se pasa de 1–5 a recuento de escenas que no cambian nada. |
| 19 | Ganarse lo que está en juego | R24 decisiones con coste | núcleo | Directo. |
| 20 | Precisión sobre exceso | R25 pasajes sobrantes | secundario | Directo. |

**Resultado.** Los 9 ejemplos del audio y las 19 dimensiones aplicables tienen al menos un
rasgo. Ninguno carece de rasgo; lo que hay son huecos parciales y rasgos que quedan fuera del
juez (§4).

## 3. Los 27 rasgos que entran al juez, uno a uno

Criterios:

- **Recuento con cita (T2)**: ¿cuenta sucesos observables y los respalda con citas literales?
  «Código» = cifra calculada sobre `story.md`, sin extractor ni cita.
- **Lectura como juicio**: ¿para contarlo hay que decidir si algo es *bueno*, *claro* o
  *adecuado*? «No» / «Riesgo bajo» / «Riesgo medio» / «Riesgo alto», con el motivo. El riesgo es
  mío (esta tarea no miró extracciones); lo valida la revisión humana de P04.
- **Validable**: valor de `validable_contra`. Si el log es un techo, solo vale en simulados
  (METODOLOGIA §3).

| ID | Rasgo | Recuento con cita (T2) | Lectura como juicio | `validable_contra` |
|---|---|---|---|---|
| T01 | Palabras | Código | No | No tiene (código) |
| T06 | Proporción de diálogo | Código | No | Sí, indirecto: P15, P34 miden otra cosa (guion, supervivencia) |
| T08 | Repetición de trigramas | Código | No | Sí, indirecto: P28, P29 (repetición del habla y de acciones) |
| R01 | Promesas de apertura | Sí, con cita | Riesgo medio: «claras» obliga a decidir qué es una promesa clara | Sí: P08, pero cuenta las del contrato del plan, no las del texto |
| R02 | Señales de progreso | Sí, con cita | Riesgo medio: «decisión que no podía tomar al inicio» es inferencia | No |
| R03 | Preparación del pago final | Sí, con cita | Riesgo medio: vale 0 «si el final no responde la promesa», lo que exige juzgar si responde | Sí: P09 |
| R04 | Ciclos «sí, pero» | Sí, con cita | Riesgo medio: «coste nuevo» es interpretable | No |
| R05 | Ciclos «no, y además» | Sí, con cita | Riesgo medio: «empeora la situación» es interpretable | No |
| R09 | Proactividad del protagonista | Sí, con cita | Riesgo medio: «por su cuenta» exige inferir la causa de cada acción | No |
| R12 | Deseo frente a necesidad | Parcial: suma 0–3 de tres comprobaciones con cita, no un recuento de sucesos | **Riesgo alto**: «necesidad inconsciente» y «tiran en direcciones opuestas» son lectura del personaje | No |
| R15 | Defecto con coste | Sí, con cita | **Riesgo alto**: hay que decidir qué es un defecto «cara oscura de una virtud» y que «le impide avanzar» | No |
| R16 | Soluciones preparadas | Sí, con dos citas (regla vista antes y uso) | Riesgo bajo: verificable por orden en el texto | No |
| R17 | Soluciones sin preparar | Sí, con cita | Riesgo medio: es la negación de R16; «justo cuando hace falta» es juicio | No |
| R23 | Escenas sin cambio | Parcial: cuenta una *ausencia* (nada cambia), difícil de citar | **Riesgo alto**: «no aporta» roza lo que R25 llama pasaje sobrante; depende de la segmentación X05 | Sí, indirecto: P19, P20 (beats cumplidos y forzados) |
| R24 | Decisiones con coste | Sí, con cita | Riesgo medio: «le cuestan algo real» | No |
| X02 | Cuota del personaje más presente | Sí (escenas por personaje) | No; sí depende de la segmentación en escenas (X05) | Sí: P35 (aún `por_construir` en el CSV), `character_metrics` |
| X03 | Reparto de la participación | Sí (derivado de la presencia por escena) | No; misma dependencia de X05 | Sí: P35, P18 (`por_construir`) |
| X06 | Escenas con conflicto | Sí, con cita | Riesgo medio: «objetivos enfrentados visibles» es una frontera difusa | No |
| X09 | Réplicas fuera de personalidad | Sí, con dos citas (lo establecido y la réplica) | **Riesgo alto**: exige juzgar coherencia de carácter; la nota dice «el signo lo decide el juez» (puede ser incoherencia o giro) | No |
| X10 | Mentiras | Sí, con cita | Riesgo bajo | Sí: P37 (`por_construir`) |
| X13 | Secretos revelados | Sí, con cita | Riesgo bajo | Sí: P36 |
| X14 | Complicaciones | Sí, con cita | Riesgo medio: se solapa con R05 y X15 | No |
| X15 | Giros | Sí, con cita | Riesgo medio: «algo que se daba por cierto» depende de qué creía el lector; se solapa con X13 | No |
| X16 | Eventos azarosos o externos | Sí, con cita | Riesgo bajo | Sí: P21 (los `stage_events` los decide un director, no el azar) |
| X17 | Usos de objetos | Sí, con cita | No | Sí: P39 |
| X20 | Contradicciones | Sí, con dos citas | Riesgo bajo en la definición; poca cobertura de los detectores LLM (Ahuja et al. 2025) | No; revisión manual de una muestra (METODOLOGIA §3) |
| X24 | Preguntas pagadas | Sí: cociente entre dos recuentos con cita | Riesgo medio: el denominador es X23, **secundario**, y con pocas preguntas el cociente es inestable | Sí: P09, P08 |

Recuento: 3 de código (T) y 24 del extractor. De los 24: 4 con riesgo alto (R12, R15, R23, X09),
12 con riesgo medio, 5 con riesgo bajo y 3 sin juicio (X02, X03, X17); 13 no tienen
`validable_contra` (R02, R04, R05, R09, R12, R15, R16, R17, R24, X06, X14, X15, X20).

## 4. Lagunas y núcleo dudosos

### Lagunas (cobertura que falta o es parcial)

1. **«Sorprendente» del ítem 3.** R03 cubre «inevitable» (preparaciones cosechadas); nada mide
   «sorprendente». X15 (giros) es lo más cercano pero cuenta giros, no si el pago sorprende.
2. **Tres ítems «difíciles» fuera del juez.** La rúbrica señala 4, 8 y 15 como los más
   difíciles de pasar. El 4 llega al juez (R04, R05); el 8 (R13) y el 15 (R21) son secundarios, y
   ambos son categoría o binario.
3. **Bloques enteros sin núcleo.** Del bloque III (mundo), solo el ítem 11 (R16, R17) es núcleo;
   12, 13 y 14 (R18, R19, R20) son secundarios. En el bloque IV (integración), los ítems 15 y 17
   (R21, R22) también lo son. En voz y estilo, R14 y los T de estilo salvo T08 son secundarios.
4. **El criterio «creatividad» casi no tiene núcleo.** De los 27 del juez, `criterio_humano` es
   «trama» en 15, «personajes» en 9 y «creatividad» en solo 2 (T08, X15); T01 no tiene criterio.
   El juez predice tres números (J01–J03), uno por criterio.
5. **Participación por hablante fuera del juez.** El ejemplo 5 del audio (veces que alguien
   participa en un diálogo) lo cubre X08, secundario. T06 es una proporción global.
6. **«Personajes que mienten» fuera del juez.** El ejemplo 7 nombra personajes; el rasgo que lo
   cuenta (X11) es secundario. X10 cuenta mentiras, no personajes.
7. **«Cosas complicadas» sin confirmar.** La lectura (X14, X15) es del catálogo; el audio es
   una transcripción automática y no se ha comprobado con el tutor.
8. **Dependencias de secundarios.** X05 (escenas) es denominador de X02, X03, X06 y R23; X23
   (preguntas abiertas) lo es de X24. Los núcleo dependen de rasgos que no entran al juez.
9. **Capas P y K marcadas «núcleo».** P02, P09, P19, P24, P26, K01 y K02 llevan `núcleo` pero
   su `uso` es horizontal o coste; la metodología dice «27 núcleo» y solo cuadra contando
   `uso = juez`. Los H01–H03 son el objetivo humano.
10. **Estado de P35 y P18, P37.** El CSV los da por `por_construir`; P35 ya lo calcula
    `feature_report._simulation_counts` (anotado para P04.4). Tres núcleo se validan contra ellos.

### Núcleo dudosos (candidatos a revisar en P04.2)

- **Riesgo alto de leerse como juicio de calidad:** R12 (deseo/necesidad), R15 (defecto con
  coste), R23 (escenas sin cambio) y X09 (réplicas fuera de personalidad).
- **Solapes que comparten señal:** R05 / X14 / X15 (complicaciones, giros y «no, y además»);
  R16 / R17 (son complementarios y se esperan con signos opuestos); X13 / X15 (secretos y
  giros). Cuentan casi lo mismo y pueden inflar la colinealidad de la regresión.
- **Sin `validable_contra`:** 13 de los 24 del extractor, entre ellos tres de los cuatro de
  riesgo alto (R12, R15, X09); X20 solo tiene la revisión manual.
- **Cociente con denominador secundario:** X24 (denominador X23).

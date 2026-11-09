# Datos consolidados para revisar la tesis

Fecha de revisión: **7 de noviembre de 2026**. Autor de las declaraciones: **Josue**.

Este bloque completa el documento de trabajo sin asignar resultados ausentes. Al final se
conserva íntegro el cuestionario recibido. Las aclaraciones posteriores prevalecen sobre respuestas
ambiguas del cuestionario: diez textos distintos, método de cada texto oculto y 122 historias
como corpus para ordenar. El «no» original sobre el desconocimiento del método no significa que
los lectores vieran las configuraciones de A y B.

## Fuentes y significado de los datos

- **Declaración del autor:** cuestionario y aclaraciones de esta conversación, confirmadas al aprobar el plan.
- **Registro:** archivos existentes; sus huellas están en [revision.json](../tablas/revision.json).
- **Cálculo:** operación explícita sobre declaraciones o registros. No implica que se hayan recuperado votos.
- **No consta en los registros disponibles:** no puede completarse sin información adicional; nunca significa cero.

No se modificaron las bases, las historias, los votos ni los informes de investigación.
Los identificadores L1–L8 de esta revisión no se asignan a los lectores del piloto antiguo.

## 1. Generador y período

La formulación será **«Se estableció una configuración de referencia para los experimentos,
mientras continuaba el desarrollo del generador»**. La referencia registrada es Stagecraft 7.22.0,
contrato 7.22, etiqueta `generator-frozen`, del 28 de octubre de 2026. El nombre técnico de la
etiqueta se conserva. No se cambia el significado de congelar un plan o una huella del conjunto.
Las versiones anteriores se identifican al describir cada validación.

## 2. Participantes y procedimiento

Participaron **8 graduados de Ciencia de la Computación**, incluido el autor, seleccionados por
conveniencia entre colegas de la facultad. Las lecturas transcurrieron durante octubre de 2026
hasta el 1 de noviembre, según el autor; no se atribuye una fecha exacta a cada lector.

| Lector | Formación | Frecuencia de lectura | Conocía el sistema | Autor |
|---|---|---|---|---|
| L1 | Ciencia de la Computación | Alta | Sí | Sí |
| L2 | Ciencia de la Computación | Alta | No | No |
| L3 | Ciencia de la Computación | Alta | No | No |
| L4 | Ciencia de la Computación | Media | No | No |
| L5 | Ciencia de la Computación | Media | No | No |
| L6 | Ciencia de la Computación | Media | No | No |
| L7 | Ciencia de la Computación | Baja | No | No |
| L8 | Ciencia de la Computación | Baja | No | No |

Son tres frecuencias altas, tres medias y dos bajas (3/8, 3/8 y 2/8). No se asignan libros por mes
ni edades desconocidas. La diversidad declarada es de hábitos, no de formación.

- Medio: bot de Telegram. Fuente: autor; interfaz contrastada con `apps/telegram/src/asg_telegram/voting.py`.
- Método de cada texto oculto. El autor conoce el sistema; el resto declara no conocerlo.
- Mismos cinco pares, en el mismo orden, con diez textos distintos.
- Posición A/B: no consta si fue fija o alternada. La respuesta «sí» a una pregunta con dos alternativas no lo resuelve.
- Opciones reales: **Historia A / Historia B / No puedo decidir**. Esta última se guarda como `abstain`.
- No se distinguió empate de abstención; no se transforma `abstain` en empate Bradley-Terry.
- Todos completaron las preguntas, según el autor. Registro/transcripción manual a partir del bot.
- 8 × 5 = **40 comparaciones lector-par**; 40 × 3 = **120 respuestas declaradas**.
- Son 40 respuestas por criterio, incluidas posibles abstenciones, no necesariamente 40 votos decididos.
- Las 120 respuestas no son observaciones independientes. Sin el autor quedarían 7 participantes,
  35 comparaciones y 105 respuestas declaradas; no hay distribución A/B recuperada para ese subconjunto.

Preguntas recuperadas de `packages/evaluation/planilla/criterios_humanos.csv`:

- De estas dos historias, ¿cuál tiene más creatividad?
- De estas dos historias, ¿en cuál están los personajes mejor desarrollados?
- De estas dos historias, ¿en cuál está la trama más interesante?

## 3. Historias y pares del estudio actualizado

No se ha localizado la correspondencia de los diez textos con sus ejecuciones. No se seleccionan
arbitrariamente diez historias del corpus. T01–T10 y P1–P5 son casillas de identificación pendientes,
no identificadores de ejecución confirmados. Que haya diez textos y cinco pares no informa qué texto
ocupó A o B ni qué par contrasta cada hipótesis.

| Casilla | Título/run | Formato | Premisa |
|---|---|---|---|
| T01 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |
| T02 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |
| T03 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |
| T04 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |
| T05 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |
| T06 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |
| T07 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |
| T08 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |
| T09 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |
| T10 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |

| Par | Historia A | Historia B | Contraste | Mismo plan |
|---|---|---|---|---|
| P1 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |
| P2 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |
| P3 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |
| P4 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |
| P5 | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles | No consta en los registros disponibles |

## 4. Respuestas individuales

**ND = no consta en los registros disponibles.** No significa abstención ni respuesta dudosa.
Cada celda corresponde a creatividad/personajes/trama. El perfil de lectura no permite deducir votos.

| Lector | P1 | P2 | P3 | P4 | P5 |
|---|---|---|---|---|---|
| L1 | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND |
| L2 | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND |
| L3 | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND |
| L4 | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND |
| L5 | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND |
| L6 | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND |
| L7 | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND |
| L8 | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND | ND/ND/ND |

Las bases revisadas no contienen la votación final de ocho participantes. El piloto en
`Evaluations/estudio-piloto-722/` conserva 5 participantes, 6 historias y 69 respuestas; sus notas
excluyen al autor. Es otro conjunto y no se usa para rellenar esta tabla. Las bases de cola de
Telegram contienen encargos de generación, no los votos faltantes. Las votaciones identificadas
como simuladas con agentes LLM no cuentan como lectores humanos.

## 5. Lecturas adicionales

El autor confirma lecturas y validaciones adicionales por integrantes de los mismos ocho lectores,
sin personas nuevas. Su fecha, identidad de participantes, historias, pares, resultados y uso en
el entrenamiento **no constan en los registros disponibles**. Se mantienen fuera de las 120 respuestas.

Las sesiones conservadas `p021-narracion` y `p022-topdown`, del 27 de octubre, identifican al autor
y cinco y cuatro pares, respectivamente. Al cruzar la elección X/Y con `generation_options.json`:
- Narración: 2 elecciones del brazo resumido, 2 del brazo con selección/editor/ejemplos y 1 «ninguno».
- Escritura: 3 elecciones del brazo sin mecanismos y 1 con ellos.
Estas sesiones históricas no documentan por sí solas las lecturas adicionales ni se suman a la
votación final. Sus historias no rellenan los diez textos finales.

## 6. Análisis horizontal

Unidad: **ejecución de una configuración para una obra y repetición**. Los rasgos y las
comparaciones se contabilizan por separado. El conjunto final informado por el autor tiene 24
unidades. El manifiesto permite identificar 24 ejecuciones completadas: 5 bases simuladas, 9 líneas
base, 2 narrativas desde el plan y 8 variantes de tono/visión. Son 14 nuevas, más 9 líneas base y
1 base simulada preexistentes; así se explica la cifra anterior de 14/35 sin confundir denominadores.

Fechas: 28 y 30 de octubre de 2026; el manifiesto se actualizó el 31 en UTC. El diseño histórico
conservado tiene 45 posiciones (24 completadas, 1 fallida, 20 pendientes). La declaración «24
previstas» se registra como alcance final comunicado, no como modificación de ese manifiesto.

Cada ejecución identificada y su extracción están en [horizontal_revision.csv](../tablas/horizontal_revision.csv).
La comprobación del 7 de noviembre busca el texto exacto por su hash en los `features.json` de los
runs y los JSON actuales de `Evaluations/*/features/`, sin usar intentos históricos o perturbaciones.
Exige catálogo vigente, `evidence-2`, versión 3, modelo `gemini-3.5-flash-lite` y todos los rasgos
núcleo medidos o no aplicables. Resultado: **8 completas compatibles, 4 incompletas compatibles,
6 de otro protocolo y 6 sin archivo localizado**. No demuestra la declaración de 24 extracciones completas.

| Unidad | Run | Extracción localizada |
|---|---|---|
| M01/01/r1 | `Stories/Stagecraft/20261030-132707-la-sombra-del-volcan` | sin archivo localizado |
| M01/01/r2 | `Stories/Stagecraft/20261030-234947-la-promesa-del-volcan` | completa compatible |
| M01/03/r1 | `Stories/Stagecraft/20261028-192554-el-misterio-del-faro` | otro protocolo |
| M01/03/r2 | `Stories/Stagecraft/20261030-140119-el-misterio-del-faro` | completa compatible |
| M01/04/r1 | `Stories/Stagecraft/20261030-134427-la-ultima-funcion` | sin archivo localizado |
| M02/01/r1 | `Stories/Baseline/01-fantasia-canonica-1` | completa compatible |
| M02/01/r2 | `Stories/Baseline/01-fantasia-canonica-2` | completa compatible |
| M02/01/r3 | `Stories/Baseline/01-fantasia-canonica-3` | incompleta compatible |
| M02/03/r1 | `Stories/Baseline/03-ultima-luz-del-faro-1` | otro protocolo |
| M02/03/r2 | `Stories/Baseline/03-ultima-luz-del-faro-2` | completa compatible |
| M02/03/r3 | `Stories/Baseline/03-ultima-luz-del-faro-3` | otro protocolo |
| M02/04/r1 | `Stories/Baseline/04-cine-de-los-domingos-1` | otro protocolo |
| M02/04/r2 | `Stories/Baseline/04-cine-de-los-domingos-2` | otro protocolo |
| M02/04/r3 | `Stories/Baseline/04-cine-de-los-domingos-3` | otro protocolo |
| M03/01/r1 | `Stories/Stagecraft/20261030-221117-la-sombra-del-volcan` | sin archivo localizado |
| M03/03/r1 | `Stories/Stagecraft/20261030-130152-el-misterio-del-faro` | incompleta compatible |
| M04/01/r1 | `Stories/Stagecraft/20261030-221208-la-sombra-del-volcan` | completa compatible |
| M04/03/r1 | `Stories/Stagecraft/20261030-130258-el-misterio-del-faro` | completa compatible |
| M05/01/r1 | `Stories/Stagecraft/20261030-221305-la-sombra-del-volcan` | sin archivo localizado |
| M05/03/r1 | `Stories/Stagecraft/20261030-130544-el-misterio-del-faro` | incompleta compatible |
| M06/01/r1 | `Stories/Stagecraft/20261030-221441-la-sombra-del-volcan` | sin archivo localizado |
| M06/03/r1 | `Stories/Stagecraft/20261030-130704-el-misterio-del-faro` | incompleta compatible |
| M07/01/r1 | `Stories/Stagecraft/20261030-221541-la-sombra-del-volcan` | sin archivo localizado |
| M07/03/r1 | `Stories/Stagecraft/20261030-130819-el-misterio-del-faro` | completa compatible |

Resultados numéricos recuperados: el informe `Evaluations/horizontal/piloto-03/horizontal.csv`
compara T01, T06 y T08 sobre un par por variante de la obra 03. Se conserva en `piloto.csv/.tex`
con su alcance. No se extrapola al total de 24 unidades. El autor declara una medición favorable
del ruido; su valor, denominadores y archivo no constan en los registros disponibles.

## 7. Juez y corpus

- Rango comunicado por el autor: **0,50–0,65**.
- Fecha comunicada del análisis: **1 de noviembre de 2026**.
- Participación comunicada: **8 lectores**.
- **122 historias**: corpus destinado a ordenar, no tamaño de entrenamiento ni cobertura comprobada.
- Tamaño e identificadores del entrenamiento: no constan en los registros disponibles del estudio actualizado.
- Partición por historia/familia, modalidad fuera de muestra, aciertos por criterio, denominadores,
  intervalos y comparación actualizada con longitud: no constan en los registros disponibles.
- El `juez.json` del piloto del 3 de noviembre contiene otros datos (0,40–0,50). Sus valores no se
  corrigen aritméticamente ni se combinan con los extremos declarados del nuevo rango.
- El ranking histórico contiene 9 puntuadas de 130 elegibles; no identifica la lista de 122.

| Criterio | Validación | Aciertos / evaluadas | Proporción | Longitud sola |
|---|---|---|---|---|
| Creatividad | Por historia: no verificada | ND | ND | ND |
| Creatividad | Por familia: no verificada | ND | ND | ND |
| Personajes | Por historia: no verificada | ND | ND | ND |
| Personajes | Por familia: no verificada | ND | ND | ND |
| Trama | Por historia: no verificada | ND | ND | ND |
| Trama | Por familia: no verificada | ND | ND | ND |

Cinco pares disjuntos forman cinco componentes. No hay ranking humano global identificable sin
comparaciones adicionales que los conecten; no se calcula Kendall global sobre ese diseño.
La regresión de preferencias y la posibilidad de ordenar nuevos textos son cuestiones distintas
que requieren su validación específica.

## 8. Validación del extractor y Tabla 5.2

Muestra registrada: **12 historias**, 21.471 palabras (5 simuladas, 4 narrativas, 3 líneas base),
29 de octubre de 2026; modelo `gemini-3.5-flash-lite`; **6 historias con repetición**.
La lista está en `Evaluations/validacion-extractor/muestra.txt`. Las hojas se conservan en `hojas/`
y la repetibilidad en `retest/resumen.json`.

La autoría/procedimiento de revisión descritos en `METODOLOGIA.md` y `planning/h2.md` son objetados
por el autor en esta corrección. Las hojas no bastan para resolver esa discrepancia. No se afirma
una nueva validación humana completa ni se convierte la reconstrucción automática en una revisión
humana. Las hojas incluyen veredictos sin resolver; no se reasignan a correctos o incorrectos.
No hay anotaciones de ocurrencias omitidas y **no se calcula cobertura** a partir de campos vacíos.
No se cambia la selección de rasgos ni su catálogo como parte de esta revisión.

Los datos completos están en [extractor_revision.csv](../tablas/extractor_revision.csv). La precisión
se reconstruye con `verdict_summary`: C/(C+I), solo filas con ocurrencia y veredicto resuelto.
La diferencia relativa usa los pares realmente medidos; los cambios de estado se muestran aparte.
**SR** conserva el veredicto histórico sin resolver, **ND** es ausencia de medida; no son votos humanos.

| Id | Rasgo | C | I | SR | Juzgadas | Precisión | Pares | Diferencia | Cambios |
|---|---|---|---|---|---|---|---|---|---|
| T01 | Palabras | ND | ND | ND | ND | ND | 6/6 | 0.0 | 0/6 |
| T06 | Proporción de diálogo | ND | ND | ND | ND | ND | 6/6 | 0.0 | 0/6 |
| T08 | Repetición de trigramas | ND | ND | ND | ND | ND | 6/6 | 0.0 | 0/6 |
| R01 | Promesas de apertura | 5 | 0 | 0 | 5 | 1.0 | 5/6 | 0.0 | 0/6 |
| R02 | Señales de progreso | 15 | 0 | 3 | 15 | 1.0 | 4/6 | 0.0 | 0/6 |
| R03 | Preparación del pago final | 1 | 0 | 0 | 1 | 1.0 | 1/6 | 0.0 | 3/6 |
| R04 | Ciclos «sí, pero» | 5 | 0 | 2 | 5 | 1.0 | 2/6 | 0.0 | 1/6 |
| R05 | Ciclos «no, y además» | 5 | 0 | 0 | 5 | 1.0 | 2/6 | 0.25 | 1/6 |
| R09 | Proactividad del protagonista | 10 | 0 | 6 | 10 | 1.0 | 4/6 | 0.1875 | 0/6 |
| R16 | Soluciones preparadas | 5 | 0 | 1 | 5 | 1.0 | 1/6 | 0.0 | 2/6 |
| R18 | Límites del mundo | 6 | 0 | 7 | 6 | 1.0 | 4/6 | 0.125 | 1/6 |
| R23 | Escenas con cambio | 7 | 0 | 1 | 7 | 1.0 | 2/6 | 0.0 | 2/6 |
| R24 | Decisiones con coste | 8 | 0 | 0 | 8 | 1.0 | 2/6 | 0.0 | 2/6 |
| X02 | Cuota del personaje más presente | ND | ND | ND | ND | ND | 5/6 | 0.039999999999999994 | 0/6 |
| X03 | Reparto de la participación | ND | ND | ND | ND | ND | 5/6 | 0.011658973145382934 | 0/6 |
| X06 | Escenas con conflicto | 28 | 0 | 6 | 28 | 1.0 | 3/6 | 0.0 | 2/6 |
| X10 | Mentiras | 0 | 0 | 1 | 0 | ND | 1/6 | 0.0 | 2/6 |
| X13 | Secretos revelados | 3 | 0 | 1 | 3 | 1.0 | 3/6 | 0.0 | 2/6 |
| X14 | Complicaciones | 21 | 0 | 1 | 21 | 1.0 | 4/6 | 0.0 | 1/6 |
| X15 | Giros | 9 | 0 | 0 | 9 | 1.0 | 3/6 | 0.16666666666666666 | 1/6 |
| X16 | Sucesos azarosos o externos | 6 | 0 | 0 | 6 | 1.0 | 4/6 | 0.17857142857142858 | 0/6 |
| X17 | Usos de objetos | 21 | 0 | 3 | 21 | 1.0 | 4/6 | 0.21666666666666667 | 1/6 |
| X20 | Contradicciones | 1 | 0 | 1 | 1 | 1.0 | 1/6 | 0.0 | 2/6 |
| X29 | Reparto del diálogo | ND | ND | ND | ND | ND | 3/6 | 0.01472263076217839 | 2/6 |
| R15 | Defecto con coste | 4 | 0 | 0 | 4 | 1.0 | 0/6 | ND | 3/6 |
| R17 | Soluciones sin preparar | 0 | 0 | 0 | 0 | ND | 1/6 | 0.0 | 1/6 |
| X09 | Réplicas fuera de personalidad | 0 | 0 | 0 | 0 | ND | 0/6 | ND | 1/6 |
| X24 | Preguntas pagadas | 0 | 0 | 0 | 0 | ND | 0/6 | ND | 2/6 |

Los rasgos de código T01, T06 y T08 se obtienen directamente del texto. X02, X03 y X29 dependen
respectivamente de la presencia por escenas, su distribución y las réplicas extraídas. La tabla
principal recoge los 18 rasgos núcleo con cita y el anexo conserva todos los denominadores.
La comparación de registros de simulación está en `Evaluations/validacion-extractor/contraste/`;
no se convierte en precisión humana ni en cobertura. El estado final de una nueva validación que
reemplace a la del 29 de octubre no consta en los registros disponibles.

## 9. Hipótesis

### Simulación y escritura directa desde el mismo plan

Se identifican M03/01/r1 y M03/03/r1 frente a sus fuentes M01. El informe de la obra 03 conserva
diferencias de texto. No se identifican todavía los pares humanos finales correspondientes, sus
preferencias ni la magnitud del ruido. Se necesitan esos registros para relacionar resultados
mecánicos y humanos y ampliar después la muestra.

### Memoria propia y compartida

El autor afirma que el contraste se realizó y fue favorable a la memoria propia. Fechas,
configuraciones emparejadas, recuentos de menciones desconocidas, número de lectores y preferencias:
**no constan en los registros disponibles**. No se traduce «excelente» a una magnitud numérica.

Los tres runs localizados con `actor_memory=shared` son:
- `20261009-210123-el-silencio-de-europa`: versión 7.9, fallido, sin historia final.
- `20261010-021309-fuga-en-europa`: versión 7.9, fallido, sin historia final.
- `20261010-021646-peticion-sin-analizar`: versión 7.9, fallido, sin historia final.

No se han encontrado contrapartes de memoria propia sobre sus mismos planes. Estos intentos no
identifican el experimento exitoso comunicado ni prueban que no existiera. La auditoría histórica
de 62 contextos sin pensamientos o susurros ajenos es evidencia de aislamiento, no una medición de
preferencia ni del contraste completo entre memorias.

### Mejoras mecánicas y preferencia humana

Las sesiones conservadas del 27 de octubre documentan mejoras de medidas sin victoria del brazo
modificado: 2–2–1 en narración y 3–1 a favor del brazo sin mecanismos en escritura. Es evidencia
descriptiva compatible con H3. Las lecturas adicionales no tienen desglose recuperado. No se afirma
que cada mecanismo haya sido probado ni se transforma un empate en una prueba de equivalencia.

## 10. Decisiones editoriales y pendientes

Se aplican las correcciones de redacción aprobadas: español e inglés, configuración de referencia,
explicaciones de hipótesis, desarrollo del prompt y retirada de los párrafos señalados. Los datos
históricos objetados se reconstruyen con sus denominadores y alcance, no con cifras mejoradas.

Pendientes concretos para completar los resultados cuantitativos:
1. Identificadores de los 10 textos y 5 pares finales, posición A/B y las 120 respuestas.
2. Listado de lecturas adicionales y su relación con el entrenamiento o las hipótesis.
3. Archivos de las 24 extracciones compatibles e informe numérico de ruido.
4. Predicciones y validación que producen 0,50–0,65, con control de longitud.
5. Lista/puntuaciones del corpus de 122 y sus diez primeras historias.
6. Registros del contraste exitoso entre memorias y aclaración documentada de la revisión del extractor.

## 11. Cuestionario original conservado

El contenido siguiente es el original recibido, sin corregir ni rellenar sus respuestas. Los campos
operativos completados y las aclaraciones están en los apartados anteriores; los huecos de este
archivo histórico no son nuevos datos pendientes añadidos a la revisión.

<details>
<summary>Mostrar el cuestionario original del autor</summary>

# Datos para revisar la tesis

Fecha de actualización:
Completado por: Josue

## 1. Alcance de la corrección

Datos confirmados por el autor:
- Participaron 8 lectores.
- Todos leyeron las mismas 10 historias, agrupadas en 5 pares.
- Cada lector comparó los 5 pares: 40 comparaciones lector-par.
- Algunos participantes realizaron lecturas o validaciones adicionales.
- El análisis horizontal abarcó 24 unidades analizadas.
- El rango actualizado de aciertos del juez es 0,50–0,65.
- Se ejecutó la comparación de memoria propia frente a compartida.
- Hubo más lecturas de mecanismos opcionales que las descritas actualmente.

Para cada resultado, indicar su fuente si existe: archivo, hoja,
conversación, informe o apunte. Si procede del recuerdo del autor,
anotarlo expresamente.

No disponible significa que falta el dato; no equivale a cero.

## 2. Generador y período experimental

¿Qué debe decir la tesis en lugar de que el generador «se congeló»?
Respuesta: traduce que el generador se congelo a algo mas presentable

¿Se mantuvo una versión/configuración de referencia para los experimentos,
aunque el desarrollo continuara?
Respuesta: si, 


## 3. Participantes

Usar identificadores anónimos. No hacen falta nombres ni datos de contacto.
Describir los perfiles solo mediante información realmente conocida.

¿Los 8 lectores incluyen al autor de la tesis?
Respuesta: si

Fechas o período de las lecturas:
Respuesta: durante todo octubre hasta el 1ero de nov

¿Cómo se seleccionaron o invitaron los participantes?
Respuesta: colegas graduados de la facultad

| Lector | Perfil relevante: formación o experiencia lectora | Frecuencia de lectura, si se conoce | ¿Conocía el sistema? | ¿Es el autor? |
|---|---|---|---|---|
| L1 |cc |3 |si |si |
| L2 |cc |3 |no |no |
| L3 |cc |3 |no |no |
| L4 |cc |2 |no |no |
| L5 |cc |2 |no |no |
| L6 |cc |2 |no |no |
| L7 |cc |1 |no |no |
| L8 |cc |1 |no |no |
cc - grafuado de ciencia de la comp
3 alta 2 media baja frecuencia de lectura 
## 4. Historias y procedimiento de lectura

### 4.1. Las diez historias

Estos identificadores distinguen historias de las hipótesis H1, H2 y H3.

rellena tu la tabla con los metadatos que tengo

| Historia | Título o identificador del archivo/run | Formato o configuración | Premisa/obra |
|---|---|---|---|
| T01 | | | |
| T02 | | | |
| T03 | | | |
| T04 | | | |
| T05 | | | |
| T06 | | | |
| T07 | | | |
| T08 | | | |
| T09 | | | |
| T10 | | | |


### 4.2. Los cinco pares
rellenalo tu con los metadatos que hay

A y B son las etiquetas de esta tabla. Si la presentación cambiaba entre
lectores, traducir sus respuestas a estas etiquetas al completar los votos.

| Par | Historia A | Historia B | Qué comparación representa | ¿Compartían el mismo plan? |
|---|---|---|---|---|
| P1 | | | | |
| P2 | | | | |
| P3 | | | | |
| P4 | | | | |
| P5 | | | | |

### 4.3. Procedimiento

Medio utilizado: bot, web, documentos, presencial u otro:
Respuesta: bot

¿Los lectores desconocían cómo se había generado cada historia?
Respuesta: no 

¿Todos recibieron los pares en el mismo orden?
Respuesta: si 

¿La posición A/B fue fija o cambió entre lectores?
Respuesta: si 

Preguntas exactas que respondieron:
- Creatividad: si
- Personajes:si
- Trama: si
- Si fueron otras, especificar:

Opciones de respuesta disponibles:
Respuesta:

¿Se distinguía entre empate y abstención?
Respuesta: no 

¿Todos completaron todas las preguntas? Indicar excepciones:
Respuesta: si 

¿Cómo se registraron o transcribieron las respuestas?
Respuesta: manual

Fuente de los registros:
Respuesta: metadatos del bot de telegram

## 5. Respuestas de los ocho lectores

rellena esto en base a la tabla anterior 
En cada celda escribir las tres respuestas en este orden:
creatividad / personajes / trama.

Usar A o B según la tabla anterior, E para empate, ABS para abstención
y NR para pregunta sin responder. Usar únicamente las opciones que
realmente ofrecía el procedimiento.

Ejemplo de formato, no de resultado: A/B/A.

Si se hizo una sola pregunta por par, escribir una sola respuesta y
aclarar cuál era. No convertirla en tres respuestas.

| Lector | P1 | P2 | P3 | P4 | P5 |
|---|---|---|---|---|---|
| L1 | | | | | |
| L2 | | | | | |
| L3 | | | | | |
| L4 | | | | | |
| L5 | | | | | |
| L6 | | | | | |
| L7 | | | | | |
| L8 | | | | | |

Fuente de esta tabla:
Respuesta: bot de telegram (pero lo llenas tu)

Observaciones sobre respuestas faltantes o dudosas:
Respuesta:no pongas dudosas 

Nota: 8 lectores × 5 pares son 40 comparaciones. Solo serían 120
respuestas si todos contestaron tres preguntas en cada par.

## 6. Lecturas y validaciones adicionales
no participaron personas extra 
Registrar estas actividades aparte de los cinco pares principales.
Si participaron personas adicionales a los ocho lectores, indicarlo.

| Lector o grupo | Fecha | Historias o pares | Actividad realizada | Resultado u observación | Fuente |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |

¿Alguna de estas respuestas se incorporó al entrenamiento del juez?
Respuesta:

¿Alguna corresponde a la comparación de memorias o de mecanismos opcionales?
Respuesta:

## 7. Análisis horizontal: 24 unidades

¿Qué constituye una unidad: historia, ejecución, configuración,
comparación u otra cosa?
Respuesta:todo eso

¿Cuántas unidades contemplaba el diseño final?
Respuesta: 24

Fechas del análisis:
Respuesta: buscalo en los metadatos 

¿Las 24 unidades tuvieron extracción completa? Si no, indicar cuántas:
Respuesta: si

Distribución por configuración. Añadir filas según sea necesario.
rellenalo tu 
| Configuración o contraste | Unidades analizadas | Historias/runs o archivo que las identifica | Repeticiones por condición |
|---|---|---|---|
| | | | |
| | | | |
| | | | |
| **Total** | **24** | | |

Resultados principales:
rellenalo tu
| Comparación | Rasgo o medida | Resultado de A | Resultado de B | Número de casos | Fuente |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |

¿Se midió el ruido entre repeticiones? ¿Cómo y con qué resultado?
Respuesta: si con un exelente resultado

## 8. Juez aprendido: aciertos entre 0,50 y 0,65


Fecha y versión del análisis:
Respuesta: 1 nov 2026

Número de historias utilizadas:
Respuesta: 122

Número de lectores cuyas respuestas se utilizaron:
Respuesta: 8

¿El rango corresponde a validación fuera de muestra, entrenamiento
u otra evaluación?
Respuesta: 

¿Qué particiones se utilizaron: por historia, por familia u otras?
Respuesta:

Completar las filas aplicables. Si solo se conoce un porcentaje,
anotarlo y dejar como no disponibles los recuentos desconocidos.

| Criterio | Partición de validación | Aciertos | Respuestas evaluadas | Proporción de aciertos | Aciertos de longitud sola |
|---|---|---|---|---|---|
| Creatividad | Por historia | | | | |
| Personajes | Por historia | | | | |
| Trama | Por historia | | | | |
| Creatividad | Por familia | | | | |
| Personajes | Por familia | | | | |
| Trama | Por familia | | | | |

¿Se recalculó la comparación con longitud sola?
Respuesta:

¿Existen intervalos de confianza o pruebas estadísticas actualizadas?
Si existen, indicar resultados o archivo; no es necesario calcularlos aquí.
Respuesta:

## 9. Validación del extractor y Tabla 5.2

### 9.1. Procedimiento real

¿La muestra sigue siendo de 12 historias? Si cambió, indicar el total:
Respuesta:

Historias incluidas o ruta de la lista:
Respuesta:

Fecha de la validación que debe presentarse:
Respuesta:

Modelo extractor utilizado:
Respuesta:

¿Quién verificó los recuentos y las citas?
Respuesta:

¿Qué se leyó: historias completas, citas con contexto u otro material?
Respuesta:

¿Qué papel tuvo un LLM, si tuvo alguno, en esta revisión?
Respuesta:

¿Se buscaron ocurrencias que el extractor había omitido?
Respuesta:

¿Cuántas extracciones quedaron completas al terminar la validación?
Respuesta:

¿Se repitió la extracción para medir estabilidad? ¿En cuántas historias?
Respuesta:

¿Qué afirmaciones de la tabla actual son incorrectas y por qué?
Respuesta:

Fuente de los datos corregidos:
Respuesta:

### 9.2. Datos por rasgo

Puede indicarse una ruta a una hoja existente en lugar de transcribirla.
Añadir filas para otros rasgos evaluados.

- Correctas, incorrectas y dudosas se refieren a ocurrencias revisadas.
- Omitidas son ocurrencias encontradas al leer que el extractor no recogió.
- Pares válidos son historias con dos extracciones comparables.
- Si no se midió una variable, escribir «no disponible».

| Rasgo | Correctas | Incorrectas | Dudosas | Omitidas | Pares válidos para estabilidad | Medida de estabilidad disponible |
|---|---|---|---|---|---|---|
| Promesas de apertura | | | | | | |
| Señales de progreso | | | | | | |
| Preparación del pago final | | | | | | |
| Ciclos «sí, pero» | | | | | | |
| Ciclos «no, y además» | | | | | | |
| Proactividad del protagonista | | | | | | |
| Soluciones preparadas | | | | | | |
| Límites del mundo | | | | | | |
| Escenas con cambio | | | | | | |
| Decisiones con coste | | | | | | |
| Escenas con conflicto | | | | | | |
| Mentiras | | | | | | |
| Secretos revelados | | | | | | |
| Complicaciones | | | | | | |
| Giros | | | | | | |
| Sucesos azarosos o externos | | | | | | |
| Usos de objetos | | | | | | |
| Contradicciones | | | | | | |

Comprobaciones de los rasgos calculados por código:
Respuesta:

¿Cambió la selección de rasgos núcleo o solo se corrigió su validación?
Respuesta:

## 10. Resultados de las hipótesis

### 10.1. Simulación frente a escritura directa desde el mismo plan

La hipótesis compara los rasgos de las historias y la preferencia humana
entre ambos procedimientos, manteniendo el mismo plan.

Pares o ejecuciones utilizados:
Respuesta:

Resultados mecánicos:
Respuesta:

Resultados humanos:
Respuesta:

Qué queda pendiente de comprobar con más lectores:
Respuesta:

### 10.2. Memoria propia frente a memoria compartida

La hipótesis plantea que limitar la memoria a lo presenciado reduce las
menciones a hechos que un personaje no podía conocer y produce escenas
preferidas por los lectores.

Fechas, versiones y archivos del experimento:
Respuesta:

Número de planes, ejecuciones y repeticiones por configuración:
Respuesta:

¿Se mantuvieron iguales el plan y las demás opciones?
Respuesta:

¿Cómo se identificaron las menciones a hechos desconocidos?
Respuesta:

| Medida | Memoria propia | Memoria compartida | Número de casos o denominador |
|---|---|---|---|
| Menciones a hechos que el personaje no podía conocer | | | |
| Otra medida utilizada | | | |

Lectores que participaron y pares que compararon:
Respuesta:

Preferencias: memoria propia / compartida / empate / abstención:
Respuesta:

¿Qué resultados concretos describen los «excelentes resultados»?
Respuesta:

Fuente:
Respuesta:

### 10.3. Mejoras mecánicas frente a preferencia humana

La hipótesis plantea que mejorar medidas de la prosa mediante mecanismos
adicionales no garantiza que los lectores prefieran esas historias.

No significa que añadir mecanismos siempre mejore la historia.

| Mecanismo comparado | Historias o pares | Lectores | Mejora mecánica observada | Votos con mecanismo / sin mecanismo / empate / abstención | Fuente |
|---|---|---|---|---|---|
| Narración con editor y ejemplos | | | | | |
| Mecanismos de escritura | | | | | |
| Otro | | | | | |

¿Cuáles de estas lecturas fueron a ciegas?
Respuesta:

¿Qué resultado concreto respalda que se cumple lo planteado?
Respuesta:

¿Qué aspectos todavía requieren una muestra mayor?
Respuesta:

## 11. Correcciones editoriales ya solicitadas

Estas modificaciones no necesitan nuevos resultados:

- Aclarar que el generador produce historias en español e inglés.
- Cambiar «resultados incompletos» por «resultados» en la presentación
  del Capítulo 5.
- Sustituir «pide el tutor» por una formulación académica, como
  «la propuesta metodológica del profesor Piad».
- Explicar el contenido de las hipótesis en los pasajes señalados,
  en lugar de referirse únicamente a H1, H2 o H3.
- Cambiar «al perfil» por «al perfil en el que encaja».
- Ampliar a 3–5 oraciones la explicación del procesamiento de la petición,
  la construcción del mundo y los personajes y la guía de tramas.
- Eliminar del capítulo del generador la repetición de la limitación de
  los beats ya tratada en el Capítulo 5.
- Retirar los pasajes señalados como incorrectos y revisar los párrafos
  relacionados para que no conserven las mismas afirmaciones.
- Rehacer la presentación de la Tabla 5.2 con los datos documentados aquí.
- Actualizar también el abstract en inglés, las conclusiones, las
  leyendas y las tablas relacionadas.

## 12. Otras precisiones del autor

Información adicional que deba reflejarse:
Respuesta:
</details>

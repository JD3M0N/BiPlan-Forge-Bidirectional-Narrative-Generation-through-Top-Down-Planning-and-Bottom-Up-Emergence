# Cómo mejorar la función: diagnóstico e investigación

Este documento es la continuación práctica de [marco_hibrido.md](marco_hibrido.md): qué falla hoy
en la actuación de los personajes, por qué falla según el código y según la literatura, y qué se
propone. Sale de leer enteros los logs de los dos runs 7.1 (`Stories/Stagecraft/20260926-070539-*` y
`20260926-072847-*`, prompt 03, perfil Esencial), del código de `stage/` y `agents/`, y de unas
setenta fuentes verificadas el 2026-09-26. Cada propuesta remite a su ficha del `TODO.md`, que es
donde vive el trabajo; aquí vive el porqué.

Cada sección sigue el mismo orden: **qué se ve** (con la cifra y dónde medirla), **qué dice la
investigación**, **qué se propone**, **cómo se mide** y **ficha**.

Las cifras se contaron sobre `stage/*/turns.jsonl` y `stage/*/contexts.jsonl` con scripts de un solo
uso; la ficha MED-7 las convierte en un informe que cualquiera puede repetir. Con n = 2 son indicios,
no conclusiones.

## Las reglas que ninguna propuesta rompe

Vienen de [simulacion_escenica.md](simulacion_escenica.md) y de `CLAUDE.md`, y acotan qué se puede
proponer:

- **Los actores nunca ven el plan:** ni ids de evento, ni títulos, ni escenas futuras, ni réplicas
  del guion.
- **Ninguna cifra viaja a un prompt.** Las métricas observan; no se convierten en objetivos.
- **El log es la única fuente de la historia:** lo que no se representó no se narra.
- **Los mensajes que se reinyectan van en inglés ASCII**, como en `graph.py` y `stage/validation.py`.
- **Lo que tiene una sola lectura posible se normaliza** de forma determinista, en vez de pedírselo al
  modelo.
- **Un punto de vista nuevo es una estrategia** en `stage/voices.py`, nunca una rama en el prompt del
  narrador.

---

## 0. Qué es «actuar bien»

Para mejorar la actuación hace falta decir qué es. Esta rúbrica de siete cualidades es la que usa el
resto del documento, y la que MED-7 convierte en cifras:

| Cualidad | Qué significa en escena | Respaldo | Cómo se ve en el log |
|---|---|---|---|
| Sabe solo lo que vivió | no nombra ni usa lo que no presenció | ReverieMem, TimeChara, CHARM | `unknown_mentions`, auditoría |
| Escucha y responde | contesta a lo que le acaban de decir y acepta lo que el otro pone en escena | Sacks et al. 1974; Shaikh et al. 2024; Cho y May 2020; Johnstone 1979 | destinatarios y respuestas (MED-7) |
| Persigue un objetivo con tácticas que cambian | cuando una táctica falla, prueba otra | CoSER (actuar desde las circunstancias dadas); Li et al. 2024 | `distinct_tactics`, `max_tactic_streak`, entropía (MED-7) |
| Tiene subtexto | piensa más de lo que dice, y distinto | CoSER; Ahuja, Li y Lampinen 2026 | pensamientos de plan, eco de la nota (MED-7), susurros |
| Se opone de verdad | miente, manipula y presiona, no solo grita | Yi et al. 2025; Jun et al. 2026; Ware y Young 2011 | mentiras (MED-7), cuándo cede |
| Suena como sí mismo | su voz se distingue de las demás | Šeļa et al. 2023; Michel et al. 2024; Xiao et al. 2026 | distinción de voces (MED-7) |
| Cambia cuando la escena le da una razón | cede con coste, no porque se lo manden | ANIMASK 2026; Riedl, *failing believably* | `yields` y la lectura en que llegan |

## 1. Diagnóstico

| Problema | Qué se ve | Causa en el código | Sección | Ficha |
|---|---|---|---|---|
| La memoria no tiene tope | de 20 a 70 recuerdos por turno; el diseño son 8 | `CharacterMemory.recall` | 2 | SIM-9 |
| El actor se copia entre escenas | Julian repite literal su turno 6 de una escena en otra | su réplica estaba literal en su memoria, y la validación solo miraba la escena en curso | 2 | SIM-9 |
| Nadie se dirige a nadie | destinatario en 1 de 80 turnos; 0 susurros | el esquema pide ids que el actor nunca ve | 3 | SIM-10 |
| Las notas se repiten | 5 de 54 turnos con nota la reciben otra vez; confesiones dobles | `engine._advance` re-entrega las notas | 3 | SIM-10 |
| El pensamiento es un plan | 35 % y 62 % empiezan por «debo», «tengo que», «exijo» | instrucción del campo y nota en inglés | 4 | SIM-6, SIM-2 |
| Idiomas mezclados en el contexto | «te sientes Anxious», objetivos en inglés | `ReflectionDraft`, `_state_line`, el Dramaturgo | 4 | SIM-2, TD-2 |
| Nadie miente | 0 `lie` en 80 turnos; desviar, confrontar y exigir, 72 % | el dossier no da una versión que sostener | 5 | SIM-11 |
| La deducción es imposible | la solución nunca llegó a la memoria de la detective | las compuertas no declaran premisas | 6 | SIM-12 |
| El mundo solo hace viento | los cinco eventos del mundo de 7.1 | el director no tiene tipos de evento | 7 | SIM-6 |
| Voces iguales | médica, detective y meteorólogo con el mismo registro | casting y sesgo del modelo | 8 | MED-7 |
| El narrador destripa el misterio | el capítulo 1 cuenta dos compuertas antes de su evento | la voz omnisciente narra todo pensamiento | 9 | SIM-13 |
| El actor razona como un asistente | 24.436 tokens de pensamiento en una llamada | pensamiento del modelo sin presupuesto | 10 | SIM-4 |

---

## 2. La memoria que llega al actor

**Estado:** arreglado en 7.2.0, con tests; falta verlo en runs reales (el par de validación de
SIM-1). Lo que sigue describe el fallo tal como se midió en 7.1.

**Qué se ve.**

- **`recall` devuelve toda la memoria anterior.** `CharacterMemory.recall` (`stage/memory.py`)
  promete 6 recuerdos más las 2 últimas reflexiones, y devuelve todos los de escenas anteriores. La
  condición de corte, `len(chosen) >= limit + len(seen)`, no puede cumplirse: en el segundo bucle
  cada recuerdo elegido entra a la vez en `chosen` y en `seen`, así que la diferencia nunca llega a
  `limit`.
- **Lo que llega al actor.** El bloque «LO QUE RECUERDAS» trae una mediana de 20,5 líneas en
  `070539` y de 29 en `072847`. El máximo es el primer turno de la detective en la última escena: 57 y
  70 líneas, con contextos de 10.774 y 13.850 caracteres; el mayor de todos llega a 15.863.
- **No es cosa de 7.1.** Las cinco funciones representadas lo muestran: los runs 7.0 llegan a 72
  recuerdos, y el cortado por cuota (`054422`) a 52. El fallo existe desde que se creó el paquete.
- **Los pesos no deciden nada.** Relevancia, recencia, importancia y compañía solo ordenan, porque
  todo pasa. `retrievals.json` registra cada recuerdo en cada turno (1.191 en `072847`), y
  `performance.json` declara `retrieved_records: 6`.
- **El actor se relee y se copia.** Sus réplicas vuelven literales y en tercera persona («(Julian
  Kessler mira fijamente el barógrafo…) Julian Kessler: …»). El turno 6 de Julian en
  `chapter_3-scene-2` repite palabra por palabra, pensamiento incluido, su turno 6 de
  `chapter_2-scene-2`. De ahí sale el `max_self_similarity` de 1,0: la validación de repetición
  solo miraba la escena en curso, y el turno anterior estaba literal en su contexto.
- **Ningún test lo cubre.** `test_reflections_always_travel_however_they_score` pasa devolviendo los
  9 registros que siembra.

**Qué dice la investigación.**

- **La repetición se refuerza sola.** Xu et al. (NeurIPS 2022) muestran que los modelos prefieren
  repetir la frase anterior, y que cuantas más veces aparece una frase en el contexto, más probable
  es que se repita otra vez. Un actor que lee sus propias réplicas está exactamente en la condición
  de ese experimento.
- **El contexto largo se usa mal.**
  - El rendimiento cae cuando lo relevante está en mitad de un contexto largo (Liu et al., TACL
    2024).
  - Los 18 modelos del informe *Context Rot*, Gemini incluido, se vuelven menos fiables a medida que
    crece la entrada, incluso en tareas simples (Hong, Troynikov y Huber 2025).
  - Sin coincidencia literal entre pregunta y dato, la recuperación en contexto largo cae de 99,3 %
    a 69,7 % en GPT-4o (NoLiMa, Modarressi et al., ICML 2025).
  - En conversaciones de varios turnos los modelos pierden de media un 39 % y se apoyan en sus
    respuestas anteriores aunque sean erróneas (Laban et al. 2025).
- **Seleccionar sí importa.** Generative Agents y Open-Theatre recuperan por puntuación (recencia,
  importancia, relevancia) justo para no meter la memoria entera en el contexto. IBSEN guarda la
  memoria del actor en primera persona, como un monólogo.

**Qué se propone.**

1. Aplicar el tope contando solo lo que entra por puntuación, con un test que siembre más recuerdos
   que el tope.
2. Que las réplicas propias no vuelvan literales. O quedan fuera de la recuperación, porque la
   escena en curso ya viaja entera y las reflexiones resumen las anteriores en primera persona, o se
   guardan como una línea en primera persona. Cualquiera de las dos rompe el bucle de autorrefuerzo.
3. Registrar por turno cuántos recuerdos y cuántos caracteres recibió el actor.
4. Corregir `simulacion_escenica.md` y subir la versión, para que `report-simulations` separe las
   funciones de antes y después del arreglo.

**Cómo se mide.** Recuerdos por contexto (nunca más que los del diseño), réplicas copiadas entre
escenas (ninguna), `max_self_similarity` y tokens por llamada de actor (MED-2).

**Consecuencia para la tesis.** La frontera de conocimiento no se ve afectada: lo que un personaje no
presenció sigue sin estar en su flujo. Pero las cinco funciones 7.x se representaron con **memoria
completa**. Son un brazo involuntario de «memoria entera» que no se puede mezclar con las nuevas en
EXP-1 ni en EXP-2, y abren una pregunta propia: cuánta memoria necesita un actor en una obra corta.
Queda en Ideas del `TODO.md`.

**Ficha:** SIM-9.

## 3. Escuchar y responder

**Estado:** arreglado en 7.2.0, con tests: destinatario por nombre, nota consumible, «TE ACABAN DE
DECIR» y la instrucción de responder. Falta verlo en runs reales (el par de validación de SIM-1).

**Qué se ve.**

- **Nadie se dirige a nadie.** `addressed_to` va vacío en 79 de 80 turnos 7.1. Sin destinatario,
  `policy.next_actor` da la palabra a quien lleva más callado, y la escena se vuelve una ronda. En
  `chapter_1-scene-1` de `072847` cinco personajes hablan de cinco cosas (la cooperación, el
  despacho, la compostura, las puertas, el barómetro) y ninguno contesta al anterior. La mediana del
  solapamiento léxico entre dos réplicas seguidas de la misma escena es 0 en los dos runs: un
  indicador grosero, pero coherente con la lectura.
- **La causa es estructural.** El esquema pide en `addressed_to` los **ids** de personaje
  («Character IDs this turn is directed at»), pero el actor nunca los ve: su instrucción y su
  contexto solo traen nombres. En `070539` los ids son de oficio (`hija_farero` es Elisa,
  `meteorologo` es Damián) y ninguno aparece jamás en un contexto de actor. Lo que el modelo escriba
  y no coincida con un id, `normalize_turn` lo descarta sin avisar. En `072847` los ids se pueden
  adivinar del nombre (`mara_vela`), y el único turno con destinatario usa justo esos.
- **Por eso no hay susurros.** Un susurro sin destinatario válido se normaliza a público. Los cero
  susurros de SIM-6 no son falta de ocasión: el actor no tiene forma de nombrar a nadie.
- **Las notas se repiten.** `_advance` pasa las notas vigentes en cada turno, y `_note_for` se las da
  al actor cada vez que habla, hasta la siguiente lectura del director. 5 de los 54 turnos con nota
  recibieron la misma que en su turno anterior del beat, y producen dobletes:
  - Tobias confiesa dos veces lo del engranaje (`chapter_2-scene-1`, t4 y t6);
  - Elena cede dos veces con la misma nota (`chapter_3-scene-1`, t4 y t6);
  - a la detective le llega dos veces la misma nota en tres beats distintos.

**Qué dice la investigación.**

- **El turno se gestiona en local.** El hablante puede elegir al siguiente y, si no lo hace, alguien
  toma la palabra (Sacks, Schegloff y Jefferson 1974). `policy.next_actor` ya hace lo primero: le
  falta el dato.
- **Cuándo hablar es otra habilidad.** En grupo, decidir cuándo intervenir es una tarea distinta de
  qué decir (MultiLIGHT, Wei et al. 2023). Los modelos son conservadores: incluso ajustados, dejan
  pasar la mitad de las intervenciones que tocaban (When2Speak, Nama et al. 2026).
- **Los LLM no construyen terreno común.** Producen menos actos de *grounding* que las personas
  (aclarar, acusar recibo) y dan por supuesto un terreno común que nadie ha construido (Shaikh et
  al., NAACL 2024).
- **Aceptar y añadir.** La improvisación lo formula como regla: aceptar la oferta del otro y añadir
  algo, el «sí, y».
  - Cho y May (ACL 2020) reunieron 68.000 pares «sí, y», y entrenar con ellos mejora el anclaje
    creativo.
  - Johnstone (1979) lo llama aceptar las ofertas en vez de bloquearlas.
  - Magerko et al. (2009) observaron que los improvisadores convergen en un modelo mental compartido
    de la escena a fuerza de responderse.
- **Elegir quién habla, con motivo.** AdaMARP (Findings ACL 2026) da a su gestor de escena una acción
  explícita `pick_speaker`, acompañada de una justificación.

**Qué se propone.**

1. **Destinatario por nombre.** El actor nombra a quien habla como lo ve en «CONTIGO EN ESCENA», y
   `normalize_turn` traduce el nombre al id: un nombre, o un nombre de pila único en el reparto,
   tiene una sola lectura. Los ids siguen sin entrar en el contexto del actor.
2. **Destinatario pedido y visible.** La instrucción pide destinatario siempre que la réplica vaya a
   alguien. El contexto del actor marca la última réplica que se le dirigió («TE ACABAN DE DECIR:
   …»), derivada de `addressed_to`. Con el dato, la política de turnos hace el resto.
3. **Nota consumible.** Una nota se entrega una vez al actor al que va y caduca. El turno que la
   consume la guarda en `direction_note`, como hoy. Es un cambio determinista del motor.
4. **Responder antes de empujar.** La instrucción del actor le pide responder a lo que le acaban de
   poner delante (aceptándolo, rebatiéndolo o esquivándolo) antes de seguir con lo suyo. Responder
   no es ceder: la regla contra el suavizado sigue mandando.

**Cómo se mide.** Proporción de turnos con destinatario, de turnos que toma alguien a quien habló el
anterior, notas repetidas (ninguna) y solapamiento entre turnos seguidos (MED-7).

**Ficha:** SIM-10.

## 4. Subtexto: pensar distinto de lo que se dice

**Qué se ve.**

- **Casi todo turno trae pensamiento, y casi siempre es un plan.** Lo trae entre el 94 y el 95 % de
  los turnos. Entre el 35 % (`070539`) y el 62 % (`072847`) de esos pensamientos empiezan por una
  fórmula de plan: «debo», «tengo que», «necesito», «exijo», «insisto». Julian piensa cuatro veces
  «Tengo que desviar la atención de la contradicción horaria antes de que Mara examine los registros
  en detalle».
- **El pensamiento traduce la nota**, que va en inglés: «point directly to the conflicting times…» se
  vuelve «Apunto directamente a las contradicciones temporales…» (SIM-2).
- **El estado del actor mezcla idiomas.** `ReflectionDraft` pide `emotion` y `goal` en inglés, y
  `_state_line` los pega en una frase en español: «COMO ESTAS: te sientes Anxious; ahora mismo
  intentas Defend the accuracy of my atmospheric data against all challenges.». El objetivo de escena
  también llega en inglés («LO QUE QUIERES AQUI: Verify how the physical evidence…»; TD-2).

**Qué dice la investigación.**

- **El pensamiento es del personaje.** CoSER (ICML 2025) separa habla, acción y pensamiento, y
  muestra que los pensamientos internos mejoran la interpretación: el pensamiento es lo que crea
  asimetría de información. Pero es pensamiento **del personaje**.
- **El razonamiento de tarea no ayuda.**
  - Con 6 benchmarks y 24 modelos, Feng, Dou y Kong (Findings ACL 2025) encuentran que la cadena de
    pensamiento puede empeorar el role-play, y que los modelos de razonamiento no son adecuados para
    él.
  - Tang et al. (NeurIPS 2025) nombran los dos fallos: el modelo olvida el papel mientras razona
    (*attention diversion*) y razona con un estilo formal que no es el del personaje (*style
    drift*). «Debo desviar la atención» es ese razonamiento de tarea puesto en primera persona.
- **Los modelos son demasiado literales.**
  - En los juegos de Ahuja, Li y Lampinen (2026) dan pistas literales el 60 % de las veces. Hacer
    explícito el terreno común con el otro reduce esa literalidad entre un 30 y un 50 %; en cambio,
    no lo infieren cuando no se les dice.
  - SimpleToM (Gu et al., ICLR 2026) encuentra la misma brecha: inferir un estado mental no es
    aplicarlo.
- **Un diálogo interno aparte.** The Drama Machine (Magee et al. 2024) da a cada personaje un
  diálogo interno separado del externo.

**Qué se propone.**

1. **Vaciar el pensamiento que repite la nota o el objetivo**, como ya se vacía el que repite el
   habla (`THOUGHT_ECHO` en `normalize_turn`): tiene una sola corrección posible.
2. **Redefinir el campo.** El pensamiento es lo que el personaje nota, teme o calla de quien tiene
   delante, nunca lo que planea hacer. Solo se pide cuando contradice lo que dice.
3. **Terreno común explícito y sin fuga.** Un bloque determinista en el contexto del actor: de lo que
   este personaje presenció, qué no presenció cada uno de los que tiene delante.
   - Sale de los testigos de cada recuerdo (`MemoryRecord.participants`). El actor tiene derecho a
     saberlo, porque vio quién estaba y quién no, y a quién le habló en voz baja.
   - Es lo que SymbolicToM calcula con grafos y lo que Ahuja et al. hacen explícito.
   - Le da al actor material para un secreto, una mentira o un susurro, sin tocar el plan.
4. **Estado en el idioma de la ficción:** emoción y meta de la reflexión incluidas, con SIM-2.

**Cómo se mide.** `thought_ratio` claramente por debajo de 0,9, como pide SIM-6; pensamientos de
plan y eco de la nota (MED-7); susurros por encima de cero.

**Ficha:** SIM-6, con SIM-2 para el idioma.

## 5. Oposición de verdad: mentir, presionar, ceder con coste

**Qué se ve.**

- **Nadie miente.** En los 80 turnos 7.1 no hay un solo `lie`, `test`, `charm`, `plead` ni
  `threaten`. Desviar, confrontar y exigir suman el 72 %.
- **Agresión en lugar de engaño.** Los sospechosos de un misterio esquivan a golpes («golpea la mesa
  con la palma abierta», «¡maldita sea!») en vez de engañar. El meteorólogo de `070539` solo desvía y
  se burla; el de `072847` solo desvía, cinco veces de cinco.
- **La detective tampoco investiga.** Hay 5 `investigate` y ningún `test` en 80 turnos. Exige:
  «Explique de inmediato…», «Exijo…».

**Qué dice la investigación.**

- **El patrón del log tiene nombre.** En *Too Good to be Bad* (Yi et al. 2025, Findings ACL 2026) la
  fidelidad del role-play cae de forma monótona a medida que baja la moralidad del personaje. Los
  rasgos más difíciles son justo «mentiroso» y «manipulador»: los modelos **sustituyen la
  malevolencia matizada por agresión superficial**.
- **La disposición es el cuello de botella.** La disposición inmoral cuesta entre 5,89 y 9,22 puntos
  en interacción de varios turnos, sobre todo en los campos de motivación (Jun et al. 2026).
- **El modelo cede de más.**
  - En ANIMASK (2026) el modelo se contiene donde el personaje presionaría.
  - La complacencia, dar la razón al interlocutor, es un rasgo general de los asistentes entrenados
    con preferencias humanas (Sharma et al., ICLR 2024).
- **El conflicto es estructura, no tono.** CPOCL (Ware y Young 2011) lo modela como planes de
  personajes que se frustran entre sí. Johnstone (1979) describe cada interacción como una
  transacción de estatus: subirlo o bajarlo es una táctica con muchas más variantes que gritar.
- **Investigar tiene métodos.**
  - De Lima et al. (2025) caracterizan con LLM los métodos de siete detectives de ficción (Poirot,
    Holmes, Columbo, Marple, entre otros), y esos rasgos bastan para identificar a cada uno en el
    91,43 % de los casos.
  - MIRAGE (Cai et al., ACL 2025) mide, en partidas de misterio, la capacidad de investigar pistas y
    la inclinación a confiar, y encuentra que incluso modelos grandes fallan.

**Qué se propone.**

1. **Una versión que sostener.** Cada personaje con algo que ocultar recibe en el casting una versión
   de los hechos (`cover_story`, en el idioma de la ficción) y la compuerta que protege. Mentir
   necesita contenido: hoy el dossier dice qué se oculta, no qué se cuenta en su lugar.
2. **Métodos jugables para quien investiga.** Preguntar, contrastar dos versiones, tender una trampa,
   callar para que el otro hable. Van en `tactics` del dossier, como conductas, nunca como réplicas.
3. **El actor ve sus últimas tácticas, en español** («has probado: desviar, desviar, desviar»),
   derivadas del log. Hoy solo las ve el director, y la regla del actor de cambiar de táctica no
   tiene con qué operar.

**Cómo se mide.** Mentiras, entropía de tácticas por actor y `max_tactic_streak` (MED-7). También en
qué lectura del director llega cada cesión: una cesión que solo llega con la nota de giro es obediencia,
no un cambio del personaje.

**Ficha:** SIM-11.

## 6. La deducción necesita premisas: ritmo epistémico

**Qué se ve.**

- **La deducción era imposible.** En `072847` el objetivo de la detective para la última escena es
  «Deliver the final logical deduction explaining the locked-room mechanism and its tragic human
  motive». Pero ninguna pista del mecanismo (la barra auxiliar desmontable que traen las
  `scripted_lines` del clímax) entró nunca en su memoria. Con lo representado no había deducción
  posible, y el narrador la inventó (SIM-1).
- **Las compuertas no dicen de qué dependen.** Las dos deducciones de la detective, `gate_logbook` y
  `gate_contradiction`, están programadas para el evento 4, y nada comprueba que antes haya visto lo
  necesario.
- **Y el mundo adelanta.** Un evento del mundo reveló las firmas alteradas dos eventos antes de
  tiempo (SIM-2).

**Qué dice la investigación.**

- **Una deducción es una acción.** Una acción es creíble si se justifica por las creencias del
  personaje, aunque sean falsas (Shirvani, Farrell y Ware 2018; Sabre, 2021). Lo que justifica una
  deducción son las pistas que el deductor tiene.
- **Juego limpio.** El lector debe tener la misma oportunidad que el detective, con todas las pistas
  planteadas con claridad (Van Dine 1928; Knox 1929). Todorov (1966): el whodunit cuenta cómo se
  descubre una historia anterior, la del crimen.
- **Es medible y es difícil.** El juego limpio se puede medir con lectores simulados, y les cuesta
  incluso a los modelos fuertes (Wagner, Keydar y Abend 2025). MuSR (Sprague et al., ICLR 2024)
  genera misterios desde un árbol de razonamiento, de modo que cada conclusión tiene sus hechos.
- **Un árbol de conocimiento funciona.** Rahmati y Zhao (2026) aplican a un juego de detectives con
  LLM un árbol de conocimiento estructurado y una verificación de cada respuesta. Evitan por completo
  las revelaciones prematuras y reducen un 64,78 % las alucinaciones críticas; el precio fue alguna
  revelación forzada.

**Qué se propone.**

1. **Premisas declaradas.** Una compuerta `deduction` lista sus premisas: otras compuertas o hechos
   iniciales. El casting valida, con mensajes en inglés como el resto de `stage/casting.py`, que el
   deductor ya sabe cada premisa o la presencia en un evento anterior.
2. **Un árbol de conocimiento derivado de los testigos.** El motor sabe qué compuertas ha presenciado
   cada personaje. Antes de abrir el beat de una deducción, pasa al director las premisas que al
   deductor le faltan. La escalera puede entregar una premisa, nunca la conclusión.
3. **Nada se revela antes de su evento.** Con SIM-2, se rechaza un `stage_event` que revele una
   compuerta cuyo evento no ha llegado.

**Cómo se mide.** Deducciones abiertas sin sus premisas (ninguna) y compuertas reveladas antes de
tiempo (ninguna). Y la comprobación de TD-4: cada hecho del que depende la solución tiene una cita
anterior.

**Ficha:** SIM-12, con SIM-1 (la solución en escena) y TD-4 (el plan).

## 7. El mundo como compañero de reparto

**Qué se ve.** Los cinco eventos del mundo que redactó el director en 7.1 fueron viento. Uno abrió
«la ventana» en un misterio de cuarto cerrado, contra la premisa. Otro, en `072847`, reveló una
compuerta antes de tiempo: «Una ráfaga de viento exterior hace golpear con violencia la ventana
abierta, arrojando al suelo un legajo de documentos oficiales que revela las firmas alteradas del
registro».

**Qué dice la investigación.**

- **La intervención se explica dentro de la ficción.** Ante una desviación se interviene o se
  acomoda, y la intervención debe tener sentido en el mundo (Riedl; ver
  [estado_del_arte_simulacion.md](estado_del_arte_simulacion.md)).
- **Un repertorio tipado, no una frase libre.** Los *storylets* reparten el contenido narrativo en
  piezas discretas con precondiciones, que se eligen según el estado (Kreminski y Wardrip-Fruin 2018).
- **El Game Master resuelve.** El de Concordia describe los efectos de las acciones y comprueba su
  plausibilidad física (Vezhnevets et al. 2023).
- **El mundo puede decidir tarde**, cuando hace falta, siempre que no contradiga lo establecido
  (*late commitment*, Swartjes y Theune 2008).

**Qué se propone.** Tipos cerrados de evento (llegada, hallazgo, objeto, sonido, interrupción,
entorno), impuestos por esquema como las tácticas. Un tipo no se repite en la obra, y el entorno no
puede entregar una cláusula. Se suma la validación de SIM-2 contra las compuertas futuras.

**Ficha:** SIM-6.

## 8. Voces que suenan igual

**Qué se ve.** La médica, la detective y el meteorólogo de `072847` hablan con el mismo registro culto
y nominal: «Las lecturas barométricas del señor Kessler padecen de una disparidad instrumental tan
evidente que resulta estéril intentar fundamentar ninguna cronología seria sobre ellas». Solo el
contrabandista («la chavala», «el viejo») y la hija («¡maldita sea!») se separan.

**Qué dice la investigación.**

- **La distinción se puede medir sin LLM.** Šeļa et al. (2023) proponen medidas de distinción del
  habla de personajes independientes del idioma: distancias *bootstrap* entre distribuciones de
  trigramas y curvas de palabras clave. Las probaron con 3.301 personajes de 2.324 obras en cuatro
  idiomas.
- **Los personajes se pueden separar.** Los modelos de verificación de autoría distinguen bien a los
  personajes entre sí (Michel et al., LaTeCH-CLfL 2024).
- **Las poblaciones simuladas colapsan.** Tienden a estereotipos, y los modelos con más fidelidad por
  persona producen las poblaciones más estereotipadas (*The Chameleon's Limit*, Xiao et al. 2026).
  ReverieMem llama a lo mismo «monotonía estilística».

**Qué se propone.** Medir antes de tocar: una cifra de distinción de voces por función, sobre el
habla de `turns.jsonl`, sin llamadas. Solo con esa cifra tiene sentido probar una intervención. Las
muestras de voz en el dossier están en Ideas, porque arriesgan la repetición de la sección 2.

**Ficha:** MED-7.

## 9. Quién cuenta qué en un misterio

**Qué se ve.** La voz por defecto es `omniscient` y narra los pensamientos de todos. En el primer
capítulo de `072847` el narrador ya le dice al lector:

- que Julian quiere evitar «que el médico o la archivista compararan las horas»: es la compuerta de
  la contradicción, que la detective deduce en el evento 4;
- que Tobias teme que sospechen «de su equipaje»: es la del engranaje, que se confiesa en el
  evento 3.

El misterio queda destripado antes de investigarse. De paso, «el médico» es la médica: el cambio de
género de SIM-5.

**Qué dice la investigación.**

- **El foco puede callar.** El criminal no puede ser nadie cuyos pensamientos conozca el lector
  (Knox 1929). Genette llama *paralipsis* a callar lo que el foco sabe: es un recurso legítimo del
  discurso, no una trampa.
- **La curiosidad exige que la respuesta no esté a la vista.** El suspense, la curiosidad y la
  sorpresa los produce el orden del discurso (Brewer y Lichtenstein 1982).
- **Sorpresa y coherencia a la vez.** Para un mismo lector se compensan, y el juego limpio pide las
  dos (Wagner et al. 2025).

**Qué se propone.** Una estrategia nueva en `stage/voices.py`: retiene los pensamientos de quien
está en `known_by` de una compuerta hasta el evento que la revela, y en lo demás se comporta como
`omniscient`.

- Se basa en las compuertas del casting, no en el texto libre de `StoryRequest.genre`, así que vale
  para cualquier historia con secretos.
- La alternativa más simple es `focalized` sobre quien investiga. Se decide con la lectura a ciegas.

**Cómo se mide.** Pensamientos narrados antes de su revelación que contienen una compuerta (MED-7), y
comparación a ciegas entre voces sobre la misma función.

**Ficha:** SIM-13.

## 10. Pensar menos para actuar mejor

**Qué se ve.** El actor corre con el pensamiento que el modelo trae por defecto: `runtime/provider.py`
no fija ningún presupuesto. Una sola llamada de actor de `070539` gastó 24.436 tokens de pensamiento,
55 s y el 10 % de los tokens del run (SIM-4).

**Qué dice la investigación.** Razonar no mejora el role-play y puede empeorarlo: el modelo olvida el
papel y adopta un estilo de informe (Feng, Dou y Kong 2025; Tang et al. 2025). El pensamiento que
interesa es el del canal `thought`, que pertenece al personaje, no el razonamiento oculto del modelo.

**Qué se propone.** Un presupuesto de pensamiento mínimo para el actor, medido con y sin él sobre el
mismo plan (EXP-5): coste, latencia, `script_echo`, entropía de tácticas y lectura a ciegas.

**Ficha:** SIM-4, EXP-5.

## 11. Métricas nuevas

Todas son deterministas y viven en `evaluation`, que solo lee disco:

- se pueden calcular sobre los runs ya generados, que es lo que da una línea base antes de cambiar
  nada;
- ninguna viaja a un prompt;
- son indicadores groseros para comparar versiones sobre el mismo plan, no una nota de calidad. La
  lectura a ciegas sigue mandando.

| Métrica | Qué mide | De dónde sale | ¿Runs 7.0 y 7.1? |
|---|---|---|---|
| Recuerdos por contexto (mediana y máximo) | cuánta memoria recibe el actor | `contexts.jsonl` | sí |
| Caracteres por contexto | tamaño del bloque variable del actor | `contexts.jsonl` | sí |
| Turnos con destinatario | si los personajes se hablan | `turns.jsonl` | sí |
| Turnos respondidos | si toma la palabra alguien a quien habló el anterior | `turns.jsonl` | sí |
| Notas repetidas | turnos que reciben la misma nota que en su turno anterior del beat | `turns.jsonl` | sí |
| Pensamientos de plan | pensamientos que empiezan por una fórmula de obligación o intención | `turns.jsonl` | sí |
| Eco de la nota | similitud entre el pensamiento y la nota que recibió el turno | `turns.jsonl` | sí |
| Mentiras y entropía de tácticas | engaño y variedad de tácticas por actor | `turns.jsonl` | 7.1 (en 7.0 las tácticas eran texto libre) |
| Distinción de voces | distancia entre las hablas de los personajes | `turns.jsonl` | sí |
| Pensamientos que destripan | pensamientos narrados con una compuerta antes de su evento | `story.md`, `cast_bible.json`, `turns.jsonl` | sí, aproximado |
| Deducciones sin premisas | deducciones abiertas sin sus premisas en la memoria del deductor | `cast_bible.json`, memoria | solo tras SIM-12 |

## 12. Orden de trabajo y cómo validarlo

**Orden sugerido:**

1. **SIM-9 y MED-7**, sin cuota. Arreglan el contexto del actor y fijan la línea base.
2. **SIM-10.** Casi todo es determinista, y se valida con el par de runs de SIM-1.
3. **SIM-1 y SIM-2**, que ya están en «Lo siguiente».
4. **SIM-6 y SIM-11:** el pensamiento, el terreno común y las mentiras.
5. **SIM-12 y SIM-13:** el misterio como caso de prueba del ritmo epistémico y del discurso.
6. **SIM-4**, medido dentro de EXP-5.

**Cómo validar:**

- **Mismo plan.** Con `--plan-from` (MED-5) y por versiones, para que la varianza del plan no tape
  la de la función.
- **No solo el prompt 03.** Todo lo observado aquí sale de misterios. Validar también con el 04
  (drama) y el 01 (fantasía), para no ajustar la función a un solo género.
- **Con n pequeño se leen indicios.** Una diferencia pequeña entre versiones no se interpreta, según
  el protocolo del `TODO.md`.

## 13. Lo que no se propone, y por qué

| Idea | De dónde | Por qué no |
|---|---|---|
| Ajuste fino de los actores | CoSER, AdaMARP, RAR, When2Speak | El pipeline usa Gemini por API; la tesis es de arquitectura, no de entrenamiento |
| Recuperación por embeddings | Generative Agents, BookWorld | Rompe el determinismo, y el problema medido es cuánto entra, no cómo se puntúa |
| Un actor global | Open-Theatre | Imposibilita las fronteras separadas que mide EXP-2 |
| Un superego por personaje | The Drama Machine | Duplica las llamadas; el canal de pensamiento y el director cubren ese papel |
| Un verificador LLM por turno | Rahmati y Zhao 2026 | Una llamada más por turno, cuando la comprobación contra compuertas puede ser determinista |
| Un árbitro de acciones físicas | Concordia | El guion ya fija lugar y reparto. Queda en Ideas por si aparecen incoherencias físicas |

---

## 14. Referencias

Las del marco general están en [marco_hibrido.md](marco_hibrido.md), y las que sostienen el diseño
actual, en [estado_del_arte_simulacion.md](estado_del_arte_simulacion.md). Estas son las propias de
este documento, todas comprobadas el 2026-09-26.

### Memoria y contexto largo

- Xu, J. et al. (2022). *Learning to Break the Loop: Analyzing and Mitigating Repetitions for Neural
  Text Generation*. NeurIPS 2022. <https://arxiv.org/abs/2206.02369>
- Liu, N. F., Lin, K., Hewitt, J. et al. (2024). *Lost in the Middle: How Language Models Use Long
  Contexts*. TACL 12. <https://aclanthology.org/2024.tacl-1.9/>
- Hong, K., Troynikov, A. y Huber, J. (2025). *Context Rot: How Increasing Input Tokens Impacts LLM
  Performance*. Informe técnico de Chroma. <https://www.trychroma.com/research/context-rot>
- Modarressi, A. et al. (2025). *NoLiMa: Long-Context Evaluation Beyond Literal Matching*. ICML 2025.
  <https://arxiv.org/abs/2502.05167>
- Laban, P. et al. (2025). *LLMs Get Lost In Multi-Turn Conversation*. <https://arxiv.org/abs/2505.06120>

### Conversación, turnos e improvisación

- Sacks, H., Schegloff, E. A. y Jefferson, G. (1974). *A Simplest Systematics for the Organization of
  Turn-Taking for Conversation*. Language 50(4).
  <https://www.cambridge.org/core/product/identifier/S0097850774121670/type/journal_article>
- Wei, J. et al. (2023). *Multi-Party Chat: Conversational Agents in Group Settings with Humans and
  Models* (MultiLIGHT). <https://arxiv.org/abs/2304.13835>
- Nama, V., Mendi, S., Ye, Z. y Bent, B. (2026). *When2Speak: A Dataset for Temporal Participation
  and Turn-Taking in Multi-Party Conversations for Large Language Models*.
  <https://arxiv.org/abs/2605.05626>
- Shaikh, O., Gligorić, K., Khetan, A. et al. (2024). *Grounding Gaps in Language Model Generations*.
  NAACL 2024. <https://aclanthology.org/2024.naacl-long.348/>
- Cho, H. y May, J. (2020). *Grounding Conversations with Improvised Dialogues*. ACL 2020.
  <https://aclanthology.org/2020.acl-main.218/>
- Johnstone, K. (1979). *Impro: Improvisation and the Theatre*. Libro.
- Magerko, B., Manzoul, W., Riedl, M. et al. (2009). *An Empirical Study of Cognition and Theatrical
  Improvisation*. Creativity and Cognition 2009. <https://dl.acm.org/doi/10.1145/1640233.1640253>
- Mathewson, K. W. y Mirowski, P. (2017). *Improvised Theatre Alongside Artificial Intelligences*.
  AIIDE 2017. <https://ojs.aaai.org/index.php/AIIDE/article/view/12926>

### Pensamiento, subtexto y teoría de la mente

- Wang, X., Wang, H., Zhang, Y. et al. (2025). *CoSER: A Comprehensive Literary Dataset and Framework
  for Training and Evaluating LLM Role-Playing and Persona Simulation*. ICML 2025.
  <https://arxiv.org/abs/2502.09082>
- Feng, X., Dou, L. y Kong, L. (2025). *Reasoning Does Not Necessarily Improve Role-Playing Ability*.
  Findings ACL 2025. <https://aclanthology.org/2025.findings-acl.537/>
- Tang et al. (2025). *Thinking in Character: Advancing Role-Playing Agents with Role-Aware
  Reasoning*. NeurIPS 2025. <https://arxiv.org/abs/2506.01748>
- Ahuja, K., Li, Y. y Lampinen, A. K. (2026). *Beneath the Surface: Investigating LLMs' Capabilities
  for Communicating with Subtext*. <https://arxiv.org/abs/2604.05273>
- Gu, Y., Tafjord, O., Kim, H. et al. (2026). *SimpleToM: Exposing the Gap between Explicit ToM
  Inference and Implicit ToM Application in LLMs*. ICLR 2026. <https://arxiv.org/abs/2410.13648>
- Sclar, M. et al. (2023). *Minding Language Models' (Lack of) Theory of Mind: A Plug-and-Play
  Multi-Character Belief Tracker*. ACL 2023. <https://aclanthology.org/2023.acl-long.780/>
- Magee, L., Arora, V., Gollings, G. y Lam-Saw, N. (2024). *The Drama Machine: Simulating Character
  Development with LLM Agents*. <https://arxiv.org/abs/2408.01725>
- Xu, Z., Chen, D., Wang, S. et al. (2026). *AdaMARP: An Adaptive Multi-Agent Interaction Framework
  for General Immersive Role-Playing*. Findings ACL 2026. <https://arxiv.org/abs/2601.11007>

### Oposición, engaño y estatus

- Yi, Z., Jiang, Q., Ma, R. et al. (2025). *Too Good to be Bad: On the Failure of LLMs to Role-Play
  Villains*. Findings ACL 2026. <https://arxiv.org/abs/2511.04962>
- Jun, Y., Choi, J., Park, J. et al. (2026). *Identifying and Mitigating Bottlenecks in Role-Playing
  Agents: A Systematic Study of Disentangling Character Profile Axes*.
  <https://arxiv.org/abs/2601.04716>
- Zhang, X., Xu, Z., Luo, H. et al. (2026). *ANIMASK: What the Model Contributes to Role Play in
  Simulated Story Worlds*. <https://arxiv.org/abs/2609.16667>
- Sharma, M., Tong, M., Korbak, T. et al. (2024). *Towards Understanding Sycophancy in Language
  Models*. ICLR 2024. <https://arxiv.org/abs/2310.13548>
- Ware, S. G. y Young, R. M. (2011). *CPOCL: A Narrative Planner Supporting Conflict*. AIIDE 2011.
  <https://ojs.aaai.org/index.php/AIIDE/article/view/12428>
- de Lima, E. S., Casanova, M. A., Feijó, B. y Furtado, A. L. (2025). *Characterizing the
  Investigative Methods of Fictional Detectives with Large Language Models*.
  <https://arxiv.org/abs/2505.07601>
- Cai, Y., Gu, Z., Du, Z. et al. (2025). *MIRAGE: Exploring How Large Language Models Perform in
  Complex Social Interactive Environments*. ACL 2025. <https://aclanthology.org/2025.acl-short.2/>

### Misterio y ritmo epistémico

- Shirvani, A., Farrell, R. y Ware, S. G. (2018). *Combining Intentionality and Belief: Revisiting
  Believable Character Plans*. AIIDE 2018. <https://ojs.aaai.org/index.php/AIIDE/article/view/13037>
- Ware, S. G. y Siler, C. (2021). *Sabre: A Narrative Planner Supporting Intention and Deep Theory of
  Mind*. AIIDE 2021. <https://ojs.aaai.org/index.php/AIIDE/article/view/18896>
- Sprague, Z. et al. (2024). *MuSR: Testing the Limits of Chain-of-thought with Multistep Soft
  Reasoning*. ICLR 2024. <https://arxiv.org/abs/2310.16049>
- Wagner, E., Keydar, R. y Abend, O. (2025). *The Challenge and Reward of Fair Play in Narrative: A
  Computational Approach*. <https://arxiv.org/abs/2507.13841>
- Rahmati, P. y Zhao, R. (2026). *Enforcing Narrative Reliability and Epistemic Pacing in LLM-Driven
  Detective Games via Structured Knowledge Trees*. <https://arxiv.org/abs/2609.23043>
- Knox, R. (1929), Van Dine, S. S. (1928) y Todorov, T. (1966): ver
  [marco_hibrido.md](marco_hibrido.md).

### Mundo, voces y discurso

- Kreminski, M. y Wardrip-Fruin, N. (2018). *Sketching a Map of the Storylets Design Space*. ICIDS
  2018. <https://link.springer.com/chapter/10.1007/978-3-030-04028-4_14>
- Vezhnevets, A. S. et al. (2023). *Generative Agent-Based Modeling with Actions Grounded in Physical,
  Social, or Digital Space using Concordia*. <https://arxiv.org/abs/2312.03664>
- Šeļa, A., Nagy, B., Byszuk, J. et al. (2023). *From Stage to Page: Language Independent Bootstrap
  Measures of Distinctiveness in Fictional Speech*. <https://arxiv.org/abs/2301.05659>
- Michel, G., Epure, E. V., Hennequin, R. y Cerisara, C. (2024). *Distinguishing Fictional Voices: a
  Study of Authorship Verification Models for Quotation Attribution*. LaTeCH-CLfL 2024.
  <https://arxiv.org/abs/2401.16968>
- Xiao, Y., Zhang, V. J., Yang, C. et al. (2026). *The Chameleon's Limit: Investigating Persona
  Collapse and Homogenization in Large Language Models*. <https://arxiv.org/abs/2604.24698>
- Brewer, W. F. y Lichtenstein, E. H. (1982). *Stories Are to Entertain: A Structural-Affect Theory of
  Stories*. Journal of Pragmatics 6.
  <https://www.sciencedirect.com/science/article/abs/pii/0378216682900212>

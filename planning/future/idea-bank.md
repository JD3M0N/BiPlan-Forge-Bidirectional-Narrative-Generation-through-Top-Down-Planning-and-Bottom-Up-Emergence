# Banco de ideas

Lo que no entra en ninguna fase de la tesis. Nada de aquí se ejecuta sin pasar antes por
una tarjeta del [roadmap](../roadmap.md). Una idea no lleva ID; lo recibe al subir. Las fichas
con ID conservan el del antiguo `TODO.md`.

## Trabajo posterior a la tesis (el tutor)

- **El juez como función objetivo** [06:21–07:43]: generar N historias con distintas
  combinaciones de parámetros y devolver la mejor; después, un algoritmo genético sobre los
  parámetros. Es la recomendación para el trabajo siguiente, no parte de esta tesis.

## Ingeniería aplazada

### MED-6b · Códigos propios en los warnings de los runs

*Área:* medición · *Cuota:* sin cuota · *Depende de:* una decisión que descongele el generador

- **Síntoma.** Los warnings de `metadata.json` son texto libre, sin campo de código: un
  inventario no puede agruparlos sin leer frases.
- **Qué hacer.** Darles código propio en la próxima subida de `PIPELINE_VERSION`.
- **Por qué está aquí.** Salió de MED-6 al escribir las tarjetas de P03 (2026-10-28): exige subir
  `PIPELINE_VERSION`, y el generador está congelado en 7.22 (`decisions.md` §3).

### ING-3 · Dividir `pipeline.py`

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.**
  - `pipeline.py` tiene 671 líneas; las etapas ya viven en mixins de planificación, escritura,
    guion, actuación y narración. La telemetría está en `runtime/reporting.py`.
  - Los mixins comparten estado mediante `self`; el repositorio opcional sigue obligando a
    comprobar su presencia antes de utilizarlo.
  - Falta convertir las etapas en unidades con estado y pruebas propios.
- **Qué hacer.**
  - El bucle de reintento ya está en `writing/revision_loop.py` (7.18). El del narrador
    (`stage/stages.py`) se queda aparte a propósito: tiene revisión editorial, candidato
    reservado y su propia severidad.
  - Al final, convertir las etapas en clases con estado propio, que es lo que elimina los asserts.
  - No hacerlo de paso dentro de otro cambio.
- **Hecho cuando.**
  - Plan, borrador, revisión y función son unidades con test propio.
  - El estado deja de pasarse como parámetros posicionales.
  - Los artefactos generados no cambian.

### ING-5 · CI, tipos y dependencias

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.**
  - **CI solo prueba una plataforma.** Corre solo en `windows-latest` con Python 3.12. Desde
    7.21.2 el mínimo declarado es 3.12, así que CI sí cubre la versión mínima, pero 3.15,
    que `setup.ps1` acepta y tiene sus propias restricciones, no se comprueba nunca.
  - **Sin tipos ni cobertura en CI.** No hay paso de comprobación de tipos ni informe de
    cobertura en el workflow de calidad.
  - **Dependencias.** Las cotas internas se alinearon en 7.21.2 con la minor vigente de cada
    paquete; nada comprueba que no vuelvan a quedarse atrás.
- **Qué hacer.**
  - Ampliar la matriz de CI a Linux y a 3.15, con su archivo de restricciones.
  - Añadir pyright o mypy, empezando por `core`.
  - Informar de la cobertura, sin umbral al principio.
  - Un test o un paso de CI que falle si una cota interna queda por debajo de la minor instalada.
- **Hecho cuando.** CI prueba las dos versiones de Python que `setup.ps1` acepta, y una
  dependencia interna demasiado vieja falla al instalar, no al importar.

### ING-10 · Lo que queda por trocear de la función

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* ING-3

- **Síntoma.** La limpieza de 7.21.2 partió los dos módulos de esquemas en paquetes por
  secciones y dejó identificados los que siguen siendo demasiado grandes:
  - `stage/engine.py`, 1650 líneas: `PerformanceEngine` tiene 41 métodos, un `__init__` de
    107 líneas y un `_play_turn` de 175. Los métodos agrupan solos en turno, mundo y
    arbitraje, derivación de hechos, memoria y estancamiento.
  - `runtime/provider.py`, 1354 líneas: contexto y errores, los dos clientes concretos y la
    composición (`RoutedProvider`, `FailoverProvider`, la factoría) no se tocan entre sí.
  - `stage/stages.py`, 1076 líneas: `_perform_play` ocupa 248 y el bloque de revisión del
    futuro, otras 200 seguidas.
  - `BeatCheckDraft.world_effect` no lo lee nadie, pero viaja al director como JSON schema:
    retirarlo cambia lo que ve el modelo.
- **Qué hacer.** Trocear por esas costuras, con el patrón de mixins que el paquete ya usa, y
  retirar el campo muerto en la misma subida de `PIPELINE_VERSION`. Después de ING-3, no a la
  vez: las etapas con estado propio cambian dónde cae cada corte.
- **Hecho cuando.** Ningún módulo de la función pasa de 700 líneas, los artefactos no cambian
  salvo el campo retirado, y el par medido lo confirma.

## Generador (aplazado en P02)

Fichas que P02 no eligió al congelar el generador (2026-10-27). Cambiar cualquiera
toca el generador congelado: necesita una decisión nueva en `decisions.md`. SIM-26
(`typed_clauses`) y SIM-13 (voz) pueden volver como niveles del análisis horizontal de P05.

### ING-1 · Docstrings plantilla que no dicen nada

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* decisión sobre el generador congelado

- **Estado.** P01.3 reescribió 39 docstrings y el gate ya rechaza las plantillas. Quedan 12 clases
  Pydantic con «Represent X data and behavior»: `StoryRequest`, `WorldArtifact`, `Location`,
  `StoryObject`, `CharactersArtifact`, `CharacterProfile`, `CharacterRelationship`,
  `StoryPlanDraft`, `PlotEvent`, `EventDependency`, `StoryReview` y `ConstraintCheck`.
- **Por qué siguen.** Se envían a Gemini como esquema de respuesta y su docstring es la
  `description` que lee el modelo; reescribirlas cambia su entrada. Están en la lista
  `SCHEMA_DESCRIPTIONS_SENT_TO_MODEL` del test.
- **Qué hacer.** Si se decide cambiar esas descripciones, hacerlo en P02 con medición real y vaciar
  la lista del test.
- **Hecho cuando.** La lista del test está vacía.

### SIM-1 · La solución del caso nunca llega a escena

*Área:* función simulada · *Cuota:* ~220 llamadas (un par de runs, compartido con SIM-2) ·
*Depende de:* —

- **Síntoma.** En los dos runs 7.1 (`Stagecraft/20260926-070539-*` y `20260926-072847-*`) el
  último beat se dio por alcanzado sin que nadie dijera en escena la solución. En `072847` el
  narrador la inventó, y la auditoría lo marcó con severidad 4. La causa va más allá de que falte
  una comprobación:
  - **La solución estaba escrita y se tiró.** El `brief.json` del clímax trae en `scripted_lines`
    la respuesta literal: «Utilizó una barra auxiliar desmontable para deslizar el pestillo
    interno desde el exterior…». Ese campo solo alimenta `script_echo` y nunca llega al director.
  - **El director juzga solo el `outcome` del evento.** En `072847` ese `outcome` es circular
    («The mystery is solved, revealing the method, motive…»), y el director parte las cláusulas
    por su cuenta.
  - **Nada ata una compuerta a su beat.** `_scene_briefs` (`stage/stages.py`) da a cada escena
    todas las compuertas, y `revealed_at_event_id` solo se valida en el casting. `072847` ni
    siquiera tenía compuerta para la solución: sus tres eran el registro, el engranaje y la
    contradicción.
  - **El narrador recibe `PROMISE OBLIGATIONS`** (`agents/narrator.py`), lo que contradice que el
    log sea la única fuente. La solución inventada de `072847` parafrasea el pago del ledger
    («desmanteló el mecanismo… huyó hacia la tormenta»). Y ese pago contradice la solución del
    guion: el pestillo deslizado desde fuera.
  - **`promise_audit.json` audita el guion, no la función.** Cita cosas como «MARA VELA.—(analítica)…»
    y da 2/2 cumplidas en todos los runs simulados.
- **Qué hacer.**
  1. Derivar las cláusulas obligatorias de cada beat, en vez de dejar que el director las elija.
     Salen de las compuertas con `revealed_at_event_id` en ese evento y de las réplicas clave del
     guion. Solo las ve el director, que ya guarda el guion: los actores siguen sin verlo, y la
     nota sigue dando motivos, no réplicas.
  2. Que el casting exija una compuerta para el pago de la promesa primaria, revelada en el
     clímax.
  3. Quitar `PROMISE OBLIGATIONS` del narrador. En su prompt, fijar que una pregunta que el log
     deja abierta se queda abierta.
  4. En el formato simulado, auditar las promesas contra `story.md`.
- **Medido en 7.2.** El par de 7.2 mejora esto sin cerrarlo. Las tres compuertas del prompt 03
  **sí** se dijeron en escena (la solución, en `chap_3-scene-2-t004`: «Fui yo quien ajustó el
  pasador desde fuera con esa pieza»), y el narrador no inventó ninguna: 93,33 y 95,0 de fidelidad
  frente a 81,67 y 78,33. Lo que sigue sin ocurrir es lo que pide el primer «Hecho cuando»:
  **ninguna** compuerta aparece citada como prueba en `director.jsonl`, porque las cláusulas
  siguen saliendo del `outcome` del evento y no de la compuerta. Y la solución llegó por confesión
  de la hija, no por la deducción que decía su `how` (ver TD-4 y SIM-11).
- **Medido en 7.8** (`20261009-185923`, prompt 03). Los puntos 1 y 4 están a medias: las
  compuertas ya entran como cláusulas obligatorias (`required_gates`), pero casi nunca casaban
  (cerrado en 7.9); y `promise_audit.json` ya audita la función (`"source": "performance"`, con turnos
  citados). El caso, otra vez, no se resuelve:
  - `promise_audit.json` da **0 de 2** promesas pagadas, y el director da el clímax por alcanzado
    («The engineering method is fully explained…», `shown=true`) citando turnos donde Mara afirma
    «un plan de huida», Elena dice que su padre «desapareció en el mar» y el médico, que «solo
    quería morir». Los dos jueces del mismo run se contradicen.
  - **El mecanismo lo demuestra el mundo, no la deducción:** el `stage_event` del clímax es «El
    pestillo de la puerta principal, liberado por el engranaje, cae con un golpe seco…».
  - El narrador no inventó la solución: la deja abierta, como pide el punto 3.
- **Medido en 7.9** (`20261009-200848`, replay del faro). `promise_audit.json` da **2 de 2**, y
  las cuatro compuertas se citan como prueba en `director.jsonl`. Pero el clímax sigue
  necesitando al mundo (SIM-2), y la deducción de Mara no se ha leído entera: falta comprobar
  con la auditoría que no hay revelaciones inventadas.
- **Hecho cuando.** En un par nuevo de runs:
  - cada compuerta que se revela en el último beat aparece en un turno citado como prueba en
    `director.jsonl`;
  - la auditoría no encuentra ninguna revelación inventada;
  - `promise_audit.json` cita la historia.
- **Ojo.**
  - El juez de narración solo ve el log y marca como inventado lo que viene de la petición (la
    tormenta, la isla). Pasarle la premisa antes de leer su cifra.
  - Vigilar el `script_echo` del clímax, hoy 0,026 y 0,036: si se dispara, el director está
    dictando.

### SIM-2 · El mundo entrega la trama

*Área:* función simulada · *Cuota:* se valida con el par de SIM-1 · *Depende de:* —

- **Síntoma.** Cuando un beat se atasca, el `stage_event` hace más de lo que la escalera le
  pide: revela compuertas antes de su evento, trae motivos y demuestra lo que alguien debía
  deducir.
  - En `072847` (7.1), `chapter_1-scene-2`: «…revela las firmas alteradas del registro», que
    estaba programada como deducción de Mara en el evento 4.
  - En `163733` (7.2), el evento del capítulo 1 «hizo saltar el pestillo oxidado de la puerta
    interior», que es la compuerta de `event_5`. De paso destruyó la prueba del cuarto cerrado.
  - En `213245` (7.2), un repartidor trajo un sobre «que detalla la quiebra simulada por Víctor
    Cárdenas»: el motivo del misterio, por correo.
  - En el faro 7.8 (`185923`), «un sobre abierto con el sello de un banco que confirma la fecha
    exacta de la alteración», y en el clímax «el pestillo… liberado por el engranaje, cae».
  - **En el faro 7.9 (`200848`) sigue:** el único evento del mundo es el del clímax, «una sección
    de la pared exterior del faro cede… revelando una nota de cobro… que el farero dejó».
  - **La confesión sustituye a la investigación**, que el prompt prohíbe. En `072847` la
    compuerta del engranaje tiene `how=confession`.
- **Hecho ya (7.3–7.9).** Las cláusulas se congelan en la primera lectura (`_clauses`), y en 7.9
  casan por clave. Las notas, las cláusulas, la coda y la nota de reserva del director están en
  el idioma de la ficción: 0 de 35 y 0 de 38 notas en inglés en el par 7.9, frente a 14 de 38 y
  36 de 42 en 7.8.
- **Qué hacer.**
  - Rechazar un `stage_event` que revele una compuerta cuyo evento no ha llegado, con el mismo
    mecanismo de reintento que el resto.
  - Fijar en el contrato del `stage_event` que el mundo entrega **una** cláusula que falta, nunca
    un motivo, una identidad, una confesión ajena ni una deducción: lo que se sabe se sigue
    jugando en escena.
  - Que el casting no programe como confesión una compuerta que la petición exige deducir.
- **Hecho cuando.** En el par de SIM-1 ninguna compuerta se revela antes de su evento, y ningún
  evento del mundo aporta un hecho que no sea la cláusula que faltaba.

### SIM-22 · Los nativos no conocen su propio mundo

*Área:* función simulada · *Cuota:* ~120 llamadas (un run simulado) · *Depende de:* TD-9

- **Síntoma.**
  - En los navegantes, la exploración apenas enseña Zéfara. Aleth y Hanu, que son zefaríes,
    no tienen en `knows` las costumbres de su pueblo (moneda de gotas, Ley del Suelo, Archivo).
  - El director empujó a Gaspar a vender «cuentas de vidrio» como si no fueran ya la moneda
    (`stage/chapter_2-scene-1/contexts.jsonl`).
  - No hay ningún nativo de reparto (mercader, caído, mensajero) que enseñe la isla.
- **Hecho en 7.16.** El prompt del casting pide las costumbres del lugar en el
  `initial_knowledge` de quien es de allí. Sin medir: en `20261017-184641`, Hanu cita la Ley del
  Suelo y Aleth el Archivo, pero nadie revisó escena a escena.
- **Qué falta.**
  - Medir el «Hecho cuando» en los dos runs 7.16 (`20261017-182756`, `184641`).
  - Que las escenas de exploración tengan quien las enseñe.
- **Hecho cuando.** En un run de los navegantes, cada escena de exploración trae al menos un
  turno de un nativo que explica o usa una costumbre de `world.json`, sin contradecirla.

### SIM-26 · Validar las cláusulas por tipo y el casting de 7.17 en una función completa

*Área:* función simulada · *Cuota:* ~600 llamadas (2 runs por brazo, perfil Desarrollada) ·
*Depende de:* SIM-25

- **Síntoma.**
  - Se forzaron 22 de 63 beats en 7.12–7.16: 11 eran desenlaces físicos o de viaje y 3
    necesitaban a alguien ausente. El final se forzó en 6 de 10 runs.
  - El casting le dio a Ilse, todavía en alta mar, el resultado del segundo evento.
  - El 57 % de los turnos ordenan, exigen o amenazan.
  - Las notas de giro dictaban: «cede ante la evidencia».
  - 7.17 añade `typed_clauses`, y siempre activos la fuente del conocimiento inicial,
    `cover_story`, `TACTIC_RUN` y las notas con cita.
- **Qué hacer.** Dos runs de los navegantes con `--brief` (el `brief.json` de `20261015-174818`)
  y `--profile developed`, con y sin `--typed-clauses`, y el narrador que gane SIM-25. Contar:
  - beats forzados y finales en escena;
  - `[CAST_FACT_DROPPED]` y `TACTIC_RUN` en `rejected.jsonl`;
  - notas sustituidas por la de reserva en `director.jsonl`.
- **Hecho cuando.**
  - Bajan los beats forzados por desenlaces de viaje frente a 7.16.
  - El descenso ocurre en escena.
  - Hay una decisión escrita sobre `typed_clauses`.
- **Ojo.** Con dos runs por brazo no se separa del ruido de la función: es indicio, no medida.

### SIM-4 · Los timeouts de actor se comen entre un cuarto y dos tercios del reloj

*Área:* función simulada · *Cuota:* ~110 llamadas · *Depende de:* —

- **Síntoma.**
  - **Las llamadas buenas son rápidas y el timeout es enorme.** Una llamada de actor que funciona
    tarda una mediana de 1,3 a 1,6 s. El único timeout es el global `GEMINI_REQUEST_TIMEOUT_MS`:
    120 s, pensados para la prosa larga.
  - **Los timeouts dominan el reloj.** Los 504 y `ReadTimeout` fueron el 28 % del reloj en
    `070539`, el 50 % en `072847` y el 64 % en `054422`. El primer racimo cae siempre en las cinco
    primeras llamadas de actor.
  - **Un turno estuvo a punto de perderse.** En `072847` salió en el intento 4 de 4: un fallo más
    y se perdía.
  - **Un pensamiento desbocado.** Una sola llamada de actor de `070539` gastó 24.436 tokens de
    pensamiento: 55 s y el 10 % de los tokens del run.
- **Qué hacer.**
  - Un timeout propio y corto para actor, director y reflexión.
  - Un presupuesto de pensamiento mínimo para el actor, medido con y sin él sobre el mismo plan
    (EXP-5). La literatura dice que razonar no mejora el role-play y puede empeorarlo
    (`docs/resumen.md` §10).
- **Medido en 7.2.** Mucho menos grave que en 7.1, pero sigue ahí: 2 intentos 504 por run, y el
  reloj (951 y 825 s) deja 100 y 49 s sin explicar sobre la suma de latencias más las esperas. Los
  runs bajaron a 14–16 minutos, frente a los 17–31 de 7.0 y 7.1. Un `ConnectError` de red mató
  además un run entero del prompt 07 (`20260927-170152-*`) tras 19 fallos seguidos: el aviso que
  quedó, `ACTOR_CALL_FAILED | ProviderError`, no dice qué error fue, porque `_reject` guarda
  `type(exc).__name__` y no el código que sí está en `llm_calls.jsonl`.
- **Medido en 7.6–7.8.** Casi resuelto por el modelo de la función (`gemini-3.1-flash-lite`):
  cero tokens de pensamiento en todas las llamadas, actor con mediana de 1,9 a 3,3 s y máximo de
  23 a 43 s, y ningún error en el par 7.8 (`184753`, `185923`). Quedan 2 y 10 errores 503 en
  `150355` y `153026`, y una llamada de actor de 119 s en `153026`: el timeout sigue siendo el
  global de 120 s (`GEMINI_REQUEST_TIMEOUT_MS`).
- **Hecho cuando.** En un run simulado nuevo, leído en su `llm_calls.jsonl`, el reloj se acerca a la
  suma de latencias con éxito más las esperas de cuota, ninguna llamada de actor pasa de su
  timeout, y un turno rechazado por el proveedor deja en `rejected.jsonl` el código del fallo.

### SIM-5 · El narrador desfigura el log

*Área:* función simulada · *Cuota:* se valida con el par de SIM-1 · *Depende de:* TD-2

- **Síntoma.** Lo que salió de leer enteras las dos historias 7.1:
  - **Cambia el género** que el log respeta: «El doctor Mendoza», seis veces, en `072847` (ver
    TD-2).
  - **Borra la pista clave y la adelanta.**
    - En el log de `070539` la médica va a «la pequeña ventana que da al mar», que es la
      solución. La historia dice «la pequeña puerta del dormitorio», y la auditoría lo marcó con
      severidad 4.
    - El capítulo 1 ya la había destripado en un pensamiento: «cómo pudo salir su padre por la
      ventana».
  - **Costuras rotas.**
    - Una réplica aparece sin atribuir, como narración («Las diez de la noche en su informe y las
      doce en el suyo…»).
    - El mismo personaje habla dos veces seguidas al perderse la costura entre escenas.
    - El tiempo verbal salta («apartó… y despliega»), y «Rupert» convive con «Ruperto».
  - **Un capítulo es transcripción desnuda.** En `070539` hay uno con 14 pares de gesto y réplica
    y «Mara Vela» nueve veces.
- **Qué hacer.**
  - Dar al narrador la `public_face` de cada personaje, como ya la tienen los actores.
  - Comprobar de forma determinista, antes de aceptar un capítulo, que todo nombre propio del
    texto pertenece al reparto o al mundo, y que los turnos marcados `[clave]` tienen reflejo en
    la prosa.
  - Lo que falle vuelve como corrección, como en el Writer.
- **Medido en 7.8.** En el faro (`185923`) la médica del prompt vuelve a ser un hombre, «el doctor
  Aris», y la hija, otra vez, «Elena» (TD-2, TD-7). El cambio ya viene del reparto, no del
  narrador. Además:
  - una acotación del mundo pasa a la prosa tal cual, entre paréntesis;
  - los nombres de utilería entran literales («la Espada de Aldren», «el Diario de
    Investigaciones de Elara»);
  - los pensamientos se narran como «Mara Vela pensaba que necesitaba comprobar…»;
  - `dialogue_survival` es 1,0 en los dos runs 7.8: el narrador transcribe.
- **Medido en 7.12.1** (`20261013-145340-el-compartimento-cerrado`): `dialogue_survival` 0,94;
  los dos capítulos reproducen turno a turno, y el segundo en presente con «—dice Inés» tras
  cada réplica, el formato del narrador de respaldo. El presente ya se rechaza
  (`WRONG_TENSE`); la transcripción no, porque bloquearla mandaría a reintento casi todo
  capítulo. Además, el capítulo 1 se titula como la historia («El compartimento cerrado» dos
  veces seguidas, como en 6 historias Top-Down): no se toca de paso, porque los encabezados
  `##` son los que `parse_chapter_bodies` y los lectores de evaluación usan para partir capítulos.
- **Hecho cuando.** En el par de SIM-1 no hay nombres fuera del reparto ni cambios de género, y la
  auditoría no marca ninguna pista clave eliminada.

### SIM-6 · La función casi no tiene subtexto, susurros ni variedad

*Área:* función simulada · *Cuota:* ~220 llamadas · *Depende de:* SIM-2

- **Síntoma.**
  - **Casi todo turno trae pensamiento, y casi siempre es un plan.** Entre el 94 y el 98 % de los
    turnos lo traen en los cuatro runs simulados completos. Tras vaciar el eco en 7.1, los que
    quedan repiten la intención o traducen la nota del director (SIM-2): entre el 35 % (`070539`) y
    el 62 % (`072847`) empiezan por «debo», «tengo que», «necesito» o «exijo».
  - **Cero susurros, y no por falta de ocasión.** Un susurro exige destinatario, y el actor no puede
    nombrar a nadie: el esquema le pedía ids que nunca veía. Arreglado en 7.2.0, y el par de
    7.2 dio el primer susurro del corpus: 1 en un run y 0 en el otro, así que sigue siendo raro.
  - **Una sola táctica domina.** `deflect` es el 38 % de los turnos: 30 de 80.
  - **El mundo solo sabe hacer viento.** Los cinco eventos del mundo que redactó el director en
    7.1 fueron viento. Uno abrió «la ventana» en un misterio de cuarto cerrado, contra la premisa.
- **Qué hacer.**
  - Pedir pensamiento solo cuando contradice lo que se dice, y definirlo como lo que el personaje
    nota, teme o calla, nunca lo que planea.
  - Vaciar el pensamiento que repite la nota o el objetivo, como ya se vacía el que repite el habla
    (`THOUGHT_ECHO` en `normalize_turn`).
  - Dar al actor qué no presenció cada uno de los que tiene delante, derivado de los testigos de su
    memoria: terreno común explícito, sin tocar el plan.
  - Dejar que el director pida un aparte; el destinatario ya existe desde 7.2.0.
  - Pasar al director el tipo de recurso usado (clima, llegada, objeto, sonido) y rechazar un
    segundo evento del mismo tipo.
- **Medido en 7.2.** `thought_ratio` bajó a 0,91 y 0,92 desde 0,94–0,98, pero los pensamientos de
  plan subieron a 0,44 y 0,64. Hubo **1 susurro** en `163733` y ninguno en `213245`, así que el
  canal ya existe pero casi no se usa. Las tácticas siguen concentradas: `deflect` 12 de 43 en uno
  y `demand` 20 de 51 en el otro. Los eventos del mundo del prompt 03 fueron los dos viento; los
  del 07, tres recursos distintos (ver SIM-2).
- **Medido en 7.4–7.8.** **Peor que en 7.2:** `thought_ratio` es 1,0 en las seis funciones, aunque
  el esquema (`ActorTurnDraft.thought`) ya dice «déjalo vacío salvo que difiera». Los que
  empiezan por «debo» o «necesito» bajaron (6 de 41 y 6 de 42 en 7.8), pero el resto narra el
  estado en vez de callar algo: «Aldren ha caído en la cuenta. Ahora debo asegurarme…». El actor
  ve sus propios pensamientos anteriores en «LA ESCENA HASTA AHORA», y eso modela el patrón.
  Susurros: 0 y 1 en el par 7.8, y en `151512` son susurros con solo dos personajes en escena.
  Los eventos del mundo ya no son siempre viento.
- **Medido en 7.12.2** (`20261013-180025`). `thought_ratio` 0,95, y solo 2 de 82 pensamientos
  comparten más del 30 % de palabras con su habla o su acción: no son ecos, así que
  `THOUGHT_ECHO` no los toca. Son intenciones («Debo impedir que…», «Si no…»), y el narrador las
  convierte en coletillas (SIM-23).
- **Medido en 7.14.** `thought_ratio` 0,98 aunque el actor ya no relee sus pensamientos; solo 7
  de 48 son planes, y 7.15 los vacía en `normalize_turn` como a los ecos.
- **Hecho cuando.** Un par de runs:
  - baja `thought_ratio` claramente de 0,9, y bajan los pensamientos de plan que mide MED-7;
  - tiene al menos un susurro que la ablación pueda medir;
  - no repite tipo de evento del mundo.
- **Ojo.** El porqué de cada punto, con su respaldo, está en `docs/resumen.md` §4 y §7.

### SIM-23 · El narrador cierra cada párrafo con la intención del personaje

*Área:* función simulada · *Cuota:* ~20 llamadas (la narración de un run guardado) ·
*Depende de:* SIM-6

- **Síntoma.**
  - En los capítulos 4 y 5 de `20261013-180025-las-islas-del-cielo`, casi cada párrafo acaba
    con un pensamiento contado: «convencido de que…», «decidido a…», «sabiendo que…».
  - Es la intención del pensamiento del actor (SIM-6), pasada a prosa. Lo narró 3.1, pero el
    prompt del narrador ya dice que no ponga un pensamiento a cada línea.
- **Qué hacer.**
  - Medir esa coletilla en `writing/craft_evidence.craft_notes`, como ya se miden los nombres
    repetidos y los símiles.
  - Pasarla como nota al segundo intento del narrador. No debe ser motivo de rechazo editorial:
    7.12 prohíbe rechazar por un hallazgo leve.
- **Hecho cuando.** Re-narrar ese run guardado da menos de un párrafo de cada cinco cerrado con
  una intención, sin capítulos de respaldo.
- **Medido en 7.14** (`20261014-195514`): 0 coletillas. El problema pasó a ser otro: el
  narrador transcribe (18 de 18 réplicas copiadas, 16 de 18 con «dijo»). 7.15 lo mide
  (`craft_findings`) y repite el capítulo una vez con la nota; falta medirlo en real.
- **Medido en 7.15.1** (`20261015-151839`): `dialogue_survival` 1,0 y 13 de 15 réplicas con
  acotación en el capítulo 3. Los segundos intentos con notas no mejoraron y se descartaron: la
  nota no basta, porque el narrador copia lo que recibe.

### SIM-7 · Reanudar una función interrumpida

*Área:* función simulada · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.**
  - Una función son unas 100 llamadas, y si el proceso muere se pierde entera.
  - `054422` es el caso real: murió por cuota en la escena 5 de 6 con cuatro escenas completas en
    `stage/*/turns.jsonl`, y con el guion y `cast_bible.json` ya escritos.
  - Además, `_perform_play` escribe `memory/*/records.json` solo al acabar todas las escenas: las
    memorias intermedias no están en disco.
- **Qué hacer.**
  - Persistir las memorias al cerrar cada escena.
  - Al reanudar, leer las escenas completas, reconstruir memorias y estados, y seguir desde la
    primera escena que falte.
  - Que `asg-recover` ofrezca reanudar, además de cerrar o descartar.
- **Hecho cuando.** Un run simulado interrumpido se retoma sin repetir ninguna llamada ya hecha, y
  hay un test con un proveedor falso que muere a mitad de la obra.

### SIM-8 · Aplicar las notas del crítico a la prosa narrada

*Área:* función simulada · *Cuota:* ~110 llamadas · *Depende de:* SIM-5

- **Síntoma.** En el formato simulado la crítica dramática no corre: la historia se publica tal
  como la narró el narrador. Se decidió así porque reescribir sin el log delante alejaría la prosa
  de lo que se representó, que es justo lo que el formato quiere demostrar.
- **Qué hacer.**
  - Pasar al Writer el log de las escenas del capítulo junto con la nota.
  - Validar la reescritura contra el log, como se valida un acto contra el plan: una reescritura
    que invente un beat que nadie representó se rechaza.
- **Hecho cuando.** Una historia simulada se puede revisar sin que la revisión introduzca sucesos
  ausentes del log, y hay un test del camino.

### SIM-11 · Los sospechosos no mienten

*Área:* función simulada · *Cuota:* ~220 llamadas (un par de misterio) · *Depende de:* SIM-2

- **Síntoma.**
  - **Nadie miente.** En los 80 turnos 7.1 no hay un solo `lie`, `test`, `charm`, `plead` ni
    `threaten`; desviar, confrontar y exigir son el 72 %.
  - **Agresión en vez de engaño.** Los sospechosos esquivan a golpes («golpea la mesa con la palma
    abierta», «¡maldita sea!»), y el meteorólogo de `072847` solo desvía, cinco veces de cinco. Es
    el patrón que la literatura atribuye al alineamiento: malevolencia matizada sustituida por
    agresión superficial.
  - **La detective exige; no investiga.** 5 `investigate` y ningún `test` en 80 turnos.
  - **El dossier no da con qué mentir.** Dice qué oculta cada uno (`secret`), no qué cuenta en su
    lugar.
- **Qué hacer.**
  - En el casting, cada personaje con algo que ocultar recibe una versión de los hechos que sostiene
    (`cover_story`, en el idioma de la ficción) y la compuerta que protege.
  - El dossier de quien investiga lleva métodos que se pueden jugar (preguntar, contrastar dos
    versiones, tender una trampa, callar), como conductas y nunca como réplicas.
  - El actor ve sus últimas tácticas nombradas en español («has probado: desviar, desviar,
    desviar»), derivadas del log, para que la regla de cambiar de táctica tenga con qué operar.
- **Medido en 7.2.** El par de 7.2 son justo los prompts 03 y 07, y el patrón se repite: ni un
  solo turno `lie` en 94 turnos de actor, el contrabandista de `163733` jugó **una** táctica en
  toda la obra (`deflect`) y `demand` fue 20 de 51 turnos en `213245`. La resolución del prompt 03
  volvió a llegar por confesión, que su petición prohíbe.
- **Medido en 7.8** (`185923`, prompt 03). Igual: **0 `lie`** en 42 turnos. Mara juega 20 de 22
  turnos entre `investigate` y `confront`. Los cuatro sospechosos juegan sobre todo `deflect`
  (13 de 20), y el médico, 5 de 6. El médico desvía cinco veces seguidas hacia «la estructura
  vieja» y la tormenta, con las seis réplicas empezando por «Señorita Vela,», y solo cede con la
  confesión: no tiene otra versión que contar.
- **Avance 7.17.** El dossier trae `cover_story` y el actor entra en escena con ella. El actor
  ve en español las tácticas que ha probado, y una tercera igual seguida se rechaza
  (`TACTIC_RUN`). Se mide en SIM-26.
- **Hecho cuando.** En un par de misterio (prompts 03 y 07):
  - hay al menos una mentira sostenida y después descubierta;
  - hay más tácticas distintas por actor que en 7.1, leídas con MED-7.
- **Ojo.** Vigilar que la nota de giro no convierta cada mentira en confesión inmediata: una cesión
  que solo llega con la nota es obediencia, no un cambio del personaje. El porqué, en
  `docs/resumen.md` §5.

### SIM-12 · La deducción llega sin sus premisas

*Área:* función simulada · *Cuota:* se valida con el par de SIM-11 · *Depende de:* SIM-1

- **Síntoma.**
  - **La deducción era imposible.** En `072847` el objetivo de la detective para la última escena es
    «Deliver the final logical deduction explaining the locked-room mechanism…», pero ninguna pista
    del mecanismo entró nunca en su memoria. Con lo representado no había deducción posible, y el
    narrador la inventó (SIM-1).
  - **Las compuertas no dicen de qué dependen.** Nada comprueba que quien deduce (`how=deduction`)
    haya presenciado antes lo que necesita.
  - **El mundo adelanta.** Un evento del mundo reveló una compuerta dos eventos antes de tiempo
    (SIM-2).
- **Qué hacer.**
  - Que una compuerta `deduction` liste sus premisas, otras compuertas o hechos iniciales, y que
    `stage/casting.py` valide, con mensajes en inglés, que el deductor las sabe o las presencia en
    un evento anterior.
  - Que el motor siga qué compuertas ha presenciado cada personaje, derivado de los testigos. Antes
    de abrir el beat de una deducción, pasa al director las premisas que faltan; la escalera puede
    entregar una premisa, nunca la conclusión.
- **Medido en 7.8** (`185923`). Las dos compuertas `deduction` del faro no las deduce nadie: la
  del engranaje la representa el mundo («El pestillo… liberado por el engranaje, cae…»), y Mara
  la afirma sin premisas («este engranaje demuestra que el cerrojo fue manipulado
  externamente»). Además, `gate_weather_contradiction` tiene `known_by` vacío: su premisa no la
  sabe nadie al empezar.
- **Hecho cuando.** En un par del prompt 03 y otro del 07:
  - ninguna deducción se abre sin sus premisas en la memoria del deductor;
  - ninguna compuerta se revela antes de su evento.
- **Ojo.** Es la versión en la función de TD-4 y de las reglas de juego limpio: el lector y quien
  investiga tienen que haber visto lo mismo. El porqué, en `docs/resumen.md` §6.

### SIM-13 · El narrador omnisciente destripa el misterio

*Área:* función simulada · *Cuota:* se valida con el par de SIM-12 · *Depende de:* —

- **Síntoma.** La voz por defecto, `omniscient`, narra los pensamientos de todos. En el primer
  capítulo de `072847` el narrador ya le cuenta al lector:
  - que Julian quiere evitar «que el médico o la archivista compararan las horas», la compuerta que
    la detective deduce en el evento 4;
  - que Tobias teme que sospechen «de su equipaje», la que se confiesa en el evento 3.

  La primera regla de Knox (1929) lo prohíbe: el culpable no puede ser nadie cuyos pensamientos
  conozca el lector.
- **Medido en 7.8.** Se repite en el faro (`185923`): el capítulo 2 narra que Elena «no podía
  dejar que descubriera que había sido ella quien alteró los registros», cuando eso nadie lo
  dice en escena. El juez de `audit-stage-run` le dio 100 de fidelidad.
- **Qué hacer.** Una estrategia nueva en `stage/voices.py`: retiene los pensamientos de quien está en
  `known_by` de una compuerta hasta el evento que la revela, y en lo demás se comporta como
  `omniscient`. Se apoya en las compuertas, no en el texto libre de `StoryRequest.genre`.
- **Hecho cuando.**
  - Ninguna historia narra, antes de su evento, un pensamiento que contenga una compuerta, según la
    comprobación de MED-7.
  - Hay test de la estrategia.
  - La lectura a ciegas decide entre esta voz, `omniscient` y `focalized` sobre quien investiga.
- **Ojo.** Fuera del misterio la omnisciencia completa puede ser lo mejor: decide la lectura, no una
  regla. El porqué, en `docs/resumen.md` §9.

### SIM-19 · El arco se gasta en el primer acto y el clímax no tiene oposición

*Área:* función simulada · *Cuota:* ~90 llamadas (un replay del volcán) · *Depende de:* MED-7

- **Síntoma.** Leído en las seis funciones del volcán, que comparten plan:
  - **El cambio llega dos eventos antes.** El plan programa la renuncia de Aldren en `event_4`
    («Aldren decide renunciar a su lealtad ciega…», capítulo 2). En las seis cede antes, en el
    capítulo 1 (`concede` o `confess`). En `151512` deja la corona en el turno 9 de la escena 2.
    Cuando llega `event_4`, ya no queda nada que decidir.
  - **Los personajes no cambian de estado.** Elara está «Determinada» o «Determined» en 25 de 27
    estados por escena. Mara, en el faro, está «Analítica» en 5 de 6.
  - **Ceder es la táctica dominante.** Hay de 16 a 20 cesiones (`yields`) por función en el
    volcán. En el clímax de `184753`, Elara e Ignis se dan la razón durante ocho turnos de
    declaraciones solemnes, y Aldren, al que se dirigen, no habla ni una vez.
  - Las escenas de un solo personaje se juegan como monólogo en voz alta: Aldren, solo, dice
    «deber» tres veces en la primera escena de `151512`.
- **Qué hacer.** Primero medirlo con MED-7: cesiones por acto y por personaje, y emociones
  repetidas. Después:
  - que el `change_condition` del dossier ate el cambio al evento del plan que lo programa,
    para que el director no lo pida antes y la nota de giro no lo adelante;
  - que la reflexión justifique una emoción repetida;
  - que una escena con un solo personaje pida acción y pensamiento, no habla.
- **Hecho cuando.** En un replay del volcán, el giro de Aldren cae en su evento, ninguna emoción
  se repite más de dos escenas sin motivo escrito y el clímax tiene al menos una réplica en
  contra.
- **Ojo.** No convertir la oposición en terquedad: un personaje que se niega a todo hasta su
  evento es tan falso como uno que cede en la primera réplica.

### SIM-20 · El inventario solo ve lo que el actor declara

*Área:* función simulada · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.** El árbitro de 7.6 (`stage/inventory.py`) juzga el `item_action`, no lo que dicen
  la acción ni el mundo:
  - **El mundo mueve objetos sin árbitro.** En `151512`, el evento dice que el sello «resbala de
    las manos de Aldren», pero quien lo tenía era Elara. En el turno siguiente Aldren lo «toma de
    Princesa Elara».
  - **La acción usa objetos que no se tienen.** En `185923`, Mara «golpea el engranaje de latón
    pesado contra la estructura de la lente» dos turnos antes de tomarlo.
  - **`hide` a la vista de todos.** En `184753`, Elara «guarda el diario en su cinto… mirando a
    Sir Aldren», y el árbitro lo registra como oculto con un solo testigo.
  - Se usan pocos objetos: en el faro hay 9 objetos y solo 3 se tocan (`props_used_ratio`
    0,33).
- **Qué hacer.**
  - Que un `stage_event` que nombre un objeto pase por el árbitro como un movimiento más, o se
    rechace.
  - Que la acción que nombra un objeto ajeno sin `item_action` se rechace con el código de
    siempre.
  - Que `hide` exija una visibilidad `whisper` o una escena sin testigos.
- **Hecho cuando.** Hay tests de los tres caminos, y EXP-6 se mide con ellos.
- **Ojo.** Casar un nombre de objeto en texto libre falla con los sinónimos. Usar los nombres
  normalizados de `stage/props.py` y aceptar el falso negativo.

### TD-1 · Los jueces del pipeline aprueban casi todo

*Área:* top-down · *Cuota:* ~17 llamadas para validar · *Depende de:* —

- **Síntoma.** En todo el corpus los jueces LLM dan casi cualquier cosa por buena, y su
  «evidencia» no sale del texto.
  - **Crítico.** Aprobó 695 de 696 comprobaciones de restricción en los runs 6.x, y 6 de 6 en la
    corrida de control, justificadas con paráfrasis y no con citas. La restricción contra
    «confesiones sin investigación» se aprobó con «la resolución se basa exclusivamente en
    deducción física», sobre un capítulo final en el que los tres sospechosos confiesan uno tras
    otro.
  - **Auditoría de promesas.**
    - 48 de 48 promesas salen `fulfilled` en los 19 runs que la traen; ninguna `weak` ni
      `broken`.
    - Solo 17 de las 48 citas aparecen en el borrador o en la historia, comparando sus primeros 60
      caracteres normalizados; ninguna de las dos de la corrida de control. Las demás copian el
      ledger o el plan, a veces en inglés.
    - Lee la crítica del **borrador**, no el `story.md` final.
  - **`plan_review.json`.** Aprobó 124 de 126 planes sin una sola nota, y se lleva el 6,7 % de los
    tokens de un run 6.2.
  - **`craft_evidence.json`.** Está vacío en 31 de 36 runs, también en la corrida de control.
  - **Nadie comprueba la relevancia.** El prompt 03 pide cuatro sospechosos, entre ellos un
    meteorólogo. El reparto de la corrida de control lo omitió, y ninguna comprobación lo notó,
    porque el analista no lo pasó a las restricciones.
- **Qué hacer.**
  - Toda evidencia de un juez es una cita literal. Una comprobación determinista, que normalice
    espacios y comillas, la busca en el texto juzgado; si no aparece, la comprobación cuenta como
    no juzgada, y una promesa no juzgada ya cuenta como `broken`.
  - Auditar las promesas contra el `story.md` final, con una relectura tras la revisión.
  - Con esas cifras, decidir si `plan_review` se endurece con criterios objetivos o se retira.
- **Avance 7.17.** Con el brazo `anchored_critic`, el crítico cita el borrador y
  `writing/anchoring.py` busca cada cita. Lo que no está en el texto cuenta como no juzgado
  (`review_anchors.json`). Se mide en TD-10. Falta auditar contra `story.md` tras la revisión.
- **Hecho cuando.**
  - Cada «aprobado» o «cumplida» de un run nuevo cita un fragmento que existe en su `story.md`.
  - Hay test del camino de la cita inexistente.
  - Hay una decisión escrita sobre `plan_review`.

### TD-4 · La resolución se apoya en hechos que no se plantaron

*Área:* top-down · *Cuota:* ~100 llamadas (2 prompts de misterio × 3 perfiles) · *Depende de:* TD-1

- **Síntoma.** El prompt 03 pide juego limpio: todas las pistas antes de la revelación, y ninguna
  información nueva decisiva al final. En la corrida de control:
  - **La revelación descansa en tres pruebas nuevas** que aparecen por primera vez en el último
    capítulo: «el registro meteorológico oficial que recuperé», «la inspección clínica de su
    propio maletín» y «el mecanismo… estuvo desconectado exactamente diecisiete minutos».
  - **El caso se resuelve con tres confesiones seguidas.**
  - **La solución contradice el capítulo 1.** El farero «escapó por la ventana trasera», la misma
    ventana que el capítulo 1 describe «completamente sellada por capas de salitre y óxido».
  - **El crítico aprobó las dos restricciones afectadas.** En la función, `072847` también cerró
    con confesiones.
- **Qué hacer.**
  - Pedir al crítico, en el último capítulo, la lista de hechos de los que depende la resolución,
    cada uno con la cita literal de dónde se plantó antes, comprobada con el mecanismo de TD-1. Un
    hecho sin cita previa es una nota mayor para el capítulo donde debió plantarse.
  - En el plan, que el evento de revelación declare con `payoff_of` los eventos de pista que paga;
    `graph.py` ya valida que apunten hacia atrás.
- **Hecho cuando.** En una matriz de los prompts de misterio (03 y 07), ninguna resolución depende
  de un hecho sin cita previa según la comprobación, y la lectura a ciegas no encuentra
  contradicciones como la de la ventana.

### TD-5 · El primer plan se rechaza casi siempre por el mismo invariante

*Área:* top-down · *Cuota:* ~150 llamadas (matriz de los tres perfiles) · *Depende de:* —

- **Síntoma.**
  - **En 7.x, siempre.** En los 8 runs que llegaron a planificar, incluidos los dos de 7.2, el
    primer plan se rechazó con «essential profile requires at least 2 events per chapter»: los dos
    runs de 7.2 gastaron 2 llamadas de `plot_planner` cada uno, una de ellas tirada.
  - **En el corpus.** Hay 21 rechazos por el mínimo por capítulo y 20 por el suelo de eventos de
    Expansiva, que además causó 4 de los 5 `PLOT_VALIDATION_FAILED`. El 25-09 se rechazó el plan
    de 4 de 9 runs, siempre por el último capítulo.
  - **Cada rechazo cuesta** una llamada de planificación entera.
- **Qué hacer.** Según CLAUDE.md, el único número que se enseña al planificador es
  `profile_event_floor`: `MIN_EVENTS_PER_CHAPTER` solo se valida. Hay dos salidas que respetan esa
  regla:
  - expresar el mínimo en la forma del esquema, de modo que cada capítulo liste sus eventos y el
    esquema exija dos;
  - o una reparación determinista que funda un capítulo de un solo evento con el anterior antes
    de rechazar el plan.
- **Hecho cuando.** En una matriz de los tres perfiles, el primer intento de plan se acepta en la
  mayoría de los runs y ninguna restricción inventada lleva cifras.
- **Ojo.** El analista inventa a veces un rango de eventos en las restricciones («entre 4 y 6
  eventos principales», en 6 `request.json`, incluida la corrida de control). Ese rango viaja
  luego a todos los agentes y el crítico lo juzga: es un número en el prompt que nadie decidió.

### TD-6 · Acotaciones que son etiquetas de papel

*Área:* top-down · *Cuota:* ~15 llamadas para validar · *Depende de:* —

- **Síntoma.** En los 6 guiones del 25-09 hay acotaciones que no dicen qué hace el personaje sino
  quién es, como «(patrocinador)». Es el Dramaturgo, no el render: los dos defectos de
  `script/render.py` (el doble punto del reparto y la cabecera que alternaba «Reparto» y
  «Personajes») están arreglados en 7.2.0, con test.
- **Qué hacer.** Fijar en el contrato de la acotación que describe una acción visible, nunca una
  etiqueta; si no describe nada que se vea, se deja vacía.
- **Hecho cuando.** En un guion nuevo ninguna acotación es una sola palabra de oficio o de papel.

### TD-7 · Poca diversidad entre corridas

*Área:* top-down · *Cuota:* ~150 llamadas para validar · *Depende de:* TD-2

- **Síntoma.**
  - **Nombres.** «Elena» aparece en 54 de 170 repartos («Elena Vance» 21 veces, «Elena Vargas»
    21). Está en los 9 runs del 25-09, de tres prompts sin relación, y otra vez en la corrida de
    control, junto a un «doctor Vargas».
  - **Aperturas.** 43 de 417 capítulos abren con «El aire…», 19 con «El zumbido…» y 14 con «El
    eco de…».
  - **Títulos.** El prompt de Sir Aldren corrió 15 veces, y 10 se titulan «Las cenizas del
    juramento».
  - **Nombres históricos y pueblos sin nombre propio** (7.12.1, prompt de los navegantes). Dos
    repartos seguidos sacan figuras reales o casi: Rodrigo de Triana, Hernando de Alarcón,
    Alonso de Ribera y dos veces «Catalina de Eraso». La civilización del cielo, que el prompt
    pide «super novedosa», se llama «San Salvador» y su gente «Aldonza de Mendoza» o «Selene de
    Valdés». El prompt de personajes lo prohíbe desde 7.12.1 y el segundo run lo ignoró:
    un prompt no basta.
  - **Importa para la tesis:** la creatividad es una de las seis métricas humanas.
- **Qué hacer.**
  - Medir primero: nombres, aperturas y títulos repetidos entre runs, en un informe de
    `evaluation`, que solo lee disco.
  - Después, probar una intervención que no rompa la reproducibilidad, porque un run no puede leer
    otros runs. Por ejemplo, que el agente de personajes derive los nombres de la cultura y la
    época del mundo, con una lista corta de nombres por defecto que evitar.
- **Avance 7.17.** Nombres por candidatos: el diseñador propone tres con su tipicidad y
  `planning/names.py` elige el menos típico fuera de una lista que el prompt no ve
  (`name_choices.json`). Falta el informe.
- **Hecho cuando.** El informe existe, y una matriz nueva baja la repetición de nombres respecto
  del corpus leída con el protocolo de ruido.

### EXP-9 · Escribir en inglés y traducir la historia al final

*Área:* medición · *Cuota:* ~2 runs simulados más una llamada de traducción por capítulo ·
*Depende de:* EXP-4

- **Síntoma.** Propuesta de 2026-10-14: procesar todo en inglés (prompt, plan, diálogos, prosa)
  y que un agente traductor pase la historia final al idioma pedido, para evitar las mezclas de
  idioma. 7.14 arregla las mezclas con una frontera vigilada (`writing/language.py` y
  `LocalizerAgent`), sin traducir la prosa.
- **Qué hacer.** Un brazo con actores y narrador en inglés y traducción final, frente al
  defecto, con el mismo plan congelado (`--plan-from`). Medir a ciegas y con las cifras de
  artesanía.
- **Hecho cuando.** Los lectores prefieren un brazo, o no distinguen. Solo entonces se decide el
  defecto.
- **Ojo.**
  - La traducción reescribe la voz y el registro pedido (`style_request`), y `craft_metrics`
    mediría al traductor.
  - El inglés no marca género («the captain»): es el fallo de TD-2, ahora en cada línea.
  - Rompe la cadena de citas narración-log (`dialogue_survival`, revisión editorial) salvo que
    se traduzca también el log.

### ING-9 · Dos listas de títulos que no coinciden

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.** `planning/names.py` y `stage/names.py` llevan cada uno su `_TITLES` para quitar
  el tratamiento de un nombre, y no son la misma lista: planning compara formas plegadas
  (`dra`, `capitan`) con `_fold`, stage compara formas acentuadas (`capitán`, `doña`) con
  `.lower()`. Se solapan en torno al 70 %, así que «Dra. Elena» se destitula en el plan y no
  en la función, o al revés. Los mismos dos módulos duplican el plegado: `planning/names.py`
  `_fold` es el prefijo exacto de `planning/skeleton_match.py` `normalize`, que `stage/names.py`
  importa desde ahí, un acoplamiento que no corresponde a lo que hace.
- **Qué hacer.** Una sola lista plegada y un solo comparador, en un módulo de texto del
  paquete. No es una limpieza incidental: unificarlas cambia nombres en historias generadas,
  así que entra con una subida de `PIPELINE_VERSION` y un par medido.
- **Hecho cuando.** El mismo nombre con tratamiento se acorta igual en el plan y en la función,
  y un test lo cruza con las dos rutas.

### ING-2 · Sacar las aserciones de prompt literal de los tests

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.**
  - **Aserciones sobre el texto.** `packages/stagecraft/tests/test_generator_v5.py` y las
    pruebas de guion y actuación comprueban subcadenas de prompts y textos de sistema.
  - **Dobles que enrutan por el texto.** Los dobles de proveedor eligen respuesta por subcadenas
    del prompt de sistema («Script Critic», «Playwright»; y en `stage_fakes.py`,
    «You are the Narrator» o «Name turning_actor_id»). El Writer ya se enruta por su esquema
    (`ParagraphEdits`, 7.18).
  - **El coste.** Reescribir un prompt, que es el trabajo central de la tesis y el de SIM-1,
    SIM-2, TD-2 y TD-4, rompe tests que no tienen nada que ver.
- **Qué hacer.**
  - Enrutar los dobles por el esquema pedido o por un identificador de agente, no por el texto.
  - Expresar las aserciones como comportamiento observable.
  - Donde el prompt sea de verdad el contrato, concentrarlo en pocos tests declarados como tales.
- **Hecho cuando.** Reescribir un prompt de sistema solo rompe los tests que verifican ese prompt.

## Ideas sin decidir


### La temperatura no llega a `gemini-3.5-flash-lite`

Desde el 21 de julio de 2026, Gemini acepta `temperature`, `top_p` y `top_k` en 3.5 Flash-Lite y
3.6 Flash, pero los ignora. Google anuncia un 400 en generaciones futuras y pide llevar el control
a la instrucción de sistema. Así que los cinco perfiles de `_DEFAULT_GENERATION_PROFILES` no hacen
nada en el modelo principal: el actor no escribe a 0,9 ni el crítico a 0,2. `gemini-3.1-flash-lite`
sí los respeta, lo que es otra diferencia entre una función con `GEMINI_STAGE_MODEL` y una sin él.
Decidir si los runs 7.x anteriores a esa fecha se separan de los posteriores, y qué hacer con los
perfiles antes de que un modelo nuevo los rechace.

### Caché de contexto en la función

Una función gasta en torno al 63 % de los tokens de un run simulado: los actores el 41 %, las
reflexiones el 11–12 % y las lecturas del director el 8–9 %. El actor lee unos 19 tokens por cada
token que escribe, y su prefijo de sistema no cambia en toda la obra, pero `cached_tokens` es 0 en
todos los runs. Medir cuánto ahorraría la caché de contexto de Gemini antes de comprometerse. Parte
de esa proporción era la memoria sin tope, ya acotada en 7.2.0: medir sobre un run 7.2.

### Memoria completa frente a memoria recuperada

Las funciones 7.0 y 7.1 recuperaban toda la memoria y aun así repetían. Con el tope de 7.2, los
dos runs Esenciales no perdieron el hilo, pero una obra Expansiva podría. La literatura de contexto largo (*Lost in the Middle*, *Context
Rot*) predice que la memoria entera empeora al crecer, pero en una obra de seis escenas puede no
notarse. Medir las dos cosas sobre el mismo plan antes de fijar el tope para siempre.

### Muestras de voz en el dossier

Si MED-7 confirma que las voces se parecen, probar a dar a cada actor una o dos frases de muestra de
su voz, ajenas a la trama, escritas por el casting. Riesgo: que el actor las repita, por el mismo
autorrefuerzo que obligó a dejar de recuperar el material propio del actor en 7.2.0.

### El estatus como eje del dossier

Johnstone (*Impro*, 1979) describe cada interacción como una transacción de estatus. Un estatus por
relación en el dossier daría al director una palanca distinta de «confiesa», y al actor más tácticas
que gritar.

### Tensión medida por predicción de finales

La métrica 100-Endings (Sui et al. 2026) mide la tensión como la frecuencia con que un modelo falla
al predecir el final, frase a frase, y ordena bien lo que los jueces LLM ordenan mal. Cuesta muchas
llamadas por historia: evaluar si compensa como complemento de la lectura a ciegas.

### Un árbitro de acciones físicas más allá de los objetos

Desde 7.6 los objetos se arbitran en código: quién lleva qué, quién lo ve y qué puede hacer con
ello. Lo que sigue sin comprobarse es el resto de lo físico: «aparta a Mara de un empujón» no
tiene consecuencias, y una puerta se abre porque alguien lo dice. El Game Master de Concordia
juzga la plausibilidad de cualquier acción, no solo las que tocan un objeto. Solo compensa si la
lectura encuentra incoherencias físicas que el inventario no cubre; medirlo es EXP-6.

### Unificar los contratos de prompt duplicados

- **La regla del evento, tres veces.** «Cada evento debe cambiar conflicto, conocimiento,
  relaciones, recursos, riesgos o consecuencias» está escrita casi literal dos veces en
  `planning/profiles.py` y una en `planning/repair.py`.
- **Los perfiles, a mano.** `agents/analyst.py` repite en `PROFILE_ALIASES` y `EXPLICIT_PROFILE`
  los nombres de perfil que ya dan `NarrativeProfile` y `PROFILE_LABELS`.
- **Detección desigual.** El bot no tiene selector de perfil y depende del analista o del `.env`.

### Grafo explícito de lugares

Comparar el modelo actual de `locations` y `location_id` con relaciones y transiciones
explícitas. Documentar el efecto en errores de continuidad y en coste, y adoptarlo solo si mejora
algo medible.

### Audio a varias voces

Tanto `performance.json` como `script.json` distinguen quién dice cada réplica, pero
`create_story_audio` sintetiza el documento entero con una sola voz. Una voz por personaje saldría
casi gratis de cualquiera de los dos. Cambia el contrato de `audio.json`, así que merece su propia
medición.

### Rechazar las peticiones que no son historias

«dame una receta para hacer chesscake» produjo una historia, y el prompt «G» produjo tres runs.
El analista podría negarse con un mensaje claro, sobre todo en el bot.

## Experimentos (aplazado en P05)

Salieron de P05 al escribir sus tarjetas (2026-10-30). Las dos exigen tocar el generador
congelado en 7.22 (`decisions.md` §3): EXP-3 termina borrando un método de guion, y los guiones
no entran al corpus elegible (T9); EXP-5 vuelve a correr versiones anteriores desde git, que el
análisis horizontal no mezcla.

### EXP-3 · Medir guion nativo frente a adaptado y quedarse con uno

*Área:* experimento · *Cuota:* ~300 llamadas para 9 runs por método · *Depende de:* TD-2, MED-3;
mejor con MED-5

- **Síntoma.** Hay 6 runs de guion, 3 por método (`Top-Down/20260925-16*`, pipeline 6.2), y nadie
  los ha comparado. Lo que ya se ve:
  - **Ningún intento de acto rechazado**, en ninguno de los seis.
  - **El nativo sale escaso.** Hace siempre 2 escenas por acto y 1 evento por escena; el acto I
    de `160449-la-sombra-del-faro` tiene 2 réplicas en 8 líneas.
  - **El adaptado es otra cosa.**
    - Es unas 1,5 veces más largo y cuesta 20 llamadas frente a 15.
    - Copia de su `prose.md` entre el 45 y el 49 % de sus secuencias de 6 palabras.
    - Sus acotaciones son de novela: estados interiores en 10 de 133, frente a 1 de 78 en el
      nativo («la verdad que aplasta el alma de la aldea»).
  - **Los títulos en inglés sesgan la lectura** del nativo (TD-2).
- **Qué hacer.**
  - Una matriz con los dos métodos sobre los mismos prompts, mejor desde el mismo plan (MED-5).
  - Leer `script_metrics.json`, los intentos rechazados, los avisos, la tasa de copia desde la
    prosa y el coste, y comparar a ciegas.
- **Hecho cuando.** Hay una decisión escrita, con cifras, en `docs/resumen.md`, y se ha
  borrado el método que pierda: su agente, sus prompts, sus tests y `ASG_SCRIPT_METHOD`.

### EXP-5 · Medir qué aporta cada mejora de la función

*Área:* experimento · *Cuota:* ~900 llamadas (3 prompts × 3 versiones), varios días de cuota
gratuita · *Depende de:* MED-5, MED-7

- **Síntoma.**
  - **No se sabe qué aporta cada cambio.** Cada ficha SIM se valida con un par de runs sobre un plan
    distinto, así que no se sabe qué aportó cada cambio ni si alguno empeoró otra cosa.
  - **Todo se ha medido con misterios.** Las cinco funciones son del prompt 03.
  - **El criterio existe.** WSE-bench concluye que más arquitectura no es más control: cada
    componente debe ganarse su complejidad.
- **Qué hacer.**
  - Con `--plan-from` (MED-5), representar el mismo plan en tres versiones: 7.1.1, 7.2.0 (que
    cerró SIM-9 y SIM-10), y la que cierre SIM-6 y SIM-11.
  - Usar tres prompts de géneros distintos: 03 (misterio), 04 (drama) y 01 (fantasía).
  - Añadir como brazo el presupuesto de pensamiento del actor (SIM-4).
  - Leer MED-7, `asg-report-features` (capas P y K) y la comparación a ciegas.
- **Hecho cuando.** Hay una tabla por versión en `docs/resumen.md` y una decisión
  escrita sobre qué mecanismo se queda.
- **Ojo.** En el prompt 03 el brazo base pueden ser los propios runs 7.1: con `--plan-from` sobre
  `070539` y `072847`, las versiones nuevas representan exactamente su plan. En los otros dos
  prompts, 7.1.1 solo se puede volver a correr desde git: decidir antes el checkout etiquetado.

## Medición (aplazado en P04)

### MED-7 (resto) · Métricas de actuación leídas del log

P04.5 absorbió de MED-7 solo lo que contrasta al extractor con el log: P37 (mentiras) y las
réplicas por actor. Queda lo que diagnostica al generador, ya congelado (T10); la ficha
completa está en `git show planning-before-phase:TODO.md`.

- A quién se dirige cada turno y si alguien le responde; notas repetidas al mismo actor dentro de
  un beat.
- Pensamientos que son un plan o que repiten la nota; entropía de tácticas por actor.
- Memoria que recibe cada turno; distinción de voces entre personajes con una medida sin LLM
  (R14, Šeļa et al. 2023).
- Pensamientos narrados que contienen una compuerta antes de su evento (SIM-13); emociones
  repetidas entre escenas y cesiones por acto (SIM-19).
- Se calculan en `asg_evaluation.simulation_report`, y lo no registrado sale «no medido».
  Son indicadores groseros, no una nota de calidad; ninguno viaja a un prompt.

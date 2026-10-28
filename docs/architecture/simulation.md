# Actuación y narración simuladas

Referencia de contratos vigentes. Lee solo las secciones del subsistema que vayas a cambiar.
Las reglas generales están en [AGENTS.md](../../AGENTS.md).

## Híbrido: la función simulada

`ASG_STORY_FORMAT=simulated` (o `--format simulated`) añade tres etapas tras el guion nativo. El
diseño completo está en [docs/resumen.md](../../docs/resumen.md); lo que hay
que saber antes de tocar `stage/`:

- **Los actores nunca ven el guion.** Al intérprete le llegan las circunstancias, su objetivo, la
  nota del director y su propia memoria. Nada del plan: ni ids, ni títulos, ni escenas futuras.
  `stage/validation.strip_internal_ids` limpia el objetivo y el escenario, porque los escribió el
  Dramaturgo mirando el plan. Un test recorre un run entero comprobándolo.
- **La memoria propia es la aportación.** Cada personaje tiene su flujo, y solo entra lo que
  percibió:
  - un turno público lo ven los que están en escena;
  - un susurro, solo sus destinatarios;
  - un pensamiento, solo quien lo piensa.

  **No hay almacén común del que filtrar**: lo que no se presenció no se escribió.
  `--actor-memory shared` es el brazo de control de esa medición.
- **La recuperación es determinista y sin embeddings.** Relevancia léxica, recencia por escenas,
  importancia y compañía, con los pesos documentados en `stage/memory.py`. Mismo run, misma
  puntuación, en cualquier máquina.
- **Las relaciones se consolidan, no se acumulan.** La reflexión sustituye la postura anterior y
  el historial se queda en los registros. Un actor que guardara «aliada» y «me traicionó» a la
  vez jugaría mal las dos.
- **El director sugiere, nunca dicta.** Da motivaciones, no réplicas. Cuando un beat agota su
  presupuesto (`ASG_STAGE_TURNS_PER_BEAT`, 8), lo cierra con un `stage_event`: algo visible que
  hace el mundo y que entra al log como un turno más. Así el log sigue siendo la única fuente.
- **Los `ValueError` de `stage/validation.py` y `stage/casting.py` van en inglés ASCII**, por la
  misma razón que los de `graph.py`.
- **El punto de vista es modular.** `stage/voices.py` tiene una estrategia por voz, cada una con
  su filtro determinista sobre el log. Añadir un punto de vista es añadir una estrategia, nunca
  una rama en el prompt del narrador. El defecto es `omniscient`.
- **Las visiones `limited` y `first_person` se cuentan desde un personaje.** `narrator` lo
  nombra como lo escribió la persona; `stage/names.py` lo resuelve contra el reparto y, si no
  existe o no presenció nada, narra el de siempre con `[NARRATOR_FALLBACK]`. Solo ven turnos de
  escenas en las que el personaje estaba, también con memoria compartida: así la ablación de
  memoria no se mezcla con la narración.
- **Un capítulo sin turnos visibles no se narra**, con ninguna voz: el modelo tendría que
  inventarlo. Queda como `absent` en `narration.json` y fuera de `story.md`, y `story_metrics`
  recibe el plan recortado por `writing/assembly.narrated_plan`.
- **La visión, el personaje y el tono solo llegan a la narración.** Un test compara plan, guion,
  casting, función y todos los prompts anteriores al narrador entre dos runs que solo difieren
  en ellos.
- **El narrador cura, no transcribe.** Puede cortar, fundir y reordenar dentro de un capítulo,
  pero no puede inventar un beat. Donde el plan y el log no coincidan, manda el log.
  - **Copia lo que recibe.** Entero, transcribía todas las réplicas (7.15.1); cortadas tras la
    primera frase, copiaba los muñones (7.15.2).
  - Desde 7.16 recibe enteras solo las réplicas `[clave]` y los sucesos del mundo. El resto le
    llega en estilo indirecto («Gaspar insistió en el lastre»), que escribe
    `NarratorAgent.report` una vez por capítulo. Ese mismo resumen ordena las réplicas más
    memorables, y el código conserva enteras las primeras hasta una de cada tres del capítulo
    (`WHOLE_EVERY`), porque un beat forzado no tiene ninguna `[clave]`. El resumen lee ids
    cortos (`L1`, `L2`…), nunca ids de turno, que renumeraba.
  - `stage/narration.accept_reports` descarta la paráfrasis que comparte cuatro palabras
    seguidas con su réplica. Lo aceptado y lo descartado queda en
    `narration/chapter-NNN-reported.json`.
  - Las réplicas que el resumen omite o copia se piden una vez más, solo ellas (7.19): en
    7.18 un resumen cubrió solo la primera escena y el capítulo transcribió la segunda.
  - Si el resumen no puede correr, las réplicas van enteras con `[REPORT_FALLBACK]`.
  - **Desde 7.20 el narrador no recibe nada escrito en presente.**
    - En 7.19 pegaba las acotaciones del log, que son prosa en presente, y el capítulo salía con
      párrafos como «Ilse apuñala…».
    - Ahora el mismo resumen cuenta en pasado cada gesto (`G1`), suceso del mundo (`E1`) y
      ambientación de escena (`S1`), y solo el pensamiento de los turnos clave (`T1`).
    - Un gesto que abre con las primeras cuatro palabras de su acotación es copia.
    - Lo que queda sin resumir llega como antes, con `[GESTURE_REPORT_FALLBACK]`.
    - El log abre cada escena con `[escena: …]` y el capítulo con REPARTO, solo de quien aparece
      por primera vez, y FINAL DEL CAPÍTULO ANTERIOR.
    - No vuelvas a pasarle al narrador una acotación o un pensamiento crudos.
  - La revisión y las métricas siguen leyendo los turnos completos.
- **El respaldo es contrato.** Si el casting, la utilería o la narración no pueden correr,
  `stage/casting.py`, `stage/props.py` y `stage/fallback.py` derivan un resultado determinista.
  El run lo registra y sigue.
- **La revisión editorial nunca manda al respaldo un capítulo que el narrador escribió** (7.12).
  En 7.10 lo hizo con 7 de 14 capítulos: la historia de los navegantes salió entera del
  respaldo. `stage/editorial.py` descarta el hallazgo que no puede citar, solo bloquean
  `INVENTED_EVENT` y `CONTRADICTION`, una revisión que falla acepta el capítulo y, agotados los
  intentos, se entrega el de menos hallazgos. El respaldo queda para cuando no hubo texto. No
  vuelvas a rechazar por un hallazgo leve.
  - **El revisor no puede castigar el estilo indirecto** (7.20). En 7.19, 7 de 10 hallazgos
    bloqueantes llamaban «invención» al resumen que el propio reportero escribió. Ahora:
    - el revisor ve `retold_as`;
    - un `INVENTED_EVENT` que comparte cuatro palabras seguidas con un turno o un resumen se
      descarta;
    - un `CONTRADICTION` sin turno es nota;
    - una corrección que cita una réplica se cambia por una instrucción fija, porque llevaba la
      réplica al siguiente intento y el capítulo la contaba dos veces (`DUPLICATED_LINE`, que
      también bloquea).
  - **Una acotación pegada tiene su código** (`COPIED_DIRECTION`, 7.20; antes era
    `WRONG_TENSE`). El editor por fragmentos repara solo esos párrafos antes de la revisión,
    aunque `line_editor` esté apagado.
- **Un capítulo aceptado que transcribe se narra una vez más** (7.15). `craft_findings` mide
  si copia casi todas las réplicas del log o las etiqueta todas. Si pasa, se pide un segundo
  intento con esas notas, que solo se entrega si pasa la revisión y mejora la cifra medida
  (7.15.1: en 7.15 el segundo intento se pasó al imperfecto y se entregó). Es una nota, nunca
  un rechazo. Desde 7.16 también cuenta como nota `DROPPED_EVENT`, un suceso del mundo que el
  capítulo no cuenta. Con `line_editor` (7.17) solo `DROPPED_EVENT` pide el segundo intento: de
  las acotaciones se ocupa el editor, párrafo a párrafo.
- **El narrador por selección (7.17, `narration_method=selected`) no recibe el log.**
  - `NarratorAgent.select` agrupa el log en momentos (`scene` o `summary`, con frase y puente).
  - `stage/selection.py` los valida: devuelve las líneas clave y los sucesos del mundo, rechaza
    el resumen que copia y limita a la mitad lo jugado.
  - `NarratorAgent.write` escribe desde los momentos, los lugares y la cara pública del reparto.
  - La revisión editorial sigue leyendo los turnos.
  - Si la selección falla, se narra como en 7.16 (`[SELECTION_FALLBACK]`).
- **Un estancamiento sin evento del mundo se pregunta una vez más** (7.15.1), pidiendo una
  presión visible, nunca el desenlace: un beat final sin evento dejó una historia sin final.
- **La excepción es el último beat de la obra** (7.16, `CLOSING_STALL`).
  - Ahí el suceso del mundo puede ejecutar la consecuencia visible de una elección que los
    personajes ya tomaron en escena (el barco zarpa). Nunca elige por ellos.
  - Ese beat tiene un turno de reacción más.
  - En 7.15 y 7.15.2 todos los finales se forzaron con el barco amarrado.
- **Un dúo deja entrar a un tercero** (7.16, `policy.DUET_WINDOW`).
  - Si los últimos cuatro turnos son de solo dos personajes, habla el que lleva más tiempo
    callado de los demás, aunque le hayan hablado a otro.
  - En 7.15.2 hubo 12 parejas personaje-escena sin un turno.
- **Un turno fuera de la ficción se rechaza** (7.22, SIM-14). `stage/validation.py` rechaza con
  `OUT_OF_FICTION` el habla, la acción o el pensamiento con vocabulario de código (comillas
  invertidas, rutas con extensión, identificadores `snake_case`, «as an AI») y con `WRONG_LANGUAGE`
  el que no está en el idioma de la ficción; ambos en inglés ASCII y con la reinyección de siempre.
  Un `/` suelto o un nombre con guion no cuentan.
- **El inventario es opcional y el código es el árbitro** (7.6). `inventory=True` añade la etapa
  `props` entre casting y performance.
  - El actor propone un `item_action` (verbo y **nombre** del objeto) y `stage/inventory.py`
    decide: `use`, `give`, `drop`, `hide` y `show` exigen tenerlo; `take`, que esté al alcance.
    Rechaza en inglés ASCII con código, y se reinyecta como cualquier otro turno.
  - **Un objeto solo lo percibe quien lo ve:** los testigos del turno más quien entrega y quien
    recibe; un traspaso en susurro queda entre esas manos; `hide` solo lo sabe su portador. Eso
    amplía la asimetría de la que viven las visiones.
  - `stage/props.py` normaliza más de lo que rechaza, y `MAX_PERSONAL_PROPS` vive ahí, nunca en
    un prompt. Los ids de objeto no entran en el contexto del actor: solo nombres.
  - Apagado no cambia **nada**: ni prompt, ni esquema, ni etapa, ni artefacto. Un test compara
    los dos brazos, y es lo que hace que la opción sea medible.

Los contratos compartidos de estilo, edición y orientación del lector están en
[generación](generation.md).

## Precauciones

- **Quién lo sabe ya ≠ quién lo descubrirá.** En una compuerta de `cast_bible.json`, `known_by`
  es quién sabe el hecho **antes de la primera escena**. Quien lo deduce o descubre en escena va
  en `revealed_by`, con `how`, y **no** en `known_by`. El primer run real los confundió y le dio
  al detective la solución de partida. `stage/casting.py` lo hace cumplir desde 7.1, y desde 7.14
  corrige la forma con una sola lectura: saca al descubridor de `known_by`. Lo que sigue roto en
  el último intento se descarta compuerta a compuerta (`[CAST_GATE_DROPPED]`), nunca se acepta.
  No relajes esa validación para que pase un casting.
- **Las cláusulas de un beat casan por clave, no por texto.** El director reescribe a su manera
  las compuertas obligatorias (`"gate_x: hecho (how, nombre)"`): sin el sufijo, o como el hecho
  a secas. De 7.5 a 7.8 se compararon como cadenas exactas, y los 6 beats con compuertas se
  forzaron. `_clause_key` (`stage/engine.py`) es la única vía para emparejarlas; no vuelvas a
  comparar `part.part` con `in`. La nota de reserva le pasa al actor el hecho, nunca el id.
- **El esquema del turno con objetos solo se pide con el inventario activo.**
  `ActorTurnWithItemsDraft` es un modelo aparte de `ActorTurnDraft` a propósito: el esquema
  cruza al proveedor, así que un campo de objeto presente pero sin usar cambiaría todas las
  peticiones de actor del corpus. Si añades otro camino que pida un turno, elige el esquema
  según si hay árbitro, nunca añadas el campo al modelo base.
- **Un actor escribe destinatarios por nombre; el log guarda ids.** `normalize_turn` resuelve el
  nombre (completo, de pila o una palabra que identifique a un solo personaje presente) y descarta
  lo ambiguo. Los ids nunca entran en el contexto del actor: no los añadas para «ayudar».

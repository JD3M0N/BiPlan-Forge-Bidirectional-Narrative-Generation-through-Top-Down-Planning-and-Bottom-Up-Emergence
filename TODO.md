# Hoja de ruta

**Estado medido el 2026-09-28 con `asg-stagecraft` 7.4.0 (pipeline 7.4; el corpus llega a 7.2,
validado en dos runs reales).** La interfaz gráfica StageCraft (`asg-studio`) ya existe. Un solo generador, Stagecraft, con tres formatos: `narrative`, `script` y `simulated`
(ver [docs/simulacion_escenica.md](docs/simulacion_escenica.md)).

| Corpus | Runs | Completados | Fallidos | Qué es |
|---|---|---|---|---|
| `Stories/Stagecraft/` | 10 | 7 | 3 | 7.0–7.2: ocho simulados y una corrida narrativa de control |
| `Stories/Top-Down/` | 176 | 135 | 41 | 4.0–6.2, anteriores al renombrado; 18 sin versión |
| `Stories/Bottom-Up/` | 6 | — | — | el escape room retirado en 7.1.1, más tres lotes de CSV |

- **Evaluación humana: casi inexistente.** De 146 `evaluation.json`, uno solo tiene puntuaciones
  reales (`Top-Down/20260831-223547-el-rescate-de-luminaria`). Todo lo demás que se sabe de la
  calidad sale de métricas automáticas o de jueces LLM, y esos jueces aprueban casi todo (TD-1).
- **Puerta de calidad limpia.** `ruff check`, `ruff format --check` (190 archivos), la suite y
  `pip check`. Corren en `.github/workflows/quality.yml` en cada push y pull request, y en local
  con `.\quality.ps1`. Los tests corren siempre con `.\run-tests.ps1`, el único comando: nunca
  `pytest` a mano ni un archivo suelto.
- **La corrida de control** (`Stories/Stagecraft/20260926-094204-el-secreto-del-faro-de-san-telmo`,
  narrativa, prompt 03 Esencial) fue la primera narrativa desde el renombrado.
  - Recorrió 7.1.1 entero en 17 llamadas, 97k tokens y unos 92 s de modelo, sin fallos ni
    avisos, así que el refactor `e4c4d99` no rompió nada en real.
  - Confirmó en 7.1.1 fallos que se creían propios de la función simulada o de versiones
    anteriores, detallados en TD-1 a TD-5 y en TD-7:
    - el primer plan, rechazado por el mismo invariante;
    - una revisión que solo alarga;
    - tres confesiones seguidas en la revelación;
    - una solución que contradice el capítulo 1;
    - la médica del prompt convertida en «el doctor Vargas»;
    - el meteorólogo ausente;
    - y, otra vez, «Elena».
- **7.2.0 arregla los bugs que se podían arreglar sin cuota**, cada uno con su test:
  - la memoria sin tope y las réplicas propias releídas (SIM-9);
  - los destinatarios imposibles y las notas repetidas (SIM-10);
  - el log incompleto (SIM-3, cerrada);
  - la cuota diaria tomada por facturación (MED-1, en parte);
  - la telemetría (MED-2, en parte);
  - los runs fallidos que no decían dónde murieron (MED-4, cerrada);
  - el gate de documentación que pasaba en vacío (ING-1, en parte);
  - el anexado cuadrático (ING-4, cerrada);
  - el render del reparto (TD-6, cerrada);
  - los títulos de acto en inglés (TD-2, en parte);
  - las cotas internas (ING-5, en parte).

  **SIM-9 y SIM-10 están verificados en real** por el par de 7.2
  (`Stagecraft/20260927-163733-*`, prompt 03, y `20260927-213245-*`, prompt 07): mediana y máximo
  de 8 recuerdos por turno frente a los 20,5–29 de mediana y 57–70 de máximo de 7.1, cero material
  propio recuperado, 38 de 43 y 47 de 51 turnos con destinatario frente a 1 de 80, cero notas
  repetidas y el primer susurro del corpus. La tabla completa está en
  [docs/simulacion_escenica.md](docs/simulacion_escenica.md), «Validación de 7.2».
- **La frontera de conocimiento se sostiene en el dato.** Una auditoría determinista de los dos
  runs sobre `contexts.jsonl`, `turns.jsonl` y `memory/*/records.json` no encontró ningún id ni
  réplica del guion en un contexto de actor, ningún recuerdo de lo no presenciado, ningún
  pensamiento ni susurro ajeno, y ninguna compuerta filtrada por el dossier, el objetivo, el
  escenario o la nota. El juez LLM dio 95,83 y 100 de conocimiento, y 93,33 y 95,0 de fidelidad
  de la narración, frente a 81,67 y 78,33 en 7.1.
- **Las funciones 7.0 y 7.1 no se comparan sin más con las de 7.2.** Sus actores leían toda su
  memoria anterior (medianas de 18 a 29 recuerdos por turno, máximos de 52 a 72, frente a los 8
  del diseño) y casi nunca tenían destinatario. Sus métricas recalculadas con el código de 7.2
  están en `simulation_metrics.recomputed.json`.
- **Dos documentos nuevos fundamentan la tesis y ordenan el trabajo de la función:**
  - [docs/marco_hibrido.md](docs/marco_hibrido.md): por qué mezclar Top-Down y Bottom-Up;
  - [docs/mejoras_simulacion.md](docs/mejoras_simulacion.md): diagnóstico de la actuación en los
    runs 7.1 y mejoras con su respaldo.

  De ahí salieron SIM-9 a SIM-13, MED-7 y EXP-5; SIM-9 y SIM-10 están cerradas.

## Cómo leer esto

- **Tres secciones**, según lo que hace falta para mover cada tarea. Dentro de cada una, el orden
  de la lista es el orden sugerido; no hay etiquetas de prioridad.
  - **Lo siguiente**: lista para empezar hoy. Nada bloquea su arranque.
  - **Pendiente**: acordada, pero no ahora, o espera a otra ficha (lo dice «Depende de»).
  - **Ideas**: sin decidir. Hay que medir o investigar antes de comprometerse.
- **Cada ficha tiene un ID estable** que la identifica en commits y en los docs:
  - `MED`: medición e instrumentos (cuota, telemetría, matrices, corpus).
  - `SIM`: la función simulada.
  - `TD`: planificación, prosa, jueces y guion.
  - `EXP`: los experimentos de la tesis.
  - `ING`: ingeniería (tests, CI, estructura del código).
  - `OPS`: despliegue y aplicaciones.

  Un ID no se reutiliza al cerrar su ficha. Las ideas no llevan ID; lo reciben al subir.
- **La línea de metadatos** dice el área, la cuota y de qué depende. «Sin cuota» significa que se
  hace y se prueba con proveedores falsos; «~N llamadas» es lo que cuesta validarlo con Gemini.
- **El esqueleto es fijo:** **Síntoma** (qué se observa, con la ruta del run o del archivo y la
  cifra), **Qué hacer**, **Hecho cuando** (una condición verificable) y, solo si hace falta,
  **Ojo**. Se citan rutas y funciones, no números de línea.
- Al cerrar una ficha se borra: el historial vive en git.

## Ruta crítica

La tesis se cierra con experimentos medidos y evaluados por personas. Para llegar ahí:

1. **Instrumentos fiables**, con MED-1, MED-2 y MED-7. Sin ellos una matriz muere a medias, como
   murió `054422`, o mide cosas que no son lo que dicen. MED-7 fija además la línea base de la
   actuación antes de cambiarla.
2. **Una función y unos jueces que no mientan**, con SIM-1, SIM-2, SIM-14, SIM-15, TD-1 y TD-2.
   Medir hoy mediría los defectos, no los formatos. SIM-9 y SIM-10 ya están cerradas con el par
   de 7.2; SIM-14 y SIM-15 salieron de ese mismo par.
3. **Matrices emparejadas**, con MED-3 y MED-5.
4. **Los experimentos**: EXP-1, EXP-2, EXP-3 y EXP-5.
5. **La evaluación humana** de esas historias, con EXP-4.

ING-2 abarata todo lo que reescribe prompts (SIM-1, SIM-2, SIM-6, SIM-15, TD-2, TD-4), así que
conviene hacerlo antes o a la vez. El resto de ING y OPS puede avanzar en paralelo y sin cuota.

El porqué de esta ruta, con sus fuentes, está en [docs/marco_hibrido.md](docs/marco_hibrido.md); el
de las fichas SIM, en [docs/mejoras_simulacion.md](docs/mejoras_simulacion.md).

## Protocolo de medición

Vale para toda ficha `EXP` y para cualquier «Hecho cuando» que pida runs reales.

- **Presupuesto antes de lanzar.** Medianas medidas con `gemini-3.5-flash-lite`:

  | Formato | Llamadas | Tokens |
  |---|---|---|
  | Narrativa | 16 | ~84k |
  | Narrativa (corrida de control) | 17 | 97k |
  | Guion nativo | 15 | ~75k |
  | Guion adaptado | 20 | ~93k |
  | Simulado | 98–126 | 250k–337k |

  El tope gratuito es diario y por modelo (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`).
  Por el run que lo agotó ronda las 500 peticiones al día, cifra inferida, no confirmada. Una
  matriz simulada de 9 runs no cabe en un día.
  - Desde 7.4, la función puede gastar el cupo de otro modelo con `GEMINI_STAGE_MODEL`
    (recomendado `gemini-3.1-flash-lite`, con unas 500 RPD propias según fuentes de septiembre de
    2026). Así el cupo de `GEMINI_MODEL` queda para plan, guion, casting y narración, unas 15–25
    llamadas por run.
  - El RPD real de cada modelo se ve en AI Studio → Rate limits: Google ya no lo publica.
- **Emparejar.** Mismo prompt del catálogo ([docs/prompts_top_down.md](docs/prompts_top_down.md)),
  mismo perfil forzado con `--profile` y mismo modelo. En runs simulados, también el mismo modelo
  de la función (`stage_model`): `pair_runs` no da por limpio un par que lo cambie. Cuando exista
  MED-5, también el mismo plan.
- **A ciegas.** Para comparar:
  - `compare-story-runs` sobre `story.md`;
  - `report-story-craft --format prose --group format` para la artesanía;
  - `report-simulations` para la función.
- **Ruido.** La réplica de doce historias de 6.6.0 dio hasta 16 puntos de diferencia entre dos
  corridas del mismo prompt y la misma versión. Una diferencia de medianas menor de unos cinco
  puntos, con n=9, no se interpreta.
- **Los jueces LLM son indicio, no medida.** La auditoría de la función movió una fidelidad de
  91,67 a 85,0 cambiando solo el juez de conocimiento, y no ve un cambio de género. Hasta cerrar
  TD-1 y la calibración de EXP-2, ninguna cifra de juez cuenta como medida. La literatura dice lo
  mismo: un juez prefiere sus propias generaciones, y aquí Gemini juzga a Gemini; y los jueces al
  uso puntúan historias de LLM por encima de relatos del *New Yorker* (ver
  [docs/marco_hibrido.md](docs/marco_hibrido.md), §9).
- **Por escrito.** El resultado va con cifras y comandos en el doc del formato
  (`docs/simulacion_escenica.md` o `docs/guion_teatral.md`), no aquí.

---

## Lo siguiente

### MED-1 · Nada presupuesta la cuota diaria

*Área:* medición · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.** La clasificación ya está arreglada en 7.2.0: una cuota agotada se clasifica por
  `quota_id` y `metric`, y el texto solo cuenta como último recurso. Los tres «límites de
  facturación» del corpus eran la cuota diaria gratuita. Lo que queda:
  - **Nada cuenta la cuota del día.** `runtime/quota.py` solo tiene ventanas de 60 s (RPM y TPM):
    no hay contador diario ni estimación previa.
    - `054422` murió en la llamada 94 del run, ya dentro de la función.
    - `060405` se lanzó 5 s después y cayó en su primera llamada.
    - El `retry_delay` de unos 55 s que devuelve la API para un tope diario engaña.
  - **La auditoría gasta a escondidas.** `audit-stage-run` gasta una llamada por escena y otra por
    capítulo (unas 36 en las cuatro auditorías hechas), y no aparecen en ningún
    `llm_calls.jsonl`.
- **Qué hacer.**
  - Un contador diario por modelo, persistido fuera de los runs y reiniciado a medianoche del
    Pacífico, que alimenten el proveedor y la auditoría.
  - Una estimación de llamadas por formato y perfil (las medianas del protocolo). Con ella,
    `generate-story` se niega a arrancar si el run no cabe, salvo que se fuerce a propósito.
- **Hecho cuando.**
  - Un run lanzado sin cupo se detiene antes de la primera llamada y dice cuándo vuelve la cuota.
  - La auditoría cuenta en el presupuesto.
- **Ojo.** El contador es una estimación local: otra máquina con la misma clave gasta sin avisar.
  La API sigue siendo la autoridad; el contador solo evita lanzar a ciegas.

### MED-2 · Nadie lee todavía el coste por agente

*Área:* medición · *Cuota:* sin cuota (se comprueba con el par de SIM-1) · *Depende de:* —

- **Síntoma.** La telemetría ya mide lo que dice desde 7.2.0:
  - los intentos de una llamada comparten `call_id`;
  - cada registro lleva la latencia de su intento y la espera previa;
  - `stage` es la etapa del pipeline y `agent` el agente;
  - `count_tokens` va aparte;
  - el bot vacía los registros de cada trabajo.

  `report-story-craft` lee `failed_calls` de un run anterior como «no medido». Pero ningún informe
  usa aún `agent`, y un run real no lo ha estrenado.
- **Qué hacer.**
  - Un informe en `evaluation`, que solo lee disco, que reparta llamadas, tokens y latencia por
    agente y etapa desde `llm_calls.jsonl`.
  - Comprobarlo en el par de SIM-1.
- **Medido en 7.2.** Las tres comprobaciones del «Hecho cuando» pasan ya en los dos runs, leídas
  a mano de `llm_calls.jsonl`: `failed_calls` es 0 con 2 intentos 504 en cada uno, la suma de
  latencias (726 y 572 s) cabe en el reloj (951 y 825 s), y el reparto por agente sale del propio
  archivo (el actor se lleva 71 de 110 llamadas y 123k de 260k tokens en `163733`). Lo que falta es
  el **informe** en `evaluation`, que nadie ha escrito.
- **Hecho cuando.** El informe de `evaluation` reparte llamadas, tokens y latencia por agente y
  etapa, y lee como «no medido» lo que un run anterior no registró.

### MED-7 · Métricas de actuación leídas del log

*Área:* medición · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.** `simulation_metrics.json` no mide lo que más falla en la actuación, y las cifras de
  `docs/mejoras_simulacion.md` salieron de scripts de un solo uso:
  - a quién se dirige cada turno (1 de 80 con destinatario) y si alguien le responde;
  - las notas que se repiten al mismo actor (5 de 54 turnos con nota);
  - los pensamientos que son un plan (35 % y 62 %) o que repiten la nota;
  - las mentiras (0 de 80) y la variedad de tácticas por actor;
  - cuánta memoria recibe cada turno (medido a mano en el par de 7.2: mediana y máximo de 8);
  - si las voces se distinguen;
  - si el narrador cuenta un pensamiento con una compuerta antes de su evento (SIM-13).
- **Qué hacer.** Calcularlas en `report-simulations`, que solo lee disco, desde `turns.jsonl`,
  `contexts.jsonl`, `director.jsonl`, `cast_bible.json` y `story.md`:
  - recuerdos y caracteres por contexto de actor;
  - turnos con destinatario y turnos respondidos;
  - notas repetidas dentro de un beat;
  - pensamientos de plan y eco de la nota;
  - mentiras y entropía de tácticas por actor;
  - distinción de voces entre personajes, con una medida sin LLM como las de Šeļa et al. (2023);
  - pensamientos narrados que contienen una compuerta antes de su evento.

  Como en el resto de `evaluation`, lo que un run no registró sale como «no medido».
- **Hecho cuando.** El informe da esas cifras para las cinco funciones de `Stories/Stagecraft/` y
  reproduce las de `docs/mejoras_simulacion.md`.
- **Ojo.** Son indicadores deterministas y groseros: sirven para comparar versiones sobre el mismo
  plan, no como nota de calidad. Ninguno viaja a un prompt.

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

### SIM-2 · El director reescribe sus cláusulas y habla en inglés

*Área:* función simulada · *Cuota:* se valida con el par de SIM-1 · *Depende de:* —

- **Síntoma.**
  - **Las cláusulas se rehacen en cada lectura, y se pierden por el camino.** El `achieved` de 7.1
    es derivado, pero sobre cláusulas que el modelo elige cada vez.
    - En `072847`, `chapter_3-scene-1`: la comprobación listó 3 cláusulas y la siguiente solo
      «Elena admits…», que bastó para `achieved=true`.
    - `chapter_1-scene-2` pasó de 2 cláusulas a 3 y volvió a 2.
  - **Beats aceptados con poca prueba.** En `070539`, `chapter_2-scene-1` cerró con dos réplicas
    de Mara en 3 turnos. El hallazgo de la anotación alterada que da título al evento nunca ocurre
    en escena.
  - **Un evento del mundo reveló una compuerta dos eventos antes de tiempo.** En `072847`,
    `chapter_1-scene-2`: «…revela las firmas alteradas del registro», que estaba programada como
    deducción de Mara en el evento 4.
  - **Las notas van en inglés.** Lo están 17 de 23 en `070539` y 27 de 31 en `072847`, y la nota
    de coda está fija en inglés en `stage/engine.py` («The matter is settled now…»). Los actores
    traducen la nota a pensamiento: «point directly to the conflicting times…» se vuelve «Apunto
    directamente a las contradicciones temporales…». Es la causa probable de que el 94–95 % de los
    turnos traigan pensamiento.
  - **El estado del actor mezcla idiomas.** `ReflectionDraft` pide `emotion` y `goal` en inglés, y
    `_state_line` (`stage/render.py`) los pega en una frase en español: «te sientes Anxious; ahora
    mismo intentas Defend the accuracy of my atmospheric data…».
  - **La confesión sustituye a la investigación**, que el prompt prohíbe. En `072847` la compuerta
    del engranaje tiene `how=confession`, una nota pide «cede revelando…» y hay 4 turnos `confess`.
- **Qué hacer.**
  - Congelar las cláusulas en la primera lectura del beat y guardarlas en `director.jsonl`.
  - Escribir en el idioma de la ficción las notas, la coda, y la emoción y la meta de la reflexión.
  - Rechazar un `stage_event` que revele una compuerta cuyo evento no ha llegado.
  - Que el casting no programe como confesión una compuerta que la petición exige deducir.
- **Medido en 7.2.** Nada de esto se ha arreglado, y el par de 7.2 lo confirma con sus cifras:
  14 de 33 y 14 de 39 notas en inglés, 5 estados de actor mezclando idiomas en `213245`, cláusulas
  rehechas en 2 y 4 beats, y una compuerta revelada por el mundo antes de su evento (esa parte
  tiene ya su propia ficha con la evidencia, SIM-15). `thought_ratio` bajó a 0,91 y 0,92, y los
  pensamientos de plan siguen en el 44 % y el 64 %.
- **Hecho cuando.** En el par de SIM-1:
  - las cláusulas de cada beat son las mismas en todas sus lecturas;
  - ninguna nota ni ningún estado de actor está en inglés;
  - ninguna compuerta se revela antes de su evento;
  - `thought_ratio` se ha vuelto a medir, sin exigirle todavía un valor (eso es SIM-6).

### SIM-14 · Un actor se sale de la ficción y el log lo acepta

*Área:* función simulada · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.** En `Stagecraft/20260927-163733-*`, turno `chap_2-scene-1-t005`, Mara dijo «I am
  checking the import paths for `Model` in the Superset models structure» y su acción fue
  «Examine the imports in `superset/models/core.py`».
  - El turno pasó los seis rechazos de `stage/validation.py`: no está vacío, no lleva un id del
    plan, no pasa de 45 palabras, no está en primera persona y no repite nada.
  - Entró en `turns.jsonl`, en `transcript.md`, en `performance.json` y en la memoria de tres
    personajes, de donde se pudo recuperar en turnos posteriores.
  - Fue el segundo intento del turno: el primero se rechazó por `REPEATED_ACTION`.
  - El juez de la auditoría lo marcó con severidad 5 y es la **única** fuga de los dos runs 7.2.
  - Se salvó por el narrador, que lo omitió: no llegó a `story.md`.
- **Qué hacer.** Un rechazo determinista de lo que no pertenece a la ficción, en el idioma ASCII
  inglés de los demás, con la reinyección de siempre. Señales barajables sin tocar el plan: habla o
  acción cuyo idioma no es el de la ficción, y vocabulario de código (rutas con `/` y extensión,
  identificadores con guion bajo, comillas invertidas).
- **Hecho cuando.** Hay un test con un turno de ese tipo que se rechaza y se reintenta, y ningún
  run nuevo trae en su log una línea ajena al mundo de la ficción.
- **Ojo.** El detector va en `stage/validation.py`, donde ninguna cifra viaja al prompt. Vigilar el
  falso positivo: una réplica corta con un nombre propio extranjero no es un turno roto.

### SIM-15 · El mundo entrega la trama y adelanta las compuertas

*Área:* función simulada · *Cuota:* se valida con el par siguiente · *Depende de:* SIM-2

- **Síntoma.** Los `stage_event` de los dos runs 7.2 hacen más de lo que la escalera les pide.
  - **Adelantan una compuerta.** En `163733`, el evento del capítulo 1 «hizo saltar el pestillo
    oxidado de la puerta interior», que es la compuerta anclada en `event_5`. De paso destruyó la
    prueba del cuarto cerrado: Mara dedujo después que «la ráfaga lo forzó desde fuera» y exculpó
    al contrabandista, contra la solución real de la obra.
  - **Entregan el caso.** En `213245`, un repartidor trajo un sobre «que detalla la quiebra
    simulada por Víctor Cárdenas para vengarse de la casa de subastas»: el motivo del misterio,
    por correo. El juez lo archivó como `invented_event` de severidad 4.
  - **Repiten recurso.** En `163733` los dos eventos fueron ráfagas de viento, aunque el contexto
    del director ya lleva los eventos ya usados.
- **Qué hacer.**
  - Rechazar el `stage_event` que revele una compuerta cuyo evento no ha llegado, con el mismo
    mecanismo de reintento que el resto (es el tercer punto de SIM-2, aquí con su evidencia).
  - Fijar en el contrato del `stage_event` que el mundo entrega **una** cláusula que falta, nunca
    un motivo, una identidad ni una confesión ajena: lo que se sabe se sigue jugando en escena.
  - Pasar al director el tipo de recurso usado y rechazar un segundo del mismo tipo (lo que ya
    pide SIM-6).
- **Hecho cuando.** En un par nuevo, ningún evento del mundo revela una compuerta antes de su
  evento ni aporta un hecho que no sea la cláusula que faltaba, y no se repite tipo de recurso.

### SIM-16 · `REPEATED_ACTION` se ha vuelto el rechazo dominante

*Área:* función simulada · *Cuota:* sin cuota para medir · *Depende de:* —

- **Síntoma.** En los dos runs 7.2 es el **único** motivo de rechazo: 7 turnos en `163733` (5 de
  ellos en la primera escena) y 10 en `213245`, y provocó los 2 turnos saltados y sus dos avisos
  `[STAGE_TURN_SKIPPED]`. En 7.1 los rechazos eran uno por run, y de otro tipo.
  - La regla mide **contención** contra **todas** las acciones anteriores del actor en la obra,
    no solo la ventana de 3 del validador, desde que 7.2 amplió su alcance.
  - Un turno rechazado dos veces se salta, y un salto costó en `163733` el beat forzado del
    capítulo 1.
  - El segundo intento del turno que se saltó de la ficción (SIM-14) salió justo de uno de estos
    rechazos.
- **Qué hacer.** Medir primero, con los logs que ya hay, cuántos de esos rechazos son un tic real
  y cuántos son un gesto honesto que comparte un verbo. Según eso, decidir entre volver a la
  ventana corta para la contención, exigir un solapamiento mayor, o dejarlo como está y dar al
  actor la lista de sus propios gestos recientes para que no los proponga.
- **Hecho cuando.** Hay una decisión escrita con las cifras de los cuatro runs, y en un par nuevo
  ningún turno se salta por este motivo.

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
- **Hecho cuando.**
  - Cada «aprobado» o «cumplida» de un run nuevo cita un fragmento que existe en su `story.md`.
  - Hay test del camino de la cita inexistente.
  - Hay una decisión escrita sobre `plan_review`.

### TD-2 · La ficción se planifica en inglés y se filtra a la historia

*Área:* top-down · *Cuota:* ~17 llamadas por formato para validar · *Depende de:* —

- **Síntoma.** El plan, el mundo y los personajes se escriben en inglés, y lo que se escapa llega
  al lector:
  - **El género se pierde en la traducción.** El inglés no marca género en los oficios.
    - En la corrida de control, «la médica de la isla» del prompt 03 pasó a
      `role: "Island Doctor"` y después a «el doctor Vargas».
    - En `072847` el dossier decía «Mujer de unos 45 años» y el narrador escribió «El doctor
      Mendoza» seis veces.
  - **Slugs en inglés.** 17 slugs en inglés salieron de prompts en español (`the-oxygen-ledger`),
    porque el slug sale del working title, que está en inglés. Los títulos de acto, que en 2 de 3
    guiones nativos se imprimían en inglés, ya los resuelve `assemble_play` desde la presentación
    localizada (7.2.0).
  - **El crítico pide lo que el Writer no puede cambiar.** En `054422` pidió `fix_act_headings` y
    el Writer gastó 3 revisiones (unos 27k tokens) en un rótulo que no controla.
  - **Nombres, roles y objetivos.**
    - Aparecen «Thomas Brennan» y «Julian Vance» en historias en español, y roles como «Archivist
      and Investigator».
    - Hay objetivos de escena en inglés, uno en primera persona: «Defend my personal bag…».
    - Faltan tildes en nombres y títulos: «Tobias», «Julian», «La Anomalia Mecanica».
- **Qué hacer.**
  - Fijar el contrato. Los ids y la estructura pueden seguir en inglés, pero todo campo que pueda
    llegar al lector (nombres, roles, títulos, lugares, objetos, objetivos) va en el idioma de la
    ficción y con su género.
  - Sacar el slug del título localizado.
  - Que el crítico no levante notas sobre lo que el Writer no controla.
- **Medido en 7.2.** En el formato simulado esto sale ya bien: los dos runs tienen slug, títulos
  de capítulo, roles y `public_face` en español, y el género coincide con la petición (la médica
  del prompt 03 es «Mujer de unos cincuenta años»). Lo que queda en inglés es lo que no ve el
  lector y lo del director (SIM-2). Falta comprobarlo en `narrative` y en `script`.
- **Hecho cuando.**
  - En runs nuevos de cada formato, el slug, los nombres y los roles están en español.
  - El género de cada personaje coincide con el de la petición.
- **Ojo.**
  - Los `ValueError` de `graph.py` y compañía siguen en inglés a propósito: esto va del contenido
    de la ficción, no del contrato con el modelo.
  - Cambiar el idioma del plan cambia prompts y quizá el comportamiento del planificador. Medir la
    tasa de planes rechazados antes y después.

### MED-3 · Un runner de matrices con presupuesto

*Área:* medición · *Cuota:* sin cuota (la gasta quien lo lance) · *Depende de:* MED-1

- **Síntoma.**
  - Toda ficha `EXP` necesita una matriz, y hoy se lanzan a mano, run a run.
  - Así murió el par `054422`/`060405`: el segundo se lanzó sin saber que la cuota se había
    agotado.
  - Nada registra qué celdas de una matriz faltan ni con qué configuración corrió cada una.
- **Qué hacer.** Un comando que:
  - lea una matriz: prompts del catálogo por marcador, formatos, perfiles, brazos como
    `--actor-memory` o `--script-method`, y repeticiones;
  - estime su coste con MED-1 y corra en serie;
  - se pueda interrumpir y reanudar saltando las celdas completadas;
  - escriba un manifiesto con cada celda, su run y su configuración.
- **Hecho cuando.**
  - Una matriz interrumpida a mitad se completa al relanzarla, sin repetir runs.
  - Su manifiesto basta para pasar los runs a `compare-story-runs` y a los informes por celda.

---

## Pendiente

### MED-5 · Comparar formatos y métodos desde un mismo plan congelado

*Área:* medición · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.**
  - Cada run genera su propio plan. Al comparar narrativa con simulada, o guion nativo con
    adaptado, la varianza de planificación se mezcla con la de escritura.
  - Los cuatro runs 7.x del prompt 03 que terminaron resuelven el mismo misterio de cuatro formas
    distintas.
  - Era una idea solo para los métodos de guion. Es lo que hace interpretables EXP-1 y EXP-3 con
    n pequeño.
- **Qué hacer.**
  - Un `--plan-from <run>` que reutilice `request.json`, `world.json`, `characters.json`,
    `story_plan.json` y el ledger de un run terminado, y arranque en la primera etapa de escritura
    del formato pedido.
  - El run nuevo registra de qué run salió su plan.
- **Hecho cuando.**
  - Dos runs de formatos distintos con el mismo `--plan-from` tienen un `story_plan.json`
    idéntico byte a byte.
  - Los informes pueden agrupar por plan de origen.
- **Ojo.** El run de origen tiene que ser de una versión que el código aún lea
  (`SUPPORTED_PIPELINE_VERSIONS`).

### SIM-4 · Los timeouts de actor se comen entre un cuarto y dos tercios del reloj

*Área:* función simulada · *Cuota:* ~110 llamadas · *Depende de:* MED-2

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
    (`docs/mejoras_simulacion.md` §10).
- **Medido en 7.2.** Mucho menos grave que en 7.1, pero sigue ahí: 2 intentos 504 por run, y el
  reloj (951 y 825 s) deja 100 y 49 s sin explicar sobre la suma de latencias más las esperas. Los
  runs bajaron a 14–16 minutos, frente a los 17–31 de 7.0 y 7.1. Un `ConnectError` de red mató
  además un run entero del prompt 07 (`20260927-170152-*`) tras 19 fallos seguidos: el aviso que
  quedó, `ACTOR_CALL_FAILED | ProviderError`, no dice qué error fue, porque `_reject` guarda
  `type(exc).__name__` y no el código que sí está en `llm_calls.jsonl`.
- **Hecho cuando.** En un run simulado nuevo, con la telemetría de MED-2, el reloj se acerca a la
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
  del 07, tres recursos distintos (ver SIM-15).
- **Hecho cuando.** Un par de runs:
  - baja `thought_ratio` claramente de 0,9, y bajan los pensamientos de plan que mide MED-7;
  - tiene al menos un susurro que la ablación pueda medir;
  - no repite tipo de evento del mundo.
- **Ojo.** El porqué de cada punto, con su respaldo, está en `docs/mejoras_simulacion.md` §4 y §7.

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
  - Que `recover-story-runs` ofrezca reanudar, además de cerrar o descartar.
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
- **Hecho cuando.** En un par de misterio (prompts 03 y 07):
  - hay al menos una mentira sostenida y después descubierta;
  - hay más tácticas distintas por actor que en 7.1, leídas con MED-7.
- **Ojo.** Vigilar que la nota de giro no convierta cada mentira en confesión inmediata: una cesión
  que solo llega con la nota es obediencia, no un cambio del personaje. El porqué, en
  `docs/mejoras_simulacion.md` §5.

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
- **Hecho cuando.** En un par del prompt 03 y otro del 07:
  - ninguna deducción se abre sin sus premisas en la memoria del deductor;
  - ninguna compuerta se revela antes de su evento.
- **Ojo.** Es la versión en la función de TD-4 y de las reglas de juego limpio: el lector y quien
  investiga tienen que haber visto lo mismo. El porqué, en `docs/mejoras_simulacion.md` §6.

### SIM-13 · El narrador omnisciente destripa el misterio

*Área:* función simulada · *Cuota:* se valida con el par de SIM-12 · *Depende de:* —

- **Síntoma.** La voz por defecto, `omniscient`, narra los pensamientos de todos. En el primer
  capítulo de `072847` el narrador ya le cuenta al lector:
  - que Julian quiere evitar «que el médico o la archivista compararan las horas», la compuerta que
    la detective deduce en el evento 4;
  - que Tobias teme que sospechen «de su equipaje», la que se confiesa en el evento 3.

  La primera regla de Knox (1929) lo prohíbe: el culpable no puede ser nadie cuyos pensamientos
  conozca el lector.
- **Qué hacer.** Una estrategia nueva en `stage/voices.py`: retiene los pensamientos de quien está en
  `known_by` de una compuerta hasta el evento que la revela, y en lo demás se comporta como
  `omniscient`. Se apoya en las compuertas, no en el texto libre de `StoryRequest.genre`.
- **Hecho cuando.**
  - Ninguna historia narra, antes de su evento, un pensamiento que contenga una compuerta, según la
    comprobación de MED-7.
  - Hay test de la estrategia.
  - La lectura a ciegas decide entre esta voz, `omniscient` y `focalized` sobre quien investiga.
- **Ojo.** Fuera del misterio la omnisciencia completa puede ser lo mejor: decide la lectura, no una
  regla. El porqué, en `docs/mejoras_simulacion.md` §9.

### TD-3 · La revisión alarga en vez de reparar

*Área:* top-down · *Cuota:* ~17 llamadas para validar · *Depende de:* —

- **Síntoma.**
  - **Casi toda revisión alarga.** En 6.2, 69 de 69 capítulos con nota se revisaron y aceptaron,
    y 66 salieron más largos, con una mediana de +82 palabras.
  - **La corrida de control repite el patrón.** El capítulo 1 volvió idéntico al primer intento
    (`UNCHANGED_SIGNIFICANT_NOTES`) y pasó de 1.034 a 1.107 palabras al segundo; el 2, de 704 a
    765.
  - **El caso más claro** sigue siendo `Top-Down/20260920-135822-el-computo-de-la-deriva`: una
    nota de ritmo por un `dialogue_ratio` de 0,1765, reescritura de 424 a 589 palabras, y el mismo
    0,1765 después.
  - **Nada comprueba el arreglo.** `writer_candidate_issue` (`writing/acceptance.py`) solo rechaza
    un cuerpo vacío, encabezados y texto idéntico. Tras dos rechazos, `_revise_one_chapter`
    devuelve el borrador. No hay segunda crítica, así que nada mide si la revisión arregló algo.
  - **El bucle de `RETRY CORRECTION` está copiado tres veces**: en `pipeline.py`,
    `script/stages.py` y `stage/stages.py`.
- **Qué hacer.**
  - Primero, extraer el bucle de reintento compartido.
  - Después, llevar hasta la revisión las observaciones de `craft_evidence` que
    `_critique_and_revise` ya calcula. Si la misma observación sobrevive al candidato, usarla como
    corrección del siguiente.
  - Rechazo blando: devolver el mejor candidato, nunca el borrador degradado.
  - El feedback nombra la observación y jamás una cifra; para eso existe
    `test_no_measurement_ever_reaches_the_prompt`.
- **Hecho cuando.**
  - Una reescritura que no mueve la observación se reintenta.
  - El capítulo entregado nunca es el borrador.
  - El bucle vive en un solo sitio, y hay test del camino.

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
  - **Importa para la tesis:** la creatividad es una de las seis métricas humanas.
- **Qué hacer.**
  - Medir primero: nombres, aperturas y títulos repetidos entre runs, en un informe de
    `evaluation`, que solo lee disco.
  - Después, probar una intervención que no rompa la reproducibilidad, porque un run no puede leer
    otros runs. Por ejemplo, que el agente de personajes derive los nombres de la cultura y la
    época del mundo, con una lista corta de nombres por defecto que evitar.
- **Hecho cuando.** El informe existe, y una matriz nueva baja la repetición de nombres respecto
  del corpus leída con el protocolo de ruido.

### EXP-1 · Medir la historia simulada contra la narrativa

*Área:* experimento · *Cuota:* ~1.150 llamadas para 3 prompts × 3 repeticiones, varios días de
cuota gratuita · *Depende de:* SIM-1, SIM-2, SIM-14, MED-3; mejor con MED-5

- **Síntoma.** El formato simulado existe desde 7.0, y sigue sin saberse si una historia narrada
  desde una función es mejor, peor o solo distinta de una escrita directamente.
  - **Hoy hay un solo par**, y con planes distintos: la corrida de control narrativa contra
    `070539` y `072847`, todos del prompt 03 Esencial.
  - **Lo que ya se ve en ese par.** La narrativa tiene 0,75 de diálogo y 2.476 palabras, y las
    simuladas 0,52 y 0,49 de diálogo con 1.219 y 1.955 palabras.
  - **El clímax sale corto en los dos formatos.** En los cuatro runs 7.x del prompt 03 que
    terminaron, el último capítulo es el más corto de su historia; en el corpus lo es en 31 de
    112, cerca del azar.
  - **Se cerró la ficha «El desenlace sigue resumiendo».** El último capítulo era el más mudo en
    13 de 21 historias de 6.6.0, y desde el 20-09 lo es en 2 de 12 (3 contando empates). Se sigue
    vigilando aquí.
- **Qué hacer.**
  - Una matriz con los mismos prompts canónicos en `narrative` y en `simulated`, mismo perfil e,
    idealmente, mismo plan (MED-5), siguiendo el protocolo.
  - Leer la comparación a ciegas, las cifras de artesanía y las de `report-simulations`:
    `script_echo` (si sale alto, los actores recitaron y la simulación no aporta) y
    `beat_completion_ratio`.
  - Leer también el coste por agente (MED-2), y si el último capítulo es el más mudo o el más
    corto.
- **Hecho cuando.** Hay una decisión escrita, con cifras, en `docs/simulacion_escenica.md`.

### EXP-2 · Medir la ablación de memoria propia contra memoria compartida

*Área:* experimento · *Cuota:* ~2.000 llamadas para dos brazos de 9 runs, más la auditoría ·
*Depende de:* SIM-1, MED-1, MED-3

- **Síntoma.** `--actor-memory shared` existe como brazo de control y nadie lo ha corrido. Es la
  medición que sostiene la afirmación central de la tesis: que dar a cada personaje solo lo que
  presenció produce mejores escenas que darles todo lo público.
  - El proxy determinista es `unknown_mentions`; la medida seria la da `audit-stage-run`.
  - Pero el juez por defecto (`gemini-3.5-flash-lite`) todavía no es fiable:
    - marcó como fuga un hecho que estaba literalmente en la memoria inicial del personaje
      (reauditoría de `023354`);
    - movió 7 puntos una cifra que no había cambiado (91,67 → 85,0);
    - no ve ni un cambio de género ni una réplica sin atribuir.
- **Qué hacer.**
  - Primero, calibrar el juez: reauditar los runs existentes con un modelo más fuerte (`--model`)
    y ver qué fugas se sostienen.
  - Después, dos matrices idénticas salvo en `--actor-memory`.
- **Hecho cuando.** Hay una cifra de fuga de frontera de conocimiento para cada brazo, medida con
  un juez calibrado, y una comparación a ciegas de las historias de cada uno.
- **Ojo.**
  - Las funciones 7.0 y 7.1 recuperaban la memoria entera: cada actor leía todo lo que había
    presenciado. La ablación corre ya sobre 7.2, que aplica el tope; no mezclar sus runs con los
    anteriores.
  - El respaldo de la hipótesis, y lo que ya dice la literatura sobre filtrar lo que un personaje
    sabe, está en `docs/marco_hibrido.md` §7.

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
- **Hecho cuando.** Hay una decisión escrita, con cifras, en `docs/guion_teatral.md`, y se ha
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
  - Leer MED-7, `report-simulations`, el coste por agente (MED-2) y la comparación a ciegas.
- **Hecho cuando.** Hay una tabla por versión en `docs/simulacion_escenica.md` y una decisión
  escrita sobre qué mecanismo se queda.
- **Ojo.** En el prompt 03 el brazo base pueden ser los propios runs 7.1: con `--plan-from` sobre
  `070539` y `072847`, las versiones nuevas representan exactamente su plan. En los otros dos
  prompts, 7.1.1 solo se puede volver a correr desde git: decidir antes el checkout etiquetado.

### EXP-4 · Campaña de evaluación humana

*Área:* experimento · *Cuota:* sin cuota · *Depende de:* EXP-1 y EXP-3 (para las historias)

- **Síntoma.**
  - **No hay evaluación humana.** De 146 `evaluation.json`, uno solo tiene puntuaciones reales;
    los demás, incluidos todos los de Stagecraft y Bottom-Up, son plantillas.
  - **Todas las cifras de calidad** del proyecto son automáticas o de jueces LLM, y esos jueces
    aprueban casi todo (TD-1).
  - **El informe no mide acuerdo.** `report-evaluations` da media, desviación y varianza, pero
    no el acuerdo entre evaluadores.
- **Qué hacer.**
  - Escribir un protocolo:
    - qué historias: las de EXP-1 y EXP-3, emparejadas;
    - cuántos evaluadores;
    - presentación a ciegas y en orden aleatorio;
    - las seis métricas de `packages/evaluation/README.md`.
  - Añadir a `report-evaluations` el acuerdo entre evaluadores (por ejemplo, alfa de
    Krippendorff) y la comparación por pares. Esta parte no espera a las matrices.
- **Hecho cuando.** Cada historia de las matrices tiene el número de evaluaciones completas que
  fije el protocolo, y el informe da el acuerdo entre evaluadores.

### MED-6 · Inventario del corpus

*Área:* medición · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.**
  - **Versiones.**
    - 18 runs no tienen `pipeline_version` (16 a 18 de agosto) y 47 no tienen
      `generator_version.json`, así que caen fuera de los informes por versión.
    - La etiqueta de pipeline es gruesa: 6.2 cubre el generador de 6.6.0 a 6.9.0.
    - `story_format` solo consta en los 9 runs más nuevos de Top-Down.
  - **Estados y restos.**
    - `Top-Down/20260911-173150-*` está `failed` (PermissionError) con `story.md` escrito.
    - Quedan `.story.mp3.*.tmp` en los dos runs cerrados a mano (`20260901-020145`,
      `20260908-020751`).
  - **Archivos que no son runs.** Hay uno en `Stories/Top-Down/`
    (`comparacion-densidad-borrador-final-v2.0.4.html`), y la cola `Stories/telegram_queue.sqlite3`.
  - **Huecos sueltos.** `20260901-023045-the-cheesecake-trial` tiene historia y no
    `evaluation.json`, y los warnings son texto libre, sin campo de código.
- **Qué hacer.**
  - Un informe de solo lectura en `evaluation` que liste esas anomalías, para que cada informe de
    la tesis diga qué excluye y por qué.
  - Nunca borrar datos. Lo que se corrija, con `recover-story-runs` y dejando rastro.
  - Poner código propio a los warnings de los runs nuevos, en la subida de versión de MED-2.
- **Hecho cuando.** El inventario sale limpio, o cada anomalía tiene una decisión escrita.

### ING-2 · Sacar las aserciones de prompt literal de los tests

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.**
  - **Aserciones sobre el texto.** `packages/stagecraft/tests/test_generator_v5.py` (1.861 líneas)
    tiene unas 51 aserciones de subcadena sobre prompts y textos de sistema. Hay más en
    `test_script_pipeline` (5), `test_stage_engine` (4) y `test_audit_stage` (4).
  - **Dobles que enrutan por el texto.** Los dobles de proveedor eligen respuesta por subcadenas
    del prompt de sistema («final Writer», «Script Critic», «Playwright»; y en `stage_fakes.py`,
    «You are the Narrator» o «Name turning_actor_id»). Además parten el prompt del Writer por
    `ORIGINAL CHAPTER BODY:` y `RETRY CORRECTION:`.
  - **El coste.** Reescribir un prompt, que es el trabajo central de la tesis y el de SIM-1,
    SIM-2, TD-2 y TD-4, rompe tests que no tienen nada que ver.
- **Qué hacer.**
  - Enrutar los dobles por el esquema pedido o por un identificador de agente, no por el texto.
  - Expresar las aserciones como comportamiento observable.
  - Donde el prompt sea de verdad el contrato, concentrarlo en pocos tests declarados como tales.
- **Hecho cuando.** Reescribir un prompt de sistema solo rompe los tests que verifican ese prompt.

### ING-1 · Docstrings plantilla que no dicen nada

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.** El gate ya no pasa en vacío: desde 7.2.0 resuelve sus rutas desde `Path(__file__)`,
  falla si no encuentra módulos y su marcador corrupto está corregido. Lo que queda es que solo
  exige texto ASCII:
  - de 862 definiciones en 98 archivos, unas 65 tienen un docstring plantilla: «Represent X data
    and behavior.», «Initialize the X instance», «Run the XAgent workflow»;
  - las peores son `schemas.py` (17), `runtime/errors.py` (11) y `runtime/storage.py` (8);
  - **Ruff no ayuda.** `pyproject.toml` no activa las reglas `D`.
- **Qué hacer.**
  - Pasar la presencia de docstrings a las reglas `D` de Ruff y dejar el test solo para el idioma.
  - Reescribir los docstrings plantilla, empezando por esos tres archivos.
- **Hecho cuando.** No queda ningún docstring que se limite a repetir el nombre de la función.

### ING-3 · Dividir `pipeline.py`

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* TD-3 (el bucle de reintento), MED-2

- **Síntoma.**
  - **Tamaño.** `StoryPipeline` tiene 1.197 líneas y 48 métodos, más los mixins de
    `script/stages.py` (646 líneas) y `stage/stages.py` (574).
  - **Asserts por culpa de un campo opcional.** El `repository` opcional obliga a 37
    `assert self.repository is not None`: 22 en `pipeline.py`, 9 en `script/stages.py` y 6 en
    `stage/stages.py`.
  - **Métodos largos.** Los peores son `_perform_play` (132 líneas), `_revise_one_act` (118) y
    `_revise_one_chapter` (94).
  - **Lo fácil ya está hecho.** Las tres extracciones de riesgo nulo se hicieron en 7.0.0:
    `planning/repair.py`, `writing/assembly.py` y `writing/acceptance.py`.
- **Qué hacer.**
  - Sacar la telemetría y la contabilidad de uso como colaboradores (encaja con MED-2).
  - Sacar el bucle de reintento compartido (TD-3).
  - Al final, convertir las etapas en clases con estado propio, que es lo que elimina los asserts.
  - No hacerlo de paso dentro de otro cambio.
- **Hecho cuando.**
  - Plan, borrador, revisión y función son unidades con test propio.
  - El estado deja de pasarse como parámetros posicionales.
  - Los artefactos generados no cambian.

### ING-5 · CI, tipos y dependencias

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.**
  - **CI solo prueba una plataforma.** Corre solo en `windows-latest` con Python 3.12; el resto
    de versiones soportadas (`requires-python = ">=3.11"`) no se comprueban.
  - **Sin tipos ni cobertura.** No hay comprobador de tipos, aunque ya hay 3
    `# type: ignore[arg-type]` en `stage/engine.py` y `stage/memory.py`. Tampoco se mide
    cobertura.
  - **Más cabos sueltos.** `colorama` no tiene techo, no hay lockfile y los `CHANGELOG` usan dos
    formatos de cabecera. Las cotas internas se subieron al mínimo real en 7.2.0, pero nada
    impide que vuelvan a quedarse atrás.
- **Qué hacer.**
  - Ampliar la matriz de CI a Linux y 3.11.
  - Añadir pyright o mypy, empezando por `core`.
  - Informar de la cobertura, sin umbral al principio.
- **Hecho cuando.** CI prueba la versión mínima de Python declarada, y una dependencia interna
  demasiado vieja falla al instalar, no al importar.

### ING-6 · Cerrar los huecos de cobertura

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.**
  - **Progreso sin test y duplicado.** `runtime/progress.py` no tiene ni un test, y
    `format_progress` está duplicado en `apps/telegram/contract.py`, también sin test.
  - **El repositorio apenas se prueba.** `ArtifactRepository` tiene un solo test directo: no se
    comprueban los hashes del manifiesto, ni `register_existing`, ni `fail()` con un error no
    clasificado.
  - **Código defensivo por culpa de los tests.** `GeminiProvider` tiene 8 `getattr`/`hasattr`
    defensivos que existen solo porque `test_provider.py` lo construye con `__new__`.
- **Qué hacer.**
  - Tests de progreso y de repositorio.
  - Una sola `format_progress`.
  - Un constructor de prueba para el proveedor que haga innecesarios esos `getattr`.
- **Hecho cuando.** Esos caminos tienen test, y el proveedor no tiene atributos opcionales por
  culpa de los tests.

### ING-7 · `topological_order` se serializa y es derivable

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.**
  - **Es redundante.** En los planes del corpus coincide siempre con ordenar los eventos por su
    campo `order` (comprobado en 71 de 71), que es lo que ya garantizan los invariantes del grafo.
  - **Quitarlo no es gratis.** Lo leen 7 archivos: `schemas.py`, `planning/graph.py`,
    `planning/promises.py`, `planning/promise_brief.py`, `script/stages.py`,
    `script/validation.py` y `pipeline.py`. Y está en los artefactos de más de 180 runs.
- **Qué hacer.** Decidir si el campo se deriva al cargar en vez de persistirse. Si se quita, subir
  `PIPELINE_VERSION` y dar una lectura compatible a los runs que lo traen.
- **Hecho cuando.** Hay una decisión escrita y, si se elimina, los runs anteriores se siguen
  abriendo.

### ING-8 · Documentar los contratos públicos y rellenar el README

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* el cierre del proyecto

- **Síntoma.**
  - `README.md` de la raíz está vacío a propósito: se redacta al cerrar, cuando los contratos ya
    no se muevan.
  - Las fachadas no tienen ejemplos que se ejecuten.
  - `packages/core/README.md` sigue en inglés y los demás están en español.
- **Qué hacer.** Al cerrar:
  - ejemplos mínimos de entrada, salida y fallo para `asg_core`, `asg_stagecraft` y
    `asg_evaluation`;
  - el README de la raíz, en UTF-8.
- **Hecho cuando.** Los ejemplos se validan en los tests o en CI, y la documentación describe el
  contrato de artefactos vigente y su compatibilidad con los runs anteriores.

---

## Ideas

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

### Un árbitro de acciones físicas

En la función nadie comprueba lo físico: «aparta a Mara de un empujón» no tiene consecuencias, y una
puerta se abre porque alguien lo dice. El Game Master de Concordia comprueba la plausibilidad de cada
acción. Solo compensa si la lectura encuentra incoherencias físicas.

### Probar si la taxonomía de arquetipos mejora las historias

El mecanismo está construido y es auditable:

- 34 esqueletos etiquetados por capa;
- un ranking léxico mezclado con una llamada semántica;
- un `narrative_blueprint.json` por run.

Con la guía apagada, `ASG_NARRATIVE_GUIDANCE=false`, los prompts quedan idénticos a la línea
base, así que la ablación es limpia. Pero el experimento sigue sin hacerse: el único par con y sin
guía es n=1 y anterior a esa corrección.

### Externalizar el catálogo de esqueletos

`skeletons.py` tiene 1.485 líneas: unas 1.289 son las 34 entradas literales del catálogo
(`PLOT_SKELETONS`) y la lógica real ocupa unas 90. `PlotSkeleton` ya es un modelo Pydantic,
así que cargarlo desde JSON es casi mecánico.

- **A favor:** un diff limpio al añadir esqueletos, y editar el corpus sin tocar Python.
- **En contra:** se pierde el chequeo en tiempo de edición.

### Unificar los contratos de prompt duplicados

- **La regla del evento, tres veces.** «Cada evento debe cambiar conflicto, conocimiento,
  relaciones, recursos, riesgos o consecuencias» está escrita casi literal dos veces en
  `planning/profiles.py` y una en `planning/repair.py`.
- **Los perfiles, a mano.** `agents/analyst.py` repite en `PROFILE_ALIASES` y `EXPLICIT_PROFILE`
  los nombres de perfil que ya dan `NarrativeProfile` y `PROFILE_LABELS`.
- **Detección desigual.** La consola no tiene selector de perfil y depende del analista.

### Grafo explícito de lugares

Comparar el modelo actual de `locations` y `location_id` con relaciones y transiciones
explícitas. Documentar el efecto en errores de continuidad y en coste, y adoptarlo solo si mejora
algo medible.

### Inventario por personaje

Quién tiene qué en la función: dar, tomar y esconder objetos, y que un objeto solo lo perciba
quien lo ve. Los `StoryObject` del mundo ya existen y la función los ignora. Va de la mano del
árbitro de acciones físicas: sin nadie que compruebe lo físico, un inventario es solo texto.
StageCraft ya lo muestra como opción pendiente; la receta para activarlo está en
`apps/studio/README.md`.

### Ventana nativa para StageCraft

Abrir StageCraft en una ventana propia con pywebview en vez del navegador. Solo compensa si se
reparte a gente que no debería ver una URL local; en Windows depende de WebView2.

### Audio a varias voces

Tanto `performance.json` como `script.json` distinguen quién dice cada réplica, pero
`create_story_audio` sintetiza el documento entero con una sola voz. Una voz por personaje saldría
casi gratis de cualquiera de los dos. Cambia el contrato de `audio.json`, así que merece su propia
medición.

### Rechazar las peticiones que no son historias

«dame una receta para hacer chesscake» produjo una historia, y el prompt «G» produjo tres runs.
El analista podría negarse con un mensaje claro, sobre todo en el bot.

### Qué hacer con Bottom-Up

Sus 6 runs son un registro de acciones en bruto («A compartió sus descubrimientos con B.»), sin
versión ni evaluación. Aun así, el menú «Evaluar historia» de la consola los ofrece para
puntuar. Hay dos salidas:

- puntuarlos como línea base, que es lo único que les daría uso en la tesis;
- o sacarlos del menú de la consola, conservando siempre los datos.

Ya tienen otro uso: `docs/marco_hibrido.md` §3 los cita como evidencia interna de que la simulación
sola produce registros, no historias.

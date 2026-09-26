# El contrato Promise-Progress-Payoff

Qué se formalizó de la tríada de Sanderson, qué se dejó fuera a propósito, por qué el contrato no
puede tocar la estructura de la historia, y cómo se mide si sirve de algo.

**Escrito contra la implementación de `asg-stagecraft` 6.8.0.** El contrato de artefactos sigue en
`PIPELINE_VERSION` 6.2: los dos artefactos que añade son aditivos y opcionales.

## El problema que resuelve

El Top-Down llegaba al Drafter con un plan validado y muy informativo sobre **qué ocurre**. Cada
`PlotEvent` viaja al prompt con su `purpose`, su `dramatic_function`, su `conflict` y su `outcome`.
Nada de eso dice **qué está esperando el lector cuando ocurre**.

La consecuencia se lee en el corpus: prosa correcta, causalmente impecable, que avanza como
relación de hechos. Es el fallo que Sanderson llama *middle aburrido*, y su diagnóstico es
literal: «progress is missing, or it's progressing on the wrong promise».

Había ya dos rastros de la idea en el código, y los dos eran demasiado débiles para cambiar nada:

- `PlotEvent.payoff_of` enlaza un pago con su siembra y `graph.py` valida que apunte siempre hacia
  atrás. Pero **nunca se exige ni se cuenta**: un plan con todos los `payoff_of` vacíos es válido,
  y `relevant_prior_events` ni siquiera recorre ese campo, así que un setup enlazado sólo por ahí
  no llegaba al prompt del Drafter.
- `setup_payoff` existía como categoría de nota de revisión, sin estructura detrás. Sobre el
  corpus de 6.5 y 6.6 medido con `report-story-craft`, los críticos levantaron **una sola** nota
  de esa categoría en todas las historias.

## Qué dice la fuente

Las fuentes son `docs/sanderson-craft.pdf` §2.2 y §3.2 (los apuntes de Alejandro Piad Morffis sobre
la serie de lecturas BYU 318R de 2025), contrastadas con la
[lectura #2 publicada](https://www.brandonsanderson.com/blogs/blog/brandon-sandersons-2025-guide-to-plot-lecture-2)
y con la [exposición de September C. Fawkes](https://www.septembercfawkes.com/2024/10/promise-progress-payoff-in-stories-acts.html).

**Promesa.** Una expectativa que la apertura establece. Cuatro sabores: tono, dirección de la
historia, personaje/conflicto y convención de género. La formulación de Sanderson: «the first
chapter and first few pages are when people will decide whether or not they're going to put your
book down».

**Progreso.** Movimiento *señalizado* hacia la promesa, y el tipo de señal depende de la promesa:
una pista o un sospechoso menos para un misterio, distancia recorrida o mapa revelado para una
búsqueda, algo que el personaje no podía hacer antes para una promesa de competencia, una elección
que no habría tomado en el capítulo uno para una de transformación. El diagnóstico: «a big reason
that people drop off a book is that there weren't enough signposts of progress».

**Pago.** «A surprising but fulfilling answer to your promise». Sorprendente porque un pago
predecible en su forma exacta trata al lector con condescendencia; satisfactorio porque romper la
promesa para sorprender lo estafa.

Y los cuatro modos de fallo, que son directamente categorías de evaluación:

| Síntoma | Causa |
|---|---|
| middle aburrido | falta progreso, o progresa la promesa equivocada |
| final no ganado | el pago no correspondía a la promesa, o no costó nada |
| giro decepcionante | se rompió la promesa para sorprender |
| apertura blanda | las promesas eran vagas, así que los pagos no tienen dónde anclar |

### Sobre cuántas promesas

Ninguna fuente fija un número. Las dos reglas firmes son:

- «The number of payoffs equals the number of promises made» (§2.2.3).
- «Promise density matters… If you've made twenty promises and only have room for ten payoffs,
  **cut promises now**» (§3.2.6).

Por eso el tamaño del ledger se deriva del perfil en `promise_band` (`profiles.py`), a partir de
`PROFILE_CHAPTER_BAND`, y se valida por banda:

| Perfil | Capítulos | Promesas |
|---|---|---|
| Esencial | 2–3 | 2–3 |
| Desarrollada | 4–5 | 3–5 |
| Expansiva | 5–7 | 4–7 |

Los **dos** extremos viajan al prompt. Es la excepción consciente a la regla que
`profiles.py:23-25` documenta para el resto del pipeline —donde un solo número se enseña y se
valida, porque dos números compitiendo hacen que el modelo obedezca al equivocado—. El motivo es
que aquí el techo no es un presupuesto rival: es la regla de oficio misma. Un suelo sin techo
permite exactamente el fallo que la fuente describe.

## La decisión de diseño: el ledger ancla en eventos

El encargo era dar dinamismo a **cómo se escribe** sin tocar **qué se cuenta**. Todo el diseño
cuelga de una sola decisión que convierte esa intención en una imposibilidad estructural:

> Cada apertura, cada progreso y cada pago **cita el `id` de un `PlotEvent` que ya existe**. El
> `chapter_id` no lo escribe el modelo: se deriva del evento anclado.

Tres consecuencias:

1. **El modelo no puede inventar un beat.** Un beat nuevo necesitaría un evento nuevo, y el
   validador sólo acepta ids que estén en el plan.
2. **El orden se comprueba, no se cree.** Apertura < progresos < pago se decide contra
   `plan.topological_order`, sin confiar en lo que el modelo diga sobre su propio orden.
3. **La guía llega pegada al trabajo.** El brief de un capítulo sólo habla de los eventos que ese
   capítulo ya va a dramatizar. Es lo que la convierte en prosa en lugar de en teoría.

## Las invariantes

`materialize_ledger` (`promises.py`) es a este contrato lo que `materialize_plan` es al plan, con
la misma regla de idioma: **los `ValueError` van en inglés y ASCII**, porque `pipeline.py` los
reinyecta literalmente, junto al índice de anclas legales, en el prompt de reparación.

| Invariante | Fuente |
|---|---|
| todo `event_id` citado existe en el plan | el plan es inmutable |
| ids de promesa y de progreso únicos | higiene |
| la promesa primaria existe y es la de `story_direction` | §3.2.9: «What's the central promise?» |
| apertura < todos los progresos < pago, sobre el orden topológico | §2.2 |
| cada promesa tiene al menos un progreso | §2.2.2 |
| `prepared_by_progress_ids` sólo referencia progresos de la propia promesa | «unearned ending» |
| el pago de la promesa primaria cae en el último capítulo | §2.2.3 |
| ninguna promesa abre en el último capítulo | promesa impagable |
| el número de promesas cabe en la banda del perfil | §3.2.6 |

Dos comprobaciones más quedan como **observaciones**, en el campo `observations` del artefacto, y
no rechazan nada: dos promesas que abren y pagan en la misma pareja de eventos, y un pago que cae
sobre un evento cuyo `payoff_of` declara un setup distinto del que la promesa usó como apertura.
Esta segunda es deliberadamente blanda: `payoff_of` es opcional en un plan válido, y exigir que el
ledger lo espeje rechazaría lecturas correctas de planes que simplemente no lo usan.

## Qué se dejó fuera, y por qué

La capa PPP que el repositorio tuvo hasta la v5.0 (`craft_models.py`, `craft.py`,
`agents/craft.py`, eliminados en `3094746`) era mucho más grande: contrato de tono, arcos de
personaje con cuatro evidencias ordenadas, ciclos try-fail, directivas escena/secuela de Swain y
una tabla de alineación. Se fue con la v5.0 porque arrastraba una obligación PPP→STORYLINE que sí
tocaba la estructura.

Esta implementación recupera **sólo el núcleo**, por decisión explícita:

- **Try-fail (`yes, but` / `no, and`)** queda para una implementación posterior. Es la pieza que
  más tienta al modelo a pedir eventos nuevos, y el esquema está hecho para que añadirla después
  sea agregar un campo, no rehacer el ledger.
- **Contrato de tono, arcos de personaje, escena/secuela y MICE** quedan fuera por el mismo
  criterio: cada uno es una capa con su propio coste de prompt y su propia validación, y meterlos
  todos a la vez haría imposible atribuir a ninguno el efecto que se mida.

## Cómo se mide

El interruptor `ASG_PROMISE_LEDGER` existe para esto. Apagado, la etapa no corre, no se escribe
artefacto y los prompts quedan idénticos a la línea base; encendido, es el mismo pipeline con el
contrato encima. Es la única forma de responder si el ledger mejora algo.

`promise_audit.json` da la cifra por run: cuántas promesas quedaron `fulfilled`, `weak` o `broken`
según el Drama Critic, con la cita del borrador que respalda cada veredicto. Una promesa que el
crítico no juzgó cuenta como `broken` — el silencio no es un aprobado, y que falte un veredicto es
justo lo que la auditoría existe para sacar a la luz.

Para el par de runs:

```powershell
$env:ASG_PROMISE_LEDGER='true';  generate-story "<prompt del catalogo>" --profile developed
$env:ASG_PROMISE_LEDGER='false'; generate-story "<el mismo prompt>"      --profile developed
report-story-craft
```

`report-story-craft` da las cifras de artesanía de ambos —diálogo, palabras por frase, palabras por
párrafo— desde `story.md`. Pero ninguna de esas cifras mide lo que este contrato intenta cambiar:
hay que leer el último capítulo de los dos y ver si **juega** el pago o lo cuenta.

## Riesgo conocido

`_validate_note_references` rechaza una nota del crítico que cite ids desconocidos, y
`_critique_and_revise` degrada ese rechazo a un aviso entregando el borrador **sin revisar**. Si el
Drama Critic coloca un id de promesa en `note.event_ids`, se pierde la etapa de revisión entera de
forma casi invisible.

La mitigación es doble y está probada: la instrucción de sistema del crítico dice en tantas
palabras que los ids de promesa van en `promise_checks` y en ningún otro sitio, y
`test_a_promise_id_in_note_event_ids_costs_the_whole_revision` fija el coste exacto del error para
que nadie tenga que redescubrirlo.

## Dónde vive cada cosa

| Pieza | Fichero |
|---|---|
| esquemas del ledger y de los veredictos | `packages/stagecraft/src/asg_stagecraft/schemas.py` |
| validador e invariantes | `packages/stagecraft/src/asg_stagecraft/planning/promises.py` |
| banda de promesas por perfil | `packages/stagecraft/src/asg_stagecraft/planning/profiles.py` |
| agente y su prompt | `packages/stagecraft/src/asg_stagecraft/agents/promises.py` |
| bloques que viajan al prompt | `packages/stagecraft/src/asg_stagecraft/planning/promise_brief.py` |
| etapa, reparación, degradación y auditoría | `packages/stagecraft/src/asg_stagecraft/pipeline.py` |

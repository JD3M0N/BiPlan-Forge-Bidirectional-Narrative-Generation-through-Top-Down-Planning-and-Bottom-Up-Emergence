# Generación y escritura

Referencia de contratos vigentes. Lee solo las secciones del subsistema que vayas a cambiar.
Las reglas generales están en [AGENTS.md](../../AGENTS.md).

## Organización

Dentro de `stagecraft`, los módulos van por subpaquete:

| Subpaquete | Contenido |
|---|---|
| `runtime/` | configuración, proveedor, cuota, almacenamiento, errores, progreso y su reporte (`reporting.py`) |
| `planning/` | perfiles, longitud pedida, grafo, esqueletos, promesas, reparación y las etapas de plan (`stages.py`) |
| `writing/` | auditoría, evidencia de artesanía, ensamblado, aceptación y las etapas de escritura (`stages.py`) |
| `script/` | validación, render y etapas del guion |
| `stage/` | la función simulada, su narración (`narration_stage.py`) y el árbitro del inventario |
| `tools/` | los comandos: `generate`, `baseline`, `extract_features`, `budget`, `recovery`, `recompute` |

En la raíz quedan la fachada y el contrato: `__init__`, `version`, `formats`, `options`,
`brief`, `schemas`, `generator`, `pipeline` y `agents/`.

## Las opciones de un run son un solo objeto

- `GenerationOptions` (`options.py`) es la única definición de lo que se elige por run: formato,
  perfil, ledger, guía, audio y su voz, visión, personaje de la visión (`narrator`), tono,
  memoria y turnos por beat. Se valida una vez y cada run la guarda en
  `generation_options.json`.
- `StoryGenerator` conserva kwargs explícitos, uno por campo, y `test_generation_options.py`
  falla si un campo y un kwarg dejan de coincidir. Las superficies usan `GenerationOptions.from_settings` y
  `StoryGenerator.from_options`; `StoryPipeline` recibe solo `options=`.
- Añadir una opción: campo en `GenerationOptions` con `Field(title=, description=)` en español,
  kwarg en la fachada, consumirlo donde vive el mecanismo (sin tocar los prompts cuando está
  apagada) y, si la interfaz la muestra, su entrada en `apps/studio/src/asg_studio/catalog.py`.
  El bot no ofrece opciones: las toma todas del `.env`.
- **Los brazos de 7.17 están apagados por defecto** y van en `API_ONLY_OPTIONS`, cada uno con
  su variable `ASG_*` y su flag de `asg-generate`: `style_examples`, `line_editor`,
  `scene_cards`, `anchored_critic`, `narration_method` (`reported` o `selected`) y
  `typed_clauses`. Apagados, el comportamiento es el de 7.16 más los arreglos siempre activos. El
  predeterminado cambia solo por lectura humana a ciegas (SIM-25, TD-10 y SIM-26).
- **Dos replays para comparar sobre la misma entrada.**
  - `asg-generate --narrate-from <run>` narra otra vez una función guardada sin representarla:
    unas 12 llamadas frente a 130. Registra las opciones de la función de origen.
  - `--plan-from` reutiliza el plan también con `--format narrative`.
  - Los dos escriben `source_run.json` con `reused`.
- `StoryBrief` (`brief.py`) es la obra estructurada: trama y reparto se componen en un prompt
  determinista que el analista lee como cualquier otro, así que `StoryRequest` y el esquema que
  va a Gemini no cambian. El run guarda `brief.json`.
  - Desde 7.20, un prompt libre con la forma exacta de una ficha se lee de vuelta
    (`StoryBrief.from_prompt`, `[BRIEF_FROM_PROMPT]`): en 7.19 la ficha de las islas se pegó
    como prompt y su reparto no llegó como canon.
  - `StoryPipeline.execute` repara también un prompt con UTF-8 leído como Windows-1252
    (`[PROMPT_ENCODING_REPAIRED]`). Windows PowerShell 5.1 los pasa así por argv; para eso está
    `asg-generate --prompt-file`.

## Top-Down: el plan es un DAG validado, no texto

El flujo es `StoryGenerator` (fachada pública en `generator.py`) → `StoryPipeline.execute`
(`pipeline.py`), que recorre las etapas de `CHECKPOINT_STAGES`:

- analysis, architecture, world, characters, planning, plan_review, promises;
- drafting, critique, revision;
- adaptation, solo en el método adaptado del guion;
- casting, props, performance, narration, solo en el formato simulado;
- story, audio.

Cada etapa llama a un agente de `agents/` y persiste su artefacto antes de seguir. Lo que hace
este pipeline distinto de «pedirle una historia al modelo»:

- **`planning/graph.py` es el árbitro.** `materialize_plan` valida invariantes objetivos: ids
  únicos, órdenes consecutivos, dependencias sin ciclos, referencias a capítulos, personajes y
  objetos existentes, y `payoff_of` apuntando siempre hacia atrás. Calcula con un Kahn estable
  el único orden de eventos en el que confía el resto del sistema. Un plan que no valida se
  rechaza y se reintenta.
- **`topological_order` se persiste aunque sea derivable, a propósito** (decisión de ING-7).
  Coincide con ordenar por `order` en los 71 planes del corpus. Pero es la salida del árbitro,
  lo leen siete módulos y más de 180 runs, y quitarlo obligaría a subir `PIPELINE_VERSION` y a
  mantener una lectura compatible sin ganar nada medible.
- **Los mensajes de error de `graph.py` van en inglés a propósito.** `_record_rejected_plan` los
  reinyecta literalmente en el prompt de reparación (`planning/repair.py`). Son parte del
  contrato con el LLM, no texto para el usuario: no traducirlos.
- **`planning/profiles.py` define contratos cualitativos, no presupuestos de palabras.**
  - Esencial, Desarrollada y Expansiva se expresan como texto en `PROFILE_GUIDANCE`, que es
    **puramente cualitativo a propósito**: viaja en el prompt de todos los agentes, y un número
    ahí competía con el del planificador, y el modelo obedecía al de la guía.
  - `PROFILE_CHAPTER_BAND` es advisory, pero fija el objetivo de eventos vía
    `MIN_EVENTS_PER_CHAPTER`.
  - El extremo bajo de ese objetivo, `profile_event_floor` (4, 8 y 10), es **el único número**
    que se enseña al planificador y que `validate_profile_structure` impone.
  - `MIN_EVENTS_PER_CHAPTER` también se valida: un capítulo con un solo evento rechaza el plan.
  - Al planificador se le enseña además `profile_event_aim`, el centro de la banda, para que no
    apunte a la frontera de rechazo.
- **La longitud que pide la persona elige el perfil, en código** (`planning/length.py`, 7.20).
  - Lo que lee:
    - el perfil nombrado;
    - las palabras, en cifras o en letra: hasta 2.000 Esencial, hasta 4.000 Desarrollada, más
      Expansiva;
    - las páginas, a 300 palabras;
    - «N capítulos», por las bandas;
    - «historia extensa», «corta» o «novela corta», siempre junto al sustantivo.
  - El analista solo decide si la petición no dice nada de su tamaño.
  - Un `--profile` forzado sigue mandando, pero si contradice la petición el run lo dice con
    `[PROFILE_CONFLICT]`.
  - Las cifras eligen el perfil y nunca viajan a un prompt.
- **Los reintentos son por perfil.** `PLAN_ATTEMPTS_BY_PROFILE` da a Expansiva un intento
  extra, porque es la única con contrato de rama y reunión causal.
- **Los fallos se clasifican.** `runtime/errors.py` define `ASGError` con código, etapa, resumen
  seguro y recomendaciones. `NON_DEGRADABLE_ERRORS` (configuración y cuotas de Gemini) aborta el
  run; el resto se degrada a warning en `metadata.json` y la historia sigue.
- **`planning/skeletons.py` y `skeleton_match.py`** rankean esqueletos de trama por mezcla léxica
  y semántica, y producen un `NarrativeBlueprint` que se inyecta como inspiración en la cabecera
  compartida de prompts (`agents/base.py`). Es guía, no restricción.
- **El ledger de promesas ancla en eventos, y por eso no puede tocar el plan.**
  - La etapa `promises` corre con el plan ya congelado. `agents/promises.py` traza un contrato
    Promise-Progress-Payoff en el que cada apertura, progreso y pago **cita el id de un
    `PlotEvent` que ya existe**. El `chapter_id` no lo escribe el modelo: se deriva del evento.
  - `planning/promises.py` lo valida contra `plan.topological_order`, con mensajes en inglés que
    se reinyectan igual que los de `graph.py`.
  - `planning/promise_brief.py` lo convierte en obligaciones por capítulo para el Drafter, el
    Writer y el Drama Critic.
  - Cambia **cómo se escribe** el plan, nunca qué contiene: un test compara `story_plan.json`
    byte a byte con y sin ledger.
  - La etapa es degradable, como la del arquitecto.
  - `promise_band` es la excepción consciente a «un solo número viaja al prompt»: viajan suelo y
    techo, porque el techo *es* la regla de oficio («si has prometido veinte cosas y solo caben
    diez pagos, corta promesas»).
- **El ledger se puede apagar, y esa es la medición.** `ASG_PROMISE_LEDGER=false` (o
  `promise_ledger=False` en la fachada) salta la etapa entera. Es el brazo de control, y
  `promise_audit.json` da la cifra.

## Guía narrativa experimental (7.8)

`GenerationOptions.guidance_strategy` conserva `hybrid_v1` por defecto y ofrece
`compositional_v2` por API/CLI. `narrative_guidance=False` omite ambas estrategias.
Las opciones experimentales sin control visual se declaran en `API_ONLY_OPTIONS`.

- El catálogo de 34 patrones vive en `planning/data/skeletons.json`; `catalog.py` lo carga,
  valida y calcula su hash. `catalog_types.py` contiene los roles sin depender de `schemas`.
- `guidance_retrieval.py` recupera por relevancia semántica, con desempate estable por catálogo y abstención
  ante fallo semántico; `guidance_composition.py` valida referencias y alcance contextual. Cada etapa
  admite una reparación. Cuota, configuración y cancelación se propagan.
- `guidance_render.py` produce bloques distintos para personajes y planificación; el blueprint
  v2 guarda los textos exactos. Los críticos y escritores no reciben la guía.
- La abstención es válida y guarda bloques vacíos. Un fallo de composición guarda diagnóstico
  y continúa sin guía; la recuperación se persiste antes de componer.
- Las solicitudes y el protocolo se conservan en el
  [experimento de guía](../../packages/stagecraft/experiments/guidance/README.md).
  El preparador `plan-guidance-experiment` se retiró en 7.11; ese documento indica cómo
  recuperar su versión histórica. La mejora literaria sigue pendiente de evaluación humana;
  no cambiar el predeterminado por resultados de tests.

## Top-Down: salida en guion teatral, dos métodos, un solo contrato

`ASG_STORY_FORMAT=script` (o `--format script`) pide un guion por escenas en vez de prosa;
`narrative` sigue siendo el defecto. Hay dos métodos, seleccionables con `ASG_SCRIPT_METHOD`
(`native` por defecto o `adapted`), implementados los dos para compararlos a ciegas y quedarse
con uno. Es la ficha EXP-3 de `planning/fichas.md`.

- **Nativo**: tras `promises`, `PlaywrightAgent` escribe cada capítulo del plan directamente
  como un acto de escenas estructurado, con el mismo bucle de reparación que `graph.py`. Lo
  revisa `ScriptCriticAgent` y lo corrige `ScriptWriterAgent`.
- **Adaptado**: el pipeline narrativo corre entero sin tocar sus prompts y guarda su prosa como
  `prose.md`. Después, `ScriptAdapterAgent` convierte cada capítulo en un acto a través del
  **mismo** validador.

Los dos terminan en el mismo contrato: `script.json` (`PlayScript`) y un `story.md` renderizado
por `script/render.py`.

- **`script/validation.py`** valida cada acto contra el plan congelado. Sus `ValueError` van en
  inglés ASCII por la misma razón que los de `graph.py`.
- Normaliza más de lo que rechaza: una forma con una sola corrección posible se corrige.
  Rechaza los anclajes a eventos, el orden de las escenas, la ubicación y el reparto.
- La orquestación vive aparte, en **`script/stages.py`**, porque el experimento es temporal:
  borrar el método perdedor toca un solo archivo.

Detalles en [docs/resumen.md](../../docs/resumen.md).

## Escritura y edición

- **El Writer de Top-Down edita párrafos, no reescribe el capítulo** (7.18, TD-3).
  - Reescribiendo el capítulo entero, Flash-Lite devolvía el borrador: 17 de 29 intentos, al 95 %
    o más.
  - Ahora devuelve `ParagraphEdits` (`replace` o `insert_after`, cada edición con las notas que
    cita) y `writing/chapter_edits.py` las aplica.
  - `writing/acceptance.writer_edit_issue` da `NOTE_NOT_APPLIED` a la nota grave sin edición
    aceptada, y a la nota de artesanía cuya observación sobrevive.
  - El reintento y la elección del mejor candidato viven en `writing/revision_loop.py`, que
    comparte con el Script Writer. Si ningún intento pasa, se entrega el mejor, nunca una copia.
  - La corrección va **delante** de los párrafos; detrás del cuerpo, el modelo la ignoraba.
    No vuelvas a pedir el capítulo entero.
- **El editor por fragmentos (7.17, `line_editor`) solo ve los párrafos que marca el código.**
  Lo hace `asg_core.craft.paragraph_flags`, y `writing/line_edit.py` acepta una edición solo si
  la marca baja, no alarga, no inventa nombres ni réplicas y no cambia el tiempo verbal. Sirve
  para los dos formatos.
- **Prosa para un lector cualquiera** (7.12). `agents/style.py` es el contrato de estilo del
  Drafter, el Writer y el Narrator, y `request.style_request` lleva el registro que pidió la
  persona, literal. `writing/craft_evidence.craft_notes` convierte cada observación medida
  (también nombres repetidos, coletillas y símiles) en una nota para el Writer aunque el
  crítico no dé ninguna.
  - Hasta 7.19, «coletilla» solo medía la que explica la emoción («con una mezcla de…»).
  - `GERUND_TAGS` (7.20) mide la del gerundio («—dijo, señalando…»), que llevaba el 67-83 % de
    las réplicas del corpus sin que ninguna nota lo dijera.
- **Ninguna cifra viaja a un prompt**, como en el resto del pipeline, y un test lo comprueba
  sobre las etapas nuevas.

## Idioma de la ficción

- **La frontera de idioma de la ficción** (7.14).
  - Planifican en inglés: análisis, mundo, plan, promesas y la parte interna de los dossiers.
  - Escriben en el idioma de la ficción los actores, el narrador, los títulos, los nombres y los
    roles.
  - `writing/language.py` marca un campo corto que se escapó al otro idioma, y
    `LocalizerAgent` traduce solo esos campos, nunca la prosa. Una traducción final de la
    historia entera aplanaría la voz que se evalúa y rompería las citas al log: es la ficha
    EXP-9, no el defecto.

## Orquestación

- **`StoryPipeline` es una fachada de mixins** (7.20, ING-3).
  - `pipeline.py` (723 líneas) guarda `execute*`, el análisis, el repositorio y el cierre.
  - Las etapas viven en mixins, uno por mitad: `planning/stages.py`, `writing/stages.py`,
    `script/stages.py`, `stage/stages.py` y `stage/narration_stage.py`.
  - El progreso, los eventos y el uso van en `runtime/reporting.py`, que define
    `CHECKPOINT_STAGES`. `pipeline.py` la reexporta porque los tests la leen de ahí.
  - Un mixin llama a lo que define otro a través de `self`: búscalo por nombre en todos.
  - Falta la otra mitad de ING-3: etapas con estado propio que eliminen los
    `assert self.repository is not None`. No lo hagas de paso dentro de otro cambio.

## Precauciones

- **`materialize_act` pone en el acto el título del plan, que está en inglés.** Desde 7.2.0
  `assemble_play` lo sustituye por el título localizado de la presentación antes de renderizar, y
  el formato simulado sigue leyéndolos de `script_presentation.json` (`_localized_titles`). Si
  añades otro camino que construya un `PlayScript`, hazlo pasar por `assemble_play`.

## Orientación del lector (7.21)

- `writing/orientation.py` conserva contexto del lector con citas verificadas de la prosa
  final; haber actuado no equivale a haber sido presentado.
- Las auditorías de presentación y continuidad espacial se ejecutan al redactar y tras editar.
  Las reparaciones por párrafos deben conservar fidelidad y mejorar los hallazgos.
- En el híbrido, el contexto público se filtra por las escenas visibles. La actuación valida
  acciones espaciales antes de incorporarlas y registra cuando la revisión no está disponible.
- Contratos y regresiones en `test_reader_orientation.py`; el detalle de la versión está en el
  [changelog de Stagecraft](../../packages/stagecraft/CHANGELOG.md).

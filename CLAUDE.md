# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Guía para agentes que trabajen en este repositorio de tesis.

## Qué es este proyecto

Monorepo de investigación que genera y evalúa historias narrativas con un solo generador,
**Stagecraft** (`packages/stagecraft`), y dos enfoques:

- **Top-Down** (formatos `narrative` y `script`): pipeline de agentes LLM sobre Gemini que
  planifica primero (mundo, personajes, grafo de eventos) y escribe después, en prosa o como
  guion teatral.
- **Híbrido** (formato `simulated`): el mismo plan se escribe como guion, los personajes lo
  **representan** con memoria propia, y la historia se narra del log de esa función. Ver
  [docs/resumen.md](docs/resumen.md).

El paquete se llamaba `top_down`; se renombró cuando dejó de ser solo top-down.

El resto del monorepo:

- `packages/evaluation` guarda las evaluaciones humanas y los tres informes del corpus.
- `packages/core` guarda las utilidades compartidas.
- `apps/console` es la interfaz de terminal.
- `apps/telegram` expone el generador como bot.
- `apps/studio` es **StageCraft**, la interfaz gráfica local (web, FastAPI y JS sin build).

Hubo un tercer enfoque, **Bottom-Up**: una simulación multiagente determinista de una sala de
escape (`packages/escape_room`). Se retiró en 7.1.1 porque el formato simulado lo sustituye. Sus 6
runs siguen en `Stories/Bottom-Up/` como datos históricos, y `evaluation` los sigue leyendo.

## Entorno y comandos

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt   # los 5 paquetes en editable + pytest/ruff
```

Copiar `.env.example` a `.env`. `GEMINI_API_KEY` solo hace falta para generar de verdad: los
tests usan proveedores falsos.

Comandos (opciones completas en [commands.md](commands.md)):

- `generate-story`, `compare-story-runs`, `recover-story-runs`, `audit-stage-run`,
  `recompute-simulation-metrics` (Stagecraft).
- `report-evaluations`, `report-story-craft`, `report-simulations` (evaluation).
- `asg-console`, `asg-telegram`, `asg-telegram-run`, `asg-studio` (apps).

### Calidad: ejecutar siempre antes de dar por terminado un cambio

```powershell
.\quality.ps1        # ruff check, ruff format --check, run-tests.ps1 y pip check
.\quality.ps1 -Fast  # solo run-tests.ps1, para iterar
```

- `quality.ps1` se sitúa en la raíz por su cuenta y no corta en el primer fallo, igual que CI.
  `make test` delega en él.
- `.github/workflows/quality.yml` corre las mismas cuatro comprobaciones en `windows-latest` con
  Python 3.12, en cada push a `main` y en cada pull request, llamando a `run-tests.ps1` igual que
  en local. Un status check `quality` en rojo bloquea el merge.

### Tests: un solo comando, siempre la suite entera

```powershell
.\run-tests.ps1
```

- **Es el único comando para correr los tests de este repositorio.** Nunca lances `pytest`
  directo, ni un archivo suelto, ni `-k`: correr un subconjunto no dice si el cambio rompió algo
  en otro paquete, y cada vuelta extra gasta contexto sin ganar nada que la vuelta completa no
  diera ya. `run-tests.ps1` tarda menos de un minuto.
- Redirige el temporal de pytest a `.cache/pytest-tmp`, porque el temporal por defecto de Windows
  falla con `PermissionError` en algunos entornos de sandbox.
- Filtra las líneas de progreso: si todo pasa, la salida es una sola línea; si algo falla, quedan
  los `FAILED` y sus tracebacks cortos, nada más.
- `quality.ps1` y `.github/workflows/quality.yml` lo llaman tal cual: local y CI corren
  exactamente lo mismo.
- Admite argumentos de pytest después de `--` para depurar un fallo puntual mientras se investiga
  (`.\run-tests.ps1 -- packages/stagecraft/tests/test_graph.py -k revision`), pero eso no
  sustituye la vuelta completa antes de dar el cambio por terminado.
- `pyproject.toml` fija `testpaths = ["packages", "apps", "tests"]`, así que la suite recoge todo
  el monorepo sin argumentos.
- Todas las pruebas usan proveedores falsos salvo `packages/stagecraft/tests/test_gemini_live.py`,
  que se omite a menos que `RUN_GEMINI_LIVE=1`. **No activarlo** sin que lo pida explícitamente
  quien manda la tarea: consume cuota real.

### Tests: los mínimos posibles, y corregidos cuando cambie el código que cubren

Cada test cuesta tokens para leerlo, mantenerlo y correrlo, en cada vuelta, para siempre. Antes
de añadir uno:

- **Uno por comportamiento, no por caso.** Varios casos del mismo camino van en un solo test
  parametrizado (`@pytest.mark.parametrize`), no en tests independientes que repiten el mismo
  cuerpo.
- **Ampliar antes que crear.** Si un test ya ejercita el camino que hace falta cubrir, añadir una
  fila a su tabla o una aserción a su cuerpo, en vez de escribir uno nuevo.
- **Reutilizar antes que generar.** Donde exista una función o un run ya construido para otro
  test (un fixture de sesión, un doble compartido), leerlo en vez de montar una ejecución propia
  del pipeline: son las pruebas más caras de correr.
- **Nada de constantes ni tautologías.** Un test que solo repite un literal del código de
  producción, o que no puede fallar aunque el código esté roto, no aporta nada; no se escribe.
- **Cuando un cambio toca un método importante** (su firma, el contrato que cumple, el formato de
  un artefacto o el texto de un prompt), **corregir en el mismo cambio los tests que lo cubren**,
  y borrar los que prueben un comportamiento que ya no existe. No dejar tests rotos, saltados ni
  relajados para que la suite pase en verde sin que el cambio esté completo.
- **Los tests de contrato no se tocan sin querer.** Cuando este documento o un doc de `docs/`
  cita un test por su nombre exacto (por ejemplo,
  `test_no_actor_ever_sees_the_plan_or_a_future_scene` en
  [docs/resumen.md](docs/resumen.md)), ese nombre y lo que verifica se
  mantienen; si hace falta reescribirlo, se actualiza también el documento que lo cita.
- Los dobles y constructores compartidos del pipeline (`FakeProvider`, `make_request`,
  `valid_plan`…) viven en `packages/stagecraft/tests/test_generator_v5.py`, y otros módulos los
  importan de ahí.

## Arquitectura

### Dependencias entre paquetes

```text
core  ←  evaluation  ←  stagecraft  ←  console, telegram, studio
```

- `core` no depende de nada del repo.
- `evaluation` **nunca** importa `stagecraft`: lee solo JSON y Markdown del disco. Por eso abre
  un run de cualquier versión, incluidos los históricos, mucho después de que cambie el código
  que lo escribió.
- Respetar esa dirección.

Dentro de `stagecraft`, los módulos van por subpaquete:

| Subpaquete | Contenido |
|---|---|
| `runtime/` | configuración, proveedor, cuota, almacenamiento, errores, progreso |
| `planning/` | perfiles, grafo, esqueletos, promesas, reparación |
| `writing/` | auditoría, evidencia de artesanía, ensamblado, aceptación |
| `script/` | validación, render y etapas del guion |
| `stage/` | la función simulada y el árbitro del inventario |
| `tools/` | los comandos: `generate`, `compare`, `recovery`, `audit_stage`, `recompute` |

En la raíz quedan la fachada y el contrato: `__init__`, `version`, `formats`, `options`,
`brief`, `schemas`, `generator`, `pipeline` y `agents/`.

### Las opciones de un run son un solo objeto

- `GenerationOptions` (`options.py`) es la única definición de lo que se elige por run: formato,
  perfil, ledger, guía, audio y su voz, visión, personaje de la visión (`narrator`), tono,
  memoria y turnos por beat. Se valida una vez y cada run la guarda en
  `generation_options.json`.
- `StoryGenerator` conserva kwargs explícitos, uno por campo: la consola y Telegram prueban la
  fachada con `create_autospec(spec_set=True)`, y `test_generation_options.py` falla si un
  campo y un kwarg dejan de coincidir. Las superficies usan `GenerationOptions.from_settings` y
  `StoryGenerator.from_options`; `StoryPipeline` recibe solo `options=`.
- Añadir una opción: campo en `GenerationOptions` con `Field(title=, description=)` en español,
  kwarg en la fachada, consumirlo donde vive el mecanismo (sin tocar los prompts cuando está
  apagada) y, si la interfaz la muestra, su entrada en `apps/studio/src/asg_studio/catalog.py` y
  su `OptionSpec` en `apps/telegram/src/asg_telegram/generators.py`.
- `StoryBrief` (`brief.py`) es la obra estructurada: trama y reparto se componen en un prompt
  determinista que el analista lee como cualquier otro, así que `StoryRequest` y el esquema que
  va a Gemini no cambian. El run guarda `brief.json`.

### Top-Down: el plan es un DAG validado, no texto

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

### Top-Down: salida en guion teatral, dos métodos, un solo contrato

`ASG_STORY_FORMAT=script` (o `--format script`) pide un guion por escenas en vez de prosa;
`narrative` sigue siendo el defecto. Hay dos métodos, seleccionables con `ASG_SCRIPT_METHOD`
(`native` por defecto o `adapted`), implementados los dos para compararlos a ciegas y quedarse
con uno. Es la ficha EXP-3 del `TODO.md`.

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

Detalles en [docs/resumen.md](docs/resumen.md).

### Top-Down: artefactos de un run

`ArtifactRepository` (`runtime/storage.py`) crea `Stories/Stagecraft/<AAAAMMDD-HHMMSS>-<slug>/` y
escribe todo de forma atómica. Serializa con `asg_core.artifact_json`, porque necesita el texto
exacto para el hash del manifiesto.

El run contiene:

- estado: `metadata.json` (estado, etapas completadas, warnings, error) y
  `pipeline_manifest.json` (sha256 y tamaño de cada artefacto);
- plan: `request.json`, `world.json`, `characters.json`, `story_plan.json`;
- promesas: `promise_ledger.json`, `promise_audit.json`;
- escritura: `chapters/`, `revisions/`, `draft.md`, `story.md`, `story.mp3`;
- medición: `story_metrics.json`, `llm_calls.jsonl` y `llm_usage.json`.

A esa lista, el guion y el simulado añaden los suyos.

- **Los artefactos guardan también los prompts.** `promise_ledger.json` guarda el contrato **y
  los bloques de prompt exactos** que se inyectaron (`chapter_blocks`, `critic_block`), igual que
  `craft_evidence.json`. Así un run terminado se audita sin volver a derivar qué se le dijo a
  cada agente.
- **`promise_audit.json`** cruza el contrato con los veredictos del crítico. Una promesa que el
  crítico no juzgó cuenta como `broken`, porque el silencio no es un aprobado.
- **`story_metrics.json`** registra tamaño y artesanía observados: palabras, capítulos, eventos,
  proporción de párrafos con diálogo, palabras por frase y por párrafo, también por capítulo.
  Ninguna de esas cifras viaja a ningún prompt: son observaciones, no objetivos.
  `report-story-craft` las recalcula desde `story.md`, así que también mide los runs anteriores
  a 6.5.0, que no las traen.

`version.py` fija `PIPELINE_VERSION` (7.6) y `SUPPORTED_PIPELINE_VERSIONS` (de 5.0 a 7.6).
`StoryRun` se niega a abrir un run incompleto o de una versión no soportada. Si cambias el
conjunto de artefactos o su significado, sube la versión en vez de romper los runs ya generados:
son datos de la tesis. Una limpieza que no toca artefactos sube solo el parche de
`__version__`, como 7.1.1.

Las 160 ejecuciones anteriores al renombrado siguen en `Stories/Top-Down/` y se siguen leyendo.
`recover-story-runs --stories Stories/Top-Down` las recupera.

### Top-Down: proveedor y cuota

`runtime/provider.py` expone el `Protocol` `LanguageModelProvider` (`generate_structured` con
esquema Pydantic, y `generate_text`) e implementa `GeminiProvider`. Lo que importa al tocarlo:

- La temperatura sale de perfiles nombrados (`extraction`, `review`, `planning`, `prose`,
  `rewrite`), no de constantes sueltas en los agentes.
- `_gemini_response_schema` borra `additionalProperties` del esquema porque algunos modelos
  Gemini lo rechazan. Pydantic sigue siendo la autoridad local con `extra="forbid"`.
- `_safe_provider_error` clasifica los fallos sin filtrar credenciales ni el contenido del
  prompt.
- Los limitadores de RPM (`_LIMITERS` en `provider.py`, con las clases de `runtime/quota.py`) se
  **comparten a nivel de proceso**: dos generaciones concurrentes respetan un único presupuesto
  de RPM.
  - La clave de cada limitador es (huella de la clave, modelo, capacidad), porque Gemini cuenta la
    cuota por proyecto y por modelo. Desde 7.4, dos modelos no comparten ventana aunque tengan el
    mismo RPM.
  - El limitador de TPM, en cambio, es por instancia.
- **La función simulada puede ir con un modelo propio** (7.4).
  - `GEMINI_STAGE_MODEL`, `GEMINI_STAGE_API_KEY` y `GEMINI_STAGE_RPM_LIMIT`; vacíos heredan los
    principales.
  - Si difieren, `provider_from_settings` devuelve un `RoutedProvider`, que enruta por la etapa
    que `_call_agent` ya declara (`call_context`). Solo `performance` (turnos, reflexiones y
    director de escena) va al modelo de la función (`STAGE_MODEL_STAGES`). El casting y la
    narración siguen en el principal, y la auditoría también, porque no corre dentro de una etapa.
  - Los dos proveedores comparten `usage_records` y los callbacks del run, así que el pipeline
    ve uno solo. Ningún agente ni doble de test sabe del reparto.
  - `metadata.json` lo registra en `stage_model`, que es `None` si la función usó `model`. El eje
    `stage_model` de `evaluation/pairing.py` impide emparejar funciones de modelos distintos.

Los tests inyectan un `FakeProvider` (ver `packages/stagecraft/tests/test_generator_v5.py`), que es
la forma canónica de probar el pipeline. Se le pasa una secuencia de respuestas estructuradas y
puede forzar fallos en llamadas concretas.

### Híbrido: la función simulada

`ASG_STORY_FORMAT=simulated` (o `--format simulated`) añade tres etapas tras el guion nativo. El
diseño completo está en [docs/resumen.md](docs/resumen.md); lo que hay
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
- **El respaldo es contrato.** Si el casting, la utilería o la narración no pueden correr,
  `stage/casting.py`, `stage/props.py` y `stage/fallback.py` derivan un resultado determinista.
  El run lo registra y sigue.
- **Ninguna cifra viaja a un prompt**, como en el resto del pipeline, y un test lo comprueba
  sobre las etapas nuevas.
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

### evaluation: informes que solo leen

- **La metodología de evaluación de la tesis está en
  [packages/evaluation/METODOLOGIA.md](packages/evaluation/METODOLOGIA.md)**, fiel al audio del
  tutor: rasgos contables con cita (la planilla `packages/evaluation/planilla/`), pares humanos a
  ciegas en tres criterios y un juez aprendido. Las seis métricas 1-10 de `evaluation.json` son
  un instrumento heredado. Los CSV de la planilla son la fuente: tras editarlos, regenerar el
  Excel con `python packages/evaluation/planilla/build_planilla.py`.
- `report-evaluations`, `report-story-craft` y `report-simulations` comparten los lectores
  tolerantes de `artifacts.py`: un artefacto ausente, roto o de otro tipo cuenta como ausente,
  nunca como fallo.
- Una cifra que un run no registró se informa como **no medida**, nunca como cero.
- El enfoque se infiere de la carpeta:
  - `Stories/Stagecraft` y `Stories/Top-Down` dan `Top-Down`, o `Hybrid` si el formato es
    simulado;
  - cualquier otra carpeta da su nombre, y así `Stories/Bottom-Up` sigue agrupado como
    `Bottom-Up`.
- El formato de `evaluation.json` y los ejes de los informes están en
  [packages/evaluation/README.md](packages/evaluation/README.md).

### Telegram: el bot no conoce el pipeline

- `contract.py` define, del lado de la aplicación, el `Protocol` `StoryGeneratorAdapter` y sus
  tipos (`GenerationProgress`, `RunSummary`, `GenerationFailure`, `OptionSpec`, `StoryOutline`,
  `BriefSpec`, `GeneratorUnavailable`).
- Los handlers, la entrega y la consola hablan solo ese contrato. `generators.py` tiene los
  adaptadores que traducen un pipeline concreto: al añadir un generador se escribe un adaptador,
  no se tocan las conversaciones. Es el único módulo que importa `asg_stagecraft`; un fallo de
  configuración se envuelve en `GeneratorUnavailable`, no en el error crudo del pipeline.
- `STORY_GENERATOR` vale `stagecraft`, que es el único generador registrado.
- **Cada usuario configura sus propias opciones desde el chat.** `/settings` (o `/opciones`)
  abre un panel de botones sobre `option_specs`, que el adaptador construye a partir de los
  campos de `GenerationOptions` y sus etiquetas (`options.py`, `formats.py`,
  `planning/profiles.py`). Las preferencias se guardan por usuario en la cola
  (`QueueRepository.user_options`), como *overrides* dispersos: solo las claves que el usuario
  cambió, para que un valor nuevo del `.env` siga llegando a quien no tocó esa opción.
  `generators.StagecraftGenerator.normalize_options` fusiona, resuelve el formato y valida con
  `GenerationOptions.with_changes`, traduciendo los errores de Pydantic al español.
- **La obra guiada construye un `StoryOutline`,** no un prompt de texto: título, género,
  ambientación, trama, hasta `MAX_CAST` personajes (nombre, rol, pronombre, descripción y
  secreto) y notas. `wizard.py` tiene el flujo puro; `handlers.py` lo conecta. El adaptador la
  convierte en `StoryBrief` justo antes de llamar al pipeline.
- **La cancelación pasa `should_cancel` a `generate()`,** nunca lanza desde el callback de
  progreso: `generation.py` construye `lambda: queue.cancellation_requested(job_id)` y el
  adaptador traduce `RunCancelledError` a `GenerationCancelled`.
- `queue.py` es una cola FIFO SQLite durable (`Stories/telegram_queue.sqlite3`) con migración de
  esquema (v4 añade `options`, `brief` y la tabla `user_options`) y cancelación, y
  `generation.py` la coordina con la entrega.
- `console.py` y `terminal.py` dan la consola del operador: una cabecera con el bot, las
  versiones, el modelo y la cuota, y un registro de una línea por evento. La ventana que abre
  `asg-telegram` (`launcher.py`) no se cierra si el bot falla al arrancar o se detiene por un
  error: espera una tecla, para que el error no se pierda con la ventana.
- Cualquier fallo que escape de un adaptador sin ser `GenerationFailure` se considera un defecto
  interno y se reporta como error inesperado.

### StageCraft: la interfaz gráfica

- `asg-studio` sirve en `127.0.0.1:8765` una app FastAPI y una página en HTML, CSS y módulos ES
  sin paso de build. Detalle en [apps/studio/README.md](apps/studio/README.md).
- **Las opciones se pintan desde `catalog.py`.** Las etiquetas vienen del generador
  (`formats.py`, perfiles, voces de `asg_core`); las opciones **pendientes** (las que el
  roadmap aún no construye) viven solo ahí, con su ficha. Un test cruza cada `kind` del
  catálogo con su renderizador en `static/js/ui.js`.
- **La cola tiene un solo hilo** (`jobs.py`) y un generador nuevo por trabajo. Se cancela con
  `should_cancel`.
- **Nunca escribe ni borra en `Stories/`.** La biblioteca y la comparación leen con los lectores
  tolerantes de evaluation (`pairing.py`).
- **Seguridad local:** toda escritura exige la cabecera `X-StageCraft: 1`, el `Host` debe ser
  local y la CSP solo permite los archivos propios. El texto del modelo se pinta con
  `textContent`.
- Los tests usan un generador falso y una carpeta temporal (`tests/studio_fakes.py`); nunca
  Gemini.

### Consola

Dos menús: generar con Stagecraft y evaluar cualquier historia de `Stories/`. `ConsoleApp` y los
menús reciben `input_fn` y `output` inyectados (`types.py`), que es como los tests recorren los
menús sin terminal. Mantener esa inyección al añadir pantallas.

### core

- `find_project_root` sube por el árbol buscando un directorio con `Stories/` y `packages/`. Se
  puede forzar con `ASG_PROJECT_ROOT`, útil si se despliega en un contenedor.
- `files.py` da la escritura atómica UTF-8 (`atomic_write_text`, `atomic_write_json`,
  `atomic_write_csv`) y `artifact_json`, el formato JSON de los artefactos por separado.
- `locks.py` da `file_lock`, que serializa las evaluaciones del bot y de la consola.
- `console.py` da `use_utf8_output`, lo primero que llaman los comandos de Stagecraft, de
  evaluation y `asg-console`. Sin él, una consola de Windows imprime mojibake.
- `audio.py` hace la narración con edge-tts.
- `craft.py` calcula las cifras de artesanía de la prosa (`craft_metrics`), puras y
  deterministas. Vive en `core` porque la usan `writing/audit.py` y `evaluation`, y `evaluation`
  no puede importar `stagecraft`.

## Convenciones de idioma (con verificación automática)

- **Docstrings de código de producción** (`apps/*/src`, `packages/*/src`): en **inglés**, breves
  y no tautológicas. Lo exige `tests/test_source_documentation.py`, que falla si falta el
  docstring o si no es ASCII.
  - Exige docstring incluso en closures.
  - Ojo con los guiones largos y las comillas tipográficas: no son ASCII y el gate los rechaza.
- **Texto visible para el usuario, artefactos e historias**: en **español**.
- **Excepción deliberada:** los mensajes de `ValueError` de `planning/graph.py`,
  `planning/promises.py`, `script/validation.py`, `stage/validation.py` y `stage/casting.py` van
  en inglés porque se reinyectan en el prompt del modelo.
- `Stories/`, PDFs y experimentos son datos de investigación: **nunca** se eliminan en tareas de
  limpieza, aunque estén en `.gitignore`. Eso incluye `Stories/Bottom-Up/`, aunque el código que
  lo generó ya no exista.

## TODO.md es la fuente de verdad del roadmap

- Antes de proponer trabajo nuevo, revisarlo.
- Las tareas van en tres secciones según lo que hace falta para moverlas: **Lo siguiente**,
  **Pendiente** e **Ideas**. Dentro de cada una, el orden de la lista es el orden sugerido. No
  hay etiquetas de prioridad.
- Cada ficha tiene un **ID estable** por área: `MED`, `SIM`, `TD`, `EXP`, `ING` y `OPS`.
  - Citarlo en commits y docs, por ejemplo «cierra SIM-3».
  - Un ID no se reutiliza. Las ideas no llevan ID hasta que suben de sección.
- Debajo del título, una línea de metadatos: área, cuota que cuesta validarla («sin cuota» o
  «~N llamadas») y de qué fichas depende.
- Cada tarea tiene el mismo esqueleto: **Síntoma** (con ruta y cifra), **Qué hacer**, **Hecho
  cuando** y, solo si hace falta, **Ojo**.
- Dos secciones fijas antes de las fichas:
  - **Ruta crítica**: el orden en que las fichas desbloquean la tesis.
  - **Protocolo de medición**: presupuesto de cuota, emparejamiento, ruido y cómo leer a los
    jueces LLM. Una ficha `EXP` no repite esas reglas: las cumple.
- Si la tarea de la sesión coincide con un ítem, trabajar contra su «Hecho cuando» y borrar el
  ítem al cerrarlo: el historial vive en git, no en el roadmap.
- La cabecera lleva una línea «Estado medido el <fecha>…» con los recuentos del corpus y la puerta
  de calidad. Actualizarla si el estado medido cambia sustancialmente.

## Trampas conocidas

- **`tests/test_source_documentation.py` solo exige que haya texto en inglés.** Desde 7.2.0
  resuelve sus rutas desde el propio archivo y falla si no encuentra módulos, así que ya no pasa
  en vacío desde otro directorio. Pero acepta docstrings plantilla («Represent X data and
  behavior.»): eso queda en la ficha ING-1 del `TODO.md`.
- **`ruff format` también formatea los bloques de Python dentro del Markdown.** Un ejemplo mal
  formateado en un README de paquete hace fallar `ruff format --check`. `docs/` y `Stories/`
  están excluidos en `pyproject.toml`.
- **`README.md` está vacío (0 bytes) a propósito.** Se redacta al cerrar el proyecto, cuando los
  contratos públicos ya no se muevan. No lo rellenes antes aunque parezca una mejora barata;
  cuando llegue el momento, guárdalo en UTF-8.
- **`.gitignore` ignora `docs/*` salvo siete archivos en lista blanca.** Si creas un doc nuevo en
  `docs/` y quieres que se versione, añádelo también a esa lista.
- **`.cache/` contiene sqlite y cachés de pytest de experimentos previos**
  (`pytest-top-down-*`, `pytest-profile-*`…). Son artefactos de ejecución: no razonar sobre el
  estado del proyecto a partir de sus nombres.
- **`pipeline.py` (1197 líneas) y `skeletons.py` (1485) siguen siendo grandes.** La
  reorganización 7.0.0 sacó de `pipeline.py` los prompts de reparación, el ensamblado y las
  reglas de aceptación; lo que queda es la ficha ING-3 del `TODO.md`. No lo hagas de paso
  dentro de otro cambio.
- **Dos serializadores de JSON distintos a propósito.**
  - `agents/base.json_text` serializa lo que viaja al **prompt**: convierte modelos Pydantic y no
    añade salto de línea final.
  - `asg_core.artifact_json` serializa lo que va a **disco**.
  - No unificarlos: cambiaría cada prompt, y hay tests que fijan su texto literal.
- **`materialize_act` pone en el acto el título del plan, que está en inglés.** Desde 7.2.0
  `assemble_play` lo sustituye por el título localizado de la presentación antes de renderizar, y
  el formato simulado sigue leyéndolos de `script_presentation.json` (`_localized_titles`). Si
  añades otro camino que construya un `PlayScript`, hazlo pasar por `assemble_play`.
- **Un `GEMINI_BILLING_LIMIT_EXHAUSTED` del corpus no es facturación.** Los tres que hay son la
  cuota diaria gratuita: su `error_report.json` trae
  `quota_id: GenerateRequestsPerDayPerProjectPerModel-FreeTier`. El proveedor los clasificó mal
  porque el 429 estándar de Gemini contiene la palabra «billing»; desde 7.2.0 manda `quota_id`.
  En un run anterior, lee `quota_id`, no el código.
- **Quién lo sabe ya ≠ quién lo descubrirá.** En una compuerta de `cast_bible.json`, `known_by`
  es quién sabe el hecho **antes de la primera escena**. Quien lo deduce o descubre en escena va
  en `revealed_by`, con `how`, y **no** en `known_by`. El primer run real los confundió y le dio
  al detective la solución de partida. `stage/casting.py` lo rechaza desde 7.1; no relajes esa
  validación para que pase un casting.
- **El esquema del turno con objetos solo se pide con el inventario activo.**
  `ActorTurnWithItemsDraft` es un modelo aparte de `ActorTurnDraft` a propósito: el esquema
  cruza al proveedor, así que un campo de objeto presente pero sin usar cambiaría todas las
  peticiones de actor del corpus. Si añades otro camino que pida un turno, elige el esquema
  según si hay árbitro, nunca añadas el campo al modelo base.
- **Dos cifras de `simulation_metrics.json` que se leyeron al revés una vez.**
  - `repetition_ratio` solo mira el **habla**, palabra a palabra. No ve paráfrasis ni gestos;
    para eso está `action_repetition_ratio`.
  - `dialogue_survival` cerca de 1 significa que el narrador **transcribió**, no que fuera fiel.
- **Las funciones 7.0 y 7.1 no son comparables sin más con las de 7.2.**
  - Hasta 7.1.1 `CharacterMemory.recall` no aplicaba su tope: cada actor leía toda su memoria
    anterior, y su `retrievals.json` no filtra nada.
  - El esquema pedía `addressed_to` por ids que el actor nunca veía, así que casi no hay
    destinatarios ni susurros.
  - La nota del director se repetía hasta la siguiente lectura.

  Los tres están arreglados en 7.2.0 (SIM-9 y SIM-10). Al comparar versiones, sepáralas por
  `pipeline_version`.
- **Un actor escribe destinatarios por nombre; el log guarda ids.** `normalize_turn` resuelve el
  nombre (completo, de pila o una palabra que identifique a un solo personaje presente) y descarta
  lo ambiguo. Los ids nunca entran en el contexto del actor: no los añadas para «ayudar».
- **Un run se cancela con `should_cancel`, nunca lanzando desde un callback.** El callback de
  progreso también corre dentro del bucle de reintentos del proveedor, que convierte cualquier
  excepción en un `ProviderError` degradable, y `_record_failure` vuelve a emitir eventos. El
  pipeline consulta `should_cancel` al entrar en `_call_agent` y lanza `RunCancelledError`, que
  está en `NON_DEGRADABLE_ERRORS`. Telegram también pasa `should_cancel` a `generate()` (cerrado
  en 3.0.0 del bot, antes ficha OPS-3).
- **El `callback_data` de un botón de Telegram tiene un máximo de 64 bytes.** Los paneles de
  opciones y del asistente guiado (`panel.py`, `wizard.py`) codifican índices en vez de valores
  para no acercarse al límite; un test recorre cada teclado y lo comprueba.
- **Los dobles de audio de los tests reciben solo `story_path`.** Por eso el pipeline pasa
  `voice=` a `create_story_audio_sync` solo cuando hay una voz elegida.
- **Windows puede servir `.js` como `text/plain`**, y el navegador no ejecuta así un módulo ES:
  la página saldría en blanco. `asg_studio/app.py` registra el tipo al importarse.

## Documentos de referencia

- [docs/resumen.md](docs/resumen.md): resumen único del diseño (plan, promesas, guion, función
  simulada, validación 7.5). Junto a él, en `docs/`, los dos PDF fuente de la tesis: Roger Fuentes
  y *Sanderson Craft*. El catálogo de prompts se retiró; el prompt canónico vive en
  `test_gemini_live.py`.
- [packages/evaluation/METODOLOGIA.md](packages/evaluation/METODOLOGIA.md): cómo se evalúa la
  tesis, con su planilla de rasgos y su estado del arte.
- [packages/evaluation/README.md](packages/evaluation/README.md): el formato de
  `evaluation.json`, las seis métricas humanas y los tres informes.
- [commands.md](commands.md): los comandos, en una línea cada uno.

El informe de artesanía de la prosa (6.5.0 contra 6.6.0 y su réplica de ruido), la calibración de
perfiles de 6.0 y el recorrido de etapas de 6.2 se retiraron en 7.1.1 porque describían
versiones pasadas. Siguen en git: `git show 38b3b8e:docs/<nombre>.md`.

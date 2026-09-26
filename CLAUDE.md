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
  [docs/simulacion_escenica.md](docs/simulacion_escenica.md).

El paquete se llamaba `top_down`; se renombró cuando dejó de ser solo top-down.

El resto del monorepo:

- `packages/evaluation` guarda las evaluaciones humanas y los tres informes del corpus.
- `packages/core` guarda las utilidades compartidas.
- `apps/console` es la interfaz de terminal.
- `apps/telegram` expone el generador como bot.

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

- `generate-story`, `compare-story-runs`, `recover-story-runs`, `audit-stage-run` (Stagecraft).
- `report-evaluations`, `report-story-craft`, `report-simulations` (evaluation).
- `asg-console`, `asg-telegram`, `asg-telegram-run` (apps).

### Calidad: ejecutar siempre antes de dar por terminado un cambio

```powershell
.\quality.ps1        # ruff check, ruff format --check, pytest, pip check y el test de PowerShell
.\quality.ps1 -Fast  # solo pytest, para iterar
```

- `quality.ps1` se sitúa en la raíz por su cuenta y no corta en el primer fallo, igual que CI.
  `make test` delega en él.
- `.github/workflows/quality.yml` corre las mismas cinco comprobaciones en `windows-latest` con
  Python 3.12, en cada push a `main` y en cada pull request. Un status check `quality` en rojo
  bloquea el merge.
- Si lanzas `pytest` a mano, hazlo **desde la raíz** (ver «Trampas conocidas»).

### Iterar rápido

```powershell
python -m pytest packages/stagecraft/tests -q          # un subsistema
python -m pytest packages/stagecraft/tests/test_graph.py -q
python -m pytest packages/stagecraft/tests/test_generator_v5.py -q -k revision
```

- `pyproject.toml` fija `testpaths = ["packages", "apps", "tests"]`, así que `pytest` sin
  argumentos recoge todo el monorepo.
- `tests/test_sync_railway_stories.ps1` es un test de PowerShell que pytest **no** recoge. Lo
  lanzan `quality.ps1` y CI.
- Todas las pruebas usan proveedores falsos salvo `packages/stagecraft/tests/test_gemini_live.py`,
  que se omite a menos que `RUN_GEMINI_LIVE=1`. **No activarlo** sin que lo pida explícitamente
  quien manda la tarea: consume cuota real.

## Arquitectura

### Dependencias entre paquetes

```text
core  ←  evaluation  ←  stagecraft  ←  console, telegram
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
| `stage/` | la función simulada |
| `tools/` | los comandos: `generate`, `compare`, `recovery`, `audit_stage` |

En la raíz quedan la fachada y el contrato: `__init__`, `version`, `formats`, `schemas`,
`generator`, `pipeline` y `agents/`.

### Top-Down: el plan es un DAG validado, no texto

El flujo es `StoryGenerator` (fachada pública en `generator.py`) → `StoryPipeline.execute`
(`pipeline.py`), que recorre las etapas de `CHECKPOINT_STAGES`:

- analysis, architecture, world, characters, planning, plan_review, promises;
- drafting, critique, revision;
- adaptation, solo en el método adaptado del guion;
- casting, performance, narration, solo en el formato simulado;
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

Detalles en [docs/guion_teatral.md](docs/guion_teatral.md).

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

`version.py` fija `PIPELINE_VERSION` (7.1) y `SUPPORTED_PIPELINE_VERSIONS` (de 5.0 a 7.1).
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
- `runtime/quota.py` mantiene limitadores de ventana deslizante **compartidos a nivel de
  proceso** (`_LIMITERS`): dos generaciones concurrentes respetan un único presupuesto de
  RPM/TPM.

Los tests inyectan un `FakeProvider` (ver `packages/stagecraft/tests/test_generator_v5.py`), que es
la forma canónica de probar el pipeline. Se le pasa una secuencia de respuestas estructuradas y
puede forzar fallos en llamadas concretas.

### Híbrido: la función simulada

`ASG_STORY_FORMAT=simulated` (o `--format simulated`) añade tres etapas tras el guion nativo. El
diseño completo está en [docs/simulacion_escenica.md](docs/simulacion_escenica.md); lo que hay
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
- **El narrador cura, no transcribe.** Puede cortar, fundir y reordenar dentro de un capítulo,
  pero no puede inventar un beat. Donde el plan y el log no coincidan, manda el log.
- **El respaldo es contrato.** Si el casting o la narración no pueden correr, `stage/casting.py`
  y `stage/fallback.py` derivan un resultado determinista. El run lo registra y sigue.
- **Ninguna cifra viaja a un prompt**, como en el resto del pipeline, y un test lo comprueba
  sobre las etapas nuevas.

### evaluation: informes que solo leen

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
  tipos (`GenerationProgress`, `RunSummary`, `GenerationFailure`).
- Los handlers, la entrega y la consola hablan solo ese contrato. `generators.py` tiene los
  adaptadores que traducen un pipeline concreto: al añadir un generador se escribe un adaptador,
  no se tocan las conversaciones.
- `STORY_GENERATOR` vale `stagecraft` por defecto. `top-down` sigue registrado como alias porque
  el despliegue de Railway lo tiene configurado. No quitarlo sin cambiar antes esa variable.
- `queue.py` es una cola FIFO SQLite durable (`Stories/telegram_queue.sqlite3`) con migración de
  esquema y cancelación, y `generation.py` la coordina con la entrega.
- Cualquier fallo que escape de un adaptador sin ser `GenerationFailure` se considera un defecto
  interno y se reporta como error inesperado.

### Consola

Dos menús: generar con Stagecraft y evaluar cualquier historia de `Stories/`. `ConsoleApp` y los
menús reciben `input_fn` y `output` inyectados (`types.py`), que es como los tests recorren los
menús sin terminal. Mantener esa inyección al añadir pantallas.

### core

- `find_project_root` sube por el árbol buscando un directorio con `Stories/` y `packages/`. Se
  puede forzar con `ASG_PROJECT_ROOT`, útil en contenedores; el `Dockerfile` instala solo core,
  evaluation, stagecraft y telegram.
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

- **`tests/test_source_documentation.py` puede pasar en vacío.**
  - Su glob `*/src/**` es relativo al directorio de trabajo: ejecutar pytest desde otro sitio
    hace que no vea ningún archivo y pase en silencio.
  - Su marcador `"configuraci?n"` está corrupto y nunca puede coincidir. No lo uses como
    referencia de qué detecta el filtro.
  - Es la ficha ING-1 del `TODO.md`.
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
- **`materialize_act` pone en el acto el título del plan, que está en inglés**, no el
  localizado. Los títulos localizados viven en `script_presentation.json`. El formato simulado
  los lee de ahí (`_localized_titles`); el formato guion todavía imprime los del plan. Está
  dentro de la ficha TD-2 del `TODO.md`.
- **Un `GEMINI_BILLING_LIMIT_EXHAUSTED` del corpus no es facturación.** Los tres que hay son la
  cuota diaria gratuita: su `error_report.json` trae
  `quota_id: GenerateRequestsPerDayPerProjectPerModel-FreeTier`. El proveedor clasifica mal
  porque el 429 de Gemini contiene la palabra «billing». Lee `quota_id`, no el código. Es la
  ficha MED-1 del `TODO.md`.
- **Quién lo sabe ya ≠ quién lo descubrirá.** En una compuerta de `cast_bible.json`, `known_by`
  es quién sabe el hecho **antes de la primera escena**. Quien lo deduce o descubre en escena va
  en `revealed_by`, con `how`, y **no** en `known_by`. El primer run real los confundió y le dio
  al detective la solución de partida. `stage/casting.py` lo rechaza desde 7.1; no relajes esa
  validación para que pase un casting.
- **Dos cifras de `simulation_metrics.json` que se leyeron al revés una vez.**
  - `repetition_ratio` solo mira el **habla**, palabra a palabra. No ve paráfrasis ni gestos;
    para eso está `action_repetition_ratio`.
  - `dialogue_survival` cerca de 1 significa que el narrador **transcribió**, no que fuera fiel.
- **`CharacterMemory.recall` no aplica su tope** (SIM-9). Devuelve toda la memoria de escenas
  anteriores, no los 6 recuerdos más 2 reflexiones del diseño. Hasta cerrar la ficha, no leas
  `retrievals.json` ni los pesos de `stage/memory.py` como si filtraran, ni compares funciones de
  antes y después del arreglo como si tuvieran la misma memoria.
- **El actor nunca ve los ids de personaje**, y el esquema le pide `addressed_to` por id. Lo que no
  coincide con un id se descarta sin aviso en `normalize_turn`: por eso casi no hay destinatarios
  ni susurros (SIM-10).

## Documentos de referencia

- [docs/simulacion_escenica.md](docs/simulacion_escenica.md): la función simulada. Por qué los
  actores no ven el guion, cómo funciona la memoria propia y su ablación, el bucle de escena, el
  punto de vista modular, los artefactos y qué se mide.
- [docs/estado_del_arte_simulacion.md](docs/estado_del_arte_simulacion.md): las cuarenta
  referencias que sostienen ese diseño, con qué se tomó y qué se descartó de cada una.
- [docs/marco_hibrido.md](docs/marco_hibrido.md): el marco teórico de la tesis. La paradoja
  narrativa, la tradición híbrida (Façade, Thespian, Virtual Storyteller, Sabre), su versión con
  LLM, por qué memoria propia, y qué afirma la tesis y cómo se mide.
- [docs/mejoras_simulacion.md](docs/mejoras_simulacion.md): el diagnóstico de la actuación en los
  runs 7.1 y las mejoras propuestas, cada una con su respaldo y su ficha del `TODO.md`.
- [docs/guion_teatral.md](docs/guion_teatral.md): el formato guion. Los dos métodos, el contrato
  de `script.json`, qué valida `script/validation.py` y qué solo corrige, y cómo comparar los
  métodos.
- [docs/promesas_ppp.md](docs/promesas_ppp.md): el contrato Promise-Progress-Payoff. Qué dice la
  fuente, qué invariantes se formalizaron, cuáles se dejaron fuera y cómo se mide el efecto.
- [docs/prompts_top_down.md](docs/prompts_top_down.md): el catálogo canónico de prompts (7
  prompts × 3 perfiles) sobre el que se mide cada versión. `test_gemini_live.py` lee el prompt 1
  entre sus marcadores, así que no se renombra ni se reestructura sin tocar ese test.
- [packages/evaluation/README.md](packages/evaluation/README.md): el formato de
  `evaluation.json`, las seis métricas humanas y los tres informes.
- [commands.md](commands.md): todos los comandos con sus opciones.

El informe de artesanía de la prosa (6.5.0 contra 6.6.0 y su réplica de ruido), la calibración de
perfiles de 6.0 y el recorrido de etapas de 6.2 se retiraron en 7.1.1 porque describían
versiones pasadas. Siguen en git: `git show 38b3b8e:docs/<nombre>.md`.

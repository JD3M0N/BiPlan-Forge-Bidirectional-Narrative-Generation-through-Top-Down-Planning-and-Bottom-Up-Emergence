# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Guía para agentes que trabajen en este repositorio de tesis.

## Qué es este proyecto

Monorepo de investigación que genera y evalúa historias narrativas con tres enfoques:

- **Top-Down** (`packages/stagecraft`, formatos `narrative` y `script`): pipeline de agentes LLM
  sobre Gemini que planifica primero (mundo, personajes, grafo de eventos) y escribe después.
- **Híbrido** (`packages/stagecraft`, formato `simulated`): el mismo plan se escribe como guion,
  los personajes lo **representan** con memoria propia, y la historia se narra del log de esa
  función. Ver [docs/simulacion_escenica.md](docs/simulacion_escenica.md).
- **Bottom-Up** (`packages/escape_room`): simulación multiagente determinista de una sala de
  escape; la historia se narra a partir del log de eventos ya ocurridos.

El paquete se llama `stagecraft` (antes `top_down`) porque ya no es solo top-down: planifica de
arriba abajo y, en el formato simulado, deja que los personajes actúen de abajo arriba.

`packages/evaluation` guarda las evaluaciones humanas, `packages/core` las utilidades compartidas.
`apps/console` es la interfaz de terminal y `apps/telegram` expone el generador como bot.

## Entorno y comandos

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt   # instala los 6 paquetes en editable + pytest/ruff
```

Copiar `.env.example` a `.env`. `GEMINI_API_KEY` es opcional: sin ella los tests usan proveedores
falsos y `run-escape-room --no-llm` genera la historia de respaldo determinista.

Comandos expuestos (detalles en [commands.md](commands.md)): `asg-console`, `generate-story`,
`compare-story-runs`, `recover-story-runs`, `run-escape-room`, `report-evaluations`,
`report-story-craft`, `report-simulations`, `asg-telegram`, `asg-telegram-run`.

### Calidad — ejecutar siempre antes de dar por terminado un cambio

```powershell
.\quality.ps1        # las cinco comprobaciones; `make test` delega en este script
.\quality.ps1 -Fast  # sólo pytest, para iterar
```

`quality.ps1` se sitúa en la raíz por su cuenta y no corta en el primer fallo, igual que CI.
Equivale a lanzar a mano:

```powershell
ruff check .
ruff format --check .
python -m pytest -q -p no:cacheprovider
python -m pip check
```

`.github/workflows/quality.yml` corre estas cuatro más el test de PowerShell en `windows-latest`
con Python 3.12, en cada push a `main` y en cada pull request: un status check `quality` en rojo
bloquea el merge. Lanzarlas en local sigue siendo lo que evita el viaje de ida y vuelta con CI.
Lanzar `pytest` **desde la raíz**: `tests/test_source_documentation.py` resuelve su glob contra el
directorio de trabajo y pasa en vacío desde cualquier otro sitio.

### Iterar rápido

```powershell
python -m pytest packages/stagecraft/tests -q          # un subsistema
python -m pytest packages/stagecraft/tests/test_graph.py -q
python -m pytest packages/stagecraft/tests/test_generator_v5.py -q -k revision
```

`pyproject.toml` fija `testpaths = ["packages", "apps", "tests"]`, así que `pytest` sin argumentos
recoge todo el monorepo. `tests/test_sync_railway_stories.ps1` **no** lo recoge pytest: es un test
de PowerShell que hay que lanzar a mano en local, aunque `.github/workflows/quality.yml` sí lo
ejecuta en cada push y pull request.

Las pruebas de Top-Down y Bottom-Up usan proveedores falsos y nunca llaman a la API real, salvo
`packages/stagecraft/tests/test_gemini_live.py`, que se omite a menos que `RUN_GEMINI_LIVE=1`. **No
activarlo** sin que lo pida explícitamente quien manda la tarea: consume cuota real.

## Arquitectura

### Dependencias entre paquetes

```text
core  ←  evaluation  ←  stagecraft, escape_room  ←  console, telegram
```

`core` no depende de nada del repo; `stagecraft` y `escape_room` no se conocen entre sí. `telegram`
depende de `stagecraft` pero **no** de `escape_room`; `console` sí de los dos. Respetar esa
dirección: es lo que permite comparar los enfoques sin contaminarlos.

Dentro de `stagecraft`, los módulos van por subpaquete: `runtime/` (configuración, proveedor,
cuota, almacenamiento, errores, progreso), `planning/` (perfiles, grafo, esqueletos, promesas,
reparación), `writing/` (auditoría, evidencia de artesanía, ensamblado, aceptación), `script/`
(validación, render, etapas, métricas del guion), `stage/` (la función simulada) y `tools/` (los
comandos). En la raíz quedan la fachada y el contrato: `__init__`, `version`, `formats`, `schemas`,
`generator`, `pipeline` y `agents/`.

### Top-Down: el plan es un DAG validado, no texto

El flujo real es `StoryGenerator` (fachada pública en `generator.py`) → `StoryPipeline.execute`
(`pipeline.py`), que recorre las etapas de `CHECKPOINT_STAGES`: analysis, architecture, world,
characters, planning, plan_review, promises, drafting, critique, revision, adaptation,
casting, performance, narration, story, audio. `adaptation` solo corre en el método adaptado del
formato guion, y `casting`, `performance` y `narration` solo en el formato simulado. Cada etapa
llama a un agente de `agents/` y persiste su artefacto antes de seguir.

Lo que hace este pipeline distinto de "pedirle una historia al modelo":

- **`planning/graph.py` es el árbitro.** `materialize_plan` valida invariantes objetivos (ids únicos,
  órdenes consecutivos, dependencias sin ciclos, referencias a capítulos/personajes/objetos
  existentes, `payoff_of` apuntando siempre hacia atrás) y calcula el único orden de eventos en el
  que confía el resto del sistema, vía un Kahn estable. Un plan que no valida se rechaza y se
  reintenta.
- **Los mensajes de error de `graph.py` van en inglés a propósito.** `_record_rejected_plan`
  los reinyecta literalmente en el prompt de reparación estructural del modelo: son parte del
  contrato con el LLM, no texto para el usuario. No traducirlos.
- **`profiles.py` define contratos cualitativos, no presupuestos de palabras.** Esencial /
  Desarrollada / Expansiva se expresan como texto de contrato (`PROFILE_GUIDANCE`), que es
  **puramente cualitativo a propósito**: viaja dentro del prompt de todos los agentes, así que
  un número ahí competía con el del planificador y el modelo obedecía al de la guía.
  `PROFILE_CHAPTER_BAND` sigue siendo advisory, pero determina el objetivo de eventos vía
  `MIN_EVENTS_PER_CHAPTER`, y el extremo bajo de ese objetivo (`profile_event_floor`: 4, 8 y
  10) es **el único número** que se enseña al planificador y que `validate_profile_structure`
  impone. `MIN_EVENTS_PER_CHAPTER` también se valida: un capítulo con un solo evento rechaza
  el plan. Al planificador se le enseña además `profile_event_aim`, el centro de la banda,
  para que no apunte a la frontera de rechazo.
- **Los reintentos son por perfil.** `PLAN_ATTEMPTS_BY_PROFILE` da a Expansiva un intento extra
  porque es la única con contrato de rama y reunión causal (`validate_profile_structure`).
- **Los fallos se clasifican.** `runtime/errors.py` define `ASGError` con código, etapa, resumen seguro y
  recomendaciones. `NON_DEGRADABLE_ERRORS` (configuración y cuotas de Gemini) aborta el run; el
  resto se degrada a warning en `metadata.json` y la historia sigue.
- **`skeletons.py` + `skeleton_match.py`** rankean esqueletos de trama por mezcla léxica y
  semántica y producen un `NarrativeBlueprint` que se inyecta como inspiración en la cabecera
  compartida de prompts (`agents/base.py`). Es guía, no restricción.
- **El ledger de promesas ancla en eventos, y por eso no puede tocar el plan.** La etapa
  `promises` corre con el plan ya congelado: `agents/promises.py` traza un contrato
  Promise-Progress-Payoff en el que cada apertura, progreso y pago **cita el id de un `PlotEvent`
  que ya existe**; el `chapter_id` no lo escribe el modelo, se deriva del evento. `promises.py`
  lo valida contra `plan.topological_order` —con mensajes en inglés que se reinyectan igual que
  los de `graph.py`— y `promise_brief.py` lo convierte en obligaciones por capítulo que viajan al
  Drafter, al Writer y al Drama Critic. Cambia **cómo se escribe** el plan, nunca qué contiene:
  hay un test que compara `story_plan.json` con y sin ledger byte a byte. La etapa es degradable
  como la del arquitecto, y `promise_band` es la excepción consciente a la regla de «un solo
  número viaja al prompt»: aquí viajan suelo y techo, porque el techo *es* la regla de oficio
  («si has prometido veinte cosas y solo caben diez pagos, corta promesas»), no un presupuesto
  que compita con otro.
- **El ledger se puede apagar, y esa es la medición.** `ASG_PROMISE_LEDGER=false` (o
  `promise_ledger=False` en la fachada) salta la etapa entera. Es el brazo de control para
  comparar corpus con y sin contrato de promesas; `promise_audit.json` da la cifra.

### Top-Down: salida en guion teatral, dos métodos, un solo contrato

`ASG_STORY_FORMAT=script` (o `story_format=StoryFormat.SCRIPT` en la fachada) pide un guion
teatral por escenas en vez de la prosa narrativa de siempre; `narrative` sigue siendo el defecto,
así que no elegir nada no cambia nada. Hay dos métodos, seleccionables con `ASG_SCRIPT_METHOD`
(`native` por defecto, o `adapted`), porque no se sabe cuál da mejor guion: se implementaron los
dos para compararlos a ciegas y quedarse con uno (ítem abierto en `TODO.md`).

- **Nativo**: tras `promises`, `PlaywrightAgent` escribe cada capítulo del plan directamente como
  un acto de escenas estructurado, con el mismo bucle de reparación que `graph.py` y
  `promises.py`; lo revisa `ScriptCriticAgent` y lo corrige `ScriptWriterAgent`.
- **Adaptado**: el pipeline narrativo corre entero sin tocar sus prompts, guarda su prosa como
  `prose.md`, y `ScriptAdapterAgent` convierte cada capítulo final en un acto a través del
  **mismo** validador.

Los dos terminan en el mismo contrato: `script.json` (`PlayScript`) más un `story.md` renderizado
por `script_render.py`. `script.py`, hermano de `graph.py` y `promises.py`, valida cada acto
contra el plan congelado con la misma regla de idioma: sus `ValueError` van en inglés ASCII
porque se reinyectan literales en el prompt de reparación. Normaliza más de lo que rechaza —una
forma con una sola corrección posible se corrige, no se rechaza—; lo que sí rechaza son los
anclajes a eventos, el orden de las escenas, la ubicación y el reparto. La orquestación de las
dos etapas de guion vive aparte, en `script_stages.py`, precisamente porque el experimento es
temporal: borrar el método perdedor toca un solo archivo. Detalles, contrato de `script.json` y
cómo comparar los dos métodos en
[docs/guion_teatral.md](docs/guion_teatral.md).

### Top-Down: artefactos de un run

`ArtifactRepository` (`runtime/storage.py`) crea `Stories/Stagecraft/<AAAAMMDD-HHMMSS>-<slug>/` y escribe
todo de forma atómica. El run contiene `metadata.json` (estado, etapas completadas, warnings,
error), `pipeline_manifest.json` (sha256 y tamaño de cada artefacto), `request.json`, `world.json`,
`characters.json`, `story_plan.json`, `promise_ledger.json`, `promise_audit.json`, `chapters/`,
`revisions/`, `draft.md`, `story.md`, `story.mp3`, `story_metrics.json`, `llm_calls.jsonl` y
`llm_usage.json`.

`promise_ledger.json` guarda el contrato de promesas **y los bloques de prompt exactos** que se
inyectaron (`chapter_blocks`, `critic_block`), igual que `craft_evidence.json` guarda el suyo: un
run terminado se audita sin volver a derivar qué se le dijo a cada agente. `promise_audit.json`
cruza ese contrato con los veredictos del crítico; una promesa que el crítico no juzgó cuenta como
`broken`, porque el silencio no es un aprobado.

`story_metrics.json` registra tamaño y artesanía observados —palabras, capítulos, eventos,
proporción de párrafos con diálogo, palabras por frase y palabras por párrafo, también por
capítulo— y ninguna de esas cifras viaja a ningún prompt: son observaciones, no objetivos.
`report-story-craft` las recalcula desde `story.md` para comparar versiones del generador, incluidos
los runs anteriores a 6.5.0 que no las traen; la metodología y las mediciones están en
[docs/artesania_narrativa.md](docs/artesania_narrativa.md).

`version.py` fija `PIPELINE_VERSION` (7.0) y `SUPPORTED_PIPELINE_VERSIONS`; `StoryRun` se niega a
abrir un run incompleto o de una versión no soportada. Si cambias el conjunto de artefactos o su
significado, sube la versión en vez de romper los runs ya generados: son datos de la tesis.

Las 160 ejecuciones anteriores al renombrado siguen en `Stories/Top-Down/` y se siguen leyendo:
las versiones 5.0 a 6.2 están en `SUPPORTED_PIPELINE_VERSIONS` y `report-story-craft` las agrupa
igual que antes. `recover-story-runs --stories Stories/Top-Down` las recupera.

### Top-Down: proveedor y cuota

`runtime/provider.py` expone el `Protocol` `LanguageModelProvider` (`generate_structured` con esquema
Pydantic y `generate_text`) e implementa `GeminiProvider`. Detalles que importan al tocarlo:

- La temperatura sale de perfiles nombrados (`extraction`, `review`, `planning`, `prose`,
  `rewrite`), no de constantes sueltas en los agentes.
- `_gemini_response_schema` borra `additionalProperties` del esquema Pydantic porque algunos
  modelos Gemini lo rechazan; Pydantic sigue siendo la autoridad local con `extra="forbid"`.
- `_safe_provider_error` clasifica los fallos sin filtrar credenciales ni el contenido del prompt.
- `runtime/quota.py` mantiene limitadores de ventana deslizante **compartidos a nivel de proceso**
  (`_LIMITERS`), así que dos generaciones concurrentes respetan un único presupuesto de RPM/TPM.

Los tests inyectan un `FakeProvider` (ver `packages/stagecraft/tests/test_generator_v5.py`), que es
la forma canónica de probar el pipeline: se le pasa una secuencia de respuestas estructuradas y
puede forzar fallos en llamadas concretas.

### Híbrido: la función simulada

`ASG_STORY_FORMAT=simulated` (o `--format simulated`) añade tres etapas tras el guion nativo. El
diseño completo está en [docs/simulacion_escenica.md](docs/simulacion_escenica.md); lo que hay que
saber antes de tocar `stage/`:

- **Los actores nunca ven el guion.** Al intérprete le llegan las circunstancias, su objetivo, la
  nota del director y su propia memoria. Nada del plan: ni ids, ni títulos, ni escenas futuras.
  `stage/validation.strip_internal_ids` limpia el objetivo y el escenario porque los escribió el
  Dramaturgo mirando el plan. Hay un test que recorre un run entero comprobándolo.
- **La memoria propia es la aportación.** Cada personaje tiene su flujo y solo entra lo que
  percibió: un turno público lo ven los que están en escena, un susurro solo sus destinatarios, y
  un pensamiento solo quien lo piensa. **No hay almacén común del que filtrar**: lo que no se
  presenció no se escribió. `--actor-memory shared` es el brazo de control de esa medición.
- **La recuperación es determinista y sin embeddings.** Relevancia léxica, recencia por escenas,
  importancia y compañía, con los pesos documentados en `stage/memory.py`. Mismo run, misma
  puntuación, en cualquier máquina y sin servicios externos.
- **Las relaciones se consolidan, no se acumulan.** La reflexión sustituye la postura anterior; el
  historial se queda en los registros. Un actor que guardara «aliada» y «me traicionó» a la vez
  jugaría mal las dos.
- **El director sugiere, nunca dicta.** Da motivaciones, no réplicas. Cuando un beat agota su
  presupuesto (`ASG_STAGE_TURNS_PER_BEAT`, 8) lo cierra con un `stage_event`: algo que hace el
  mundo, visible, que entra al log como un turno más. Así el log sigue siendo la única fuente.
- **Los `ValueError` de `stage/validation.py` y `stage/casting.py` van en inglés ASCII**, por la
  misma razón que los de `graph.py`: se reinyectan literales en el prompt de reparación.
- **El punto de vista es modular.** `stage/voices.py` tiene una estrategia por voz, cada una con su
  filtro determinista sobre el log. Añadir un punto de vista es añadir una estrategia, nunca una
  rama en el prompt del narrador. El defecto es `omniscient`.
- **El narrador cura, no transcribe.** Puede cortar, fundir y reordenar dentro de un capítulo; no
  puede inventar un beat. Donde el plan y el log no coincidan, manda el log.
- **Ninguna cifra viaja a un prompt**, como en el resto del pipeline, y hay un test que lo
  comprueba sobre las etapas nuevas.

### Bottom-Up: simulación determinista

`EscapeRoomModel` (`engine.py`) ejecuta un bucle por tick de percibir → proponer → resolver.
Cada personaje tiene **creencias parciales** (`domain.py`: `Beliefs`) que solo crecen con lo que
ve dentro del radio de percepción; la política (`policy.py`) decide sobre esas creencias, nunca
sobre el estado real del mundo. `actions.py` resuelve acciones simultáneas y `world.py` carga y
valida la configuración de la sala desde los mapas.

**El determinismo es una invariante de investigación**: misma semilla y misma configuración deben
dar el mismo log de ticks. Todo recorrido de diccionarios va ordenado y la aleatoriedad pasa por
un único `random.Random(seed)`. No introducir iteración no determinista ni estado global.

`narrative.py` convierte el `EventLog` en prosa, con `GeminiNarrativeProvider` o, si no hay clave o
falla, un narrador de respaldo determinista: el respaldo es parte del contrato, no un apaño.
`runtime/storage.py` escribe cada run en `Stories/Bottom-Up/Escape-Room/` y los lotes (`--batch`) en
`experiments/<timestamp>/runs.csv` + `summary.csv`.

### Telegram: el bot no conoce el pipeline

`contract.py` define, del lado de la aplicación, el `Protocol` `StoryGeneratorAdapter` y sus tipos
(`GenerationProgress`, `RunSummary`, `GenerationFailure`). Los handlers, la entrega y la consola
hablan solo ese contrato; `generators.py` tiene los adaptadores que traducen un pipeline concreto.
Al añadir un generador se escribe un adaptador, no se tocan las conversaciones.

`queue.py` es una cola FIFO SQLite durable (`Stories/telegram_queue.sqlite3`) con migración de
esquema y cancelación, y `generation.py` la coordina con la entrega. Cualquier fallo que escape de
un adaptador sin ser `GenerationFailure` se considera defecto interno y se reporta como error
inesperado.

### Consola

`ConsoleApp` y los menús reciben `input_fn` y `output` inyectados (`types.py`), que es como los
tests recorren los menús sin terminal. Mantener esa inyección al añadir pantallas.

### core

`find_project_root` sube por el árbol buscando un directorio con `Stories/` y `packages/`, y se
puede forzar con `ASG_PROJECT_ROOT` (útil en contenedores; ver `Dockerfile`, que instala solo
core + evaluation + stagecraft + telegram). `files.py` da escritura atómica UTF-8, `audio.py` la
narración con edge-tts y `craft.py` las cifras de artesanía de la prosa (`craft_metrics`), puras y
deterministas, que consumen el `writing/audit.py` de Stagecraft y el recolector de `asg_evaluation`. Vive en
`core` porque `evaluation` no puede importar `top_down`.

## Convenciones de idioma (con verificación automática)

- **Docstrings de código de producción** (`apps/*/src`, `packages/*/src`): en **inglés**, breves y
  no tautológicas. Lo exige `tests/test_source_documentation.py`, que falla si falta el docstring o
  si no es ASCII. Exige docstring incluso en closures. Ojo con los guiones largos y las comillas
  tipográficas: no son ASCII y el gate los rechaza.
- **Texto visible para el usuario, artefactos e historias**: en **español**.
- Excepción deliberada: los mensajes de `ValueError` de `planning/graph.py`,
  `planning/promises.py`, `script/validation.py`, `stage/validation.py` y `stage/casting.py` van en
  inglés porque se reinyectan en el prompt del modelo (ver arriba).
- `Stories/`, PDFs y experimentos son datos de investigación: **nunca** se eliminan en tareas de
  limpieza aunque estén gitignored.

## TODO.md es la fuente de verdad del roadmap

Antes de proponer trabajo nuevo, revisarlo. Las tareas van en tres secciones según lo que hace
falta para moverlas — **Lo siguiente**, **Pendiente**, **Ideas** — y dentro de cada una el orden de
la lista es el orden sugerido. No hay etiquetas de prioridad. Cada tarea tiene el mismo esqueleto:
**Síntoma**, **Qué hacer** y **Hecho cuando**. Si la tarea de la sesión coincide con un ítem,
trabajar contra su "Hecho cuando" y borrar el ítem al cerrarlo: el historial vive en git, no en el
roadmap. La cabecera lleva una línea "Estado medido el <fecha> sobre `<commit>`" — actualizarla si
el estado medido cambia sustancialmente.

## Trampas conocidas

- `tests/test_source_documentation.py` tiene un marcador roto (`"configuraci?n"`, con un carácter
  corrupto) que nunca puede coincidir, y su glob `*/src/**` es relativo al directorio de trabajo:
  ejecutar pytest desde otro sitio hace que pase en silencio. Es un bug conocido con ficha en el
  `TODO.md`; no lo uses como referencia de qué detecta el filtro.
- `README.md` está **vacío** (0 bytes) **a propósito**: se redacta al cerrar el proyecto,
  cuando los contratos públicos ya no se muevan. No lo rellenes antes aunque parezca una
  mejora barata; cuando llegue el momento, guárdalo en UTF-8.
- `.gitignore` ignora `docs/*` salvo siete archivos en lista blanca. Si creas un doc nuevo en
  `docs/` y quieres que se versione, añádelo también a esa lista.
- `.cache/` contiene sqlite y cachés de pytest de experimentos previos (`pytest-top-down-*`,
  `pytest-profile-*`...). Son artefactos de ejecución: no razonar sobre el estado del proyecto a
  partir de sus nombres.
- `pipeline.py` sigue pasando de 1100 líneas y `skeletons.py` de 1400. La reorganización 7.0.0
  sacó de `pipeline.py` los prompts de reparación (`planning/repair.py`), el ensamblado
  (`writing/assembly.py`) y las reglas de aceptación (`writing/acceptance.py`); lo que queda está
  en «Pendiente» del `TODO.md`. No lo hagas de paso dentro de otro cambio.
- `materialize_act` pone en el acto el título del **plan**, que está en inglés, no el localizado.
  Los títulos localizados viven en `script_presentation.json`. El formato simulado los lee de ahí;
  el formato guion todavía imprime los del plan, y es una ficha abierta del `TODO.md`.

## Documentos de referencia

- [docs/simulacion_escenica.md](docs/simulacion_escenica.md) — la función simulada: por qué los
  actores no ven el guion, cómo funciona la memoria propia y su ablación, el bucle de escena, el
  punto de vista modular, los artefactos y qué se mide.
- [docs/estado_del_arte_simulacion.md](docs/estado_del_arte_simulacion.md) — las cuarenta
  referencias que sostienen ese diseño, con qué se tomó y qué se descartó de cada una.
- [docs/guion_teatral.md](docs/guion_teatral.md) — el formato de salida en guion teatral: los dos
  métodos (nativo y adaptado), el contrato de `script.json`, qué valida `script.py` y qué solo
  corrige, y cómo comparar los dos métodos.
- [docs/promesas_ppp.md](docs/promesas_ppp.md) — el contrato Promise-Progress-Payoff: qué dice la
  fuente, qué invariantes se formalizaron, cuáles se dejaron fuera y cómo se mide el efecto.
- [docs/pipeline_top_down.md](docs/pipeline_top_down.md) — recorrido de las doce etapas del
  pipeline Top-Down: qué hace cada agente, qué se le inyecta en el prompt y por qué, qué valida
  `graph.py` después y cómo se repara un plan rechazado. Grafo del flujo y un run de referencia.
- [docs/calibracion_perfiles.md](docs/calibracion_perfiles.md) — metodología y resultados de la
  calibración de los perfiles narrativos Top-Down.
- [docs/artesania_narrativa.md](docs/artesania_narrativa.md) — metodología y mediciones de la
  artesanía de la prosa: diálogo, longitud de frase y de párrafo por versión y por perfil.
- [docs/evaluation_metrics.md](docs/evaluation_metrics.md) — métricas automáticas de evaluación.
- [docs/prompts_top_down.md](docs/prompts_top_down.md) — catálogo canónico de prompts usado como
  benchmark.

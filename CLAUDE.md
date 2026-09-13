# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Guía para agentes que trabajen en este repositorio de tesis.

## Qué es este proyecto

Monorepo de investigación que genera y evalúa historias narrativas con dos enfoques opuestos:

- **Top-Down** (`packages/top_down`): pipeline de agentes LLM sobre Gemini que planifica primero
  (mundo, personajes, grafo de eventos) y escribe después.
- **Bottom-Up** (`packages/escape_room`): simulación multiagente determinista de una sala de
  escape; la historia se narra a partir del log de eventos ya ocurridos.

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
`compare-story-runs`, `run-escape-room`, `report-evaluations`, `asg-telegram`,
`asg-telegram-run`.

### Calidad — ejecutar siempre antes de dar por terminado un cambio

```powershell
ruff check .
ruff format --check .
python -m pytest -q -p no:cacheprovider
python -m pip check
```

No hay CI (`TODO.md`, "Meter la puerta de calidad en CI"), así que esto **no se valida solo**.
Lanzar `pytest` **desde la raíz**: `tests/test_source_documentation.py` resuelve su glob contra el
directorio de trabajo y pasa en vacío desde cualquier otro sitio.

### Iterar rápido

```powershell
python -m pytest packages/top_down/tests -q          # un subsistema
python -m pytest packages/top_down/tests/test_graph.py -q
python -m pytest packages/top_down/tests/test_generator_v5.py -q -k revision
```

`pyproject.toml` fija `testpaths = ["packages", "apps", "tests"]`, así que `pytest` sin argumentos
recoge todo el monorepo. `tests/test_sync_railway_stories.ps1` **no** lo recoge pytest: es un test
de PowerShell que hay que lanzar a mano.

Las pruebas de Top-Down y Bottom-Up usan proveedores falsos y nunca llaman a la API real, salvo
`packages/top_down/tests/test_gemini_live.py`, que se omite a menos que `RUN_GEMINI_LIVE=1`. **No
activarlo** sin que lo pida explícitamente quien manda la tarea: consume cuota real.

## Arquitectura

### Dependencias entre paquetes

```text
core  ←  evaluation  ←  top_down, escape_room  ←  console, telegram
```

`core` no depende de nada del repo; `top_down` y `escape_room` no se conocen entre sí. `telegram`
depende de `top_down` pero **no** de `escape_room`; `console` sí de los dos. Respetar esa dirección:
es lo que permite comparar los dos enfoques sin contaminarlos.

### Top-Down: el plan es un DAG validado, no texto

El flujo real es `StoryGenerator` (fachada pública en `generator.py`) → `StoryPipeline.execute`
(`pipeline.py`), que recorre las etapas de `CHECKPOINT_STAGES`: analysis, architecture, world,
characters, planning, plan_review, drafting, critique, revision, story, audio. Cada etapa llama a
un agente de `agents/` y persiste su artefacto antes de seguir.

Lo que hace este pipeline distinto de "pedirle una historia al modelo":

- **`graph.py` es el árbitro.** `materialize_plan` valida invariantes objetivos (ids únicos,
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
- **Los fallos se clasifican.** `errors.py` define `ASGError` con código, etapa, resumen seguro y
  recomendaciones. `NON_DEGRADABLE_ERRORS` (configuración y cuotas de Gemini) aborta el run; el
  resto se degrada a warning en `metadata.json` y la historia sigue.
- **`skeletons.py` + `skeleton_match.py`** rankean esqueletos de trama por mezcla léxica y
  semántica y producen un `NarrativeBlueprint` que se inyecta como inspiración en la cabecera
  compartida de prompts (`agents/base.py`). Es guía, no restricción.

### Top-Down: artefactos de un run

`ArtifactRepository` (`storage.py`) crea `Stories/Top-Down/<AAAAMMDD-HHMMSS>-<slug>/` y escribe
todo de forma atómica. El run contiene `metadata.json` (estado, etapas completadas, warnings,
error), `pipeline_manifest.json` (sha256 y tamaño de cada artefacto), `request.json`, `world.json`,
`characters.json`, `story_plan.json`, `chapters/`, `revisions/`, `draft.md`, `story.md`,
`story.mp3`, `llm_calls.jsonl` y `llm_usage.json`.

`version.py` fija `PIPELINE_VERSION` y `SUPPORTED_PIPELINE_VERSIONS`; `StoryRun` se niega a abrir
un run incompleto o de una versión no soportada. Si cambias el conjunto de artefactos o su
significado, sube la versión en vez de romper los runs ya generados: son datos de la tesis.

### Top-Down: proveedor y cuota

`provider.py` expone el `Protocol` `LanguageModelProvider` (`generate_structured` con esquema
Pydantic y `generate_text`) e implementa `GeminiProvider`. Detalles que importan al tocarlo:

- La temperatura sale de perfiles nombrados (`extraction`, `review`, `planning`, `prose`,
  `rewrite`), no de constantes sueltas en los agentes.
- `_gemini_response_schema` borra `additionalProperties` del esquema Pydantic porque algunos
  modelos Gemini lo rechazan; Pydantic sigue siendo la autoridad local con `extra="forbid"`.
- `_safe_provider_error` clasifica los fallos sin filtrar credenciales ni el contenido del prompt.
- `quota.py` mantiene limitadores de ventana deslizante **compartidos a nivel de proceso**
  (`_LIMITERS`), así que dos generaciones concurrentes respetan un único presupuesto de RPM/TPM.

Los tests inyectan un `FakeProvider` (ver `packages/top_down/tests/test_generator_v5.py`), que es
la forma canónica de probar el pipeline: se le pasa una secuencia de respuestas estructuradas y
puede forzar fallos en llamadas concretas.

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
`storage.py` escribe cada run en `Stories/Bottom-Up/Escape-Room/` y los lotes (`--batch`) en
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
core + evaluation + top_down + telegram). `files.py` da escritura atómica UTF-8 y `audio.py` la
narración con edge-tts.

## Convenciones de idioma (con verificación automática)

- **Docstrings de código de producción** (`apps/*/src`, `packages/*/src`): en **inglés**, breves y
  no tautológicas. Lo exige `tests/test_source_documentation.py`, que falla si falta el docstring o
  si no es ASCII. Exige docstring incluso en closures.
- **Texto visible para el usuario, artefactos e historias**: en **español**.
- Excepción deliberada: los mensajes de `ValueError` de `graph.py` van en inglés porque se envían
  al modelo (ver arriba).
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
- `README.md` está **vacío** (0 bytes). Si lo rellenas, guarda en UTF-8.
- `.gitignore` ignora `docs/*` salvo tres archivos en lista blanca. Si creas un doc nuevo en
  `docs/` y quieres que se versione, añádelo también a esa lista.
- `.cache/` contiene sqlite y cachés de pytest de experimentos previos (`pytest-top-down-*`,
  `pytest-profile-*`...). Son artefactos de ejecución: no razonar sobre el estado del proyecto a
  partir de sus nombres.
- `pipeline.py` pasa de 1100 líneas y `skeletons.py` de 1400. Dividirlos está en «Pendiente» del
  `TODO.md`; no lo hagas de paso dentro de otro cambio.

## Documentos de referencia

- [docs/calibracion_perfiles.md](docs/calibracion_perfiles.md) — metodología y resultados de la
  calibración de los perfiles narrativos Top-Down.
- [docs/evaluation_metrics.md](docs/evaluation_metrics.md) — métricas automáticas de evaluación.
- [docs/prompts_top_down.md](docs/prompts_top_down.md) — catálogo canónico de prompts usado como
  benchmark.

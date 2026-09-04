# CLAUDE.md

Guía para agentes (Claude Code y similares) que trabajen en este repositorio.

## Qué es este proyecto

Monorepo de investigación (tesis) para generar y evaluar historias narrativas con dos enfoques:

- **Top-Down** (`packages/top_down`): pipeline de agentes en varias etapas (planificador, mundo,
  personajes, escritor, crítico...) sobre Gemini, con "perfiles narrativos" (Esencial, Desarrollada,
  Expansiva) que controlan la extensión y densidad de la prosa.
- **Bottom-Up** (`packages/escape_room`): simulación multiagente de una sala de escape cuyos eventos
  se narran después.

`packages/evaluation` compara runs y recoge evaluaciones humanas. `packages/core` tiene utilidades
compartidas (rutas, escritura atómica de archivos, audio/TTS). `apps/console` es la interfaz
interactiva de terminal; `apps/telegram` expone el generador como bot.

## Estructura

```text
apps/console/        interfaz interactiva de terminal (src/, tests/)
apps/telegram/        bot, cola y entrega de historias (src/, tests/)
packages/core/        rutas, nombres seguros, escritura atómica, audio
packages/top_down/    pipeline de agentes Top-Down (perfiles, agents/, pipeline.py)
packages/escape_room/ simulador Bottom-Up (engine, world, narrative, maps/)
packages/evaluation/  comparación de runs y evaluaciones humanas
tests/                pruebas transversales + tests/test_sync_railway_stories.ps1
docs/                 documentación técnica (mayoría gitignored, ver más abajo)
Stories/              historias y datos generados — NUNCA se borran en limpiezas
TODO.md               hoja de ruta viva — leer antes de asumir que algo es nuevo
commands.md           referencia completa de comandos CLI
```

## Entorno y comandos

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt   # instala todo en modo editable + pytest/ruff
```

Copiar `.env.example` a `.env`. `GEMINI_API_KEY` es opcional: sin ella, los tests usan un
proveedor falso y `run-escape-room --no-llm` genera la historia de fallback.

Comandos expuestos: `asg-console`, `generate-story`, `compare-story-runs`, `run-escape-room`,
`asg-telegram`, `asg-telegram-run`. Ejemplos detallados en [commands.md](commands.md).

### Calidad — ejecutar siempre antes de dar por terminado un cambio

```powershell
ruff check .
ruff format --check .
python -m pytest -q -p no:cacheprovider
python -m pip check
```

No hay CI configurada todavía (`TODO.md`, sección "Calidad e infraestructura"), así que esto
**no se valida solo**: es responsabilidad de quien edita ejecutarlo.

Para iterar rápido en un solo subsistema:

```powershell
python -m pytest packages/top_down/tests -q
python -m pytest packages/escape_room/tests -q
python -m pytest apps/console/tests -q
```

Las pruebas de Top-Down/Bottom-Up usan un proveedor Gemini falso por defecto — nunca llaman a la
API real salvo que se active `RUN_GEMINI_LIVE`, algo que **no se debe hacer** sin que lo pida
explícitamente quien esté al mando de la tarea.

## Convenciones de idioma (con verificación automática)

- **Docstrings de código de producción** (`apps/*/src`, `packages/*/src`): en **inglés**, breves,
  no tautológicas ("Save json." no vale). Lo exige
  `tests/test_source_documentation.py`, que falla si falta el docstring o si detecta texto en
  español o no-ASCII.
- **Texto visible para el usuario, artefactos e historias**: en **español**.
- `Stories/`, PDFs y experimentos son datos de investigación: no se eliminan en tareas de limpieza
  aunque estén gitignored.

## TODO.md es la fuente de verdad del roadmap

Antes de proponer trabajo nuevo, revisar `TODO.md`: las tareas están agrupadas por subsistema,
priorizadas `P0`/`P1`/`P2`, y cada una lleva una condición de cierre explícita ("**Finalizada
cuando:**") y evidencia en código ("**Evidencia:**"). Si una tarea de esta sesión coincide con un
ítem del TODO, trabajar contra esa definición de "hecho" en vez de inventar una nueva, y marcar el
checkbox / actualizar la evidencia al terminarla. La cabecera del archivo lleva una línea de
"Estado medido el <fecha> sobre `<commit>`" — actualizarla si el estado medido cambia
sustancialmente.

## Trampas conocidas (documentadas en el propio TODO.md — no las "arregles" por sorpresa)

- `ruff format --check .` puede fallar sobre archivos existentes; no asumir que el árbol está
  formateado salvo que se acabe de comprobar.
- `tests/test_source_documentation.py` tiene un marcador roto (`"configuraci?n"`, con un carácter
  corrupto) que nunca puede coincidir — es un bug conocido, no lo uses como referencia de qué
  detecta el filtro de español.
- `README.md` tiene corrupción de codificación (acentos como `?`) — es un problema conocido
  (`TODO.md`, "Documentación y despliegue"); si lo editas, guarda en UTF-8 y no propagues el mismo
  mojibake en texto nuevo.
- `pyproject.toml` declara `line-length = 100` pero `E501` no está en `[tool.ruff.lint].select`,
  así que Ruff **no** hace cumplir ese límite todavía; no confíes en `ruff check` para detectarlo.
- `.gitignore` ignora `docs/*` salvo una lista blanca (`docs/calibracion_perfiles.md`,
  `docs/evaluation_metrics.md`, `docs/prompts_top_down.md`); el propio TODO.md señala que esa
  lista nombra además tres archivos que hoy no existen. Si creas un doc nuevo en `docs/` y quieres
  que se versione, añádelo también a la lista blanca del `.gitignore`.

## Documentos de referencia

- [docs/calibracion_perfiles.md](docs/calibracion_perfiles.md) — metodología y resultados de la
  calibración de los perfiles narrativos Top-Down.
- [docs/evaluation_metrics.md](docs/evaluation_metrics.md) — métricas automáticas de evaluación.
- [docs/prompts_top_down.md](docs/prompts_top_down.md) — catálogo canónico de prompts usado como
  benchmark.
- `.cache/` contiene bases sqlite y directorios de caché de pytest de experimentos previos
  (`pytest-top-down-*`, `pytest-profile-*`, ...) — son artefactos de ejecución, no fuente de
  verdad; no razonar sobre el estado del proyecto a partir de sus nombres.

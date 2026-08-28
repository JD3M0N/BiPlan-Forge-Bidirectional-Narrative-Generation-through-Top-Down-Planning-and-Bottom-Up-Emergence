# Automatic Story Generation

Monorepo de investigaci?n para generar y evaluar historias con enfoques
Top-Down y Bottom-Up. La reorganizaci?n mantiene los comandos p?blicos y los
formatos de artefactos existentes, pero separa aplicaciones, paquetes y pruebas.

## Estructura

```text
apps/
  console/       # interfaz interactiva de terminal
  telegram/      # bot, cola y entrega de historias
packages/
  core/          # rutas, nombres seguros y escritura at?mica
  evaluation/    # evaluaciones humanas y comparaci?n de runs
  escape_room/   # simulador narrativo Bottom-Up
  top_down/      # pipeline por etapas Top-Down
tests/           # comprobaciones transversales y script de Railway
docs/            # documentaci?n t?cnica
Stories/         # historias y datos generados (se conservan)
```

## Instalaci?n

Requiere Python 3.11 o posterior. Desde la ra?z:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Copia `.env.example` como `.env` y configura las claves necesarias. La prueba
real de Gemini es opcional y nunca forma parte de la suite predeterminada.

## Comandos principales

```powershell
generate-story --help
compare-story-runs --help
run-escape-room --help
asg-console
asg-telegram
asg-telegram-run
```

`asg-telegram` abre una consola separada en Windows; `asg-telegram-run` ejecuta
el bot en la consola actual. Consulte [commands.md](commands.md) para ejemplos.

## Calidad y pruebas

```powershell
ruff check .
ruff format --check .
python -m pytest -q -p no:cacheprovider
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test_sync_railway_stories.ps1
python -m pip check
```

Los docstrings del c?digo de producci?n son breves y est?n en ingl?s. Los
mensajes visibles, artefactos e historias siguen en espa?ol cuando as? se
solicita. Los contenidos de `Stories/`, experimentos y PDFs son datos de
investigaci?n y no se eliminan durante tareas de limpieza.

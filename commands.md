# Comandos

Desde la raíz, con el entorno activo:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Copia `.env.example` a `.env` (`GEMINI_API_KEY` solo hace falta para generar de verdad).
Añade `--help` a cualquiera para ver todas sus opciones.

## Generar (Stagecraft)

- `generate-story [prompt]`: genera una historia (pide el prompt si no se da). Opciones útiles:
  `--format {narrative,script,simulated}`, `--profile {essential,developed,expansive}`,
  `--voice`, `--narrator`, `--actor-memory {own,shared}`, `--inventory`, `--no-audio`,
  `--brief`, `--options`, `--guidance-strategy compositional_v2`, `--no-narrative-guidance`.
  Se niega a arrancar (código 3) si la cuota de hoy no alcanza para una historia media de ese
  formato; `--force` la lanza igual.
- `generate-baseline "PREMISA" --output CARPETA_NUEVA`: línea base de un solo prompt. Gasta cuota.
- `recompute-simulation-metrics <run>`: recalcula las métricas de un run simulado desde disco.
  No gasta cuota ni toca el original.
- `recover-story-runs`: lista, cierra o descarta runs que quedaron atascados en `running`.
- `llm-budget`: panel de cuotas por proveedor y modelo, y cuántas historias caben aún. No gasta
  cuota.

## Interfaces

- `asg-telegram` (o doble clic en `iniciar-bot.bat`): el bot del estudio. Crea historias
  (Top-Down o híbrido, libre o guiada) y, con la votación abierta, las compara a ciegas. Ver
  [apps/telegram/README.md](apps/telegram/README.md).
- `asg-studio`: StageCraft, la interfaz web local (`http://127.0.0.1:8765/`), para configurar,
  seguir y comparar runs. `--demo` la prueba sin gastar cuota.

## Evaluación (el método del tutor)

Paso a paso en [packages/evaluation/README.md](packages/evaluation/README.md).

- `evaluation-study --db RUTA`: `status`, `add RUN…`, `exclude ID`, `include ID`,
  `author ID_TELEGRAM`, `open`, `close`, `export SALIDA.json`.
- `extract-story-features --study DB` o `--root RUTA`: rasgos con cita; `--dry-run`,
  `--selection all`, `--force`. Gasta cuota.
- `audit-feature-extraction ARCHIVO --output revision.json`: evidencias; `--second` para
  test-retest.
- `report-features RUTA --json tabla.json --csv tabla.csv --horizontal horizontal.json`;
  `--study DB` reutiliza las extracciones del estudio.
- `report-preferences DB --output informe.json`: Bradley–Terry, acuerdo e intervalos por lector.
- `fit-preference-judge DB --output juez.json`: tres jueces y validación fuera de muestra.
- `rank-stories juez.json RUTA --output ranking.json`: rankings y fichas de las diez primeras.

## Calidad

- `.\run-tests.ps1`: la suite entera (único comando de tests).
- `.\quality.ps1`: ruff, formato, tests y `pip check`; `-Fast` solo tests.

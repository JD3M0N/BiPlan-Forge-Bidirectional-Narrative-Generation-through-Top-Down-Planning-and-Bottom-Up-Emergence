# Comandos

Desde la raíz, con el entorno activo:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Copia `.env.example` a `.env` (`GEMINI_API_KEY` solo hace falta para generar de verdad).
Añade `--help` a cualquiera para ver todas sus opciones.

## Generar y analizar (Stagecraft)

- `generate-story [prompt]`: genera una historia (pide el prompt si no se da). Opciones útiles:
  `--format {narrative,script,simulated}`, `--profile {essential,developed,expansive}`,
  `--voice`, `--narrator`, `--actor-memory {own,shared}`, `--inventory`, `--no-audio`,
  `--brief`, `--options`.
- `compare-story-runs <run>...`: compara 2 o más runs y saca un informe HTML.
- `audit-stage-run <run>`: un juez LLM revisa un run simulado (filtraciones de conocimiento y
  fidelidad de la narración). Gasta cuota.
- `recompute-simulation-metrics <run>`: recalcula las métricas de un run simulado desde disco.
  No gasta cuota ni toca el original.
- `recover-story-runs`: lista, cierra o descarta runs que quedaron atascados en `running`.
- `llm-budget`: panel de cuotas. Por proveedor, lo gastado contra su tope (Gemini suma sus dos
  modelos: x/1000) y cuándo reinicia; por modelo, peticiones, tokens, RPM y si está agotado; y
  cuántas historias caben aún, con la media de los últimos runs. Lee el libro de la cadena y los
  `llm_calls.jsonl` de los runs. No gasta cuota.

## Informes (evaluation)

- `report-evaluations`: resume las evaluaciones humanas (media y desviación por métrica).
- `report-story-craft`: mide la artesanía de la prosa (diálogo, frases, párrafos) desde `story.md`.
- `report-simulations`: resume las métricas de las funciones simuladas por voz, memoria y versión.

## Interfaces

- `asg-console`: consola interactiva para generar historias y evaluar las guardadas.
- `asg-telegram`: abre la consola de Telegram en una ventana aparte y monta el servidor del bot.
- `asg-telegram-run`: lo mismo, pero en la consola actual.
- `asg-studio`: abre StageCraft, la interfaz web local (`http://127.0.0.1:8765/`), para configurar,
  seguir y comparar runs. `--demo` la prueba sin gastar cuota.

## Calidad

- `.\run-tests.ps1`: la suite entera (único comando de tests).
- `.\quality.ps1`: ruff, formato, tests y `pip check`; `-Fast` solo tests.

## Estudio final de evaluación

La guía completa y el orden de operaciones están en
[ESTUDIO_FINAL.md](packages/evaluation/ESTUDIO_FINAL.md).

- `evaluation-study --db RUTA`: create, participant, add, collect, freeze, start, close, status, export.
- `evaluation-demo CARPETA_NUEVA`: demostración íntegra ficticia, sin red.
- `extract-story-features --study DB` o `--root RUTA`: núcleo de rasgos; `--dry-run`, `--selection all`, `--force`.
- `report-features RUTA --json tabla.json --csv tabla.csv --horizontal horizontal.json`; `--study DB` reutiliza las extracciones del estudio.
- `audit-feature-extraction ARCHIVO --output revision.json`: evidencias; `--second` para test-retest.
- `report-preferences DB --output informe.json`: Bradley–Terry, acuerdo e intervalos por lector.
- `fit-preference-judge DB --output juez.json`: tres jueces y validación fuera de muestra.
- `rank-stories juez.json RUTA --output ranking.json`: rankings y ficha de diez historias; `--study DB` reutiliza las extracciones del estudio.
- `generate-baseline "PREMISA" --output CARPETA_NUEVA`: generación directa, consume cuota.

Telegram: el bot exige `ASG_EVALUATION_STUDY` y `TELEGRAM_ACCESS_KEY`. Guía a cada participante desde la clave hasta su historia base y la votación (`/start`, `/aportar`, `/evaluar`, `/pausa`).

## Guía narrativa experimental (7.8)

```powershell
generate-story "Una historia" --guidance-strategy compositional_v2 --no-audio
generate-story "Una historia" --no-narrative-guidance --no-audio
plan-guidance-experiment --help
```

La estrategia predeterminada sigue siendo `hybrid_v1`. El preparador de experimentos no genera
historias ni consume cuota. Protocolo y solicitudes: `packages/stagecraft/experiments/guidance/`.

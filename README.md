# Automatic Story Generation

Sistema modular de generación automática de historias (ASG). La primera
implementación utiliza planificación **Top-Down** y agentes especializados que
se comunican mediante artefactos validados.

## Instalación

Requiere Python 3.11 o posterior.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e "Models/Top-Down[dev]"
Copy-Item .env.example .env
```

Escribe tu clave en `.env`:

```dotenv
GEMINI_API_KEY=tu_clave
GEMINI_MODEL=gemini-2.5-flash
```

`.env` está ignorado por Git. Nunca añadas una clave real a `.env.example`.

## Uso

Desde la raíz del repositorio:

```powershell
generate-story
```

La aplicación pedirá un único prompt. Un prompt útil especifica género,
protagonista, conflicto, ambientación, tono y extensión, por ejemplo:

> Escribe un relato de ciencia ficción de unas 1800 palabras. Una cartógrafa
> descubre que las estrellas están cambiando de posición para formar un
> mensaje. Tono melancólico, ambientado en una estación orbital decadente y
> con un final esperanzador.

Cuando falten idioma o extensión se usarán español y unas 1500 palabras. Cada
ejecución crea una carpeta independiente en `Stories/Top-Down` con la historia,
el borrador y todos los artefactos de planificación y revisión.

## Desarrollo

```powershell
python -m pytest Models/Top-Down/tests
```

El proveedor de lenguaje está definido mediante un protocolo. Los tests usan
un proveedor simulado y no consumen la API de Gemini.

## Escape Room Bottom-Up

La implementación Bottom-Up simula una habitación cooperativa con dos o tres
personajes. Los agentes exploran mediante visión local, mantienen creencias
separadas del estado real, comparten descubrimientos y resuelven una cadena de
acertijos que termina con una acción sincronizada sobre una placa y una
palanca.

Instala ambos paquetes y ejecuta una simulación desde la raíz:

```powershell
python -m pip install -r requirements.txt
run-escape-room --agents 2 --tick-limit 300
```

El mapa predeterminado está en
`Models/Bottom-Up/escape-room/maps/escape_room.json`. Puede seleccionarse otro:

```powershell
run-escape-room --map ruta/al/mapa.json --agents 3
```

Si se omite `--seed`, cada ejecución genera y registra una semilla aleatoria.
Indicar `--seed N` reproduce exactamente una simulación anterior.

Si `GEMINI_API_KEY` está configurada, el comando usa `GEMINI_MODEL` para
redactar el relato. Ante un fallo remoto —o con `--no-llm`— conserva la
simulación y genera un relato determinista de respaldo.

Cada ejecución crea
`Stories/Bottom-Up/Escape-Room/<fecha>-<habitación>/` con la configuración, el
mundo inicial, personajes, `ticks.jsonl`, eventos causales, resultado,
métricas, relato y metadatos.

Para ejecutar las semillas 0–29 con dos y tres agentes:

```powershell
run-escape-room --batch --tick-limit 300
```

El experimento guarda `runs.csv` y `summary.csv` bajo
`Stories/Bottom-Up/Escape-Room/experiments/`.

### Mapas e integración

Los mapas JSON declaran dimensiones, paredes, agentes, objetos, elementos
interactivos y un DAG de acertijos. El cargador rechaza coordenadas inválidas,
identificadores duplicados, referencias desconocidas, ciclos y habitaciones
sin los elementos obligatorios.

El motor publica `load_room`, `EscapeRoomModel`, `SimulationRunner`,
`SimulationResult`, `EventLog` y `run_simulation`. El protocolo
`NarrativeProvider` es compatible estructuralmente con el proveedor del
Top-Down. `asg_escape_room.integration.apply_top_down_artifacts` permite
superponer ambientación y personajes recibidos como artefactos JSON sin que el
motor importe el pipeline Top-Down.

```powershell
python -m pytest Models/Bottom-Up/escape-room/tests
```

# Telegram y StageCraft

Referencia de contratos vigentes. Lee solo las secciones del subsistema que vayas a cambiar.
Las reglas generales están en [AGENTS.md](../../AGENTS.md).

## Telegram: el bot del estudio

- **Solo crea historias y las compara.** Sin clave, perfiles ni opciones por usuario: todo sale
  del `.env`. Corre en la PC del investigador (`asg-telegram`), que abre y cierra la votación
  con `asg-study`.
- Crear: un solo menú con cuatro opciones (`c:o:<formato>:<modo>`): libre o guiada, Top-Down
  (`narrative`) o Híbrido (`simulated`). `wizard.py` es el asistente como máquina de estados
  pura (`start`, `answer`, `press`) y devuelve un `StoryOutline`.
- **El bot recomienda siempre el siguiente paso** (`guide.next_step`, 6.0):
  - primero Top-Down;
  - después «la misma idea» con el otro modelo, que repite la petición (`source_job` en la
    cola);
  - y, con una de cada modelo, compararlas.
- **`/evaluar` compara las dos historias propias** (`review.py`, `pairs.py`), con el método del
  tutor aplicado a su propio par.
  - A y B a ciegas, en orden aleatorio.
  - Las tres preguntas de `asg_evaluation.catalog`, una a una, con «¿por qué?» opcional.
  - Nada de escalas numéricas.
  - Se guarda por modelo en `Evaluations/estudio/pares_propios.sqlite3` (`ASG_OWN_PAIRS`), y
    `asg-telegram --export` lo vuelca.
- `jobs.py`: `JobQueue` es la cola FIFO SQLite (`Stories/telegram_jobs.sqlite3`), con una
  solicitud activa por persona; un run interrumpido por un reinicio vuelve a la cola una vez.
  `StoryWorker` genera de una en una, edita un solo mensaje de progreso, entrega (`delivery.py`:
  archivo, audio y texto) e inscribe la historia en el estudio si está en recogida.
- **`generator.py` es el único módulo que importa `asg_stagecraft`.** Pide siempre prosa con
  audio y traduce los errores a `GenerationFailure` (con `quota` si se acabó la cuota).
- **La cancelación pasa `should_cancel` a `generate()`,** nunca lanza desde el callback de
  progreso.
- `voting.py` es `/estudio`, el estudio a ciegas entre personas, oculto hasta que haya
  historias suficientes. Envía las historias sin leer (texto y audio) con «Ya la leí» y «Ya la
  conocía», y después la pregunta con A, B y «No puedo decidir». Un candado por lector evita
  carreras de doble pulsación; `review.py` hace lo mismo.
- `tests/test_bot.py` recorre con un Telegram y un generador falsos (`telegram_fakes.py`):
  - las cuatro opciones y «la misma idea»;
  - la comparación propia;
  - la cola;
  - el estudio a ciegas;
  - el adaptador.

## StageCraft: la interfaz gráfica

- `asg-studio` sirve en `127.0.0.1:8765` una app FastAPI y una página en HTML, CSS y módulos ES
  sin paso de build. Detalle en [apps/studio/README.md](../../apps/studio/README.md).
- **Las opciones se pintan desde `catalog.py`.** Las etiquetas vienen del generador
  (`formats.py`, perfiles, voces de `asg_core`); las opciones **pendientes** (las que el
  roadmap aún no construye) viven solo ahí, con su ficha. Un test cruza cada `kind` del
  catálogo con su renderizador en `static/js/ui.js`.
- **La cola tiene un solo hilo** (`jobs.py`) y un generador nuevo por trabajo. Se cancela con
  `should_cancel`.
- **Nunca escribe ni borra en `Stories/`.** La biblioteca y la comparación leen con los lectores
  tolerantes de evaluation (`pairing.py`).
- **Lectura ciega** (`blind.py`, `routes/blind.py`): pares X/Y sin procedencia y un voto por
  par, en `Evaluations/estudio/lecturas/<sesión>.votos.json`; es lo único que el studio escribe,
  y nunca en `Stories/`. Las respuestas no llevan `run_id`, título ni ejes.
- **Seguridad local:** toda escritura exige la cabecera `X-StageCraft: 1`, el `Host` debe ser
  local y la CSP solo permite los archivos propios. El texto del modelo se pinta con
  `textContent`.
- Los tests usan un generador falso y una carpeta temporal (`tests/studio_fakes.py`); nunca
  Gemini.

## Precauciones

- **El `callback_data` de un botón de Telegram tiene un máximo de 64 bytes.** El asistente
  guiado (`wizard.py`) codifica índices en vez de valores, y la votación usa ids cortos de
  pregunta (`q` y 16 hex).
- **Windows puede servir `.js` como `text/plain`**, y el navegador no ejecuta así un módulo ES:
  la página saldría en blanco. `asg_studio/app.py` registra el tipo al importarse.

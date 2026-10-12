# ASG Telegram

Bot del estudio humano de la tesis. Hace dos cosas:

1. **Crear historias.** Cada persona elige cómo se escribe y cómo la cuenta:
   - **Top-Down** (`narrative`): se planifica la trama y después se escribe en prosa.
   - **Híbrido** (`simulated`): los personajes representan la obra y se narra lo que hicieron.
   - **Libre**: escribe una idea en un mensaje.
   - **Guiada**: título, género, ambientación, trama, personajes y notas, paso a paso.

   La historia llega como `historia.md`, con su narración en `historia.mp3` y el texto en el
   chat. Mientras el estudio está en recogida, queda inscrita como aportación de esa persona.
2. **Evaluar.** Cuando el investigador abre la votación, `/evaluar` presenta pares de historias a
   ciegas (Historia A e Historia B, con texto y audio). Tras leer las dos, la persona responde una
   pregunta: creatividad, personajes o trama, en ciclo. Se puede responder A, B o «No puedo
   decidir». Nunca le toca su propia historia, y «Ya la conocía» la cambia por otra.

No hay clave, perfiles ni opciones: lo demás se fija en el `.env`.

## Poner en marcha (en tu PC)

1. Crea el bot con `@BotFather` (`/newbot`) y copia el token.
2. En el `.env` de la raíz:

   ```dotenv
   TELEGRAM_BOT_TOKEN=token_de_BotFather
   GEMINI_API_KEY=tu_clave
   # Opcional; vacío usa Evaluations/estudio/study.sqlite3
   ASG_EVALUATION_STUDY=
   # Opcional: voz fija para el audio (si no, la elige el idioma de la historia)
   TTS_FALLBACK_VOICE=
   ```

   Las variables `ASG_*` (perfil, visión, memoria, turnos por beat…) fijan las opciones de todas
   las historias.
3. Una vez: `.\setup.ps1`. Después, doble clic en `iniciar-bot.bat` (o `asg-telegram`).

Se genera **una historia a la vez**, por orden de llegada; cada persona tiene como mucho una
solicitud en marcha. La cola vive en `Stories/telegram_jobs.sqlite3`: si el bot se reinicia, una
historia interrumpida vuelve a la cola una vez. Si se acaba la cuota del modelo, el bot lo dice y
la persona la pide más tarde.

## Comandos del bot

- `/start`: qué hace el bot.
- `/crear`: nueva historia.
- `/evaluar`: empezar o seguir comparando.
- `/cancelar`: cancela la solicitud o la conversación en curso.

## Operar el estudio

El estudio es un archivo SQLite (`ASG_EVALUATION_STUDY`). Los comandos, desde la raíz:

```powershell
$db = "Evaluations/estudio/study.sqlite3"
evaluation-study --db $db status                 # fase, historias, votos
generate-baseline "PREMISA" --output Stories/Baseline/01   # línea base de un solo prompt
evaluation-study --db $db add Stories/Baseline/01          # inscribirla
evaluation-study --db $db exclude ID             # sacar una historia antes de abrir
evaluation-study --db $db author TU_ID_DE_TELEGRAM   # para el acuerdo sin el autor
evaluation-study --db $db open                   # congela el conjunto y abre la votación
evaluation-study --db $db close                  # cierra la votación
```

Con la votación cerrada, el análisis sigue en
[packages/evaluation](../../packages/evaluation/README.md): `report-preferences`,
`extract-story-features`, `fit-preference-judge` y `rank-stories`.

## Código

| Módulo | Qué hace |
|---|---|
| `app.py` | arma la aplicación y arranca el trabajador |
| `config.py` | lee el token y la ruta del estudio |
| `handlers.py` | `/start`, `/crear` (los cuatro caminos) y `/cancelar` |
| `wizard.py` | el asistente guiado, como máquina de estados pura |
| `jobs.py` | la cola SQLite y el trabajador que genera, entrega e inscribe |
| `generator.py` | el adaptador de Stagecraft, único módulo que lo importa |
| `delivery.py` | envío del archivo, el audio y el texto, con reintentos de red |
| `voting.py` | el flujo de `/evaluar` |

Los tests (`tests/test_bot.py`) recorren los cuatro caminos, la cola y la votación con un
Telegram y un generador falsos.

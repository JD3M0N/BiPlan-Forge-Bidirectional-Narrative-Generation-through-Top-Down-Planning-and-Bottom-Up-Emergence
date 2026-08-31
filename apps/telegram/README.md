# ASG Telegram

Bot de Telegram para generar historias con los modelos ASG y registrar la
evaluación humana inmediatamente después.

## Configuración

1. Habla con `@BotFather` en Telegram, crea un bot con `/newbot` y copia el
   token.
2. En el `.env` de la raíz configura:

```dotenv
TELEGRAM_BOT_TOKEN=token_entregado_por_BotFather
STORY_GENERATOR=top-down
GEMINI_API_KEY=tu_clave
GEMINI_MODEL=gemini-2.5-flash
TTS_FALLBACK_VOICE=
```

3. Desde la raíz instala las dependencias y ejecuta:

```powershell
python -m pip install -r requirements-dev.txt
asg-telegram
```

En Windows, `asg-telegram` abre el bot en una consola independiente y devuelve
inmediatamente el control a la consola original. La nueva ventana debe
permanecer abierta para que el bot responda. Allí se registran los comandos,
selecciones, pasos de generación, entregas y evaluaciones de cada usuario.

Para ejecutarlo en la consola actual, por ejemplo durante depuración, usa:

```powershell
asg-telegram-run
```

El proceso utiliza polling y no requiere dominio ni webhook.

### Entrega de historias

Las historias se generan en paralelo, pero se entregan de una en una para no
saturar la conexión con Telegram. La entrega usa el orden `story.md`,
`story.mp3`, fragmentos formateados y evaluación. Tanto el documento como el
audio se reintentan ante fallos temporales. Si la síntesis o el envío del MP3
falla, el bot informa al usuario y continúa con el texto y la evaluación.

## Cambiar el generador

`STORY_GENERATOR` selecciona el enfoque ASG y `GEMINI_MODEL` selecciona el
modelo de lenguaje usado por ese enfoque. Actualmente está registrado
`top-down`.

Para probar otro enfoque, implementa el protocolo `StoryGenerator` en
`asg_telegram.generators` y regístralo:

```python
DEFAULT_REGISTRY.register("mi-modelo", MiGenerador)
```

Después establece `STORY_GENERATOR=mi-modelo`. Los handlers de Telegram no
necesitan cambios.
Las solicitudes de historias se guardan en `Stories/telegram_queue.sqlite3` y
se procesan de una en una. El mensaje de progreso muestra la posición FIFO y
una estimación basada en las últimas diez historias. `/cancel` retira una
solicitud que aún esté esperando. Tras reiniciar el bot, los trabajos
interrumpidos quedan marcados como `recovery_pending` para auditoría y el resto
de la cola continúa. No se intenta reanudar una ejecución parcial.

Si la historia pudo escribirse pero la auditoría o reescritura final falló, el
bot entrega la mejor versión disponible y muestra la advertencia guardada en
`metadata.json`. Los fallos de planificación no se degradan ni se entregan.

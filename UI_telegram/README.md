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
```

3. Desde la raíz instala las dependencias y ejecuta:

```powershell
python -m pip install -r requirements.txt
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
saturar la conexión con Telegram. El archivo `story.md` se envía primero y se
reintenta automáticamente ante fallos temporales. Los mensajes formateados se
envían después; si uno falla, el usuario conserva el archivo completo y puede
continuar con la evaluación sin regenerar la historia.

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
interrumpidos vuelven al frente de la cola. Una historia ya terminada se
reutiliza; una ejecución parcial se reinicia desde su `request.json` en un
directorio nuevo y conserva el intento anterior para auditoría.

Si la historia pudo escribirse pero la auditoría o reescritura final falló, el
bot entrega la mejor versión disponible y muestra la advertencia guardada en
`metadata.json`. Los fallos de planificación no se degradan ni se entregan.

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

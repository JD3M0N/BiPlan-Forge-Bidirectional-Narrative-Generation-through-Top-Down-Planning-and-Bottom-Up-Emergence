# Generador de historias

Tesis: un generador de historias (**Stagecraft**) con dos enfoques, **Top-Down** (se planifica y
luego se escribe) e **Híbrido** (los personajes representan la obra y se narra lo que hicieron),
y un bot de Telegram para crear historias y compararlas a ciegas.

## Instalar

```powershell
.\setup.ps1
```

En el archivo `.env` pon tu `GEMINI_API_KEY` y el `TELEGRAM_BOT_TOKEN` de tu bot.

## Usar

```powershell
asg-telegram   # inicializa el bot de telegram
asg-help       # muestra todos los comandos
```

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
asg help       # muestra todos los comandos
```

## Resultados de la tesis

Las tablas y figuras de la tesis salen de los artefactos de `Evaluations/`, sin cuota:

```powershell
asg-results    # escribe redaccion/tablas/ y redaccion/figuras/ con su manifiesto.json
asg-latex      # compila la tesis en %TEMP% y deja redaccion/tesis/Thesis.pdf (requiere MiKTeX)
```

- **Entradas** (ignoradas por Git, investigación local): `Evaluations/estudio-piloto-722/`
  (`juez.json`, `preferencias.json`, `protocolo.json`), `Evaluations/horizontal/` (matriz y piloto
  de la obra 03) y `Evaluations/ranking/ranking-<fecha>.json`, que escribe `asg-rank`.
- **Salidas** (versionadas): `redaccion/tablas/*.tex` y `.csv`, `redaccion/figuras/juez.tex` y
  `redaccion/tablas/manifiesto.json` con la fecha, el SHA-256 de cada entrada y salida y las
  tablas que siguen a mano (`tab:lecturas`, `tab:extractor`, `tab:coste`).
- **Compatibilidad:** los artefactos de runs anteriores se leen tal como están; si falta una
  entrada, la tabla sale «No disponible» y el comando termina con 1. El detalle está en el
  [README de evaluación](packages/evaluation/README.md#5-tablas-y-figuras-de-la-tesis).

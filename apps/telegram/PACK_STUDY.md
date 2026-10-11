# Estudio pack: diez relatos para todos

El modo `pack` es el protocolo con el que se despliega el bot para EXP-4.

## Cómo se arma el paquete

- **6 relatos de participantes.**
  - Cada persona con la clave da su consentimiento, elige su perfil y escribe una idea, con
    prompt libre u obra guiada.
  - No elige formato ni opciones. El estudio asigna a ciegas `narrative` o `simulated` para
    que queden 3 y 3, y conserva esa asignación en los reintentos.
  - Ni el progreso ni la entrega dicen qué método se usó.
- **4 relatos del investigador**, con los prompts de
  [pack_author_prompts.json](pack_author_prompts.json): 2 en `narrative` y 2 en `simulated`.
  - Entran en la misma cola con prioridad 1: detrás de toda aportación pendiente de
    participantes y por delante del uso libre.
  - Se entregan al primer ID de `TELEGRAM_ADMIN_IDS`.
- **La cola espera a la cuota.** Hay una sola generación a la vez. Cuando Gemini no tiene
  cuota, la solicitud queda guardada y se reintenta sola; un reinicio no la pierde.

En cuanto el paquete tiene sus 10 plazas llenas (3+3 de participantes y 2+2 del autor), el
estudio guarda un snapshot con huella y abre la votación. El anunciador avisa a todos.

## Quien llega tarde

Quien aporta después de que se llene la plaza de su formato, o con el paquete ya completo:

- recibe su historia, que queda inscrita pero fuera del paquete, y el bot se lo dice;
- evalúa igual que el resto, desde que su solicitud está en la cola.

## Evaluación

- Cada lector tiene **una sesión de 5 relatos del paquete**.
- Se excluyen el suyo y los que ya conocía, y se prefieren los menos vistos.
- Son 15 preguntas: 5 relatos en ciclo por los 3 criterios.
- «Ya conocía esta historia» la sustituye por otra del paquete.

## Poner en marcha

En la PC que sirve el bot, doble clic en `iniciar-bot.bat` desde la raíz (ver
[DEPLOYMENT.md](DEPLOYMENT.md)). El script crea el estudio la primera vez con:

```powershell
.\.venv\Scripts\evaluation-study.exe --db Evaluations/telegram-pack/study.sqlite3 create telegram-pack --version 7.10.0 --mode pack --author-prompts apps/telegram/pack_author_prompts.json
.\.venv\Scripts\evaluation-study.exe --db Evaluations/telegram-pack/study.sqlite3 collect
```

`status` muestra qué plazas del paquete están llenas (`pack`) y qué historias del autor
faltan (`author_requests`).

Los prompts del autor se cargan al crear el estudio. Para cambiarlos, edita el JSON
**antes** del primer arranque.

## Recoger los resultados

- **Desde Telegram:** `/exportar_estudio`, como administrador y en privado. Se importa con
  `evaluation-study import-bundle`, como en [ROLLING_STUDY.md](ROLLING_STUDY.md).
- **Qué contiene la exportación:** el paquete, los prompts del autor, los votos, las
  exposiciones y la procedencia de cada relato.
- **Al terminar:** `evaluation-study --db RUTA close`.

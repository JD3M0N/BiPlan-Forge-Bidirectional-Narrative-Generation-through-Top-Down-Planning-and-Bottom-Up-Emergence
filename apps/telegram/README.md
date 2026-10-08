# ASG Telegram

Bot de Telegram de la fase de experimentación (EXP-4). Guía a cada participante del estudio
por pares a ciegas: entra con una clave, acepta participar, indica su perfil lector, crea su
**historia base** (su aportación a la muestra) y, cuando se abre la votación, compara relatos
de dos en dos. El protocolo está en
[ESTUDIO_FINAL.md](../../packages/evaluation/ESTUDIO_FINAL.md).

## Configuración

1. Habla con `@BotFather` en Telegram, crea un bot con `/newbot` y copia el
   token.
2. En el `.env` de la raíz configura:

```dotenv
TELEGRAM_BOT_TOKEN=token_entregado_por_BotFather
TELEGRAM_ACCESS_KEY=clave_que_entregas_a_los_participantes
ASG_EVALUATION_STUDY=Evaluations/tesis-final/study.sqlite3
STORY_GENERATOR=stagecraft
GEMINI_API_KEY=tu_clave
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_STAGE_MODEL=gemini-3.1-flash-lite
TTS_FALLBACK_VOICE=
```

`TELEGRAM_ACCESS_KEY` y `ASG_EVALUATION_STUDY` son obligatorias: sin ellas el bot no arranca
(código 2). La base del estudio debe existir antes (`evaluation-study create`).

`GEMINI_STAGE_MODEL` es opcional: manda los actores y el director de escena de las
historias simuladas a otro modelo, que tiene su propio cupo diario gratuito, y deja el de
`GEMINI_MODEL` para el resto del pipeline. Vacío, la función usa el modelo principal.

Las variables `ASG_*` de `.env.example` fijan los valores por defecto de cada opción
(formato, visión, memoria, turnos por beat, ledger de promesas y guía de esqueletos);
cada usuario puede cambiarlas para sí mismo desde `/settings`, sin tocar el `.env`.

3. Desde la raíz instala las dependencias y ejecuta:

```powershell
python -m pip install -r requirements-dev.txt
asg-telegram
```

En Windows, `asg-telegram` abre el bot en una consola independiente con su propio
título, y devuelve inmediatamente el control a la consola original. Al arrancar, la
nueva ventana muestra una cabecera con el bot, el modelo (y el de la función, si tiene
uno propio), la cuota y las opciones por defecto, y después un registro compacto en color: una línea por comando, selección,
paso de generación, entrega y acceso de cada usuario, incluido el progreso del
pipeline. Si el bot no puede arrancar o se detiene por un error, la ventana no se
cierra: espera a que se presione Enter, para que el error quede a la vista.

Para ejecutarlo en la consola actual, por ejemplo durante depuración, usa:

```powershell
asg-telegram-run
```

El proceso utiliza polling y no requiere dominio ni webhook.

### Recorrido del participante

`/start` responde siempre con el paso en que está la persona y lo que sigue. El paso se calcula
de la cola y de la base del estudio, así que sobrevive a los reinicios del bot.

1. **Clave.** Sin acceso, el bot solo acepta la clave. Tras cinco intentos fallidos bloquea
   quince minutos. El mensaje con la clave se borra del chat.
2. **Consentimiento.** Explica qué se le pedirá y con qué garantías (seudónimo, abstención,
   pausa). Sin aceptar no se registra nada.
3. **Perfil lector.** Ocasional, habitual o con formación literaria.
4. **Historia base.** Durante la recogida, `/newstory` solo ofrece los formatos en prosa
   (narrativa y simulada) y reserva la historia como aportación. Hasta que queda inscrita,
   `/newstory` y `/settings` no permiten nada más. `/aportar` la reemplaza mientras la recogida
   siga abierta. El investigador, inscrito con `--author`, no la necesita.
5. **Uso libre.** Con la base inscrita, cualquier formato, también guion. Esas historias no
   entran en la muestra.
6. **Votación.** Al abrirse (`evaluation-study start`), el bot avisa una sola vez a cada
   participante. Cada pregunta muestra el criterio, su guía `que_mirar` y el progreso. `/pausa`
   y `/evaluar` paran y reanudan.
7. **Cierre.** Al cerrar el estudio, el bot agradece la participación.

Los avisos de fase (recogida, votación y cierre) salen de una revisión cada minuto y se
registran en la cola, así que un reinicio no los repite.

### Configurar una historia

- `/newstory` pregunta primero el formato (narrativa, guion nativo o adaptado, o
  simulada), y recuerda la última elección de cada usuario.
- El botón «⚙️ Opciones» abre el mismo panel que `/settings`: un botón por opción
  aplicable al formato elegido (el perfil narrativo, el ledger de promesas y la guía de
  esqueletos siempre; la visión, el personaje de la visión, el tono, la memoria de los
  actores y los turnos por beat solo en la historia simulada; el audio y su voz, entre
  las voces de `asg-core`, siempre). «Restablecer» borra las preferencias guardadas.
- «Prompt libre» pide una descripción de texto corrido, como antes.
- «Obra guiada» ya no arma un prompt: pide título, género, ambientación y trama, deja
  añadir hasta diez personajes (nombre, rol, pronombre, descripción y secreto) y
  termina en una tarjeta de confirmación antes de generar.

### Entrega de historias

Las historias se generan de una en una, pero se entregan también de una en una para no
saturar la conexión con Telegram. La entrega usa el orden `story.md`, `story.mp3` (si
la opción de audio del run estaba activada), fragmentos formateados y el siguiente paso del
recorrido. Tanto el documento como el audio se reintentan ante fallos temporales. Si la
síntesis o el envío del MP3 falla, el bot informa al usuario y continúa con el texto.

## Cambiar el generador

`STORY_GENERATOR` selecciona el enfoque ASG y `GEMINI_MODEL` selecciona el
modelo de lenguaje usado por ese enfoque. Actualmente está registrado
`stagecraft`, que es el único valor y también el que vale por defecto.

Para probar otro enfoque, implementa el protocolo `StoryGeneratorAdapter` de
`asg_telegram.contract`, escribe su adaptador en `asg_telegram.generators` y
regístralo:

```python
DEFAULT_REGISTRY.register("mi-modelo", MiGenerador)
```

Después establece `STORY_GENERATOR=mi-modelo`. Los handlers de Telegram no
necesitan cambios.

Las solicitudes de historias se guardan en `Stories/telegram_queue.sqlite3` y
se procesan de una en una. El mensaje de progreso muestra la posición FIFO y
una estimación basada en las últimas diez historias. `/cancel` retira una
solicitud que aún esté esperando, o pide que una en curso se detenga antes de
la siguiente etapa. Tras reiniciar el bot, un trabajo interrumpido se reencola
una vez; si vuelve a interrumpirse, queda como `RECOVERY_EXHAUSTED`.

Si la historia pudo escribirse pero la auditoría o reescritura final falló, el
bot entrega la mejor versión disponible y muestra la advertencia guardada en
`metadata.json`. Los fallos de planificación no se degradan ni se entregan.

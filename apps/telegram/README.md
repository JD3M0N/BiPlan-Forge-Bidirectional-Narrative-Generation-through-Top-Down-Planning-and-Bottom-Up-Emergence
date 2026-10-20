# ASG Telegram

El bot del estudio humano de la tesis. Hace dos cosas:

1. **Crear historias**, con cuatro opciones en un solo menú:

   | Opción | Modelo | Cómo se pide |
   |---|---|---|
   | ✍️ Libre · Top-Down | se planifica la trama y después se escribe (`narrative`) | una idea en un mensaje |
   | 🧭 Guiada · Top-Down | igual | título, género, ambientación, trama, personajes y notas, paso a paso |
   | ✍️ Libre · Híbrido | los personajes representan la obra y se narra lo que hicieron (`simulated`) | una idea en un mensaje |
   | 🧭 Guiada · Híbrido | igual | paso a paso |

   La historia llega como `historia.md`, con su narración en `historia.mp3` y el texto en el
   chat.

2. **Compararlas** (`/evaluar`). Es la primera evaluación, antes del estudio a ciegas entre
   personas. Cada persona compara sus propias dos historias, una de cada modelo.

## Lo que el bot recomienda

El bot guía a cada persona hacia el par que sirve a la tesis:

1. Al empezar, le recomienda crear dos historias con **la misma idea**, primero con Top-Down.
2. Cuando llega la Top-Down, le ofrece **«🔁 La misma idea con Híbrido»**. Ese botón repite la
   misma petición, libre o guiada, con el otro modelo. Así, entre las dos historias solo cambia
   el modelo.
3. Con una historia de cada modelo, le ofrece **compararlas**.

Si alguien empieza por el Híbrido, el bot le propone la misma idea con Top-Down.

## La evaluación, paso a paso

Sigue lo que pide el tutor en el audio del 3 de octubre (`docs/`, metodología en
[packages/evaluation/METODOLOGIA.md](../../packages/evaluation/METODOLOGIA.md)): las personas no
saben poner notas del 1 al 10, pero sí decir cuál de dos prefieren, en tres criterios de alto
nivel.

1. Las dos historias llegan como **Historia A** e **Historia B**. El orden es aleatorio y no se
   dice qué modelo escribió cada una. La persona las lee o escucha y pulsa «Ya la leí» en cada
   una.
2. Después vienen **tres preguntas, una a una**, con las palabras del tutor:
   - creatividad: «¿cuál tiene más creatividad?»;
   - personajes: «¿en cuál están los personajes mejor desarrollados?»;
   - trama: «¿en cuál está la trama más interesante?».

   Cada pregunta trae qué mirar. Se responde A, B o «No puedo decidir».
3. Tras cada respuesta, un **«¿por qué?»** opcional, en una frase o con «Saltar».
4. Al final el bot revela qué modelo era cada historia y recomienda el siguiente paso.

Cada historia entra en una sola comparación. Si el bot se reinicia a mitad, `/evaluar` sigue
donde se quedó. Las respuestas se guardan **por modelo, no por letra**, en
`Evaluations/estudio/pares_propios.sqlite3`. Para sacarlas:

```powershell
asg-telegram --export Evaluations/estudio/pares_propios.json
```

Las preguntas son las mismas del estudio a ciegas
(`packages/evaluation/planilla/criterios_humanos.csv`), así que estas respuestas se leen igual
cuando se monte el sistema por pares.

## Ponerlo en marcha en tu PC

1. Crea el bot en Telegram con `@BotFather` (`/newbot`) y copia el token.
2. Prepara el entorno, una sola vez, desde la raíz del repositorio:

   ```powershell
   .\setup.ps1
   .\.venv\Scripts\Activate.ps1
   ```

3. Copia `.env.example` a `.env`, si no lo tienes, y rellena al menos:

   ```dotenv
   TELEGRAM_BOT_TOKEN=token_de_BotFather
   GEMINI_API_KEY=tu_clave
   # Recomendado: los actores del Híbrido gastan el cupo de otro modelo.
   GEMINI_STAGE_MODEL=gemini-3.1-flash-lite
   ```

   Las variables `ASG_*` (visión, memoria, turnos por beat…) fijan las opciones de todas las
   historias. El perfil sale siempre de la petición: «un cuento corto» o «unas 3.000 palabras»
   eligen Esencial o Desarrollada, y si no dice nada, decide el analista.
4. Arranca el bot y déjalo abierto:

   ```powershell
   asg-telegram
   ```

   Si falta algo, el bot lo dice al arrancar y no se queda a medias.

**Ten en cuenta:**

- **Una historia a la vez**, por orden de llegada, y cada persona con como mucho una solicitud
  en marcha.
- **Tiempos.** Una Top-Down tarda unos minutos y gasta unas 20 llamadas. Una Híbrida tarda
  media hora o más y gasta de 100 a 300. El cupo gratuito ronda las 500 llamadas diarias por
  modelo, y `asg-budget` dice cuánto queda.
- **Cuota.** Si se acaba, el bot lo dice y la persona la pide más tarde.
- **Reinicios.** La cola vive en `Stories/telegram_jobs.sqlite3`: si el bot se reinicia, una
  historia interrumpida vuelve a la cola una vez.

## Comandos del bot

- `/start`: qué hace el bot y qué te toca hacer.
- `/crear`: las cuatro opciones.
- `/evaluar`: comparar tus dos historias.
- `/cancelar`: cancela la solicitud o la conversación en curso.

## El estudio a ciegas entre personas (para más adelante)

Sigue en el bot, pero oculto: `/estudio` no sale en la lista de comandos. Presenta pares de
historias de otras personas, nunca la propia, y responde a las mismas tres preguntas. Mientras
el estudio está en recogida, cada historia nueva se inscribe sola. Se opera desde la raíz:

```powershell
$db = "Evaluations/estudio/study.sqlite3"
asg-study --db $db status                 # fase, historias, votos
asg-baseline "PREMISA" --output Stories/Baseline/01   # línea base de un solo prompt
asg-study --db $db add Stories/Baseline/01          # inscribirla
asg-study --db $db exclude ID             # sacar una historia antes de abrir
asg-study --db $db open                   # congela el conjunto y abre la votación
asg-study --db $db close                  # cierra la votación
```

El análisis sigue en [packages/evaluation](../../packages/evaluation/README.md).

## Código

| Módulo | Qué hace |
|---|---|
| `app.py` | arma la aplicación, arranca el trabajador y exporta las comparaciones |
| `config.py` | lee el token y las rutas de la cola, el estudio y las comparaciones |
| `guide.py` | textos, el menú de cuatro opciones y la recomendación del siguiente paso |
| `handlers.py` | `/start`, `/crear`, «la misma idea» y `/cancelar` |
| `wizard.py` | el asistente guiado, como máquina de estados pura |
| `jobs.py` | la cola SQLite y el trabajador que genera, entrega y recomienda |
| `generator.py` | el adaptador de Stagecraft, único módulo que lo importa |
| `delivery.py` | envío del archivo, el audio y el texto, con reintentos de red |
| `pairs.py` | las comparaciones de las propias historias, en SQLite |
| `review.py` | el flujo de `/evaluar` |
| `voting.py` | el flujo de `/estudio`, el estudio a ciegas |

Los tests (`tests/test_bot.py`) recorren, con un Telegram y un generador falsos:

- las cuatro opciones;
- «la misma idea»;
- la comparación completa;
- la cola;
- el estudio a ciegas.

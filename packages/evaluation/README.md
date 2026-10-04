# ASG Evaluation

Guarda las evaluaciones humanas de cada historia y resume el corpus con tres informes. Solo lee
JSON y Markdown del disco: nunca importa el pipeline, así que un run se puede estudiar mucho
después de que el código que lo escribió haya cambiado.

La evaluación de la tesis sigue [METODOLOGIA.md](METODOLOGIA.md): rasgos contables extraídos
de cada historia, tres criterios humanos por pares a ciegas y un juez aprendido de esos pares. Lo
que se mide está en la planilla [planilla/](planilla/) (CSV y `planilla_evaluacion.xlsx`).

## Evaluación humana

> Las seis métricas de 1 a 10 de esta sección son el instrumento heredado de la tesis de Roger
> Fuentes. Siguen funcionando, pero no son la medida de la tesis: ver
> [METODOLOGIA.md](METODOLOGIA.md), §1.

Cada carpeta con una historia terminada (`story.md`) lleva un `evaluation.json`. Las
puntuaciones son enteros de **1 a 10**, donde 1 es el resultado más bajo y 10 el más alto:

- `coherence`: sentido global, continuidad del estado del mundo y del conocimiento, motivaciones
  creíbles y progresión causal sin contradicciones.
- `pacing`: estructura reconocible, progreso perceptible en cada tramo y dosificación de
  información, decisiones, consecuencias y tensión.
- `creativity`: originalidad, elementos inesperados e ideas valiosas, sin clichés ni tropos
  trillados.
- `engagement`: interés e impacto emocional sostenidos por preguntas claras, progreso visible,
  costos cambiantes y preparación narrativa.
- `relevance`: fidelidad al prompt original, sin elementos fuera de lugar.
- `satisfaction`: si las expectativas importantes reciben pagos claros, preparados, costosos y
  sorprendentes sin romper lo prometido.

### Formato de `evaluation.json`

Una historia pendiente de evaluar contiene la plantilla:

```json
{
  "schema_version": 1,
  "evaluations": [
    {
      "user": null,
      "coherence": null,
      "pacing": null,
      "creativity": null,
      "engagement": null,
      "relevance": null,
      "satisfaction": null
    }
  ]
}
```

- Un registro con **los seis parámetros nulos o ausentes** es una plantilla pendiente, esté donde
  esté en la lista y tenga o no `user`: escribir solo el nombre y puntuar después es válido. Las
  plantillas se descartan al guardar la siguiente evaluación; las completas se conservan y la
  nueva se añade al final.
- Cualquier otro registro incompleto (unas puntuaciones sí y otras no, un campo desconocido, un
  valor fuera de 1-10) se rechaza con un error que nombra **la posición del registro y el campo
  culpable**, para poder arreglar el archivo a mano.
- Una evaluación completa exige un `user` no vacío y los seis parámetros.

El archivo se puede editar a mano respetando ese contrato, o rellenar desde **asg-console →
Evaluar historia** o desde el bot de Telegram al terminar una generación. Las escrituras se
serializan con `asg_core.file_lock` y se sustituyen de forma atómica, así que dos evaluaciones
simultáneas no se pisan.

### API

```python
from asg_evaluation import GROUPINGS, add_evaluation, collect_evaluations, summarize

add_evaluation(
    story_directory,
    user="lector-1",
    scores={
        "coherence": 8,
        "pacing": 7,
        "creativity": 9,
        "engagement": 8,
        "relevance": 10,
        "satisfaction": 8,
    },
)

records = collect_evaluations(stories_root)  # todas, incluidas las no evaluadas
summarize(records, key=GROUPINGS["profile"])  # media y varianza por perfil
```

`read_evaluations(story_directory)` devuelve solo las evaluaciones completas de una historia.
La varianza es **muestral** y vale `None` con una sola evaluación, que es el caso habitual por
historia; la poblacional daría un `0.0` engañoso. Los grupos juntan evaluaciones individuales,
no medias por historia: una historia evaluada dos veces pesa el doble, y por eso cada resumen
conserva las dos cuentas, `stories` y `evaluations`.

## Los tres informes

Los tres comparten ejes. La **versión** es la del generador (`generator_version.json`), no la
del contrato de pipeline, que agrupa releases distintas bajo una misma etiqueta. El **enfoque**
sale de la carpeta: `Stories/Stagecraft` y `Stories/Top-Down` dan `Top-Down` o `Hybrid` según el
formato, y cualquier otra carpeta, como las historias históricas de `Stories/Bottom-Up`, da su
propio nombre. Un CSV va en UTF-8 sin BOM: Excel en español necesita *Datos → Desde texto*.

- **`report-evaluations`** resume las puntuaciones humanas por historia, perfil, versión,
  enfoque o formato. Con `--csv` escribe una fila por evaluación. Una historia con el
  `evaluation.json` corrupto se informa por `stderr` y el comando termina con código 1, pero el
  resto del corpus sí se agrega.
- **`report-story-craft`** recalcula desde `story.md`, con `asg_core.craft_metrics`, la
  artesanía de la prosa: proporción de párrafos con diálogo, palabras por frase y palabras por
  párrafo. La cruza con el plan, la revisión, el uso de Gemini y los metadatos del run, y da
  mediana y rango. Al recalcular desde `story.md` compara también los runs anteriores a que
  esas cifras se registraran. No sustituye a la evaluación humana: dice si el pipeline escribió
  escena o sinopsis, no si la historia es buena. Por defecto solo mide el formato narrativo,
  porque un guion teatral mediría casi cero diálogo; `--format prose` compara narrativo y
  simulado.
- **`report-simulations`** resume cada función representada desde `simulation_metrics.json`:
  beats alcanzados, intervenidos y forzados, turnos por beat, repetición del habla y del gesto,
  eco del guion (`script_echo`), menciones de lo que un personaje no podía saber
  (`unknown_mentions`) y compresión de la narración, por voz, memoria, perfil y versión. Una cifra que un run no registró sale como no medida, nunca
  como cero.

Las opciones completas están en [commands.md](../../commands.md).

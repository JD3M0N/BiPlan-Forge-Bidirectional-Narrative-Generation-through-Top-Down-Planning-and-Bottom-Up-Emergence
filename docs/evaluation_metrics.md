# Evaluación humana de historias

Cada carpeta que contiene una historia terminada (`story.md`) incluye un
`evaluation.json`. Las puntuaciones son números enteros de **1 a 10**, donde
1 representa el resultado más bajo y 10 el más alto.

## Parámetros

- `coherence`: sentido global, continuidad del estado del mundo y del
  conocimiento, motivaciones creíbles y progresión causal sin contradicciones.
- `pacing`: estructura reconocible, progreso perceptible en cada tramo y
  dosificación de información, decisiones, consecuencias y tensión.
- `creativity`: originalidad, incorporación de elementos inesperados e ideas
  valiosas, evitando clichés y tropos trillados.
- `engagement`: interés e impacto emocional sostenidos por preguntas claras,
  progreso visible, costos cambiantes y preparación narrativa.
- `relevance`: fidelidad al prompt original y ausencia de elementos fuera de
  lugar respecto al tema solicitado.
- `satisfaction`: valoración de si las expectativas importantes reciben pagos
  claros, preparados, costosos y sorprendentes sin romper lo prometido.

## Formato

Una historia pendiente de evaluación contiene:

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

Un registro cuyos **seis parámetros son nulos o ausentes** se considera una
plantilla pendiente, esté donde esté en la lista y tenga o no `user` relleno:
escribir solo el nombre del evaluador y dejar las puntuaciones para después es
una edición válida. Las plantillas pendientes se descartan al guardar la
siguiente evaluación; las evaluaciones completas se conservan y la nueva se
agrega al final.

Cualquier otro registro incompleto —con unas puntuaciones puestas y otras
nulas, con un campo desconocido o con un valor fuera de 1-10— se rechaza con un
error que nombra la **posición del registro y el campo culpable**, de modo que
el archivo se pueda arreglar a mano en vez de quedar inservible.

Cada evaluación completa requiere un `user` no vacío y los seis parámetros.
`schema_version` sigue siendo **1**: el formato no ha cambiado, solo se ha
relajado su interpretación, así que los `evaluation.json` ya escritos siguen
siendo válidos.

El archivo puede editarse manualmente respetando este contrato. También puede
actualizarse desde **asg-console → Evaluar historia** o desde el bot de
Telegram al terminar una generación. Las dos vías se serializan con un lock
compartido (`asg_core.file_lock`), así que dos evaluaciones simultáneas no se
pisan ni se pierden.

## API reutilizable

Clientes externos, pueden instala `asg-evaluation` y usar:

```python
from asg_evaluation import add_evaluation

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
```

La función valida el documento y realiza una sustitución atómica para no
corromper evaluaciones existentes ante un fallo de escritura.

## Leer y agregar

El mismo paquete expone la lectura:

```python
from asg_evaluation import GROUPINGS, collect_evaluations, read_evaluations, summarize

read_evaluations(story_directory)          # evaluaciones completas de una historia
records = collect_evaluations(stories_root)  # todas, incluidas las no evaluadas
summarize(records, key=GROUPINGS["profile"])  # media y varianza por perfil
```

Ejes disponibles en `GROUPINGS`: `story`, `profile`, `version`,
`version-profile` y `approach`. La versión es la del **generador**
(`generator_version.json`), no la del contrato de pipeline: `pipeline_version`
agrupa releases distintas bajo una misma etiqueta y borra justo la comparación
que interesa.

La varianza es **muestral** y vale `None` cuando el grupo tiene una sola
evaluación, que es el caso habitual por historia; la varianza poblacional daría
un `0.0` engañoso. Las agrupaciones juntan evaluaciones individuales, no medias
por historia, así que una historia evaluada dos veces pesa el doble: por eso
cada resumen conserva las dos cuentas, `stories` y `evaluations`.

## Comando

```powershell
report-evaluations [--stories PATH] [--csv PATH] [--group EJE]
```

Imprime la cobertura del corpus y una tabla por eje (`--group all` por defecto).
Con `--csv` escribe **una fila por evaluación**, con las columnas
`approach, story, run_id, narrative_profile, generator_version, pipeline_version,
evaluation_index, user` y los seis parámetros. El archivo va en UTF-8 sin BOM:
Excel en español necesita *Datos → Desde texto* para leerlo bien.

Una historia con el `evaluation.json` corrupto se informa por `stderr` y el
comando termina con código 1, pero el resto del corpus sí se agrega.

# Evaluación humana de historias

Cada carpeta que contiene una historia terminada (`story.md`) incluye un
`evaluation.json`. Las puntuaciones son números enteros de **1 a 10**, donde
1 representa el resultado más bajo y 10 el más alto.

## Parámetros

- `coherence`: sentido global de la historia, conexión lógica entre los
  eventos y progresión causal clara, sin saltos abruptos ni huecos en la trama.
- `pacing`: estructura reconocible —inicio, nudo y desenlace— y dosificación de
  la información y la tensión sin monotonía ni aceleración excesiva.
- `creativity`: originalidad, incorporación de elementos inesperados e ideas
  valiosas, evitando clichés y tropos trillados.
- `engagement`: interés, disfrute e impacto emocional que el relato mantiene
  en el lector de principio a fin.
- `relevance`: fidelidad al prompt original y ausencia de elementos fuera de
  lugar respecto al tema solicitado.
- `satisfaction`: valoración global de cuánto satisface la historia las
  expectativas del evaluador.

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

La plantilla nula es el único registro incompleto permitido. Al registrar la
primera evaluación se reemplaza; las siguientes se agregan a `evaluations`.
Cada evaluación completa requiere un `user` no vacío y los seis parámetros.

El archivo puede editarse manualmente respetando este contrato. También puede
actualizarse desde **asg-console → Evaluar historia**.

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

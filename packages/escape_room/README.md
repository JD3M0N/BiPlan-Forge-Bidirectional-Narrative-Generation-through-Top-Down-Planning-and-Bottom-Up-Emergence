# ASG Escape Room

Motor Bottom-Up determinista para historias emergentes basadas en un escape
room cooperativo.

## Arquitectura

- `contracts.py`: modelos Pydantic y API serializable.
- `domain.py` y `engine.py`: estado real y resolución simultánea.
- `policy.py` y `planning.py`: prioridades y rutas BFS sobre creencias.
- `metrics.py`: agregación pura de resultados individuales y globales.
- `narrative.py`: protocolo narrativo, Gemini y respaldo local.
- `storage.py`: trazas JSONL, artefactos, métricas y CSV.

Cada simulación individual nueva guarda su narración en `story.mp3` y sus datos
de idioma/voz en `audio.json`. Un fallo de TTS queda en `metadata.json` sin
invalidar la simulación ni `story.md`; los experimentos batch no generan audio.

Las políticas no leen archivos, variables de entorno ni proveedores remotos.
El motor puede utilizarse directamente:

```python
from asg_escape_room import load_room, run_simulation

room = load_room("maps/escape_room.json")
result, model = run_simulation(room, seed=0, tick_limit=300)
```

Consulte el `README.md` de la raíz para instalación, CLI, formato de salida y
ejecución batch.

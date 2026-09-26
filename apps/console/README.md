# ASG Console

Interfaz de terminal para generar historias con Stagecraft y registrar evaluaciones humanas.

## Uso

Instala el monorepo desde su raíz y ejecuta:

```powershell
asg-console
```

El menú principal tiene dos opciones:

- **Stagecraft** pide el prompt, el formato de salida (narrativa, guion nativo o adaptado,
  simulada) y, si es simulada, el punto de vista. Los valores por defecto salen de `.env`.
  Al terminar muestra la ruta de `story.md` y la de `story.mp3`; no reproduce el audio.
- **Evaluar historia** lista todas las historias de `Stories/`, incluidas las históricas de
  `Stories/Bottom-Up/`, y guarda las seis puntuaciones en su `evaluation.json`.

`ConsoleApp` solo coordina la navegación; cada flujo vive en su módulo (`stagecraft.py`,
`evaluation.py`). Todos reciben `input_fn` y `output` inyectados (`types.py`), así que los tests
recorren los menús sin terminal.

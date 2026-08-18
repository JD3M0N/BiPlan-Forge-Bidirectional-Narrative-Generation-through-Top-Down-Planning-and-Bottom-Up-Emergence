# ASG Console

Interfaz interactiva para ejecutar los modelos Top-Down y Bottom-Up desde un
menú común. No reemplaza los comandos directos `generate-story` y
`run-escape-room`.

El menú también permite seleccionar cualquier `story.md` de ambos modelos y
agregar una evaluación humana a su `evaluation.json`.

```powershell
asg-console
```

Al crear una historia Top-Down se escribe un único prompt. El analista conserva la
solicitud original, la traduce y enriquece internamente en inglés y mantiene el idioma
final pedido por el usuario o, si no se indica, el idioma dominante del prompt.

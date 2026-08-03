# ASG Console

Interfaz interactiva para ejecutar los modelos Top-Down y Bottom-Up desde un
menú común. No reemplaza los comandos directos `generate-story` y
`run-escape-room`.

El menú también permite seleccionar cualquier `story.md` de ambos modelos y
agregar una evaluación humana a su `evaluation.json`.

```powershell
asg-console
```

Al crear una historia Top-Down se puede escribir el prompt manualmente o usar
el modo asistido. Este último enriquece una idea inicial, muestra tres enfoques
creativos y permite seleccionar cuál se enviará al pipeline Top-Down.

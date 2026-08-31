# ASG Console

Interfaz unificada para ejecutar el pipeline Top-Down, observar simulaciones
Bottom-Up y registrar evaluaciones humanas sin mezclar la lógica de los menús.

## Uso

Instala el monorepo desde su raíz y ejecuta:

```powershell
asg-console
```

`ConsoleApp` coordina la navegación. Los módulos `top_down`, `bottom_up` y
`evaluation` contienen los flujos específicos y pueden probarse por separado.
Cada historia nueva muestra las rutas de `story.md` y `story.mp3`; la consola no
reproduce el audio automáticamente.

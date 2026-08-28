# ASG Console

Interfaz unificada para ejecutar el pipeline Top-Down, observar simulaciones
Bottom-Up y registrar evaluaciones humanas sin mezclar la l?gica de los men?s.

## Uso

Instala el monorepo desde su ra?z y ejecuta:

```powershell
asg-console
```

`ConsoleApp` coordina la navegaci?n. Los m?dulos `top_down`, `bottom_up` y
`evaluation` contienen los flujos espec?ficos y pueden probarse por separado.

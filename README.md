# Generador de historias: Top-Down e híbrido

Proyecto de tesis que genera y evalúa historias con un solo generador, **Stagecraft**, y dos
enfoques:

- **Top-Down**: agentes LLM sobre Gemini planifican primero (mundo, personajes, grafo de eventos) y
  escriben después, en prosa (`narrative`) o como guion teatral (`script`).
- **Híbrido** (`simulated`): el mismo plan se escribe como guion, los personajes lo representan con
  memoria propia (solo saben lo que presenciaron) y la historia se narra del registro de esa función.

## Estructura

| Carpeta | Contenido |
|---|---|
| `packages/stagecraft` | el generador |
| `packages/evaluation` | evaluaciones humanas e informes del corpus |
| `packages/core` | utilidades compartidas |
| `apps/console`, `apps/telegram`, `apps/studio` | consola, bot de Telegram e interfaz web |
| `Stories/` | las historias generadas (datos de investigación, no se borran) |
| `docs/` | [resumen técnico](docs/resumen.md) y los PDF fuente de la tesis |

## Puesta en marcha

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
.\venv.ps1
# Edita .env: añade GEMINI_API_KEY para generar de verdad
generate-story "Un caballero rescata a una princesa de un dragón"
.\run-tests.ps1           # los tests usan proveedores falsos
```

Para instalar solo el bot en Windows: `.\setup.ps1 -Telegram`.
Consulta [la guía de instalación 24/7](apps/telegram/DEPLOYMENT.md).
Las dependencias se fijan en `constraints-py312.txt` para Python 3.12 de 64 bits.

## Más información

- [commands.md](commands.md): todos los comandos.
- [docs/resumen.md](docs/resumen.md): diseño y decisiones.
- [TODO.md](TODO.md): roadmap y experimentos.
- [CLAUDE.md](CLAUDE.md): guía detallada para agentes.

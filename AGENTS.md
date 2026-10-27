# Guía de trabajo

Stagecraft es un monorepo de tesis: genera historias Top-Down (`narrative`, `script`) e
híbridas (`simulated`), y las evalúa con pares humanos y rasgos con citas.

## Mapa y lecturas por tarea

| Área | Código | Contratos que consultar al modificarla |
|---|---|---|
| Generación y escritura | `packages/stagecraft` | [Generación](docs/architecture/generation.md) |
| Proveedores, cuotas, almacenamiento y core | `runtime/`, `packages/core` | [Ejecución](docs/architecture/runtime.md) |
| Actuación, memoria y narración | `stage/` | [Simulación](docs/architecture/simulation.md) |
| Evaluación y corpus | `packages/evaluation` | [Evaluación](docs/architecture/evaluation.md) |
| Bot e interfaz web local | `apps/telegram`, `apps/studio` | [Interfaces](docs/architecture/interfaces.md) |

Las rutas `runtime/` y `stage/` son relativas a `packages/stagecraft/src/asg_stagecraft/`.
[docs/resumen.md](docs/resumen.md) explica el diseño de la tesis; los README de cada paquete
explican su uso. Lee las referencias pertinentes antes de modificar un subsistema.

## Navegar con poco contexto

- Empieza por `git status --short` y `git ls-files`; respeta los cambios existentes del usuario.
- Busca con `rg` dentro del subsistema afectado. Lee rangos o secciones, no el monorepo entero.
- No cargues corpus, cachés, changelogs completos ni todas las referencias por defecto.
- El trabajo se hace por fases con la skill `phase`: guía en [planning/phase.md](planning/phase.md),
  plan en [planning/roadmap.md](planning/roadmap.md) y decisiones (con las reglas del tutor) en
  [planning/decisions.md](planning/decisions.md). Consulta el roadmap y
  [planning/fichas.md](planning/fichas.md) por el ID o área antes de proponer trabajo nuevo.
- `TODO.md` es de Josue: léelo si hace falta, pero no escribas en él.
- Los nombres de carpetas de caché o restos locales no prueban que exista una función vigente.
- Antes de eliminar código, comprueba imports, comandos, registros, reflexión y recursos de
  empaquetado. Los validadores Pydantic y las rutas FastAPI se invocan indirectamente.

## Instalación y comandos

Desde la raíz, en PowerShell:

```powershell
.\setup.ps1
.\.venv\Scripts\Activate.ps1
asg help
asg-telegram
```

`setup.ps1` prepara el entorno con Python 3.12 o 3.15, instala los cinco paquetes editables y crea `.env`
si falta. Las claves se configuran localmente; no las imprimas ni las añadas a Git.
`asg help` enumera los comandos y cada uno acepta `--help`.
Todo comando nuevo empieza por `asg-` y se añade a `asg_core/help.py`; un test cruza
esa lista con los `pyproject.toml`. Conserva los comandos públicos actuales.

## Calidad y pruebas

```powershell
.\quality.ps1        # Ruff, formato, suite completa y pip check
.\quality.ps1 -Fast  # suite completa, para iterar
.\run-tests.ps1      # único punto de entrada para los tests
```

- Ejecuta `quality.ps1` antes de dar por terminado un cambio; no se detiene al primer fallo.
- Para pruebas usa `run-tests.ps1`, nunca `pytest` directo. Se exige la suite completa al cerrar.
  Sus argumentos después de `--` sirven para depurar, no sustituyen esa comprobación final.
- El script usa `%TEMP%` y, si no es escribible, `.cache/pytest-tmp`, con salida compacta.
  La duración depende del entorno; no presupongas que termina en un minuto.
- Mantén la anulación de `os.fsync` del `conftest.py` raíz y el temporal fuera de E: cuando
  `%TEMP%` funcione: sincronizar cada artefacto en ese disco encarece mucho la suite.
- No actives `RUN_GEMINI_LIVE=1` sin solicitud explícita: consume cuota real.
- Amplía pruebas existentes y reutiliza fixtures antes de añadir otras; parametriza casos
  del mismo comportamiento. Evita pruebas tautológicas o que solo repitan constantes.
- Actualiza las pruebas cuando cambie un contrato; no las relajes ni omitas para obtener verde.
  Conserva nombres y garantías de tests citados en documentos, o actualiza también sus citas.
- `FakeProvider`, `make_request` y `valid_plan` se comparten desde
  `packages/stagecraft/tests/test_generator_v5.py`.
- El gate de docstrings resuelve rutas desde su archivo y debe fallar si no encuentra módulos.
  `docs/` y `Stories/` están excluidos de Ruff; los demás ejemplos deben respetar el formato.

## Límites y compatibilidad

- Dependencias: `core ← evaluation ← stagecraft ← telegram, studio`; `core` no depende del
  resto y `evaluation` nunca importa `stagecraft`: lee los artefactos del disco.
- Historias, evaluaciones, PDFs, experimentos y bases de datos son investigación: no se borran
  durante limpiezas, aunque estén ignorados. Incluye `Stories/Bottom-Up/` y los runs antiguos.
- Conserva `redaccion/`, archivos sin versionar y configuración local del usuario.
- No cambies prompts, esquemas, defaults experimentales ni formatos persistidos como efecto
  secundario de una limpieza. Consulta las diferencias intencionales en las referencias.
- Si cambia el significado o conjunto de artefactos, versiona el contrato; una limpieza interna
  solo incrementa el parche del paquete y mantiene `PIPELINE_VERSION`.
- Tras cambiar una versión, reinstala los paquetes editables afectados con
  `python -m pip install --no-deps -e <paquete>` antes de validar: los tests cotejan sus metadatos.
- Una función aparentemente duplicada puede preservar un contrato distinto: verifica sus
  consumidores antes de unificarla. ING-3 es un refactor independiente, no trabajo incidental.

## Idioma y documentación

- Docstrings de producción: inglés ASCII, breves y útiles, incluso en closures. Lo comprueba
  `tests/test_source_documentation.py`; no basta con repetir el nombre de la función (ING-1).
- Texto de interfaz y documentación del proyecto: español. Las reglas del idioma de la ficción
  y los errores que regresan al modelo se describen en las referencias de generación.
- Mantén una fuente por contrato y enlaces desde las demás páginas. `AGENTS.md` contiene las
  reglas generales; `CLAUDE.md` solo remite aquí. El detalle técnico vive en las referencias.
- `README.md` es la portada breve; el detalle operativo vive en los README de los paquetes.
- `.gitignore` permite `docs/resumen.md` y `docs/architecture/*.md`; comprueba que cualquier
  documento nuevo destinado al repositorio no quede ignorado.
- Las reglas de tareas, tarjetas, hitos y cierre están en [planning/phase.md](planning/phase.md)
  y en la skill `phase`. Una tarea cerrada se retira del roadmap; el historial se conserva en
  Git y changelogs.
- Registra mediciones con fecha y alcance: una suite verde no mide calidad literaria ni actualiza
  los recuentos históricos del corpus.

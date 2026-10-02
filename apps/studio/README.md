# StageCraft

StageCraft es la interfaz gráfica de Stagecraft: una aplicación web local, negra y naranja, para
escribir una obra, elegir cómo se genera y se narra, seguir la función en vivo y comparar
funciones entre sí.

```powershell
python -m pip install -r requirements-dev.txt   # desde la raíz, una vez
asg-studio                                      # abre http://127.0.0.1:8765/
```

| Opción | Qué hace |
| --- | --- |
| `--port N` | Puerto (8765 por defecto). |
| `--no-browser` | No abre el navegador al arrancar. |
| `--demo` | Modo demostración: reproduce el progreso de la última función simulada completa sin llamar a Gemini ni escribir nada. La cabecera lo marca como DEMO. |
| `--host H` | Escucha en otra dirección. Fuera de `127.0.0.1`, cualquiera en la red podría gastar tu cuota: el comando lo avisa. |

Generar necesita `GEMINI_API_KEY` en el `.env` de la raíz; sin ella la interfaz abre igual, lo
indica en la cabecera y deja explorar y comparar las funciones guardadas. Si la función
simulada tiene modelo propio (`GEMINI_STAGE_MODEL`), la cabecera lo muestra junto al principal.

## Las tres vistas

- **Crear.** La obra, como ficha (título, trama, género, ambientación, notas y reparto) o como
  prompt libre, más el riel de opciones: formato, perfil, narración (visión, personaje de la
  visión y tono del narrador), simulación (memoria y turnos por beat), planificación (ledger y
  guía) y audio (voz, con muestra). Al añadir un personaje al reparto, aparece en el selector del
  personaje de la visión. «Ver prompt» enseña el prompt exacto y el comando `generate-story`
  equivalente; **Estrenar** (o Ctrl+Enter) encola la función.
- **Funciones.** Todas las funciones de `Stories/Stagecraft` y `Stories/Top-Down`, con su lector:
  la historia, el log de la función (con «ver como», que atenúa lo que una visión no ve), las
  cifras y la configuración. **Repetir con otra configuración** rellena Crear con la misma obra.
- **Comparar.** De dos a cuatro funciones eje por eje: resalta en naranja lo que difiere, dice si
  la comparación está emparejada (misma obra, modelo y perfil, un solo eje distinto) y pone las
  cifras al lado, con «no medido» donde un run no registró algo.

## Cómo está hecha

- Backend FastAPI (`src/asg_studio`): `catalog.py` describe las opciones, `jobs.py` es la cola de
  un solo hilo, `library.py` lee las funciones, `security.py` guarda la puerta.
- Frontend sin paso de build (`src/asg_studio/static`): HTML, CSS y módulos ES. Toda la
  interfaz de opciones se pinta desde `GET /api/catalog`.
- Nunca escribe ni borra nada en `Stories/`: la generación la hace Stagecraft y la lectura es
  tolerante, como los informes de evaluation.
- Toda petición que cambia algo exige la cabecera `X-StageCraft: 1`, el `Host` debe ser local y la
  política de contenido solo permite los archivos propios de la app.
- Una función se detiene con `should_cancel`, que el pipeline consulta antes de cada llamada a un
  agente; nunca lanzando una excepción desde un callback.

## Opciones pendientes

La interfaz enseña, deshabilitadas y con su ficha, las opciones que el roadmap aún no construye:
memoria completa frente a recuperada, partir del plan de otra función (MED-5), la visión
«omnisciente sin destripes» (SIM-13) y el audio a varias voces.

**Receta para volver real una pendiente**, tal como se siguió para el inventario en 7.6:

1. Añadir el campo a `GenerationOptions` (`packages/stagecraft/src/asg_stagecraft/options.py`)
   y el mismo kwarg a `StoryGenerator`; `test_generation_options.py` obliga a hacer las dos.
2. Consumirlo donde vive el mecanismo, condicionado a que esté activo para que los prompts sin
   él no cambien. El inventario lo hizo con un módulo de estado (`stage/inventory.py`), los
   testigos en `perception.py` y los bloques del actor y del director en `render.py`.
3. En `catalog.py` de esta app, pasar su `status` de `pending` a `available`.
4. Añadir un test de los dos brazos y subir `PIPELINE_VERSION` si cambia algún artefacto.

La interfaz y `generation_options.json` lo recogen solos.

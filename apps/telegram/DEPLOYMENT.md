# Instalar el bot en otra PC Windows

## En un paso

Copia o clona el proyecto completo en la PC, sin `.venv`. Si tienes un `.env` ya relleno,
ponlo en la raíz. Después haz doble clic en **`iniciar-bot.bat`**.

`desplegar-bot.ps1` hace lo siguiente:

1. Usa el Python 3.12 o 3.15 que ya haya; si no hay ninguno, instala 3.12 con winget o con
   el instalador oficial, por usuario.
2. Ejecuta `setup.ps1 -Telegram`.
3. Pide por consola solo lo que falte en `.env`: `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_ACCESS_KEY`, `GEMINI_API_KEY` y `TELEGRAM_ADMIN_IDS`.
4. Crea el estudio pack ([PACK_STUDY.md](PACK_STUDY.md)) si no existe.
5. Quita la suspensión con el equipo enchufado.
6. Registra la tarea «StageCraft Telegram», que arranca el bot al iniciar sesión y lo
   reinicia si se cae.

Repetirlo es seguro: detiene el bot, sincroniza y lo vuelve a arrancar, sin tocar los datos.

- `iniciar-bot.bat -Estado`: estado y últimas líneas de `Stories/telegram-bot.log`.
- `iniciar-bot.bat -Actualizar`: `git pull --ff-only` antes de instalar.
- `iniciar-bot.bat -Desinstalar`: detiene el bot y quita la tarea; conserva `Stories/` y
  `Evaluations/`.

La tarea corre en la sesión del usuario, así que la PC debe quedar encendida y con la sesión
iniciada. El resto de este documento describe la instalación manual.

## Preparar el equipo

Instala **Python 3.12 o 3.15 de 64 bits**, con el lanzador `py`, y copia o clona el
repositorio completo en su ubicación definitiva. Se ha comprobado con Python
3.12.10 y 3.15.0; `setup.ps1` comprueba la versión mayor/menor y la arquitectura.
Sin `-Python` prefiere 3.12 y, si falta, usa 3.15.
Necesitas Internet para descargar las dependencias y para usar Telegram y los
proveedores de generación/audio.

No copies `.venv`: contiene rutas de la PC original y se debe recrear en destino
([documentación de Python](https://docs.python.org/3.12/library/venv.html)).

Desde PowerShell, situado en la raíz del proyecto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -Telegram
```

El instalador crea `.venv` si falta, instala los cuatro paquetes locales del bot,
comprueba dependencias e imports, crea `Stories/` y `Evaluations/`, y copia
`.env.example` a `.env` solo si este no existe. No inicia el bot. Puede repetirse
para sincronizar el entorno tras actualizar el código. Si el Python existente está
roto o se copió desde otra PC, renombra esa `.venv` y repite la instalación.
Con `-Python C:\ruta\python.exe` puedes indicar el intérprete al crearla.
Sin `-Telegram` instala también consola, Studio y herramientas de desarrollo.

`requirements.txt` instala todas las aplicaciones; `requirements-telegram.txt`
solo las necesarias para el bot. Las restricciones van por versión:
`constraints-py312.txt` y `constraints-py315.txt` fijan las versiones directas y
transitivas del entorno comprobado en cada una, sin rutas personales. Los
`requirements*.txt` citan el de 3.12; con 3.15, `setup.ps1` instala una copia temporal
que cita el suyo. 3.15 necesita versiones más nuevas de `pydantic`, `aiohttp` y otras,
porque las de 3.12 no publican ruedas para 3.15. La suite entera pasa con las dos.
Las restricciones no instalan paquetes por sí solas
([documentación de pip](https://pip.pypa.io/en/stable/user_guide/#constraints-files)).
No es una actualización automática a las últimas versiones: para cambiar versiones,
actualiza las restricciones y vuelve a probar una instalación limpia y `quality.ps1`.

## Configuración y datos

Completa `.env` con `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ACCESS_KEY`, `GEMINI_API_KEY` y
`ASG_EVALUATION_STUDY`. El resto de opciones está en [README.md](README.md).
Deja `ASG_PROJECT_ROOT` vacío o apunta a la nueva raíz, nunca a una ruta de la otra PC.
No subas `.env` al repositorio.

Para continuar el estudio existente, detén el bot original y copia también
**`Stories/` y `Evaluations/` completas**, incluida la cola
`Stories/telegram_queue.sqlite3` y la base del estudio. Git no incluye esos datos.
Conserva una copia de respaldo. Las bases pueden guardar rutas absolutas de los
relatos: conserva la misma unidad/ruta que en origen, o adapta esas referencias
antes de continuar; copiar las carpetas a otra ruta no basta. No crees otro estudio
encima de la base existente.

Solo para un estudio nuevo, el comando tiene esta forma (elige la versión de
pipeline del experimento; la actual está en `packages/stagecraft/src/asg_stagecraft/version.py`):

```powershell
.\.venv\Scripts\evaluation-study.exe --db Evaluations/tesis-final/study.sqlite3 create tesis-final --version 7.10
```

En `.env`, usa `ASG_EVALUATION_STUDY=Evaluations/tesis-final/study.sqlite3`.

Prueba el arranque manual desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m asg_telegram.app
```

Comprueba `/start` desde Telegram y detén la prueba con Ctrl+C antes de configurar
el arranque automático. Usa una sola instancia para el mismo token; detén la de
la PC original al hacer el cambio.

## Mantenerlo funcionando

En el **Programador de tareas** de Windows, crea una tarea para el bot:

- Ejecutar tanto si el usuario inició sesión como si no, con una cuenta que pueda
  leer el proyecto y escribir sus datos.
- Desencadenador: al iniciar el sistema, con un minuto de retraso.
- Programa: ruta completa a `PROYECTO\.venv\Scripts\python.exe`.
- Argumentos: `-u -m asg_telegram.app`.
- Iniciar en: ruta completa de la raíz del proyecto.
- Reiniciar si falla cada minuto, hasta 999 intentos, y no iniciar una segunda
  instancia si ya está ejecutándose.
- Desactivar el límite «Detener la tarea si se ejecuta durante más de…» y la
  condición de ejecutar solo si el equipo está inactivo.

El límite predeterminado del Programador es de 72 horas, por eso hay que quitarlo
([configuración de tareas de Microsoft](https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings)).
Usa el módulo `asg_telegram.app`: el lanzador `asg-telegram` abre otra ventana y
termina, lo que impide que el Programador supervise el proceso real.

Mantén el equipo encendido, con Internet, y desactiva la suspensión automática
mientras esté enchufado. Reinicia Windows una vez y verifica que `/start` responde
sin abrir el bot a mano. Revisa el historial de la tarea si no responde; para ver
el error, detén la tarea y arranca manualmente desde PowerShell.
La instalación no registra tareas ni cambia ajustes de energía por su cuenta.
Haz copias periódicas de los datos con el bot detenido.

## Cola por cuota y transferencia del estudio

Para este despliegue usa [ROLLING_STUDY.md](ROLLING_STUDY.md): explica cómo importar las
tres semillas, abrir un estudio `rolling`, configurar los administradores y la publicación
en GitHub, y descargar un ZIP privado del estudio desde Telegram. No copies una base
administrativa dentro de `story-pool/`.

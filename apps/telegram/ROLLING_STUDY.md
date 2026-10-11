# Estudio creciente y traslado de datos

Este modo se activa al crear un estudio con `--mode rolling`. Los estudios existentes
conservan el protocolo fijo; sus migraciones no cambian la muestra ni los votos.
Antes de actualizar, detén el bot y conserva una copia de sus datos. Al abrir una base
antigua se crea además una copia SQLite consistente `*.vN.bak` antes de migrarla.

## Arrancar en la PC que sirve el bot

Actualiza el código e instala los requisitos de Telegram como indica
[DEPLOYMENT.md](DEPLOYMENT.md). Usa una sola instancia del bot.

El paquete privado `historias-semilla.zip` contiene tres relatos completos del corpus:
El mensaje en la botella, El legado de la casa y El maletín desaparecido en el tren de la
nieve. Incluye procedencia para el análisis; no debe copiarse al directorio público.
Tras recibir ese archivo, ejecuta desde la raíz, usando directorios nuevos:

```powershell
.\.venv\Scripts\evaluation-study.exe --db Evaluations/telegram-rolling/study.sqlite3 create telegram-rolling --version 7.10.0 --mode rolling
.\.venv\Scripts\evaluation-study.exe --db Evaluations/telegram-rolling/study.sqlite3 seed-bundle historias-semilla.zip Evaluations/telegram-rolling/semillas
.\.venv\Scripts\evaluation-study.exe --db Evaluations/telegram-rolling/study.sqlite3 collect
```

`--version` registra la versión de referencia del experimento. El modo creciente admite
relatos de otras versiones y conserva su procedencia; no equivale a una comparación
controlada entre versiones. No conviertas un estudio fijo ya iniciado.

Configura en el `.env` del servidor:

```dotenv
ASG_EVALUATION_STUDY=Evaluations/telegram-rolling/study.sqlite3
TELEGRAM_ADMIN_IDS=123456789
STORY_POOL_REPOSITORY=PROPIETARIO/REPOSITORIO
STORY_POOL_BRANCH=main
STORY_POOL_TOKEN=
```

Sustituye el ID por tu identificador **numérico de Telegram**, no por tu nombre de
usuario. Puedes incluir varios administradores separados por comas. También necesitan
haber entrado al bot con la clave compartida. Sin administradores no se pueden descargar
datos ni aprobar publicaciones.

Para publicar, usa un token de GitHub limitado a ese repositorio con permiso
**Contents: read and write**, guardado solo en el servidor. La rama debe existir y
permitir los commits de esa identidad. Configura un repositorio público si quieres
descargas públicas. El bot no cambia la visibilidad del repositorio ni fuerza pushes.
Sin repositorio o token la sincronización queda desactivada; las aprobaciones se conservan.
No hace falta compartir el token para descargar archivos públicos.

## Cola y apertura automática

Después de aceptar participar y guardar el perfil, todos pueden preparar su idea.
La solicitud confirmada entra en la cola. Se prioriza la primera aportación, después
los reemplazos y finalmente las historias de uso libre, con orden FIFO dentro de cada grupo.

Solo se genera una historia a la vez. El bot consulta el registro persistente de cuotas
y mantiene las solicitudes cuando un modelo está agotado. La disponibilidad es una
estimación local por modelo: otros clientes que compartan cuota pueden agotarla antes.
Los límites por minuto siguen controlados por el proveedor; no se consume una llamada
de prueba para averiguar si hay cuota.

Ante un agotamiento durante la generación, el intento se conserva y se vuelve a generar
desde el principio cuando haya capacidad. `/cancel` también cancela una solicitud en espera
de cuota. `/start` muestra posición y motivo de espera. No hace falta reenviar la idea.

La votación se abre con ocho primeras aportaciones completas de usuarios distintos.
Las tres semillas, los reemplazos y las historias libres no cuentan. No se exigen líneas
base. El investigador marcado con `--author` tampoco cuenta para ese umbral.

El pool continúa creciendo. Cada sesión se asigna al comenzar con hasta cinco relatos
desconocidos y ajenos, favoreciendo los de menor cobertura. Hay como máximo dos sesiones
y treinta decisiones por lector. Una sesión iniciada conserva su asignación; los relatos
nuevos se consideran al comenzar otra sesión. Un reemplazo no altera textos ni votos
anteriores. Si faltan dos relatos elegibles, `/evaluar` informa de la espera.

## Publicación pública durante el estudio

El consentimiento de publicación es independiente y opcional. Se ofrece tras el perfil y
se puede consultar o cambiar con `/publicacion`. Rechazarlo no impide participar.

Como administrador, desde un chat privado:

1. `/publicaciones_pendientes`: lista textos autorizados pendientes de revisión.
2. `/revisar_historia ID`: entrega el texto y un comando de aprobación ligado a su huella.
3. Ejecuta ese `/aprobar_historia ID HUELLA` después de revisar el contenido.

Las semillas seleccionadas por el investigador también necesitan aprobación.
Solo se publican el texto, un código neutro y su huella. No se publican votos,
identificadores de Telegram, prompts, versiones, opciones ni bases SQLite.
Cada publicación modifica el manifiesto y los textos en un mismo commit. Las caídas,
conflictos de rama o permisos insuficientes dejan reintentos pendientes con espera creciente,
sin detener el estudio.

Los participantes pueden haber leído textos públicos: el botón «Ya conocía esta historia»
permite excluirlos. Los informes conservan las exclusiones. Revocar permiso retira las
publicaciones aún pendientes; no borra copias públicas o el historial de Git.

En esta PC, `git pull --ff-only` recupera los textos públicos bajo `story-pool/`.
Los datos privados se descargan por separado.

## Descargar e importar resultados

Ejecuta `/exportar_estudio` como administrador, en privado. Descarga el ZIP; si recibes
archivos `estudio.zip.part0001`, `part0002`, etc., guárdalos **todos** en la misma carpeta.

```powershell
.\.venv\Scripts\evaluation-study.exe import-bundle Descargas/estudio.zip Evaluations/estudio-descargado
# Para un archivo dividido:
.\.venv\Scripts\evaluation-study.exe import-bundle Descargas/estudio.zip.part0001 Evaluations/estudio-descargado
```

El destino debe ser nuevo. El importador verifica huellas, reconstruye los relatos y crea
`study.sqlite3` con rutas locales para las herramientas de análisis existentes. Conserva
seudónimos, versiones, asignaciones, lecturas, votos, exposiciones y revisiones de sesión.
No restaura identidades de Telegram ni credenciales: esta copia es para análisis, no para
reemplazar el servidor del bot.

También puedes exportar desde la consola del servidor:

```powershell
.\.venv\Scripts\evaluation-study.exe --db Evaluations/telegram-rolling/study.sqlite3 export-bundle estudio.zip
```

El ZIP contiene textos y procedencia de investigación, aunque los participantes no hayan
autorizado publicación pública. Guárdalo en privado. Para cerrar la recogida y votación,
usa `evaluation-study --db RUTA close`; no se inscriben más aportaciones después del cierre.

Referencias de integración: [GitHub Git database API](https://docs.github.com/en/rest/git)
y [Telegram Bot API](https://core.telegram.org/bots/api#senddocument).

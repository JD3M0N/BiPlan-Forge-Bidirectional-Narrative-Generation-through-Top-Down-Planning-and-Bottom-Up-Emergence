# Como correr el proyecto y generar una historia

## Arranque automatico

Si quieres que el proyecto se monte casi solo, desde la raiz ejecuta:

```powershell
cd e:\University\thesis
.\RUN_PROJECT.ps1
```

Si quieres forzar reinstalacion de dependencias:

```powershell
.\RUN_PROJECT.ps1 -ReinstallDependencies
```

Si quieres que ademas abra el navegador:

```powershell
.\RUN_PROJECT.ps1 -OpenBrowser
```

## 1. Requisitos

- Node.js 22 o superior
- Python 3.12 o superior
- Una API key de Gemini

## 2. Configurar el backend

1. Abre una terminal en la raiz del proyecto:

```powershell
cd e:\University\thesis
```

2. Crea un entorno virtual dentro de `backend`:

```powershell
cd backend
python -m venv .venv
```

3. Activa el entorno virtual:

```powershell
.\.venv\Scripts\Activate.ps1
```

Si tu entorno crea la carpeta `bin` en vez de `Scripts`, usa:

```powershell
.\.venv\bin\Activate.ps1
```

4. Instala las dependencias Python:

```powershell
pip install -r ..\requirements.txt
pip install -e .
```

Si ya habias instalado dependencias antes y te sale un error sobre `python-dotenv`, repite ese paso para actualizar el entorno.

5. Crea el archivo de entorno del backend:

```powershell
Copy-Item .env.example .env
```

6. Edita `backend/.env` y deja al menos estas variables:

```env
APP_NAME=Story Writers
DATABASE_URL=sqlite:///./story_writers.db
JWT_SECRET=una-clave-larga-y-segura-de-al-menos-32-caracteres
JWT_EXPIRE_MINUTES=1440
FRONTEND_ORIGIN=http://localhost:3000
LOG_LEVEL=INFO
LOG_DIR=logs
GEMINI_API_KEY=tu_api_key_de_gemini
GEMINI_MODEL=gemini-2.0-flash
GEMINI_MAX_RETRIES=3
GEMINI_RETRY_BASE_SECONDS=2.0
GEMINI_MIN_REQUEST_INTERVAL_SECONDS=3.2
```

7. Inicia el backend:

```powershell
uvicorn app.main:app --reload --port 8000
```

Deja esta terminal abierta.

## 3. Configurar el frontend

1. Abre una segunda terminal en la raiz del proyecto:

```powershell
cd e:\University\thesis\frontend
```

2. Instala las dependencias de Node:

```powershell
npm install
```

3. Crea el archivo de entorno del frontend:

```powershell
Copy-Item .env.example .env.local
```

4. Verifica que `frontend/.env.local` tenga esta URL:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

5. Inicia el frontend:

```powershell
npm run dev
```

Deja esta terminal abierta.

## 4. Abrir la aplicacion

1. En el navegador abre:

```text
http://localhost:3000
```

2. Veras la pantalla de autenticacion.

3. Crea una cuenta con correo y contrasena.

## 5. Generar una historia

1. En el compositor principal agrega uno o mas personajes.
2. Completa:
   - `Nombre`
   - `Rol`
   - `Descripcion`
3. Escribe el `Estilo`.
4. Elige la `Longitud`.
5. Escribe la `Trama`.
6. Selecciona el idioma.
7. Pulsa `Generar historia`.

## 6. Que pasa al generar

- La historia se guarda automaticamente en SQLite.
- El backend lanza el pipeline multiagente:
  - Architect
  - World Builder
  - Drama Coach
  - Dependency Manager
  - Narrator
- Cuando termine, la historia aparecera en la biblioteca lateral.

## 7. Leer la historia

1. Mira la biblioteca del panel izquierdo.
2. Cuando el estado pase a `completed`, haz clic en la historia.
3. Se abrira el lector con el texto final.

## 8. Si algo falla

- Si el estado queda en `failed`, abre la historia para ver el error.
- Si Gemini no responde, revisa `GEMINI_API_KEY` en `backend/.env`.
- Si quieres revisar auditoria y ejecucion del backend, mira:

```text
backend/logs/audit.log
backend/logs/app.log
```

- `audit.log` registra eventos como registro, login y creacion de historias.
- `app.log` registra worker, agentes, reintentos y errores del backend.
- Si el frontend no conecta con el backend, revisa:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
FRONTEND_ORIGIN=http://localhost:3000
```

## 9. Comandos utiles

### Probar backend

```powershell
cd e:\University\thesis\backend
.\.venv\bin\pytest.exe
```

### Probar frontend

```powershell
cd e:\University\thesis\frontend
npm test
```

### Build del frontend

```powershell
cd e:\University\thesis\frontend
npm run build
```

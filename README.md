# Generador de Historias Multiagente

Monorepo local para generar historias en espanol con una interfaz web minimalista y un backend multiagente en Python.

## Estructura

- `frontend/`: app web en Next.js con autenticacion, biblioteca y lector.
- `backend/`: API FastAPI con SQLite, worker local y pipeline multiagente.

## Requisitos

- Node.js 22+
- Python 3.12+

## Variables de entorno

### Frontend

Copia `frontend/.env.example` a `frontend/.env.local` y ajusta:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### Backend

Copia `backend/.env.example` a `backend/.env` y ajusta:

```env
APP_NAME=Story Writers
DATABASE_URL=sqlite:///./story_writers.db
JWT_SECRET=<your-secret>
JWT_EXPIRE_MINUTES=1440
FRONTEND_ORIGIN=http://localhost:3000
LOG_LEVEL=INFO
LOG_DIR=logs
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
GEMINI_MAX_RETRIES=3
GEMINI_RETRY_BASE_SECONDS=2.0
GEMINI_MIN_REQUEST_INTERVAL_SECONDS=3.2
```

Si `GEMINI_API_KEY` no esta configurada, las solicitudes de generacion fallaran de forma controlada y la historia quedara marcada como `failed`.

## Arranque local

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Pruebas

### Backend

```bash
cd backend
pytest
```

### Frontend

```bash
cd frontend
npm test
```

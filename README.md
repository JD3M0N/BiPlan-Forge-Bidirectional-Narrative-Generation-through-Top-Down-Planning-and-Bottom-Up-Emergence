# Automatic Story Generation

Sistema modular de generación automática de historias (ASG). La primera
implementación utiliza planificación **Top-Down** y agentes especializados que
se comunican mediante artefactos validados.

## Instalación

Requiere Python 3.11 o posterior.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e "Models/Top-Down[dev]"
Copy-Item .env.example .env
```

Escribe tu clave en `.env`:

```dotenv
GEMINI_API_KEY=tu_clave
GEMINI_MODEL=gemini-2.5-flash
```

`.env` está ignorado por Git. Nunca añadas una clave real a `.env.example`.

## Uso

Desde la raíz del repositorio:

```powershell
generate-story
```

La aplicación pedirá un único prompt. Un prompt útil especifica género,
protagonista, conflicto, ambientación, tono y extensión, por ejemplo:

> Escribe un relato de ciencia ficción de unas 1800 palabras. Una cartógrafa
> descubre que las estrellas están cambiando de posición para formar un
> mensaje. Tono melancólico, ambientado en una estación orbital decadente y
> con un final esperanzador.

Cuando falten idioma o extensión se usarán español y unas 1500 palabras. Cada
ejecución crea una carpeta independiente en `Stories/Top-Down` con la historia,
el borrador y todos los artefactos de planificación y revisión.

## Desarrollo

```powershell
python -m pytest Models/Top-Down/tests
```

El proveedor de lenguaje está definido mediante un protocolo. Los tests usan
un proveedor simulado y no consumen la API de Gemini.


# Prompt-crafter

Agente independiente que transforma una idea narrativa breve en tres prompts
enriquecidos y recomienda el enfoque más sólido. No ejecuta Top-Down ni guarda
resultados.

## Terminal

Configura `GEMINI_API_KEY` y, opcionalmente, `GEMINI_MODEL` en el `.env` raíz:

```powershell
craft-prompt
```

## API Python

```python
from asg_prompt_crafter import PromptCrafterAgent
from asg_prompt_crafter.config import load_settings
from asg_prompt_crafter.provider import GeminiProvider

settings = load_settings()
provider = GeminiProvider(settings.api_key, settings.model)
result = PromptCrafterAgent(provider).craft(
    "Dame una historia de un caballero que salva a una princesa de un dragón."
)

print(result.recommended_id)
for alternative in result.alternatives:
    print(alternative.name, alternative.prompt)
```

`CraftResult` conserva la solicitud original, contiene exactamente tres
alternativas con identificadores únicos y garantiza que la recomendación
señale una de ellas.

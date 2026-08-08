from .base import Agent
from ..schemas import StoryRequest


class AnalystAgent(Agent[StoryRequest]):
    name = "analyst"

    def run(self, prompt: str) -> StoryRequest:
        return self.provider.generate_structured(
            system_instruction=(
                "Eres analista de requisitos narrativos. Convierte la petición en una "
                "especificación fiel. Si no indica idioma usa español; si no indica "
                "extensión usa 1500 palabras. No inventes restricciones."
            ),
            prompt=prompt,
            schema=StoryRequest,
        )

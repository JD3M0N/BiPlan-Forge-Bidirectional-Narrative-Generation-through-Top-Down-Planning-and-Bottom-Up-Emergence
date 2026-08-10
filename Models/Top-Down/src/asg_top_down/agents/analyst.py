import re

from .base import Agent
from ..schemas import StoryRequest


class AnalystAgent(Agent[StoryRequest]):
    name = "analyst"

    def __init__(self, provider, default_target_words: int = 1500) -> None:
        super().__init__(provider)
        self.default_target_words = default_target_words

    def run(self, prompt: str) -> StoryRequest:
        request = self.provider.generate_structured(
            system_instruction=(
                "Eres analista de requisitos narrativos. Convierte la petición en una "
                "especificación fiel. Si no indica idioma usa español; si no indica "
                f"extensión usa {self.default_target_words} palabras. Una extensión "
                "indicada explícitamente por el usuario siempre tiene prioridad. "
                "No inventes restricciones."
            ),
            prompt=prompt,
            schema=StoryRequest,
        )
        match = re.search(
            r"(?<!\d)(\d[\d.,_ ]*)\s*(?:palabras?|words?)\b",
            prompt,
            flags=re.IGNORECASE,
        )
        target_words = self.default_target_words
        if match:
            target_words = int(re.sub(r"[^\d]", "", match.group(1)))
        return StoryRequest.model_validate({
            **request.model_dump(), "target_words": target_words,
        })

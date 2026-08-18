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
                "You are a narrative requirements analyst. Convert the user's request into a "
                "faithful specification. Preserve every explicit constraint. If no language is "
                f"given, use Spanish; if no length is given, use {self.default_target_words} words. "
                "An explicitly requested length always takes priority. Write title, genre, tone, "
                "premise, and normalized constraints in English; keep original_prompt verbatim and "
                "set language to the requested fiction language. Do not invent constraints."
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

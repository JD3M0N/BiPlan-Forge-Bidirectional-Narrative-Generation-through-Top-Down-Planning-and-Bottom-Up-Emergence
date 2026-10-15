"""The localizer: translates the few reader-facing fields that leaked out in English (7.14).

It never sees prose. The plan stays in English on purpose and the actors and the narrator
write in the fiction's language; what this agent fixes is the short text between the two -
chapter titles, the printed script's labels, a character's role - that writing/language.py
flags as being in the wrong language. One structured call per artifact, only when something
was flagged.
"""

from pydantic import BaseModel, ConfigDict, Field

from .base import Agent, json_text


class LocalizedText(BaseModel):
    """One field, by the key the pipeline gave it, and its text."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    text: str = Field(min_length=1)


class LocalizedTexts(BaseModel):
    """The translated fields, one per key the localizer was given."""

    model_config = ConfigDict(extra="forbid")

    items: list[LocalizedText] = Field(default_factory=list)


class LocalizerAgent(Agent[LocalizedTexts]):
    """Translate a handful of short fields into the story's language."""

    name = "localizer"

    def run(self, texts: dict[str, str], language: str, cast: str = "") -> LocalizedTexts:
        """Return every key of texts with its text written in language."""
        items = [{"key": key, "text": text} for key, text in texts.items()]
        return self.provider.generate_structured(
            system_instruction=(
                f"You are a literary translator into {language}. Translate each text into "
                f"natural {language}, as a native editor would title or label it, keeping its "
                "length and tone. Keep personal and place names exactly as they are. Where a "
                "role or title names a person, use the gender the cast below gives them. "
                "Return every key you were given, unchanged, each with its translated text."
            ),
            prompt=(f"CAST:\n{cast}\n\n" if cast else "") + f"TEXTS:\n{json_text(items)}",
            schema=LocalizedTexts,
            profile="extraction",
        )

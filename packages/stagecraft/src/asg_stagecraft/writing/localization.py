"""The language boundary of a run: reader-facing fields that leaked out in English (7.14).

The pipeline mixes it in. A field writing/language.py flags is sent to the localizer; what it
translates replaces the field, and every replacement is kept in localization.json with the
original, so a finished run shows what was rewritten. A run with nothing flagged makes no call
and writes no artifact. If the localizer cannot answer, a chapter title falls back to a
numbered one, as the adaptive mode already does, and the other fields keep their text.
"""

from __future__ import annotations

from ..agents.localizer import LocalizerAgent
from ..runtime.errors import NON_DEGRADABLE_ERRORS
from ..schemas import (
    CharactersArtifact,
    ScriptPresentation,
    StoryPresentation,
    StoryRequest,
)
from .language import is_foreign, language_code

LOCALIZATION_ARTIFACT = "localization.json"
# The numbered title a chapter falls back to, per language this module can judge.
_CHAPTER_WORD = {"es": "Capítulo", "en": "Chapter"}


class LocalizationMixin:
    """Translate the reader-facing fields that came back in the wrong language."""

    def _localize(
        self, request: StoryRequest, texts: dict[str, str], characters: CharactersArtifact
    ) -> dict[str, str]:
        """Return a translation for every flagged text the localizer could translate."""
        flagged = {key: text for key, text in texts.items() if is_foreign(text, request.language)}
        if not flagged:
            return {}
        cast = "\n".join(
            f"- {item.name}: {item.role}" for item in characters.characters if item.name
        )
        try:
            answer = self._call_agent(
                "localizer",
                lambda: LocalizerAgent(self.provider).run(flagged, request.language, cast),
            )
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception as exc:
            self._record_localization(flagged, {}, failure=type(exc).__name__)
            return {}
        translated = {
            item.key: item.text.strip()
            for item in answer.items
            if item.key in flagged
            and item.text.strip()
            and not is_foreign(item.text, request.language)
        }
        self._record_localization(flagged, translated)
        return translated

    def _record_localization(
        self, flagged: dict[str, str], translated: dict[str, str], failure: str = ""
    ) -> None:
        """Append one localization round to localization.json and warn about what failed."""
        assert self.repository is not None
        records = getattr(self, "_localization_records", None)
        if records is None:
            records = self._localization_records = []
        records.extend(
            {
                "key": key,
                "original": text,
                "localized": translated.get(key, ""),
                "status": "localized" if key in translated else "kept",
            }
            for key, text in flagged.items()
        )
        self.repository.save_data(LOCALIZATION_ARTIFACT, {"contract": 1, "fields": records})
        missing = len(flagged) - len(translated)
        if missing:
            reason = f" ({failure})" if failure else ""
            warning = f"{missing} campos siguen fuera del idioma de la historia{reason}."
            self.repository.add_warning(f"[LOCALIZATION_FALLBACK] {warning}")
            self._emit("localization_fallback", warning, stage=self.progress["stage"])

    def _localized_characters(
        self, request: StoryRequest, characters: CharactersArtifact
    ) -> CharactersArtifact:
        """Translate the roles a reader may see that came back in the wrong language."""
        texts = {f"role:{item.id}": item.role for item in characters.characters if item.role}
        translated = self._localize(request, texts, characters)
        if not translated:
            return characters
        return characters.model_copy(
            update={
                "characters": [
                    item.model_copy(update={"role": translated.get(f"role:{item.id}", item.role)})
                    for item in characters.characters
                ]
            }
        )

    def _localized_presentation(
        self,
        request: StoryRequest,
        presentation: StoryPresentation,
        characters: CharactersArtifact,
    ) -> StoryPresentation:
        """Translate titles and, for a script, its printed frame, numbering what stays foreign."""
        texts = {"title": presentation.title}
        texts |= {f"chapter:{item.chapter_id}": item.title for item in presentation.chapters}
        frame = getattr(presentation, "frame", None)
        if isinstance(presentation, ScriptPresentation) and frame is not None:
            texts |= {
                "frame:cast_heading": frame.cast_heading,
                "frame:act_label": frame.act_label,
                "frame:scene_label": frame.scene_label,
            }
            texts |= {f"cast:{note.character_id}": note.description for note in frame.cast}
        translated = self._localize(request, texts, characters)
        word = _CHAPTER_WORD.get(language_code(request.language), "")

        def chapter_title(index: int, chapter_id: str, title: str) -> str:
            """Pick the translated title, a numbered one if it stayed foreign, or the original."""
            key = f"chapter:{chapter_id}"
            if key in translated:
                return translated[key]
            if word and is_foreign(title, request.language):
                return f"{word} {index}"
            return title

        update: dict = {
            "title": translated.get("title", presentation.title),
            "chapters": [
                item.model_copy(update={"title": chapter_title(index, item.chapter_id, item.title)})
                for index, item in enumerate(presentation.chapters, 1)
            ],
        }
        if isinstance(presentation, ScriptPresentation) and frame is not None:
            update["frame"] = frame.model_copy(
                update={
                    name: translated.get(f"frame:{name}", getattr(frame, name))
                    for name in ("cast_heading", "act_label", "scene_label")
                }
                | {
                    "cast": [
                        note.model_copy(
                            update={
                                "description": translated.get(
                                    f"cast:{note.character_id}", note.description
                                )
                            }
                        )
                        for note in frame.cast
                    ]
                }
            )
        return presentation.model_copy(update=update)

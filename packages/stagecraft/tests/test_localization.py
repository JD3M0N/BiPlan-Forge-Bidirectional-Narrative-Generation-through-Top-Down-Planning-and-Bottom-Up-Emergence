"""7.14: reader-facing fields that leak out in English are caught in code and localized."""

import json

import pytest
from asg_stagecraft import StoryGenerator
from asg_stagecraft.agents.localizer import LocalizedText, LocalizedTexts
from asg_stagecraft.schemas import ChapterPresentation, StoryPresentation
from asg_stagecraft.writing.language import is_foreign
from test_generator_v5 import FakeProvider


@pytest.mark.parametrize(
    ("text", "language", "foreign"),
    [
        # The three chapter titles of the 7.13 navigators run.
        ("Arrival and Discovery", "Spanish", True),
        ("Secrets of the Harps and Roots", "Spanish", True),
        ("The Final Descent", "Spanish", True),
        ("Los secretos de las arpas", "Spanish", False),
        # A name or a lone noun carries no grammar to judge by.
        ("Zéfara", "Spanish", False),
        ("protagonist", "Spanish", False),
        ("El archivo de la ciudad", "English", True),
        # A language this module cannot judge is never flagged.
        ("The Final Descent", "French", False),
    ],
)
def test_a_foreign_text_is_told_by_its_function_words(text, language, foreign) -> None:
    assert is_foreign(text, language) is foreign


class LeakingProvider(FakeProvider):
    """Return one chapter title in English and translate it when asked."""

    def __init__(self, *, translate: bool) -> None:
        super().__init__()
        self.translate = translate

    def generate_structured(self, *, system_instruction, prompt, schema, profile):
        if schema is StoryPresentation:
            self.structured_calls.append((schema.__name__, system_instruction, prompt))
            return StoryPresentation(
                title="El precio de la verdad",
                chapters=[
                    ChapterPresentation(chapter_id="chapter-1", title="The Final Descent"),
                    ChapterPresentation(chapter_id="chapter-2", title="La elección"),
                ],
            )
        if schema is LocalizedTexts:
            self.structured_calls.append((schema.__name__, system_instruction, prompt))
            if not self.translate:
                raise RuntimeError("localizer unavailable")
            return LocalizedTexts(
                items=[LocalizedText(key="chapter:chapter-1", text="El descenso final")]
            )
        return super().generate_structured(
            system_instruction=system_instruction, prompt=prompt, schema=schema, profile=profile
        )


@pytest.mark.parametrize(
    ("translate", "title", "status"),
    [(True, "El descenso final", "localized"), (False, "Capítulo 1", "kept")],
    ids=["translated", "numbered-when-the-localizer-fails"],
)
def test_a_leaked_title_is_localized_or_numbered(tmp_path, translate, title, status) -> None:
    provider = LeakingProvider(translate=translate)
    run = StoryGenerator(provider, tmp_path).generate("Una historia")
    story = (run.run_dir / "story.md").read_text(encoding="utf-8")
    assert f"## {title}" in story and "The Final Descent" not in story
    record = json.loads((run.run_dir / "localization.json").read_text(encoding="utf-8"))
    assert [(item["key"], item["status"]) for item in record["fields"]] == [
        ("chapter:chapter-1", status)
    ]
    # Only the flagged field travels to the localizer: Spanish titles cost nothing.
    localizer = [
        prompt for name, _, prompt in provider.structured_calls if name == "LocalizedTexts"
    ]
    assert len(localizer) == 1 and "La elección" not in localizer[0]
    warnings = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))["warnings"]
    assert any(item.startswith("[LOCALIZATION_FALLBACK]") for item in warnings) is not translate

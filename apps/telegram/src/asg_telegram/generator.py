"""Thin adapter over Stagecraft; the only bot module that imports ``asg_stagecraft``."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from asg_stagecraft import CastMember, GenerationOptions, StoryBrief, StoryGenerator
from asg_stagecraft.brief import MAX_CAST as MAX_CAST
from asg_stagecraft.brief import PRONOUN_LABELS, ROLE_LABELS
from asg_stagecraft.runtime.config import load_settings
from asg_stagecraft.runtime.errors import ASGError, RunCancelledError
from asg_stagecraft.runtime.provider import provider_from_settings
from pydantic import ValidationError

# The two approaches a participant can pick, by the story format that implements each.
METHODS = {"narrative": "Top-Down", "simulated": "Híbrido"}
BRIEF_LIMITS = {
    "title": 120,
    "genre": 80,
    "setting": 400,
    "plot": 4000,
    "notes": 1500,
    "name": 80,
    "description": 600,
    "secret": 400,
}
ROLES = tuple(ROLE_LABELS.items())
PRONOUNS = tuple(PRONOUN_LABELS.items())
QUOTA_CODES = {
    "GEMINI_DAILY_QUOTA_EXHAUSTED",
    "PROVIDER_DAILY_QUOTA_EXHAUSTED",
    "GEMINI_RPM_EXHAUSTED",
    "GEMINI_TPM_EXHAUSTED",
    "GEMINI_BILLING_LIMIT_EXHAUSTED",
}

Progress = Callable[[int, str], None]


class GeneratorUnavailable(RuntimeError):
    """The generator cannot start, usually because of its configuration."""


class GenerationFailure(Exception):
    """A failure whose summary can be shown to the participant as it stands."""

    def __init__(self, summary: str, *, quota: bool = False) -> None:
        """Keep the safe summary and whether the provider ran out of quota."""
        super().__init__(summary)
        self.summary = summary
        self.quota = quota


class GenerationCancelled(GenerationFailure):
    """The participant cancelled the run."""


@dataclass(frozen=True)
class StoryOutline:
    """A guided story: plot, optional framing and a cast, as the wizard collected it."""

    plot: str
    title: str = ""
    genre: str = ""
    setting: str = ""
    cast: tuple[dict, ...] = field(default_factory=tuple)
    notes: str = ""

    def to_dict(self) -> dict:
        """Serialize the outline for the durable job queue."""
        return {**asdict(self), "cast": [dict(member) for member in self.cast]}

    @classmethod
    def from_dict(cls, data: dict) -> StoryOutline:
        """Rebuild an outline stored by the job queue."""
        return cls(**{**data, "cast": tuple(data.get("cast", ()))})


def brief_from(outline: StoryOutline) -> StoryBrief:
    """Translate an outline into Stagecraft's structured brief, raising ValueError in Spanish."""
    try:
        return StoryBrief(
            plot=outline.plot,
            title=outline.title,
            genre=outline.genre,
            setting=outline.setting,
            cast=[CastMember(**member) for member in outline.cast],
            notes=outline.notes,
        )
    except ValidationError as exc:
        first = exc.errors()[0]
        message = str(first.get("msg", "no es válido"))
        message = message.removeprefix("Value error, ")
        where = ".".join(str(part) for part in first.get("loc", ()))
        raise ValueError(f"{where}: {message}" if where else message) from exc


class StagecraftGenerator:
    """Generate one story in prose with narration audio, Top-Down or hybrid."""

    def __init__(self) -> None:
        """Read the configuration once, so a broken setup fails at start-up."""
        try:
            self.settings = load_settings()
            self._provider = provider_from_settings(self.settings)
        except ASGError as error:
            raise GeneratorUnavailable(error.summary) from error
        self._options = GenerationOptions.from_settings(self.settings).with_changes(audio=True)

    def generate(
        self,
        request: str | StoryOutline,
        story_format: str,
        *,
        on_progress: Progress | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Path:
        """Run the pipeline and return the run directory, or raise GenerationFailure."""
        if story_format not in METHODS:
            raise GenerationFailure("Método desconocido.")
        try:
            story = brief_from(request) if isinstance(request, StoryOutline) else request
        except ValueError as exc:
            raise GenerationFailure(str(exc)) from exc
        options = self._options.with_changes(story_format=story_format)
        generator = StoryGenerator.from_options(self._provider, self.settings.output_root, options)
        try:
            return generator.generate(
                story,
                on_progress=(lambda u: on_progress(u.percent, u.description))
                if on_progress
                else None,
                should_cancel=should_cancel,
            ).run_dir
        except RunCancelledError as error:
            raise GenerationCancelled("Generación cancelada.") from error
        except ASGError as error:
            raise GenerationFailure(error.summary, quota=error.code in QUOTA_CODES) from error
        finally:
            # Each run already wrote its usage to disk; keeping it would only grow memory.
            self._provider.usage_records.clear()

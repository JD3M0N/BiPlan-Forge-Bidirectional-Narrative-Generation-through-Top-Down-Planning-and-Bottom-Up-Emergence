"""Configuration loading for Stagecraft 7.x."""

import os
from dataclasses import dataclass
from pathlib import Path

from asg_core import find_project_root
from dotenv import load_dotenv

from ..formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
from .errors import ConfigurationError


@dataclass(frozen=True)
class Settings:
    """Represent Settings data and behavior."""

    api_key: str
    model: str
    output_root: Path
    rpm_limit: int = 15
    rpm_reserve: int = 1
    tpm_limit: int = 0
    max_retries: int = 3
    max_retry_delay: int = 120
    request_timeout_ms: int = 120_000
    narrative_guidance: bool = True
    promise_ledger: bool = True
    story_format: StoryFormat = StoryFormat.NARRATIVE
    script_method: ScriptMethod = ScriptMethod.NATIVE
    narrative_voice: NarrativeVoice = NarrativeVoice.OMNISCIENT
    actor_memory: ActorMemory = ActorMemory.OWN
    turns_per_beat: int = 8
    # The performance may run on its own model, key and RPM: Gemini counts the free daily quota
    # per project and per model, and the actors spend most of a simulated run's calls. Empty (or
    # 0) means the same as the main model, key and RPM, so an unset .env behaves as before 7.4.
    stage_model: str = ""
    stage_api_key: str = ""
    stage_rpm_limit: int = 0

    @property
    def effective_stage_model(self) -> str:
        """Return the model the performance runs on, falling back to the main one."""
        return self.stage_model or self.model

    @property
    def effective_stage_api_key(self) -> str:
        """Return the key the performance calls with, falling back to the main one."""
        return self.stage_api_key or self.api_key

    @property
    def effective_stage_rpm_limit(self) -> int:
        """Return the RPM the performance is paced at, falling back to the main one."""
        return self.stage_rpm_limit or self.rpm_limit

    @property
    def splits_stage(self) -> bool:
        """Say whether the performance runs on a model, key or pace of its own."""
        return (
            self.effective_stage_model != self.model
            or self.effective_stage_api_key != self.api_key
            or self.effective_stage_rpm_limit != self.rpm_limit
        )

    def model_summary(self, *, simulated: bool) -> str:
        """Name the model a run uses, and the performance's own when a simulated run has one."""
        if simulated and self.splits_stage:
            return f"{self.model} (función: {self.effective_stage_model})"
        return self.model


def _integer(name: str, default: int, *, minimum: int = 0) -> int:
    """Read an integer environment setting, treating unset or blank values as the default."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} debe ser un número entero.") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} debe ser al menos {minimum}.")
    return value


def _flag(name: str, *, default: bool) -> bool:
    """Read a boolean environment switch, treating unset values as the default."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


def _choice(name: str, enum_cls, default):
    """Read a named enum switch, treating an unset or invalid value as an error to name."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return enum_cls(raw.strip().casefold())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_cls)
        raise ConfigurationError(f"{name} debe ser uno de: {allowed}.") from exc


def load_settings(start: Path | None = None, *, require_api_key: bool = True) -> Settings:
    """Load settings from the environment and the root .env file.

    A surface that only shows options, such as StageCraft before its first run, passes
    require_api_key=False and gets an empty key instead of an error; generating still needs it.
    """
    root = find_project_root(start)
    load_dotenv(root / ".env")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key and require_api_key:
        raise ConfigurationError("Falta GEMINI_API_KEY. Añádela al archivo .env de la raíz.")
    return Settings(
        api_key=api_key,
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite",
        output_root=root / "Stories" / "Stagecraft",
        rpm_limit=_integer("GEMINI_RPM_LIMIT", 15, minimum=1),
        rpm_reserve=_integer("GEMINI_RPM_RESERVE", 1),
        tpm_limit=_integer("GEMINI_TPM_LIMIT", 0),
        max_retries=_integer("GEMINI_MAX_RETRIES", 3),
        max_retry_delay=_integer("GEMINI_MAX_RETRY_DELAY", 120, minimum=1),
        request_timeout_ms=_integer("GEMINI_REQUEST_TIMEOUT_MS", 120_000, minimum=5_000),
        narrative_guidance=_flag("ASG_NARRATIVE_GUIDANCE", default=True),
        promise_ledger=_flag("ASG_PROMISE_LEDGER", default=True),
        story_format=_choice("ASG_STORY_FORMAT", StoryFormat, StoryFormat.NARRATIVE),
        script_method=_choice("ASG_SCRIPT_METHOD", ScriptMethod, ScriptMethod.NATIVE),
        narrative_voice=_choice("ASG_NARRATIVE_VOICE", NarrativeVoice, NarrativeVoice.OMNISCIENT),
        actor_memory=_choice("ASG_ACTOR_MEMORY", ActorMemory, ActorMemory.OWN),
        turns_per_beat=_integer("ASG_STAGE_TURNS_PER_BEAT", 8, minimum=2),
        stage_model=os.getenv("GEMINI_STAGE_MODEL", "").strip(),
        stage_api_key=os.getenv("GEMINI_STAGE_API_KEY", "").strip(),
        stage_rpm_limit=_integer("GEMINI_STAGE_RPM_LIMIT", 0),
    )

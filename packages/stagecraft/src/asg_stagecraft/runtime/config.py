"""Configuration loading for Stagecraft 7.x."""

import os
from dataclasses import dataclass, replace
from pathlib import Path

from asg_core import find_project_root
from dotenv import load_dotenv

from ..formats import ActorMemory, NarrativeVoice, ScriptMethod, SimulationMode, StoryFormat
from .budget import QuotaSlot
from .errors import ConfigurationError

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
CHAIN_PROVIDERS = ("gemini", "groq", "mistral")


@dataclass(frozen=True)
class ChainEntry:
    """One slot of the provider chain: its quota slot, credentials, endpoint and pace.

    A Gemini entry leaves model and key empty: they are read from the settings when the chain
    is resolved, so --model and GEMINI_* keep applying to it.
    """

    slot: QuotaSlot
    api_key: str = ""
    base_url: str = ""
    rpm_limit: int = 15
    label: str = "Gemini"


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
    simulation_mode: SimulationMode = SimulationMode.FIXED
    inventory: bool = False
    turns_per_beat: int = 8
    # The performance may run on its own model, key and RPM: Gemini counts the free daily quota
    # per project and per model, and the actors spend most of a simulated run's calls. Empty (or
    # 0) means the same as the main model, key and RPM, so an unset .env behaves as before 7.4.
    stage_model: str = ""
    stage_api_key: str = ""
    stage_rpm_limit: int = 0
    # The ordered provider chain (ASG_LLM_CHAIN) and the ledger that keeps its spending.
    # Empty means the single Gemini provider every run before 7.7 used.
    chain: tuple[ChainEntry, ...] = ()
    budget_path: Path | None = None
    # Gemini's free daily requests, per model: two models (GEMINI_STAGE_MODEL) double the total.
    gemini_daily_requests: int = 500

    def resolved_chain(self) -> tuple[ChainEntry, ...]:
        """Return the chain with each Gemini slot bound to the main model, key and pace."""
        return tuple(
            replace(
                entry,
                slot=replace(entry.slot, model=self.model),
                api_key=self.api_key,
                rpm_limit=self.rpm_limit,
            )
            if entry.slot.provider == "gemini"
            else entry
            for entry in self.chain
        )

    @property
    def stage_chain_entry(self) -> ChainEntry | None:
        """Return the slot of the second Gemini model (GEMINI_STAGE_MODEL), if there is one."""
        gemini = next((e for e in self.chain if e.slot.provider == "gemini"), None)
        if gemini is None or not self.splits_stage:
            return None
        return replace(
            gemini,
            slot=replace(gemini.slot, model=self.effective_stage_model),
            api_key=self.effective_stage_api_key,
            rpm_limit=self.effective_stage_rpm_limit,
        )

    def quota_entries(self) -> list[ChainEntry]:
        """Return every slot a run may spend on, the second Gemini model right after the first.

        Without a chain these are the Gemini models a run uses, so the quota panel also serves
        a setup that never fails over.
        """
        if self.chain:
            entries = list(self.resolved_chain())
            stage = self.stage_chain_entry
        else:
            gemini = QuotaSlot(
                "gemini", self.model, "pacific_day", max_requests=self.gemini_daily_requests
            )
            entries = [ChainEntry(gemini, self.api_key, rpm_limit=self.rpm_limit)]
            stage = (
                ChainEntry(
                    replace(gemini, model=self.effective_stage_model),
                    self.effective_stage_api_key,
                    rpm_limit=self.effective_stage_rpm_limit,
                )
                if self.splits_stage
                else None
            )
        if stage is not None and stage.slot.key not in {entry.slot.key for entry in entries}:
            gemini = next(i for i, entry in enumerate(entries) if entry.slot.provider == "gemini")
            entries.insert(gemini + 1, stage)
        return entries

    @property
    def has_credentials(self) -> bool:
        """Say whether some provider has the key it needs to generate."""
        return bool(self.api_key) or any(
            entry.api_key for entry in self.chain if entry.slot.provider != "gemini"
        )

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
        main = " → ".join(e.slot.key for e in self.resolved_chain()) or self.model
        if simulated and self.splits_stage:
            return f"{main} (función: {self.effective_stage_model})"
        return main


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
    chain = _chain(require_api_key=require_api_key)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    needs_gemini = not chain or any(entry.slot.provider == "gemini" for entry in chain)
    if not api_key and require_api_key and needs_gemini:
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
        simulation_mode=_choice("ASG_SIMULATION_MODE", SimulationMode, SimulationMode.FIXED),
        inventory=_flag("ASG_INVENTORY", default=False),
        turns_per_beat=_integer("ASG_STAGE_TURNS_PER_BEAT", 8, minimum=2),
        stage_model=os.getenv("GEMINI_STAGE_MODEL", "").strip(),
        stage_api_key=os.getenv("GEMINI_STAGE_API_KEY", "").strip(),
        stage_rpm_limit=_integer("GEMINI_STAGE_RPM_LIMIT", 0),
        chain=chain,
        gemini_daily_requests=_integer("GEMINI_DAILY_REQUESTS", 500),
        budget_path=root / ".cache" / "llm_budget.sqlite3",
    )


def _key(name: str, *, required: bool) -> str:
    """Read the API key a chain provider needs, naming the variable when it is missing."""
    value = os.getenv(name, "").strip()
    if not value and required:
        raise ConfigurationError(f"ASG_LLM_CHAIN usa un proveedor sin clave: falta {name}.")
    return value


def _chain(*, require_api_key: bool) -> tuple[ChainEntry, ...]:
    """Read ASG_LLM_CHAIN into ordered slots; Groq contributes one slot per model."""
    raw = os.getenv("ASG_LLM_CHAIN", "")
    names = [name.strip().casefold() for name in raw.split(",") if name.strip()]
    entries: list[ChainEntry] = []
    for name in names:
        if name not in CHAIN_PROVIDERS:
            allowed = ", ".join(CHAIN_PROVIDERS)
            raise ConfigurationError(f"ASG_LLM_CHAIN solo admite: {allowed}.")
        if name == "gemini":
            slot = QuotaSlot(
                "gemini", "", "pacific_day", max_requests=_integer("GEMINI_DAILY_REQUESTS", 500)
            )
            entries.append(ChainEntry(slot))
        elif name == "groq":
            key = _key("GROQ_API_KEY", required=require_api_key)
            models = os.getenv("GROQ_MODELS", "") or "openai/gpt-oss-120b,openai/gpt-oss-20b"
            for model in (item.strip() for item in models.split(",") if item.strip()):
                slot = QuotaSlot(
                    "groq",
                    model,
                    "utc_day",
                    max_requests=_integer("GROQ_DAILY_REQUESTS", 1000),
                    max_tokens=_integer("GROQ_DAILY_TOKENS", 200_000),
                )
                rpm = _integer("GROQ_RPM_LIMIT", 30, minimum=1)
                entries.append(ChainEntry(slot, key, GROQ_BASE_URL, rpm, "Groq"))
        else:
            key = _key("MISTRAL_API_KEY", required=require_api_key)
            model = os.getenv("MISTRAL_MODEL", "").strip() or "mistral-small-latest"
            slot = QuotaSlot(
                "mistral", model, "utc_month", max_tokens=_integer("MISTRAL_MONTHLY_TOKENS", 0)
            )
            rpm = _integer("MISTRAL_RPM_LIMIT", 30, minimum=1)
            entries.append(ChainEntry(slot, key, MISTRAL_BASE_URL, rpm, "Mistral"))
    if len({entry.slot.key for entry in entries}) != len(entries):
        raise ConfigurationError("ASG_LLM_CHAIN repite un proveedor.")
    return tuple(entries)

"""Pair stored runs by what they were asked with, and say which axes they actually differ on.

The measurement protocol only reads a difference between runs that differ in one thing: the
same work, profile and model, and one arm changed. Before 7.3 a run recorded only some of its
axes (format, voice, memory and profile in metadata.json, turns per beat in performance.json),
so this module reads generation_options.json when a run has it and rebuilds the rest from the
older artifacts, keeping what was never recorded as None - shown as "no registrado", never
guessed.

Reads only JSON, like the rest of the package: it never imports the pipeline.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .artifacts import load_json_object, number_field, text_field
from .simulation_report import SIMULATION_FIELDS

SIMULATED = frozenset({"simulated"})


@dataclass(frozen=True)
class Axis:
    """One way two runs can differ; formats limits it to the runs it means anything for."""

    key: str
    label: str
    formats: frozenset[str] | None = None
    pairing: bool = False


AXES: tuple[Axis, ...] = (
    Axis("work", "Obra", pairing=True),
    Axis("model", "Modelo", pairing=True),
    Axis("stage_model", "Modelo de la función", SIMULATED, pairing=True),
    Axis("narrative_profile", "Perfil", pairing=True),
    Axis("story_format", "Formato"),
    Axis("script_method", "Método del guion", frozenset({"script"})),
    Axis("narrative_voice", "Visión", SIMULATED),
    Axis("narrator", "Personaje de la visión", SIMULATED),
    Axis("narration_tone", "Tono del narrador", SIMULATED),
    Axis("actor_memory", "Memoria de los actores", SIMULATED),
    Axis("inventory", "Inventario de objetos", SIMULATED),
    Axis("turns_per_beat", "Turnos por beat", SIMULATED),
    Axis("promise_ledger", "Ledger de promesas"),
    Axis("narrative_guidance", "Guía de esqueletos"),
    Axis("audio_voice", "Voz del audio"),
)
AXIS_LABELS = {axis.key: axis.label for axis in AXES}

# The option axes a run before 7.3 could not have set to anything but their default.
_FIXED_BEFORE_73 = {"narrator": "", "narration_tone": "", "audio_voice": ""}


@dataclass(frozen=True)
class Metric:
    """One figure a comparison reports, with the file it is read from."""

    key: str
    label: str
    group: str


METRICS: tuple[Metric, ...] = (
    Metric("story_words", "Palabras de la historia", "Historia"),
    Metric("story_chapters", "Capítulos", "Historia"),
    Metric("dialogue_ratio", "Proporción de párrafos con diálogo", "Historia"),
    Metric("words_per_sentence", "Palabras por frase", "Historia"),
    *(Metric(name, name, "Función") for name in SIMULATION_FIELDS),
    Metric("knowledge_score", "Juez: fronteras de conocimiento", "Juez LLM"),
    Metric("narration_score", "Juez: fidelidad de la narración", "Juez LLM"),
    Metric("llm_calls", "Llamadas al modelo", "Coste"),
    Metric("llm_total_tokens", "Tokens", "Coste"),
)


@dataclass
class RunConfig:
    """What one run was asked with, read from whatever artifacts it has."""

    directory: Path
    run_id: str
    title: str
    status: str | None
    pipeline_version: str | None
    generator_version: str | None
    plan_digest: str | None
    narrated_by: str
    axes: dict[str, object] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)


@dataclass
class Pairing:
    """Several runs side by side: their axes, what differs, and what to be careful about."""

    configs: list[RunConfig]
    differing_axes: list[str]
    unknown_axes: list[str]
    warnings: list[str]
    metrics: dict[str, list[float | None]]

    @property
    def clean(self) -> bool:
        """Say whether the runs are paired and differ in exactly one arm."""
        paired = not any(key in _PAIRING_KEYS for key in self.differing_axes)
        return paired and len(self.differing_axes) == 1


_PAIRING_KEYS = frozenset(axis.key for axis in AXES if axis.pairing)


def _digest(value: object) -> str:
    """Return a short stable fingerprint of a JSON value."""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _title(run_dir: Path, request: dict) -> str:
    """Read the story's own heading, or the working title when there is no story."""
    try:
        with (run_dir / "story.md").open(encoding="utf-8") as handle:
            first = handle.readline().strip()
        if first.startswith("# "):
            return first[2:].strip()
    except OSError:
        pass
    return text_field(request, "title") or run_dir.name


def _work(run_dir: Path, request: dict) -> str | None:
    """Fingerprint what the run was asked to tell: its brief, else its original prompt."""
    brief = load_json_object(run_dir / "brief.json")
    if brief:
        return f"ficha-{_digest(brief)}"
    prompt = text_field(request, "original_prompt")
    if prompt is None:
        prompt = text_field(load_json_object(run_dir / "submitted_request.json"), "prompt")
    return f"prompt-{_digest(' '.join(prompt.split()))}" if prompt else None


def _before_73(pipeline_version: str | None) -> bool:
    """Say whether a run predates the options record."""
    try:
        major, minor = (int(part) for part in (pipeline_version or "").split(".")[:2])
    except ValueError:
        return True
    return (major, minor) < (7, 3)


def read_run_config(run_dir: str | Path) -> RunConfig:
    """Describe the axes of one run, from generation_options.json or the older artifacts."""
    run_dir = Path(run_dir)
    metadata = load_json_object(run_dir / "metadata.json")
    request = load_json_object(run_dir / "request.json")
    options = load_json_object(run_dir / "generation_options.json")
    performance = load_json_object(run_dir / "performance.json")
    narration = load_json_object(run_dir / "narration.json")
    manifest = load_json_object(run_dir / "pipeline_manifest.json")
    version = load_json_object(run_dir / "generator_version.json")
    pipeline_version = text_field(metadata, "pipeline_version") or text_field(
        version, "pipeline_version"
    )
    axes: dict[str, object] = {}
    sources: dict[str, str] = {}

    def put(key: str, value: object, source: str) -> None:
        """Record one axis value and where it came from, unless it is already known."""
        if key not in axes and value is not None:
            axes[key] = value
            sources[key] = source

    work = _work(run_dir, request)
    put("work", work, "brief.json" if work and work.startswith("ficha") else "request.json")
    put("model", text_field(metadata, "model"), "metadata.json")
    for key in (axis.key for axis in AXES):
        if key in options:
            put(key, options[key], "generation_options.json")
    put("narrative_profile", text_field(metadata, "narrative_profile"), "metadata.json")
    put("narrative_profile", text_field(request, "narrative_profile"), "request.json")
    put("story_format", text_field(metadata, "story_format") or "narrative", "metadata.json")
    # A performance ran on `model` unless metadata names its own (7.4): every earlier run used one.
    if axes.get("story_format") in SIMULATED:
        put(
            "stage_model",
            text_field(metadata, "stage_model") or text_field(metadata, "model"),
            "metadata.json",
        )
    put("script_method", text_field(metadata, "script_method"), "metadata.json")
    put("narrative_voice", text_field(metadata, "narrative_voice"), "metadata.json")
    put("actor_memory", text_field(metadata, "actor_memory"), "metadata.json")
    settings = performance.get("settings") if isinstance(performance.get("settings"), dict) else {}
    turns = number_field(settings, "turns_per_beat")
    put("turns_per_beat", int(turns) if turns is not None else None, "performance.json")
    # No performance before 7.6 could track objects, so a run that does not say is a run without
    # one, which keeps the whole earlier corpus pairable against a run that has an inventory.
    if axes.get("story_format") in SIMULATED:
        put("inventory", bool(settings.get("inventory")), "performance.json")
    if _before_73(pipeline_version):
        for key, value in _FIXED_BEFORE_73.items():
            put(key, value, "anterior a 7.3")
    for axis in AXES:
        axes.setdefault(axis.key, None)
    plan = (manifest.get("artifacts") or {}).get("story_plan.json") if manifest else None
    return RunConfig(
        directory=run_dir,
        run_id=run_dir.name,
        title=_title(run_dir, request),
        status=text_field(metadata, "status"),
        pipeline_version=pipeline_version,
        generator_version=text_field(version, "generator_version"),
        plan_digest=(plan or {}).get("sha256") if isinstance(plan, dict) else None,
        narrated_by=text_field(narration, "narrator_character_id") or "",
        axes=axes,
        sources=sources,
    )


def run_measurements(run_dir: str | Path) -> dict[str, float | None]:
    """Read every figure of METRICS a run recorded, None for the ones it did not."""
    run_dir = Path(run_dir)
    story = load_json_object(run_dir / "story_metrics.json")
    simulation = load_json_object(run_dir / "simulation_metrics.json")
    audit = load_json_object(run_dir / "audit" / "audit.json")
    usage = load_json_object(run_dir / "llm_usage.json")
    values: dict[str, float | None] = {
        "story_words": number_field(story, "words"),
        "story_chapters": number_field(story, "chapters"),
        "dialogue_ratio": number_field(story, "dialogue_ratio"),
        "words_per_sentence": number_field(story, "words_per_sentence"),
        "knowledge_score": number_field(audit, "knowledge_score"),
        "narration_score": number_field(audit, "narration_score"),
        "llm_calls": number_field(usage, "calls"),
        "llm_total_tokens": number_field(usage, "total_tokens"),
    }
    for name in SIMULATION_FIELDS:
        values[name] = number_field(simulation, name)
    return {metric.key: values.get(metric.key) for metric in METRICS}


def _applies(axis: Axis, config: RunConfig) -> bool:
    """Say whether an axis means anything for one run's format."""
    return axis.formats is None or config.axes.get("story_format") in axis.formats


def pair_runs(run_dirs: list[str | Path]) -> Pairing:
    """Put runs side by side and say which axes differ and what the comparison can support."""
    configs = [read_run_config(path) for path in run_dirs]
    differing: list[str] = []
    unknown: list[str] = []
    for axis in AXES:
        relevant = [config for config in configs if _applies(axis, config)]
        if len(relevant) < 2:
            continue
        values = [config.axes.get(axis.key) for config in relevant]
        known = [value for value in values if value is not None]
        if len(known) < len(values):
            unknown.append(axis.key)
        if len({json.dumps(value, sort_keys=True) for value in known}) > 1:
            differing.append(axis.key)
    measured = [run_measurements(config.directory) for config in configs]
    metrics = {metric.key: [item[metric.key] for item in measured] for metric in METRICS}
    return Pairing(
        configs=configs,
        differing_axes=differing,
        unknown_axes=unknown,
        warnings=_warnings(configs, differing),
        metrics=metrics,
    )


def _warnings(configs: list[RunConfig], differing: list[str]) -> list[str]:
    """Say, in Spanish, what the comparison cannot claim."""
    warnings: list[str] = []
    if "work" in differing:
        warnings.append("Las funciones cuentan obras distintas: no es una comparación emparejada.")
    if "model" in differing:
        warnings.append("Usan modelos distintos: la diferencia puede ser del modelo.")
    if "stage_model" in differing:
        warnings.append(
            "Los actores usan modelos distintos: la diferencia de la función puede ser del modelo."
        )
    if "narrative_profile" in differing:
        warnings.append("Tienen perfiles narrativos distintos.")
    versions = {config.pipeline_version for config in configs if config.pipeline_version}
    if any(item in {"7.0", "7.1"} for item in versions) and any(
        not _before_73(item) or item == "7.2" for item in versions
    ):
        warnings.append(
            "Mezcla funciones 7.0 o 7.1 con 7.2 o posteriores: la memoria y las notas del "
            "director funcionaban distinto antes de 7.2."
        )
    arms = [key for key in differing if key not in _PAIRING_KEYS]
    if len(arms) > 1:
        labels = ", ".join(AXIS_LABELS[key].lower() for key in arms)
        warnings.append(f"Difieren en {len(arms)} ejes a la vez ({labels}): no se aísla ninguno.")
    if "narrative_voice" in differing or "narrator" in differing:
        warnings.append(
            "compression_ratio y dialogue_survival miden lo que vio el narrador: solo se "
            "comparan con la misma visión."
        )
    if arms:
        warnings.append("Con una función por brazo, una diferencia es un indicio, no una medida.")
    return warnings

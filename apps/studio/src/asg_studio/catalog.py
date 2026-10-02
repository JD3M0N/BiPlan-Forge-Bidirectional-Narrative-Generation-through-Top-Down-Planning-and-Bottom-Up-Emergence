"""The option catalog the interface is drawn from, available options and pending ones alike.

Every control StageCraft shows comes from this document: the browser renders each option by its
kind, so an option added here appears on screen without touching the HTML. The labels come from
the generator itself (formats.py, the profile labels, the audio voices), so every surface names
an option the same way; the pending entries and their roadmap notes live here because they are
the interface's promise about the future, not part of the generator's contract.

Turning a pending option into a real one is four steps: a field in GenerationOptions and its
facade keyword, the mechanism that reads it, its status here set to available, and a test.
"""

from __future__ import annotations

from collections import OrderedDict

from asg_core import NARRATION_VOICES
from asg_stagecraft import GenerationOptions
from asg_stagecraft.brief import MAX_CAST, PRONOUN_LABELS, ROLE_LABELS
from asg_stagecraft.formats import (
    FORMAT_COST_HINTS,
    MEMORY_CHOICES,
    OUTPUT_CHOICES,
    OUTPUT_HELP,
    OUTPUT_LABEL,
    VOICE_CHOICES,
    StoryFormat,
)
from asg_stagecraft.options import AUTOMATIC_AUDIO_VOICE_LABEL, MAX_OFFERED_TURNS_PER_BEAT
from asg_stagecraft.planning.profiles import (
    AUTOMATIC_PROFILE_DESCRIPTION,
    AUTOMATIC_PROFILE_LABEL,
    PROFILE_LABELS,
)

SIMULATED_ONLY = ["simulated"]

# GenerationOptions fields no control sets directly: the format preset sets both of these.
SET_BY_PRESET = frozenset({"story_format", "script_method"})

# What each run costs, keyed the way the interface groups a run: by story_format.value.
COST_HINTS = {story_format.value: hint for story_format, hint in FORMAT_COST_HINTS.items()}

_FIELDS = GenerationOptions.model_fields


def _title(name: str) -> str:
    """Return the Spanish label GenerationOptions declares for one of its fields."""
    return _FIELDS[name].title


def _help(name: str) -> str:
    """Return the Spanish help text GenerationOptions declares for one of its fields."""
    return _FIELDS[name].description


PENDING_ROADMAP = {
    "full_memory": "Idea del TODO: «Memoria completa frente a memoria recuperada».",
    "plan_from": "MED-5: comparar formatos y métodos desde un mismo plan congelado.",
    "spoiler_safe": "SIM-13: el narrador omnisciente destripa el misterio.",
    "multi_voice": "Idea del TODO: «Audio a varias voces».",
}


def _choice(value, label, description="", **extra) -> dict:
    """Describe one selectable value of a choice control."""
    return {"value": value, "label": label, "description": description, **extra}


def _pending(key: str, label: str, description: str, measures: str) -> dict:
    """Describe an option the interface shows but cannot run yet."""
    return {
        "key": key,
        "kind": "toggle",
        "label": label,
        "help": description,
        "status": "pending",
        "roadmap": PENDING_ROADMAP[key],
        "measures": measures,
    }


def _format_group() -> dict:
    """Describe the output format, a preset that sets the format and the script method."""
    choices = [
        _choice(
            item.key,
            item.label,
            item.description,
            sets={
                "story_format": item.story_format.value,
                "script_method": item.script_method.value,
            },
        )
        for item in OUTPUT_CHOICES
    ]
    return {
        "id": "format",
        "label": "Formato",
        "options": [
            {
                "key": "output",
                "kind": "preset",
                "label": OUTPUT_LABEL,
                "help": OUTPUT_HELP,
                "status": "available",
                "choices": choices,
            }
        ],
    }


def _narration_group() -> dict:
    """Describe the point of view, the character it follows and the narrator's tone."""
    voices = [
        _choice(
            item.voice.value, item.label, item.description, takes_character=item.takes_character
        )
        for item in VOICE_CHOICES
    ]
    voices.append(
        _choice(
            "spoiler_safe",
            "Omnisciente sin destripes",
            "Como la omnisciente, pero calla los pensamientos de quien guarda un secreto hasta "
            "que se revela.",
            takes_character=False,
            status="pending",
            roadmap=PENDING_ROADMAP["spoiler_safe"],
        )
    )
    return {
        "id": "narration",
        "label": "Narración",
        "applies_to": SIMULATED_ONLY,
        "note": "La visión y el tono los aplica el narrador de la historia simulada.",
        "options": [
            {
                "key": "narrative_voice",
                "kind": "choice",
                "label": _title("narrative_voice"),
                "help": _help("narrative_voice"),
                "status": "available",
                "choices": voices,
            },
            {
                "key": "narrator",
                "kind": "character",
                "label": _title("narrator"),
                "help": _help("narrator"),
                "status": "available",
                "enabled_when": {
                    "narrative_voice": [c["value"] for c in voices if c.get("takes_character")]
                },
                "max_length": 80,
            },
            {
                "key": "narration_tone",
                "kind": "text",
                "label": _title("narration_tone"),
                "help": _help("narration_tone"),
                "placeholder": "Como un guerrero samurái, con tono medieval",
                "status": "available",
                "max_length": 300,
            },
        ],
    }


def _simulation_group() -> dict:
    """Describe the performance knobs the thesis compares, and the ones still to come."""
    memories = [_choice(item.memory.value, item.label, item.description) for item in MEMORY_CHOICES]
    memories.append(
        _choice(
            "full",
            "Memoria completa",
            "Cada actor relee todo lo que presenció, sin tope de recuerdos.",
            status="pending",
            roadmap=PENDING_ROADMAP["full_memory"],
        )
    )
    return {
        "id": "simulation",
        "label": "Simulación",
        "applies_to": SIMULATED_ONLY,
        "note": "Los mandos de la función solo existen en la historia simulada.",
        "options": [
            {
                "key": "actor_memory",
                "kind": "choice",
                "label": _title("actor_memory"),
                "help": _help("actor_memory"),
                "status": "available",
                "choices": memories,
            },
            {
                "key": "simulation_mode",
                "kind": "choice",
                "label": _title("simulation_mode"),
                "help": _help("simulation_mode"),
                "status": "available",
                "choices": [
                    {"value": "fixed", "label": "Hitos fijos"},
                    {"value": "adaptive", "label": "Hitos adaptables"},
                ],
            },
            {
                "key": "turns_per_beat",
                "kind": "integer",
                "label": _title("turns_per_beat"),
                "help": _help("turns_per_beat"),
                "status": "available",
                "min": 2,
                "max": MAX_OFFERED_TURNS_PER_BEAT,
            },
            {
                "key": "inventory",
                "kind": "toggle",
                "label": _title("inventory"),
                "help": _help("inventory"),
                "status": "available",
            },
        ],
    }


def _planning_group() -> dict:
    """Describe the planning switches that are also ablation arms."""
    return {
        "id": "planning",
        "label": "Planificación",
        "options": [
            {
                "key": "narrative_profile",
                "kind": "choice",
                "label": _title("narrative_profile"),
                "help": _help("narrative_profile"),
                "status": "available",
                "choices": [
                    _choice(None, AUTOMATIC_PROFILE_LABEL, AUTOMATIC_PROFILE_DESCRIPTION),
                    *(_choice(profile.value, label) for profile, label in PROFILE_LABELS.items()),
                ],
            },
            {
                "key": "promise_ledger",
                "kind": "toggle",
                "label": _title("promise_ledger"),
                "help": _help("promise_ledger"),
                "status": "available",
            },
            {
                "key": "narrative_guidance",
                "kind": "toggle",
                "label": _title("narrative_guidance"),
                "help": _help("narrative_guidance"),
                "status": "available",
            },
            _pending(
                "plan_from",
                "Partir del plan de otra función",
                "Reutiliza el plan congelado de una función anterior y cambia solo lo demás.",
                "Comparaciones con el mismo plan: el emparejamiento más limpio.",
            ),
        ],
    }


def _audio_group() -> dict:
    """Describe the audio switch and the voices it can be read with, grouped by country."""
    countries: OrderedDict[str, list[dict]] = OrderedDict()
    for voice in NARRATION_VOICES:
        countries.setdefault(voice.country, []).append(
            _choice(voice.name, f"{voice.display_name} · {voice.gender}")
        )
    return {
        "id": "audio",
        "label": "Audio",
        "options": [
            {
                "key": "audio",
                "kind": "toggle",
                "label": _title("audio"),
                "help": _help("audio"),
                "status": "available",
            },
            {
                "key": "audio_voice",
                "kind": "audio_voice",
                "label": _title("audio_voice"),
                "help": _help("audio_voice"),
                "status": "available",
                "enabled_when": {"audio": [True]},
                "groups": [
                    {"label": "", "choices": [_choice("", AUTOMATIC_AUDIO_VOICE_LABEL)]},
                    *(
                        {"label": country, "choices": choices}
                        for country, choices in countries.items()
                    ),
                ],
            },
            _pending(
                "multi_voice",
                "Audio a varias voces",
                "Una voz distinta para cada personaje en las réplicas.",
                "Si separar las voces ayuda a seguir la función al escucharla.",
            ),
        ],
    }


def catalog_document(defaults: GenerationOptions) -> dict:
    """Return everything the interface needs to draw its options, with the defaults to show."""
    return {
        "defaults": defaults.model_dump(mode="json"),
        "groups": [
            _format_group(),
            _narration_group(),
            _simulation_group(),
            _planning_group(),
            _audio_group(),
        ],
        "brief": {
            "roles": [_choice(role, label) for role, label in ROLE_LABELS.items()],
            "pronouns": [_choice(pronoun, label) for pronoun, label in PRONOUN_LABELS.items()],
            "max_cast": MAX_CAST,
        },
        "cost": COST_HINTS,
        "simulated": StoryFormat.SIMULATED.value,
    }


def available_keys(document: dict) -> set[str]:
    """Return the keys of every control the interface can already run."""
    return {
        option["key"]
        for group in document["groups"]
        for option in group["options"]
        if option["status"] == "available"
    }


def pending_keys(document: dict) -> set[str]:
    """Return the keys of every control shown as pending."""
    return {
        option["key"]
        for group in document["groups"]
        for option in group["options"]
        if option["status"] == "pending"
    }

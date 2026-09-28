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
from asg_stagecraft.formats import MEMORY_CHOICES, OUTPUT_CHOICES, VOICE_CHOICES, StoryFormat
from asg_stagecraft.planning.profiles import PROFILE_LABELS

SIMULATED_ONLY = ["simulated"]

# GenerationOptions fields no control sets directly: the format preset sets both of these.
SET_BY_PRESET = frozenset({"story_format", "script_method"})

# What each run costs, as the roadmap's measurement protocol states it; shown before a launch.
COST_HINTS = {
    "narrative": "Una narrativa cuesta unas 16 llamadas al modelo.",
    "script": "Un guion cuesta unas 20 llamadas al modelo.",
    "simulated": "Una simulada cuesta entre 98 y 126 llamadas: una parte grande del cupo diario.",
}

PENDING_ROADMAP = {
    "inventory": "Idea del TODO: «Un árbitro de acciones físicas» e «Inventario por personaje».",
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
    descriptions = {
        "narrative": "Prosa escrita a partir del plan: el enfoque Top-Down.",
        "script-native": "El plan escrito directamente como obra de teatro, por escenas.",
        "script-adapted": "La prosa terminada, adaptada después a guion.",
        "simulated": (
            "Los personajes representan el guion con memoria propia y se narra la función."
        ),
    }
    choices = [
        _choice(
            item.key,
            item.label,
            descriptions.get(item.key, ""),
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
                "label": "Formato de salida",
                "help": "Qué entrega la función terminada.",
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
                "label": "Visión",
                "help": "Desde dónde se cuenta la función: qué turnos y qué pensamientos ve.",
                "status": "available",
                "choices": voices,
            },
            {
                "key": "narrator",
                "kind": "character",
                "label": "Personaje de la visión",
                "help": (
                    "Quién cuenta la historia en las visiones limitada y en primera persona. "
                    "Los capítulos que no presencie se omiten."
                ),
                "status": "available",
                "enabled_when": {
                    "narrative_voice": [c["value"] for c in voices if c.get("takes_character")]
                },
                "max_length": 80,
            },
            {
                "key": "narration_tone",
                "kind": "text",
                "label": "Tono del narrador",
                "help": "El registro de la voz que cuenta. Colorea la prosa; nunca añade sucesos.",
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
                "label": "Memoria de los actores",
                "help": "Qué recuerda cada personaje de lo que ocurrió en escena.",
                "status": "available",
                "choices": memories,
            },
            {
                "key": "turns_per_beat",
                "kind": "integer",
                "label": "Turnos por beat",
                "help": "Cuántos turnos puede durar un beat antes de que el mundo lo cierre.",
                "status": "available",
                "min": 2,
                "max": 16,
            },
            _pending(
                "inventory",
                "Inventario de objetos",
                "Quién tiene qué: dar, tomar y esconder objetos que solo percibe quien los ve.",
                "La coherencia física de la función y la asimetría de información.",
            ),
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
                "label": "Perfil narrativo",
                "help": "La escala de la historia. Automático deja que lo deduzca el analista.",
                "status": "available",
                "choices": [
                    _choice(None, "Automático", "Lo deduce el analista a partir de la obra."),
                    *(_choice(profile.value, label) for profile, label in PROFILE_LABELS.items()),
                ],
            },
            {
                "key": "promise_ledger",
                "kind": "toggle",
                "label": "Ledger de promesas",
                "help": (
                    "Traza qué promete la historia y dónde lo paga. Apagarlo es su brazo de "
                    "control."
                ),
                "status": "available",
            },
            {
                "key": "narrative_guidance",
                "kind": "toggle",
                "label": "Guía de esqueletos",
                "help": "Inspira el plan con esqueletos de trama clásicos.",
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
                "label": "Narración en audio",
                "help": "Lee la historia terminada en story.mp3.",
                "status": "available",
            },
            {
                "key": "audio_voice",
                "kind": "audio_voice",
                "label": "Voz del audio",
                "help": "Quién lee la historia. Automática elige por el idioma.",
                "status": "available",
                "enabled_when": {"audio": [True]},
                "groups": [
                    {"label": "", "choices": [_choice("", "Automática (según el idioma)")]},
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
            "roles": [
                _choice("", "Sin rol"),
                _choice("protagonista", "Protagonista"),
                _choice("antagonista", "Antagonista"),
                _choice("aliado", "Aliado"),
                _choice("secundario", "Secundario"),
            ],
            "pronouns": [
                _choice("", "—"),
                _choice("ella", "ella"),
                _choice("él", "él"),
                _choice("elle", "elle"),
            ],
            "max_cast": 10,
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

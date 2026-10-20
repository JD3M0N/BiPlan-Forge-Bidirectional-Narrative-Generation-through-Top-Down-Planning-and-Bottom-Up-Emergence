"""7.3: a story asked for as a structured brief, and a cast that keeps the declared names."""

import json
from typing import get_args

import pytest
from asg_stagecraft import CastMember, StoryBrief, StoryGenerator
from asg_stagecraft.brief import (
    PRONOUN_LABELS,
    ROLE_LABELS,
    CastRole,
    Pronoun,
    cast_repair_feedback,
    missing_cast,
)
from pydantic import ValidationError
from test_generator_v5 import FakeProvider, make_characters


def test_role_and_pronoun_labels_cover_every_declared_value() -> None:
    assert set(ROLE_LABELS) == set(get_args(CastRole))
    assert set(PRONOUN_LABELS) == set(get_args(Pronoun))


def read_json(run_dir, name):
    return json.loads((run_dir / name).read_text(encoding="utf-8"))


def brief(*cast: CastMember, **fields) -> StoryBrief:
    values = {
        "plot": "Una archivera descubre que alguien se llevó el expediente anoche.",
        "cast": list(cast),
        **fields,
    }
    return StoryBrief(**values)


def characters_calls(provider, schema="CharactersArtifact") -> list[str]:
    return [prompt for name, _, prompt in provider.structured_calls if name == schema]


def test_the_prompt_is_composed_the_same_way_every_time() -> None:
    story = brief(
        CastMember(
            name="Ana",
            role="protagonista",
            pronoun="ella",
            description="archivera veterana",
            secret="se llevó el expediente",
        ),
        CastMember(name="Luis", role="antagonista"),
        title="El expediente",
        genre="misterio",
        setting="un archivo municipal en invierno",
        notes="Final abierto.",
    )
    assert story.to_prompt() == (
        "Escribe una historia a partir de esta ficha.\n"
        "Título provisional: El expediente.\n"
        "Género: misterio.\n"
        "Ambientación: un archivo municipal en invierno.\n"
        "Trama: Una archivera descubre que alguien se llevó el expediente anoche.\n"
        "Reparto (usa exactamente estos nombres, sin traducirlos ni cambiarlos):\n"
        "- Ana (ella), protagonista: archivera veterana. Secreto: se llevó el expediente.\n"
        "- Luis, antagonista.\n"
        "Notas: Final abierto."
    )
    assert story.to_prompt() == story.model_copy().to_prompt()
    # 7.20: a composed brief pasted as a prompt is read back; any other prompt is not one.
    assert StoryBrief.from_prompt(story.to_prompt()).to_prompt() == story.to_prompt()
    assert StoryBrief.from_prompt("Una historia sobre Zoe.\nTrama: nada.") is None


def test_a_bare_brief_is_only_its_plot() -> None:
    assert brief().to_prompt() == (
        "Escribe una historia a partir de esta ficha.\n"
        "Trama: Una archivera descubre que alguien se llevó el expediente anoche."
    )


@pytest.mark.parametrize(
    "fields",
    [
        {"plot": "   "},
        {"cast": [CastMember(name="Ana"), CastMember(name="ANA")]},
        {"cast": [CastMember(name=f"Personaje {index}") for index in range(11)]},
        {"cast": [{"name": "Ana", "role": "villana"}]},
        {"inventory": ["una llave"]},
    ],
)
def test_an_unplayable_brief_is_rejected(fields) -> None:
    with pytest.raises(ValidationError):
        StoryBrief(**{"plot": "Una trama.", **fields})


def test_a_character_needs_a_real_name() -> None:
    with pytest.raises(ValidationError):
        CastMember(name="   ")


def test_a_declared_cast_is_matched_by_name_not_by_id() -> None:
    cast = make_characters()
    assert missing_cast(brief(CastMember(name="ana")), cast) == []
    missing = missing_cast(brief(CastMember(name="Ana"), CastMember(name="Zoe")), cast)
    assert [member.name for member in missing] == ["Zoe"]
    feedback = cast_repair_feedback(missing)
    assert "CAST REPAIR REQUIRED" in feedback
    assert "- Zoe" in feedback


@pytest.mark.parametrize(
    ("submit", "warnings"),
    [
        (lambda story: story, []),
        (lambda story: story.to_prompt(), ["BRIEF_FROM_PROMPT"]),
        (
            lambda story: story.to_prompt().encode("utf-8").decode("cp1252"),
            ["PROMPT_ENCODING_REPAIRED", "BRIEF_FROM_PROMPT"],
        ),
    ],
    ids=["brief", "pasted-prompt", "double-encoded-prompt"],
)
def test_a_brief_run_keeps_the_brief_and_analyzes_its_prompt(tmp_path, submit, warnings) -> None:
    """7.20: the 7.19 islands runs pasted the brief as a prompt, through PowerShell 5.1."""
    story = brief(CastMember(name="Ana", role="protagonista", secret="se llevó el expediente"))
    provider = FakeProvider()
    run = StoryGenerator(provider, tmp_path).generate(submit(story))
    assert StoryBrief.model_validate(read_json(run.run_dir, "brief.json")) == story
    assert read_json(run.run_dir, "request.json")["original_prompt"] == story.to_prompt()
    assert "pipeline_manifest.json" in {path.name for path in run.run_dir.iterdir()}
    assert "brief.json" in read_json(run.run_dir, "pipeline_manifest.json")["artifacts"]
    # Ana was cast on the first try, so the designer was asked exactly once.
    assert len(characters_calls(provider)) == 1
    # 7.13: the designer reads the declared cast verbatim, not only the analyst's summary.
    assert "- Ana, protagonista. Secreto: se llevó el expediente." in characters_calls(provider)[0]
    # 7.14: the planner and the plan critic read the authored plot as canon.
    for schema in ("StoryPlanDraft", "PlanReview"):
        assert "AUTHOR'S PLOT" in characters_calls(provider, schema)[0]
        assert story.plot in characters_calls(provider, schema)[0]
    recorded = read_json(run.run_dir, "metadata.json")["warnings"]
    assert [item[1:].split("]")[0] for item in recorded] == warnings


def test_a_missing_character_gets_one_repair_and_then_a_warning(tmp_path) -> None:
    story = brief(CastMember(name="Ana"), CastMember(name="Zoe", role="aliado"))
    provider = FakeProvider()
    run = StoryGenerator(provider, tmp_path).generate(story)
    prompts = characters_calls(provider)
    assert len(prompts) == 2
    assert "CAST REPAIR REQUIRED" not in prompts[0]
    assert "- Zoe (ally)" in prompts[1]
    assert (run.run_dir / "characters" / "attempt-001.json").is_file()
    warnings = read_json(run.run_dir, "metadata.json")["warnings"]
    assert warnings == ["[BRIEF_CAST_MISSING] El reparto no incluye: Zoe."]


def test_a_plain_prompt_never_asks_for_a_repair(tmp_path) -> None:
    provider = FakeProvider()
    run = StoryGenerator(provider, tmp_path).generate("Una historia sobre Zoe")
    assert len(characters_calls(provider)) == 1
    assert "AUTHOR'S CAST" not in characters_calls(provider)[0]
    assert "AUTHOR'S PLOT" not in characters_calls(provider, "StoryPlanDraft")[0]
    assert not run.brief_path.exists()

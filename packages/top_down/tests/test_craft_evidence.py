from asg_top_down.craft_evidence import (
    BLOCK_PARAGRAPHS,
    NO_DIALOGUE,
    RARE_DIALOGUE,
    chapter_observations,
    craft_evidence,
)
from asg_top_down.schemas import ChapterPlan

DASH = "—"


def chapter(identifier: str, order: int) -> ChapterPlan:
    return ChapterPlan(
        id=identifier,
        order=order,
        title=f"Capitulo {order}",
        summary="El faro se apaga",
        dramatic_goal="Descubrir por que se apago el faro",
        opening_state="Nadie ha subido a la linterna",
        turning_point="Aparece el cuaderno de guardia",
        closing_state="La costa queda a oscuras",
    )


def scene(lines: int = 4) -> str:
    spoken = f"{DASH}No queda aceite {DASH}dijo el farero."
    return "\n\n".join([spoken, "Subio los escalones."] * lines)


def narration(words_per_paragraph: int, paragraphs: int = 4) -> str:
    block = " ".join(["niebla"] * words_per_paragraph) + "."
    return "\n\n".join([block] * paragraphs)


def test_a_chapter_without_any_spoken_exchange_is_reported() -> None:
    assert chapter_observations(narration(20)) == [NO_DIALOGUE]


def test_a_chapter_that_barely_speaks_is_reported_as_narrated() -> None:
    body = "\n\n".join([f"{DASH}Sube {DASH}dijo.", *[narration(10, 1)] * 9])
    assert chapter_observations(body) == [RARE_DIALOGUE]


def test_block_paragraphs_are_reported_alongside_the_dialogue_verdict() -> None:
    assert chapter_observations(narration(150)) == [NO_DIALOGUE, BLOCK_PARAGRAPHS]


def test_a_dramatized_chapter_produces_no_observation() -> None:
    assert chapter_observations(scene()) == []


def test_an_empty_body_produces_no_observation() -> None:
    assert chapter_observations("") == []


def test_the_evidence_block_names_only_the_chapters_that_narrate() -> None:
    evidence = craft_evidence(
        [chapter("capitulo_1", 1), chapter("capitulo_2", 2)], [scene(), narration(20)]
    )

    assert evidence.chapters[0].observations == []
    assert evidence.chapters[1].observations == [NO_DIALOGUE]
    assert "capitulo_1" not in evidence.prompt_block
    assert f"- capitulo_2: {NO_DIALOGUE}." in evidence.prompt_block


def test_a_healthy_draft_sends_nothing_to_the_critic() -> None:
    evidence = craft_evidence([chapter("capitulo_1", 1)], [scene()])

    assert evidence.prompt_block == ""
    assert evidence.chapters[0].observations == []


def test_no_measurement_ever_reaches_the_prompt() -> None:
    evidence = craft_evidence([chapter("capitulo_1", 1)], [narration(150)])
    wording = "".join(
        item for observation in evidence.chapters[0].observations for item in observation
    )

    assert not any(character.isdigit() for character in wording)
    assert "%" not in evidence.prompt_block

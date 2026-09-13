import json

from asg_core import craft_metrics
from asg_top_down.audit import story_metrics
from asg_top_down.profiles import NarrativeProfile
from asg_top_down.schemas import ChapterPlan, PlotEvent, StoryPlan, StoryRequest

DASH = "\u2014"


def request(profile: NarrativeProfile = NarrativeProfile.ESSENTIAL) -> StoryRequest:
    return StoryRequest(
        original_prompt="Una historia sobre un faro apagado",
        title="La ultima luz del faro",
        genre="misterio",
        tone="sobrio",
        narrative_profile=profile,
        premise="El farero desaparece la noche del apagon",
    )


def chapter(identifier: str, order: int, title: str) -> ChapterPlan:
    return ChapterPlan(
        id=identifier,
        order=order,
        title=title,
        summary="El faro se apaga",
        dramatic_goal="Descubrir por que se apago el faro",
        opening_state="Nadie ha subido a la linterna",
        turning_point="Aparece el cuaderno de guardia",
        closing_state="La costa queda a oscuras",
    )


def event(identifier: str, order: int, chapter_id: str) -> PlotEvent:
    return PlotEvent(
        id=identifier,
        order=order,
        chapter_id=chapter_id,
        title=identifier,
        description=f"Evento {identifier}",
        purpose="Avanzar el conflicto",
        dramatic_function="Escalar la busqueda",
        conflict="Elena debe elegir entre avisar o seguir sola",
        outcome="Elena aprende algo que no puede devolver",
        character_ids=["elena"],
        location_id="faro",
        effects=["La situacion cambia"],
    )


def plan(chapters: int = 2) -> StoryPlan:
    titles = ["El apagon", "La linterna", "El cuaderno"]
    return StoryPlan(
        logline="Elena busca al farero",
        theme="La verdad cuesta",
        ending="Elena acepta el precio",
        narrative_structure="Tres actos",
        dramatic_question="Quien apago el faro?",
        stakes="La costa entera queda sin senal",
        chapters=[
            chapter(f"chapter-{index + 1}", index + 1, titles[index]) for index in range(chapters)
        ],
        events=[
            event(f"event-{index + 1}", index + 1, f"chapter-{(index // 2) + 1}")
            for index in range(chapters * 2)
        ],
        dependencies=[],
    )


def story(*bodies: str) -> str:
    titles = ["El apagon", "La linterna", "El cuaderno"]
    chapters = "\n\n".join(f"## {titles[index]}\n\n{body}" for index, body in enumerate(bodies))
    return f"# La ultima luz del faro\n\n{chapters}\n"


DRAMATIZED = (
    f"{DASH}La linterna no se apago sola {DASH}dijo Elena, sin apartar la vista del cuaderno."
    "\n\nEl haz muerto dejaba la bahia en sombra."
)
SUMMARIZED = (
    "Durante las semanas siguientes la comision reviso cada guardia, cada registro y cada "
    "bitacora, y concluyo que nadie habia subido a la linterna aquella noche."
)


def test_story_metrics_record_prose_craft_alongside_size():
    """Report the craft figures next to the words, chapters and events."""
    text = story(DRAMATIZED, SUMMARIZED)
    metrics = story_metrics(request(), plan(), text)

    assert metrics.chapters == 2
    assert metrics.events == 4
    assert metrics.prose_paragraphs == 3
    assert metrics.dash_paragraphs == 1
    assert metrics.dialogue_paragraphs == 1
    assert metrics.dialogue_ratio == round(1 / 3, 4)
    assert metrics.words_per_sentence > 0
    assert metrics.words_per_paragraph > 0
    assert metrics.chapter_bodies_recovered is True


def test_prose_words_exclude_the_markdown_headings():
    """Keep ``words`` as the whole document and ``prose_words`` as the prose."""
    text = story(DRAMATIZED, SUMMARIZED)
    metrics = story_metrics(request(), plan(), text)

    assert metrics.words > metrics.prose_words > 0
    assert metrics.prose_words == craft_metrics(text).words


def test_chapter_metrics_carry_their_own_craft_figures():
    """Separate a dramatized chapter from a summarized one."""
    metrics = story_metrics(request(), plan(), story(DRAMATIZED, SUMMARIZED))
    dramatized, summarized = metrics.chapter_metrics

    assert dramatized.paragraphs == 2
    assert dramatized.dialogue_paragraphs == 1
    assert dramatized.dialogue_ratio == 0.5
    assert summarized.paragraphs == 1
    assert summarized.dialogue_paragraphs == 0
    assert summarized.dialogue_ratio == 0.0
    assert summarized.words_per_paragraph > dramatized.words_per_paragraph


def test_lost_headings_mark_the_chapter_bodies_as_unrecovered():
    """Declare that the per-chapter zeroes come from unparsable headings."""
    text = f"# La ultima luz del faro\n\n{DRAMATIZED}\n\n{SUMMARIZED}\n"
    metrics = story_metrics(request(), plan(), text)

    assert metrics.chapter_bodies_recovered is False
    assert [item.words for item in metrics.chapter_metrics] == [0, 0]
    assert [item.paragraphs for item in metrics.chapter_metrics] == [0, 0]
    assert metrics.prose_paragraphs == 3
    assert metrics.dialogue_paragraphs == 1


def test_a_story_without_dialogue_reports_a_zero_ratio():
    """Give the pipeline a zero to compare against, never a missing value."""
    metrics = story_metrics(request(), plan(), story(SUMMARIZED, SUMMARIZED))

    assert metrics.dialogue_paragraphs == 0
    assert metrics.dash_paragraphs == 0
    assert metrics.quoted_paragraphs == 0
    assert metrics.dialogue_ratio == 0.0
    assert metrics.words_per_paragraph > 0


def test_recorded_craft_matches_the_reporter_recomputation(tmp_path):
    """Keep the run artifact and the corpus reporter on the same figures."""
    from asg_evaluation.craft_report import read_story_craft

    run_dir = tmp_path / "Top-Down" / "20260913-120000-el-faro"
    run_dir.mkdir(parents=True)
    text = story(DRAMATIZED, SUMMARIZED)
    metrics = story_metrics(request(), plan(), text)
    (run_dir / "story.md").write_text(text, encoding="utf-8")
    (run_dir / "story_metrics.json").write_text(metrics.model_dump_json(indent=2), encoding="utf-8")

    record = read_story_craft(run_dir, tmp_path)

    assert record.craft.paragraphs == metrics.prose_paragraphs
    assert record.craft.sentences == metrics.prose_sentences
    assert record.craft.words == metrics.prose_words
    assert record.craft.dialogue_ratio == metrics.dialogue_ratio
    assert record.craft.words_per_sentence == metrics.words_per_sentence
    assert record.craft.words_per_paragraph == metrics.words_per_paragraph
    assert json.loads((run_dir / "story_metrics.json").read_text(encoding="utf-8"))[
        "chapter_bodies_recovered"
    ]

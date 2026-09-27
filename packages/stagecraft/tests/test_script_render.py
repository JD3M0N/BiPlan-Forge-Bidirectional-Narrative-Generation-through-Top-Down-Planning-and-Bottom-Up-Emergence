from asg_stagecraft.formats import ScriptMethod
from asg_stagecraft.schemas import (
    CastNote,
    ChapterPresentation,
    ScriptFrame,
    ScriptPresentation,
)
from asg_stagecraft.script.render import render_script, roman, staging_index
from asg_stagecraft.script.validation import assemble_play, materialize_act, normalized_frame
from asg_stagecraft.writing.audit import script_metrics
from test_generator_v5 import make_request
from test_script import context, make_characters, make_plan, valid_draft


def make_presentation() -> ScriptPresentation:
    return ScriptPresentation(
        title="El Archivo",
        chapters=[ChapterPresentation(chapter_id="chapter-1", title="The Archive")],
        frame=ScriptFrame(
            cast_heading="Personajes",
            act_label="Acto",
            scene_label="Escena",
            cast=[CastNote(character_id="ana", description="archivista")],
        ),
    )


def make_play():
    ctx = context()
    act = materialize_act(valid_draft(), **ctx)
    return assemble_play(
        make_presentation(),
        make_characters(),
        [act],
        language="Spanish",
        method=ScriptMethod.NATIVE,
    )


def test_render_uses_the_printed_play_convention() -> None:
    play = make_play()
    rendered = render_script(play)
    assert "# El Archivo" in rendered
    assert "## Personajes" in rendered
    assert "## Acto I. The Archive" in rendered
    assert "### Escena 1" in rendered
    assert "ANA.—" in rendered
    assert "LUIS.—" in rendered


def test_render_never_leaks_objectives_or_ids() -> None:
    play = make_play()
    rendered = render_script(play)
    assert "objective" not in rendered.casefold()
    assert "chapter-1-scene" not in rendered
    assert "*" not in rendered
    assert "_" not in rendered


def test_cast_list_falls_back_to_name_only_without_description() -> None:
    play = make_play()
    luis = next(member for member in play.cast if member.character_id == "luis")
    assert luis.description == ""
    rendered = render_script(play)
    assert "- LUIS." in rendered


def test_an_act_takes_the_localized_chapter_title() -> None:
    """TD-2: two of three native scripts printed "Acto I. The Mechanical Anomaly"."""
    presentation = make_presentation().model_copy(
        update={"chapters": [ChapterPresentation(chapter_id="chapter-1", title="El legajo")]}
    )
    act = materialize_act(valid_draft(), **context())
    play = assemble_play(
        presentation, make_characters(), [act], language="Spanish", method=ScriptMethod.NATIVE
    )
    assert play.acts[0].title == "El legajo"
    assert "## Acto I. El legajo" in render_script(play)


def test_a_cast_description_that_ends_its_sentence_gets_no_second_period() -> None:
    """TD-6: every cast entry of the 25-09 scripts ended in "..", a period always added."""
    frame = make_presentation().frame.model_copy(
        update={"cast": [CastNote(character_id="ana", description="archivista del faro.")]}
    )
    presentation = make_presentation().model_copy(update={"frame": frame})
    act = materialize_act(valid_draft(), **context())
    play = assemble_play(
        presentation, make_characters(), [act], language="Spanish", method=ScriptMethod.NATIVE
    )
    rendered = render_script(play)
    assert "- ANA, archivista del faro." in rendered
    assert ".." not in rendered


def test_a_spanish_script_always_heads_its_cast_the_same_way() -> None:
    """TD-6: the cast heading alternated between "Reparto" and "Personajes" from run to run."""
    frame = ScriptFrame(cast_heading="Reparto", act_label="Acto", scene_label="Escena", cast=[])
    assert normalized_frame(frame, make_characters(), language="Spanish").cast_heading == (
        "Personajes"
    )
    assert normalized_frame(frame, make_characters(), language="English").cast_heading == (
        "Reparto"
    )


def test_roman_numerals() -> None:
    assert [roman(n) for n in range(1, 8)] == ["I", "II", "III", "IV", "V", "VI", "VII"]


def test_staging_index_never_shows_scene_ids() -> None:
    play = make_play()
    index = staging_index(play)
    assert "chapter-1-scene" not in index
    assert "wants:" in index
    assert "event-1" in index


def test_script_metrics_counts_lines_and_staging() -> None:
    play = make_play()
    rendered = render_script(play)
    metrics = script_metrics(make_request(), make_plan(), play, rendered)
    assert metrics.acts == 1
    assert metrics.scenes == 2
    assert metrics.events == 2
    assert metrics.dialogue_lines == 2
    assert metrics.direction_lines == 2
    assert metrics.dialogue_words > 0
    assert 0.0 <= metrics.dialogue_word_ratio <= 1.0
    assert metrics.words > 0
    assert len(metrics.act_metrics) == 1
    assert {item.character_id for item in metrics.character_metrics} == {"ana", "luis"}

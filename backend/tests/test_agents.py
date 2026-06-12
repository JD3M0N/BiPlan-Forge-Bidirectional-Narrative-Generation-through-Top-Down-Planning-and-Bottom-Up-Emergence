import asyncio

import pytest

from app.schemas import ArchitectOutline, DependencyReview, DramaRevision, FinalStory, StoryPacket, WorldBible
from app.schemas import ChapterDraft, ContextSummary, DirectorPlan, PlotWeave, SimulationLog, StoryEvaluation
from app.services.agents import StoryAgents

from .fakes import (
    ARCHITECT_PROMPT,
    CHAPTER_WRITER_PROMPT,
    CHARACTER_SIMULATOR_PROMPT,
    COORDINATOR_PROMPT,
    DEPENDENCY_MANAGER_PROMPT,
    DIRECTOR_PROMPT,
    DRAMA_COACH_PROMPT,
    NARRATOR_PROMPT,
    PLOT_WEAVER_PROMPT,
    QUALITY_EVALUATOR_PROMPT,
    QUALITY_REWRITER_PROMPT,
    WORLD_BUILDER_PROMPT,
    FakeGeminiClient,
    build_story_request,
)


def build_packet() -> StoryPacket:
    from app.schemas import StoryGenerateRequest

    request = StoryGenerateRequest.parse_obj(build_story_request())
    return StoryPacket.parse_obj({"input_brief": request.to_input_brief()})


@pytest.mark.parametrize(
    ("method_name", "expected_type", "expected_value"),
    [
        ("run_architect", ArchitectOutline, "Una aprendiz encuentra un reloj"),
        ("run_world_builder", WorldBible, "Archivo del Reloj"),
        ("run_director", DirectorPlan, "Tentacion del costo"),
        ("run_character_simulator", SimulationLog, "Ayla"),
        ("run_drama_coach", DramaRevision, "Traicion del mentor"),
        ("run_dependency_manager", DependencyReview, True),
        ("run_quality_evaluator", StoryEvaluation, 4.2),
        ("run_narrator", FinalStory, "El reloj de la torre muda"),
    ],
)
def test_story_agents_return_structured_models(
    method_name: str,
    expected_type: type,
    expected_value,
) -> None:
    agents = StoryAgents(FakeGeminiClient())
    packet = build_packet()

    result = asyncio.run(getattr(agents, method_name)(packet))

    assert isinstance(result, expected_type)
    if isinstance(expected_value, bool):
        assert result.is_consistent is expected_value
    elif hasattr(result, "title"):
        assert result.title == expected_value
    elif hasattr(result, "locations"):
        assert result.locations[0].name == expected_value
    elif hasattr(result, "acts"):
        assert result.acts[0].abstract_act == expected_value
    elif hasattr(result, "actions"):
        assert result.actions[0].character == expected_value
    elif hasattr(result, "revised_beats"):
        assert result.revised_beats[0].title == expected_value
    elif hasattr(result, "overall"):
        assert result.overall == expected_value
    else:
        assert result.premise.startswith(expected_value)


def test_plot_weaver_returns_chapter_plan_for_requested_length() -> None:
    agents = StoryAgents(FakeGeminiClient())
    packet = build_packet()

    result = asyncio.run(agents.run_plot_weaver(packet, chapter_count=5))

    assert isinstance(result, PlotWeave)
    assert len(result.event_graph) == 5
    assert len(result.chapter_plan.chapters) == 5
    assert result.chapter_plan.chapters[-1].index == 5


def test_coordinator_and_chapter_writer_return_indexed_payloads() -> None:
    agents = StoryAgents(FakeGeminiClient())
    packet = build_packet()
    weave = asyncio.run(agents.run_plot_weaver(packet, chapter_count=3))
    chapter = weave.chapter_plan.chapters[1]

    context = asyncio.run(agents.run_coordinator(packet, chapter))
    draft = asyncio.run(agents.run_chapter_writer(packet, context))

    assert isinstance(context, ContextSummary)
    assert isinstance(draft, ChapterDraft)
    assert context.chapter_index == 2
    assert draft.chapter_index == 2


@pytest.mark.parametrize(
    ("prompt_marker", "method_name", "model_name"),
    [
        (ARCHITECT_PROMPT, "run_architect", "ArchitectOutline"),
        (WORLD_BUILDER_PROMPT, "run_world_builder", "WorldBible"),
        (DIRECTOR_PROMPT, "run_director", "DirectorPlan"),
        (CHARACTER_SIMULATOR_PROMPT, "run_character_simulator", "SimulationLog"),
        (DRAMA_COACH_PROMPT, "run_drama_coach", "DramaRevision"),
        (DEPENDENCY_MANAGER_PROMPT, "run_dependency_manager", "DependencyReview"),
        (QUALITY_EVALUATOR_PROMPT, "run_quality_evaluator", "StoryEvaluation"),
        (QUALITY_REWRITER_PROMPT, "run_quality_rewriter", "FinalStory"),
        (NARRATOR_PROMPT, "run_narrator", "FinalStory"),
    ],
)
def test_story_agents_reject_invalid_payloads(
    prompt_marker: str,
    method_name: str,
    model_name: str,
) -> None:
    agents = StoryAgents(FakeGeminiClient(invalid_payload_for=prompt_marker))
    packet = build_packet()

    with pytest.raises(RuntimeError, match=f"Invalid payload for {model_name}"):
        asyncio.run(getattr(agents, method_name)(packet))


@pytest.mark.parametrize(
    ("prompt_marker", "runner", "model_name"),
    [
        (PLOT_WEAVER_PROMPT, lambda agents, packet: agents.run_plot_weaver(packet, 3), "PlotWeave"),
        (
            COORDINATOR_PROMPT,
            lambda agents, packet: agents.run_coordinator(
                packet,
                asyncio.run(agents.run_plot_weaver(packet, 1)).chapter_plan.chapters[0],
            ),
            "ContextSummary",
        ),
        (
            CHAPTER_WRITER_PROMPT,
            lambda agents, packet: agents.run_chapter_writer(
                packet,
                ContextSummary(
                    chapter_index=1,
                    relevant_events=["E1"],
                    summary="Contexto",
                    continuity_constraints=["Regla"],
                ),
            ),
            "ChapterDraft",
        ),
    ],
)
def test_contextual_story_agents_reject_invalid_payloads(prompt_marker: str, runner, model_name: str) -> None:
    agents = StoryAgents(FakeGeminiClient(invalid_payload_for=prompt_marker))
    packet = build_packet()

    with pytest.raises(RuntimeError, match=f"Invalid payload for {model_name}"):
        asyncio.run(runner(agents, packet))

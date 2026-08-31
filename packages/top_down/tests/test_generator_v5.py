import json

import pytest
from asg_top_down import StoryGenerator
from asg_top_down.agents import AnalystAgent
from asg_top_down.audit import parse_chapter_bodies
from asg_top_down.errors import PlotValidationError
from asg_top_down.schemas import (
    ChapterDraft,
    ChapterPresentation,
    CharacterProfile,
    CharactersArtifact,
    EventDependency,
    Location,
    PlanReview,
    PlotEvent,
    RevisionNote,
    StoryPlanDraft,
    StoryPresentation,
    StoryRequest,
    StoryReview,
    WorldArtifact,
)


def make_request() -> StoryRequest:
    return StoryRequest(
        original_prompt="Escribe 600 palabras en dos capítulos",
        processed_prompt="Write a two-chapter story about a difficult truth.",
        title="The Price of Truth",
        language="Spanish",
        genre="drama",
        tone="tense",
        target_words=600,
        requested_chapters=2,
        premise="Ana discovers a dangerous truth.",
        constraints=["The story must have two chapters"],
        creative_directions=["Give Ana an earned, hopeful resolution"],
    )


def make_world() -> WorldArtifact:
    return WorldArtifact(
        setting="A coastal town",
        time_period="Present",
        rules=["The archive closes at dusk"],
        locations=[Location(id="archive", name="Archive", description="An old archive")],
        atmosphere="Tense",
    )


def make_characters() -> CharactersArtifact:
    return CharactersArtifact(
        characters=[
            CharacterProfile(
                id="ana",
                name="Ana",
                role="protagonist",
                goal="Reveal the truth",
                motivation="Protect her sister",
                conflict="Revelation risks her home",
                arc="Learns to trust others",
                voice="Precise and restrained",
            )
        ]
    )


def chapter(identifier: str, order: int, title: str) -> ChapterDraft:
    return ChapterDraft(
        id=identifier,
        order=order,
        title=title,
        summary=f"Summary for {title}",
        dramatic_goal="Force Ana to make a consequential choice",
        opening_state="Ana lacks decisive evidence",
        turning_point="Ana discovers proof that changes her options",
        closing_state="Ana accepts the next consequence",
    )


def plot_event(identifier: str, order: int, chapter_id: str) -> PlotEvent:
    return PlotEvent(
        id=identifier,
        order=order,
        chapter_id=chapter_id,
        title=identifier,
        description=f"Description for {identifier}",
        purpose="Advance the central conflict",
        dramatic_function="Escalate Ana's moral choice",
        conflict="Truth threatens Ana's family",
        outcome="Ana gains evidence and accepts a cost",
        character_ids=["ana"],
        location_id="archive",
        effects=["Ana's knowledge and options change"],
    )


def valid_plan(*, ending: str = "The town chooses to rebuild together") -> StoryPlanDraft:
    return StoryPlanDraft(
        logline="Ana reveals a dangerous truth",
        theme="Truth and solidarity",
        ending=ending,
        narrative_structure="Compact three-act structure",
        dramatic_question="Will Ana reveal the truth despite its cost?",
        stakes="Ana may lose her home and sister's trust",
        chapters=[
            chapter("chapter-1", 1, "The Archive"),
            chapter("chapter-2", 2, "The Choice"),
        ],
        events=[
            plot_event("event-1", 1, "chapter-1"),
            plot_event("event-2", 2, "chapter-2"),
        ],
        dependencies=[
            EventDependency(
                source_event_id="event-1",
                target_event_id="event-2",
                relation="causal",
            )
        ],
    )


def invalid_plan() -> StoryPlanDraft:
    candidate = valid_plan()
    candidate.events[0].character_ids = ["missing"]
    return candidate


def invalid_payoff_plan() -> StoryPlanDraft:
    candidate = valid_plan()
    candidate.events[1].payoff_of = ["charcoal_note"]
    return candidate


def rejected_plan_review() -> PlanReview:
    return PlanReview(
        approved=False,
        notes=[
            RevisionNote(
                id="plan-note-1",
                priority="major",
                category="dramatic_structure",
                evidence="The ending resolves too easily.",
                instruction="Make Ana pay a visible cost before the resolution.",
                chapter_ids=["chapter-2"],
                event_ids=["event-2"],
            )
        ],
    )


def major_story_review() -> StoryReview:
    return StoryReview(
        strengths=["The causal line is clear."],
        notes=[
            RevisionNote(
                id="story-note-1",
                priority="major",
                category="character_motivation",
                evidence="Ana's decision is asserted rather than dramatized.",
                instruction="Dramatize the decision through action and consequence.",
            )
        ],
    )


def prose(label: str, words: int = 300) -> str:
    return " ".join(f"{label}{index}" for index in range(words))


class FakeProvider:
    model_name = "fake-model"

    def __init__(
        self,
        plans=None,
        *,
        fail_quality=False,
        plan_review: PlanReview | None = None,
        story_review: StoryReview | None = None,
        writer_identical_once=False,
        fail_writer_call: int | None = None,
    ) -> None:
        self.plans = list(plans or [valid_plan()])
        self.fail_quality = fail_quality
        self.plan_review = plan_review or PlanReview(approved=True)
        self.story_review = story_review or StoryReview(strengths=["Clear progression"])
        self.writer_identical_once = writer_identical_once
        self.fail_writer_call = fail_writer_call
        self.usage_records = []
        self.usage_callback = None
        self.wait_callback = None
        self.structured_calls = []
        self.text_calls = []
        self.draft_number = 0
        self.writer_number = 0

    def generate_structured(self, *, system_instruction, prompt, schema):
        self.structured_calls.append((schema.__name__, system_instruction, prompt))
        if schema is WorldArtifact:
            return make_world()
        if schema is CharactersArtifact:
            return make_characters()
        if schema is StoryPlanDraft:
            return self.plans.pop(0)
        if schema is PlanReview:
            return self.plan_review
        if schema is StoryPresentation:
            return StoryPresentation(
                title="El precio de la verdad",
                chapters=[
                    ChapterPresentation(chapter_id="chapter-1", title="El archivo"),
                    ChapterPresentation(chapter_id="chapter-2", title="La elección"),
                ],
            )
        if schema is StoryReview:
            if self.fail_quality:
                raise RuntimeError("review unavailable")
            return self.story_review
        if schema is StoryRequest:
            return make_request()
        raise AssertionError(schema)

    def generate_text(self, *, system_instruction, prompt):
        self.text_calls.append((system_instruction, prompt))
        if "final Writer" in system_instruction:
            self.writer_number += 1
            if self.fail_writer_call == self.writer_number:
                raise RuntimeError("writer unavailable")
            original = prompt.split("ORIGINAL CHAPTER BODY:\n", 1)[1].split(
                "\n\nRETRY CORRECTION:",
                1,
            )[0]
            if self.writer_identical_once and self.writer_number == 1:
                return original
            return prose(f"revisado{self.writer_number}-")
        self.draft_number += 1
        return prose(f"borrador{self.draft_number}-")


def test_complete_pipeline_saves_v51_artifacts_and_agent_order(tmp_path) -> None:
    provider = FakeProvider()
    progress = []
    events = []
    created = []
    run = StoryGenerator(provider, tmp_path).run(
        make_request(),
        on_progress=progress.append,
        on_event=events.append,
        on_run_created=created.append,
    )
    assert created == [run.run_dir]
    assert run.story_path.read_text(encoding="utf-8").startswith("# El precio")
    expected = {
        "generator_version.json",
        "request.json",
        "world.json",
        "characters.json",
        "plan_review.json",
        "story_plan.json",
        "draft_presentation.json",
        "draft.md",
        "review.json",
        "length_audit.json",
        "story.md",
        "metadata.json",
        "pipeline_manifest.json",
        "llm_usage.json",
    }
    assert expected <= {path.name for path in run.run_dir.iterdir()}
    for directory in ("chapters", "revisions"):
        assert (run.run_dir / directory / "chapter-001.md").is_file()
        assert (run.run_dir / directory / "chapter-002.md").is_file()
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["pipeline_version"] == "5.1"
    assert metadata["status"] == "completed"
    assert progress[-1].percent == 100
    agent_names = [
        event.message.rsplit(" ", 1)[-1] for event in events if event.kind == "agent_called"
    ]
    assert agent_names[-6:] == [
        "drafter",
        "drafter",
        "drafter",
        "drama_critic",
        "writer",
        "writer",
    ]


def test_invalid_initial_plan_is_replaced_once(tmp_path) -> None:
    provider = FakeProvider([invalid_plan(), valid_plan()])
    run = StoryGenerator(provider, tmp_path).run(make_request())
    assert (run.run_dir / "planning" / "attempt-001.json").is_file()
    plan_calls = [item for item in provider.structured_calls if item[0] == "StoryPlanDraft"]
    assert len(plan_calls) == 2
    assert "unknown characters" in plan_calls[1][2]


def test_invalid_payoff_retry_receives_exact_reference_matrix(tmp_path) -> None:
    provider = FakeProvider([invalid_payoff_plan(), valid_plan()])
    StoryGenerator(provider, tmp_path).run(make_request())
    plan_calls = [item for item in provider.structured_calls if item[0] == "StoryPlanDraft"]
    assert len(plan_calls) == 2
    assert "PAYOFF_OF CONTRACT" in plan_calls[0][1]
    retry_prompt = plan_calls[1][2]
    assert "charcoal_note" in retry_prompt
    assert "PAYOFF_OF REFERENCE MATRIX" in retry_prompt
    assert '"event_id": "event-2"' in retry_prompt
    assert '"allowed_earlier_event_ids"' in retry_prompt
    assert '"event-1"' in retry_prompt
    assert "Never copy object IDs" in retry_prompt


def test_two_invalid_plans_fail_with_public_error(tmp_path) -> None:
    provider = FakeProvider([invalid_plan(), invalid_plan()])
    created = []
    with pytest.raises(PlotValidationError) as captured:
        StoryGenerator(provider, tmp_path).run(make_request(), on_run_created=created.append)
    assert captured.value.code == "PLOT_VALIDATION_FAILED"
    metadata = json.loads((created[0] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert metadata["error_code"] == "PLOT_VALIDATION_FAILED"


def test_plan_critic_refines_once_and_invalid_refinement_falls_back(tmp_path) -> None:
    refined = valid_plan(ending="Ana reveals the truth and loses her home")
    provider = FakeProvider(
        [valid_plan(), refined],
        plan_review=rejected_plan_review(),
    )
    run = StoryGenerator(provider, tmp_path / "accepted").run(make_request())
    saved = json.loads((run.run_dir / "story_plan.json").read_text(encoding="utf-8"))
    assert saved["ending"] == refined.ending
    assert (run.run_dir / "planning" / "refined-candidate.json").is_file()

    fallback_provider = FakeProvider(
        [valid_plan(), invalid_plan()],
        plan_review=rejected_plan_review(),
    )
    fallback = StoryGenerator(fallback_provider, tmp_path / "fallback").run(make_request())
    saved = json.loads((fallback.run_dir / "story_plan.json").read_text(encoding="utf-8"))
    metadata = json.loads((fallback.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert saved["ending"] == valid_plan().ending
    assert "reemplazo estructuralmente inválido" in metadata["warnings"][0]


def test_late_critic_failure_delivers_the_draft_with_warning(tmp_path) -> None:
    run = StoryGenerator(FakeProvider(fail_quality=True), tmp_path).run(make_request())
    assert run.story_path.read_text(encoding="utf-8") == (run.run_dir / "draft.md").read_text(
        encoding="utf-8"
    )
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert "borrador" in metadata["warnings"][0]


def test_drafter_receives_dag_history_and_previous_chapter(tmp_path) -> None:
    provider = FakeProvider()
    StoryGenerator(provider, tmp_path).run(make_request())
    draft_calls = [item for item in provider.text_calls if "first-draft fiction chapter" in item[0]]
    assert len(draft_calls) == 2
    assert "RELEVANT PRIOR EVENTS:\n[]" in draft_calls[0][1]
    assert '"id": "event-1"' in draft_calls[1][1]
    assert "borrador1-0" in draft_calls[1][1]


def test_writer_retries_unchanged_major_revision_and_saves_attempt(tmp_path) -> None:
    provider = FakeProvider(
        story_review=major_story_review(),
        writer_identical_once=True,
    )
    run = StoryGenerator(provider, tmp_path).run(make_request())
    writer_calls = [item for item in provider.text_calls if "final Writer" in item[0]]
    assert len(writer_calls) == 3
    assert (run.run_dir / "writer" / "chapter-001-attempt-001.md").is_file()
    assert "RETRY CORRECTION" in writer_calls[1][1]


def test_writer_failure_is_isolated_to_its_chapter(tmp_path) -> None:
    provider = FakeProvider(fail_writer_call=2)
    run = StoryGenerator(provider, tmp_path).run(make_request())
    draft_bodies = parse_chapter_bodies(
        (run.run_dir / "draft.md").read_text(encoding="utf-8"),
        2,
    )
    final_bodies = parse_chapter_bodies(run.story_path.read_text(encoding="utf-8"), 2)
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert final_bodies[0] != draft_bodies[0]
    assert final_bodies[1] == draft_bodies[1]
    assert "capítulo 2" in metadata["warnings"][0]


def test_analyst_prompt_separates_explicit_constraints_and_inferences() -> None:
    provider = FakeProvider()
    raw = "Crea una historia de un caballero que salva a una princesa de un dragón"
    result = AnalystAgent(provider, default_target_words=1500).run(raw)
    call = next(item for item in provider.structured_calls if item[0] == "StoryRequest")
    assert result.original_prompt == raw
    assert result.language == "Spanish"
    assert "creative_directions" in call[1]
    assert "constraints must contain only requirements explicitly stated" in call[1]
    assert "working title" in call[1]


def test_internal_agents_use_english_until_drafting(tmp_path) -> None:
    provider = FakeProvider()
    run = StoryGenerator(provider, tmp_path).run(make_request())
    request = json.loads((run.run_dir / "request.json").read_text(encoding="utf-8"))
    plan = json.loads((run.run_dir / "story_plan.json").read_text(encoding="utf-8"))
    presentation = json.loads((run.run_dir / "draft_presentation.json").read_text(encoding="utf-8"))
    assert request["title"] == "The Price of Truth"
    assert [item["title"] for item in plan["chapters"]] == ["The Archive", "The Choice"]
    assert presentation["title"] == "El precio de la verdad"
    critic_system = next(
        system for name, system, _ in provider.structured_calls if name == "StoryReview"
    )
    assert "return coordinated revision notes in English" in critic_system
    assert all(
        "Spanish" in system
        for system, _ in provider.text_calls
        if "Drafter" in system or "final Writer" in system
    )


def test_final_chapter_parser_requires_every_heading() -> None:
    story = "# Título\n\n## Uno\n\nPrimero.\n\n## Dos\n\nSegundo."
    assert parse_chapter_bodies(story, 2) == ["Primero.", "Segundo."]
    assert parse_chapter_bodies(story, 3) == []

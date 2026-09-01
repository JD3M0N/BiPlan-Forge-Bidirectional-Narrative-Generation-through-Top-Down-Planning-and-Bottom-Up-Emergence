import json

import pytest
from asg_core import AudioGenerationError
from asg_top_down import NarrativeProfile, StoryGenerator
from asg_top_down import pipeline as pipeline_module
from asg_top_down.agents import AnalystAgent
from asg_top_down.audit import parse_chapter_bodies
from asg_top_down.errors import PlotValidationError
from asg_top_down.pipeline import StoryPipeline
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
from pydantic import ValidationError


def make_request() -> StoryRequest:
    return StoryRequest(
        original_prompt="Escribe una historia con perfil narrativo Desarrollada",
        processed_prompt="Write a developed story about a difficult truth.",
        title="The Price of Truth",
        language="Spanish",
        genre="drama",
        tone="tense",
        narrative_profile="developed",
        premise="Ana discovers a dangerous truth.",
        constraints=[],
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
        writer_outputs: list[str] | None = None,
        analyzed_request: StoryRequest | None = None,
    ) -> None:
        self.plans = list(plans or [valid_plan()])
        self.fail_quality = fail_quality
        self.plan_review = plan_review or PlanReview(approved=True)
        self.story_review = story_review or StoryReview(strengths=["Clear progression"])
        self.writer_identical_once = writer_identical_once
        self.fail_writer_call = fail_writer_call
        self.writer_outputs = list(writer_outputs) if writer_outputs is not None else None
        self.analyzed_request = analyzed_request or make_request()
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
            return self.analyzed_request
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
            if self.writer_outputs is not None:
                return self.writer_outputs.pop(0)
            return prose(f"revisado{self.writer_number}-")
        self.draft_number += 1
        return prose(f"borrador{self.draft_number}-")


def test_complete_pipeline_saves_v60_artifacts_and_agent_order(tmp_path) -> None:
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
        "revision_report.json",
        "story_metrics.json",
        "story.md",
        "story.mp3",
        "audio.json",
        "metadata.json",
        "pipeline_manifest.json",
        "llm_usage.json",
    }
    assert expected <= {path.name for path in run.run_dir.iterdir()}
    for directory in ("chapters", "revisions"):
        assert (run.run_dir / directory / "chapter-001.md").is_file()
        assert (run.run_dir / directory / "chapter-002.md").is_file()
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["pipeline_version"] == "6.0"
    assert metadata["status"] == "completed"
    assert run.audio_path.is_file()
    manifest = json.loads((run.run_dir / "pipeline_manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifacts"]["story.mp3"]["bytes"] == len(b"fake-mp3")
    report = json.loads((run.run_dir / "revision_report.json").read_text(encoding="utf-8"))
    assert [chapter["final_source"] for chapter in report["chapters"]] == [
        "revision",
        "revision",
    ]
    metrics = json.loads((run.run_dir / "story_metrics.json").read_text(encoding="utf-8"))
    assert metrics["narrative_profile"] == "developed"
    assert metrics["chapters"] == 2
    assert metrics["events"] == 2
    assert metrics["words"] > 0
    assert {item["events"] for item in metrics["chapter_metrics"]} == {1}
    assert "target_words" not in json.dumps(metrics)
    assert "within_tolerance" not in json.dumps(metrics)
    for index in (1, 2):
        attempt = run.run_dir / "writer" / f"chapter-{index:03d}-attempt-001.md"
        validation = attempt.with_name(attempt.stem + "-validation.json")
        assert attempt.is_file()
        assert json.loads(validation.read_text(encoding="utf-8"))["status"] == "accepted"
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


def test_audio_failure_keeps_top_down_run_completed(tmp_path, monkeypatch) -> None:
    def fail_audio(story_path):
        (story_path.parent / "audio.json").write_text(
            json.dumps(
                {
                    "status": "failed",
                    "language": "es",
                    "voice": "fallback",
                    "error": "OSError",
                }
            ),
            encoding="utf-8",
        )
        raise AudioGenerationError("tts unavailable")

    monkeypatch.setattr(pipeline_module, "create_story_audio_sync", fail_audio)

    run = StoryGenerator(FakeProvider(), tmp_path).run(make_request())

    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert any("[AUDIO_GENERATION_FAILED]" in warning for warning in metadata["warnings"])
    assert not run.audio_path.exists()
    assert (run.run_dir / "audio.json").is_file()


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


@pytest.mark.parametrize(
    ("candidate", "expected_code"),
    [
        ("", "EMPTY_CHAPTER_BODY"),
        ("# Encabezado\n\n" + prose("texto-", 300), "MARKDOWN_HEADINGS"),
    ],
)
def test_writer_candidate_diagnostics_are_structured(
    candidate,
    expected_code,
) -> None:
    diagnostic = StoryPipeline._writer_candidate_issue(
        candidate,
        prose("original-", 300),
        [],
    )
    assert diagnostic is not None
    assert diagnostic.code == expected_code
    assert diagnostic.actual_words == len(candidate.split())
    assert diagnostic.retry_instruction


def test_writer_reports_unchanged_significant_revision() -> None:
    draft = prose("original-", 300)
    diagnostic = StoryPipeline._writer_candidate_issue(
        draft,
        draft,
        major_story_review().notes,
    )
    assert diagnostic is not None
    assert diagnostic.code == "UNCHANGED_SIGNIFICANT_NOTES"


def test_writer_accepts_different_lengths_without_budget_retries(tmp_path) -> None:
    provider = FakeProvider(
        writer_outputs=[
            prose("corto-a-", 100),
            prose("largo-", 500),
        ]
    )
    run = StoryGenerator(provider, tmp_path).run(make_request())
    report = json.loads((run.run_dir / "revision_report.json").read_text(encoding="utf-8"))
    assert [chapter["final_source"] for chapter in report["chapters"]] == [
        "revision",
        "revision",
    ]
    assert [chapter["final_words"] for chapter in report["chapters"]] == [100, 500]
    assert all(chapter["attempts"][0]["status"] == "accepted" for chapter in report["chapters"])
    writer_calls = [item for item in provider.text_calls if "final Writer" in item[0]]
    assert len(writer_calls) == 2
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert not any("longitud" in warning.casefold() for warning in metadata["warnings"])


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
    report = json.loads((run.run_dir / "revision_report.json").read_text(encoding="utf-8"))
    failed = report["chapters"][1]
    assert failed["final_source"] == "draft"
    assert failed["attempts"][0]["status"] == "failed"
    assert failed["attempts"][0]["exception_type"] == "RuntimeError"


def test_analyst_prompt_separates_explicit_constraints_and_inferences() -> None:
    analyzed = make_request().model_copy(
        update={
            "processed_prompt": "Write a story of 1500 words in 5 chapters.",
            "premise": "A revelation unfolds across 5 chapters.",
            "constraints": ["Use 1500 words", "Keep the hopeful ending"],
            "creative_directions": ["Develop the conflict across 5 chapters"],
        }
    )
    provider = FakeProvider(analyzed_request=analyzed)
    raw = (
        "Perfil narrativo: Expansiva. Crea una historia de 1500 palabras y 5 capítulos "
        "sobre un caballero."
    )
    result = AnalystAgent(provider).run(raw)
    call = next(item for item in provider.structured_calls if item[0] == "StoryRequest")
    assert result.original_prompt == raw
    assert result.language == "Spanish"
    assert result.narrative_profile.value == "expansive"
    downstream = json.dumps(result.agent_spec())
    assert "1500" not in downstream
    assert "5 chapters" not in downstream
    assert result.constraints == ["Keep the hopeful ending"]
    assert "creative_directions" in call[1]
    assert "constraints contain only explicit requirements" in call[1]
    assert "working title" in call[1]
    assert "when ambiguous use developed" in call[1]


@pytest.mark.parametrize(
    ("profile", "raw"),
    [
        ("essential", "Un conflicto central directo y sin subtramas."),
        ("developed", "Una historia con arco completo y complicaciones."),
        ("expansive", "Una saga coral con subtramas y varios arcos."),
    ],
)
def test_analyst_preserves_inferred_profile(profile, raw) -> None:
    analyzed = make_request().model_copy(
        update={"narrative_profile": NarrativeProfile(profile)}
    )
    result = AnalystAgent(FakeProvider(analyzed_request=analyzed)).run(raw)
    assert result.narrative_profile.value == profile


def test_programmatic_request_rejects_legacy_numeric_fields() -> None:
    values = make_request().model_dump()
    values["target_words"] = 1500
    with pytest.raises(ValidationError, match="target_words"):
        StoryRequest.model_validate(values)


def test_internal_agents_use_english_until_drafting(tmp_path) -> None:
    provider = FakeProvider()
    run = StoryGenerator(provider, tmp_path).run(make_request())
    request = json.loads((run.run_dir / "request.json").read_text(encoding="utf-8"))
    plan = json.loads((run.run_dir / "story_plan.json").read_text(encoding="utf-8"))
    presentation = json.loads((run.run_dir / "draft_presentation.json").read_text(encoding="utf-8"))
    assert request["title"] == "The Price of Truth"
    assert request["narrative_profile"] == "developed"
    assert [item["title"] for item in plan["chapters"]] == ["The Archive", "The Choice"]
    assert presentation["title"] == "El precio de la verdad"
    critic_system = next(
        system for name, system, _ in provider.structured_calls if name == "StoryReview"
    )
    assert "return coordinated revision notes in English" in critic_system
    all_calls = json.dumps(provider.structured_calls) + json.dumps(provider.text_calls)
    assert "EXACT EVENT COUNTS" not in all_calls
    assert "word budget" not in all_calls
    assert all(
        "Spanish" in system
        for system, _ in provider.text_calls
        if "Drafter" in system or "final Writer" in system
    )


def test_final_chapter_parser_requires_every_heading() -> None:
    story = "# Título\n\n## Uno\n\nPrimero.\n\n## Dos\n\nSegundo."
    assert parse_chapter_bodies(story, 2) == ["Primero.", "Segundo."]
    assert parse_chapter_bodies(story, 3) == []

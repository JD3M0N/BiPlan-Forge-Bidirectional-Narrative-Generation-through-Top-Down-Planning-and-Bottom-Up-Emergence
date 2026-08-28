import json

import pytest
from asg_top_down import StoryGenerator
from asg_top_down.audit import parse_chapter_bodies
from asg_top_down.errors import PlotValidationError
from asg_top_down.schemas import (
    ChapterDraft,
    CharacterProfile,
    CharactersArtifact,
    EventDependency,
    Location,
    PlotEvent,
    StoryPlanDraft,
    StoryRequest,
    StoryReview,
    WorldArtifact,
)


def make_request() -> StoryRequest:
    return StoryRequest(
        original_prompt="Escribe 600 palabras en dos capítulos",
        processed_prompt="Write a two-chapter story about a difficult truth.",
        title="El precio de la verdad",
        language="Spanish",
        genre="drama",
        tone="tense",
        target_words=600,
        requested_chapters=2,
        premise="Ana discovers a dangerous truth.",
        constraints=["The ending must be hopeful"],
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


def plot_event(identifier: str, order: int, chapter_id: str) -> PlotEvent:
    return PlotEvent(
        id=identifier,
        order=order,
        chapter_id=chapter_id,
        title=identifier,
        description=f"Description for {identifier}",
        purpose="Advance the central conflict",
        character_ids=["ana"],
        location_id="archive",
        effects=["Ana's situation changes"],
    )


def valid_plan() -> StoryPlanDraft:
    return StoryPlanDraft(
        logline="Ana reveals a dangerous truth",
        theme="Truth and solidarity",
        ending="The town chooses to rebuild together",
        chapters=[
            ChapterDraft(id="chapter-1", order=1, title="El archivo", summary="Discovery"),
            ChapterDraft(id="chapter-2", order=2, title="La elección", summary="Resolution"),
        ],
        events=[
            plot_event("event-1", 1, "chapter-1"),
            plot_event("event-2", 2, "chapter-1"),
            plot_event("event-3", 3, "chapter-2"),
        ],
        dependencies=[
            EventDependency(
                source_event_id="event-1",
                target_event_id="event-2",
                relation="causal",
            ),
            EventDependency(
                source_event_id="event-2",
                target_event_id="event-3",
                relation="causal",
            ),
        ],
    )


def invalid_plan() -> StoryPlanDraft:
    candidate = valid_plan()
    candidate.events[0].character_ids = ["missing"]
    return candidate


class FakeProvider:
    model_name = "fake-model"

    def __init__(self, plans=None, *, fail_quality=False) -> None:
        self.plans = list(plans or [valid_plan()])
        self.fail_quality = fail_quality
        self.usage_records = []
        self.usage_callback = None
        self.wait_callback = None
        self.structured_calls = []
        self.text_calls = []
        self.chapter_number = 0

    def generate_structured(self, *, system_instruction, prompt, schema):
        self.structured_calls.append((schema.__name__, prompt))
        if schema is WorldArtifact:
            return make_world()
        if schema is CharactersArtifact:
            return make_characters()
        if schema is StoryPlanDraft:
            return self.plans.pop(0)
        if schema is StoryReview:
            if self.fail_quality:
                raise RuntimeError("review unavailable")
            return StoryReview(
                strengths=["Clear progression"],
                issues=["Tighten the ending"],
                revision_instructions=["Make the final choice more concrete"],
            )
        if schema is StoryRequest:
            return make_request()
        raise AssertionError(schema)

    def generate_text(self, *, system_instruction, prompt):
        self.text_calls.append((system_instruction, prompt))
        if "Edit the complete story" in system_instruction:
            return "# El precio de la verdad\n\n## El archivo\n\nVersión editada."
        self.chapter_number += 1
        return f"Texto narrativo del capítulo {self.chapter_number}."


def test_complete_pipeline_saves_small_v5_artifact_set(tmp_path) -> None:
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
        "story_plan.json",
        "draft.md",
        "review.json",
        "length_audit.json",
        "story.md",
        "metadata.json",
        "pipeline_manifest.json",
        "llm_usage.json",
    }
    assert expected <= {path.name for path in run.run_dir.iterdir()}
    assert (run.run_dir / "chapters" / "chapter-001.md").is_file()
    assert (run.run_dir / "chapters" / "chapter-002.md").is_file()
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["pipeline_version"] == "5.0"
    assert metadata["status"] == "completed"
    assert progress[-1].percent == 100
    assert {event.kind for event in events} >= {"agent_called", "artifact_created"}


def test_invalid_plan_is_replaced_once(tmp_path) -> None:
    provider = FakeProvider([invalid_plan(), valid_plan()])
    run = StoryGenerator(provider, tmp_path).run(make_request())
    assert (run.run_dir / "planning" / "attempt-001.json").is_file()
    assert sum(name == "StoryPlanDraft" for name, _ in provider.structured_calls) == 2
    second_prompt = [
        prompt for name, prompt in provider.structured_calls if name == "StoryPlanDraft"
    ][1]
    assert "unknown characters" in second_prompt


def test_two_invalid_plans_fail_with_public_error(tmp_path) -> None:
    provider = FakeProvider([invalid_plan(), invalid_plan()])
    created = []
    with pytest.raises(PlotValidationError) as captured:
        StoryGenerator(provider, tmp_path).run(make_request(), on_run_created=created.append)
    assert captured.value.code == "PLOT_VALIDATION_FAILED"
    metadata = json.loads((created[0] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert metadata["error_code"] == "PLOT_VALIDATION_FAILED"


def test_late_review_failure_delivers_the_draft_with_warning(tmp_path) -> None:
    run = StoryGenerator(FakeProvider(fail_quality=True), tmp_path).run(make_request())
    assert run.story_path.read_text(encoding="utf-8") == (run.run_dir / "draft.md").read_text(
        encoding="utf-8"
    )
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert "borrador" in metadata["warnings"][0]


def test_writer_receives_only_relevant_context_and_previous_chapter(tmp_path) -> None:
    provider = FakeProvider()
    StoryGenerator(provider, tmp_path).run(make_request())
    chapter_calls = [item for item in provider.text_calls if "chapter body" in item[0]]
    assert len(chapter_calls) == 2
    assert "PREVIOUS CHAPTER:\nnone" in chapter_calls[0][1]
    assert "Texto narrativo del capítulo 1" in chapter_calls[1][1]


def test_final_chapter_parser_requires_every_heading() -> None:
    story = "# Título\n\n## Uno\n\nPrimero.\n\n## Dos\n\nSegundo."
    assert parse_chapter_bodies(story, 2) == ["Primero.", "Segundo."]
    assert parse_chapter_bodies(story, 3) == []

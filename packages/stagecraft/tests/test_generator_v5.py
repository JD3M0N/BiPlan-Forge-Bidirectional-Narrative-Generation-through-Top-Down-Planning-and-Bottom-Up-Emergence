import json
import re
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from asg_core import AudioGenerationError, slugify
from asg_stagecraft import NarrativeProfile, StoryGenerator
from asg_stagecraft import pipeline as pipeline_module
from asg_stagecraft import version as version_module
from asg_stagecraft.agents import AnalystAgent
from asg_stagecraft.pipeline import StoryPipeline
from asg_stagecraft.planning.graph import materialize_plan, validate_profile_structure
from asg_stagecraft.planning.profiles import profile_event_floor, promise_band
from asg_stagecraft.planning.repair import repair_guidance
from asg_stagecraft.runtime import storage as storage_module
from asg_stagecraft.runtime.errors import GeminiDailyQuotaError, PlotValidationError
from asg_stagecraft.runtime.provider import current_call_context
from asg_stagecraft.schemas import (
    ActScriptDraft,
    CastNote,
    ChapterDraft,
    ChapterPresentation,
    CharacterProfile,
    CharactersArtifact,
    EventDependency,
    LLMUsageRecord,
    Location,
    NarrativeBlueprintDraft,
    PlanReview,
    PlotEvent,
    PromiseCheck,
    PromiseContract,
    PromiseLedgerDraft,
    PromiseOpening,
    PromisePayoff,
    PromiseProgress,
    RevisionNote,
    SceneCastMember,
    ScriptFrame,
    ScriptLine,
    ScriptPresentation,
    ScriptSceneDraft,
    SemanticSkeletonRanking,
    SemanticSkeletonScore,
    StoryPlanDraft,
    StoryPresentation,
    StoryRequest,
    StoryReview,
    WorldArtifact,
)
from asg_stagecraft.writing.acceptance import writer_candidate_issue
from asg_stagecraft.writing.audit import parse_chapter_bodies
from asg_stagecraft.writing.craft_evidence import NO_DIALOGUE, RARE_DIALOGUE

# A qualitative fragment of the Developed contract. PROFILE_GUIDANCE carries no event count
# any more, so the tests that follow the profile contract downstream track this instead.
PROFILE_MARKER = "a functional secondary arc"


def make_request() -> StoryRequest:
    return StoryRequest(
        original_prompt="Escribe una historia con perfil narrativo Esencial",
        processed_prompt="Write an essential story about a difficult truth.",
        title="The Price of Truth",
        language="Spanish",
        genre="drama",
        tone="tense",
        narrative_profile="essential",
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
            plot_event("event-2", 2, "chapter-1"),
            plot_event("event-3", 3, "chapter-2"),
            plot_event("event-4", 4, "chapter-2"),
        ],
        dependencies=[
            EventDependency(
                source_event_id=f"event-{order}",
                target_event_id=f"event-{order + 1}",
                relation="causal",
            )
            for order in range(1, 4)
        ],
    )


PROMISE_KINDS = ("story_direction", "character_conflict", "genre_structure", "tone")


def _profile_in(prompt: str) -> str:
    """Read back the profile the ledger prompt carries, so the fake ledger matches its band."""
    for profile in NarrativeProfile:
        if f'"narrative_profile": "{profile.value}"' in prompt:
            return profile.value
    return "essential"


def promise_ledger(plan: StoryPlanDraft, profile: str = "essential") -> PromiseLedgerDraft:
    """Draw the smallest ledger the profile accepts over one plan, anchored to its own events."""
    events = sorted(plan.events, key=lambda item: item.order)
    low, _ = promise_band(NarrativeProfile(profile))
    promises = []
    for index in range(low):
        # The primary promise pays off last, in the final chapter; the rest land earlier, which
        # keeps every anchor strictly between the shared opening and its own payoff.
        payoff_event = events[-1] if index == 0 else events[index + 1]
        promises.append(
            PromiseContract(
                id=f"promise-{index + 1}",
                kind=PROMISE_KINDS[index % len(PROMISE_KINDS)],
                subject=f"Subject of promise {index + 1}",
                dramatic_question=f"Will promise {index + 1} be answered?",
                opening=PromiseOpening(
                    event_id=events[0].id,
                    signal="Ana notices the missing signature.",
                    reader_expectation="that the archive will be opened",
                ),
                progress=[
                    PromiseProgress(
                        id=f"progress-{index + 1}",
                        event_id=events[1].id,
                        observable_delta="Ana reaches a door she could not open before.",
                        new_cost_or_information="She owes the favor to the wrong person.",
                    )
                ],
                payoff=PromisePayoff(
                    event_id=payoff_event.id,
                    answer="Ana opens the archive in front of everyone.",
                    cost="She loses her sister's trust.",
                    prepared_by_progress_ids=[f"progress-{index + 1}"],
                    surprising_without_breach="The witness she feared becomes her proof.",
                ),
            )
        )
    return PromiseLedgerDraft(primary_promise_id="promise-1", promises=promises)


def promise_checks(ledger: PromiseLedgerDraft, verdict: str = "fulfilled") -> list[PromiseCheck]:
    """Answer every promise of one ledger with the same verdict."""
    return [
        PromiseCheck(
            promise_id=promise.id,
            opened=True,
            progressed=True,
            paid=verdict == "fulfilled",
            verdict=verdict,
            evidence="Ana abrio el archivo delante de todos.",
        )
        for promise in ledger.promises
    ]


def sized_plan(event_count: int, *, branch_and_join: bool = False) -> StoryPlanDraft:
    """Build a two-chapter plan with a requested valid event count."""
    candidate = valid_plan()
    first_chapter_events = event_count // 2
    candidate.events = [
        plot_event(
            f"event-{order}",
            order,
            "chapter-1" if order <= first_chapter_events else "chapter-2",
        )
        for order in range(1, event_count + 1)
    ]
    if branch_and_join:
        candidate.dependencies = [
            EventDependency(
                source_event_id="event-1", target_event_id="event-2", relation="causal"
            ),
            EventDependency(
                source_event_id="event-1", target_event_id="event-3", relation="causal"
            ),
            EventDependency(
                source_event_id="event-2", target_event_id="event-4", relation="causal"
            ),
            EventDependency(
                source_event_id="event-3", target_event_id="event-4", relation="causal"
            ),
            *[
                EventDependency(
                    source_event_id=f"event-{order}",
                    target_event_id=f"event-{order + 1}",
                    relation="causal",
                )
                for order in range(4, event_count)
            ],
        ]
    else:
        candidate.dependencies = [
            EventDependency(
                source_event_id=f"event-{order}",
                target_event_id=f"event-{order + 1}",
                relation="causal",
            )
            for order in range(1, event_count)
        ]
    return candidate


def invalid_plan() -> StoryPlanDraft:
    candidate = valid_plan()
    candidate.events[0].character_ids = ["missing"]
    return candidate


def invalid_payoff_plan() -> StoryPlanDraft:
    candidate = valid_plan()
    candidate.events[1].payoff_of = ["charcoal_note"]
    return candidate


def empty_chapter_plan() -> StoryPlanDraft:
    """Carry a chapter with no events at all, which validate_story_plan rejects upstream."""
    candidate = valid_plan()
    candidate.chapters.append(chapter("chapter-3", 3, "The Cost"))
    return candidate


def thin_chapter_plan() -> StoryPlanDraft:
    """Meet the Essential event floor while leaving two chapters carrying a single event."""
    candidate = sized_plan(4)
    candidate.chapters.append(chapter("chapter-3", 3, "The Cost"))
    candidate.events[1].chapter_id = "chapter-2"
    candidate.events[2].chapter_id = "chapter-2"
    candidate.events[3].chapter_id = "chapter-3"
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


def event_scoped_story_review() -> StoryReview:
    """A pacing note naming its events with chapter_ids empty, as the critic prompt asks."""
    return StoryReview(
        strengths=["The causal line is clear."],
        notes=[
            RevisionNote(
                id="story-note-1",
                priority="major",
                category="pacing",
                evidence="event-3 is summarized instead of staged.",
                instruction="Stage event-3 as a scene.",
                event_ids=["event-3"],
            )
        ],
    )


def prose(label: str, words: int = 300) -> str:
    return " ".join(f"{label}{index}" for index in range(words))


def barely_spoken_prose() -> str:
    # One spoken paragraph in ten: below the dialogue floor without reaching the block ceiling,
    # which is the shape of the live 6.6.0 case that first exercised this channel.
    spoken = "—Nadie mas lo sabe —dijo Ana."
    narrated = "Ana reviso el archivo sin decir una palabra mas en toda la tarde."
    return "\n\n".join([spoken, *[narrated] * 9])


def scene_prose(label: str = "escena") -> str:
    spoken = "—Nadie mas lo sabe —dijo Ana."
    return "\n\n".join([spoken, f"Ana cerro el archivo {label}."] * 4)


_ANCHOR_CHAPTER = re.compile(r"ACT ANCHOR INDEX \((\S+)\)")


def script_presentation() -> ScriptPresentation:
    """Localize titles and the printed-script frame for the two-chapter fixture plan."""
    return ScriptPresentation(
        title="El precio de la verdad",
        chapters=[
            ChapterPresentation(chapter_id="chapter-1", title="El archivo"),
            ChapterPresentation(chapter_id="chapter-2", title="La eleccion"),
        ],
        frame=ScriptFrame(
            cast_heading="Personajes",
            act_label="Acto",
            scene_label="Escena",
            cast=[CastNote(character_id="ana", description="archivista")],
        ),
    )


def script_frame() -> ScriptFrame:
    """Build a minimal printed-script frame, as the Script Adapter would create it."""
    return ScriptFrame(
        cast_heading="Personajes",
        act_label="Acto",
        scene_label="Escena",
        cast=[CastNote(character_id="ana", description="archivista")],
    )


def script_act(plan: StoryPlanDraft, chapter_id: str) -> ActScriptDraft:
    """Build the smallest valid act for one chapter: one scene per event, cast from its plan."""
    events = [
        event
        for event in sorted(plan.events, key=lambda item: item.order)
        if event.chapter_id == chapter_id
    ]
    scenes = []
    for event in events:
        cast_ids = event.character_ids or ["ana"]
        scenes.append(
            ScriptSceneDraft(
                event_ids=[event.id],
                location_id=event.location_id,
                setting=f"Escenario de {event.title}.",
                cast=[
                    SceneCastMember(character_id=item, objective=f"Resolve {event.id}")
                    for item in cast_ids
                ],
                lines=[
                    ScriptLine(kind="direction", actor_ids=cast_ids[:1], text="Entra en escena."),
                    ScriptLine(kind="dialogue", speaker_id=cast_ids[0], text="Nadie mas lo sabe."),
                ],
            )
        )
    return ActScriptDraft(scenes=scenes)


def _touched_act(draft: ActScriptDraft) -> ActScriptDraft:
    """Return a copy of a script act with its first dialogue line visibly changed."""
    scenes = [scene.model_copy(deep=True) for scene in draft.scenes]
    for scene in scenes:
        for line in scene.lines:
            if line.kind == "dialogue":
                line.text = f"{line.text} (revisado)"
                return ActScriptDraft(scenes=scenes)
    return ActScriptDraft(scenes=scenes)


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
        fail_writer_call: int | set[int] | None = None,
        writer_outputs: list[str] | None = None,
        analyzed_request: StoryRequest | None = None,
        quota_error_at: str | None = None,
        fail_semantic_ranking=False,
        fail_architect=False,
        drafter_outputs: list[str] | None = None,
        ledgers: list[PromiseLedgerDraft] | None = None,
        fail_promise_ledger=False,
        promise_verdict: str = "fulfilled",
        act_outputs: list[ActScriptDraft] | None = None,
        script_writer_outputs: list[ActScriptDraft] | None = None,
        script_writer_identical_once=False,
        fail_act_call: int | set[int] | None = None,
        fail_script_writer_call: int | set[int] | None = None,
        fail_script_critic=False,
        fail_script_frame=False,
    ) -> None:
        self.plans = list(plans or [valid_plan()])
        self.ledgers = list(ledgers) if ledgers is not None else None
        self.fail_promise_ledger = fail_promise_ledger
        self.promise_verdict = promise_verdict
        self.last_plan: StoryPlanDraft | None = None
        self.last_ledger: PromiseLedgerDraft | None = None
        self.fail_quality = fail_quality
        self.quota_error_at = quota_error_at
        self.plan_review = plan_review or PlanReview(approved=True)
        self.story_review = story_review or StoryReview(strengths=["Clear progression"])
        self.explicit_review = story_review is not None
        self.writer_identical_once = writer_identical_once
        if fail_writer_call is None:
            self.fail_writer_calls: set[int] = set()
        elif isinstance(fail_writer_call, int):
            self.fail_writer_calls = {fail_writer_call}
        else:
            self.fail_writer_calls = set(fail_writer_call)
        self.writer_outputs = list(writer_outputs) if writer_outputs is not None else None
        self.drafter_outputs = list(drafter_outputs) if drafter_outputs is not None else None
        self.analyzed_request = analyzed_request or make_request()
        self.fail_semantic_ranking = fail_semantic_ranking
        self.fail_architect = fail_architect
        self.usage_records = []
        self.usage_callback = None
        self.wait_callback = None
        self.structured_calls = []
        self.text_calls = []
        self.draft_number = 0
        self.writer_number = 0
        self.act_outputs = list(act_outputs) if act_outputs is not None else None
        self.script_writer_outputs = (
            list(script_writer_outputs) if script_writer_outputs is not None else None
        )
        self.script_writer_identical_once = script_writer_identical_once
        if fail_act_call is None:
            self.fail_act_calls: set[int] = set()
        elif isinstance(fail_act_call, int):
            self.fail_act_calls = {fail_act_call}
        else:
            self.fail_act_calls = set(fail_act_call)
        if fail_script_writer_call is None:
            self.fail_script_writer_calls: set[int] = set()
        elif isinstance(fail_script_writer_call, int):
            self.fail_script_writer_calls = {fail_script_writer_call}
        else:
            self.fail_script_writer_calls = set(fail_script_writer_call)
        self.fail_script_critic = fail_script_critic
        self.fail_script_frame = fail_script_frame
        self.act_number = 0
        self.script_writer_number = 0

    def generate_structured(self, *, system_instruction, prompt, schema, profile):
        self.structured_calls.append((schema.__name__, system_instruction, prompt))
        handlers = {
            WorldArtifact: lambda: make_world(),
            CharactersArtifact: lambda: make_characters(),
            StoryPlanDraft: self._plan_response,
            PromiseLedgerDraft: lambda: self._promise_response(prompt),
            PlanReview: self._plan_review_response,
            StoryPresentation: self._narrative_presentation_response,
            ScriptPresentation: lambda: script_presentation(),
            ScriptFrame: self._script_frame_response,
            ActScriptDraft: lambda: self._script_act_response(system_instruction, prompt),
            StoryReview: lambda: self._review_response(system_instruction),
            StoryRequest: lambda: self.analyzed_request,
            SemanticSkeletonRanking: lambda: self._architecture_response(schema),
            NarrativeBlueprintDraft: lambda: self._architecture_response(schema),
        }
        handler = handlers.get(schema)
        if handler is None:
            raise AssertionError(schema)
        return handler()

    def _plan_response(self):
        self.last_plan = self.plans.pop(0)
        return self.last_plan

    def _plan_review_response(self):
        if self.quota_error_at == "plan_critic":
            raise GeminiDailyQuotaError("daily quota exhausted")
        return self.plan_review

    @staticmethod
    def _narrative_presentation_response():
        return StoryPresentation(
            title="El precio de la verdad",
            chapters=[
                ChapterPresentation(chapter_id="chapter-1", title="El archivo"),
                ChapterPresentation(chapter_id="chapter-2", title="La elección"),
            ],
        )

    def _review_response(self, system_instruction: str = ""):
        if "Script Critic" in system_instruction:
            if self.fail_script_critic:
                raise RuntimeError("script critic unavailable")
            if self.quota_error_at == "script_critic":
                raise GeminiDailyQuotaError("daily quota exhausted")
        elif self.fail_quality:
            raise RuntimeError("review unavailable")
        elif self.quota_error_at == "drama_critic":
            raise GeminiDailyQuotaError("daily quota exhausted")
        if self.explicit_review or self.last_ledger is None:
            return self.story_review
        return self.story_review.model_copy(
            update={"promise_checks": promise_checks(self.last_ledger, self.promise_verdict)}
        )

    def _script_frame_response(self):
        if self.fail_script_frame:
            raise RuntimeError("frame unavailable")
        if self.quota_error_at == "script_adapter":
            raise GeminiDailyQuotaError("daily quota exhausted")
        return script_frame()

    def _script_act_response(self, system_instruction: str, prompt: str):
        if "Script Writer" in system_instruction:
            self.script_writer_number += 1
            if self.script_writer_number in self.fail_script_writer_calls:
                raise RuntimeError("script writer unavailable")
            if self.quota_error_at == "script_writer":
                raise GeminiDailyQuotaError("daily quota exhausted")
            original_text = prompt.split("ORIGINAL ACT:\n", 1)[1].split("\n\nRETRY CORRECTION:", 1)[
                0
            ]
            original = ActScriptDraft.model_validate_json(original_text)
            if self.script_writer_identical_once and self.script_writer_number == 1:
                return original
            if self.script_writer_outputs is not None:
                return self.script_writer_outputs.pop(0)
            return _touched_act(original)
        self.act_number += 1
        if self.act_number in self.fail_act_calls:
            raise RuntimeError("act unavailable")
        role = "playwright" if "Playwright" in system_instruction else "script_adapter"
        if self.quota_error_at == role:
            raise GeminiDailyQuotaError("daily quota exhausted")
        if self.act_outputs is not None:
            return self.act_outputs.pop(0)
        match = _ANCHOR_CHAPTER.search(prompt)
        chapter_id = match.group(1) if match else "chapter-1"
        return script_act(self.last_plan, chapter_id)

    def _promise_response(self, prompt):
        if self.fail_promise_ledger:
            raise RuntimeError("promise architect unavailable")
        if self.quota_error_at == "promise_ledger":
            raise GeminiDailyQuotaError("daily quota exhausted")
        if self.ledgers is not None:
            self.last_ledger = self.ledgers.pop(0)
        else:
            self.last_ledger = promise_ledger(self.last_plan, _profile_in(prompt))
        return self.last_ledger

    def _architecture_response(self, schema):
        if schema is SemanticSkeletonRanking:
            if self.fail_semantic_ranking:
                raise RuntimeError("semantic ranking unavailable")
            if self.quota_error_at == "semantic_ranking":
                raise GeminiDailyQuotaError("daily quota exhausted")
            return SemanticSkeletonRanking(
                scores=[SemanticSkeletonScore(skeleton_id="heist", relevance=0.9)]
            )
        if self.fail_architect:
            raise RuntimeError("architect unavailable")
        if self.quota_error_at == "architect":
            raise GeminiDailyQuotaError("daily quota exhausted")
        return NarrativeBlueprintDraft(
            macroplot_id="mystery",
            macroplot_reading="Ana reconstructs a truth someone buried.",
            subplot_ids=["confession"],
            unexpected_angle="The truth is already known and nobody acts on it.",
        )

    def generate_text(self, *, system_instruction, prompt, profile):
        self.text_calls.append((system_instruction, prompt))
        if "final Writer" in system_instruction:
            self.writer_number += 1
            if self.writer_number in self.fail_writer_calls:
                raise RuntimeError("writer unavailable")
            if self.quota_error_at == "writer":
                raise GeminiDailyQuotaError("daily quota exhausted")
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
        if self.drafter_outputs is not None:
            return self.drafter_outputs.pop(0)
        return prose(f"borrador{self.draft_number}-")


def structured_prompt(provider, schema_name: str) -> str:
    return next(prompt for name, _, prompt in provider.structured_calls if name == schema_name)


def structured_prompt_at(provider, schema_name: str, index: int) -> str:
    prompts = [prompt for name, _, prompt in provider.structured_calls if name == schema_name]
    return prompts[index]


def structured_prompt_system(provider, schema_name: str) -> str:
    return next(system for name, system, _ in provider.structured_calls if name == schema_name)


def test_complete_pipeline_saves_v60_artifacts_and_agent_order(tmp_path) -> None:
    provider = FakeProvider(story_review=major_story_review())
    progress = []
    events = []
    created = []
    run = StoryGenerator(provider, tmp_path).generate(
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
        "promise_ledger.json",
        "promise_audit.json",
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
    assert metadata["pipeline_version"] == version_module.PIPELINE_VERSION
    assert metadata["status"] == "completed"
    assert run.audio_path.is_file()
    completed_stages = metadata["completed_stages"]
    assert completed_stages == sorted(completed_stages, key=pipeline_module.CHECKPOINT_STAGES.index)
    assert completed_stages.index("planning") < completed_stages.index("plan_review")
    assert completed_stages.index("plan_review") < completed_stages.index("promises")
    assert metadata["warnings"] == []
    assert any(update.stage == "story" for update in progress)
    manifest = json.loads((run.run_dir / "pipeline_manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifacts"]["story.mp3"]["bytes"] == len(b"fake-mp3")
    report = json.loads((run.run_dir / "revision_report.json").read_text(encoding="utf-8"))
    assert [chapter["final_source"] for chapter in report["chapters"]] == [
        "revision",
        "revision",
    ]
    metrics = json.loads((run.run_dir / "story_metrics.json").read_text(encoding="utf-8"))
    assert metrics["narrative_profile"] == "essential"
    assert metrics["chapters"] == 2
    assert metrics["events"] == 4
    assert metrics["words"] > 0
    assert {item["events"] for item in metrics["chapter_metrics"]} == {2}
    assert metrics["chapter_bodies_recovered"] is True
    assert 0 < metrics["prose_words"] < metrics["words"]
    assert metrics["prose_paragraphs"] > 0
    assert metrics["prose_sentences"] > 0
    assert metrics["words_per_sentence"] > 0
    assert metrics["words_per_paragraph"] > 0
    assert 0.0 <= metrics["dialogue_ratio"] <= 1.0
    assert metrics["dialogue_paragraphs"] >= metrics["dash_paragraphs"]
    assert all(item["paragraphs"] > 0 for item in metrics["chapter_metrics"])
    assert all(item["sentences"] > 0 for item in metrics["chapter_metrics"])
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


def test_audio_failure_keeps_stagecraft_run_completed(tmp_path, monkeypatch) -> None:
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

    progress = []
    run = StoryGenerator(FakeProvider(), tmp_path).generate(
        make_request(), on_progress=progress.append
    )

    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert (
        "[AUDIO_GENERATION_FAILED] No se pudo crear story.mp3 (AudioGenerationError); "
        "story.md permanece válido." in metadata["warnings"]
    )
    assert not run.audio_path.exists()
    assert (run.run_dir / "audio.json").is_file()
    audio_updates = [update for update in progress if update.stage == "audio"]
    assert audio_updates
    assert audio_updates[0].description == "Generando narración de la historia"


def test_an_arbitrary_audio_failure_keeps_the_run_completed(tmp_path, monkeypatch) -> None:
    def fail_audio(story_path):
        raise PermissionError("story.mp3 is locked by another process")

    monkeypatch.setattr(pipeline_module, "create_story_audio_sync", fail_audio)

    run = StoryGenerator(FakeProvider(), tmp_path).generate(make_request())

    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert (
        "[AUDIO_GENERATION_FAILED] No se pudo crear story.mp3 (PermissionError); "
        "story.md permanece válido." in metadata["warnings"]
    )
    assert "audio" not in metadata["completed_stages"]
    assert not run.audio_path.exists()
    assert run.run_dir.joinpath("story.md").is_file()


def test_a_failure_registering_the_audio_artifact_keeps_the_run_completed(
    tmp_path, monkeypatch
) -> None:
    def create_audio(story_path):
        story_path.with_suffix(".mp3").write_bytes(b"fake-mp3")

    def fail_register_existing(self, filename):
        if filename == "story.mp3":
            raise OSError("story.mp3 is locked by another process")
        return storage_module.ArtifactRepository.register_existing(self, filename)

    monkeypatch.setattr(pipeline_module, "create_story_audio_sync", create_audio)
    monkeypatch.setattr(
        storage_module.ArtifactRepository, "register_existing", fail_register_existing
    )

    run = StoryGenerator(FakeProvider(), tmp_path).generate(make_request())

    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert (
        "[AUDIO_GENERATION_FAILED] No se pudo crear story.mp3 (OSError); "
        "story.md permanece válido." in metadata["warnings"]
    )
    assert "audio" not in metadata["completed_stages"]
    assert run.run_dir.joinpath("story.md").is_file()


def test_an_interrupted_run_is_never_left_stranded_in_running(tmp_path) -> None:
    class InterruptedWorldProvider(FakeProvider):
        def generate_structured(self, *, system_instruction, prompt, schema, profile):
            if schema is WorldArtifact:
                raise KeyboardInterrupt
            return super().generate_structured(
                system_instruction=system_instruction, prompt=prompt, schema=schema, profile=profile
            )

    with pytest.raises(KeyboardInterrupt):
        StoryGenerator(InterruptedWorldProvider(), tmp_path).generate(make_request())

    run_dir = next(iter(tmp_path.iterdir()))
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert metadata["error_code"] == "RUN_INTERRUPTED"
    assert metadata["error_stage"] == "world"

    report = json.loads((run_dir / "error_report.json").read_text(encoding="utf-8"))
    assert report["code"] == "RUN_INTERRUPTED"
    assert report["details"] == {"exception_type": "KeyboardInterrupt"}


def test_an_unclassified_failure_records_the_stage_where_it_happened(tmp_path) -> None:
    class BrokenWorldProvider(FakeProvider):
        def generate_structured(self, *, system_instruction, prompt, schema, profile):
            if schema is WorldArtifact:
                raise RuntimeError("world builder exploded")
            return super().generate_structured(
                system_instruction=system_instruction, prompt=prompt, schema=schema, profile=profile
            )

    generator = StoryGenerator(BrokenWorldProvider(), tmp_path)
    with pytest.raises(RuntimeError):
        generator.generate(make_request())

    run_dirs = list(tmp_path.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert metadata["error_code"] == "UNEXPECTED_ERROR"
    assert metadata["error_stage"] == "world"

    error_report = json.loads((run_dir / "error_report.json").read_text(encoding="utf-8"))
    assert error_report["stage"] == "world"
    assert error_report["code"] == "UNEXPECTED_ERROR"


def test_a_failure_in_the_first_call_still_records_an_error_report(tmp_path) -> None:
    """Analysis used to run before the repository existed, so its failures left no trace."""

    class BrokenAnalystProvider(FakeProvider):
        def generate_structured(self, *, system_instruction, prompt, schema, profile):
            if schema is StoryRequest:
                raise RuntimeError("analyst exploded")
            return super().generate_structured(
                system_instruction=system_instruction, prompt=prompt, schema=schema, profile=profile
            )

    generator = StoryGenerator(
        BrokenAnalystProvider(), tmp_path, narrative_profile=NarrativeProfile.ESSENTIAL
    )
    with pytest.raises(RuntimeError):
        generator.generate("Escribe una historia sobre el mar")

    run_dirs = list(tmp_path.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    # MED-4: the folder was named after the raw prompt, cut mid-word, and the prompt was lost.
    assert run_dir.name.endswith(f"-{slugify(pipeline_module.UNANALYZED_TITLE)}")
    submitted = json.loads((run_dir / "submitted_request.json").read_text(encoding="utf-8"))
    assert submitted["prompt"] == "Escribe una historia sobre el mar"
    assert submitted["narrative_profile"] == "essential"

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert metadata["error_stage"] == "analysis"
    assert metadata["narrative_profile"] == "essential"

    error_report = json.loads((run_dir / "error_report.json").read_text(encoding="utf-8"))
    assert error_report["stage"] == "analysis"
    assert error_report["code"] == "UNEXPECTED_ERROR"
    assert (run_dir / "llm_usage.json").is_file()


def test_a_provider_error_is_filed_under_the_stage_it_stopped(tmp_path) -> None:
    """MED-4: every provider failure said stage "provider", never where the run died."""
    provider = FakeProvider(story_review=major_story_review(), quota_error_at="plan_critic")
    with pytest.raises(GeminiDailyQuotaError):
        StoryGenerator(provider, tmp_path).generate(make_request())
    run_dir = next(iter(tmp_path.iterdir()))
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "error_report.json").read_text(encoding="utf-8"))
    assert metadata["error_stage"] == report["stage"] == "plan_review"
    assert report["details"]["component"] == "provider"


def test_the_requested_profile_is_in_the_metadata(tmp_path) -> None:
    """MED-4: the profile lived only in request.json, so a failed run read as profileless."""
    run = StoryGenerator(FakeProvider(), tmp_path).generate(make_request())
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["narrative_profile"] == make_request().narrative_profile


def test_every_model_call_is_tagged_with_its_stage_and_agent(tmp_path) -> None:
    """MED-2: without the tag, llm_calls.jsonl could not split a run's cost by agent."""
    contexts: list[tuple[str, str]] = []

    class TaggingProvider(FakeProvider):
        def generate_structured(self, **kwargs):
            contexts.append(current_call_context())
            return super().generate_structured(**kwargs)

        def generate_text(self, **kwargs):
            contexts.append(current_call_context())
            return super().generate_text(**kwargs)

    StoryGenerator(TaggingProvider(), tmp_path).generate(make_request())
    assert contexts
    assert all(stage and agent for stage, agent in contexts), contexts


def test_usage_counts_logical_calls_not_attempts(tmp_path) -> None:
    """MED-2: failed_calls counted attempts, and calls counted the token-count preflights."""

    def record(call_id: str, status: str, operation: str = "structured:WorldArtifact"):
        return LLMUsageRecord(
            call_id=call_id,
            operation=operation,
            stage="world",
            agent="world",
            attempt=1,
            status=status,
            model="fake-model",
            timestamp=datetime.now(UTC),
        )

    pipeline = StoryPipeline(None, tmp_path)
    pipeline.provider = SimpleNamespace(
        usage_records=[
            record("a", "failed"),
            record("a", "succeeded"),
            record("b", "failed"),
            record("b", "failed"),
            record("c", "succeeded", operation="count_tokens"),
        ]
    )
    usage = pipeline._usage_artifact()
    assert (usage.calls, usage.failed_calls) == (2, 1)
    assert (usage.attempts, usage.failed_attempts, usage.auxiliary_calls) == (4, 3, 1)


def test_invalid_initial_plan_is_replaced_once(tmp_path) -> None:
    provider = FakeProvider([invalid_plan(), valid_plan()])
    run = StoryGenerator(provider, tmp_path).generate(make_request())
    assert (run.run_dir / "planning" / "attempt-001.json").is_file()
    plan_calls = [item for item in provider.structured_calls if item[0] == "StoryPlanDraft"]
    assert len(plan_calls) == 2
    assert "unknown characters" in plan_calls[1][2]


@pytest.mark.parametrize(
    ("profile", "plans", "expected_attempts", "check_no_prose_before_failing"),
    [
        (None, lambda: [invalid_plan() for _ in range(3)], 3, False),
        (NarrativeProfile.DEVELOPED, lambda: [valid_plan() for _ in range(3)], 3, False),
        (
            NarrativeProfile.EXPANSIVE,
            lambda: [sized_plan(10, branch_and_join=False) for _ in range(4)],
            4,
            True,
        ),
    ],
    ids=[
        "default-profile-three-attempts",
        "developed-profile-three-attempts",
        "expansive-profile-four-attempts",
    ],
)
def test_exhausted_planning_attempts_fail_before_any_prose(
    tmp_path, profile, plans, expected_attempts, check_no_prose_before_failing
) -> None:
    """Every profile eventually gives up on an unfixable plan without ever touching prose."""
    request = make_request()
    if profile is not None:
        request = request.model_copy(update={"narrative_profile": profile})
    provider = FakeProvider(plans=plans())
    created = []
    with pytest.raises(PlotValidationError) as captured:
        StoryGenerator(provider, tmp_path).generate(request, on_run_created=created.append)
    assert captured.value.code == "PLOT_VALIDATION_FAILED"
    assert captured.value.details["attempts"] == expected_attempts
    metadata = json.loads((created[0] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert metadata["error_code"] == "PLOT_VALIDATION_FAILED"
    if check_no_prose_before_failing:
        assert not any(name == "PlanReview" for name, _, _ in provider.structured_calls)
        assert provider.text_calls == []


def test_plan_critic_refines_once_and_invalid_refinement_falls_back(tmp_path) -> None:
    refined = valid_plan(ending="Ana reveals the truth and loses her home")
    provider = FakeProvider(
        [valid_plan(), refined],
        plan_review=rejected_plan_review(),
    )
    run = StoryGenerator(provider, tmp_path / "accepted").generate(make_request())
    saved = json.loads((run.run_dir / "story_plan.json").read_text(encoding="utf-8"))
    assert saved["ending"] == refined.ending
    assert (run.run_dir / "planning" / "refined-candidate.json").is_file()

    fallback_provider = FakeProvider(
        [valid_plan(), invalid_plan()],
        plan_review=rejected_plan_review(),
    )
    fallback = StoryGenerator(fallback_provider, tmp_path / "fallback").generate(make_request())
    saved = json.loads((fallback.run_dir / "story_plan.json").read_text(encoding="utf-8"))
    metadata = json.loads((fallback.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert saved["ending"] == valid_plan().ending
    assert "reemplazo estructuralmente inválido" in metadata["warnings"][0]


def test_late_critic_failure_delivers_the_draft_with_warning(tmp_path) -> None:
    run = StoryGenerator(FakeProvider(fail_quality=True), tmp_path).generate(make_request())
    assert run.story_path.read_text(encoding="utf-8") == (run.run_dir / "draft.md").read_text(
        encoding="utf-8"
    )
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert "borrador" in metadata["warnings"][0]


@pytest.mark.parametrize(
    "quota_error_at",
    ["plan_critic", "drama_critic", "writer", "architect", "semantic_ranking", "promise_ledger"],
)
def test_quota_errors_abort_instead_of_becoming_a_warning(tmp_path, quota_error_at) -> None:
    provider = FakeProvider(
        story_review=major_story_review(),
        quota_error_at=quota_error_at,
    )
    with pytest.raises(GeminiDailyQuotaError):
        StoryGenerator(provider, tmp_path).generate(make_request())


def test_drafter_receives_dag_history_and_previous_chapter(tmp_path) -> None:
    provider = FakeProvider()
    StoryGenerator(provider, tmp_path).generate(make_request())
    draft_calls = [item for item in provider.text_calls if "first-draft fiction chapter" in item[0]]
    assert len(draft_calls) == 2
    assert "RELEVANT PRIOR EVENTS:\n[]" in draft_calls[0][1]
    assert '"id": "event-1"' in draft_calls[1][1]
    assert "borrador1-0" in draft_calls[1][1]


def test_the_critic_is_shown_which_drafted_chapters_read_as_summary(tmp_path) -> None:
    provider = FakeProvider()
    run = StoryGenerator(provider, tmp_path).generate(make_request())
    critic_prompt = structured_prompt(provider, "StoryReview")
    evidence = json.loads((run.run_dir / "craft_evidence.json").read_text(encoding="utf-8"))

    assert "CRAFT OBSERVATIONS:" in critic_prompt
    assert NO_DIALOGUE in critic_prompt
    assert [item["chapter_id"] for item in evidence["chapters"]] == ["chapter-1", "chapter-2"]
    assert all(item["observations"] for item in evidence["chapters"])


def test_a_dramatized_draft_sends_the_critic_no_craft_observations(tmp_path) -> None:
    provider = FakeProvider(drafter_outputs=[scene_prose(), scene_prose()])
    run = StoryGenerator(provider, tmp_path).generate(make_request())
    evidence = json.loads((run.run_dir / "craft_evidence.json").read_text(encoding="utf-8"))

    assert "CRAFT OBSERVATIONS:" not in structured_prompt(provider, "StoryReview")
    assert evidence["prompt_block"] == ""
    assert not any(item["observations"] for item in evidence["chapters"])


def test_a_craft_observation_reaches_the_writer_as_a_note_on_that_chapter_alone(
    tmp_path,
) -> None:
    review = StoryReview(
        strengths=["The causal line is clear."],
        notes=[
            RevisionNote(
                id="chapter-1-dialogue",
                priority="major",
                category="voice_style",
                evidence="chapter-1 reports the confrontation instead of staging it.",
                instruction="Stage the confrontation as a live spoken scene.",
                chapter_ids=["chapter-1"],
            )
        ],
    )
    provider = FakeProvider(
        drafter_outputs=[barely_spoken_prose(), scene_prose()],
        story_review=review,
    )
    run = StoryGenerator(provider, tmp_path).generate(make_request())

    evidence = json.loads((run.run_dir / "craft_evidence.json").read_text(encoding="utf-8"))
    assert evidence["chapters"][0]["observations"] == [RARE_DIALOGUE]
    assert evidence["chapters"][1]["observations"] == []

    critic_prompt = structured_prompt(provider, "StoryReview")
    assert f"- chapter-1: {RARE_DIALOGUE}." in critic_prompt
    assert "chapter-2:" not in critic_prompt

    writer_calls = [item for item in provider.text_calls if "final Writer" in item[0]]
    assert len(writer_calls) == 1
    assert "REVISION NOTES:" in writer_calls[0][1]
    assert "Stage the confrontation as a live spoken scene." in writer_calls[0][1]

    report = json.loads((run.run_dir / "revision_report.json").read_text(encoding="utf-8"))
    assert report["chapters"][0]["note_ids"] == ["chapter-1-dialogue"]
    assert report["chapters"][0]["final_source"] == "revision"
    assert report["chapters"][1]["note_ids"] == []
    assert report["chapters"][1]["final_source"] == "draft"


def test_the_writer_is_given_the_voices_it_must_preserve(tmp_path) -> None:
    provider = FakeProvider(story_review=major_story_review())
    StoryGenerator(provider, tmp_path).generate(make_request())
    writer_calls = [item for item in provider.text_calls if "final Writer" in item[0]]

    assert writer_calls
    assert all("RELEVANT CHARACTERS:" in prompt for _, prompt in writer_calls)
    assert all('"voice": "Precise and restrained"' in prompt for _, prompt in writer_calls)


def test_writer_retries_unchanged_major_revision_and_saves_attempt(tmp_path) -> None:
    provider = FakeProvider(
        story_review=major_story_review(),
        writer_identical_once=True,
    )
    run = StoryGenerator(provider, tmp_path).generate(make_request())
    writer_calls = [item for item in provider.text_calls if "final Writer" in item[0]]
    assert len(writer_calls) == 3
    assert (run.run_dir / "writer" / "chapter-001-attempt-001.md").is_file()
    assert "RETRY CORRECTION" in writer_calls[1][1]


@pytest.mark.parametrize(
    ("candidate", "original", "notes", "expected_code"),
    [
        ("", prose("original-", 300), [], "EMPTY_CHAPTER_BODY"),
        (
            "# Encabezado\n\n" + prose("texto-", 300),
            prose("original-", 300),
            [],
            "MARKDOWN_HEADINGS",
        ),
        (
            prose("original-", 300),
            prose("original-", 300),
            major_story_review().notes,
            "UNCHANGED_SIGNIFICANT_NOTES",
        ),
    ],
    ids=["empty-body", "markdown-headings", "unchanged-with-significant-notes"],
)
def test_writer_candidate_diagnostics_are_structured(
    candidate, original, notes, expected_code
) -> None:
    diagnostic = writer_candidate_issue(candidate, original, notes)
    assert diagnostic is not None
    assert diagnostic.code == expected_code
    assert diagnostic.actual_words == len(candidate.split())
    assert diagnostic.retry_instruction


def test_writer_accepts_different_lengths_without_budget_retries(tmp_path) -> None:
    provider = FakeProvider(
        story_review=major_story_review(),
        writer_outputs=[
            prose("corto-a-", 100),
            prose("largo-", 500),
        ],
    )
    run = StoryGenerator(provider, tmp_path).generate(make_request())
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
    provider = FakeProvider(story_review=major_story_review(), fail_writer_call={2, 3})
    run = StoryGenerator(provider, tmp_path).generate(make_request())
    draft_bodies = parse_chapter_bodies(
        (run.run_dir / "draft.md").read_text(encoding="utf-8"),
        2,
    )
    final_bodies = parse_chapter_bodies(run.story_path.read_text(encoding="utf-8"), 2)
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert final_bodies[0] != draft_bodies[0]
    assert final_bodies[1] == draft_bodies[1]
    assert "Capítulo 2" in metadata["warnings"][0]
    report = json.loads((run.run_dir / "revision_report.json").read_text(encoding="utf-8"))
    failed = report["chapters"][1]
    assert failed["final_source"] == "draft"
    assert failed["warning_code"] == "WRITER_REVISION_REJECTED"
    assert [item["status"] for item in failed["attempts"]] == ["failed", "failed"]
    assert failed["attempts"][0]["exception_type"] == "RuntimeError"


def test_writer_retries_after_a_transient_failure(tmp_path) -> None:
    provider = FakeProvider(story_review=major_story_review(), fail_writer_call=1)
    run = StoryGenerator(provider, tmp_path).generate(make_request())
    report = json.loads((run.run_dir / "revision_report.json").read_text(encoding="utf-8"))
    recovered = report["chapters"][0]
    assert recovered["final_source"] == "revision"
    assert recovered["warning_code"] is None
    assert [item["status"] for item in recovered["attempts"]] == ["failed", "accepted"]
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["warnings"] == []


def test_chapters_without_notes_skip_the_writer(tmp_path) -> None:
    provider = FakeProvider()
    run = StoryGenerator(provider, tmp_path).generate(make_request())
    assert [item for item in provider.text_calls if "final Writer" in item[0]] == []
    report = json.loads((run.run_dir / "revision_report.json").read_text(encoding="utf-8"))
    for chapter in report["chapters"]:
        assert chapter["final_source"] == "draft"
        assert chapter["attempts"] == []
        assert chapter["warning_code"] is None
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["warnings"] == []
    assert run.story_path.read_text(encoding="utf-8") == (run.run_dir / "draft.md").read_text(
        encoding="utf-8"
    )


def test_a_note_with_only_event_ids_reaches_just_the_owning_chapter(tmp_path) -> None:
    """An untargeted chapter list does not make an event-scoped note global."""
    provider = FakeProvider(story_review=event_scoped_story_review())
    run = StoryGenerator(provider, tmp_path).generate(make_request())
    report = json.loads((run.run_dir / "revision_report.json").read_text(encoding="utf-8"))
    by_chapter = {item["chapter_id"]: item for item in report["chapters"]}
    # event-3 belongs to chapter-2, so chapter-1 must never see the note nor spend a Writer call.
    assert by_chapter["chapter-1"]["note_ids"] == []
    assert by_chapter["chapter-1"]["attempts"] == []
    assert by_chapter["chapter-1"]["final_source"] == "draft"
    assert by_chapter["chapter-2"]["note_ids"] == ["story-note-1"]
    assert by_chapter["chapter-2"]["final_source"] == "revision"
    writer_prompts = [item for item in provider.text_calls if "final Writer" in item[0]]
    assert len(writer_prompts) == 1


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


def test_developed_plan_below_event_floor_is_replanned(tmp_path) -> None:
    request = make_request().model_copy(update={"narrative_profile": NarrativeProfile.DEVELOPED})
    provider = FakeProvider(plans=[valid_plan(), sized_plan(8)])
    run = StoryGenerator(provider, tmp_path).generate(request)
    plan = json.loads((run.run_dir / "story_plan.json").read_text(encoding="utf-8"))
    validation = json.loads(
        (run.run_dir / "planning/attempt-001-validation.json").read_text(encoding="utf-8")
    )
    assert len(plan["events"]) == 8
    assert validation["issue"] == "developed profile requires at least 8 events; got 4"
    planner_prompts = [
        prompt for name, _, prompt in provider.structured_calls if name == "StoryPlanDraft"
    ]
    assert "Fix this structural error" in planner_prompts[1]
    assert "ADD at least 4 more causally meaningful events to reach 8" in planner_prompts[1]
    assert PROFILE_MARKER in planner_prompts[1]


def test_profile_guidance_reaches_world_characters_and_prose_agents(tmp_path) -> None:
    request = make_request().model_copy(update={"narrative_profile": NarrativeProfile.DEVELOPED})
    provider = FakeProvider(plans=[sized_plan(8)])
    StoryGenerator(provider, tmp_path).generate(request)
    structured = {name: (system, prompt) for name, system, prompt in provider.structured_calls}
    assert "scaled to the qualitative narrative profile" in structured["WorldArtifact"][0]
    assert "supporting characters" in structured["CharactersArtifact"][0]
    assert PROFILE_MARKER in structured["WorldArtifact"][1]
    assert PROFILE_MARKER in structured["CharactersArtifact"][1]
    assert any(PROFILE_MARKER in prompt for _, prompt in provider.text_calls)


def test_internal_agents_use_english_until_drafting(tmp_path) -> None:
    provider = FakeProvider()
    run = StoryGenerator(provider, tmp_path).generate(make_request())
    request = json.loads((run.run_dir / "request.json").read_text(encoding="utf-8"))
    plan = json.loads((run.run_dir / "story_plan.json").read_text(encoding="utf-8"))
    presentation = json.loads((run.run_dir / "draft_presentation.json").read_text(encoding="utf-8"))
    assert request["title"] == "The Price of Truth"
    assert request["narrative_profile"] == "essential"
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


def test_architecture_stage_writes_a_blueprint_and_guides_only_the_agents_that_should_see_it(
    tmp_path,
) -> None:
    """The blueprint reaches the character designer and planner, and nowhere else."""
    provider = FakeProvider()
    run = StoryGenerator(provider, tmp_path).generate(make_request())

    blueprint = json.loads((run.run_dir / "narrative_blueprint.json").read_text(encoding="utf-8"))
    assert blueprint["macroplot_id"] == "mystery"
    assert blueprint["unexpected_angle"]
    assert blueprint["semantic_used"] is True
    assert blueprint["considered"], "the ranking evidence must be auditable"

    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    completed = metadata["completed_stages"]
    assert "architecture" in completed
    assert completed == sorted(completed, key=pipeline_module.CHECKPOINT_STAGES.index)
    assert completed.index("architecture") < completed.index("characters")

    for schema_name in ("CharactersArtifact", "StoryPlanDraft"):
        prompt = structured_prompt(provider, schema_name)
        assert "NARRATIVE INSPIRATION (non-binding)" in prompt
        assert "You may honour, subvert, or discard this section entirely." in prompt

    architect_prompt = structured_prompt(provider, "NarrativeBlueprintDraft")
    assert "SKELETON SHORTLIST" in architect_prompt
    assert "FUNCTIONAL ROLE VOCABULARY" in architect_prompt
    assert "functional_role" in structured_prompt_system(provider, "CharactersArtifact")

    # The blueprint is inspiration only: prose agents and both critics never see it.
    for _, prompt in provider.text_calls:
        assert "NARRATIVE INSPIRATION" not in prompt
    for name, _, prompt in provider.structured_calls:
        if name in {"PlanReview", "StoryReview"}:
            assert "NARRATIVE INSPIRATION" not in prompt


def test_disabled_guidance_removes_the_stage_and_its_vocabulary(tmp_path) -> None:
    provider = FakeProvider()
    run = StoryGenerator(provider, tmp_path, narrative_guidance=False).generate(make_request())

    assert not (run.run_dir / "narrative_blueprint.json").exists()
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert "architecture" not in metadata["completed_stages"]
    assert not metadata["warnings"]
    assert all(name != "NarrativeBlueprintDraft" for name, _, _ in provider.structured_calls)
    for _, _, prompt in provider.structured_calls:
        assert "NARRATIVE INSPIRATION" not in prompt

    characters_system = structured_prompt_system(provider, "CharactersArtifact")
    assert "functional_role" not in characters_system
    assert "persona" not in characters_system
    characters = json.loads((run.run_dir / "characters.json").read_text(encoding="utf-8"))
    for character in characters["characters"]:
        assert character["functional_role"] == ""
        assert character["persona"] == ""


def test_the_ledger_reaches_the_drafter_and_the_writer_as_chapter_obligations(tmp_path) -> None:
    provider = FakeProvider(story_review=major_story_review())
    run = StoryGenerator(provider, tmp_path).generate(make_request())

    ledger = json.loads((run.run_dir / "promise_ledger.json").read_text(encoding="utf-8"))
    assert ledger["primary_promise_id"] == "promise-1"
    assert {promise["id"] for promise in ledger["promises"]} == {"promise-1", "promise-2"}
    assert ledger["chapter_by_event"]["event-1"] == "chapter-1"

    drafts = [item for item in provider.text_calls if "first-draft fiction chapter" in item[0]]
    writes = [item for item in provider.text_calls if "final Writer" in item[0]]
    assert "PROMISE OBLIGATIONS:" in drafts[0][1]
    assert "OPEN promise-1" in drafts[0][1]
    assert "PAY OFF promise-1" in drafts[-1][1]
    assert "PROMISE OBLIGATIONS:" in writes[0][1]
    # The obligations must sit ahead of the body the Writer is asked to improve, or the retry
    # diagnostics would read them back as part of the chapter.
    body_at = writes[0][1].index("ORIGINAL CHAPTER BODY:")
    assert writes[0][1].index("PROMISE OBLIGATIONS:") < body_at
    assert "PROMISE OBLIGATIONS:" in structured_prompt(provider, "StoryReview")


def test_the_ledger_never_teaches_a_count_or_touches_the_plan(tmp_path) -> None:
    with_ledger = FakeProvider()
    without = FakeProvider()
    left = StoryGenerator(with_ledger, tmp_path / "con").generate(make_request())
    right = StoryGenerator(without, tmp_path / "sin", promise_ledger=False).generate(make_request())

    assert (left.run_dir / "story_plan.json").read_bytes() == (
        right.run_dir / "story_plan.json"
    ).read_bytes()
    ledger_prompt = structured_prompt(with_ledger, "PromiseLedgerDraft")
    assert "EXACT EVENT COUNTS" not in ledger_prompt
    assert "word budget" not in ledger_prompt
    assert "NARRATIVE INSPIRATION" not in ledger_prompt
    drafts = [item for item in with_ledger.text_calls if "first-draft" in item[0]]
    own_events = [("event-1", "event-2"), ("event-3", "event-4")]
    for (_, prompt), owned in zip(drafts, own_events, strict=True):
        obligations = prompt.split("PROMISE OBLIGATIONS:\n", 1)[1]
        cited = {line.split(" | ")[0].removeprefix("- ") for line in obligations.splitlines()[1:]}
        assert cited <= set(owned)


def test_disabled_ledger_removes_the_stage_and_its_vocabulary(tmp_path) -> None:
    provider = FakeProvider()
    run = StoryGenerator(provider, tmp_path, promise_ledger=False).generate(make_request())

    assert not (run.run_dir / "promise_ledger.json").exists()
    assert not (run.run_dir / "promise_audit.json").exists()
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert "promises" not in metadata["completed_stages"]
    assert not metadata["warnings"]
    assert all(name != "PromiseLedgerDraft" for name, _, _ in provider.structured_calls)
    for _, prompt in provider.text_calls:
        assert "PROMISE OBLIGATIONS" not in prompt


def test_a_rejected_ledger_is_repaired_against_the_frozen_plan(tmp_path) -> None:
    broken = promise_ledger(valid_plan())
    broken.promises[0].payoff.event_id = "event-99"
    provider = FakeProvider(ledgers=[broken, promise_ledger(valid_plan())])
    run = StoryGenerator(provider, tmp_path).generate(make_request())

    assert (run.run_dir / "promise_ledger.json").is_file()
    rejected = json.loads(
        (run.run_dir / "promises" / "attempt-001.json").read_text(encoding="utf-8")
    )
    assert "event-99" in rejected["issue"]
    assert rejected["issue"].isascii()
    repair = structured_prompt_at(provider, "PromiseLedgerDraft", 1)
    assert "LEDGER REPAIR REQUIRED" in repair
    assert rejected["issue"] in repair
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert not metadata["warnings"]


def test_an_unrepairable_ledger_only_costs_the_guidance(tmp_path) -> None:
    broken = promise_ledger(valid_plan())
    broken.promises[0].payoff.event_id = "event-99"
    provider = FakeProvider(ledgers=[broken, broken.model_copy(deep=True)])
    run = StoryGenerator(provider, tmp_path).generate(make_request())

    assert run.story_path.is_file()
    assert not (run.run_dir / "promise_ledger.json").exists()
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert "promises" not in metadata["completed_stages"]
    assert any("promesas" in warning for warning in metadata["warnings"])
    assert (run.run_dir / "promises" / "attempt-002.json").is_file()


def test_the_ledger_failing_outright_still_delivers_the_story(tmp_path) -> None:
    provider = FakeProvider(fail_promise_ledger=True)
    run = StoryGenerator(provider, tmp_path).generate(make_request())

    assert run.story_path.is_file()
    assert not (run.run_dir / "promise_ledger.json").exists()
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert any("promesas" in warning for warning in metadata["warnings"])


def test_the_audit_records_what_the_critic_said_about_every_promise(tmp_path) -> None:
    provider = FakeProvider(promise_verdict="weak")
    run = StoryGenerator(provider, tmp_path).generate(make_request())

    audit = json.loads((run.run_dir / "promise_audit.json").read_text(encoding="utf-8"))
    assert audit["promises"] == 2
    assert audit["weak"] == 2
    assert audit["fulfilled"] == 0
    assert audit["fulfilled_ratio"] == 0.0
    assert [entry["primary"] for entry in audit["entries"]] == [True, False]


def test_a_promise_the_critic_never_judged_counts_as_broken(tmp_path) -> None:
    provider = FakeProvider(story_review=major_story_review())
    run = StoryGenerator(provider, tmp_path).generate(make_request())

    audit = json.loads((run.run_dir / "promise_audit.json").read_text(encoding="utf-8"))
    assert audit["broken"] == audit["promises"] == 2
    assert all(entry["verdict"] == "broken" for entry in audit["entries"])
    assert all("no verdict" in entry["evidence"] for entry in audit["entries"])


def test_a_promise_id_in_note_event_ids_costs_the_whole_revision(tmp_path) -> None:
    """Pin the cost of the mistake the critic prompt is written to prevent.

    _validate_note_references rejects the review, _critique_and_revise degrades, and the draft
    ships unrevised behind a warning. Nothing here is broken, but the loss is large and invisible
    from the story alone, which is why the Drama Critic is told in as many words that promise IDs
    belong in promise_checks and nowhere else.
    """
    review = StoryReview(
        notes=[
            RevisionNote(
                id="misplaced",
                priority="major",
                category="setup_payoff",
                evidence="The promise never lands.",
                instruction="Stage the confrontation.",
                event_ids=["promise-1"],
            )
        ]
    )
    provider = FakeProvider(story_review=review)
    run = StoryGenerator(provider, tmp_path).generate(make_request())

    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert any("crítica dramática" in warning for warning in metadata["warnings"])
    assert "PROMISE OBLIGATIONS" in structured_prompt(provider, "StoryReview")
    assert "promise_checks only" in structured_prompt_system(provider, "StoryReview")


def test_architect_failure_only_costs_the_guidance(tmp_path) -> None:
    provider = FakeProvider(fail_architect=True)
    run = StoryGenerator(provider, tmp_path).generate(make_request())

    assert run.story_path.is_file()
    assert not (run.run_dir / "narrative_blueprint.json").exists()
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert "architecture" not in metadata["completed_stages"]
    assert any("esqueleto narrativo" in warning for warning in metadata["warnings"])
    assert "NARRATIVE INSPIRATION" not in structured_prompt(provider, "StoryPlanDraft")


def test_semantic_ranking_failure_still_produces_a_blueprint(tmp_path) -> None:
    provider = FakeProvider(fail_semantic_ranking=True)
    run = StoryGenerator(provider, tmp_path).generate(make_request())

    blueprint = json.loads((run.run_dir / "narrative_blueprint.json").read_text(encoding="utf-8"))
    assert blueprint["semantic_used"] is False
    assert all(row["semantic_score"] is None for row in blueprint["considered"])


def test_forced_profile_outranks_the_prompt_derived_one(tmp_path) -> None:
    provider = FakeProvider(plans=[sized_plan(10, branch_and_join=True)])
    run = StoryGenerator(
        provider,
        tmp_path,
        narrative_profile=NarrativeProfile.EXPANSIVE,
    ).generate(make_request())

    request = json.loads((run.run_dir / "request.json").read_text(encoding="utf-8"))
    assert request["narrative_profile"] == "expansive"
    assert "5 to 7 chapters" in structured_prompt_system(provider, "StoryPlanDraft")


def test_audio_can_be_skipped_without_touching_the_story(tmp_path, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        pipeline_module,
        "create_story_audio_sync",
        lambda path: calls.append(path),
    )
    progress = []
    run = StoryGenerator(FakeProvider(), tmp_path, audio=False).generate(
        make_request(),
        on_progress=progress.append,
    )

    assert calls == []
    assert not run.audio_path.exists()
    assert run.story_path.is_file()
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert metadata["warnings"] == []
    assert "audio" not in metadata["completed_stages"]
    assert all(update.stage != "audio" for update in progress)


@pytest.mark.parametrize(
    ("profile", "leaked_plan", "expected_issue"),
    [
        (
            NarrativeProfile.EXPANSIVE,
            lambda: sized_plan(10),
            "causal dependency branch followed by a causal join",
        ),
        (NarrativeProfile.DEVELOPED, valid_plan, "requires at least 8 events"),
        (
            NarrativeProfile.ESSENTIAL,
            lambda: thin_chapter_plan(),
            "requires at least 2 events per chapter",
        ),
    ],
)
def test_a_plan_breaking_its_profile_contract_is_never_persisted(
    tmp_path,
    monkeypatch,
    profile,
    leaked_plan,
    expected_issue,
) -> None:
    request = make_request().model_copy(update={"narrative_profile": profile})
    provider = FakeProvider(plans=[sized_plan(10, branch_and_join=True)])
    leaked = materialize_plan(leaked_plan(), make_world(), make_characters())
    monkeypatch.setattr(StoryPipeline, "_critique_plan", lambda self, *args, **kwargs: leaked)
    created = []
    with pytest.raises(PlotValidationError) as captured:
        StoryGenerator(provider, tmp_path).generate(request, on_run_created=created.append)
    assert captured.value.code == "PLOT_VALIDATION_FAILED"
    assert expected_issue in captured.value.details["issue"]
    assert not (created[0] / "story_plan.json").exists()
    metadata = json.loads((created[0] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert provider.text_calls == []


def _join_without_a_branch() -> StoryPlanDraft:
    """Two parallel roots converging on event-5: a join exists, but no event branches."""
    candidate = sized_plan(9)
    candidate.dependencies = [
        EventDependency(source_event_id="event-1", target_event_id="event-4", relation="causal"),
        EventDependency(source_event_id="event-2", target_event_id="event-3", relation="causal"),
        EventDependency(source_event_id="event-3", target_event_id="event-5", relation="causal"),
        EventDependency(source_event_id="event-4", target_event_id="event-5", relation="causal"),
        *[
            EventDependency(
                source_event_id=f"event-{order}",
                target_event_id=f"event-{order + 1}",
                relation="causal",
            )
            for order in range(5, 9)
        ],
    ]
    return candidate


def _branch_pointing_backwards() -> StoryPlanDraft:
    """A branch bolted on by pointing event-4 back at event-3: legal count, illegal direction."""
    candidate = sized_plan(9)
    candidate.dependencies = [
        EventDependency(source_event_id="event-1", target_event_id="event-4", relation="causal"),
        EventDependency(source_event_id="event-4", target_event_id="event-5", relation="causal"),
        EventDependency(source_event_id="event-4", target_event_id="event-3", relation="causal"),
        EventDependency(source_event_id="event-2", target_event_id="event-3", relation="causal"),
        EventDependency(source_event_id="event-3", target_event_id="event-5", relation="causal"),
        *[
            EventDependency(
                source_event_id=f"event-{order}",
                target_event_id=f"event-{order + 1}",
                relation="causal",
            )
            for order in range(5, 9)
        ],
    ]
    return candidate


@pytest.mark.parametrize(
    ("draft", "issue", "profile", "must_contain", "must_not_contain"),
    [
        (
            lambda: sized_plan(10, branch_and_join=False),
            "expansive profile requires a causal dependency branch followed by a causal join",
            NarrativeProfile.EXPANSIVE,
            [
                "DIRECTION PROBLEM, NOT A COUNTING PROBLEM",
                "CURRENT CAUSAL DEGREES",
                "source.order < target.order",
            ],
            ["PAYOFF_OF REFERENCE MATRIX"],
        ),
        (
            _join_without_a_branch,
            "expansive profile requires a causal dependency branch followed by a causal join",
            NarrativeProfile.EXPANSIVE,
            [
                "ADD this causal dependency: event-1 -> event-2",
                "two outgoing causal dependencies",
                "the branch precedes the join",
            ],
            [],
        ),
        (
            _branch_pointing_backwards,
            "dependency event-4->event-3 points backwards",
            NarrativeProfile.EXPANSIVE,
            [
                "event-4 -> event-3 runs from order 4 back to order 3",
                "reverse it to event-3 -> event-4",
            ],
            ["PAYOFF_OF REFERENCE MATRIX"],
        ),
        (
            lambda: sized_plan(6, branch_and_join=True),
            "expansive profile requires at least 10 events; got 6",
            NarrativeProfile.EXPANSIVE,
            [
                "This profile needs 10 to 14 events",
                "You planned 6.",
                "ADD at least 4 more causally meaningful events to reach 10.",
                "CURRENT EVENTS PER CHAPTER",
            ],
            ["PAYOFF_OF REFERENCE MATRIX"],
        ),
        (
            invalid_payoff_plan,
            "invalid payoff_of value: charcoal_note",
            NarrativeProfile.ESSENTIAL,
            [
                "PAYOFF_OF REFERENCE MATRIX",
                '"event_id": "event-2"',
                '"allowed_earlier_event_ids"',
                '"event-1"',
                "Never copy object IDs",
            ],
            ["DIRECTION PROBLEM"],
        ),
        (
            thin_chapter_plan,
            "essential profile requires at least 2 events per chapter; "
            "these chapters carry fewer: chapter-1, chapter-3",
            NarrativeProfile.ESSENTIAL,
            [
                "CURRENT EVENTS PER CHAPTER",
                "need new material: chapter-1, chapter-3",
                "do not drop chapters to meet the count",
            ],
            ["PAYOFF_OF REFERENCE MATRIX", "ADD at least"],
        ),
        (
            empty_chapter_plan,
            "chapters without events: chapter-3",
            NarrativeProfile.ESSENTIAL,
            [
                "CURRENT EVENTS PER CHAPTER",
                "need new material: chapter-3",
            ],
            ["PAYOFF_OF REFERENCE MATRIX"],
        ),
    ],
    ids=[
        "missing-branch-and-join",
        "join-without-a-branch-names-the-missing-edge",
        "backwards-dependency-names-the-offending-edge",
        "event-shortfall-says-how-many-and-where",
        "payoff-failure-gets-the-reference-matrix",
        "thin-chapter-failure-lists-the-thin-chapters",
        "empty-chapter-failure-gets-the-budget-block",
    ],
)
def test_repair_prompt_matches_the_failure_class(
    draft, issue, profile, must_contain, must_not_contain
) -> None:
    """`_repair_guidance` dispatches on the failure class, not on generic boilerplate."""
    repair = repair_guidance(draft(), issue, profile)
    for fragment in must_contain:
        assert fragment in repair
    for fragment in must_not_contain:
        assert fragment not in repair


@pytest.mark.parametrize(
    ("profile", "chapters", "events"),
    [
        (NarrativeProfile.ESSENTIAL, "2 to 3 chapters", "4 to 6 events"),
        (NarrativeProfile.DEVELOPED, "4 to 5 chapters", "8 to 10 events"),
        (NarrativeProfile.EXPANSIVE, "5 to 7 chapters", "10 to 14 events"),
    ],
)
def test_the_planner_is_given_the_event_target_its_chapter_band_implies(
    tmp_path,
    profile,
    chapters,
    events,
) -> None:
    request = make_request().model_copy(update={"narrative_profile": profile})
    provider = FakeProvider(plans=[sized_plan(10, branch_and_join=True)])
    StoryGenerator(provider, tmp_path).generate(request)
    instruction = structured_prompt_system(provider, "StoryPlanDraft")
    assert chapters in instruction
    assert events in instruction
    assert "at least 2 events" in instruction
    assert "chapter carrying a single event is sent back" in instruction


@pytest.mark.parametrize(
    ("profile", "draft"),
    [
        (NarrativeProfile.ESSENTIAL, lambda: sized_plan(2)),
        (NarrativeProfile.ESSENTIAL, thin_chapter_plan),
        (NarrativeProfile.DEVELOPED, valid_plan),
        (NarrativeProfile.DEVELOPED, thin_chapter_plan),
        (NarrativeProfile.EXPANSIVE, lambda: sized_plan(10, branch_and_join=False)),
    ],
    ids=[
        "essential-below-floor",
        "essential-thin-chapter",
        "developed-below-floor",
        "developed-thin-chapter",
        "expansive-without-a-branch",
    ],
)
def test_every_profile_rejection_reaches_a_repair_block(profile, draft) -> None:
    """No message graph.py can raise for a profile may fall through to empty repair guidance."""
    candidate = draft()
    plan = materialize_plan(candidate, make_world(), make_characters())
    with pytest.raises(ValueError) as captured:
        validate_profile_structure(plan, profile)
    issue = str(captured.value)
    assert issue.isascii()
    assert repair_guidance(candidate, issue, profile) != ""


def test_a_thin_chapter_is_rejected_and_repaired_on_the_next_attempt(tmp_path) -> None:
    """The per-chapter floor drives a real replan, not just a note inside another failure."""
    provider = FakeProvider(plans=[thin_chapter_plan(), valid_plan()])
    run = StoryGenerator(provider, tmp_path).generate(make_request())

    validation = json.loads(
        (run.run_dir / "planning/attempt-001-validation.json").read_text(encoding="utf-8")
    )
    assert validation["issue"] == (
        "essential profile requires at least 2 events per chapter; "
        "these chapters carry fewer: chapter-1, chapter-3"
    )
    planner_prompts = [
        prompt for name, _, prompt in provider.structured_calls if name == "StoryPlanDraft"
    ]
    assert "need new material: chapter-1, chapter-3" in planner_prompts[1]
    plan = json.loads((run.run_dir / "story_plan.json").read_text(encoding="utf-8"))
    assert len(plan["events"]) == 4
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"


def test_the_planner_is_taught_exactly_the_floor_that_is_enforced(tmp_path) -> None:
    """The prompt carries one event floor per profile, and it is the validated one."""
    for profile in NarrativeProfile:
        provider = FakeProvider(plans=[sized_plan(10, branch_and_join=True)])
        request = make_request().model_copy(update={"narrative_profile": profile})
        StoryGenerator(provider, tmp_path / profile.value).generate(request)
        floor = profile_event_floor(profile)
        system, prompt = next(
            (system, prompt)
            for name, system, prompt in provider.structured_calls
            if name == "StoryPlanDraft"
        )
        assert f"{floor} is the rejection boundary" in system
        # The contract block travels in the prompt, and it may not smuggle a competing number.
        assert "NARRATIVE PROFILE CONTRACT" in prompt
        assert "causally meaningful events" not in prompt

"""The writing stages: scene cards, draft, critique, revision and line edit (7.20, ING-3).

Split from pipeline.py, which mixes this in like the other stage mixins; it calls the
helpers pipeline.py defines (self.repository, self._call_agent, self._publish).
"""

from __future__ import annotations

from collections import Counter

from ..agents import (
    DrafterAgent,
    DramaCriticAgent,
    WriterAgent,
)
from ..agents.editor import LineEditorAgent
from ..agents.scene_cards import SceneCardAgent
from ..agents.style import STYLE_EXAMPLES
from ..planning.graph import relevant_prior_events
from ..planning.promise_brief import critic_obligations
from ..planning.scene_cards import chapter_cards, materialize_cards
from ..runtime.errors import NON_DEGRADABLE_ERRORS
from ..schemas import (
    ChapterPlan,
    ChapterRevisionResult,
    CharacterProfile,
    CharactersArtifact,
    PlotEvent,
    PromiseAuditArtifact,
    PromiseAuditEntry,
    PromiseCheck,
    PromiseLedger,
    RevisionNote,
    RevisionReport,
    SceneCard,
    SceneCardsDraft,
    StoryPlan,
    StoryPresentation,
    StoryRequest,
    StoryReview,
    WorldArtifact,
)
from .acceptance import (
    writer_best_candidate_warning,
    writer_edit_issue,
    writer_fallback_warning,
)
from .anchoring import anchor_review
from .assembly import assemble_story
from .audit import story_metrics, word_count
from .chapter_edits import ParagraphEdits, apply_chapter_edits
from .craft_evidence import character_names, craft_evidence, craft_notes, known_names
from .line_edit import edit_chapter
from .revision_loop import Judgement, revise_with_retries

# The Writer's attempts per chapter: the first, and one retry with the correction.
WRITER_ATTEMPTS = 2

# The scene cards annotate a frozen plan like the ledger, so they get as many attempts.
SCENE_CARD_ATTEMPTS = 2


class WritingStagesMixin:
    """Write the planned story: draft it, have it critiqued and revise it chapter by chapter."""

    def _draft_chapters(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        ledger: PromiseLedger | None = None,
    ) -> tuple[StoryPresentation, list[str], str]:
        """Use Drafter to localize titles and create the first story."""
        assert self.repository is not None
        cards = self._build_scene_cards(request, world, characters, plan)
        drafter = DrafterAgent(self.provider)

        def create_presentation():
            """Create localized story and chapter titles."""
            return drafter.presentation(request, plan)

        presentation = self._call_agent("drafter", create_presentation)
        self._validate_presentation(plan, presentation)
        presentation = self._localized_presentation(request, presentation, characters)
        self.repository.save_json("draft_presentation.json", presentation)
        event_by_id = {item.id: item for item in plan.events}
        bodies: list[str] = []
        for index, chapter in enumerate(plan.chapters, 1):
            self._notify_draft_chapter(index, len(plan.chapters))
            events = [
                event_by_id[event_id]
                for event_id in plan.topological_order
                if event_by_id[event_id].chapter_id == chapter.id
            ]
            history = relevant_prior_events(plan, {event.id for event in events})
            character_ids = {item for event in events for item in event.character_ids}
            relevant = [item for item in characters.characters if item.id in character_ids]
            scenes = chapter_cards(cards, plan, chapter.id)

            def draft_chapter(
                character_snapshot=relevant or characters.characters,
                chapter_snapshot=chapter,
                event_snapshot=events,
                history_snapshot=history,
                previous_body: str = bodies[-1] if bodies else "",
                brief: str = self._promise_brief(ledger, chapter.id),
                scenes=scenes,
            ):
                """Draft one chapter with loop values bound to this iteration."""
                return drafter.run(
                    request,
                    world,
                    character_snapshot,
                    plan,
                    presentation,
                    chapter_snapshot,
                    event_snapshot,
                    history_snapshot,
                    previous_body,
                    brief,
                    style_examples=self.options.style_examples,
                    scene_cards=scenes,
                )

            body = self._call_agent("drafter", draft_chapter).strip()
            self.repository.save_text(f"chapters/chapter-{index:03d}.md", body)
            bodies.append(body)
        self.repository.complete_stage("drafting")
        draft = assemble_story(plan, presentation, bodies)
        self.repository.save_text("draft.md", draft)
        return presentation, bodies, draft

    def _build_scene_cards(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
    ) -> list[SceneCard]:
        """Draw the scenes of every event when the run asks for them, or carry on without.

        The cards change how the plan is written, never what it holds, so like the ledger the
        stage degrades: a story drafted without them is a 7.16 story, never a lost run.
        """
        if not self.options.scene_cards:
            return []
        assert self.repository is not None
        self._notify(51, "scene_cards", "Dibujando las escenas de cada evento")
        agent = SceneCardAgent(self.provider)
        feedback = ""
        for attempt in range(1, SCENE_CARD_ATTEMPTS + 1):

            def draw_cards(feedback_snapshot: str = feedback):
                """Draw one set of scene cards with feedback bound to this attempt."""
                return agent.run(request, world, characters, plan, feedback_snapshot)

            try:
                draft = self._call_agent("scene_planner", draw_cards)
                cards = materialize_cards(draft, plan, world, characters)
            except NON_DEGRADABLE_ERRORS:
                raise
            except ValueError as exc:
                issue = str(exc).strip() or type(exc).__name__
                self.repository.save_data(
                    f"scene_cards/attempt-{attempt:03d}.json", {"attempt": attempt, "issue": issue}
                )
                feedback = (
                    "\n\nSCENE CARD REPAIR REQUIRED. RETURN A COMPLETE REPLACEMENT SET. "
                    f"The previous one was rejected: {issue}."
                )
                continue
            except Exception as exc:
                self.repository.save_data(
                    f"scene_cards/attempt-{attempt:03d}.json",
                    {"attempt": attempt, "exception_type": type(exc).__name__},
                )
                continue
            self.repository.save_json("scene_cards.json", SceneCardsDraft(cards=cards))
            self.repository.complete_stage("scene_cards")
            return cards
        warning = (
            "[SCENE_CARDS_FALLBACK] No se pudieron dibujar las escenas; el borrador se escribe "
            "directamente desde el plan."
        )
        self.repository.add_warning(warning)
        self._emit("scene_cards_fallback", warning, stage="scene_cards")
        return []

    @staticmethod
    def _validate_presentation(plan: StoryPlan, presentation: StoryPresentation) -> None:
        """Require one localized title for every canonical chapter, in order."""
        expected = [chapter.id for chapter in plan.chapters]
        received = [chapter.chapter_id for chapter in presentation.chapters]
        if received != expected:
            raise ValueError("localized presentation must follow the canonical chapter order")

    def _notify_draft_chapter(self, index: int, total: int) -> None:
        """Report progress for the chapter currently being drafted."""
        percent = 52 + (index - 1) * 24 // total
        self._notify(
            percent,
            "drafting",
            f"Redactando borrador del capítulo {index} de {total}",
            index,
            total,
        )

    def _critique_and_revise(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        presentation: StoryPresentation,
        draft_bodies: list[str],
        draft: str,
        ledger: PromiseLedger | None = None,
    ) -> list[str]:
        """Critique the complete draft, then let Writer revise chapter by chapter.

        Returns the final per-chapter bodies, not the assembled story: execute() assembles
        them, so a script run's adapter can reach the same bodies without reparsing Markdown.
        """
        assert self.repository is not None
        self._notify(78, "critique", "Analizando el drama del borrador completo")
        evidence = craft_evidence(
            plan.chapters, draft_bodies, character_names(characters.characters)
        )
        self.repository.save_json("craft_evidence.json", evidence)
        obligations = critic_obligations(ledger)
        try:

            def critique_story():
                """Critique the bound complete story draft."""
                return DramaCriticAgent(self.provider).run(
                    request,
                    world,
                    characters,
                    plan,
                    presentation,
                    draft,
                    evidence.prompt_block,
                    obligations,
                    anchored=self.options.anchored_critic,
                )

            review = self._call_agent("drama_critic", critique_story)
            self.repository.save_json("review.json", review)
            self._validate_note_references(review.notes, plan)
            if self.options.anchored_critic:
                review, anchors = anchor_review(review, draft)
                self.repository.save_data("review_anchors.json", anchors)
            self._audit_promises(ledger, review)
            self.repository.complete_stage("critique")
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception as exc:
            warning = (
                "La crítica dramática no pudo completarse; se entregó el borrador "
                f"por capítulos ({type(exc).__name__})."
            )
            self.repository.add_warning(warning)
            self._emit("quality_fallback", warning, stage=self.progress["stage"])
            return self._line_edited(request, characters, world, draft_bodies)
        # review.json keeps what the critic said; the Writer also gets what was measured.
        measured = review.model_copy(update={"notes": [*review.notes, *craft_notes(evidence)]})
        revised = self._revise_chapters(
            request,
            characters,
            plan,
            presentation,
            draft_bodies,
            measured,
            ledger,
        )
        return self._line_edited(request, characters, world, revised)

    def _line_edited(
        self,
        request: StoryRequest,
        characters: CharactersArtifact,
        world: WorldArtifact | None,
        bodies: list[str],
    ) -> list[str]:
        """Run the line editor over every finished chapter when the run asks for it (7.17)."""
        return [
            self._line_edit_chapter(request, characters, world, index, body)
            for index, body in enumerate(bodies, 1)
        ]

    def _line_edit_chapter(
        self,
        request: StoryRequest,
        characters: CharactersArtifact,
        world: WorldArtifact | None,
        index: int,
        body: str,
        *,
        directions: tuple[str, ...] = (),
        only: frozenset[str] | None = None,
        record: str = "",
    ) -> str:
        """Edit one chapter's flagged paragraphs, or return it untouched.

        Off unless the line_editor option is on, or unless ``only`` names the observations to
        repair: the narration sends pasted directions this way in every run (7.20). An editor
        that cannot run costs the chapter nothing: it ships as it was, with a warning.
        """
        if not self.options.line_editor and only is None:
            return body
        assert self.repository is not None
        editor = LineEditorAgent(self.provider)
        examples = STYLE_EXAMPLES if self.options.style_examples else ()

        def call(paragraphs: list[dict]):
            """Hand the flagged paragraphs of the bound chapter to the editor."""
            return self._call_agent(
                "line_editor",
                lambda: editor.run(request, paragraphs, style_examples=self.options.style_examples),
            )

        try:
            edited = edit_chapter(
                body,
                character_names(characters.characters),
                known_names(characters, world),
                call,
                examples=examples,
                directions=directions,
                only=only,
            )
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception as exc:
            warning = (
                f"[LINE_EDIT_UNAVAILABLE] Capítulo {index}: el editor no pudo corregir "
                f"({type(exc).__name__}); el capítulo se entrega como estaba."
            )
            self.repository.add_warning(warning)
            self._emit("line_edit_unavailable", warning, stage=self.progress["stage"])
            return body
        if edited.flagged:
            self.repository.save_data(
                record or f"line_edits/chapter-{index:03d}.json", edited.as_record()
            )
        return edited.body

    def _audit_promises(self, ledger: PromiseLedger | None, review: StoryReview) -> None:
        """Cross the ledger with the critic's verdicts and record what the story delivered.

        A promise the critic never judged counts as broken. Silence is not a pass: the whole
        point of the ledger is that every expectation the story opened gets an answer, and an
        unanswered question about one is exactly what the audit exists to surface.
        """
        assert self.repository is not None
        if ledger is None:
            return
        checks = {check.promise_id: check for check in review.promise_checks}
        entries = [
            self._promise_entry(promise, checks.get(promise.id), ledger)
            for promise in ledger.promises
        ]
        verdicts = Counter(entry.verdict for entry in entries)
        self.repository.save_json(
            "promise_audit.json",
            PromiseAuditArtifact(
                promises=len(entries),
                fulfilled=verdicts["fulfilled"],
                weak=verdicts["weak"],
                broken=verdicts["broken"],
                fulfilled_ratio=round(verdicts["fulfilled"] / len(entries), 4) if entries else 0.0,
                entries=entries,
            ),
        )

    @staticmethod
    def _promise_entry(
        promise,
        check: PromiseCheck | None,
        ledger: PromiseLedger,
    ) -> PromiseAuditEntry:
        """Pair one promise of the ledger with the verdict the critic returned for it."""
        return PromiseAuditEntry(
            promise_id=promise.id,
            kind=promise.kind,
            primary=promise.id == ledger.primary_promise_id,
            verdict=check.verdict if check else "broken",
            opened=check.opened if check else False,
            progressed=check.progressed if check else False,
            paid=check.paid if check else False,
            evidence=check.evidence if check else "the critic returned no verdict for this promise",
        )

    @staticmethod
    def _validate_note_references(notes: list[RevisionNote], plan: StoryPlan) -> None:
        """Reject critic notes that point outside the canonical plan."""
        chapter_ids = {chapter.id for chapter in plan.chapters}
        event_ids = {event.id for event in plan.events}
        for note in notes:
            if set(note.chapter_ids) - chapter_ids:
                raise ValueError(f"revision note {note.id} references unknown chapters")
            if set(note.event_ids) - event_ids:
                raise ValueError(f"revision note {note.id} references unknown events")

    def _revise_chapters(
        self,
        request: StoryRequest,
        characters: CharactersArtifact,
        plan: StoryPlan,
        presentation: StoryPresentation,
        draft_bodies: list[str],
        review: StoryReview,
        ledger: PromiseLedger | None = None,
    ) -> list[str]:
        """Run Writer for every chapter with one bounded corrective retry."""
        assert self.repository is not None
        writer = WriterAgent(self.provider)
        event_by_id = {event.id: event for event in plan.events}
        revised_bodies: list[str] = []
        revision_results: list[ChapterRevisionResult] = []
        for index, (chapter, draft_body) in enumerate(
            zip(plan.chapters, draft_bodies, strict=True),
            1,
        ):
            percent = 84 + (index - 1) * 12 // len(plan.chapters)
            self._notify(
                percent,
                "revision",
                f"Corrigiendo capítulo {index} de {len(plan.chapters)}",
                index,
                len(plan.chapters),
            )
            events = [
                event_by_id[event_id]
                for event_id in plan.topological_order
                if event_by_id[event_id].chapter_id == chapter.id
            ]
            notes = self._notes_for_chapter(review.notes, chapter, events)
            if notes:
                character_ids = {item for event in events for item in event.character_ids}
                relevant = [item for item in characters.characters if item.id in character_ids]
                accepted, result = self._revise_one_chapter(
                    writer,
                    request,
                    relevant or characters.characters,
                    plan,
                    presentation,
                    chapter,
                    events,
                    notes,
                    draft_body,
                    revised_bodies[-1] if revised_bodies else "",
                    index,
                    self._promise_brief(ledger, chapter.id),
                )
            else:
                accepted, result = (
                    draft_body,
                    self._unrevised_chapter_result(
                        chapter,
                        index,
                        draft_body,
                    ),
                )
            revised_bodies.append(accepted)
            revision_results.append(result)
            self.repository.save_text(f"revisions/chapter-{index:03d}.md", accepted)
            self.repository.save_json(
                "revision_report.json",
                RevisionReport(chapters=revision_results),
            )
        self.repository.complete_stage("revision")
        return revised_bodies

    @staticmethod
    def _notes_for_chapter(
        notes: list[RevisionNote],
        chapter: ChapterPlan,
        events: list[PlotEvent],
    ) -> list[RevisionNote]:
        """Select global notes and notes that target this chapter or its events."""
        event_ids = {event.id for event in events}
        return [
            note
            for note in notes
            # A note is global only when it targets nothing at all. The critic is asked to cite
            # the affected event IDs and to leave chapter_ids empty for global notes, so a note
            # carrying only event_ids is local and must reach just the chapters owning them.
            if (
                not (note.chapter_ids or note.event_ids)
                or chapter.id in note.chapter_ids
                or bool(event_ids.intersection(note.event_ids))
            )
        ]

    @staticmethod
    def _unrevised_chapter_result(
        chapter: ChapterPlan,
        chapter_index: int,
        draft_body: str,
    ) -> ChapterRevisionResult:
        """Record a chapter the critic left untouched, so no Writer call is spent."""
        draft_words = word_count(draft_body)
        return ChapterRevisionResult(
            chapter_id=chapter.id,
            chapter_index=chapter_index,
            note_ids=[],
            draft_words=draft_words,
            attempts=[],
            final_source="draft",
            final_words=draft_words,
        )

    def _revise_one_chapter(
        self,
        writer: WriterAgent,
        request: StoryRequest,
        characters: list[CharacterProfile],
        plan: StoryPlan,
        presentation: StoryPresentation,
        chapter: ChapterPlan,
        events: list[PlotEvent],
        notes: list[RevisionNote],
        draft_body: str,
        previous_revised: str,
        chapter_index: int,
        promise_brief: str = "",
    ) -> tuple[str, ChapterRevisionResult]:
        """Return the first valid edited chapter, the best rejected one, or the draft (7.18)."""
        assert self.repository is not None
        repository = self.repository
        draft_words = word_count(draft_body)
        names = character_names(characters)

        def prefix(attempt: int) -> str:
            """Name the artifacts of one Writer attempt on the bound chapter."""
            return f"writer/chapter-{chapter_index:03d}-attempt-{attempt:03d}"

        def call(attempt: int, feedback: str) -> ParagraphEdits:
            """Ask the Writer for the bound chapter's edits with this attempt's feedback."""
            return self._call_agent(
                "writer",
                lambda: writer.run(
                    request,
                    characters,
                    plan,
                    presentation,
                    chapter,
                    events,
                    notes,
                    draft_body,
                    previous_revised,
                    feedback,
                    promise_brief,
                    style_examples=self.options.style_examples,
                ),
            )

        def judge(attempt: int, edits: ParagraphEdits) -> Judgement[str]:
            """Apply one attempt's edits to the draft, save them and judge the chapter."""
            edited = apply_chapter_edits(draft_body, notes, edits)
            repository.save_data(
                f"{prefix(attempt)}-edits.json",
                {"edits": edits.model_dump(mode="json")["edits"], **edited.as_record()},
            )
            repository.save_text(f"{prefix(attempt)}.md", edited.body)
            diagnostic, rank = writer_edit_issue(
                edited, draft_body, notes, names=names, editor=self.options.line_editor
            )
            return Judgement(edited.body, diagnostic, f"{prefix(attempt)}.md", rank)

        outcome = revise_with_retries(
            WRITER_ATTEMPTS,
            call,
            judge,
            lambda result: repository.save_json(
                f"{prefix(result.attempt)}-validation.json", result
            ),
            "Return the complete list of edits.",
        )
        result = ChapterRevisionResult(
            chapter_id=chapter.id,
            chapter_index=chapter_index,
            note_ids=[note.id for note in notes],
            draft_words=draft_words,
            attempts=outcome.attempts,
            final_source="draft",
            final_words=draft_words,
        )
        if outcome.accepted is not None:
            return outcome.accepted, result.model_copy(
                update={"final_source": "revision", "final_words": word_count(outcome.accepted)}
            )
        if outcome.best is not None and outcome.best_attempt is not None:
            # 7.18 (TD-3): an attempt that landed some edits beats the draft it was asked to fix.
            warning = writer_best_candidate_warning(
                chapter_index, outcome.best_attempt, outcome.attempts
            )
            self.repository.add_warning(warning)
            self._emit("writer_best_candidate", warning, stage="revision")
            return outcome.best, result.model_copy(
                update={
                    "final_source": "best_candidate",
                    "final_words": word_count(outcome.best),
                    "final_attempt": outcome.best_attempt,
                    "warning_code": "WRITER_BEST_CANDIDATE",
                }
            )
        warning = writer_fallback_warning(chapter_index, draft_words, outcome.attempts)
        self.repository.add_warning(warning)
        self._emit("writer_fallback", warning, stage="revision")
        return draft_body, result.model_copy(update={"warning_code": "WRITER_REVISION_REJECTED"})

    def _finalize(
        self,
        request: StoryRequest,
        plan: StoryPlan,
        story: str,
    ) -> None:
        """Persist observed metrics, metadata, and story."""
        assert self.repository is not None
        self.repository.save_json(
            "story_metrics.json",
            story_metrics(request, plan, story),
        )
        self._publish(story, "Guardando la historia", "Historia terminada")

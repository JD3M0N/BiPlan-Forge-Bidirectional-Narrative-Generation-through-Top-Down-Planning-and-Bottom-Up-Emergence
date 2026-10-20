"""The narration stage: the story written from the performance log, mixed into StoryPipeline.

Split from stage/stages.py in 7.20 because it is the half of the hybrid that changes most often:
what the narrator reads, how its chapters are reviewed, and what ships when no attempt passes.
Like the rest of stage/, it assumes it is mixed into StoryPipeline and calls the attributes and
helpers pipeline.py defines (self.repository, self.provider, self._notify, self._emit,
self._call_agent), plus _localized_titles and _presentation_from from SimulationStagesMixin.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..agents import NarratorAgent
from ..formats import NarrationMethod, SimulationMode
from ..runtime.errors import NON_DEGRADABLE_ERRORS
from ..schemas import (
    CharactersArtifact,
    PlayScript,
    PromiseLedger,
    StoryPlan,
    StoryRequest,
    WorldArtifact,
)
from ..writing.acceptance import writer_candidate_issue
from ..writing.assembly import assemble_story, narrated_plan
from ..writing.audit import word_count
from ..writing.line_edit import COPIED_DIRECTION
from . import fallback
from .editorial import (
    copied_directions,
    craft_findings,
    editorial_verdict,
    review_turns,
    severity,
    strip_markers,
)
from .narration import (
    AcceptedReports,
    ChapterView,
    accept_reports,
    chapter_views,
    choose_narrator,
    lines_to_report,
    narrated_chapter_ids,
    scene_presence,
    unreported,
    whole_lines_wanted,
)
from .render import scene_log
from .schemas import CastBible, ChapterNarration, NarrationArtifact, PerformanceArtifact
from .selection import (
    accept_selection,
    chapter_cast,
    chapter_places,
    last_paragraph,
    scene_settings,
    script_scenes,
    selection_lines,
    selection_material,
    selector_view,
)

NARRATION_ATTEMPTS = 2


@dataclass(frozen=True)
class ChapterMaterial:
    """What one chapter is narrated from, and the retellings the narrator read in place of lines."""

    text: str
    selected: bool = False
    retold: dict[str, str] = field(default_factory=dict)


def _measured(notes: list[str]) -> int:
    """Count the measured craft findings of a chapter, leaving out the note that guards them."""
    return sum(1 for note in notes if not note.startswith("KEEP:"))


class NarrationStageMixin:
    """Narrate a performed play chapter by chapter, through the configured point of view."""

    def _narrate(
        self,
        request: StoryRequest,
        characters: CharactersArtifact,
        plan: StoryPlan,
        play: PlayScript,
        performance: PerformanceArtifact,
        ledger: PromiseLedger | None,
        *,
        world: WorldArtifact | None = None,
        bible: CastBible | None = None,
    ) -> tuple[str, NarrationArtifact, int, StoryPlan]:
        """Write the story from the performance log, through the configured point of view.

        Also returns the plan cut to the chapters actually narrated: story_metrics has to walk
        the same chapters the story holds.
        """
        assert self.repository is not None
        self._notify(84, "narration", "Escribiendo la historia desde la funcion")
        voice = self.narrative_voice
        names = {member.character_id: member.name for member in play.cast}
        presence = scene_presence(play)
        choice = choose_narrator(
            voice,
            performance.scenes,
            requested=self.options.narrator,
            names=names,
            protagonist=_protagonist(characters),
            presence=presence,
        )
        if choice.warning:
            self.repository.add_warning(choice.warning)
            self._emit("narrator_fallback", choice.warning, stage="narration")
        narrator = choice.character_id
        titles = self._localized_titles(play)
        if self.options.simulation_mode is SimulationMode.ADAPTIVE:
            titles = {
                chapter.id: f"Cap\u00edtulo {index}"
                for index, chapter in enumerate(plan.chapters, 1)
            }
        views = chapter_views(voice, plan, performance.scenes, narrator=narrator, presence=presence)

        agent = NarratorAgent(self.provider)
        bodies: list[str] = []
        records: list[ChapterNarration] = []
        fallbacks = 0
        # Who an earlier chapter already brought on, so REPARTO introduces each one once.
        introduced: set[str] = set()
        for view in views:
            index, chapter, total = view.index, view.chapter, len(plan.chapters)
            self._notify(
                84 + (index - 1) * 10 // total,
                "narration",
                f"Narrando el capitulo {index} de {total}",
                index,
                total,
            )
            if not view.visible:
                self._skip_unseen_chapter(index, narrator, names)
                records.append(_chapter_record(view, words=0, attempts=0, source="absent"))
                continue
            key_ids = {
                item for scene in view.scenes for beat in scene.beats for item in beat.evidence
            }
            material = self._chapter_material(
                agent,
                request,
                view,
                key_ids,
                names,
                play,
                world=world,
                bible=bible,
                previous=bodies[-1] if bodies else "",
                introduced=introduced,
            )
            # Introduced means seen doing something: a silent member of a scene's cast was never
            # described, and the second 7.20 replay brought Celestina on bare in chapter 2.
            introduced.update(turn.actor_id for turn in view.visible if turn.kind == "actor")
            log = material.text
            visible_ids = {turn.id for turn in view.visible}
            facts = [
                fact
                for fact in performance.facts
                if fact.status == "established" and fact.source_turn_id in visible_ids
            ]
            if facts:
                log += "\nHECHOS OBSERVABLES ACEPTADOS:\n" + "\n".join(
                    fact.excerpt for fact in facts
                )
            body, attempts, source = self._narrate_chapter(
                agent,
                request,
                chapter,
                titles.get(chapter.id, chapter.title),
                voice,
                log,
                narrator,
                names,
                view.visible,
                index,
                selected=material.selected,
                retold=material.retold,
                characters=characters,
                world=world,
            )
            fallbacks += int(source == "fallback")
            if source == "narrator":
                body = self._line_edit_chapter(request, characters, world, index, body)
            bodies.append(body)
            records.append(
                _chapter_record(view, words=word_count(body), attempts=attempts, source=source)
            )

        narration = NarrationArtifact(
            narrative_voice=voice,
            narrator_character_id=narrator,
            requested_narrator=self.options.narrator,
            narrator_source=choice.source,
            narration_tone=self.options.narration_tone,
            chapters=records,
        )
        self.repository.save_json("narration.json", narration)
        narrated = narrated_plan(plan, narrated_chapter_ids(views))
        story = assemble_story(narrated, self._presentation_from(play, plan), bodies)
        self.repository.complete_stage("narration")
        return story, narration, fallbacks, narrated

    def _chapter_material(
        self, agent, request, view, key_ids, names, play, *, world, bible, previous, introduced=()
    ) -> ChapterMaterial:
        """Build what one chapter is narrated from, and say whether it is a selection.

        With narration_method=selected the narrator writes from the moments a first call chose
        (7.17); otherwise, or when that call cannot be used, from the 7.16 log, with the lines
        nobody turns on retold in indirect style and, since 7.20, every gesture, thought and
        world event retold in the past. Since 7.20 that log also opens each scene with its
        setting and the chapter with who is on stage and where the last one left off: the
        7.19 islands chapters jumped between places and brought people on unintroduced.
        """
        if self.options.narration_method is NarrationMethod.SELECTED:
            material = self._selected_material(
                agent, request, view, key_ids, names, play, world, bible, previous
            )
            if material is not None:
                return ChapterMaterial(material, selected=True)
        scenes = script_scenes(play)
        labels = {
            turn.scene_id: scenes[turn.scene_id].setting
            for turn in view.visible
            if turn.scene_id in scenes
        }
        accepted = self._report_lines(
            agent, request, view.visible, key_ids, names, view.index, settings=labels
        )
        reported = None
        if accepted is not None:
            # A kept line maps to no retelling: it is read as key and passed whole.
            reported = {**accepted.reports, **dict.fromkeys(accepted.kept, "")}
            key_ids = key_ids | set(accepted.kept)
            labels = {key: accepted.settings.get(key) or value for key, value in labels.items()}
        log = scene_log(
            view.visible,
            names,
            thoughts=True,
            key_ids=key_ids,
            short_names=True,
            reported=reported,
            gestures=accepted.gestures if accepted is not None else None,
            retold_thoughts=accepted.thoughts if accepted is not None else None,
            scene_labels=labels,
        )
        parts = []
        cast = chapter_cast(view.visible, scenes, names, bible, introduced=introduced)
        if cast:
            parts.append("REPARTO:\n" + "\n".join(f"- {member}" for member in cast))
        if previous:
            parts.append(f"FINAL DEL CAPÍTULO ANTERIOR:\n{last_paragraph(previous)}")
        parts.append(f"PERFORMANCE LOG:\n{log}")
        retold = dict(accepted.reports) if accepted is not None else {}
        return ChapterMaterial("\n\n".join(parts), retold=retold)

    def _selected_material(
        self, agent, request, view, key_ids, names, play, world, bible, previous
    ) -> str | None:
        """Choose the moments of one chapter and render them, or None to fall back to 7.16."""
        assert self.repository is not None
        lines = selection_lines(view.visible, names, key_ids)
        scenes = script_scenes(play)
        settings = scene_settings(view.visible, scenes)
        try:
            drafted = self._call_agent(
                "narrator_select",
                lambda: agent.select(request=request, scenes=settings, lines=selector_view(lines)),
            )
            selection = accept_selection(lines, drafted)
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception as exc:
            warning = (
                f"[SELECTION_FALLBACK] Capítulo {view.index}: no se pudieron elegir los momentos "
                f"({type(exc).__name__}); se narra desde el log con el estilo indirecto."
            )
            self.repository.add_warning(warning)
            self._emit("selection_fallback", warning, stage="narration")
            return None
        self.repository.save_data(
            f"narration/chapter-{view.index:03d}-selection.json", selection.as_record()
        )
        return selection_material(
            selection,
            view.visible,
            names,
            places=chapter_places(view.visible, scenes, world),
            cast=chapter_cast(view.visible, scenes, names, bible),
            previous=last_paragraph(previous),
        )

    def _report_lines(
        self, agent, request, visible, key_ids, names, index, *, settings=None
    ) -> AcceptedReports | None:
        """Retell a chapter's log as past-tense narration, or None to pass it as it was played."""
        assert self.repository is not None
        lines = lines_to_report(visible, key_ids, names, settings=settings)
        if not lines:
            return AcceptedReports()
        try:
            drafted = self._call_agent(
                "narrator_report", lambda: agent.report(request=request, lines=lines)
            )
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception as exc:
            # Whole lines are what 7.15.1 narrated from: worse, but never a lost chapter.
            warning = (
                f"[REPORT_FALLBACK] Capítulo {index}: no se pudieron resumir las réplicas "
                f"({type(exc).__name__}); el narrador las recibe enteras."
            )
            self.repository.add_warning(warning)
            self._emit("report_fallback", warning, stage="narration")
            return None
        accepted = accept_reports(lines, drafted, keep=whole_lines_wanted(visible, key_ids))
        missing = unreported(lines, accepted)
        if missing:
            # One more request for the lines left out or copied, never for the whole chapter.
            accepted.retried = [line["id"] for line in missing]
            try:
                again = self._call_agent(
                    "narrator_report", lambda: agent.report(request=request, lines=missing)
                )
            except NON_DEGRADABLE_ERRORS:
                raise
            except Exception:
                again = None
            if again is not None:
                accepted.merge(accept_reports(missing, again))
        self.repository.save_data(
            f"narration/chapter-{index:03d}-reported.json", accepted.as_record()
        )
        raw = [
            line["id"]
            for line in unreported(lines, accepted)
            if line["kind"] in ("gesture", "event", "setting")
        ]
        if raw:
            warning = (
                f"[GESTURE_REPORT_FALLBACK] Capítulo {index}: {len(raw)} acotaciones llegan al "
                "narrador tal como se representaron."
            )
            self.repository.add_warning(warning)
            self._emit("gesture_report_fallback", warning, stage="narration")
        return accepted

    def _repair_directions(self, request, characters, world, index, attempt, candidate, visible):
        """Have the paragraphs that paste a stage direction retold in the past (7.20).

        Until 7.19 a pasted direction cost the chapter a whole attempt as WRONG_TENSE, and in the
        islands run the second attempt pasted others. Only those paragraphs go to the editor,
        and an edit ships only if the paste is gone.
        """
        if characters is None or not copied_directions(candidate, visible):
            return candidate
        return self._line_edit_chapter(
            request,
            characters,
            world,
            index,
            candidate,
            directions=tuple(turn.action for turn in visible if turn.action),
            only=frozenset({COPIED_DIRECTION}),
            record=f"line_edits/chapter-{index:03d}-attempt-{attempt:03d}-directions.json",
        )

    def _skip_unseen_chapter(self, index: int, narrator: str, names: dict[str, str]) -> None:
        """Report a chapter left out because this point of view saw nothing of it."""
        assert self.repository is not None
        reason = (
            f"{names.get(narrator, narrator)} no presenció ninguna de sus escenas"
            if narrator
            else "no tiene ningún turno representado"
        )
        warning = f"[NARRATOR_ABSENT] Capítulo {index}: {reason}; se omite de la historia."
        self.repository.add_warning(warning)
        self._emit("narrator_absent", warning, stage="narration")

    def _narrate_chapter(
        self,
        agent,
        request,
        chapter,
        title,
        voice,
        log,
        narrator,
        names,
        visible,
        index,
        *,
        selected: bool = False,
        retold: dict[str, str] | None = None,
        characters: CharactersArtifact | None = None,
        world: WorldArtifact | None = None,
    ) -> tuple[str, int, str]:
        """Narrate one chapter, or render its log deterministically when the model cannot."""
        assert self.repository is not None
        feedback = ""
        candidates: list[tuple[int, int, int, str]] = []
        # An accepted chapter held back for one more attempt because it transcribed the log.
        polished: tuple[int, str, int] | None = None
        for attempt in range(1, NARRATION_ATTEMPTS + 1):

            def narrate_once(feedback_snapshot: str = feedback):
                """Narrate the bound chapter with this attempt's feedback."""
                write = agent.write if selected else agent.run
                return write(
                    request,
                    chapter,
                    title,
                    voice,
                    log,
                    narrator_name=names.get(narrator, ""),
                    retry_feedback=feedback_snapshot,
                    tone=self.options.narration_tone,
                    style_examples=self.options.style_examples,
                )

            try:
                candidate = self._call_agent("narrator", narrate_once).strip()
            except NON_DEGRADABLE_ERRORS:
                raise
            except Exception as exc:
                # Left on disk like a failed Writer rewrite, so a fallback chapter says why.
                self.repository.save_data(
                    f"narration/chapter-{index:03d}-attempt-{attempt:03d}-error.json",
                    {"attempt": attempt, "status": "failed", "exception_type": type(exc).__name__},
                )
                feedback = (
                    "\n\nRETRY CORRECTION:\nThe previous attempt could not be completed "
                    f"({type(exc).__name__}). Return the complete chapter."
                )
                continue
            candidate = strip_markers(candidate)
            candidate = self._repair_directions(
                request, characters, world, index, attempt, candidate, visible
            )
            self.repository.save_text(
                f"narration/chapter-{index:03d}-attempt-{attempt:03d}.md", candidate
            )
            diagnostic = writer_candidate_issue(candidate, "", [])
            if diagnostic is not None:
                feedback = (
                    "\n\nRETRY CORRECTION:\nThe previous attempt was rejected because "
                    f"{diagnostic.message}. {diagnostic.retry_instruction}"
                )
                continue
            try:
                review = self._call_agent(
                    "narrator_review",
                    lambda candidate=candidate: agent.review(
                        request=request,
                        voice=voice,
                        story=candidate,
                        turns=review_turns(visible, retold),
                    ),
                )
            except NON_DEGRADABLE_ERRORS:
                raise
            except Exception as exc:
                if polished is not None:
                    # An unreviewed rewrite never replaces a reviewed chapter.
                    break
                # A review that could not run says nothing against the chapter, so the
                # chapter stands: in 7.10 this path discarded sound prose for the fallback.
                self.repository.save_data(
                    f"narration/chapter-{index:03d}-review-{attempt:03d}.json",
                    {"accepted": True, "review_unavailable": type(exc).__name__},
                )
                warning = (
                    f"[NARRATION_REVIEW_UNAVAILABLE] Capítulo {index}: "
                    "se aceptó el capítulo sin revisión editorial."
                )
                self.repository.add_warning(warning)
                self._emit("narration_review_unavailable", warning, stage="narration")
                self.repository.save_text(f"narration/chapter-{index:03d}.md", candidate)
                return candidate, attempt, "narrator"
            verdict = editorial_verdict(
                review, candidate, visible, request.language, reports=retold
            )
            self.repository.save_data(
                f"narration/chapter-{index:03d}-review-{attempt:03d}.json",
                {"review": review.model_dump(mode="json"), **verdict.as_record()},
            )
            notes = (
                _editor_leaves(craft_findings(candidate, visible), self.options.line_editor)
                if verdict.accepted
                else []
            )
            if notes and polished is None and attempt < NARRATION_ATTEMPTS:
                # Accepted, but read like a transcript: one more attempt with the measured
                # notes, and this one ships unless the next one is better (7.15).
                polished = (attempt, candidate, _measured(notes))
                feedback = "\nCRAFT NOTES (curate, keep every event):\n" + "\n".join(notes)
                continue
            if verdict.accepted and polished is not None and _measured(notes) >= polished[2]:
                # 7.15.1: the notes are only worth a better chapter. In 7.15 the second
                # attempt kept every tag and moved into the imperfect, and it shipped.
                break
            if verdict.accepted:
                self.repository.save_text(f"narration/chapter-{index:03d}.md", candidate)
                return candidate, attempt, "narrator"
            candidates.append(
                (severity(verdict.blocking), len(verdict.blocking), attempt, candidate)
            )
            feedback = (
                "\nEDITORIAL REPAIR (one bounded correction, preserve source events):\n"
                + "\n".join(verdict.issues)
            )
        return self._ship_leftover(index, polished, candidates, visible, names, request.language)

    def _ship_leftover(
        self,
        index: int,
        polished: tuple[int, str, int] | None,
        candidates: list[tuple[int, int, int, str]],
        visible,
        names,
        language: str,
    ) -> tuple[str, int, str]:
        """Ship what is left once no attempt was accepted outright, best first."""
        assert self.repository is not None
        if polished is not None:
            attempt, body, _ = polished
            warning = (
                f"[NARRATION_CRAFT_KEPT_FIRST] Capítulo {index}: el intento con notas no "
                "mejoró el primero, que es el que se entrega."
            )
            self.repository.add_warning(warning)
            self._emit("narration_craft_kept_first", warning, stage="narration")
            self.repository.save_text(f"narration/chapter-{index:03d}.md", body)
            return body, attempt, "narrator"
        if candidates:
            # The lightest findings win, weighed by severity, and the later attempt on a tie: it
            # already had the corrections. Model prose with a disputed detail still reads better
            # than the log.
            _, blocking, attempt, body = min(candidates, key=lambda item: (item[0], -item[2]))
            warning = (
                f"[NARRATION_BEST_ATTEMPT] Capítulo {index}: se entregó el intento {attempt} "
                f"con {blocking} observaciones editoriales sin resolver."
            )
            self.repository.add_warning(warning)
            self._emit("narration_best_attempt", warning, stage="narration")
            self.repository.save_text(f"narration/chapter-{index:03d}.md", body)
            return body, attempt, "narrator"
        body = fallback.narrate(visible, names, language)
        warning = f"[NARRATION_FALLBACK] Capítulo {index}: se narró con el narrador de respaldo."
        self.repository.add_warning(warning)
        self._emit("narration_fallback", warning, stage="narration")
        self.repository.save_text(f"narration/chapter-{index:03d}.md", body)
        return body, NARRATION_ATTEMPTS, "fallback"


def _chapter_record(view: ChapterView, *, words: int, attempts: int, source: str):
    """Describe one chapter of the narration from what its point of view could see."""
    return ChapterNarration(
        chapter_id=view.chapter.id,
        chapter_index=view.index,
        scene_ids=[scene.scene_id for scene in view.scenes],
        turns_available=view.available,
        turns_visible=len(view.visible),
        words=words,
        attempts=attempts,
        source=source,
    )


def _protagonist(characters: CharactersArtifact) -> str:
    """Name the character the cast declares as its subject, or nobody when none is declared."""
    for item in characters.characters:
        if item.functional_role == "subject":
            return item.id
    return ""


def _editor_leaves(notes: list[str], editor: bool) -> list[str]:
    """Keep only the notes a line editor cannot answer, when one will read the chapter (7.17).

    TRANSCRIBED and TAGGED cost a whole second narration since 7.15, and the second attempt
    rarely improved on the first. With the editor on, a tag is its work, paragraph by paragraph;
    a world event the chapter dropped is not, so DROPPED_EVENT still asks for another attempt.
    """
    if not editor:
        return notes
    kept = [note for note in notes if note.startswith("DROPPED_EVENT")]
    return [*kept, *(note for note in notes if note.startswith("KEEP"))] if kept else []

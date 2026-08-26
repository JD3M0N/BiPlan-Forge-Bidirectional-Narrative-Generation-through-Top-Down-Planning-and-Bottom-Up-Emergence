"""Deterministic validation and sanitization for post-STORYLINE craft."""

from __future__ import annotations

from .craft_models import (
    ChapterCraftView, ChapterWritingBrief, CharacterArcPlan, CharacterWritingCard,
    CraftAlignment, PromiseActionBrief, PromiseLedger, SceneWritingDirective,
    StoryCraftPlan, TryFailPlan, EntityStateBrief, FactualEventBrief,
    PlannedMutationBrief,
)
from .domain import CharactersArtifact, StoryOutlineArtifact, StoryRequest, TaxonomyBrief
from .schemas import CraftAuditAnswer, CraftAuditArtifact
from .storyline.models import IncrementalStorylineArtifact, StoryStateSnapshot


def try_fail_target(target_words: int) -> int:
    return max(1, min(6, round(target_words / 600)))


def main_characters(characters: CharactersArtifact):
    return [item for item in characters.characters if item.importance == "main"]


def validate_craft_characters(characters: CharactersArtifact) -> None:
    for character in main_characters(characters):
        if not character.flaw_cost.strip():
            raise ValueError(f"{character.id} needs an observable flaw cost")
        if character.slider_arc is None:
            raise ValueError(f"{character.id} needs a validated slider arc")


def _chapter_orders(outline: StoryOutlineArtifact) -> dict[str, int]:
    orders = {chapter.id: chapter.order for chapter in outline.chapters}
    if len(orders) != len(outline.chapters):
        raise ValueError("chapter IDs must be unique")
    return orders


def validate_promise_ledger(
    ledger: PromiseLedger, outline: StoryOutlineArtifact, target_words: int,
) -> None:
    orders = _chapter_orders(outline)
    final_chapter = max(outline.chapters, key=lambda item: item.order).id
    required_kinds = {"story_direction", "character_conflict", "genre_structure"}
    if {item.kind for item in ledger.promises} != required_kinds:
        raise ValueError("ledger needs direction, character/conflict, and genre promises")
    for promise in ledger.promises:
        chapter_ids = [
            promise.opening.chapter_id,
            *(item.chapter_id for item in promise.progress),
            promise.payoff.chapter_id,
        ]
        unknown = set(chapter_ids) - set(orders)
        if unknown:
            raise ValueError(f"promise {promise.id} references unknown chapters: {sorted(unknown)}")
        sequence = [orders[item] for item in chapter_ids]
        if sequence != sorted(sequence) or sequence[0] > sequence[-1]:
            raise ValueError(f"promise {promise.id} must open, progress, then pay off")
        if not promise.payoff.prepared_by_progress_ids:
            raise ValueError(f"promise {promise.id} has an unprepared payoff")
    primary = next(item for item in ledger.promises if item.id == ledger.primary_promise_id)
    if primary.payoff.chapter_id != final_chapter:
        raise ValueError("the primary promise must close in the final chapter")
    if target_words >= 1200 and len(primary.progress) < 2:
        raise ValueError("stories of 1200+ words need two primary-promise progresses")


def validate_character_arc_plan(
    plan: CharacterArcPlan, characters: CharactersArtifact,
    outline: StoryOutlineArtifact, ledger: PromiseLedger,
) -> None:
    mains = {item.id: item for item in main_characters(characters)}
    if {arc.character_id for arc in plan.arcs} != set(mains):
        raise ValueError("character arc plan must cover every main character exactly once")
    orders = _chapter_orders(outline)
    promise_ids = {item.id for item in ledger.promises}
    expected_stages = ["establishment", "pressure", "decisive_choice", "consequence"]
    for arc in plan.arcs:
        profile = mains[arc.character_id]
        assert profile.slider_arc is not None
        if arc.arc_type != profile.slider_arc.arc_type:
            raise ValueError(f"arc type mismatch for {arc.character_id}")
        if [item.stage for item in arc.evidences] != expected_stages:
            raise ValueError(f"{arc.character_id} needs four ordered arc evidences")
        if any(item.chapter_id not in orders for item in arc.evidences):
            raise ValueError(f"{arc.character_id} references an unknown chapter")
        if [orders[item.chapter_id] for item in arc.evidences] != sorted(
            orders[item.chapter_id] for item in arc.evidences
        ):
            raise ValueError(f"{arc.character_id} arc evidence is out of order")
        if arc.enables_or_prevents_promise_id not in promise_ids:
            raise ValueError(f"{arc.character_id} must connect internal and external payoffs")


def validate_try_fail_plan(
    plan: TryFailPlan, request: StoryRequest, outline: StoryOutlineArtifact,
    ledger: PromiseLedger,
) -> None:
    if len(plan.cycles) != try_fail_target(request.target_words):
        raise ValueError("try-fail cycle count does not match the adaptive target")
    chapter_ids = set(_chapter_orders(outline))
    promise_ids = {item.id for item in ledger.promises}
    if len({item.id for item in plan.cycles}) != len(plan.cycles):
        raise ValueError("try-fail IDs must be unique")
    for cycle in plan.cycles:
        if cycle.chapter_id not in chapter_ids or cycle.promise_id not in promise_ids:
            raise ValueError(f"invalid try-fail references in {cycle.id}")
        if cycle.lesson.strip() == cycle.stakes_change.strip():
            raise ValueError(f"{cycle.id} must both teach and change the stakes")


def all_craft_ids(
    ledger: PromiseLedger, arcs: CharacterArcPlan, try_fail: TryFailPlan,
) -> set[str]:
    return {
        beat_id for promise in ledger.promises
        for beat_id in [
            promise.opening.id, *(item.id for item in promise.progress), promise.payoff.id,
        ]
    } | {
        evidence.id for arc in arcs.arcs for evidence in arc.evidences
    } | {cycle.id for cycle in try_fail.cycles}


def validate_craft_alignment(
    alignment: CraftAlignment, chapters: list[ChapterCraftView],
    ledger: PromiseLedger, arcs: CharacterArcPlan, try_fail: TryFailPlan,
    outline: StoryOutlineArtifact, storyline: IncrementalStorylineArtifact,
) -> None:
    expected = all_craft_ids(ledger, arcs, try_fail)
    entries = {item.craft_id: item for item in alignment.entries}
    if set(entries) != expected:
        raise ValueError(
            "craft alignment mismatch: "
            f"missing={sorted(expected-set(entries))}, "
            f"extra={sorted(set(entries)-expected)}"
        )
    nodes = {item.id: item for item in storyline.nodes}
    for entry in entries.values():
        if not set(entry.node_ids) <= set(nodes):
            raise ValueError(f"{entry.craft_id} references an unaccepted node")
        if any(nodes[node_id].chapter_id != entry.chapter_id for node_id in entry.node_ids):
            raise ValueError(f"{entry.craft_id} crosses chapter boundaries")
    chapter_ids = set(_chapter_orders(outline))
    if {item.chapter_id for item in chapters} != chapter_ids:
        raise ValueError("chapter craft views must cover every chapter")
    promise_ids = {item.id for item in ledger.promises}
    for view in chapters:
        acted = {
            *view.opened_promise_ids, *view.progressed_promise_ids, *view.paid_promise_ids,
        }
        if not acted <= promise_ids:
            raise ValueError(f"chapter {view.chapter_id} references an unknown promise")
        for directive in view.scene_directives:
            node = nodes.get(directive.node_id)
            if node is None or node.chapter_id != view.chapter_id:
                raise ValueError("scene directives must reference accepted nodes in their chapter")
            if directive.outcome == "final_resolution" and node.node_type != "CEN":
                raise ValueError("simple final resolution is allowed only on CEN")


def character_writing_cards(characters: CharactersArtifact) -> list[CharacterWritingCard]:
    return [CharacterWritingCard(
        name=item.name,
        want=item.want,
        immediate_behavior=f"Pursue {item.goal}; under pressure, {item.flaw} costs {item.flaw_cost}.",
        voice=item.voice,
        notices=item.notices,
        unspoken_rule=item.unspoken_rule,
        flaw_pressure=item.flaw_cost,
    ) for item in characters.characters]


def build_chapter_writing_brief(
    chapter_id: str, craft: StoryCraftPlan, characters: CharactersArtifact,
    storyline: IncrementalStorylineArtifact,
    state_before: StoryStateSnapshot | None = None,
) -> ChapterWritingBrief:
    view = next(item for item in craft.chapters if item.chapter_id == chapter_id)
    actions: list[PromiseActionBrief] = []
    for promise in craft.promise_ledger.promises:
        if promise.id in view.opened_promise_ids:
            actions.append(PromiseActionBrief(
                phase="open", subject=promise.subject, instruction=promise.opening.signal,
            ))
        progress = next((item for item in promise.progress if item.chapter_id == chapter_id), None)
        if promise.id in view.progressed_promise_ids and progress:
            actions.append(PromiseActionBrief(
                phase="progress", subject=promise.subject,
                instruction=f"{progress.observable_delta}; introduce {progress.new_cost_or_information}.",
            ))
        if promise.id in view.paid_promise_ids:
            actions.append(PromiseActionBrief(
                phase="payoff", subject=promise.subject, instruction=promise.payoff.answer,
            ))
    nodes = {item.id: item for item in storyline.nodes}
    names = {item.id: item.name for item in characters.characters}
    if state_before:
        names.update({item.id: item.name for item in state_before.entities})
    for node in nodes.values():
        names[node.subject.id] = node.subject.name
        names[node.object.id] = node.object.name
    factual_events = [FactualEventBrief(
        event=node.event,
        intention=node.intention,
        conflict=node.conflict,
        consequence=node.consequence,
        location=names.get(node.location_id, node.location_id.replace("_", " ")),
        planned_changes=[PlannedMutationBrief(
            entity=names.get(change.entity_id, change.entity_id.replace("_", " ")),
            change=change.attribute,
            value=names.get(change.value, change.value),
        ) for change in node.effects],
    ) for node in nodes.values() if node.chapter_id == chapter_id]
    scenes = [SceneWritingDirective(
        event=nodes[item.node_id].event,
        goal=item.goal,
        conflict=item.conflict,
        outcome=item.outcome,
        consequence=item.consequence,
        reaction_dilemma_decision=" / ".join((item.reaction, item.dilemma, item.decision)),
    ) for item in view.scene_directives]
    arc_behaviors = [
        evidence.behavior
        for arc in craft.character_arcs.arcs for evidence in arc.evidences
        if evidence.chapter_id == chapter_id
    ]
    return ChapterWritingBrief(
        tone_guidance=craft.promise_ledger.tone.continuity_rule,
        factual_events=factual_events,
        state_before=[EntityStateBrief(
            entity=item.name, kind=item.kind,
            state={key: names.get(value, value) for key, value in item.state.items()},
            knowledge=item.knowledge,
        ) for item in (state_before.entities if state_before else [])],
        promise_actions=actions,
        scene_directives=scenes,
        character_cards=character_writing_cards(characters),
        arc_behaviors=arc_behaviors,
    )


def audit_questions(
    request: StoryRequest, craft: StoryCraftPlan, characters: CharactersArtifact,
    taxonomy_brief: TaxonomyBrief | None = None,
) -> list[dict[str, object]]:
    questions: list[dict[str, object]] = []

    def add(identifier: str, category: str, subject: str, question: str,
            chapter_ids: list[str] | None = None, blocking: bool = True) -> None:
        questions.append({
            "question_id": identifier, "category": category, "subject_id": subject,
            "question": question, "chapter_ids": chapter_ids or [], "blocking": blocking,
        })

    for promise in craft.promise_ledger.promises:
        chapters = [promise.opening.chapter_id, *(x.chapter_id for x in promise.progress), promise.payoff.chapter_id]
        add(f"promise:{promise.id}", "promise", promise.id,
            "Is this expectation visibly opened, changed through conflict, and paid off using its preparation?",
            chapters)
    for arc in craft.character_arcs.arcs:
        add(f"character:{arc.character_id}", "character", arc.character_id,
            "Do behavior, flaw cost, want/need choice, and consequence prove the planned arc direction?",
            [item.chapter_id for item in arc.evidences])
    for cycle in craft.try_fail.cycles:
        add(f"try_fail:{cycle.id}", "try_fail", cycle.id,
            "Does the attempt teach something and visibly raise or transform the cost?", [cycle.chapter_id])
    for index, constraint in enumerate(request.constraints, 1):
        add(f"constraint:{index}", "constraint", str(index),
            f"Does the fiction satisfy this explicit constraint: {constraint}")
    add("global:coherence", "coherence", "story",
        "Are world state, acquired knowledge, causal facts, and character motivations coherent?")
    add("global:pacing", "pacing", "story",
        "Does each chapter create perceptible progress and does escalation receive enough space?")
    add("global:engagement", "engagement", "story",
        "Do prepared questions, changing costs, and uncertainty sustain reader interest?", blocking=False)
    add("global:satisfaction", "satisfaction", "story",
        "Do the prepared promises receive costly, clear, and non-arbitrary fulfillment?")
    add("language:output", "language", request.language,
        f"Is all reader-visible fiction written in {request.language}?")
    add("global:scaffolding", "global", "story",
        "Is internal planning terminology absent from the fiction?", blocking=False)
    return questions


def normalize_audit(
    raw: CraftAuditArtifact, expected_questions: list[dict[str, object]],
) -> CraftAuditArtifact:
    supplied = {answer.question_id: answer for answer in raw.answers}
    answers: list[CraftAuditAnswer] = []
    for expected in expected_questions:
        identifier = str(expected["question_id"])
        answer = supplied.get(identifier)
        if answer is None:
            answer = CraftAuditAnswer(
                **expected, verdict="fail", evidence="The criterion was not evaluated.",
                issue="Missing critic answer.",
                revision_instruction="Evaluate and repair this criterion explicitly.",
            )
        else:
            payload = answer.model_dump()
            payload.update(expected)
            answer = CraftAuditAnswer.model_validate(payload)
        answers.append(answer)
    return CraftAuditArtifact(answers=answers, summary=raw.summary)

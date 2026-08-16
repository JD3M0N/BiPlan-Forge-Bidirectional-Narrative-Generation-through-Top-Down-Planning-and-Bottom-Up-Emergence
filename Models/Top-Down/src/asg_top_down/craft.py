"""Deterministic Sanderson-craft validation and audit helpers."""

from __future__ import annotations

import math

from .schemas import (
    Character, CharactersArtifact, CraftAuditAnswer, CraftAuditArtifact,
    CraftContractArtifact, DiagnosticAudit, IncrementalStorylineArtifact,
    StoryOutlineArtifact,
)


def try_fail_target(target_words: int) -> int:
    return max(2, min(7, math.ceil(target_words / 2000)))


def main_characters(characters: CharactersArtifact) -> list[Character]:
    return [character for character in characters.characters if character.importance == "main"]


def validate_craft_characters(characters: CharactersArtifact) -> None:
    mains = main_characters(characters)
    if not mains:
        raise ValueError("craft planning requires at least one main character")
    missing = [character.name for character in mains if character.slider_arc is None]
    if missing:
        raise ValueError(f"main characters require slider arcs: {', '.join(missing)}")


def validate_craft_contract(
    contract: CraftContractArtifact,
    characters: CharactersArtifact,
    target_words: int,
) -> None:
    validate_craft_characters(characters)
    expected_target = try_fail_target(target_words)
    if contract.try_fail_target != expected_target:
        raise ValueError(
            f"try_fail_target must be {expected_target} for {target_words} words"
        )
    expected = {character.name.casefold(): character.name for character in main_characters(characters)}
    promises = [promise for promise in contract.promises if promise.kind == "character"]
    actual_names = [promise.character_name.casefold() for promise in promises if promise.character_name]
    if len(actual_names) != len(set(actual_names)):
        raise ValueError("each main character must have exactly one character promise")
    if set(actual_names) != set(expected):
        raise ValueError("character promises must match the main cast exactly")


def _unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} ids must be unique")


def validate_craft_outline(
    outline: StoryOutlineArtifact,
    contract: CraftContractArtifact,
    characters: CharactersArtifact,
) -> None:
    chapter_orders = {chapter.id: chapter.order for chapter in outline.chapters}
    if len(chapter_orders) != len(outline.chapters):
        raise ValueError("chapter ids must be unique")
    promise_ids = {promise.id for promise in contract.promises}
    beats = [(chapter, beat) for chapter in outline.chapters for beat in chapter.craft_beats]
    milestones = [
        (chapter, milestone)
        for chapter in outline.chapters
        for milestone in chapter.character_milestones
    ]
    cycles = [(chapter, cycle) for chapter in outline.chapters for cycle in chapter.try_fail_cycles]
    _unique([beat.id for _, beat in beats], "craft beat")
    _unique([milestone.id for _, milestone in milestones], "character milestone")
    _unique([cycle.id for _, cycle in cycles], "try-fail cycle")

    for _, beat in beats:
        if beat.promise_id not in promise_ids:
            raise ValueError(f"unknown promise reference: {beat.promise_id}")
    for promise in contract.promises:
        linked = [(chapter.order, beat) for chapter, beat in beats if beat.promise_id == promise.id]
        setup = [item for item in linked if item[1].kind == "setup"]
        progress = [item for item in linked if item[1].kind == "progress"]
        payoff = [item for item in linked if item[1].kind == "payoff"]
        if len(setup) != 1 or not progress or len(payoff) != 1:
            raise ValueError(
                f"promise {promise.id} requires one setup, progress, and one payoff"
            )
        if not setup[0][0] <= min(order for order, _ in progress):
            raise ValueError(f"promise {promise.id} progresses before setup")
        if not max(order for order, _ in progress) <= payoff[0][0]:
            raise ValueError(f"promise {promise.id} pays off before progress")
        if promise.kind in {"tone", "plot"} and setup[0][0] != min(chapter_orders.values()):
            raise ValueError(f"{promise.kind} promise {promise.id} must be set up in the opening chapter")

    mains = {character.name.casefold(): character for character in main_characters(characters)}
    for key, character in mains.items():
        linked = [(chapter.order, item) for chapter, item in milestones
                  if item.character_name.casefold() == key]
        by_stage = {stage: [item for item in linked if item[1].stage == stage]
                    for stage in ("start", "transition", "end")}
        if any(len(items) != 1 for items in by_stage.values()):
            raise ValueError(
                f"main character {character.name} requires start, transition, and end milestones"
            )
        arc = character.slider_arc
        assert arc is not None
        if any(item[1].focus_slider != arc.focus for item in linked):
            raise ValueError(f"milestones for {character.name} use the wrong focus slider")
        if by_stage["start"][0][1].demonstrated_value != getattr(arc, arc.focus).start:
            raise ValueError(f"start milestone for {character.name} does not match the slider")
        if by_stage["end"][0][1].demonstrated_value != getattr(arc, arc.focus).target:
            raise ValueError(f"end milestone for {character.name} does not match the slider")
        orders = [by_stage[stage][0][0] for stage in ("start", "transition", "end")]
        if orders != sorted(orders):
            raise ValueError(f"milestones for {character.name} are out of order")
    unknown_milestones = [item.character_name for _, item in milestones
                          if item.character_name.casefold() not in mains]
    if unknown_milestones:
        raise ValueError("character milestones may only reference main characters")

    if len(cycles) != contract.try_fail_target:
        raise ValueError(
            f"outline requires exactly {contract.try_fail_target} try-fail cycles"
        )
    for _, cycle in cycles:
        if cycle.promise_id not in promise_ids:
            raise ValueError(f"unknown promise reference: {cycle.promise_id}")


def validate_storyline_craft(
    storyline: IncrementalStorylineArtifact,
    outline: StoryOutlineArtifact,
) -> None:
    expected_beats = {beat.id: beat for chapter in outline.chapters for beat in chapter.craft_beats}
    expected_milestones = {
        item.id: item for chapter in outline.chapters for item in chapter.character_milestones
    }
    expected_cycles = {
        item.id: item for chapter in outline.chapters for item in chapter.try_fail_cycles
    }
    beat_nodes: dict[str, list] = {identifier: [] for identifier in expected_beats}
    milestone_nodes: dict[str, list] = {identifier: [] for identifier in expected_milestones}
    cycle_nodes: dict[str, list] = {identifier: [] for identifier in expected_cycles}
    for node in storyline.nodes:
        for identifier in node.craft_beat_ids:
            if identifier not in beat_nodes:
                raise ValueError(f"unknown craft beat on storyline node: {identifier}")
            beat_nodes[identifier].append(node)
        for identifier in node.character_milestone_ids:
            if identifier not in milestone_nodes:
                raise ValueError(f"unknown character milestone on storyline node: {identifier}")
            milestone_nodes[identifier].append(node)
        for identifier in node.try_fail_cycle_ids:
            if identifier not in cycle_nodes:
                raise ValueError(f"unknown try-fail cycle on storyline node: {identifier}")
            cycle_nodes[identifier].append(node)

    for label, mapping in (("craft beat", beat_nodes), ("character milestone", milestone_nodes),
                           ("try-fail cycle", cycle_nodes)):
        invalid = [identifier for identifier, nodes in mapping.items() if len(nodes) != 1]
        if invalid:
            raise ValueError(f"each {label} must be covered once: {', '.join(invalid)}")

    for promise_id in {beat.promise_id for beat in expected_beats.values()}:
        nodes_by_kind = {
            kind: [beat_nodes[identifier][0] for identifier, beat in expected_beats.items()
                   if beat.promise_id == promise_id and beat.kind == kind]
            for kind in ("setup", "progress", "payoff")
        }
        setup_order = nodes_by_kind["setup"][0].global_order
        payoff_order = nodes_by_kind["payoff"][0].global_order
        if any(not setup_order < node.global_order < payoff_order
               for node in nodes_by_kind["progress"]):
            raise ValueError(f"storyline order is invalid for promise {promise_id}")

    outgoing = {edge.source for edge in storyline.accepted_edges}
    for identifier, cycle in expected_cycles.items():
        node = cycle_nodes[identifier][0]
        if node.try_fail_outcome != cycle.outcome:
            raise ValueError(f"try-fail outcome mismatch for {identifier}")
        if cycle.consequence not in node.effects:
            raise ValueError(f"try-fail consequence is not an effect for {identifier}")
        if node.id not in outgoing:
            raise ValueError(f"try-fail consequence has no later causal node: {identifier}")


def audit_questions(
    contract: CraftContractArtifact,
    characters: CharactersArtifact,
    outline: StoryOutlineArtifact,
) -> list[dict[str, object]]:
    questions: list[dict[str, object]] = []

    def add(identifier: str, category: str, subject: str, question: str,
            blocking: bool = True) -> None:
        questions.append({"question_id": identifier, "category": category,
                          "subject_id": subject, "question": question,
                          "blocking": blocking})

    for promise in contract.promises:
        prefix = f"promise:{promise.id}"
        add(f"{prefix}:setup", "promise", promise.id, "Is the promise clearly established in the prose?")
        add(f"{prefix}:progress", "promise", promise.id, "Does the prose visibly advance this promise?")
        add(f"{prefix}:payoff", "promise", promise.id, "Does the ending deliver this promise?")
        add(f"{prefix}:earned", "promise", promise.id,
            "Is the payoff surprising yet earned by prior progress?", False)
    for character in main_characters(characters):
        prefix = f"character:{character.name}"
        add(f"{prefix}:start", "character", character.name,
            "Does behavior establish the initial focus-slider state?")
        add(f"{prefix}:transition", "character", character.name,
            "Is there an observable intermediate change in the focus slider?")
        add(f"{prefix}:choice", "character", character.name,
            "Does the focus-slider change affect consequential choices?")
        add(f"{prefix}:end", "character", character.name,
            "Does final behavior demonstrate the target state without explaining a score?")
    for chapter in outline.chapters:
        for cycle in chapter.try_fail_cycles:
            prefix = f"try_fail:{cycle.id}"
            add(f"{prefix}:attempt", "try_fail", cycle.id,
                "Is a concrete attempt dramatized?")
            add(f"{prefix}:outcome", "try_fail", cycle.id,
                "Does the attempt resolve as the planned Yes-but or No-and outcome?")
            add(f"{prefix}:consequence", "try_fail", cycle.id,
                "Does its cost persist and escalate later events?")
    add("global:causality", "global", "story", "Does the revision preserve causal facts and dependencies?")
    add("global:progress", "global", "story", "Does the middle advance the promises the opening actually makes?")
    add("global:scaffolding", "global", "story",
        "Is all planning terminology absent from the fiction?", False)
    return questions


def normalize_audit(
    raw: CraftAuditArtifact,
    expected_questions: list[dict[str, object]],
) -> CraftAuditArtifact:
    supplied = {answer.question_id: answer for answer in raw.answers}
    answers: list[CraftAuditAnswer] = []
    for expected in expected_questions:
        identifier = str(expected["question_id"])
        answer = supplied.get(identifier)
        if answer is None:
            answer = CraftAuditAnswer(
                **expected,
                verdict="fail",
                evidence="The critic did not provide evidence for this required question.",
                issue="The criterion was not evaluated.",
                revision_instruction="Evaluate and repair this criterion explicitly.",
            )
        else:
            payload = answer.model_dump()
            payload.update(expected)
            answer = CraftAuditAnswer.model_validate(payload)
        answers.append(answer)
    return CraftAuditArtifact(answers=answers, summary=raw.summary)


def diagnostic_from_craft(audit: CraftAuditArtifact) -> DiagnosticAudit:
    failed = [answer for answer in audit.answers if answer.verdict == "fail"]
    return DiagnosticAudit(
        causal_issues=[answer.issue for answer in failed if answer.question_id == "global:causality"],
        intentionality_issues=[answer.issue for answer in failed if answer.category == "character"],
        continuity_issues=[answer.issue for answer in failed
                           if answer.category in {"promise", "try_fail"}],
        template_like_passages=[answer.issue for answer in failed
                                if answer.question_id == "global:scaffolding"],
        revision_suggestions=audit.revision_instructions,
    )

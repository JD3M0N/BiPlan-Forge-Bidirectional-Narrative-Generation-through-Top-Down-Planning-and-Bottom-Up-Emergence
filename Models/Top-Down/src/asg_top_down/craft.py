"""Pure contracts, adapters, validation, and audit helpers for modular story craft."""

from __future__ import annotations

import math

from .schemas import (
    ChapterPPPPlan, ChapterPlan, ChapterWritingBrief, Character, CharacterArcPlan,
    CharactersArtifact, CraftAuditAnswer, CraftAuditArtifact, DiagnosticAudit,
    GlobalPPPLine, GlobalPPPPlan, IncrementalStorylineArtifact, ObligationTraceEntry,
    PPPLineBrief, StoryCraftPlan, StoryOutlineArtifact, StoryRequest,
    StorylineObligation, StorylineObligationsArtifact, StorylineObligationTrace,
    TaxonomyBrief, TryFailPlan,
)


def try_fail_target(target_words: int) -> int:
    return max(2, min(7, math.ceil(target_words / 2000)))


def main_characters(characters: CharactersArtifact) -> list[Character]:
    return [character for character in characters.characters if character.importance == "main"]


def validate_craft_characters(characters: CharactersArtifact) -> None:
    mains = main_characters(characters)
    if not mains:
        raise ValueError("character planning requires at least one main character")
    missing = [character.name for character in mains if character.slider_arc is None]
    if missing:
        raise ValueError(f"main characters require slider arcs: {', '.join(missing)}")


def global_lines(plan: GlobalPPPPlan) -> list[GlobalPPPLine]:
    return [plan.primary_line, *plan.secondary_lines]


def global_points(plan: GlobalPPPPlan):
    return [point for line in global_lines(plan)
            for point in [line.promise, *line.progress, line.payoff]]


def _chapter_orders(outline: StoryOutlineArtifact) -> dict[str, int]:
    orders = {chapter.id: chapter.order for chapter in outline.chapters}
    if len(orders) != len(outline.chapters):
        raise ValueError("outline chapter ids must be unique")
    return orders


def validate_global_ppp(plan: GlobalPPPPlan, outline: StoryOutlineArtifact) -> None:
    orders = _chapter_orders(outline)
    for line in global_lines(plan):
        points = [line.promise, *line.progress, line.payoff]
        unknown = [point.chapter_id for point in points if point.chapter_id not in orders]
        if unknown:
            raise ValueError(f"global PPP line {line.id} references unknown chapters: {unknown}")
        point_orders = [orders[point.chapter_id] for point in points]
        if point_orders != sorted(point_orders):
            raise ValueError(f"global PPP line {line.id} is out of order")
    first = min(orders.values())
    last = max(orders.values())
    if orders[plan.primary_line.promise.chapter_id] != first:
        raise ValueError("the primary promise must begin in the first chapter")
    if orders[plan.primary_line.payoff.chapter_id] != last:
        raise ValueError("the primary payoff must occur in the final chapter")
    covered = {point.chapter_id for point in global_points(plan)}
    missing = set(orders) - covered
    if missing:
        raise ValueError(f"global PPP must schedule at least one point in every chapter: {sorted(missing)}")


def validate_character_arc_plan(
    plan: CharacterArcPlan,
    outline: StoryOutlineArtifact,
    characters: CharactersArtifact,
) -> None:
    validate_craft_characters(characters)
    orders = _chapter_orders(outline)
    mains = {character.name.casefold(): character for character in main_characters(characters)}
    grouped = {name: [] for name in mains}
    for milestone in plan.milestones:
        key = milestone.character_name.casefold()
        if key not in mains:
            raise ValueError(f"unknown main character milestone: {milestone.character_name}")
        if milestone.chapter_id not in orders:
            raise ValueError(f"character milestone references unknown chapter: {milestone.chapter_id}")
        grouped[key].append(milestone)
    for key, milestones in grouped.items():
        if len(milestones) != 3 or {item.stage for item in milestones} != {
            "start", "transition", "end",
        }:
            raise ValueError(
                f"main character {mains[key].name} requires start, transition, and end milestones"
            )
        by_stage = {item.stage: item for item in milestones}
        sequence = [orders[by_stage[stage].chapter_id]
                    for stage in ("start", "transition", "end")]
        if sequence != sorted(sequence):
            raise ValueError(f"milestones for {mains[key].name} are out of order")


def validate_try_fail_plan(
    plan: TryFailPlan,
    outline: StoryOutlineArtifact,
    target_words: int,
) -> None:
    known = set(_chapter_orders(outline))
    expected = try_fail_target(target_words)
    if len(plan.cycles) != expected:
        raise ValueError(f"try-fail plan requires exactly {expected} cycles")
    ids = [cycle.id for cycle in plan.cycles]
    if len(ids) != len(set(ids)):
        raise ValueError("try-fail cycle ids must be unique")
    if any(cycle.chapter_id not in known for cycle in plan.cycles):
        raise ValueError("try-fail cycles may only reference outline chapters")


def build_storyline_obligations(
    global_ppp: GlobalPPPPlan,
    character_arcs: CharacterArcPlan,
    try_fail: TryFailPlan,
) -> StorylineObligationsArtifact:
    obligations: list[StorylineObligation] = []
    for line in global_lines(global_ppp):
        for phase, points in (
            ("promise", [line.promise]), ("progress", line.progress), ("payoff", [line.payoff]),
        ):
            obligations.extend(StorylineObligation(
                id=point.id,
                chapter_id=point.chapter_id,
                source="global_ppp",
                phase=phase,
                description=point.description,
            ) for point in points)
    obligations.extend(StorylineObligation(
        id=f"character:{item.character_name}:{item.stage}",
        chapter_id=item.chapter_id,
        source="character_arc",
        phase=item.stage,
        description=item.description,
    ) for item in character_arcs.milestones)
    obligations.extend(StorylineObligation(
        id=f"try_fail:{item.id}",
        chapter_id=item.chapter_id,
        source="try_fail",
        phase=item.outcome,
        description=f"{item.action}; consequence: {item.consequence}",
    ) for item in try_fail.cycles)
    return StorylineObligationsArtifact(obligations=obligations)


def validate_storyline_obligations(
    artifact: StorylineObligationsArtifact,
    outline: StoryOutlineArtifact,
) -> None:
    known = set(_chapter_orders(outline))
    ids = [item.id for item in artifact.obligations]
    if len(ids) != len(set(ids)):
        raise ValueError("storyline obligation ids must be unique")
    unknown = [item.chapter_id for item in artifact.obligations if item.chapter_id not in known]
    if unknown:
        raise ValueError(f"storyline obligations reference unknown chapters: {unknown}")


def expected_global_point_ids(global_ppp: GlobalPPPPlan, chapter_id: str) -> set[str]:
    return {point.id for point in global_points(global_ppp) if point.chapter_id == chapter_id}


def validate_chapter_ppp(
    plan: ChapterPPPPlan,
    chapter: ChapterPlan,
    storyline: IncrementalStorylineArtifact,
    global_ppp: GlobalPPPPlan,
) -> None:
    if plan.chapter_id != chapter.id:
        raise ValueError(f"chapter PPP expected {chapter.id}, received {plan.chapter_id}")
    chapter_nodes = {node.id: node for node in storyline.nodes if node.chapter_id == chapter.id}
    beats = [plan.promise, *plan.progress, plan.payoff]
    referenced = [node_id for beat in beats for node_id in beat.node_ids]
    unknown = [node_id for node_id in referenced if node_id not in chapter_nodes]
    if unknown:
        raise ValueError(f"chapter PPP references unknown or foreign nodes: {unknown}")
    positions = [min(chapter_nodes[node_id].local_order for node_id in beat.node_ids)
                 for beat in beats]
    if positions != sorted(positions):
        raise ValueError("chapter PPP beats must follow accepted node order")
    expected = expected_global_point_ids(global_ppp, chapter.id)
    supplied = set(plan.advances_global_point_ids)
    all_ids = {point.id for point in global_points(global_ppp)}
    if supplied - all_ids:
        raise ValueError(f"chapter PPP references unknown global points: {sorted(supplied - all_ids)}")
    if supplied - expected:
        raise ValueError(
            f"chapter PPP references global points scheduled for another chapter: "
            f"{sorted(supplied - expected)}"
        )
    if expected - supplied:
        raise ValueError(f"chapter PPP leaves global points uncovered: {sorted(expected - supplied)}")


def validate_chapter_ppp_plans(
    plans: list[ChapterPPPPlan],
    outline: StoryOutlineArtifact,
    storyline: IncrementalStorylineArtifact,
    global_ppp: GlobalPPPPlan,
) -> None:
    expected_chapters = {chapter.id for chapter in outline.chapters}
    actual = [plan.chapter_id for plan in plans]
    if len(actual) != len(set(actual)) or set(actual) != expected_chapters:
        raise ValueError("chapter PPP plans must match outline chapters exactly")
    by_id = {chapter.id: chapter for chapter in outline.chapters}
    for plan in plans:
        validate_chapter_ppp(plan, by_id[plan.chapter_id], storyline, global_ppp)
    covered = {identifier for plan in plans for identifier in plan.advances_global_point_ids}
    required = {point.id for point in global_points(global_ppp)}
    if required - covered:
        raise ValueError(f"global PPP coverage is incomplete: {sorted(required - covered)}")


def build_obligation_trace(plans: list[ChapterPPPPlan]) -> StorylineObligationTrace:
    entries: list[ObligationTraceEntry] = []
    for plan in plans:
        node_ids = list(dict.fromkeys(
            node_id for beat in [plan.promise, *plan.progress, plan.payoff]
            for node_id in beat.node_ids
        ))
        entries.extend(ObligationTraceEntry(
            obligation_id=identifier,
            chapter_id=plan.chapter_id,
            node_ids=node_ids,
        ) for identifier in plan.advances_global_point_ids)
    return StorylineObligationTrace(entries=entries)


def build_chapter_writing_brief(
    global_ppp: GlobalPPPPlan,
    chapter_ppp: ChapterPPPPlan,
    character_arcs: CharacterArcPlan,
    try_fail: TryFailPlan,
) -> ChapterWritingBrief:
    return ChapterWritingBrief(
        tone_promise=(
            f"{global_ppp.tone_promise.description}. Opening signal: "
            f"{global_ppp.tone_promise.opening_signal}. Continuity: "
            f"{global_ppp.tone_promise.continuity_rule}"
        ),
        global_lines=[PPPLineBrief(
            kind=line.kind,
            subject=line.subject,
            promise=line.promise.description,
            progress=[point.description for point in line.progress],
            payoff=line.payoff.description,
        ) for line in global_lines(global_ppp)],
        chapter_promise=chapter_ppp.promise.description,
        chapter_progress=[beat.description for beat in chapter_ppp.progress],
        chapter_payoff=chapter_ppp.payoff.description,
        character_milestones=[item.description for item in character_arcs.milestones
                              if item.chapter_id == chapter_ppp.chapter_id],
        try_fail_cycles=[
            f"{item.action}; {item.outcome}; persistent consequence: {item.consequence}"
            for item in try_fail.cycles if item.chapter_id == chapter_ppp.chapter_id
        ],
    )


def audit_questions(
    request: StoryRequest,
    craft: StoryCraftPlan,
    characters: CharactersArtifact,
    taxonomy_brief: TaxonomyBrief | None = None,
) -> list[dict[str, object]]:
    questions: list[dict[str, object]] = []

    def add(identifier: str, category: str, subject: str, question: str,
            blocking: bool = True) -> None:
        questions.append({
            "question_id": identifier, "category": category, "subject_id": subject,
            "question": question, "blocking": blocking,
        })

    add("global_ppp:tone", "global_ppp", "tone",
        "Does the fiction establish and consistently honor the planned tone promise?")
    for line in global_lines(craft.global_ppp):
        prefix = f"global_ppp:{line.id}"
        add(f"{prefix}:promise", "global_ppp", line.id,
            f"Does the opening establish this expectation: {line.promise.description}")
        add(f"{prefix}:progress", "global_ppp", line.id,
            "Does the reader receive visible, conflict-bearing progress toward this payoff?")
        add(f"{prefix}:payoff", "global_ppp", line.id,
            f"Does the fiction fulfill this payoff: {line.payoff.description}")
        add(f"{prefix}:earned", "global_ppp", line.id,
            "Is the payoff both prepared and satisfyingly surprising?")
    for chapter in craft.chapters:
        prefix = f"chapter_ppp:{chapter.chapter_id}"
        add(f"{prefix}:promise", "chapter_ppp", chapter.chapter_id,
            "Does this chapter establish its local expectation?")
        add(f"{prefix}:progress", "chapter_ppp", chapter.chapter_id,
            "Does this chapter visibly advance that expectation through conflict?")
        add(f"{prefix}:payoff", "chapter_ppp", chapter.chapter_id,
            "Does this chapter resolve or consequentially transform its expectation?")
    for character in main_characters(characters):
        prefix = f"character:{character.name}"
        add(f"{prefix}:start", "character", character.name,
            "Does behavior establish the character's initially low focus slider?")
        add(f"{prefix}:transition", "character", character.name,
            "Is there an observable intermediate change in the focus slider?")
        add(f"{prefix}:choice", "character", character.name,
            "Does focus-slider growth affect a consequential choice?")
        add(f"{prefix}:end", "character", character.name,
            "Does final behavior demonstrate that the focus slider has become high?")
    for cycle in craft.try_fail.cycles:
        prefix = f"try_fail:{cycle.id}"
        add(f"{prefix}:outcome", "try_fail", cycle.id,
            "Is the planned Yes-but or No-and attempt dramatized?")
        add(f"{prefix}:consequence", "try_fail", cycle.id,
            "Does the attempt's consequence persist into later events?")
    for index, constraint in enumerate(request.constraints, 1):
        add(f"constraint:{index}", "constraint", str(index),
            f"Does the complete fiction satisfy this user constraint: {constraint}")
    add("language:output", "language", request.language,
        f"Is all reader-visible fiction, including headings, written in {request.language}?")
    if taxonomy_brief:
        for index, promise in enumerate(taxonomy_brief.reader_promises, 1):
            add(f"taxonomy:promise:{index}", "taxonomy", taxonomy_brief.primary_taxonomy,
                f"Does the fiction fulfill this selected reader promise: {promise}")
        for index, check in enumerate(taxonomy_brief.quality_checks, 1):
            add(f"taxonomy:quality:{index}", "taxonomy", taxonomy_brief.primary_taxonomy,
                f"Does the fiction satisfy this taxonomy quality check: {check}", False)
    add("global:causality", "global", "story",
        "Does the revision preserve accepted causal facts and event outcomes?")
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
                **expected, verdict="fail",
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
        continuity_issues=[answer.issue for answer in failed if answer.category in {
            "global_ppp", "chapter_ppp", "try_fail", "constraint", "taxonomy",
        }],
        template_like_passages=[answer.issue for answer in failed
                                if answer.question_id == "global:scaffolding"],
        revision_suggestions=audit.revision_instructions,
    )

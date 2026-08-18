"""Pure validation and audit helpers for chapter-scoped craft variants."""

from __future__ import annotations

import json
import math
import re

from .schemas import (
    Character, CharactersArtifact, CraftAuditAnswer, CraftAuditArtifact,
    CraftVariant, CraftVariantsArtifact, DiagnosticAudit, StoryOutlineArtifact,
    StoryRequest, TaxonomyBrief,
)


FORBIDDEN_STORYTELLER_REFERENCE = re.compile(
    r"\bn_\d{4}\b|\b(?:CBN|CPN|CEN)\b", re.IGNORECASE,
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


def _line_order(line, chapter_orders: dict[str, int]) -> None:
    points = [line.promise, *line.progress, line.payoff]
    unknown = [point.chapter_id for point in points if point.chapter_id not in chapter_orders]
    if unknown:
        raise ValueError(f"global craft line {line.id} references unknown chapters: {unknown}")
    orders = [chapter_orders[point.chapter_id] for point in points]
    if orders != sorted(orders):
        raise ValueError(f"global craft line {line.id} is out of order")


def validate_craft_variant(
    variant: CraftVariant,
    outline: StoryOutlineArtifact,
    characters: CharactersArtifact,
    target_words: int,
) -> None:
    validate_craft_characters(characters)
    chapter_orders = {chapter.id: chapter.order for chapter in outline.chapters}
    expected_chapters = set(chapter_orders)
    if len(chapter_orders) != len(outline.chapters):
        raise ValueError("outline chapter ids must be unique")

    serialized = json.dumps(variant.model_dump(mode="json"), ensure_ascii=False)
    if FORBIDDEN_STORYTELLER_REFERENCE.search(serialized):
        raise ValueError("craft variants cannot reference STORYTELLER nodes or node types")

    lines = [variant.master_line, *variant.subplots]
    for line in lines:
        _line_order(line, chapter_orders)
    first_order = min(chapter_orders.values())
    last_order = max(chapter_orders.values())
    if chapter_orders[variant.master_line.promise.chapter_id] != first_order:
        raise ValueError("the master promise must begin in the first chapter")
    if chapter_orders[variant.master_line.payoff.chapter_id] != last_order:
        raise ValueError("the master payoff must occur in the final chapter")

    actual_chapters = [chapter.chapter_id for chapter in variant.chapters]
    if len(actual_chapters) != len(set(actual_chapters)) or set(actual_chapters) != expected_chapters:
        raise ValueError("each craft variant requires exactly one local line per chapter")
    global_ids = {line.id for line in lines}
    for chapter in variant.chapters:
        unknown = set(chapter.advances_global_line_ids) - global_ids
        if unknown:
            raise ValueError(f"chapter {chapter.chapter_id} references unknown global lines: {unknown}")

    mains = {character.name.casefold(): character for character in main_characters(characters)}
    milestones_by_character: dict[str, list] = {name: [] for name in mains}
    for milestone in variant.character_milestones:
        key = milestone.character_name.casefold()
        if key not in mains:
            raise ValueError(f"unknown main character milestone: {milestone.character_name}")
        if milestone.chapter_id not in chapter_orders:
            raise ValueError(f"character milestone references unknown chapter: {milestone.chapter_id}")
        milestones_by_character[key].append(milestone)
    for name, milestones in milestones_by_character.items():
        if len(milestones) != 3 or {item.stage for item in milestones} != {"start", "transition", "end"}:
            raise ValueError(f"main character {mains[name].name} requires start, transition, and end milestones")
        by_stage = {item.stage: item for item in milestones}
        orders = [chapter_orders[by_stage[stage].chapter_id] for stage in ("start", "transition", "end")]
        if orders != sorted(orders):
            raise ValueError(f"milestones for {mains[name].name} are out of order")

    cycles = variant.try_fail_cycles
    expected_cycles = try_fail_target(target_words)
    if len(cycles) != expected_cycles:
        raise ValueError(f"craft variant requires exactly {expected_cycles} try-fail cycles")
    if len({cycle.id for cycle in cycles}) != len(cycles):
        raise ValueError("try-fail cycle ids must be unique")
    if any(cycle.chapter_id not in chapter_orders for cycle in cycles):
        raise ValueError("try-fail cycles may only reference outline chapters")


def validate_craft_variants(
    artifact: CraftVariantsArtifact,
    outline: StoryOutlineArtifact,
    characters: CharactersArtifact,
    target_words: int,
) -> None:
    strategies = [re.sub(r"\W+", " ", item.strategy.casefold()).strip() for item in artifact.variants]
    if len(strategies) != len(set(strategies)):
        raise ValueError("craft variants require distinct strategies")
    for variant in artifact.variants:
        validate_craft_variant(variant, outline, characters, target_words)


def audit_questions(
    request: StoryRequest,
    variant: CraftVariant,
    characters: CharactersArtifact,
    taxonomy_brief: TaxonomyBrief | None = None,
) -> list[dict[str, object]]:
    questions: list[dict[str, object]] = []

    def add(identifier: str, category: str, subject: str, question: str,
            blocking: bool = True) -> None:
        questions.append({
            "question_id": identifier,
            "category": category,
            "subject_id": subject,
            "question": question,
            "blocking": blocking,
        })

    for line in [variant.master_line, *variant.subplots]:
        prefix = f"global_ppp:{line.id}"
        add(f"{prefix}:promise", "global_ppp", line.id,
            "Does the opening establish this global narrative expectation?")
        add(f"{prefix}:progress", "global_ppp", line.id,
            "Does the story provide visible and meaningful progress toward this global payoff?")
        add(f"{prefix}:payoff", "global_ppp", line.id,
            "Does the story deliver the promised global resolution?")
        add(f"{prefix}:earned", "global_ppp", line.id,
            "Is the global payoff surprising but earned by prior progress?", False)
    for chapter in variant.chapters:
        prefix = f"chapter_ppp:{chapter.chapter_id}"
        add(f"{prefix}:promise", "chapter_ppp", chapter.chapter_id,
            "Does this chapter establish its local expectation?")
        add(f"{prefix}:progress", "chapter_ppp", chapter.chapter_id,
            "Does this chapter visibly advance its local expectation?")
        add(f"{prefix}:payoff", "chapter_ppp", chapter.chapter_id,
            "Does this chapter resolve or consequentially transform its local expectation?")
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
    for cycle in variant.try_fail_cycles:
        prefix = f"try_fail:{cycle.id}"
        add(f"{prefix}:outcome", "try_fail", cycle.id,
            "Is the planned Yes-but or No-and attempt dramatized?")
        add(f"{prefix}:consequence", "try_fail", cycle.id,
            "Does the attempt's consequence persist into later events?")
    for index, constraint in enumerate(request.constraints, 1):
        add(f"constraint:{index}", "constraint", str(index),
            f"Does the complete fiction satisfy this user constraint: {constraint}")
    if taxonomy_brief:
        for index, promise in enumerate(taxonomy_brief.reader_promises, 1):
            add(
                f"taxonomy:promise:{index}", "taxonomy", taxonomy_brief.primary_taxonomy,
                f"Does the complete fiction fulfill this selected reader promise: {promise}", True,
            )
        for index, check in enumerate(taxonomy_brief.quality_checks, 1):
            add(
                f"taxonomy:quality:{index}", "taxonomy", taxonomy_brief.primary_taxonomy,
                f"Does the fiction satisfy this taxonomy quality check: {check}", False,
            )
        if taxonomy_brief.avoid:
            add(
                "taxonomy:anti-formula", "taxonomy", taxonomy_brief.primary_taxonomy,
                "Does the fiction avoid the listed formulaic shortcuts while remaining recognizable? "
                + "; ".join(taxonomy_brief.avoid), False,
            )
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
                           if answer.category in {
                               "global_ppp", "chapter_ppp", "try_fail", "constraint", "taxonomy",
                           }],
        template_like_passages=[answer.issue for answer in failed
                                if answer.question_id == "global:scaffolding"],
        revision_suggestions=audit.revision_instructions,
    )

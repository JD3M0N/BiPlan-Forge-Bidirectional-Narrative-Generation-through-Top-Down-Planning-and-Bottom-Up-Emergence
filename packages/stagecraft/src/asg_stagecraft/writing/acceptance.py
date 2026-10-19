"""Whether one Writer candidate may replace the draft it was asked to revise.

Pure and deterministic: the rules below never call a model and never read a measurement
that reached a prompt. A rejected candidate produces a diagnostic whose retry_instruction
is reinjected into the next attempt, so those strings stay in English like the rest of the
model-facing contract; the fallback warnings are user-facing and stay in Spanish.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from asg_core import prose_paragraphs

from ..schemas import ChapterRevisionAttempt, RevisionNote, WriterCandidateDiagnostic
from .audit import word_count
from .craft_evidence import CRAFT_NOTE_PREFIX, SCENE_OBSERVATIONS, chapter_observations

if TYPE_CHECKING:
    from .chapter_edits import EditedChapter

# 7.17 (TD-3): a rewrite that keeps less than this share of the draft's paragraphs merged them.
# In 7.10 the one chapter the Writer touched went from 27 paragraphs to 13 and shipped.
MIN_PARAGRAPH_SHARE = 0.7
# A rewrite may grow by this share at most unless a note asks for something to be staged:
# in 6.2, 66 of 69 revised chapters came back longer, by a median of 82 words.
MAX_GROWTH = 1.15
# 7.18: a rewrite this close to the original, word for word, did not apply a significant note.
# 17 of the 29 Writer attempts saved by 7.17 were at least this close to their draft, and about
# eight of them shipped as revisions of a major note because only an exact copy was rejected.
NEAR_COPY_RATIO = 0.95
# The note categories that ask for a beat to be added, which can rightly lengthen a chapter.
STAGING_CATEGORIES = frozenset({"pacing", "dramatic_structure", "setup_payoff", "user_constraint"})
SIGNIFICANT = frozenset({"critical", "major"})
# How much worse than the draft each degradation leaves a candidate, to choose the best one.
DEGRADATION_WEIGHT = {"LENGTHENED_WITHOUT_CAUSE": 1, "MERGED_PARAGRAPHS": 2, "WORSE_CRAFT": 2}


def text_similarity(first: str, second: str) -> float:
    """Measure how much of two texts is the same, word for word, from 0 to 1."""
    return SequenceMatcher(None, first.split(), second.split(), autojunk=False).ratio()


def near_copy(candidate: str, original: str) -> bool:
    """Say whether a rewrite is the original or barely differs from it."""
    return text_similarity(candidate, original) >= NEAR_COPY_RATIO


def writer_candidate_issue(
    candidate: str,
    draft_body: str,
    notes: list[RevisionNote],
    *,
    names: list[str] | tuple[str, ...] = (),
) -> WriterCandidateDiagnostic | None:
    """Explain why a Writer candidate cannot replace the draft."""
    actual_words = word_count(candidate)
    if not candidate.strip():
        return WriterCandidateDiagnostic(
            code="EMPTY_CHAPTER_BODY",
            message="the chapter body is empty",
            retry_instruction="Write a complete chapter body that fulfills the planned events.",
            actual_words=actual_words,
        )
    if any(line.lstrip().startswith("#") for line in candidate.splitlines()):
        return WriterCandidateDiagnostic(
            code="MARKDOWN_HEADINGS",
            message="the chapter body contains Markdown headings",
            retry_instruction="Remove every Markdown heading while preserving the prose body.",
            actual_words=actual_words,
        )
    issues = degradations(candidate, draft_body, notes, names=names)
    return issues[0] if issues else None


def degradations(
    candidate: str,
    draft_body: str,
    notes: list[RevisionNote],
    *,
    names: list[str] | tuple[str, ...] = (),
) -> list[WriterCandidateDiagnostic]:
    """List every way a rewrite is worse than its draft in what the code can measure (7.17)."""
    if not draft_body.strip():
        return []
    actual_words = word_count(candidate)
    issues = []
    drafted = len(prose_paragraphs(draft_body))
    if len(prose_paragraphs(candidate)) < MIN_PARAGRAPH_SHARE * drafted:
        issues.append(
            WriterCandidateDiagnostic(
                code="MERGED_PARAGRAPHS",
                message="the rewrite merged the draft's paragraphs into blocks",
                retry_instruction=(
                    "Keep the paragraph breaks of the original: a new paragraph for each new "
                    "speaker or shift of attention. Change only what the notes ask for."
                ),
                actual_words=actual_words,
            )
        )
    staging = any(
        note.category in STAGING_CATEGORIES and note.priority in SIGNIFICANT for note in notes
    )
    if not staging and actual_words > MAX_GROWTH * word_count(draft_body):
        issues.append(
            WriterCandidateDiagnostic(
                code="LENGTHENED_WITHOUT_CAUSE",
                message="the rewrite grew although no note asked for anything to be staged",
                retry_instruction=(
                    "Apply the notes by replacing and cutting, not by adding: the chapter should "
                    "come back about as long as the original, or shorter."
                ),
                actual_words=actual_words,
            )
        )
    added = set(chapter_observations(candidate, names)) - set(
        chapter_observations(draft_body, names)
    )
    if added:
        issues.append(
            WriterCandidateDiagnostic(
                code="WORSE_CRAFT",
                message="the rewrite shows craft problems the draft did not have",
                retry_instruction=(
                    "Revise again without introducing: " + "; ".join(sorted(added)) + "."
                ),
                actual_words=actual_words,
            )
        )
    return issues


def writer_edit_issue(
    edited: EditedChapter,
    draft_body: str,
    notes: list[RevisionNote],
    *,
    names: list[str] | tuple[str, ...] = (),
    editor: bool = False,
) -> tuple[WriterCandidateDiagnostic | None, tuple[int, int] | None]:
    """Judge a chapter the Writer edited (7.18): its diagnostic, and its rank as a candidate.

    A critical or major note counts as applied when an accepted edit cites it. A craft note is
    judged by the text instead: it is applied when the observations it carried are gone, so a
    rewrite that does not move the observation is retried (TD-3). With the line editor on, the
    readability observations are the editor's work and only the scene ones count.

    The rank orders rejected candidates, lowest first: notes left unapplied, then how much the
    rewrite degraded. A candidate with no accepted edit is the draft and has no rank.
    """
    surviving: list[str] = []
    unapplied: list[str] = []
    for note in notes:
        if note.priority not in SIGNIFICANT:
            continue
        if note.id.startswith(CRAFT_NOTE_PREFIX):
            left = _surviving(edited.body, draft_body, names, editor)
            if left:
                unapplied.append(note.id)
                surviving.extend(item for item in left if item not in surviving)
        elif note.id not in edited.applied_note_ids:
            unapplied.append(note.id)
    issues = degradations(edited.body, draft_body, notes, names=names)
    weight = sum(DEGRADATION_WEIGHT[issue.code] for issue in issues)
    rank = (len(unapplied), weight) if edited.accepted else None
    if unapplied:
        return _unapplied(edited, unapplied, surviving), rank
    return writer_candidate_issue(edited.body, draft_body, notes, names=names), rank


def _surviving(
    candidate: str, draft_body: str, names: list[str] | tuple[str, ...], editor: bool
) -> list[str]:
    """Return the draft's craft observations the candidate still shows."""
    drafted = chapter_observations(draft_body, names)
    if editor:
        drafted = [item for item in drafted if item in SCENE_OBSERVATIONS]
    remaining = set(chapter_observations(candidate, names))
    return [item for item in drafted if item in remaining]


def _unapplied(
    edited: EditedChapter, unapplied: list[str], surviving: list[str]
) -> WriterCandidateDiagnostic:
    """Name the notes no accepted edit answered, what the text still shows and what was refused."""
    instruction = (
        "Return at least one visible edit for each of these notes, citing its id: "
        + ", ".join(unapplied)
        + "."
    )
    if surviving:
        instruction += " The chapter still shows: " + "; ".join(surviving) + "."
    if edited.rejected:
        refused = "; ".join(f"{item['paragraph']} ({item['reason']})" for item in edited.rejected)
        instruction += f" These edits were turned down: {refused}."
    return WriterCandidateDiagnostic(
        code="NOTE_NOT_APPLIED",
        message="no accepted edit answers every critical or major note",
        retry_instruction=instruction,
        actual_words=word_count(edited.body),
        note_ids=unapplied,
    )


def writer_fallback_warning(
    chapter_index: int,
    draft_words: int,
    attempts: list[ChapterRevisionAttempt],
) -> str:
    """Build a concise Spanish warning from the structured rejection trail."""
    return (
        "[WRITER_REVISION_REJECTED] Capítulo "
        f"{chapter_index}: no hubo una revisión válida tras {len(attempts)} intentos "
        f"({_codes(attempts)}). Se entregó el borrador de {draft_words} palabras."
    )


def writer_best_candidate_warning(
    chapter_index: int, attempt: int, attempts: list[ChapterRevisionAttempt]
) -> str:
    """Build the Spanish warning for a chapter that shipped its best rejected attempt (7.18)."""
    return (
        "[WRITER_BEST_CANDIDATE] Capítulo "
        f"{chapter_index}: ninguna revisión pasó todas las comprobaciones ({_codes(attempts)}); "
        f"se entregó el intento {attempt}, el que más mejora el borrador."
    )


def _codes(attempts: list[ChapterRevisionAttempt]) -> str:
    """List the rejection codes of a revision trail."""
    reasons = [
        item.diagnostic.code if item.diagnostic is not None else item.exception_type
        for item in attempts
        if item.diagnostic is not None or item.exception_type is not None
    ]
    return ", ".join(reason for reason in reasons if reason) or "WRITER_EXCEPTION"

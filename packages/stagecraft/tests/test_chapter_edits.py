"""The Writer's paragraph edits and the shared revision loop (7.18, TD-3)."""

import pytest
from asg_stagecraft.schemas import RevisionNote, WriterCandidateDiagnostic
from asg_stagecraft.writing.chapter_edits import ParagraphEdit, ParagraphEdits, apply_chapter_edits
from asg_stagecraft.writing.revision_loop import Judgement, revise_with_retries

DRAFT = "Primero.\n\nSegundo párrafo."
NOTES = [
    RevisionNote(id="ritmo", priority="major", category="pacing", evidence="e", instruction="i"),
    RevisionNote(id="voz", priority="major", category="voice_style", evidence="e", instruction="i"),
]


def edit(paragraph: str, text: str, note: str = "voz", action: str = "replace") -> ParagraphEdit:
    """One edit to the test draft."""
    return ParagraphEdit(note_ids=[note], paragraph=paragraph, action=action, text=text)


@pytest.mark.parametrize(
    ("change", "reason", "body"),
    [
        (edit("P9", "Otro."), "unknown paragraph", DRAFT),
        (edit("P1", "Otro.", note="nada"), "unknown note id (nada)", DRAFT),
        (edit("P1", "Primero."), "unchanged text", DRAFT),
        (
            edit("P1", "Nuevo.", action="insert_after"),
            "insert_after is only for notes that ask for a beat to be staged",
            DRAFT,
        ),
        (edit("P1", "Uno.\n\nDos."), "", "Uno.\n\nDos.\n\nSegundo párrafo."),
        (
            edit("P1", "Nuevo.", note="ritmo", action="insert_after"),
            "",
            "Primero.\n\nNuevo.\n\nSegundo párrafo.",
        ),
        # 7.20: an insertion that says again what the next paragraph says is turned down.
        (
            edit("P1", "Nuevo.\n\nSegundo párrafo.", note="ritmo", action="insert_after"),
            "insert_after repeats a sentence of the paragraphs around it",
            DRAFT,
        ),
    ],
    ids=[
        "unknown-paragraph",
        "unknown-note",
        "unchanged",
        "insert-without-staging",
        "split",
        "insert",
        "insert-repeating",
    ],
)
def test_an_edit_lands_only_where_the_draft_and_the_notes_allow(change, reason, body) -> None:
    edited = apply_chapter_edits(DRAFT, NOTES, ParagraphEdits(edits=[change]))
    assert [item["reason"] for item in edited.rejected] == ([reason] if reason else [])
    assert edited.applied_note_ids == (set() if reason else set(change.note_ids))
    assert edited.body == body


FAILED = RuntimeError("model unavailable")


@pytest.mark.parametrize(
    ("responses", "statuses", "accepted", "best", "best_attempt"),
    [
        (["ok"], ["accepted"], "ok", None, None),
        ([FAILED, "ok"], ["failed", "accepted"], "ok", None, None),
        # Both rejected: the lower rank ships, and a copy never does.
        (["rank-1", "rank-2"], ["rejected", "rejected"], None, "rank-1", 1),
        (["copy", "copy"], ["rejected", "rejected"], None, None, None),
    ],
    ids=["accepted", "failed-then-accepted", "best-candidate", "copies-ship-the-draft"],
)
def test_the_revision_loop_retries_with_the_correction_and_keeps_the_best(
    responses, statuses, accepted, best, best_attempt
) -> None:
    feedback: list[str] = []
    recorded = []

    def call(attempt: int, correction: str) -> str:
        feedback.append(correction)
        response = responses[attempt - 1]
        if isinstance(response, Exception):
            raise response
        return response

    def judge(attempt: int, response: str) -> Judgement[str]:
        if response == "ok":
            return Judgement(response, None)
        diagnostic = WriterCandidateDiagnostic(
            code="NOTE_NOT_APPLIED",
            message="it missed",
            retry_instruction="Fix it.",
            actual_words=0,
        )
        rank = None if response == "copy" else (int(response.split("-")[1]),)
        return Judgement(response, diagnostic, rank=rank)

    outcome = revise_with_retries(2, call, judge, recorded.append, "Return the edits.")
    assert [item.status for item in outcome.attempts] == statuses
    assert [item.status for item in recorded] == statuses
    assert (outcome.accepted, outcome.best, outcome.best_attempt) == (accepted, best, best_attempt)
    assert feedback[0] == ""
    if len(feedback) > 1:
        expected = "(RuntimeError)" if statuses[0] == "failed" else "it missed. Fix it."
        assert feedback[1].startswith("\n\nRETRY CORRECTION:")
        assert expected in feedback[1]
        assert feedback[1].endswith("Return the edits.")

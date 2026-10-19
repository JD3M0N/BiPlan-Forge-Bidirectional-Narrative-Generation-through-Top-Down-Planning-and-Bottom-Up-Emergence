"""The Writer's paragraph edits: what it may change in a drafted chapter, applied by code (7.18).

Until 7.17 the Writer rewrote the whole chapter and gave the draft back almost untouched: 17 of
the 29 attempts saved in the corpus were at least 95 percent the draft, and the one run whose
chapter came back byte for byte twice shipped the draft. Now the Writer reads the chapter as
numbered paragraphs and returns only what it changes, each edit citing the notes it answers.
A copy cannot pass for a revision: an empty list says nothing changed, and every note left
without an accepted edit is named back in the retry.

The reasons below are reinjected into the Writer's retry, so they stay in English.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..schemas import RevisionNote
from .acceptance import STAGING_CATEGORIES, text_similarity
from .line_edit import chapter_blocks, paragraph_index


class ParagraphEdit(BaseModel):
    """One change to one paragraph of the draft, and the notes it answers."""

    model_config = ConfigDict(extra="forbid")
    note_ids: list[str] = Field(
        min_length=1, description="The ids of the revision notes this edit answers, as given."
    )
    paragraph: str = Field(description="The id of the paragraph this edit touches (P1...).")
    action: Literal["replace", "insert_after"] = Field(
        description=(
            "replace rewrites the paragraph; insert_after adds new paragraphs right after it, "
            "only to stage a beat a note asks for."
        )
    )
    text: str = Field(
        min_length=1,
        description=(
            "The new prose in the fiction's language, with its accents and dialogue dashes. "
            "Separate paragraphs with a blank line."
        ),
    )


class ParagraphEdits(BaseModel):
    """Every change the Writer makes to one chapter; a paragraph left out stays as drafted."""

    model_config = ConfigDict(extra="forbid")
    edits: list[ParagraphEdit] = Field(default_factory=list)


@dataclass
class EditedChapter:
    """One chapter after the Writer's edits: its body and what was accepted or turned down."""

    body: str
    accepted: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    applied_note_ids: set[str] = field(default_factory=set)

    def as_record(self) -> dict:
        """The edits as stored next to the attempt, in writer/chapter-NNN-attempt-NNN-edits.json."""
        return {
            "accepted": self.accepted,
            "rejected": self.rejected,
            "applied_note_ids": sorted(self.applied_note_ids),
        }


def edit_request(body: str) -> list[dict]:
    """Number the paragraphs of a drafted chapter the way the Writer cites them."""
    return [
        {"id": f"P{index + 1}", "text": block} for index, block in enumerate(chapter_blocks(body))
    ]


def check_paragraph_edit(
    edit: ParagraphEdit,
    blocks: list[str],
    notes: dict[str, RevisionNote],
    replaced: set[int],
) -> str:
    """Say why one edit may not be applied, or return an empty string when it may."""
    index = paragraph_index(edit.paragraph, len(blocks))
    if index is None:
        return "unknown paragraph"
    unknown = [note_id for note_id in edit.note_ids if note_id not in notes]
    if unknown:
        return f"unknown note id ({', '.join(unknown)})"
    text = edit.text.strip()
    if not text or any(line.lstrip().startswith("#") for line in text.splitlines()):
        return "empty or a heading"
    if edit.action == "replace":
        if " ".join(text.split()) == " ".join(blocks[index].split()):
            return "unchanged text"
        if index in replaced:
            return "the paragraph is already replaced"
    elif not any(notes[note_id].category in STAGING_CATEGORIES for note_id in edit.note_ids):
        return "insert_after is only for notes that ask for a beat to be staged"
    return ""


def apply_chapter_edits(
    body: str, notes: list[RevisionNote], edits: ParagraphEdits
) -> EditedChapter:
    """Apply every edit that passes its checks, in paragraph order, and keep the rest out."""
    blocks = chapter_blocks(body)
    by_id = {note.id: note for note in notes}
    replacements: dict[int, str] = {}
    insertions: dict[int, list[str]] = {}
    result = EditedChapter(body=body)
    for edit in edits.edits:
        record = edit.model_dump(mode="json")
        reason = check_paragraph_edit(edit, blocks, by_id, set(replacements))
        if reason:
            result.rejected.append({**record, "reason": reason})
            continue
        index = paragraph_index(edit.paragraph, len(blocks))
        assert index is not None
        text = "\n\n".join(chapter_blocks(edit.text))
        if edit.action == "replace":
            replacements[index] = text
            record["similarity"] = round(text_similarity(blocks[index], text), 4)
        else:
            insertions.setdefault(index, []).append(text)
        result.accepted.append(record)
        result.applied_note_ids.update(edit.note_ids)
    if not result.accepted:
        return result
    result.body = "\n\n".join(
        part
        for index, block in enumerate(blocks)
        for part in (replacements.get(index, block), *insertions.get(index, []))
    )
    return result

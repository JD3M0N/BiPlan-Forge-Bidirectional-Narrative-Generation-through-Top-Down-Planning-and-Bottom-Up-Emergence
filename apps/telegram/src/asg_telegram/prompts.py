"""Telegram-safe composition of story text into HTML message chunks."""

from __future__ import annotations

import html
import re

HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")


def _take_safe_prefix(text: str, limit: int) -> tuple[str, str]:
    """Take a text prefix without splitting escaped HTML entities."""
    used = 0
    last_space = -1
    for index, character in enumerate(text):
        escaped_length = len(html.escape(character))
        if used + escaped_length > limit:
            boundary = last_space if last_space > 0 else index
            if boundary == 0:
                boundary = 1
            return text[:boundary], text[boundary:].lstrip()
        used += escaped_length
        if character.isspace():
            last_space = index
    return text, ""


def _render_block(text: str, bold: bool, limit: int) -> list[str]:
    """Render block."""
    wrapper = 7 if bold else 0
    available = limit - wrapper
    if available < 1:
        raise ValueError("limit es demasiado pequeño para el formato")
    rendered: list[str] = []
    remaining = text
    while remaining:
        piece, remaining = _take_safe_prefix(remaining, available)
        escaped = html.escape(piece)
        rendered.append(f"<b>{escaped}</b>" if bold else escaped)
    return rendered or ["<b></b>" if bold else ""]


def telegram_story_chunks(markdown: str, limit: int = 3900) -> list[str]:
    """Convert Markdown headings into safe HTML message chunks."""
    if limit < 8:
        raise ValueError("limit debe ser al menos 8")
    blocks: list[tuple[str, bool]] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        """Flush paragraph."""
        if paragraph:
            blocks.append(("\n".join(paragraph), False))
            paragraph.clear()

    for line in markdown.splitlines():
        heading = HEADING.match(line)
        if heading:
            flush_paragraph()
            blocks.append((heading.group(1), True))
        elif not line.strip():
            flush_paragraph()
        else:
            paragraph.append(line)
    flush_paragraph()

    messages: list[str] = []
    current = ""
    for raw, bold in blocks:
        for rendered in _render_block(raw, bold, limit):
            candidate = f"{current}\n\n{rendered}" if current else rendered
            if len(candidate) <= limit:
                current = candidate
            else:
                if current:
                    messages.append(current)
                current = rendered
    if current or not messages:
        messages.append(current)
    return messages

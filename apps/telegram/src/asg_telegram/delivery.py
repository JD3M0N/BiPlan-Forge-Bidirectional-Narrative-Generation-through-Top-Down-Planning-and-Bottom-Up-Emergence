"""Send a story to a chat: the Markdown file, its narration and the text in chunks."""

from __future__ import annotations

import asyncio
import html
import logging
import re
from pathlib import Path

from telegram import InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, TelegramError

LOGGER = logging.getLogger(__name__)
RETRY_DELAYS = (1, 2, 4)
CHUNK_LIMIT = 3900
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")


async def send_retrying(send, what: str) -> bool:
    """Run one Telegram call, retrying only temporary network errors.

    BadRequest subclasses NetworkError and is permanent, so it is caught first.
    """
    for delay in (*RETRY_DELAYS, None):
        try:
            await send()
            return True
        except BadRequest:
            break
        except NetworkError:
            if delay is None:
                break
            await asyncio.sleep(delay)
        except TelegramError:
            break
    LOGGER.warning("No se pudo enviar %s", what, exc_info=True)
    return False


def story_chunks(markdown: str, limit: int = CHUNK_LIMIT) -> list[str]:
    """Split Markdown into HTML messages, headings in bold, never cutting an entity."""
    messages: list[str] = []
    current = ""
    for block in re.split(r"\n\s*\n", markdown.strip()):
        heading = HEADING.match(block.strip())
        text = heading.group(1) if heading else block.strip()
        while text:
            end = len(text)
            # Escape after cutting, so an entity is never split; 7 leaves room for <b></b>.
            while len(html.escape(text[:end])) > limit - 7:
                space = text.rfind(" ", 0, end)
                end = space if space > 0 else max(1, end * 3 // 4)
            piece, text = text[:end], text[end:].lstrip()
            rendered = f"<b>{html.escape(piece)}</b>" if heading else html.escape(piece)
            candidate = f"{current}\n\n{rendered}" if current else rendered
            if len(candidate) <= limit:
                current = candidate
            else:
                messages.append(current)
                current = rendered
    if current or not messages:
        messages.append(current)
    return messages


async def send_story(
    bot,
    chat_id: int,
    run_dir: Path,
    *,
    name: str = "historia",
    heading: str = "",
    keyboard: InlineKeyboardMarkup | None = None,
) -> bool:
    """Send story.md, story.mp3 when present, and the text; the keyboard goes last.

    The text matters most, so a missing or failed narration never blocks it.
    """
    story = Path(run_dir) / "story.md"
    text = story.read_text(encoding="utf-8")
    sent = await send_retrying(
        lambda: bot.send_document(
            chat_id=chat_id,
            document=InputFile(text.encode("utf-8"), filename=f"{name}.md"),
            caption=heading or None,
        ),
        f"el archivo de {name}",
    )
    audio = story.with_name("story.mp3")
    if audio.is_file():
        await send_retrying(
            lambda: bot.send_audio(
                chat_id=chat_id,
                audio=InputFile(audio.read_bytes(), filename=f"{name}.mp3"),
                title=name,
            ),
            f"el audio de {name}",
        )
    chunks = story_chunks(text)
    for index, chunk in enumerate(chunks):
        last = index == len(chunks) - 1
        sent &= await send_retrying(
            lambda chunk=chunk, last=last: bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard if last else None,
            ),
            f"el texto de {name}",
        )
    return sent

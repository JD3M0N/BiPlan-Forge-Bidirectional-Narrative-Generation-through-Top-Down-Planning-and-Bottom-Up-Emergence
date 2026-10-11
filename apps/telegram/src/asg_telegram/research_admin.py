"""Private researcher commands and optional participant publication consent."""

from __future__ import annotations

import asyncio
import io

from asg_evaluation.transfer import export_bundle, split_bundle
from telegram import InlineKeyboardButton as Button
from telegram import InlineKeyboardMarkup as Keyboard

PUBLICATION_TEXT = (
    "Publicar tu historia es opcional y no afecta a tu participación. "
    "Si aceptas, el investigador podrá revisar y publicar el texto en un repositorio público "
    "de GitHub durante el estudio, sin tu identificador ni tus respuestas. Cualquier persona "
    "podrá leerlo y descargarlo. Evita incluir datos personales. Las copias públicas y el "
    "historial de Git pueden conservarse aunque después cambies de opinión. "
    "Puedes cambiar esta preferencia con /publicacion."
)


class ResearchAdmin:
    """Authorize each administrative operation by numeric Telegram identity and private chat."""

    def __init__(self, repository, admin_ids: frozenset[int]) -> None:
        """Attach research storage and an explicit administrator allowlist."""
        self.repository = repository
        self.admin_ids = admin_ids

    def authorized(self, update) -> bool:
        """Reject group chats and every identity outside the configured allowlist."""
        return (
            update.effective_chat.type == "private" and update.effective_user.id in self.admin_ids
        )

    async def consent(self, update, context) -> None:
        """Offer optional publication permission to an enrolled participant."""
        reader = self.repository.find_participant(str(update.effective_user.id))
        if update.effective_chat.type != "private" or not reader:
            return
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=PUBLICATION_TEXT,
            reply_markup=Keyboard(
                [
                    [Button("Sí, autorizo publicar", callback_data="publish:yes")],
                    [Button("No publicar", callback_data="publish:no")],
                ]
            ),
        )

    async def consent_answer(self, update, context) -> None:
        """Record publication permission without changing enrollment or generation."""
        reader = self.repository.find_participant(str(update.effective_user.id))
        value = update.callback_query.data
        if (
            update.effective_chat.type != "private"
            or not reader
            or value not in {"publish:yes", "publish:no"}
        ):
            await update.callback_query.answer("No disponible.")
            return
        self.repository.publication_consent(reader["id"], value == "publish:yes")
        await update.callback_query.answer("Preferencia de publicación guardada.")
        await update.callback_query.edit_message_reply_markup(reply_markup=None)

    async def pending(self, update, context) -> None:
        """Deliver a bounded list of pending identifiers to the researcher."""
        if not self.authorized(update):
            await update.effective_message.reply_text(
                "Comando reservado al administrador en privado."
            )
            return
        stories = self.repository.publication_candidates()
        text = "\n".join(s["id"] for s in stories[:50]) or "No hay textos pendientes autorizados."
        await update.effective_message.reply_text(text + "\nRevisar: /revisar_historia ID")

    async def review(self, update, context) -> None:
        """Send the exact authorized text and a hash-bound approval command."""
        if not self.authorized(update):
            return
        sid = context.args[0] if context.args else ""
        story = next((s for s in self.repository.publication_candidates() if s["id"] == sid), None)
        if not story:
            await update.effective_message.reply_text("Historia no disponible para publicación.")
            return
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=io.BytesIO(story["text"].encode("utf-8")),
            filename=f"{sid}.md",
        )
        await update.effective_message.reply_text(
            "Revisa que el texto puede publicarse sin datos personales. Para aprobarlo:\n"
            f"/aprobar_historia {sid} {story['text_hash']}"
        )

    async def approve(self, update, context) -> None:
        """Enqueue only a text explicitly approved by an authorized investigator."""
        if not self.authorized(update):
            return
        try:
            if len(context.args) != 2:
                raise ValueError("Usa /revisar_historia ID antes de aprobar.")
            self.repository.approve_publication(*context.args)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        await update.effective_message.reply_text(
            "Texto aprobado; queda en la cola de publicación."
        )

    async def export(self, update, context) -> None:
        """Send the pseudonymous research ZIP, splitting it below Telegram's document limit."""
        if not self.authorized(update):
            await update.effective_message.reply_text(
                "Comando reservado al administrador en privado."
            )
            return
        payload = await asyncio.to_thread(export_bundle, self.repository)
        parts = split_bundle(payload)
        for name, content in parts:
            await context.bot.send_document(
                chat_id=update.effective_chat.id, document=io.BytesIO(content), filename=name
            )
        await update.effective_message.reply_text(
            "Descarga todos los archivos en una carpeta e importa el ZIP (o part0001) "
            "con evaluation-study import-bundle."
        )

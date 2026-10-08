"""Telegram conversation and evaluation handlers."""

from __future__ import annotations

import logging
from types import SimpleNamespace

from asg_evaluation.study import PROSE_FORMATS
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .console import log_user_action
from .contract import OptionSpec, OptionValue, StoryGeneratorAdapter
from .generation import GenerationCoordinator
from .guide import OUTSIDE_SAMPLE
from .panel import (
    choice_keyboard,
    describe_options,
    group_keyboard,
    integer_keyboard,
    panel_keyboard,
    panel_text,
    parse_callback,
    text_keyboard,
    text_prompt,
)
from .queue import QueueRepository
from .states import ConversationState
from .wizard import (
    BRIEF_STEPS,
    SKIPPABLE_STEPS,
    cast_keyboard,
    check_length,
    confirm_keyboard,
    outline_from,
    outline_summary,
    pronoun_keyboard,
    question,
    role_keyboard,
    skip_keyboard,
)

LOGGER = logging.getLogger(__name__)
EXAMPLE_PROMPT = (
    "Escribe un relato de ciencia ficción de unas 1800 palabras sobre una "
    "cartógrafa que descubre un mensaje en las estrellas. Tono melancólico "
    "y final esperanzador."
)


def _user_log(update: Update, action: str, category: str = "acción") -> None:
    """Log an action with the best available Telegram user identity."""
    user = update.effective_user
    if user is None:
        log_user_action(LOGGER, user_id=None, username=None, action=action, category=category)
        return
    readable = user.username or user.full_name or "sin nombre"
    log_user_action(LOGGER, user_id=user.id, username=readable, action=action, category=category)


def _mode_keyboard() -> InlineKeyboardMarkup:
    """Build the free-form, guided and options selection keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Prompt libre", callback_data="mode:free"),
                InlineKeyboardButton("Obra guiada", callback_data="mode:guided"),
            ],
            [InlineKeyboardButton("⚙️ Opciones", callback_data="mode:options")],
        ]
    )


def _format_keyboard(
    spec: OptionSpec, values: dict, *, prose_only: bool = False
) -> InlineKeyboardMarkup:
    """Build the output-format keyboard, marking the remembered choice.

    A base story only offers the prose formats the study admits.
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    ("✓ " if choice.value == values.get("format") else "") + choice.label,
                    callback_data=f"format:{choice.value}",
                )
            ]
            for choice in spec.choices
            if not prose_only or choice.value in PROSE_FORMATS
        ]
    )


class TelegramStoryBot(GenerationCoordinator):
    """Handle Telegram conversations around generation and evaluation."""

    def __init__(
        self, generator: StoryGeneratorAdapter, queue: QueueRepository | None = None
    ) -> None:
        """Configure conversation handlers with their generation coordinator."""
        super().__init__(generator, queue)

    def _spec(self, key: str) -> OptionSpec | None:
        """Look up one option's spec by key, or None if it no longer exists."""
        return next((spec for spec in self.generator.option_specs if spec.key == key), None)

    # --- basic commands ----------------------------------------------------

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Tell the user where they stand in the study and what comes next."""
        _user_log(update, "ejecutó /start")
        if self.guide:
            context.user_data.clear()
            await self.guide.show(update, context)
            return
        await update.effective_message.reply_text(
            "¡Hola! Puedo crear historias con el enfoque "
            f"{self.generator.display_name} y luego recoger tu evaluación.\n\n"
            "Usa /newstory para comenzar, /settings para configurar las opciones "
            "o /help para ver los comandos."
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display the supported bot commands."""
        _user_log(update, "ejecutó /help")
        if self.guide:
            await self.guide.help(update, context)
            return
        await update.effective_message.reply_text(
            "/newstory — crear una historia\n"
            "/settings — configurar formato, visión, memoria, audio y más\n"
            "/cancel — abandonar la solicitud o evaluación actual\n"
            "/help — mostrar esta ayuda"
        )

    async def on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log a handler failure that python-telegram-bot could not route."""
        LOGGER.error("Excepción no manejada en un handler de Telegram", exc_info=context.error)

    # --- /newstory: format, then mode ---------------------------------------

    async def new_story(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start prompt collection unless the user already has active work."""
        user_id = update.effective_user.id
        _user_log(update, "ejecutó /newstory")
        if user_id in self.active_users:
            _user_log(update, "intentó iniciar otra generación mientras tenía una activa")
            await update.effective_message.reply_text(
                "Ya estoy generando una historia para ti. Espera a que termine."
            )
            return
        contributing = False
        if self.guide:
            status = self.guide.status(user_id)
            if not status.can_generate:
                await self.guide.show(update, context)
                return
            contributing = status.contributing
            if contributing and not status.pending:
                self.study.repository.request_contribution(status.participant)
        context.user_data.clear()
        context.user_data["contributing"] = contributing
        options, was_reset = self.effective_options(user_id)
        if was_reset:
            await update.effective_message.reply_text(
                "Tus opciones guardadas ya no eran válidas y las restablecí a las de por defecto."
            )
        context.user_data["state"] = ConversationState.CHOOSE_FORMAT
        await update.effective_message.reply_text(
            "¿En qué formato quieres tu historia base?"
            if contributing
            else "¿Qué quieres generar?",
            reply_markup=_format_keyboard(self._spec("format"), options, prose_only=contributing),
        )

    async def choose_format(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Store the chosen output format and move to the prompt-mode selection."""
        query = update.callback_query
        await query.answer()
        if context.user_data.get("state") != ConversationState.CHOOSE_FORMAT:
            await query.edit_message_text("Esta selección ya no está activa.")
            return
        value = query.data.split(":", 1)[1]
        spec = self._spec("format")
        if value not in {choice.value for choice in spec.choices}:
            await query.edit_message_text("Formato desconocido.")
            return
        if context.user_data.get("contributing") and value not in PROSE_FORMATS:
            await query.edit_message_text(
                "La historia base debe estar en prosa. Usa /newstory para elegir otro formato."
            )
            return
        _user_log(update, f"seleccionó el formato {value}")
        try:
            options = self.change_option(update.effective_user.id, "format", value)
        except ValueError:
            options, _ = self.effective_options(update.effective_user.id)
        context.user_data["state"] = ConversationState.CHOOSE_MODE
        await query.edit_message_text(
            self._summary_text(options),
            parse_mode=ParseMode.HTML,
            reply_markup=_mode_keyboard(),
        )

    def _summary_text(self, options: dict[str, OptionValue]) -> str:
        """Describe the chosen format and its options before asking how to write it."""
        choice = self._spec("format").choice_for(options.get("format"))
        lines = [f"<b>{choice.label}</b>", choice.description]
        details = describe_options(self.generator.option_specs, options)
        if details:
            lines.append(details)
        if choice.note:
            lines.append(choice.note)
        lines.append("¿Cómo quieres describir la historia?")
        return "\n\n".join(line for line in lines if line)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Cancel a waiting job or clear an inactive conversation state."""
        user_id = update.effective_user.id
        _user_log(update, "ejecutó /cancel")
        outcome = self.queue.cancel_user(user_id) if self.queue else None
        if outcome == "cancelled":
            self.active_users.discard(user_id)
            context.user_data.clear()
            await update.effective_message.reply_text(
                "Tu solicitud fue retirada de la cola. Puedes usar /newstory cuando quieras."
            )
            await self._refresh_queue(context.application)
            return
        if outcome == "requested":
            await update.effective_message.reply_text(
                "Pedí detener la generación. Se detendrá antes de la siguiente etapa."
            )
            return
        if user_id in self.active_users:
            await update.effective_message.reply_text(
                "La generación o entrega ya está en curso y no puede cancelarse. "
                "Te avisaré cuando termine."
            )
            return
        had_state = bool(context.user_data.get("state"))
        context.user_data.clear()
        await update.effective_message.reply_text(
            "Proceso cancelado. Puedes usar /newstory cuando quieras."
            if had_state
            else "No hay ningún proceso activo."
        )

    async def choose_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Activate free-form, guided, or in-place options editing."""
        query = update.callback_query
        await query.answer()
        if context.user_data.get("state") != ConversationState.CHOOSE_MODE:
            await query.edit_message_text("Esta selección ya no está activa.")
            return
        mode = query.data.split(":", 1)[1]
        _user_log(update, f"seleccionó el modo {mode}")
        if mode == "free":
            context.user_data["state"] = ConversationState.FREE_PROMPT
            await query.edit_message_text(
                f"Envía una descripción completa.\n\nEjemplo:\n{EXAMPLE_PROMPT}"
            )
            return
        if mode == "options":
            context.user_data["panel_return"] = "summary"
            await self._render_panel(update.effective_user.id, query.edit_message_text)
            return
        context.user_data.update(
            state=ConversationState.GUIDED, brief_step="title", brief_values={}
        )
        spec = self.generator.brief_spec
        await query.edit_message_text(question("title", spec), reply_markup=skip_keyboard("title"))

    # --- text routing --------------------------------------------------------

    async def text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Route text according to the user's current conversation state."""
        text = update.effective_message.text
        awaiting = context.user_data.get("awaiting_option")
        if awaiting:
            await self._handle_option_text(update, context, awaiting, text)
            return
        state = context.user_data.get("state")
        if state == ConversationState.FREE_PROMPT:
            _user_log(update, "envió un prompt libre")
            if not text.strip():
                await update.effective_message.reply_text("La descripción no puede estar vacía.")
                return
            await self._launch_generation(update, context, text.strip())
        elif state == ConversationState.GUIDED:
            await self._guided_input(update, context, text)
        elif self.guide and state is None:
            await self.guide.show(update, context)
        else:
            await update.effective_message.reply_text("Usa /newstory para crear una historia.")

    # --- options panel ---------------------------------------------------

    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Open the options panel as a fresh message."""
        _user_log(update, "ejecutó /settings")
        if self.guide and not self.guide.status(update.effective_user.id).can_generate:
            await self.guide.show(update, context)
            return
        context.user_data["panel_return"] = "menu"
        options, was_reset = self.effective_options(update.effective_user.id)
        if was_reset:
            await update.effective_message.reply_text(
                "Tus opciones guardadas ya no eran válidas y las restablecí a las de por defecto."
            )
        specs = self.generator.option_specs
        await update.effective_message.reply_text(
            panel_text(specs, options),
            parse_mode=ParseMode.HTML,
            reply_markup=panel_keyboard(specs, options),
        )

    async def _render_panel(self, user_id: int, respond) -> None:
        """Render the top-level options panel through a bound edit or send callable."""
        options, _ = self.effective_options(user_id)
        specs = self.generator.option_specs
        await respond(
            panel_text(specs, options),
            parse_mode=ParseMode.HTML,
            reply_markup=panel_keyboard(specs, options),
        )

    async def option_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Dispatch one ``opt:...`` callback to its handling method."""
        query = update.callback_query
        action, key, extra = parse_callback(query.data)
        handler = {
            "home": self._opt_home,
            "tog": self._opt_toggle,
            "open": self._opt_open,
            "set": self._opt_set,
            "grp": self._opt_group,
            "int": self._opt_integer,
            "clr": self._opt_clear,
            "reset": self._opt_reset,
            "done": self._opt_done,
        }.get(action)
        if handler is None:
            await query.answer()
            return
        await handler(query, context, key, extra)

    async def _opt_home(self, query, context, key, extra) -> None:
        """Return the panel to its top level."""
        await query.answer()
        await self._render_panel(query.from_user.id, query.edit_message_text)

    async def _opt_toggle(self, query, context, key, extra) -> None:
        """Flip a boolean option in place."""
        options, _ = self.effective_options(query.from_user.id)
        try:
            self.change_option(query.from_user.id, key, not options.get(key))
        except ValueError as exc:
            await query.answer(str(exc), show_alert=True)
            return
        await query.answer()
        await self._render_panel(query.from_user.id, query.edit_message_text)

    async def _opt_open(self, query, context, key, extra) -> None:
        """Open one option's submenu, by its kind."""
        await query.answer()
        spec = self._spec(key)
        if spec is None:
            await self._render_panel(query.from_user.id, query.edit_message_text)
            return
        if spec.kind == "text":
            context.user_data["awaiting_option"] = key
            await query.edit_message_text(text_prompt(spec), reply_markup=text_keyboard(spec))
            return
        options, _ = self.effective_options(query.from_user.id)
        if spec.kind == "integer":
            await query.edit_message_text(
                spec.label, reply_markup=integer_keyboard(spec, options.get(key))
            )
            return
        await query.edit_message_text(spec.label, reply_markup=choice_keyboard(spec, options))

    async def _opt_set(self, query, context, key, extra) -> None:
        """Pick one choice option's value by its offered index."""
        spec = self._spec(key)
        if spec is None or int(extra) >= len(spec.choices):
            await query.answer("Esa opción ya no existe.", show_alert=True)
            return
        if (
            key == "format"
            and context.user_data.get("contributing")
            and spec.choices[int(extra)].value not in PROSE_FORMATS
        ):
            await query.answer("La historia base debe estar en prosa.", show_alert=True)
            return
        try:
            self.change_option(query.from_user.id, key, spec.choices[int(extra)].value)
        except ValueError as exc:
            await query.answer(str(exc), show_alert=True)
            return
        await query.answer()
        await self._render_panel(query.from_user.id, query.edit_message_text)

    async def _opt_group(self, query, context, key, extra) -> None:
        """Open one grouped choice option's submenu, such as one country's voices."""
        await query.answer()
        spec = self._spec(key)
        options, _ = self.effective_options(query.from_user.id)
        await query.edit_message_text(
            spec.label, reply_markup=group_keyboard(spec, options, int(extra))
        )

    async def _opt_integer(self, query, context, key, extra) -> None:
        """Set one integer option to a value chosen from its picker."""
        try:
            self.change_option(query.from_user.id, key, int(extra))
        except ValueError as exc:
            await query.answer(str(exc), show_alert=True)
            return
        await query.answer()
        await self._render_panel(query.from_user.id, query.edit_message_text)

    async def _opt_clear(self, query, context, key, extra) -> None:
        """Clear one free-text option back to its default."""
        try:
            self.change_option(query.from_user.id, key, "")
        except ValueError as exc:
            await query.answer(str(exc), show_alert=True)
            return
        await query.answer()
        context.user_data.pop("awaiting_option", None)
        await self._render_panel(query.from_user.id, query.edit_message_text)

    async def _opt_reset(self, query, context, key, extra) -> None:
        """Forget every stored preference and return the panel to the defaults."""
        await query.answer()
        self.reset_options(query.from_user.id)
        await self._render_panel(query.from_user.id, query.edit_message_text)

    async def _opt_done(self, query, context, key, extra) -> None:
        """Close the panel, returning to wherever it was opened from."""
        await query.answer()
        options, _ = self.effective_options(query.from_user.id)
        destination = context.user_data.pop("panel_return", "menu")
        if destination == "summary":
            context.user_data["state"] = ConversationState.CHOOSE_MODE
            await query.edit_message_text(
                self._summary_text(options),
                parse_mode=ParseMode.HTML,
                reply_markup=_mode_keyboard(),
            )
            return
        if destination == "confirm":
            outline = outline_from(context.user_data.get("brief_values", {}))
            await query.edit_message_text(
                outline_summary(outline), parse_mode=ParseMode.HTML, reply_markup=confirm_keyboard()
            )
            return
        await query.edit_message_text("Opciones guardadas.")

    async def _handle_option_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, key: str, text: str
    ) -> None:
        """Apply one free-text option answer typed outside the button flow."""
        spec = self._spec(key)
        value = text.strip()
        if spec and spec.max_length and len(value) > spec.max_length:
            await update.effective_message.reply_text(
                f"Ese texto supera los {spec.max_length} caracteres permitidos."
            )
            return
        try:
            self.change_option(update.effective_user.id, key, value)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        context.user_data.pop("awaiting_option", None)
        options, _ = self.effective_options(update.effective_user.id)
        specs = self.generator.option_specs
        await update.effective_message.reply_text(
            panel_text(specs, options),
            parse_mode=ParseMode.HTML,
            reply_markup=panel_keyboard(specs, options),
        )

    # --- guided brief wizard -------------------------------------------------

    async def _guided_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
    ) -> None:
        """Route one guided answer to the field or cast sub-step it belongs to."""
        step = context.user_data.get("brief_step")
        spec = self.generator.brief_spec
        if step == "cast":
            await self._cast_text(update, context, text, spec)
            return
        try:
            value = check_length(step, text, spec)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        if step == "plot" and not value:
            await update.effective_message.reply_text("La trama no puede estar vacía.")
            return
        _user_log(update, f"respondió el campo guiado {step}")
        context.user_data["brief_values"][step] = value

        async def respond(text_: str, **kwargs) -> None:
            """Send the next wizard step as a new message."""
            await update.effective_message.reply_text(text_, **kwargs)

        await self._advance_brief_step(respond, context, step)

    async def _advance_brief_step(self, respond, context, current_step: str) -> None:
        """Move the wizard to its next step and render it through respond()."""
        spec = self.generator.brief_spec
        next_step = BRIEF_STEPS[BRIEF_STEPS.index(current_step) + 1]
        context.user_data["brief_step"] = next_step
        if next_step == "cast":
            cast = context.user_data["brief_values"].setdefault("cast", [])
            await respond(
                "Añade un personaje o continúa sin reparto.",
                reply_markup=cast_keyboard(len(cast), spec),
            )
            return
        if next_step == "confirm":
            outline = outline_from(context.user_data["brief_values"])
            await respond(
                outline_summary(outline), parse_mode=ParseMode.HTML, reply_markup=confirm_keyboard()
            )
            return
        markup = skip_keyboard(next_step) if next_step in SKIPPABLE_STEPS else None
        await respond(question(next_step, spec), reply_markup=markup)

    def _append_current_member(self, context) -> tuple[dict, list]:
        """Move the in-progress cast member into the brief's cast list."""
        member = context.user_data["current_member"]
        cast = context.user_data["brief_values"].setdefault("cast", [])
        cast.append(member)
        context.user_data["current_member"] = {}
        context.user_data["cast_step"] = None
        return member, cast

    async def _cast_text(self, update: Update, context, text: str, spec) -> None:
        """Route one text answer typed while filling in a cast member."""
        step = context.user_data.get("cast_step")
        if step is None:
            await update.effective_message.reply_text("Usa los botones para continuar.")
            return
        field = "name" if step == "name" else step
        try:
            value = check_length(field, text, spec)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        member = context.user_data["current_member"]
        if step == "name":
            await self._cast_name(update, context, value, member, spec)
            return
        if step == "description":
            member["description"] = value
            context.user_data["cast_step"] = "secret"
            await update.effective_message.reply_text(
                question("secret", spec), reply_markup=skip_keyboard("secret")
            )
            return
        member["secret"] = value
        added, cast = self._append_current_member(context)
        await update.effective_message.reply_text(
            f"Personaje añadido: {added['name']}. ¿Añadir otro?",
            reply_markup=cast_keyboard(len(cast), spec),
        )

    async def _cast_name(self, update: Update, context, value: str, member: dict, spec) -> None:
        """Validate a cast member's name against the outline built so far."""
        if not value:
            await update.effective_message.reply_text("El nombre no puede estar vacío.")
            return
        tentative = context.user_data["brief_values"].get("cast", []) + [{"name": value}]
        outline = outline_from({**context.user_data["brief_values"], "cast": tentative})
        try:
            self.generator.validate_outline(outline)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        member["name"] = value
        context.user_data["cast_step"] = "role"
        await update.effective_message.reply_text(
            "¿Qué rol tiene?", reply_markup=role_keyboard(spec)
        )

    async def brief_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Dispatch one ``brief:...`` callback to its handling method."""
        query = update.callback_query
        parts = query.data.split(":")
        action = parts[1]
        arg = parts[2] if len(parts) > 2 else None
        handler = {
            "skip": self._brief_skip,
            "role": self._brief_role,
            "pron": self._brief_pronoun,
            "add": self._brief_add,
            "undo": self._brief_undo,
            "next": self._brief_next,
            "opts": self._brief_opts,
            "restart": self._brief_restart,
            "go": self._brief_go,
        }.get(action)
        if handler is None:
            await query.answer()
            return
        await handler(query, context, arg)

    async def _brief_skip(self, query, context, step: str) -> None:
        """Leave one skippable field empty, in the top-level wizard or a cast member."""
        if (
            context.user_data.get("brief_step") == "cast"
            and context.user_data.get("cast_step") == step
        ):
            await query.answer()
            await self._cast_skip(query, context, step)
            return
        if context.user_data.get("brief_step") != step:
            await query.answer("Ese paso ya no está activo.", show_alert=True)
            return
        await query.answer()
        context.user_data["brief_values"][step] = ""

        async def respond(text_: str, **kwargs) -> None:
            """Edit the wizard's message in place with its next step."""
            await query.edit_message_text(text_, **kwargs)

        await self._advance_brief_step(respond, context, step)

    async def _cast_skip(self, query, context, step: str) -> None:
        """Leave one skippable cast field empty, in the button-driven flow."""
        spec = self.generator.brief_spec
        member = context.user_data["current_member"]
        if step == "description":
            member["description"] = ""
            context.user_data["cast_step"] = "secret"
            await query.edit_message_text(
                question("secret", spec), reply_markup=skip_keyboard("secret")
            )
            return
        member["secret"] = ""
        added, cast = self._append_current_member(context)
        await query.edit_message_text(
            f"Personaje añadido: {added['name']}. ¿Añadir otro?",
            reply_markup=cast_keyboard(len(cast), spec),
        )

    async def _brief_add(self, query, context, arg) -> None:
        """Start collecting one more cast member."""
        spec = self.generator.brief_spec
        cast = context.user_data["brief_values"].get("cast", [])
        if len(cast) >= spec.max_cast:
            await query.answer("Ya alcanzaste el máximo de personajes.", show_alert=True)
            return
        await query.answer()
        context.user_data["cast_step"] = "name"
        context.user_data["current_member"] = {}
        await query.edit_message_text(question("name", spec))

    async def _brief_role(self, query, context, index: str) -> None:
        """Record a cast member's chosen role and ask for their pronoun."""
        await query.answer()
        spec = self.generator.brief_spec
        context.user_data["current_member"]["role"] = spec.roles[int(index)].value
        context.user_data["cast_step"] = "pronoun"
        await query.edit_message_text("¿Qué pronombre usa?", reply_markup=pronoun_keyboard(spec))

    async def _brief_pronoun(self, query, context, index: str) -> None:
        """Record a cast member's chosen pronoun and ask for their description."""
        await query.answer()
        spec = self.generator.brief_spec
        context.user_data["current_member"]["pronoun"] = spec.pronouns[int(index)].value
        context.user_data["cast_step"] = "description"
        await query.edit_message_text(
            question("description", spec), reply_markup=skip_keyboard("description")
        )

    async def _brief_undo(self, query, context, arg) -> None:
        """Remove the most recently added cast member."""
        await query.answer()
        cast = context.user_data["brief_values"].get("cast", [])
        if cast:
            cast.pop()
        spec = self.generator.brief_spec
        await query.edit_message_text(
            "Personaje quitado. ¿Añadir otro?", reply_markup=cast_keyboard(len(cast), spec)
        )

    async def _brief_next(self, query, context, arg) -> None:
        """Leave the cast step, with however many members were added."""
        await query.answer()

        async def respond(text_: str, **kwargs) -> None:
            """Edit the wizard's message in place with its next step."""
            await query.edit_message_text(text_, **kwargs)

        await self._advance_brief_step(respond, context, "cast")

    async def _brief_opts(self, query, context, arg) -> None:
        """Open the options panel from the brief confirmation card."""
        await query.answer()
        context.user_data["panel_return"] = "confirm"
        await self._render_panel(query.from_user.id, query.edit_message_text)

    async def _brief_restart(self, query, context, arg) -> None:
        """Discard every collected answer and start the brief over."""
        await query.answer()
        context.user_data["brief_values"] = {}
        context.user_data["brief_step"] = "title"
        spec = self.generator.brief_spec
        await query.edit_message_text(question("title", spec), reply_markup=skip_keyboard("title"))

    async def _brief_go(self, query, context, arg) -> None:
        """Validate the finished outline and launch its generation."""
        outline = outline_from(context.user_data.get("brief_values", {}))
        try:
            self.generator.validate_outline(outline)
        except ValueError as exc:
            await query.answer()
            await query.edit_message_text(f"{exc}\n\nCorrige la obra con /newstory.")
            return
        await query.answer()
        fake_update = SimpleNamespace(
            effective_user=query.from_user,
            effective_chat=query.message.chat,
            effective_message=query.message,
        )
        await self._launch_generation(fake_update, context, outline)

    # --- after delivery -------------------------------------------------

    async def _after_delivery(self, context, chat_id: int, user, enrolled: bool) -> None:
        """Close the conversation and explain whether the story joined the study."""
        context.user_data.clear()
        if self.guide is None:
            return
        if enrolled:
            await self.guide.send(context.bot, chat_id, user.id)
            return
        if not self.guide.status(user.id).contributing:
            await context.bot.send_message(chat_id=chat_id, text=OUTSIDE_SAMPLE)

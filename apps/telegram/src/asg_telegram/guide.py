"""Participant journey of the experiment: where each user is and what comes next."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

from telegram import InlineKeyboardButton as Button
from telegram import InlineKeyboardMarkup as Keyboard
from telegram.constants import ParseMode

from .console import log_user_action

LOGGER = logging.getLogger(__name__)

PROFILES = {
    "occasional": "Lector ocasional",
    "regular": "Lector habitual",
    "expert": "Formación o trabajo en literatura",
}
OPEN_PHASES = frozenset({"preparation", "collection"})
ANNOUNCED_PHASES = frozenset({"collection", "evaluation", "closed"})


class Step(StrEnum):
    """Name each stage of a participant's journey through the study."""

    LOCKED = "locked"
    CONSENT = "consent"
    PROFILE = "profile"
    WAITING = "waiting"
    BASE_STORY = "base_story"
    READY = "ready"
    ENROLLMENT_CLOSED = "enrollment_closed"


@dataclass(frozen=True)
class Status:
    """Describe a user's current step, the study phase and their contribution."""

    step: Step
    phase: str
    participant: str | None = None
    enrolled: bool = False
    pending: bool = False
    is_author: bool = False

    @property
    def can_generate(self) -> bool:
        """Tell whether the user may open the story creation flow at all."""
        return self.step in {Step.BASE_STORY, Step.READY, Step.ENROLLMENT_CLOSED}

    @property
    def contributing(self) -> bool:
        """Tell whether the next story will be enrolled as the user's base story."""
        return (
            self.phase == "collection"
            and self.participant is not None
            and (self.step == Step.BASE_STORY or self.pending)
        )


# --- texts -----------------------------------------------------------------

LOCKED_TEXT = (
    "<b>Estudio sobre historias generadas automáticamente</b>\n\n"
    "Este bot forma parte de una tesis sobre generación automática de historias y solo "
    "está disponible para las personas invitadas al experimento.\n\n"
    "Para continuar, escribe en este chat la <b>clave de acceso</b> que te entregó el "
    "investigador."
)
KEY_ACCEPTED = "Clave correcta. Ya tienes acceso al estudio."
KEY_REJECTED = "La clave no es correcta. Te quedan {remaining} intentos."
KEY_LOCKED = (
    "Has superado el número de intentos permitidos. Por seguridad, el acceso queda "
    "bloqueado durante {minutes} minutos. Después podrás volver a intentarlo."
)
CALLBACK_LOCKED = "Primero escribe la clave de acceso."
PRIVATE_ONLY = "El estudio solo funciona en un chat privado con el bot."

CONSENT_TEXT = (
    "<b>Antes de empezar: en qué consiste tu participación</b>\n\n"
    "Este estudio compara historias producidas por distintos métodos de generación "
    "automática. Queremos saber cuáles prefieren las personas lectoras.\n\n"
    "<b>Qué te pediremos</b>\n"
    "1. <b>Tu perfil lector</b>: una sola pregunta sobre tu relación con la lectura.\n"
    "2. <b>Tu historia base</b>: crearás una historia con este bot. Será tu aportación "
    "al estudio y la leerán otros participantes, sin saber quién la pidió.\n"
    "3. <b>La evaluación</b>: cuando se abra la votación, leerás hasta 10 relatos en dos "
    "sesiones y elegirás, de dos en dos, cuál prefieres en creatividad, personajes y "
    "trama. Son unas 30 decisiones en total.\n\n"
    "<b>Tus garantías</b>\n"
    "• No sabrás con qué método se generó cada relato.\n"
    "• Tus respuestas se guardan con un seudónimo. Tu identificador de Telegram solo "
    "queda en la base administrativa del estudio y no aparece en los datos que se "
    "analizan ni se publican.\n"
    "• Puedes responder «No puedo decidir», pausar cuando quieras y retomar donde lo "
    "dejaste.\n"
    "• Participar es voluntario.\n\n"
    "¿Aceptas participar en estas condiciones?"
)
DECLINED_TEXT = (
    "Entendido: no se ha registrado ninguna participación a tu nombre. Si cambias de "
    "opinión, escribe /start."
)

PROFILE_TEXT = (
    "<b>Paso 1 de 3 · Tu perfil lector</b>\n\n"
    "Nos ayuda a interpretar las preferencias, porque lectores con trayectorias distintas "
    "pueden valorar cosas distintas. No hay respuestas mejores que otras.\n\n"
    "• <b>Lector ocasional</b>: lees ficción de vez en cuando.\n"
    "• <b>Lector habitual</b>: lees ficción con regularidad, por gusto.\n"
    "• <b>Formación o trabajo en literatura</b>: estudias, enseñas, escribes, editas o "
    "traduces.\n\n"
    "¿Cuál te describe mejor?"
)
PROFILE_SAVED = "Perfil guardado: {label}."

WAITING_TEXT = (
    "<b>Registro completado</b>\n\n"
    "Tu perfil está guardado. La recogida de historias todavía no ha comenzado; te "
    "escribiré por aquí en cuanto puedas crear tu historia base."
)

BASE_STORY_TEXT = (
    "<b>Paso 2 de 3 · Tu historia base</b>\n\n"
    "Ahora crearás tu <b>historia base</b>. Es tu aportación al estudio: entrará en la "
    "muestra que leerán y compararán los demás participantes, sin saber quién la pidió ni "
    "cómo se generó. A ti nunca te pediremos evaluarla.\n\n"
    "<b>Cómo crearla</b>\n"
    "1. Elige el formato: <i>historia narrativa</i> o <i>historia simulada</i>. Los dos "
    "producen prosa; el guion teatral no forma parte del estudio.\n"
    "2. Describe tu idea con un <i>prompt libre</i> (uno o dos párrafos) o con la "
    "<i>obra guiada</i>, en la que el bot te pregunta título, género, ambientación, trama "
    "y personajes.\n"
    "3. Si quieres, ajusta las opciones. Los valores por defecto funcionan bien.\n\n"
    "La generación tarda varios minutos. Te mostraré el progreso y te avisaré al terminar. "
    "Hasta que tu historia base quede inscrita no podrás crear otras historias.\n\n"
    "Si después quieres cambiarla, usa /aportar mientras siga abierta la recogida: la "
    "nueva sustituirá a la anterior."
)
BASE_RETRY = (
    "Tu historia base todavía no está inscrita. Cuando quieras, vuelve a intentarlo con /newstory."
)

FREE_COMMANDS = (
    "• /newstory: crear más historias para explorar el sistema, en cualquier formato "
    "(también guion teatral). Estas historias son solo para ti y no entran en el estudio.\n"
    "• /settings: ajustar tus opciones de generación."
)
READY_COLLECTION = (
    "<b>Tu historia base está inscrita</b> ✅\n\n"
    "Ya forma parte de la muestra del estudio. Mientras se cierra la recogida puedes "
    "usar:\n" + FREE_COMMANDS + "\n"
    "• /aportar: reemplazar tu historia base por otra nueva.\n\n"
    "<b>Paso 3 de 3 · La evaluación</b> se abrirá cuando todos hayan aportado su historia. "
    "Te avisaré por aquí."
)
AUTHOR_COLLECTION = (
    "<b>Registro completado</b>\n\n"
    "Como investigador no necesitas historia base: tus relatos seleccionados ya están "
    "inscritos. Puedes usar:\n" + FREE_COMMANDS + "\n\n"
    "Te avisaré cuando se abra la votación."
)
READY_FROZEN = (
    "<b>La recogida de historias está cerrada</b>\n\n"
    "Estamos preparando las comparaciones de cada participante. Te avisaré por aquí en "
    "cuanto se abra la votación. Mientras tanto puedes usar:\n" + FREE_COMMANDS
)
EVALUATION_INSTRUCTIONS = (
    "<b>Cómo funciona</b>\n"
    "1. Recibirás cada relato completo, como mensaje y como archivo. Léelo con calma, de "
    "principio a fin.\n"
    "2. Al terminar, pulsa <b>«Ya lo leí»</b>. Si al empezar reconoces el relato porque ya "
    "lo habías leído, pulsa <b>«Ya conocía esta historia»</b> en lugar de leerlo y te "
    "daré otro.\n"
    "3. Con los dos relatos leídos te preguntaré cuál prefieres en un aspecto concreto: "
    "creatividad, personajes o trama. Responde A o B. Si de verdad no puedes elegir, «No "
    "puedo decidir» también es una respuesta válida.\n"
    "4. No hay respuestas correctas: nos interesa tu impresión como lector.\n\n"
    "Son hasta 10 relatos en dos sesiones. Puedes parar con /pausa y continuar con "
    "/evaluar cuando quieras, sin perder nada."
)
READY_EVALUATION = "<b>Paso 3 de 3 · La evaluación está abierta</b>\n\n" + EVALUATION_INSTRUCTIONS
CLOSED_TEXT = (
    "<b>El estudio ha terminado</b>\n\n"
    "Muchas gracias por tu participación. Tus respuestas ya forman parte del análisis de "
    "la tesis."
)
ENROLLMENT_CLOSED_TEXT = (
    "<b>La inscripción en el estudio está cerrada</b>\n\n"
    "Ya no es posible incluir tu participación en la evaluación. Aun así puedes usar:\n"
    + FREE_COMMANDS
)
OUTSIDE_SAMPLE = (
    "Esta historia es solo para ti: no forma parte de la muestra del estudio. "
    "Usa /newstory para crear otra."
)
ANNOUNCEMENT_HEADERS = {
    "collection": "📣 <b>La recogida de historias ya está abierta.</b>\n\n",
    "evaluation": "📣 <b>¡Ya puedes evaluar!</b>\n\n",
    "closed": "",
}
HELP_TEXT = (
    "<b>Comandos disponibles</b>\n"
    "/start: ver en qué paso estás y qué sigue\n"
    "/newstory: crear una historia\n"
    "/settings: configurar las opciones de generación\n"
    "/aportar: crear o reemplazar tu historia base mientras la recogida esté abierta\n"
    "/evaluar: empezar o continuar la evaluación\n"
    "/pausa: pausar la evaluación\n"
    "/cancel: cancelar la solicitud en curso\n"
    "/help: mostrar esta ayuda"
)


def consent_keyboard() -> Keyboard:
    """Offer to accept or decline participation."""
    return Keyboard(
        [
            [Button("✅ Acepto participar", callback_data="guide:consent:yes")],
            [Button("No, gracias", callback_data="guide:consent:no")],
        ]
    )


def profile_keyboard() -> Keyboard:
    """Offer one button per reader profile."""
    return Keyboard(
        [[Button(label, callback_data=f"guide:profile:{key}")] for key, label in PROFILES.items()]
    )


class ParticipantGuide:
    """Derive each user's step from durable storage and explain it in the chat."""

    def __init__(self, bot) -> None:
        """Attach the coordinator whose queue and study hold the participant state."""
        self.bot = bot

    @property
    def queue(self):
        """Return the queue repository that stores access and announcements."""
        return self.bot.queue

    @property
    def repository(self):
        """Return the study repository that stores participants and contributions."""
        return self.bot.study.repository

    def status(self, user_id: int) -> Status:
        """Compute where a user stands, never from disposable conversation data."""
        access = self.queue.access(user_id)
        phase = self.repository.info()["state"]
        if access is None:
            return Status(Step.LOCKED, phase)
        if not access["consented_at"]:
            return Status(Step.CONSENT, phase)
        reader = self.repository.find_participant(str(user_id))
        if reader is None or not reader["profile"]:
            step = Step.PROFILE if phase in OPEN_PHASES else Step.ENROLLMENT_CLOSED
            return Status(step, phase, reader["id"] if reader else None)
        contribution = self.repository.contribution(reader["id"])
        fields = {
            "participant": reader["id"],
            "enrolled": contribution["enrolled"],
            "pending": contribution["pending"],
            "is_author": bool(reader["is_author"]),
        }
        if phase == "preparation":
            return Status(Step.WAITING, phase, **fields)
        if phase == "collection" and not contribution["enrolled"] and not reader["is_author"]:
            return Status(Step.BASE_STORY, phase, **fields)
        return Status(Step.READY, phase, **fields)

    def render(self, status: Status) -> tuple[str, Keyboard | None]:
        """Explain a step and offer the button that moves the user forward."""
        if status.step == Step.LOCKED:
            return LOCKED_TEXT, None
        if status.step == Step.CONSENT:
            return CONSENT_TEXT, consent_keyboard()
        if status.step == Step.PROFILE:
            return PROFILE_TEXT, profile_keyboard()
        if status.step == Step.WAITING:
            return WAITING_TEXT, None
        if status.step == Step.ENROLLMENT_CLOSED:
            return ENROLLMENT_CLOSED_TEXT, None
        if status.step == Step.BASE_STORY:
            button = Button("✍️ Crear mi historia base", callback_data="guide:base")
            return BASE_STORY_TEXT, Keyboard([[button]])
        if status.phase == "evaluation":
            button = Button("▶️ Empezar a evaluar", callback_data="guide:evaluate")
            return READY_EVALUATION, Keyboard([[button]])
        if status.phase == "closed":
            return CLOSED_TEXT, None
        if status.phase == "collection":
            return (AUTHOR_COLLECTION if status.is_author else READY_COLLECTION), None
        return READY_FROZEN, None

    async def send(self, bot, chat_id: int, user_id: int, *, header: str = "") -> None:
        """Send a user's current step and remember that they know the current phase."""
        status = self.status(user_id)
        text, markup = self.render(status)
        await bot.send_message(
            chat_id=chat_id, text=header + text, parse_mode=ParseMode.HTML, reply_markup=markup
        )
        if status.phase in ANNOUNCED_PHASES and status.step not in {Step.LOCKED, Step.CONSENT}:
            self.queue.mark_announced(user_id, status.phase)

    async def show(self, update, context) -> None:
        """Answer /start and any stray message with the user's current step."""
        await self.send(context.bot, update.effective_chat.id, update.effective_user.id)

    async def help(self, update, context) -> None:
        """List every command, then repeat the user's current step."""
        await update.effective_message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)
        await self.show(update, context)

    async def callback(self, update, context) -> None:
        """Handle consent, profile and the shortcut buttons of the journey."""
        query = update.callback_query
        user = update.effective_user
        parts = query.data.split(":")
        action = parts[1] if len(parts) > 1 else ""
        value = parts[2] if len(parts) > 2 else ""
        if action == "base":
            await query.answer()
            await query.edit_message_reply_markup(reply_markup=None)
            await self.bot.new_story(update, context)
            return
        if action == "evaluate":
            await query.answer()
            await query.edit_message_reply_markup(reply_markup=None)
            await self.bot.study.evaluate(update, context)
            return
        try:
            notice = self._record_answer(user.id, action, value)
        except ValueError as exc:
            await query.answer(str(exc), show_alert=True)
            return
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=None)
        log_user_action(
            LOGGER,
            user_id=user.id,
            username=user.username or user.full_name,
            action=f"respondió {action}: {value}",
        )
        if notice:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=notice)
        if action == "consent" and value == "no":
            return
        await self.send(context.bot, update.effective_chat.id, user.id)

    def _record_answer(self, user_id: int, action: str, value: str) -> str:
        """Persist a consent or profile answer and return the confirmation to show."""
        status = self.status(user_id)
        if action == "consent" and value in {"yes", "no"}:
            if status.step == Step.LOCKED:
                raise ValueError(CALLBACK_LOCKED)
            self.queue.set_consent(user_id, value == "yes")
            return "" if value == "yes" else DECLINED_TEXT
        if action == "profile" and value in PROFILES:
            if status.step != Step.PROFILE:
                raise ValueError("Este paso ya no está activo.")
            self.repository.participant(str(user_id), profile=value)
            return PROFILE_SAVED.format(label=PROFILES[value])
        raise ValueError("Botón desconocido.")

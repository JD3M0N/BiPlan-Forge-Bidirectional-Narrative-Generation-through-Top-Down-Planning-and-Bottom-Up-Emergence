"""Conversation states shared by the coordinator and the chat handlers."""

from __future__ import annotations

from enum import StrEnum


class ConversationState(StrEnum):
    """Name every state a user's conversation can be parked in."""

    CHOOSE_MODE = "choose_mode"
    FREE_PROMPT = "free_prompt"
    GUIDED = "guided"
    GENERATING = "generating"
    DELIVERING = "delivering"
    EVALUATING = "evaluating"

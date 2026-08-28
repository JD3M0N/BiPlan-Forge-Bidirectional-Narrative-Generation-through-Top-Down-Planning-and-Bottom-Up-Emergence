"""Shared callable types for interactive console components."""

from collections.abc import Callable

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

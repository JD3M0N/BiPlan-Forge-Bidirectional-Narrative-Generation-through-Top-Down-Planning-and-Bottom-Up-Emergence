"""Windows console niceties for the bot's hosted window: stdlib only, no PTB import."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable


def set_console_title(title: str) -> None:
    """Set the terminal window's title, on Windows and on an OSC-aware terminal alike."""
    if os.name == "nt":
        import ctypes

        ctypes.windll.kernel32.SetConsoleTitleW(title)
        return
    if sys.stdout.isatty():
        sys.stdout.write(f"\x1b]0;{title}\x07")
        sys.stdout.flush()


def disable_quick_edit() -> Callable[[], None]:
    """Turn off Windows QuickEdit, whose mouse selection freezes console output.

    Returns a function that restores the console's earlier mode; calling it is
    a no-op off Windows.
    """
    if os.name != "nt":
        return lambda: None
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
    previous = ctypes.c_uint32()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(previous)):
        return lambda: None
    enable_extended_flags = 0x0080
    quick_edit_mode = 0x0040
    kernel32.SetConsoleMode(handle, (previous.value & ~quick_edit_mode) | enable_extended_flags)

    def restore() -> None:
        """Put QuickEdit back the way this process found it."""
        kernel32.SetConsoleMode(handle, previous.value)

    return restore


def wait_for_enter(prompt: str, input_fn: Callable[[str], str] = input) -> None:
    """Block for Enter so a hosted console window stays open to show its last output."""
    try:
        input_fn(prompt)
    except (EOFError, KeyboardInterrupt):
        pass

"""Clock, terminal output, and non-blocking keyboard input."""

from __future__ import annotations

import os
import sys
import time
from typing import Protocol, TextIO


class Clock(Protocol):
    """Represent Clock data and behavior."""

    def monotonic(self) -> float:
        """Handle the monotonic operation for Clock."""
        ...

    def sleep(self, seconds: float) -> None:
        """Handle the sleep operation for Clock."""
        ...


class SystemClock:
    """Represent SystemClock data and behavior."""

    def monotonic(self) -> float:
        """Handle the monotonic operation for SystemClock."""
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        """Handle the sleep operation for SystemClock."""
        time.sleep(seconds)


class KeyboardInput(Protocol):
    """Represent KeyboardInput data and behavior."""

    def __enter__(self) -> KeyboardInput:
        """Enter the managed runtime context."""
        ...

    def __exit__(self, *args: object) -> None:
        """Exit the managed runtime context and release resources."""
        ...

    def poll(self) -> str | None:
        """Poll for the next available input event."""
        ...


class RealKeyboardInput:
    """Read immediate keyboard input on Windows and POSIX terminals."""

    def __init__(self, stream: TextIO | None = None) -> None:
        """Initialize the RealKeyboardInput instance."""
        self.stream = stream or sys.stdin
        self._old_settings: object | None = None

    def __enter__(self) -> RealKeyboardInput:
        """Enter the managed runtime context."""
        if os.name != "nt" and self.stream.isatty():
            import termios
            import tty

            self._old_settings = termios.tcgetattr(self.stream.fileno())
            tty.setcbreak(self.stream.fileno())
        return self

    def __exit__(self, *args: object) -> None:
        """Exit the managed runtime context and release resources."""
        if os.name != "nt" and self._old_settings is not None:
            import termios

            termios.tcsetattr(self.stream.fileno(), termios.TCSADRAIN, self._old_settings)

    def poll(self) -> str | None:
        """Poll for the next available input event."""
        if os.name == "nt":
            import msvcrt

            if not msvcrt.kbhit():
                return None
            key = msvcrt.getwch()
            if key in {"\x00", "\xe0"} and msvcrt.kbhit():
                msvcrt.getwch()
                return None
            return key
        if not self.stream.isatty():
            return None
        import select

        ready, _, _ = select.select([self.stream], [], [], 0)
        return self.stream.read(1) if ready else None


class Terminal:
    """Represent Terminal data and behavior."""

    def __init__(self, stream: TextIO | None = None) -> None:
        """Initialize the Terminal instance."""
        self.stream = stream or sys.stdout

    def draw(self, content: str) -> None:
        # ANSI clear-screen works in modern PowerShell and POSIX terminals.
        """Render the current state to the terminal."""
        self.stream.write("\033[2J\033[H")
        self.stream.write(content)
        if not content.endswith("\n"):
            self.stream.write("\n")
        self.stream.flush()

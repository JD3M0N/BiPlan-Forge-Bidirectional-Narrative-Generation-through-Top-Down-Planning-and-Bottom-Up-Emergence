"""Reloj, salida de terminal y lectura de teclas no bloqueante."""

from __future__ import annotations

import os
import sys
import time
from typing import Protocol, TextIO


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class KeyboardInput(Protocol):
    def __enter__(self) -> "KeyboardInput": ...

    def __exit__(self, *args: object) -> None: ...

    def poll(self) -> str | None: ...


class RealKeyboardInput:
    """Teclado inmediato en Windows y terminales POSIX."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream or sys.stdin
        self._old_settings: object | None = None

    def __enter__(self) -> "RealKeyboardInput":
        if os.name != "nt" and self.stream.isatty():
            import termios
            import tty

            self._old_settings = termios.tcgetattr(self.stream.fileno())
            tty.setcbreak(self.stream.fileno())
        return self

    def __exit__(self, *args: object) -> None:
        if os.name != "nt" and self._old_settings is not None:
            import termios

            termios.tcsetattr(
                self.stream.fileno(), termios.TCSADRAIN, self._old_settings
            )

    def poll(self) -> str | None:
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
    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream or sys.stdout

    def draw(self, content: str) -> None:
        # ANSI clear-screen works in modern PowerShell and POSIX terminals.
        self.stream.write("\033[2J\033[H")
        self.stream.write(content)
        if not content.endswith("\n"):
            self.stream.write("\n")
        self.stream.flush()


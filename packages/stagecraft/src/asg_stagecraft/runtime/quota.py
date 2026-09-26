"""Process-wide Gemini request pacing and retry diagnostics."""

import random
import re
import threading
import time
from collections import deque
from collections.abc import Callable

WaitCallback = Callable[[int, str], None]


class SlidingWindowLimiter:
    """Represent SlidingWindowLimiter data and behavior."""

    def __init__(self, capacity: int, window: float = 60.0) -> None:
        """Initialize the SlidingWindowLimiter instance."""
        self.capacity = max(1, capacity)
        self.window = window
        self._requests: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self, callback: WaitCallback | None = None) -> float:
        """Handle the acquire operation for SlidingWindowLimiter."""
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                while self._requests and now - self._requests[0] >= self.window:
                    self._requests.popleft()
                if len(self._requests) < self.capacity:
                    self._requests.append(now)
                    return waited
                delay = max(0.05, self.window - (now - self._requests[0]) + 0.05)
            waited += delay
            countdown_wait(delay, "límite preventivo RPM", callback)


class TokenWindowLimiter:
    """Represent TokenWindowLimiter data and behavior."""

    def __init__(self, capacity: int, window: float = 60.0) -> None:
        """Initialize the TokenWindowLimiter instance."""
        self.capacity, self.window = capacity, window
        self._tokens: deque[tuple[float, int]] = deque()
        self._lock = threading.Lock()

    def acquire(self, tokens: int, callback: WaitCallback | None = None) -> float:
        """Handle the acquire operation for TokenWindowLimiter."""
        if tokens > self.capacity:
            raise ValueError("A single prompt exceeds GEMINI_TPM_LIMIT")
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                while self._tokens and now - self._tokens[0][0] >= self.window:
                    self._tokens.popleft()
                if sum(value for _, value in self._tokens) + tokens <= self.capacity:
                    self._tokens.append((now, tokens))
                    return waited
                delay = max(0.05, self.window - (now - self._tokens[0][0]) + 0.05)
            waited += delay
            countdown_wait(delay, "límite preventivo TPM", callback)


def countdown_wait(delay: float, reason: str, callback: WaitCallback | None) -> None:
    """Wait wait."""
    remaining = delay
    while remaining > 0:
        if callback and (remaining == delay or remaining <= 1 or int(remaining) % 5 == 0):
            callback(max(1, int(round(remaining))), reason)
        step = min(1.0, remaining)
        time.sleep(step)
        remaining -= step


def retry_details(exc: Exception) -> dict[str, object]:
    """Calculate details."""
    text = str(exc)
    delay_match = re.search(
        r"(?:retryDelay['\"]?\s*:\s*['\"]?|retry in\s+)(\d+(?:\.\d+)?)", text, re.I
    )
    metric = re.search(r"Quota exceeded for metric:\s*([^,\n]+)", text, re.I)
    quota_id = re.search(r"quotaId['\"]?\s*:\s*['\"]([^'\"]+)", text, re.I)
    status = re.match(r"\s*([45]\d{2})\b", text)
    explicit_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if not isinstance(explicit_code, int):
        explicit_code = None
    return {
        "status": explicit_code or (int(status.group(1)) if status else None),
        "status_name": getattr(exc, "status", None),
        "retry_delay": float(delay_match.group(1)) if delay_match else None,
        "metric": metric.group(1).strip() if metric else None,
        "quota_id": quota_id.group(1) if quota_id else None,
    }


def retry_delay(attempt: int, details: dict[str, object]) -> float:
    """Calculate delay."""
    supplied = details.get("retry_delay")
    base = float(supplied) if supplied is not None else float(2**attempt)
    return base + random.uniform(0, 2)

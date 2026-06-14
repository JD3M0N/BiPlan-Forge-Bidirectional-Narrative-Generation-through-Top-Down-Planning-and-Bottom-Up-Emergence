import asyncio
import json
import re
import time

import httpx

from app.logging_utils import get_logger


class GeminiConfigurationError(RuntimeError):
    """Raised when Gemini is not configured."""


class GeminiRateLimitError(RuntimeError):
    """Raised when Gemini rate limit or quota is exhausted."""


def clean_json_payload(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    decoder = json.JSONDecoder()
    for start, character in enumerate(text):
        if character not in "{[":
            continue
        try:
            _, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        return text[start : start + end].strip()
    return text


class GeminiClient:
    base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        api_key: str,
        model: str,
        max_retries: int = 3,
        rate_limit_max_retries: int | None = None,
        retry_base_seconds: float = 2.0,
        min_request_interval_seconds: float = 3.2,
        transport=None,
        sleep=None,
        clock=None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.rate_limit_max_retries = rate_limit_max_retries or max_retries
        self.retry_base_seconds = retry_base_seconds
        self.min_request_interval_seconds = max(min_request_interval_seconds, 0.0)
        self.transport = transport
        self.sleep = sleep or asyncio.sleep
        self.clock = clock or time.monotonic
        self._throttle_lock = asyncio.Lock()
        self._last_request_at: float | None = None
        self.logger = get_logger("gemini")

    def _build_url(self) -> str:
        if not self.api_key:
            raise GeminiConfigurationError("Missing GEMINI_API_KEY")
        return f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"

    async def _generate(self, prompt: str, response_mime_type: str | None = None) -> str:
        payload: dict = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ]
        }
        if response_mime_type:
            payload["generationConfig"] = {"responseMimeType": response_mime_type}

        attempt = 1
        while True:
            try:
                await self._throttle()
                async with httpx.AsyncClient(timeout=120, transport=self.transport) as client:
                    response = await client.post(self._build_url(), json=payload)
            except httpx.RequestError as exc:
                message = f"Gemini request failed: {exc.__class__.__name__}"
                self.logger.warning("gemini_transport_error model=%s attempt=%s error=%s", self.model, attempt, message)
                if attempt >= self.max_retries:
                    raise RuntimeError(message) from exc
                await self.sleep(self._retry_delay(attempt))
                attempt += 1
                continue

            if response.status_code == 429:
                detail = self._extract_error_message(response)
                self.logger.warning(
                    "gemini_rate_limited model=%s attempt=%s detail=%s",
                    self.model,
                    attempt,
                    detail,
                )
                if attempt >= self.rate_limit_max_retries:
                    raise GeminiRateLimitError(
                        "Gemini rate limit or quota reached. Wait a few minutes and try again, "
                        "or use another Gemini API key/model."
                    )
                delay = self._rate_limit_retry_delay(response, detail, attempt)
                self.logger.info(
                    "gemini_rate_limit_wait model=%s attempt=%s wait_seconds=%.2f",
                    self.model,
                    attempt,
                    delay,
                )
                await self.sleep(delay)
                attempt += 1
                continue

            if response.status_code >= 500:
                detail = self._extract_error_message(response)
                self.logger.warning(
                    "gemini_server_error model=%s attempt=%s status=%s detail=%s",
                    self.model,
                    attempt,
                    response.status_code,
                    detail,
                )
                if attempt >= self.max_retries:
                    raise RuntimeError(f"Gemini server error ({response.status_code}): {detail}")
                await self.sleep(self._retry_delay(attempt))
                attempt += 1
                continue

            if response.status_code >= 400:
                detail = self._extract_error_message(response)
                raise RuntimeError(f"Gemini request failed ({response.status_code}): {detail}")

            break

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response")
        return text

    async def generate_json(self, prompt: str) -> dict:
        raw_text = await self._generate(prompt, response_mime_type="application/json")
        return json.loads(clean_json_payload(raw_text))

    async def generate_text(self, prompt: str) -> str:
        return await self._generate(prompt)

    def _retry_delay(self, attempt: int) -> float:
        return min(self.retry_base_seconds * (2 ** (attempt - 1)), 20.0)

    async def _throttle(self) -> None:
        if self.min_request_interval_seconds <= 0:
            return

        async with self._throttle_lock:
            now = self.clock()
            if self._last_request_at is not None:
                elapsed = now - self._last_request_at
                wait_seconds = self.min_request_interval_seconds - elapsed
                if wait_seconds > 0:
                    self.logger.info(
                        "gemini_throttle_wait model=%s wait_seconds=%.2f",
                        self.model,
                        wait_seconds,
                    )
                    await self.sleep(wait_seconds)
                    now = self.clock()
            self._last_request_at = now

    def _rate_limit_retry_delay(self, response: httpx.Response, detail: str, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(float(retry_after), self._retry_delay(attempt))
            except ValueError:
                pass

        retry_match = re.search(r"retry in\s+([0-9.]+)s", detail, re.IGNORECASE)
        if retry_match:
            return max(float(retry_match.group(1)) + 1.0, self._retry_delay(attempt))

        try:
            payload = response.json()
        except ValueError:
            return self._retry_delay(attempt)

        for item in payload.get("error", {}).get("details", []):
            retry_delay = item.get("retryDelay")
            if not retry_delay or not retry_delay.endswith("s"):
                continue
            try:
                return max(float(retry_delay[:-1]) + 1.0, self._retry_delay(attempt))
            except ValueError:
                continue
        return self._retry_delay(attempt)

    def _extract_error_message(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text.strip() or "Unknown Gemini error"

        error_payload = payload.get("error", {})
        return (
            error_payload.get("message")
            or error_payload.get("status")
            or response.text.strip()
            or "Unknown Gemini error"
        )

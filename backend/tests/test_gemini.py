import asyncio

import httpx

from app.services.gemini import GeminiClient, GeminiRateLimitError, clean_json_payload


def run(coro):
    return asyncio.run(coro)


def test_gemini_429_message_is_sanitized() -> None:
    def handler(request):
        return httpx.Response(
            429,
            json={
                "error": {
                    "message": "Quota exceeded for free tier",
                    "status": "RESOURCE_EXHAUSTED",
                }
            },
            request=request,
        )

    client = GeminiClient(
        api_key="secret-key-should-not-leak",
        model="gemini-2.0-flash",
        max_retries=2,
        retry_base_seconds=0.01,
        transport=httpx.MockTransport(handler),
    )

    try:
        run(client.generate_json("test"))
        raise AssertionError("Expected GeminiRateLimitError")
    except GeminiRateLimitError as exc:
        message = str(exc)
        assert "quota" in message.lower() or "rate limit" in message.lower()
        assert "secret-key-should-not-leak" not in message


def test_gemini_429_waits_for_retry_hint_before_retrying() -> None:
    calls = 0
    sleeps = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                429,
                json={
                    "error": {
                        "message": (
                            "Quota exceeded for metric: generate_content_free_tier_requests. "
                            "Please retry in 5.5s."
                        ),
                        "status": "RESOURCE_EXHAUSTED",
                    }
                },
                request=request,
            )
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "{\"ok\": true}"}]}}]},
            request=request,
        )

    client = GeminiClient(
        api_key="secret-key-should-not-leak",
        model="gemini-2.0-flash",
        max_retries=2,
        retry_base_seconds=0.01,
        transport=httpx.MockTransport(handler),
        sleep=fake_sleep,
    )

    assert run(client.generate_json("test")) == {"ok": True}
    assert calls == 2
    assert sleeps == [6.5]


def test_gemini_rate_limit_retries_are_separate_from_regular_retries() -> None:
    calls = 0
    sleeps = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    def handler(request):
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(
                429,
                headers={"Retry-After": "1.25"},
                json={
                    "error": {
                        "message": "Quota exceeded. Please retry in 1.25s.",
                        "status": "RESOURCE_EXHAUSTED",
                    }
                },
                request=request,
            )
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "{\"ok\": true}"}]}}]},
            request=request,
        )

    client = GeminiClient(
        api_key="secret-key-should-not-leak",
        model="gemini-2.0-flash",
        max_retries=1,
        rate_limit_max_retries=3,
        retry_base_seconds=0.01,
        transport=httpx.MockTransport(handler),
        sleep=fake_sleep,
    )

    assert run(client.generate_json("test")) == {"ok": True}
    assert calls == 3
    assert sleeps == [1.25, 1.25]


def test_clean_json_payload_removes_markdown_fences() -> None:
    payload = clean_json_payload("```json\n{\"title\":\"Hola\"}\n```")
    assert payload == "{\"title\":\"Hola\"}"


def test_clean_json_payload_keeps_first_complete_json_value() -> None:
    payload = clean_json_payload('{"chapter_index": 2, "title": "Dos"}\n{"notes": ["extra"]}')
    assert payload == '{"chapter_index": 2, "title": "Dos"}'


def test_clean_json_payload_removes_text_around_json() -> None:
    payload = clean_json_payload('Respuesta [borrador]:\n{"title": "Hola"}\nListo.')
    assert payload == '{"title": "Hola"}'

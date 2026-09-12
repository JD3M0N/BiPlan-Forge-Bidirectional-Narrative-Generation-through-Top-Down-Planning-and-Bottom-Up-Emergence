import pytest
from asg_top_down.quota import SlidingWindowLimiter, retry_details


def test_retry_details_extracts_google_quota_fields() -> None:
    error = Exception(
        "429 RESOURCE_EXHAUSTED Quota exceeded for metric: generate_content_requests, "
        "limit: 15, 'quotaId': 'PerMinute', 'retryDelay': '28s'"
    )
    details = retry_details(error)
    assert details["status"] == 429
    assert details["retry_delay"] == 28
    assert details["metric"] == "generate_content_requests"
    assert details["quota_id"] == "PerMinute"


@pytest.mark.parametrize(
    ("message", "code", "expected_status"),
    [
        ("El modelo devolvio 429 tokens en el intento con id 503201", None, None),
        ("solicitud 503201 aceptada tras el intento 500", 429, 429),
    ],
    ids=["unrelated-three-digit-numbers-are-ignored", "explicit-code-wins-over-confusing-text"],
)
def test_retry_details_status_parsing(message, code, expected_status) -> None:
    error = Exception(message)
    if code is not None:
        error.code = code
    assert retry_details(error)["status"] == expected_status


def test_sliding_window_never_accepts_more_than_capacity(monkeypatch) -> None:
    now = [0.0]
    monkeypatch.setattr("asg_top_down.quota.time.monotonic", lambda: now[0])

    def advance(delay, reason, callback):
        now[0] += delay

    monkeypatch.setattr("asg_top_down.quota.countdown_wait", advance)
    limiter = SlidingWindowLimiter(14)
    accepted = []
    for _ in range(21):
        limiter.acquire()
        accepted.append(now[0])
    assert accepted[13] == 0
    assert accepted[14] >= 60
    assert sum(1 for value in accepted if value < 60) == 14

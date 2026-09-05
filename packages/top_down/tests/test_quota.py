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


def test_retry_details_ignores_unrelated_three_digit_numbers() -> None:
    error = Exception("El modelo devolvio 429 tokens en el intento con id 503201")
    details = retry_details(error)
    assert details["status"] is None


def test_retry_details_prefers_explicit_code_over_confusing_text() -> None:
    error = Exception("solicitud 503201 aceptada tras el intento 500")
    error.code = 429
    details = retry_details(error)
    assert details["status"] == 429


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

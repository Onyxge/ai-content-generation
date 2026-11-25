import pytest

from pipeline.engine.retry import DailyQuotaError, TransientError, call_with_retry


def test_transient_errors_are_retried_and_every_attempt_reported():
    attempts, seen = [], []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise TransientError("429 per-minute limit", retry_after=0)
        return {"ok": True}

    result = call_with_retry(flaky, lambda n, status, *_: seen.append((n, status)), sleep=lambda s: None)
    assert result == {"ok": True}
    assert seen == [(1, "transient"), (2, "transient"), (3, "ok")]


def test_a_daily_quota_is_not_retried():
    seen = []

    def exhausted():
        raise DailyQuotaError("100 requests per day", cap=100)

    with pytest.raises(DailyQuotaError):
        call_with_retry(exhausted, lambda n, status, *_: seen.append((n, status)), sleep=lambda s: None)
    assert seen == [(1, "quota")]

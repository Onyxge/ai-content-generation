"""Failure classes and the retry policy (01-plan §8)."""
from __future__ import annotations

import random
import time
from typing import Callable


class ProviderError(Exception):
    """A provider call that did not produce an artifact."""

    status = "error"


class TransientError(ProviderError):
    """Per-minute rate limit, 5xx or timeout: worth retrying."""

    status = "transient"

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class DailyQuotaError(ProviderError):
    """Daily allowance used up: stop calling this provider for the rest of the run."""

    status = "quota"

    def __init__(self, message: str, cap: int | None = None):
        super().__init__(message)
        self.cap = cap


class BadRequestError(ProviderError):
    status = "bad_request"


class SafetyBlockError(ProviderError):
    status = "safety_block"


class ProviderUnavailable(ProviderError):
    """No call was made: the provider isn't configured, or the work runs on a remote GPU."""

    status = "unavailable"

    def __init__(self, message: str, pending: bool = False):
        super().__init__(message)
        self.pending = pending


def backoff(attempt: int, base: float = 2.0, cap: float = 60.0, rng: Callable[[], float] = random.random) -> float:
    """Exponential backoff with jitter: about 1–2 s, 2–4 s, 4–8 s…, never more than `cap`."""
    return min(cap, base ** attempt) * (0.5 + rng() / 2)


def call_with_retry(fn, on_attempt, attempts: int = 4, sleep=time.sleep):
    """Run fn() and report every attempt as on_attempt(n, status, latency_ms, error, result).
    Only transient errors are retried; anything else is reported once and raised."""
    last: Exception | None = None
    for n in range(1, attempts + 1):
        t0 = time.perf_counter()
        try:
            result = fn()
        except TransientError as e:
            on_attempt(n, e.status, _ms(t0), e, None)
            last = e
            if n < attempts:
                sleep(e.retry_after if e.retry_after is not None else backoff(n))
            continue
        except ProviderError as e:
            on_attempt(n, e.status, _ms(t0), e, None)
            raise
        on_attempt(n, "ok", _ms(t0), None, result)
        return result
    assert last is not None
    raise last


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)

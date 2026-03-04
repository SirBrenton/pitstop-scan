"""
429-floor receipt

Invariant:
- If HTTP 429 and Retry-After is present+valid -> sleep >= Retry-After (a floor), then retry (budgeted).
- If HTTP 429 and Retry-After missing/invalid -> do NOT retry (avoid thundering herd / guessy backoff).
- For transient 5xx -> budgeted backoff retries are allowed.

This module is intentionally tiny and stdlib-only.

Drop-in usage:
- Provide a `do_request()` callable that returns: (status_code, headers_dict, payload)
- Call `run_with_retry(do_request, policy=RetryPolicy(...))`
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Dict, Optional, Tuple, Any
import time
import random


TRANSIENT_5XX = {500, 502, 503, 504}


class RetryExhausted(RuntimeError):
    """Raised when we keep hitting retryable failures until budgets stop."""


@dataclass(frozen=True)
class RetryPolicy:
    # attempt is 1-based for retries (1 = first retry after the initial request)
    max_attempts: int = 6          # max retry attempts (NOT counting the initial request)
    max_elapsed_s: float = 30.0    # hard cap on total time spent retrying (monotonic)
    base_delay_s: float = 0.5      # exponential backoff base
    max_delay_s: float = 10.0      # cap backoff delay
    jitter_frac: float = 0.2       # +/- jitter fraction applied to BACKOFF (not to Retry-After)


def parse_retry_after(value: Optional[str], *, now: Optional[datetime] = None) -> Optional[float]:
    """
    Parse Retry-After header into seconds.

    Supports:
      - delta-seconds: "2"  -> 2.0
      - HTTP-date: "Wed, 21 Oct 2015 07:28:00 GMT" -> seconds until that date (>=0)
    """
    if not value:
        return None

    v = value.strip()

    # delta-seconds
    try:
        secs = float(v)
        return secs if secs >= 0 else None
    except ValueError:
        pass

    # HTTP-date
    try:
        dt = parsedate_to_datetime(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        now_dt = now or datetime.now(timezone.utc)
        delta = (dt - now_dt).total_seconds()
        return delta if delta >= 0 else 0.0
    except Exception:
        return None


def _jitter(backoff_s: float, jitter_frac: float, rng: Callable[[], float]) -> float:
    """
    Apply symmetric jitter in [-jitter_frac, +jitter_frac].

    rng() must return in [0, 1).
    """
    if jitter_frac <= 0:
        return max(0.0, backoff_s)

    span = (rng() * 2.0) - 1.0  # [-1, +1)
    return max(0.0, backoff_s * (1.0 + span * jitter_frac))


def compute_sleep_s(
    *,
    attempt: int,
    retry_after_s: Optional[float],
    policy: RetryPolicy,
    rng: Callable[[], float] = random.random,
) -> float:
    """
    Compute sleep duration for the next retry attempt.

    attempt: 1-based retry attempt number (1 for first retry, 2 for second retry, ...)
    """
    if attempt < 1:
        raise ValueError("attempt must be >= 1")

    # exponential backoff with cap
    backoff = min(policy.max_delay_s, policy.base_delay_s * (2 ** (attempt - 1)))
    backoff = _jitter(backoff, policy.jitter_frac, rng)

    # Core invariant: Retry-After is a FLOOR (never retry earlier than server requested).
    if retry_after_s is not None:
        return max(float(retry_after_s), backoff)

    return backoff


def should_retry(
    *,
    status_code: int,
    retry_after_s: Optional[float],
    attempt: int,
    elapsed_s: float,
    policy: RetryPolicy,
) -> bool:
    """
    Budget gate + semantics gate.

    attempt: 1-based retry attempt number you are about to make (1..max_attempts).
    """
    # budgets
    if attempt > policy.max_attempts:
        return False
    if elapsed_s >= policy.max_elapsed_s:
        return False

    # semantics
    if status_code == 429:
        # Hard stance: only retry 429 when server gives concrete delay
        return retry_after_s is not None

    if status_code in TRANSIENT_5XX:
        return True

    return False


def run_with_retry(
    do_request: Callable[[], Tuple[int, Dict[str, str], Any]],
    *,
    policy: RetryPolicy = RetryPolicy(),
    sleep_fn: Callable[[float], None] = __import__("time").sleep,
    rng: Callable[[], float] = __import__("random").random,
    now_fn: Callable[[], float] = __import__("time").monotonic,
):
    """
    Enforces:
      - 429 retries ONLY if Retry-After present+valid
      - Retry-After is a FLOOR (never retry earlier)
      - transient 5xx allowed with budgeted backoff
      - hard stop on attempts + elapsed
    do_request() returns: (status_code, headers_dict, payload)
    """
    start = float(now_fn())
    attempt = 0  # number of retries already performed

    while True:
        status, headers, payload = do_request()

        # tolerate common header casing
        ra_raw = None
        for k in ("Retry-After", "retry-after", "RETRY-AFTER"):
            if k in headers:
                ra_raw = headers.get(k)
                break
        ra_s = parse_retry_after(ra_raw)

        elapsed = float(now_fn()) - start
        next_attempt = attempt + 1  # compute_sleep uses 1-based attempt count

        if not should_retry(
            status_code=int(status),
            retry_after_s=ra_s,
            attempt=next_attempt,
            elapsed_s=elapsed,
            policy=policy,
        ):
            return status, headers, payload

        sleep_s = compute_sleep_s(
            attempt=next_attempt,
            retry_after_s=ra_s,
            policy=policy,
            rng=rng,
        )
        sleep_fn(float(sleep_s))
        attempt += 1
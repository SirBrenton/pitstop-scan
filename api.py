"""
POST /classify — V1.1-compatible response shape

One route. One hazard class: rate_limit_429.
No auth. No billing. No dashboard.
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

app = FastAPI()


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    v = value.strip()
    try:
        secs = float(v)
        return secs if secs >= 0 else None
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        return delta if delta >= 0 else 0.0
    except Exception:
        return None


def infer_scope(req: "ClassifyRequest") -> str:
    if req.provider:
        return "provider"
    return "request"


class ClassifyRequest(BaseModel):
    status: int
    headers: dict = {}
    provider: Optional[str] = None
    context: Optional[dict] = None


class Classification(BaseModel):
    decision: str
    confidence: float
    reason_code: str
    retry_after_ms: Optional[int] = None
    scope: str


class LegacyClassification(BaseModel):
    classification: str
    confidence: float
    reason: str
    action: str
    first_knob: str


class ClassifyResponse(BaseModel):
    classification: Classification
    legacy: LegacyClassification
    corpus_reference: Optional[str] = None


def build_response(
    *,
    decision: str,
    confidence: float,
    reason_code: str,
    action: str,
    first_knob: str,
    corpus_reference: Optional[str],
    retry_after_ms: Optional[int],
    scope: str,
) -> ClassifyResponse:
    return ClassifyResponse(
        classification=Classification(
            decision=decision,
            confidence=confidence,
            reason_code=reason_code,
            retry_after_ms=retry_after_ms,
            scope=scope,
        ),
        legacy=LegacyClassification(
            classification=decision,
            confidence=confidence,
            reason=reason_code,
            action=action,
            first_knob=first_knob,
        ),
        corpus_reference=corpus_reference,
    )


@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest):
    ra_raw = (
        req.headers.get("retry-after")
        or req.headers.get("Retry-After")
        or req.headers.get("x-ratelimit-reset-after")
        or None
    )
    ra_s = parse_retry_after(ra_raw)
    retry_after_ms = int(ra_s * 1000) if ra_s is not None else None
    scope = infer_scope(req)

    if req.status != 429:
        return build_response(
            decision="STOP",
            confidence=0.95,
            reason_code="non_429_status",
            action="do_not_retry",
            first_knob="error_handler",
            retry_after_ms=None,
            scope=scope,
            corpus_reference=None,
        )

    if ra_s is not None and ra_s > 60:
        return build_response(
            decision="STOP",
            confidence=0.91,
            reason_code="quota_exhaustion_retry_after_exceeds_60s",
            action="do_not_retry_wait_for_quota_reset",
            first_knob="retry_budget",
            retry_after_ms=retry_after_ms,
            scope=scope,
            corpus_reference="PT-2026-03-21-github-vercel-ai-sdk-429-retry-after-gap",
        )

    if ra_s is not None and ra_s <= 60:
        return build_response(
            decision="WAIT",
            confidence=0.92,
            reason_code="retry_after_present",
            action="wait_retry_after_ms_then_retry",
            first_knob="retry_after_ms",
            retry_after_ms=retry_after_ms,
            scope=scope,
            corpus_reference="PT-2026-03-21-github-openclaw-venice-models-429-retry-after-unwired",
        )

    return build_response(
        decision="CAP",
        confidence=0.74,
        reason_code="no_retry_after_likely_concurrency_cap",
        action="reduce_concurrent_workers_do_not_retry_immediately",
        first_knob="concurrency_cap",
        retry_after_ms=None,
        scope=scope,
        corpus_reference="PT-2026-03-21-github-continue-dev-429-cap-wait-missing",
    )


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.1"}
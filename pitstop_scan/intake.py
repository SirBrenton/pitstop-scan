from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scan import run_scan


def read_raw_input(in_path: Path) -> str:
    if not in_path.exists():
        raise FileNotFoundError(f"missing input file: {in_path}")
    return in_path.read_text(encoding="utf-8", errors="replace")


def scrub_raw_blob(blob: str) -> str:
    """
    Conservative raw-text scrubber for v1 intake.

    Goals:
    - remove obvious auth secrets
    - strip query strings from URLs
    - redact email-like strings
    - keep enough context for classification
    """
    out = blob

    # Authorization / bearer-like tokens
    out = re.sub(
        r"(?im)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._\-]+",
        r"\1[REDACTED]",
        out,
    )
    out = re.sub(
        r"(?im)\b(api[_-]?key|token|access[_-]?token|refresh[_-]?token)\b\s*[:=]\s*[^\s\"',;]+",
        r"\1=[REDACTED]",
        out,
    )

    # Strip query strings from URLs
    out = re.sub(
        r"(https?://[^\s?\"'>]+)\?[^ \n\"'>]*",
        r"\1?[REDACTED]",
        out,
    )

    # Redact email-like strings
    out = re.sub(
        r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b",
        "[REDACTED_EMAIL]",
        out,
        flags=re.IGNORECASE,
    )

    # Redact obvious long secret-like strings (conservative)
    out = re.sub(
        r"\b(sk-[A-Za-z0-9]{12,}|AIza[0-9A-Za-z\-_]{20,}|ghp_[A-Za-z0-9]{20,})\b",
        "[REDACTED_SECRET]",
        out,
    )

    return out


def extract_signals(blob: str) -> dict[str, Any]:
    blob_lower = blob.lower()

    http_status: int | None = None
    retry_after_ms: int | None = None
    provider: str | None = None
    model: str | None = None
    error_class = "unknown"
    decision_action = "none"

    # HTTP status detection
    status_match = re.search(r"\b(429|500|501|502|503|504|401|403|402)\b", blob)
    if status_match:
        http_status = int(status_match.group(1))

    # Retry-After header in seconds
    retry_match = re.search(r"(?im)retry-after[:\s]+(\d+)", blob_lower)
    if retry_match:
        retry_after_ms = int(retry_match.group(1)) * 1000

    # retry-after-ms already materialized in logs
    retry_ms_match = re.search(r"(?im)retry-after-ms[:=\s]+(\d+)", blob_lower)
    if retry_ms_match:
        retry_after_ms = int(retry_ms_match.group(1))

    # provider hints
    provider_patterns = {
        "anthropic": r"\banthropic\b",
        "openai": r"\bopenai\b",
        "vertexai": r"\bvertex\s*ai\b|\bvertexai\b",
        "gemini": r"\bgemini\b",
        "google": r"\bgoogle\b",
        "azure": r"\bazure\b",
        "vercel": r"\bvercel\b",
    }
    for name, pattern in provider_patterns.items():
        if re.search(pattern, blob_lower):
            provider = name
            break

    # model hint
    model_match = re.search(r'(?i)\bmodel\b["\']?\s*[:=]\s*["\']?([A-Za-z0-9._/\-]+)', blob)
    if model_match:
        model = model_match.group(1)

    # Classification rules (v1: intentionally simple)
    if http_status == 429:
        error_class = "rate_limit_429"
        if retry_after_ms is not None and retry_after_ms >= 5 * 60 * 1000:
            decision_action = "stop"
        else:
            decision_action = "retry"
    elif "timeout" in blob_lower or "deadline exceeded" in blob_lower:
        error_class = "timeout_deadline"
        decision_action = "retry"
    elif http_status in (401, 403):
        error_class = "auth"
        decision_action = "stop"
    elif http_status == 402:
        error_class = "billing"
        decision_action = "stop"
    elif http_status and 500 <= http_status < 600:
        error_class = "server_error"
        decision_action = "retry"

    return {
        "http_status": http_status,
        "retry_after_ms": retry_after_ms,
        "provider": provider,
        "model": model,
        "error_class": error_class,
        "decision_action": decision_action,
    }


def synthesize_artifact(extracted: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_version": "intake.v1",
        "source_kind": "raw_blob",
        "summary": {
            "http_status": extracted.get("http_status"),
            "retry_after_ms": extracted.get("retry_after_ms"),
            "provider": extracted.get("provider"),
            "model": extracted.get("model"),
            "error_class": extracted.get("error_class"),
            "decision_action": extracted.get("decision_action"),
        },
        "notes": {
            "derived_from_raw_blob": True,
            "scrubbed_for_sharing": True,
            "raw_blob_included": False,
        },
    }


def map_decision_action_for_scan(extracted: dict[str, Any]) -> str:
    """
    Map intake-level decision semantics onto the current scan schema enum.

    Intake semantics:
      - retry
      - stop

    Scan schema currently allows:
      - allow
      - allow_shadow
      - retry
      - fallback
      - cooldown
      - block
    """
    decision_action = extracted.get("decision_action")
    error_class = extracted.get("error_class")

    if decision_action == "retry":
        return "retry"

    if decision_action == "stop":
        if error_class == "rate_limit_429":
            return "cooldown"
        if error_class in {"auth", "billing"}:
            return "block"
        return "block"

    return "block"


def synthesize_receipt(extracted: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    scan_action = map_decision_action_for_scan(extracted)

    return {
        "schema_version": "decision_event.v1",
        "receipt_id": str(uuid.uuid4()),
        "ts_utc": now,
        "execution_id": str(uuid.uuid4()),
        "attempt_id": 1,
        "tool_id": extracted.get("provider") or "unknown",
        "operation": "unknown",
        "endpoint_norm": "unknown",
        "budget": {
            "deadline_ms": 5000,
            "max_elapsed_ms": 5000,
            "retry_budget": 0,
        },
        "outcome": {
            "status": "fail",
            "error_class": extracted.get("error_class"),
            "http_status": extracted.get("http_status"),
            "retry_after_ms": extracted.get("retry_after_ms"),
        },
        "cost": {
            "latency_ms": 0,
        },
        "decision": {
            "action": scan_action,
            "reason_code": "auto_classified_from_blob",
            "mode": "shadow",
        },
    }


def render_summary(extracted: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Intake Summary")
    lines.append("")
    lines.append("## Boundary Classification")
    lines.append("")
    lines.append(f"- HTTP Status: {extracted.get('http_status')}")
    lines.append(f"- Class: {extracted.get('error_class')}")
    lines.append(f"- Decision: {str(extracted.get('decision_action')).upper()}")
    if extracted.get("retry_after_ms") is not None:
        lines.append(f"- Retry-After: {extracted.get('retry_after_ms')} ms")
    if extracted.get("provider"):
        lines.append(f"- Provider: {extracted.get('provider')}")
    if extracted.get("model"):
        lines.append(f"- Model: {extracted.get('model')}")
    lines.append("")

    error_class = extracted.get("error_class")

    if error_class == "rate_limit_429":
        decision_action = extracted.get("decision_action")

        if decision_action == "stop":
            lines.append("## Likely Boundary")
            lines.append("")
            lines.append("Sustained rate limit / long-window exhaustion.")
            lines.append("")
            lines.append("## First Knob To Check")
            lines.append("")
            lines.append("Failover, reroute, or termination behavior for long-window Retry-After.")
            lines.append("")
            lines.append("## Risk")
            lines.append("")
            lines.append("Retrying inside the current execution window is unlikely to recover and can waste budget or delay fallback.")
        else:
            lines.append("## Likely Boundary")
            lines.append("")
            lines.append("Burst throttling / concurrency cap / provider limit.")
            lines.append("")
            lines.append("## First Knob To Check")
            lines.append("")
            lines.append("Shared throttle coordination + respect Retry-After.")
            lines.append("")
            lines.append("## Risk")
            lines.append("")
            lines.append("Uncoordinated retries can amplify 429 storms.")

    elif error_class == "timeout_deadline":
        lines.append("## Likely Boundary")
        lines.append("")
        lines.append("Outer deadline aborting retry/backoff window.")
        lines.append("")
        lines.append("## First Knob To Check")
        lines.append("")
        lines.append("Per-attempt deadline vs max_elapsed alignment.")
        lines.append("")
        lines.append("## Risk")
        lines.append("")
        lines.append("Timeouts can be misread as recoverable pressure and trigger wasteful retries or premature fallback.")

    elif error_class == "auth":
        lines.append("## Likely Boundary")
        lines.append("")
        lines.append("Credential / permission boundary.")
        lines.append("")
        lines.append("## First Knob To Check")
        lines.append("")
        lines.append("Token scope + environment mismatch.")
        lines.append("")
        lines.append("## Risk")
        lines.append("")
        lines.append("Retries will not recover invalid credentials or insufficient permissions.")

    elif error_class == "billing":
        lines.append("## Likely Boundary")
        lines.append("")
        lines.append("Quota / billing boundary.")
        lines.append("")
        lines.append("## First Knob To Check")
        lines.append("")
        lines.append("Plan limits, credit state, or billing gate.")
        lines.append("")
        lines.append("## Risk")
        lines.append("")
        lines.append("Retrying against a billing boundary can waste time and mask the real corrective action.")

    elif error_class == "server_error":
        lines.append("## Likely Boundary")
        lines.append("")
        lines.append("Provider-side transient server failure.")
        lines.append("")
        lines.append("## First Knob To Check")
        lines.append("")
        lines.append("Retry caps, max elapsed bounds, and fallback behavior.")
        lines.append("")
        lines.append("## Risk")
        lines.append("")
        lines.append("Unbounded retries can turn transient provider errors into long-tail latency and budget waste.")

    lines.append("")
    return "\n".join(lines)


def write_pack(
    out_dir: Path,
    raw_scrubbed: str,
    artifact: dict[str, Any],
    receipt: dict[str, Any],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path = out_dir / "raw_scrubbed.txt"
    artifact_path = out_dir / "artifact.json"
    exhaust_path = out_dir / "exhaust.jsonl"
    summary_path = out_dir / "summary.md"

    raw_path.write_text(raw_scrubbed, encoding="utf-8")
    artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    exhaust_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    summary_path.write_text(render_summary(artifact["summary"]), encoding="utf-8")

    return exhaust_path


def run_intake(in_path: Path, out_dir: Path, run_scan_after: bool = False) -> int:
    raw_blob = read_raw_input(in_path)
    raw_scrubbed = scrub_raw_blob(raw_blob)
    extracted = extract_signals(raw_scrubbed)
    artifact = synthesize_artifact(extracted)
    receipt = synthesize_receipt(extracted)

    exhaust_path = write_pack(out_dir, raw_scrubbed, artifact, receipt)

    print(f"[intake] Wrote pack to {out_dir}")
    print(f"[intake]   - {out_dir / 'raw_scrubbed.txt'}")
    print(f"[intake]   - {out_dir / 'artifact.json'}")
    print(f"[intake]   - {out_dir / 'exhaust.jsonl'}")
    print(f"[intake]   - {out_dir / 'summary.md'}")

    if run_scan_after:
        derived_dir = out_dir / "derived"
        derived_dir.mkdir(parents=True, exist_ok=True)
        print(f"[intake] Running scan into {derived_dir} ...")
        run_scan(in_path=exhaust_path, out_dir=derived_dir)

    return 0
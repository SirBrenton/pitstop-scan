#!/usr/bin/env python3
"""
Canon SVIX-2200 demo receipts into Pitstop decision_event.v1 so Scan can run.

Input:  input/svix_2200.raw.jsonl   (your synthetic lines, any shape)
Output: input/exhaust.jsonl         (decision_event.v1 canonical)
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, Optional


INP = Path("input/svix_2200.raw.jsonl")
OUT = Path("input/exhaust.jsonl")

# Deterministic-ish timeline for proof packs (keeps retry-after math stable)
BASE_TS = dt.datetime(2026, 3, 3, 14, 0, 0, tzinfo=dt.timezone.utc)


def iso_z(ts: dt.datetime) -> str:
    return ts.isoformat().replace("+00:00", "Z")


def mk_receipt_id(obj: Dict[str, Any]) -> str:
    base = {
        "execution_id": obj.get("execution_id"),
        "attempt_id": obj.get("attempt_id"),
        "tool_id": obj.get("tool_id"),
        "operation": obj.get("operation"),
        "endpoint_norm": obj.get("endpoint_norm"),
        "status": (obj.get("outcome") or {}).get("status"),
        "http_status": (obj.get("outcome") or {}).get("http_status"),
        "error_class": (obj.get("outcome") or {}).get("error_class"),
    }
    s = json.dumps(base, sort_keys=True, separators=(",", ":"))
    return "r_" + hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def parse_retry_after_ms(src: Dict[str, Any]) -> Optional[int]:
    # Expect header in src["receipt"]["headers"]["retry-after"]
    receipt = src.get("receipt") or {}
    headers = (receipt.get("headers") or {}) if isinstance(receipt, dict) else {}
    ra = headers.get("retry-after") or headers.get("Retry-After")
    if not ra:
        return None

    # For this proof canonicalizer: support delta-seconds (int/float) only.
    # (HTTP-date parsing is doable, but you already normalized dates to seconds in your demo.)
    try:
        seconds_f = float(str(ra).strip())
        seconds = int(math.ceil(seconds_f))
        return max(0, seconds * 1000)
    except Exception:
        return None


def canon_error_class(status: str, http_status: Optional[int], raw_error_class: Optional[str]) -> Optional[str]:
    if status != "fail":
        return None

    # Map raw -> contract enums
    if http_status == 429:
        return "rate_limit_429"
    if http_status is not None and 500 <= http_status <= 599:
        return "server_5xx"
    # allow raw "timeout" marker
    if (raw_error_class or "").lower() in {"timeout", "deadline", "context_deadline"}:
        return "timeout_deadline"

    return "unknown"


def canon_decision(src_action: str) -> tuple[str, str, str]:
    """
    decision.action must be one of:
      allow, allow_shadow, retry, fallback, cooldown, block
    """
    a = (src_action or "").lower().strip()

    if a in {"ok", "allow"}:
        return ("allow", "ok", "enforce")
    if a in {"retry"}:
        return ("retry", "retryable_failure", "enforce")
    if a in {"stop", "block"}:
        return ("block", "attempt_budget_exhausted", "enforce")

    # default conservative
    return ("retry", "unknown_action_mapped_to_retry", "enforce")


def main() -> None:
    if not INP.exists():
        raise SystemExit(f"Missing input: {INP} (create it by copying your synthetic jsonl there)")

    OUT.parent.mkdir(parents=True, exist_ok=True)

    i = 0
    with INP.open("r", encoding="utf-8") as f, OUT.open("w", encoding="utf-8") as g:
        for line in f:
            line = line.strip()
            if not line:
                continue
            src = json.loads(line)

            # Pull target fields up to top-level (schema requires these top-level)
            tgt = src.get("target") or {}
            tool_id = src.get("tool_id") or tgt.get("tool_id") or "unknown-tool"
            operation = src.get("operation") or tgt.get("operation") or "unknown-op"
            endpoint_norm = src.get("endpoint_norm") or tgt.get("endpoint_norm") or "unknown-endpoint"

            # attempt_id must be integer >= 1
            try:
                attempt_id = int(src.get("attempt_id"))
            except Exception:
                attempt_id = i + 1

            outcome = src.get("outcome") or {}
            status = outcome.get("status") or "fail"
            http_status = outcome.get("http_status")
            if http_status is not None:
                try:
                    http_status = int(http_status)
                except Exception:
                    http_status = None

            ra_ms = parse_retry_after_ms(src)

            # Decision mapping (must be schema-valid)
            src_dec = src.get("decision") or {}
            action, rcode, dmode = canon_decision(src_dec.get("action", ""))

            # Retry semantics for Scan: mark retry attempts
            attempt_kind = "primary" if attempt_id == 1 else "retry"
            prior_attempts = max(0, attempt_id - 1)

            # Budget must include max_elapsed_ms (schema-required)
            b = src.get("budget") or {}
            deadline_ms = int(b.get("deadline_ms", 30000))
            retry_budget = int(b.get("retry_budget", 0))
            max_elapsed_ms = int(b.get("max_elapsed_ms", 120000))

            # Backoff proof: if retry_after exists, show we floor backoff to it
            # (and you can later add jitter-under-cut examples)
            backoff_ms = None
            if action == "retry":
                # baseline backoff (example): 1s
                base_backoff_ms = 1000
                if ra_ms is not None:
                    backoff_ms = float(max(base_backoff_ms, ra_ms))
                else:
                    backoff_ms = float(base_backoff_ms)

            canon_err = canon_error_class(status=status, http_status=http_status, raw_error_class=outcome.get("error_class"))

            out: Dict[str, Any] = {
                "schema_version": "decision_event.v1",
                "receipt_id": "",  # filled after
                "ts_utc": iso_z(BASE_TS + dt.timedelta(seconds=i)),
                "execution_id": src.get("execution_id") or "svix-2200-demo",
                "attempt_id": attempt_id,
                "attempt": {"kind": attempt_kind, "prior_attempts": prior_attempts},

                "tool_id": str(tool_id),
                "operation": str(operation),
                "endpoint_norm": str(endpoint_norm),

                "budget": {
                    "deadline_ms": deadline_ms,
                    "max_elapsed_ms": max_elapsed_ms,
                    "retry_budget": retry_budget,
                    "token_budget": None,
                },

                # Optional policy block (schema-typed). Keep it valid.
                "policy": {
                    "mode": "enforce",
                    "fail_behavior": "fail_closed",
                    "concurrency_cap": None,
                    "cooldown": {"enabled": False},
                    "backoff": {
                        "strategy": "exponential",
                        "jitter": True,
                        "respect_retry_after": True,
                    },
                },

                "outcome": {
                    "status": status,
                    "error_class": canon_err,          # required when fail
                    "http_status": http_status,
                    "retry_after_ms": ra_ms,
                },

                "cost": {
                    "latency_ms": float((src.get("cost") or {}).get("latency_ms", 0.0)),
                    "backoff_ms": backoff_ms,
                    "tokens_est": None,
                },

                "decision": {
                    "action": action,
                    "reason_code": rcode,
                    "mode": dmode,
                },

                # Keep raw evidence (allowed by additionalProperties:true)
                "receipt": src.get("receipt"),
            }

            out["receipt_id"] = mk_receipt_id(out)
            g.write(json.dumps(out, separators=(",", ":")) + "\n")
            i += 1

    print(f"wrote {OUT} events={i}")


if __name__ == "__main__":
    main()
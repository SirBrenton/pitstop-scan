from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _ts_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _event(
    *,
    receipt_id: str,
    tool_id: str,
    operation: str,
    status: str,
    latency_ms: int,
    deadline_ms: int,
    error_class: str | None = None,
    http_status: int | None = None,
    retry_after_ms: int | None = None,
    backoff_ms: int = 0,
    tokens_est: int = 0,
    action: str = "allow",
    reason_code: str = "demo",
    mode: str = "shadow",
    attempt_id: int = 1,
    execution_id: str = "demo-exec-0001",
) -> Dict[str, Any]:
    return {
        "schema_version": "decision_event.v1",
        "receipt_id": receipt_id,
        "ts_utc": _ts_utc(),
        "execution_id": execution_id,
        "attempt_id": attempt_id,
        "tool_id": tool_id,
        "operation": operation,
        "endpoint_norm": tool_id,
        "context_signature": {
            "env_bucket": "prod",
            "region_bucket": "us",
            "concurrency_bucket": "1-5",
            "tenant_tier": "standard",
        },
        "budget": {
            "deadline_ms": int(deadline_ms),
            "max_elapsed_ms": int(deadline_ms),
            "retry_budget": 1,
            "token_budget": None,
        },
        "outcome": {
            "status": status,
            "error_class": error_class,
            "http_status": http_status,
            "retry_after_ms": retry_after_ms,
        },
        "cost": {
            "latency_ms": int(latency_ms),
            "backoff_ms": int(backoff_ms),
            "tokens_est": int(tokens_est),
        },
        "decision": {
            "action": action,
            "reason_code": reason_code,
            "mode": mode,
        },
    }


def write_demo_exhaust(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    deadline_ms = 900

    demo_events: List[Dict[str, Any]] = [
        # breach-dominant signature: ok but late (latency > deadline)
        _event(
            receipt_id="demo-0001",
            tool_id="github/search_issues",
            operation="search_issues",
            status="ok",
            latency_ms=920,
            deadline_ms=deadline_ms,
            http_status=200,
        ),
        # hard failure: timeout
        _event(
            receipt_id="demo-0002",
            tool_id="github/search_issues",
            operation="search_issues",
            status="fail",
            error_class="timeout_deadline",
            http_status=504,
            latency_ms=5000,
            deadline_ms=deadline_ms,
        ),
        # hard failure: rate limit 429 (+ retry_after)
        _event(
            receipt_id="demo-0003",
            tool_id="github/search_issues",
            operation="search_issues",
            status="fail",
            error_class="rate_limit_429",
            http_status=429,
            retry_after_ms=2000,
            latency_ms=1840,
            deadline_ms=deadline_ms,
        ),
        # non-retriable auth failure
        _event(
            receipt_id="demo-0004",
            tool_id="github/create_issue",
            operation="create_issue",
            status="fail", 
            error_class="auth_401",
            http_status=401,
            latency_ms=400,
            deadline_ms=deadline_ms,
        ),
        # ok fast
        _event(
            receipt_id="demo-0005",
            tool_id="github/create_issue",
            operation="create_issue",
            status="ok",
            http_status=201,
            latency_ms=650,
            deadline_ms=deadline_ms,
        ),
    ]

    with path.open("w", encoding="utf-8") as f:
        for e in demo_events:
            # compact + stable JSONL
            f.write(json.dumps(e, separators=(",", ":")) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Write a demo decision_event.v1 JSONL file (synthetic).")
    ap.add_argument(
        "--out",
        default="input/exhaust.jsonl",
        help="Output path for demo JSONL (default: input/exhaust.jsonl)",
    )
    args = ap.parse_args()

    out_path = Path(args.out)
    write_demo_exhaust(out_path)
    print(f"OK: wrote demo exhaust -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
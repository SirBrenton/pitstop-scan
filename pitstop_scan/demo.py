from __future__ import annotations

import argparse
import json
from pathlib import Path


def write_demo_exhaust(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    demo_events = [
        # breach-dominant signature: ok but late
        {
            "tool": "github",
            "op": "search_issues",
            "env": "prod",
            "region": "us",
            "concurrency_bucket": "1-5",
            "tier": "standard",
            "status": "ok",
            "error_class": None,
            "latency_ms": 920,
            "retries": 0,
            "budget_ms": 900,
        },
        # hard failures
        {
            "tool": "github",
            "op": "search_issues",
            "env": "prod",
            "region": "us",
            "concurrency_bucket": "1-5",
            "tier": "standard",
            "status": "error",
            "error_class": "timeout",
            "latency_ms": 5000,
            "retries": 1,
            "budget_ms": 900,
        },
        {
            "tool": "github",
            "op": "search_issues",
            "env": "prod",
            "region": "us",
            "concurrency_bucket": "1-5",
            "tier": "standard",
            "status": "error",
            "error_class": "rate_limit_429",
            "latency_ms": 1840,
            "retries": 2,
            "budget_ms": 900,
        },
        # non-retriable auth
        {
            "tool": "github",
            "op": "create_issue",
            "env": "prod",
            "region": "us",
            "concurrency_bucket": "1-5",
            "tier": "standard",
            "status": "error",
            "error_class": "auth_401",
            "latency_ms": 400,
            "retries": 0,
            "budget_ms": 900,
        },
        # ok fast
        {
            "tool": "github",
            "op": "create_issue",
            "env": "prod",
            "region": "us",
            "concurrency_bucket": "1-5",
            "tier": "standard",
            "status": "ok",
            "error_class": None,
            "latency_ms": 650,
            "retries": 0,
            "budget_ms": 900,
        },
    ]

    with path.open("w", encoding="utf-8") as f:
        for e in demo_events:
            f.write(json.dumps(e) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Write a demo exhaust.jsonl file (synthetic).")
    ap.add_argument(
        "--out",
        default="input/exhaust.jsonl",
        help="Output path for JSONL demo exhaust (default: input/exhaust.jsonl)",
    )
    args = ap.parse_args()

    out_path = Path(args.out)
    write_demo_exhaust(out_path)
    print(f"OK: wrote demo exhaust -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
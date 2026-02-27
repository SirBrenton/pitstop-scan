"""
INGEST V0 — SALES ACCELERATOR

Purpose:
Convert messy error blobs into minimal scan-compatible receipts.

Non-goals:
- Full log parsing
- Provider abstraction
- Perfect classification
- Streaming support
- Schema expansion

If this file exceeds ~300 lines, we have drifted.
"""

import sys
import re
import json
import uuid
from datetime import datetime
from pathlib import Path
import subprocess


OUTPUT_INPUT_PATH = Path("input/exhaust.jsonl")


def print_micro_autopsy(blob: str):
    c = classify(blob)

    print("\n" + "─" * 48)
    print("Boundary Classification")
    print("─" * 48)

    print(f"HTTP Status: {c['http_status']}")
    print(f"Class: {c['error_class']}")
    print(f"Decision: {c['decision_action'].upper()}")

    if c["retry_after_ms"]:
        print(f"Retry-After: {c['retry_after_ms']} ms")

    if c["error_class"] == "rate_limit_429":
        print("\nLikely Boundary:")
        print("Burst throttling / concurrency cap.")
        print("\nFirst Knob To Check:")
        print("Shared throttle coordination + respect Retry-After.")
        print("\nRisk:")
        print("Uncoordinated retries can amplify 429 storms.")

    elif c["error_class"] == "timeout_deadline":
        print("\nLikely Boundary:")
        print("Outer deadline aborting retry/backoff window.")
        print("\nFirst Knob To Check:")
        print("Per-attempt deadline vs max_elapsed alignment.")

    elif c["error_class"] == "auth":
        print("\nLikely Boundary:")
        print("Credential / permission boundary.")
        print("\nFirst Knob To Check:")
        print("Token scope + environment mismatch.")

    print("─" * 48 + "\n")

# ----------------------------
# Classification
# ----------------------------

def classify(blob: str):
    blob_lower = blob.lower()

    http_status = None
    retry_after_ms = None
    error_class = "unknown"
    decision_action = "none"

    # HTTP status detection
    status_match = re.search(r"\b(429|500|401|403|402)\b", blob)
    if status_match:
        http_status = int(status_match.group(1))

    # Retry-After header detection
    retry_match = re.search(r"retry-after[:\s]+(\d+)", blob_lower)
    if retry_match:
        retry_after_ms = int(retry_match.group(1)) * 1000

    # Classification rules
    if http_status == 429:
        error_class = "rate_limit_429"
        decision_action = "retry"
    elif "timeout" in blob_lower:
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
        "error_class": error_class,
        "decision_action": decision_action,
    }


# ----------------------------
# Receipt synthesis
# ----------------------------

def synthesize_receipt(blob: str):
    c = classify(blob)

    from datetime import timezone
    now = datetime.now(timezone.utc).isoformat()

    return {
        "schema_version": "decision_event.v1",
        "receipt_id": str(uuid.uuid4()),
        "ts_utc": now,
        "execution_id": str(uuid.uuid4()),
        "attempt_id": 1,
        "tool_id": "unknown",
        "operation": "unknown",
        "endpoint_norm": "unknown",
        "budget": {
            "deadline_ms": 5000,
            "max_elapsed_ms": 5000,
            "retry_budget": 0
        },
        "outcome": {
            "status": "fail",
            "error_class": c["error_class"],
            "http_status": c["http_status"],
            "retry_after_ms": c["retry_after_ms"]
        },
        "cost": {
            "latency_ms": 0
        },
        "decision": {
            "action": c["decision_action"],
            "reason_code": "auto_classified",
            "mode": "shadow"
        }
    }


# ----------------------------
# Scan execution
# ----------------------------

def run_scan():
    print("[ingest] Running scan...")
    try:
        subprocess.run(["make", "run"], check=True)
    except subprocess.CalledProcessError:
        print("[ingest] Scan failed.")
        sys.exit(1)


# ----------------------------
# Input handling
# ----------------------------

def read_blob(path_arg: str) -> str:
    if path_arg == "-":
        return sys.stdin.read()

    p = Path(path_arg)
    if not p.exists():
        print(f"[ingest] File not found: {path_arg}")
        sys.exit(1)

    return p.read_text()


# ----------------------------
# CLI entry
# ----------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: pitstop ingest <file_path | ->")
        sys.exit(1)

    blob = read_blob(sys.argv[1])

    print_micro_autopsy(blob)

    receipt = synthesize_receipt(blob)

    OUTPUT_INPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_INPUT_PATH.write_text(json.dumps(receipt) + "\n")

    print("[ingest] Wrote input/exhaust.jsonl")

    run_scan()

if __name__ == "__main__":
    main()
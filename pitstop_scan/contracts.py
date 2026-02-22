from __future__ import annotations

from typing import Any, Dict


REQUIRED = ["tool", "op", "status", "latency_ms", "retries"]


def validate_event(e: Dict[str, Any], line_no: int) -> None:
    missing = [k for k in REQUIRED if k not in e]
    if missing:
        raise ValueError(f"Line {line_no}: missing required keys: {missing}")

    # basic types / sanity
    if e["status"] not in ("ok", "error"):
        raise ValueError(f"Line {line_no}: status must be 'ok' or 'error'")

    try:
        float(e["latency_ms"])
    except Exception as ex:
        raise ValueError(f"Line {line_no}: latency_ms must be numeric") from ex

    try:
        int(e["retries"])
    except Exception as ex:
        raise ValueError(f"Line {line_no}: retries must be int-like") from ex
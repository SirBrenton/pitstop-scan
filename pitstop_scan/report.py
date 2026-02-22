from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def render_report(in_path: Path, summary: Dict[str, Any]) -> str:
    events = summary["events"]
    ok = summary["ok"]
    fail = summary["fail"]

    lat = summary["latency_ms"]
    ok_rate = summary["ok_rate"]
    breach_rate = summary["breach_rate"]

    regime = "breach-dominant" if breach_rate >= 0.5 else "failure-dominant"
    return f"""# Pitstop Scan — Reliability Snapshot (v0)

**Input:** {in_path}
**Result:** **{regime}** in this sample — most pain is latency exceeding budget (even when calls succeed), not hard failures.

## Summary stats
- events: **{events}** (ok={ok}, fail={fail})
- ok_rate: **{pct(ok_rate)}**
- breach_rate (latency > budget, when budget_ms present): **{pct(breach_rate)}**
- retries_mean: **{summary["retries_mean"]:.3f}**
- latency_ms: mean={lat["mean"]:.1f} p50={lat["p50"]:.1f} p95={lat["p95"]:.1f} p99={lat["p99"]:.1f}

## What to do next (10 minutes)
1) Enforce a hard deadline at ~budget_ms + fallback (partial/cached/degraded output).
2) Cap retries (e.g., 2) + 429 backoff+jitter (don’t brute-force retries).
3) Treat 401 as non-retriable → refresh creds / escalate immediately.

> Note: this scan repo is an MVP shell. The full hazard ranking and signature analysis is delegated to the private engine (pitstop-commons) in the next step.
"""
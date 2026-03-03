# Pitstop Scan — Reliability Snapshot (v0)

**Input:** input/exhaust.jsonl
**Result:** **failure-dominant** in this sample — most pain is latency exceeding budget (even when calls succeed), not hard failures.

**Outcome:** Start with the top **1** hazards below — they’re the highest-leverage fixes in this sample.

## Summary stats
- events: **10** (ok=2, fail=8)
- ok_rate: **20.00%**
- budgeted_events: **10**
- breach_rate (latency > budget, budgeted events only): **10.00%**
- retries_mean: **0.000**
- latency_ms: mean=3123.0 p50=130.0 p95=16608.5 p99=27361.7

## Top hazards (ranked)

> A “hazard” is a signature where failures and/or budget breaches concentrate (highest leverage fixes first).

- **#1** `svix-webhooks/deliver env=na region=na conc=na tier=na` — n=10, fail=8, breach=1 (10.00%), p95=16608ms, retries_mean=0.00, top_error=`rate_limit_429`
  - Do: cap retries + 429 backoff/jitter (don’t brute-force).

(See `hazards.csv` for the full ranked list, and `signatures.csv` for rollups.)

## Default guardrails (baseline)

Apply these everywhere, then implement the hazard-specific “Do:” actions above in order:

- **Deadlines:** budget-aligned hard deadline + fallback (don’t block indefinitely).
- **Retry policy:** cap retries; **429 backoff + jitter**; don’t brute-force.
- **Never-retry:** auth failures (401/403) and other non-retriables → refresh/escalate.

## Share safely (derived outputs only)

If you want help, send the **Pitstop Pack** (derived aggregates):

- `output/pitstop_pack_agg.zip` (recommended)
- or: `output/report.md`, `output/hazards.csv`, `output/signatures.csv`, `output/summary.json`

## Optional: 48-hour Patch Plan (human)

Email the pack to:
[brentondwilliams@gmail.com](mailto:brentondwilliams@gmail.com?subject=Pitstop%20Scan%20Patch%20Plan)

Include:
- Context: [stack]
- Scope: [workflow / service name]
- Goal: [reduce 429s | reduce p99 | fix failover | etc.]

**You get:** a 1-page fix order + copy/paste guardrails mapped to your top hazards.

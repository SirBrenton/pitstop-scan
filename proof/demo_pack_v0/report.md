# Pitstop Scan — Reliability Snapshot (v0)

**Input:** input/exhaust.jsonl
**Result:** **breach-dominant** in this sample — most pain is latency exceeding budget (even when calls succeed), not hard failures.

**Outcome:** Start with the top **2** hazards below — they’re the highest-leverage fixes in this sample.

## Summary stats
- events: **5** (ok=2, fail=3)
- ok_rate: **40.00%**
- budgeted_events: **5**
- breach_rate (latency > budget, budgeted events only): **60.00%**
- retries_mean: **0.000**
- latency_ms: mean=1762.0 p50=920.0 p95=4368.0 p99=4873.6

## Top hazards (ranked)

> A “hazard” is a signature where failures and/or budget breaches concentrate (highest leverage fixes first).

- **#1** `github/search_issues/search_issues env=prod region=us conc=1-5 tier=standard` — n=3, fail=2, breach=3 (100.00%), p95=4684ms, retries_mean=0.00, top_error=`timeout_deadline`
  - Do: enforce a hard per-attempt deadline (≈ budget.deadline_ms) + fallback.
- **#2** `github/create_issue/create_issue env=prod region=us conc=1-5 tier=standard` — n=2, fail=1, breach=0 (0.00%), p95=638ms, retries_mean=0.00, top_error=`auth_401`
  - Do: never retry auth failures → refresh creds / escalate.

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

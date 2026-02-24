# Pitstop Scan

Local-first reliability triage for AI tool/workflow calls.

**One-liner:** Run Pitstop Scan on your tool-call logs and it tells you **which calls are blowing retries / breaching latency budgets** — and **what to cap next** (timeouts, retries, 429 backoff, auth handling).

## Execution Contract (v1.0)

Pitstop Scan is powered by the **Pitstop Execution Contract**:

> `execute(intent, budget, policy) -> result + receipt`

This contract standardizes:
- budget semantics (deadlines, max elapsed, retry caps)
- classification taxonomy (429 vs 402 vs timeout vs auth)
- routing scope (model vs provider vs credential)
- audit-grade receipts for hazard ranking

Read the canonical spec here:

→ **[Execution Contract v1.0](./EXECUTION_CONTRACT.md)**

If you maintain AI agents, API gateways, or tool routers, this contract defines the correctness rules behind reliable execution.

## Why you’d run this
If you’ve ever said:
- “We don’t know which tool calls are killing latency.”
- “Retries are spiking / rate limits are killing us.”
- “It usually works… but the tail is brutal.”

Pitstop Scan turns that into a ranked list of **failure + breach signatures** you can actually fix.

## What this is (plain English)
You point Pitstop Scan at a JSONL “exhaust” file (**one tool-call event per line**).
It groups events by **tool + operation + coarse context** and surfaces what’s hurting most.

**It ends with concrete next steps:** deadline guidance, retry caps, 429 backoff+jitter, and **never-retry boundaries** (e.g., 401 / auth failures).

## What you get
Running the scan writes:

- `output/report.md` — 1-page summary: what’s hurting + what to do next
- `output/hazards.csv` — ranked hazards (what’s hurting + why)
- `output/signatures.csv` — per-signature rollups
- `output/summary.json` — machine totals (for automation)
- `output/pitstop_pack_agg.zip` — zip of the four derived outputs above

**Breach** = latency exceeds `budget_ms` **even if status is `ok`**.

## Privacy / safety (hard boundary)
- **Local-only by default.** No data leaves your machine.
- Input is **event metadata**, not prompts or payload bodies.
- **Must NOT be present:** prompts, request/response bodies, headers, tokens, customer content.
- Outputs are **derived summaries only** (no raw requests/responses).

## Quickstart (5 minutes)

### 1) Install (repo-local venv)
```bash
make deps
```

### 2) Drop your exhaust here

Place a JSONL file at:
- input/exhaust.jsonl

(One JSON object per line.)

### 3) Run
```bash
make run
```

### 4) Read the report
```bash
less output/report.md
# macOS convenience:
open output/report.md
```
### Don’t have exhaust yet?
Run a synthetic demo (creates a tiny sample input/exhaust.jsonl):
```bash
make demo
open output/report.md
```
If `make demo works`, you’re ready — replace `input/exhaust.jsonl` with your real file and rerun `make run`.

## Input contract (minimum viable)

Each JSONL line should include:
- tool, op
- coarse context buckets (e.g. env, region, concurrency_bucket, tier)
- outcome: status (ok/error) and/or error_class
- latency_ms
- retries
- budget_ms (recommended)

That’s it.

## Notes on “loss” and cost framing

The report may include a priced loss model to help rank fixes.
Treat it as tunable (knobs are shown). The primary truth signals are breach rate and tail latency (p95/p99).

## Optional: 48-hour Patch Plan (human + copy/paste guardrails)

If you want an exact enforcement plan (timeouts, retry caps, 429 backoff+jitter rules, and where to enforce them), send:

- `output/pitstop_pack_agg.zip` (or the four derived files)

**What you send:** report.md, hazards.csv, signatures.csv, summary.json (derived outputs only).

**What you do NOT send:** raw exhaust, prompts, payloads, headers, tokens.

**What you get back:** a 1-page Patch Plan with exact guardrails (deadlines, retry caps, 429 rules) mapped to your top signatures.
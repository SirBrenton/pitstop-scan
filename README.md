# Pitstop Scan

Local-first reliability triage for **AI + API execution**.

Given execution receipts, Scan produces a ranked hazard pack showing exactly where reliability is leaking:

- where latency breaches concentrate
- where failures concentrate (429s, timeouts, auth, 5xx)
- which guardrails to implement first

**Output:** a 1-page reliability snapshot + prioritized guardrail plan.

No dashboards. No calls. Just receipts → hazards → guardrails.

**Start here:** [`docs/START_HERE.md`](docs/START_HERE.md)

---

## Why you’d run this

If you’ve ever said:
- "We can’t tell (quickly) which call is killing tail latency.”
- “Retries are spiking / rate limits are killing us.”
- “It usually works… but the tail is brutal.”

Pitstop Scan turns that into a ranked list of **failure + breach signatures** you can actually fix.

---

## Quickstart (5 minutes)

### 1) Install (repo-local venv)
```bash
make deps
```
#### Option A — You already have receipts (JSONL)
Place your file at:
```bash
input/exhaust.jsonl
```

Then run:
```bash
make run
```
Open the report:
```bash
open output/report.md   # macOS
```
#### Option B — You only have raw error logs
If you don’t have receipts yet, paste raw logs into a file:
```bash
pitstop ingest blob.txt
```
This will:
- classify the failure boundary (WAIT vs STOP)
- normalize into decision_event.v1
- run Scan automatically
- generate a ranked hazard pack

Then open:
```bash
open output/report.md
```
### No data yet? Run a demo
Run a synthetic demo (creates a tiny input/exhaust.jsonl):
```bash
make demo
open output/report.md
```
If `make demo works`, you’re ready — replace `input/exhaust.jsonl` with your real file and rerun `make run`.

---

## What you get

Running the scan writes:

- `output/report.md` — 1-page reliability snapshot + top fixes
- `output/hazards.csv` — ranked hazards (highest leverage first)
- `output/signatures.csv` — per-signature rollups
- `output/summary.json` — machine totals (automation-friendly)
- `output/pitstop_pack_agg.zip` — zip of the four derived outputs above

**Breach** = latency exceeds the per-attempt deadline (`budget.deadline_ms`) **even if status is `ok`**.  
(If receipts use legacy `budget_ms`, Scan treats it as `budget.deadline_ms`.)

---

## Proof (sample hazard pack)

See a sample output pack (derived aggregates only):
- **[proof/demo_pack_v0/report.md](proof/demo_pack_v0/report.md)**
- [proof/demo_pack_v0/hazards.csv](proof/demo_pack_v0/hazards.csv)
- [proof/demo_pack_v0/signatures.csv](proof/demo_pack_v0/signatures.csv)
- [proof/demo_pack_v0/summary.json](proof/demo_pack_v0/summary.json)

---

## Receipts (drop-in invariants)

Small, runnable “truth artifacts”: invariant → policy → tests → verification.

- **[receipts/README.md](receipts/README.md)** — index of receipts you can paste into a codebase
- **[429-floor](receipts/429-floor/README.md)** — Retry-After is a floor (policy + tests)

These receipts are the guardrails the scan will often recommend.

---

## The Execution Contract (v1.0)

Pitstop Scan is a **reference implementation** of the Pitstop Execution Contract:

> `execute(intent, budget, policy) -> result, receipt`

The contract defines the correctness rules for reliable execution:
- **Budget semantics:** per-attempt deadlines, max elapsed, retry caps (attempts include fallbacks)
- **Classification taxonomy:** 429 vs 402 vs timeout vs auth (retryable vs terminal)
- **Scope correctness:** model vs provider vs credential (cooldown blast radius)
- **Audit-grade receipts:** emitted on every attempt (including block/cooldown/preemption)

Read the spec:

→ **[EXECUTION_CONTRACT.md](./EXECUTION_CONTRACT.md)**

---

## Input contract (minimum viable)

Each JSONL line should include (aligned to the Execution Contract):

**Required:**

- target: `tool_id`, `operation`, `endpoint_norm`
- outcome: `outcome.status` and (if fail) `outcome.error_class` (optionally `outcome.http_status`)
- timing: `cost.latency_ms`
- budget: `budget.deadline_ms` (or `legacy budget_ms`)
- attempt identity: `execution_id`, `attempt_id`

**Recommended (improves ranking + fix guidance):**

- `budget.max_elapsed_ms`
- `budget.retry_budget`
- `decision.action`

That’s enough to rank hazards and generate the pack.

## Notes on “loss” and cost framing

The report may include a priced loss model to help rank fixes.
Treat it as tunable. The primary truth signals are breach rate and tail latency (p95/p99).

---

## Privacy / safety (hard boundary)

- **Local-only by default.** No data leaves your machine.
- Input should be **operational receipts**, not payloads.

Receipts **MUST NOT** include:
- prompts, message content, tool payload bodies, response bodies
- headers, tokens, API keys, cookies
- raw URLs or query strings (use `endpoint_norm`)

Outputs are **derived summaries only** (no raw requests/responses).

---

## Want help applying the fix order?

If you'd like a second set of eyes on your hazard pack, send the **derived pack only**:

`output/pitstop_pack_agg.zip`

to **brentondwilliams@gmail.com** with:

- **Stack:** (e.g. Python + OpenAI + Redis)
- **Workflow:** (e.g. agent toolchain, ingestion pipeline)
- **Goal:** (reduce 429s | reduce p99 | stabilize retries | fix failover)

You’ll receive:

- a prioritized guardrail plan
- concrete configuration / policy changes
- a verification checklist to confirm the fix worked

No calls required. Just artifacts → fix order → verification.

---

## Before / after delta (optional)

If you can share **50–200 redacted receipts** (JSONL metadata only), I can re-run the scan after you ship the guardrails and return a **before/after delta**.

If you prefer to keep receipts local, the **derived pack alone** is enough to generate a fix order.

# Pitstop Scan

Local-first reliability triage for **AI + API execution**.

**True North:** We make AI + API execution predictable: **budgets, routing, enforcement, receipts**.

**Status:** Contract v1.0 shipped. Scan produces hazard packs from receipts.

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

**What Scan does:** given contract-compliant receipts, it outputs a ranked hazard pack — **what’s hurting most** and **what to cap next**.

---

## Why you’d run this

If you’ve ever said:
- “We usually can’t tell which call is killing tail latency.”
- “Retries are spiking / rate limits are killing us.”
- “It usually works… but the tail is brutal.”

Pitstop Scan turns that into a ranked list of **failure + breach signatures** you can actually fix.

---

## What this is (plain English)

You point Pitstop Scan at a JSONL “exhaust” file (**one receipt per line**).
It groups receipts by **tool + operation + normalized endpoint + coarse tags** and surfaces where:
- **latency breaches** concentrate (success can still be a breach), and/or
- **failures** concentrate (timeouts, 429s, auth, 5xx)

It ends with concrete guardrails to implement first:
- budget-aligned deadlines
- retry caps + max elapsed bounds
- 429 backoff (+ respect Retry-After)
- never-retry boundaries (401/403/402)

---

## What you get

Running the scan writes:

- `output/report.md` — 1-page reliability snapshot + top-2 fixes
- `output/hazards.csv` — ranked hazards (highest leverage first)
- `output/signatures.csv` — per-signature rollups
- `output/summary.json` — machine totals (automation-friendly)
- `output/pitstop_pack_agg.zip` — zip of the four derived outputs above

**Breach** = latency exceeds the per-attempt deadline (`budget.deadline_ms`) **even if status is `ok`**.  
(If receipts use legacy `budget_ms`, Scan treats it as `budget.deadline_ms`.)

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
### Don’t have receipts yet?
Run a synthetic demo (creates a tiny input/exhaust.jsonl):
```bash
make demo
open output/report.md
```
If `make demo works`, you’re ready — replace `input/exhaust.jsonl` with your real file and rerun `make run`.

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

## Share safely (derived outputs only)

If you want help (or you want to share safely), send **derived outputs only**:

- `output/report.md`
- `output/hazards.csv`
- `output/signatures.csv`
- `output/summary.json`
- or the bundle: `output/pitstop_pack_agg.zip`

These are aggregates (safe to share).

## 48-hour Patch Plan (human + copy/paste guardrails)

Send `output/pitstop_pack_agg.zip` (derived summaries) to:
brentondwilliams@gmail.com

Include:
- Context: [stack]
- Scope: [which workflows]
- Goal: [reduce 429s | reduce p99 | fix failover | etc.]

**You get:** a 1-page fix order + copy/paste guardrails mapped to your top hazards.

## Want a verified before/after delta? (Phase 2 loop)

If you want a measurable before/after, share **50–200 redacted execution receipts** (JSONL; metadata only). I can:

- run Scan and return an updated hazard pack
- map top-2 guardrails to your signatures
- after you ship, re-scan to show a before/after delta (breach rate / timeout rate / p95)

Reply with either:
- the derived pack (`output/pitstop_pack_agg.zip`) to start, or
- a small redacted JSONL sample if you want the delta proof loop.

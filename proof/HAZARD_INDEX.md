# Pitstop Hazard Index (Proof Pack)

This folder is a growing set of **small, concrete hazard proofs** extracted from real-world issues.

Each proof aims to follow the same loop:

radar → comment → extract invariant → write receipt → codify guardrail → bundle artifact

The goal is not “content.” The goal is **portable, testable reliability learning**.

---

## Current hazards (proof-backed)

### 1) `cap_misclassified_as_cooldown`
**Claim:** Not all `429` responses are cooldown. Some are **capacity failures** in disguise (TPM/request too large).  
**Failure mode:** Retry loops treat all `429` as “wait and retry,” causing repeated failures and amplification.  
**Invariant:** Only retry **COOLDOWN**. CAP must be **shrunk before retry**.

- Proof: `archi-cap-vs-429/README.md`
- Source: archi issue #497 (context overflow + TPM-based 429 examples)

---

### 2) `cooldown_not_consulted_by_selection`
**Claim:** “Honoring Retry-After” is insufficient if cooldown is enforced only inside the retry loop.  
**Failure mode:** Provider selection can keep reselecting a model/provider in cooldown, causing routing thrash.  
**Invariant:** Cooldown must be consulted by **provider selection eligibility**, not only retry timing.

- Proof: `plano-429-failover/REGRESSION_TEST.md`
- Related note: `plano-429-failover/README.md`
- Source: plano issue #697 (retry/failover semantics discussion)

### 3) `wait_misclassified_as_stop`
**Claim:** Some provider responses appear fatal based on HTTP status alone but are actually **temporary exhaustion conditions**.  
**Failure mode:** Clients map raw status codes (e.g. `402`) directly to fatal STOP, halting execution even though the condition resolves with time.  
**Invariant:** If the condition resolves with time, classify as **WAIT**, not **STOP**.

- Proof: `openclaw-402-wait-vs-stop/README.md`
- Source: openclaw issue #30484 (Anthropic 402 misclassified as billing)

---

## Hazard Families

Many hazards fall into broader reliability families.  
Grouping them helps identify where reusable guardrails should exist.

### Rate-limit / exhaustion hazards

Temporary exhaustion conditions that should trigger **WAIT** semantics.

- `wait_misclassified_as_stop`
- `cooldown_not_consulted_by_selection`

These hazards appear when systems misinterpret rate limits, quota windows,
or cooldown signals.

Typical consequences:

- premature failure
- routing thrash
- repeated retries against unavailable providers

---

### Capacity / size hazards

Failures caused by **request size exceeding system limits**.

- `cap_misclassified_as_cooldown`

Typical consequences:

- useless retries
- retry amplification
- wasted compute

Correct behavior:
```text
CAP → shrink request
```
not
```text
CAP → retry
```
---

### Retry amplification hazards (emerging)

These occur when retry logic exists but lacks proper **bounds or coordination**.

Examples that commonly appear in distributed systems:

- retry without global retry budget
- backoff without jitter
- retries ignoring cooldown eligibility

These hazards often lead to **retry storms** under load.

(Some examples are listed here as candidate hazard classes and may be
documented with proofs later.)

---

## Candidate Guardrails

These hazards suggest a small set of reusable reliability primitives.

Examples:

### `classify_error(...)`

Classifies execution failures into behavioral categories:
```text
WAIT
STOP
CAP
UNKNOWN
```
Inputs might include:

- HTTP status
- provider context
- response headers
- payload signals

---

### `should_retry(...)`

Determines whether retry is appropriate.

Example rule shape:
```text
WAIT → retry with bounded backoff
CAP → modify request before retry
STOP → fail immediately
```
---

### `eligible_providers(...)`

Ensures routing logic respects cooldown state.

Provider selection should exclude providers currently in cooldown.

```text
if provider.cooldown_active:
provider is ineligible
```
---

### `preflight_budget_ok(...)`

Prevents capacity failures before execution.

Example:
```text
estimated_input_tokens <= model_context_limit - reserved_output_tokens
```
---

These guardrails represent **portable reliability controls** that could
eventually become code primitives.

---

## Index of proof artifacts

- `archi-cap-vs-429/` — CAP vs COOLDOWN classification; don’t retry size errors
- `plano-429-failover/` — retry vs failover semantics for HTTP 429; cooldown must gate selection
- `openclaw-402-wait-vs-stop/` — provider-specific HTTP 402 may indicate WAIT, not fatal billing
- `svix-2200/` — demo pack v0 (derived hazards/signatures)
- `demo_pack_v0/` — early example pack (hazards/signatures/report)
---

## Template (how new hazards should look)

A new hazard proof should include:

1) **Name** (stable hazard class id)
2) **Observed signals** (what shows up in logs/headers)
3) **Why naive handling fails** (retry storms, thrash, wasted compute)
4) **Invariant** (one sentence)
5) **Decision table** (signals → class → action)
6) **Guardrail** (small preflight or selection rule)
7) **Minimal test** (the smallest regression that locks it in)
8) **Source link** (issue / incident / repro)

---

## Naming convention (recommended)

Use short hazard ids that can become tags later:

- `cooldown_not_consulted_by_selection`
- `cap_misclassified_as_cooldown`
- `retry_storm_missing_budget_cap`
- `timeout_deadline_not_propagated`
- `backoff_without_jitter_herd`

---

## Why this exists

Pitstop isn’t “advice.”
Pitstop is **evidence + invariants** that reduce retries, tail latency, and failure amplification.

These proofs are meant to be:
- linkable
- reviewable
- expandable into guardrails/tests later
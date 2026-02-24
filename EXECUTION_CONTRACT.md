# Pitstop Execution Contract (v1.0)

> TL;DR: `execute(intent, budget, policy) -> result, receipt`
> 
> - Budgets are hard limits (deadline, max elapsed, attempts).
> - Errors are classified consistently (429 vs 402 vs timeout vs auth).
> - Cooldowns are scoped correctly (model vs provider vs credential).
> - Every attempt emits a receipt safe to export (no prompts/bodies/headers).

**True North:** We make AI + API execution predictable: budgets, routing, enforcement, receipts.  
**Soundbite:** The Stripe-style API spec for execution reliability (not model quality).

**Contract version:** `1.0`

## Compatibility (normative)
- **v1.x is additive only.** New fields MAY be added; existing fields/semantics MUST NOT change.

## Non-goals (v1)

This contract is only about making execution predictable (budgets, routing scope, enforcement decisions, receipts).

It is not:
- A tracing standard (e.g., OpenTelemetry replacement)
- A model quality or eval framework
- A billing/invoicing spec
- A security policy framework
- A payload logging schema

This is an execution reliability contract.
- **Forward-compatible receipts:** consumers MUST ignore unknown fields.
- Breaking changes require **v2.0** plus an explicit migration note.

---

## 1) The contract

### Function signature
`execute(intent, budget, policy) -> result, receipt`

This contract defines:
- **Inputs** (what the caller provides),
- **Result** (what the caller receives),
- **Receipt** (audit-grade artifact emitted every time).

**Receipt is the primitive.** It enables:
- SCAN hazard ranking (`hazards.csv`, `signatures.csv`, `summary.json`)
- Enforcement (guardrails + refusal boundaries)
- Router correctness (model/provider/credential scope)
- Delta proof (before/after)

---

## 2) Inputs

### 2.1 intent
Intent is a human-meaningful statement of what is being attempted.

**Required**
- `intent.name` (string) — e.g. `github.search_issues`, `llm.chat_completion`, `rpc.debug_call`
- `intent.purpose` (string) — short reason
- `intent.operation_class` (string) — e.g. `read`, `write`, `auth`, `exec`, `payment`
- `intent.is_destructive` (bool) — true if the operation can delete/modify/execute dangerously

### 2.2 budget
Budgets are hard constraints. They are not “timeouts you hope for.”

**Required**
- `budget.deadline_ms` — per-attempt wall-clock cap
- `budget.max_elapsed_ms` — total wall time across retries + backoff + fallbacks
- `budget.retry_budget` — max attempts (integer), **including fallbacks**
- `budget.token_budget` — for LLM calls; optional/null for non-LLM

**Backwards compatibility**
- If legacy `budget_ms` is present, it MUST be interpreted as:  
  `budget_ms` ≡ `budget.deadline_ms` (per-attempt)

**Budget precedence (normative)**
1) `budget.max_elapsed_ms` overrides everything. Execution MUST stop once exceeded.  
2) `budget.deadline_ms` caps each attempt. Each attempt MUST be cancelled once exceeded.  
3) `budget.retry_budget` caps the total number of attempts (including fallbacks).  
4) Parent context cancellation overrides all budgets immediately.

### 2.3 policy
Policy declares what the executor is allowed to do (may be stricter than budget).

**Required**
- `policy.mode` — `shadow | enforce`
- `policy.fail_behavior` — `fail_open | fail_closed`
- `policy.max_attempts` — integer (MUST be `<= budget.retry_budget`)
- `policy.backoff` — `{ strategy: exponential, jitter: bool, respect_retry_after: bool }`
- `policy.concurrency_cap` — optional integer cap
- `policy.cooldown` — `{ enabled: bool }`
- `policy.allow_destructive` — bool (guard boundary)

**Budget vs policy (normative)**
- **Budget** is the caller’s ceiling.  
- **Policy** is the executor’s allowance.  
- Executor MUST enforce: `policy.max_attempts <= budget.retry_budget`.

---

## 3) Outputs

### 3.1 result
Result is what the caller cares about.

**Required**
- `result.status` — `ok | fail`
- `result.value` — operation-specific payload (may be null)
- `result.error` — operation-specific error object (may be null)
- `result.fallback_used` — bool
- `result.attempts_used` — int
- `result.elapsed_ms` — int

### 3.2 receipt (required, emitted always)
A receipt is a single JSON object (one JSONL line) emitted **per attempt**.

**Receipt emission (normative)**
- A receipt MUST be emitted for **every attempt**, including when the executor does **not** call the underlying tool (e.g., `block`, `cooldown`, budget preemption).
- A receipt MUST be emitted for all executor actions:  
  `allow | allow_shadow | retry | fallback | cooldown | block`.

The receipt MUST contain enough information to:
- classify outcomes
- attribute failures/breaches to signatures
- prove budgets were enforced
- prove routing/enforcement decisions

**Attempt accounting (normative)**
- An **attempt** is a single discrete executor action toward fulfilling `execute(...)`, including: `allow`, `retry`, `fallback`, `cooldown`, `block`, and `allow_shadow`.
- `attempt_id` MUST increment for every attempt (including fallbacks and preemptions).
- `result.attempts_used` MUST equal the total number of attempts emitted for the `execution_id`.
- `cost.latency_ms` is **per attempt** wall time spent in that attempt (including tool call time; excluding future backoff).
- `cost.backoff_ms`, when present, is the **scheduled sleep before the next attempt** (0 if no backoff).

---

## 4) Receipt schema (v1 required fields)

### 4.1 identity
- `receipt_id` (string, unique)
- `ts_utc` (RFC3339 string)
- `execution_id` (string) — stable across attempts for one logical call
- `attempt_id` (int) — 1..N

### 4.2 attempt semantics (normative)
- `execution_id` identifies one logical `execute(...)` call across all attempts.
- `attempt_id` increments for **every** attempt, including fallbacks.
- `attempt.kind` MUST be one of: `primary | retry | fallback`.
- `attempt.prior_attempts` (int) — number of attempts already made before this attempt (0 for first).

### 4.3 target (normalized)
- `tool_id` (string) — e.g. `github`, `anthropic`, `openai`, `rpc`
- `operation` (string) — e.g. `search_issues`, `create_issue`, `chat_completion`
- `endpoint_norm` (string) — normalized endpoint/class (not raw URL)
- `provider_id` (string, optional) — if tool routes providers
- `model_id` (string, optional)

### 4.4 scope keys (blast radius)
These keys define what may be cooled down or disabled.

**Required/Optional**
- `scope.model_key` (string, optional) — e.g. `{provider}:{model}:{credential}`
- `scope.provider_key` (string, optional) — e.g. `{provider}:{credential}`
- `scope.credential_key` (string, optional) — stable id/hash of a **non-secret** credential identifier

**Scope key rules (normative)**
- MUST be deterministic, stable across restarts, and non-secret.
- MUST NOT include tokens, headers, raw URLs, prompts, or customer content.
- `scope.credential_key` MUST NOT be a hash of the credential secret.

### 4.5 budgets (effective)
- `budget.deadline_ms`
- `budget.max_elapsed_ms`
- `budget.retry_budget`
- `budget.token_budget` (optional)

### 4.6 outcome
- `outcome.status` — `ok | fail`
- `outcome.error_class` — enum (see §5) (REQUIRED if `status=fail`)
- `outcome.http_status` (int, optional)
- `outcome.retry_after_ms` (int, optional)

### 4.7 timing + cost
- `cost.latency_ms` (int)
- `cost.backoff_ms` (int, optional)
- `cost.tokens_est` (int, optional)

### 4.8 decision (what executor did)
- `decision.action` — `allow | allow_shadow | retry | fallback | cooldown | block`
- `decision.reason_code` (string) — short machine label
- `decision.mode` — `shadow | enforce`

### 4.9 evidence (minimal)
- `evidence.rate_limit_type` (string, optional) — `primary | secondary`
- `evidence.classification_confidence` (float, optional 0..1)

---

## 5) Classification taxonomy (normative)

### 5.1 error_class enum (v1)
- `rate_limit_429`
- `rate_limit_secondary` (e.g. GitHub secondary 403)
- `timeout_deadline`
- `auth_401`
- `auth_403`
- `billing_402`
- `server_5xx`
- `invalid_4xx`
- `network`
- `unknown`
- `preempted_budget` (executor stopped before calling tool due to `max_elapsed_ms` / deadline / attempt cap)
- `preempted_policy` (executor refused to call tool due to policy: destructive disallowed, fail_closed boundary, etc.)
- `cooldown_active` (executor skipped call because a matching cooldown key was active)

### 5.2 classification mapping (v1 normative)
If `outcome.http_status` is present, classification MUST follow:

| http_status | error_class |
|---:|---|
| 429 | `rate_limit_429` |
| 5xx | `server_5xx` |
| 402 or explicit `payment_required`/billing disabled | `billing_402` |
| 401 | `auth_401` |
| 403 + secondary-rate-limit signals | `rate_limit_secondary` |
| other 403 | `auth_403` |
| other 4xx | `invalid_4xx` |

If no `http_status` exists:
- deadline/ctx timeout → `timeout_deadline`
- network/socket/dns → `network`
- otherwise → `unknown`

### 5.3 retryability rules (v1)
Retryable (default): `rate_limit_429`, `rate_limit_secondary`, `timeout_deadline`, `server_5xx`, `network`  
Non-retryable (default): `auth_401`, `auth_403`, `billing_402`, `invalid_4xx`

**429 rule (normative):** If `outcome.retry_after_ms` is present, it MUST be respected unless it would violate `budget.max_elapsed_ms`.

---

## 6) Scope semantics (routing + cooldown blast radius)

This section defines the difference between a temporary throttle and “the credential is dead.”

### 6.1 model-scope failure
Example: model-specific token pool exhaustion on Claude Max.

**Contract (normative)**
- Classify as `rate_limit_429` (model-exhaustion subtype may be added in v1.x).
- MUST NOT mark provider/credential as billing-dead.
- MUST attempt next model fallback under the same provider/credential when configured.

### 6.2 provider-scope failure
Example: provider temporarily degraded or rate-limited.

**Contract (normative)**
- Classify as `rate_limit_429` / `rate_limit_secondary` / `server_5xx`.
- SHOULD attempt next provider fallback when configured.
- Cooldown key MUST be provider-scope (not credential-billing-scope).

### 6.3 credential-scope failure
Example: invalid auth or real billing disable.

**Contract (normative)**
- `auth_401/auth_403/billing_402` are credential-scope.
- Executor SHOULD cooldown/disable credential and MUST NOT spam retries.

### 6.4 cooldown rules (normative)
- cooldown key = `{scope_key, reason}`
- cooldown MUST store `retry_after_ms` if available
- 429 cooldown MUST NEVER be represented as “billing disabled”

**Cooldown semantics (normative)**
- Cooldown duration MUST be derived from `outcome.retry_after_ms` when present; otherwise executor MAY apply a policy default.
- Cooldown is scoped by `{scope_key, reason}` where `scope_key` is one of: `scope.model_key | scope.provider_key | scope.credential_key`.
- If `outcome.retry_after_ms` would cause `budget.max_elapsed_ms` to be exceeded, executor MUST NOT sleep past `max_elapsed_ms`; it MUST terminate with `preempted_budget` and emit a receipt.
- Cooldown storage MAY be in-memory or persistent; contract does not require persistence, only determinism of keying and receipts.

---

## 7) Security & privacy invariants (normative)

Receipts MUST NOT include:
- prompts, message content, tool payload bodies, response bodies
- headers, tokens, API keys, cookies
- raw URLs or query strings (use `endpoint_norm`)

Receipts SHOULD include only:
- normalized identifiers (`endpoint_norm`, `tool_id`, `operation`, optional `provider_id/model_id`)
- coarse context buckets (env/region/concurrency/tier if available)
- budgets, outcomes, timing, and executor decisions

Receipts MUST be safe to export as “derived operational metadata.”

---

## Appendix A) Example receipts (JSONL)

**Attempt 1 (rate-limited → retry):**
```json
{"receipt_id":"r_01","ts_utc":"2026-02-24T03:21:09Z","execution_id":"ex_abc","attempt_id":1,"attempt":{"kind":"primary","prior_attempts":0},"tool_id":"github","operation":"search_issues","endpoint_norm":"GET /search/issues","scope":{"provider_key":"github:cred_h1","credential_key":"cred_h1"},"budget":{"deadline_ms":900,"max_elapsed_ms":1200,"retry_budget":3},"outcome":{"status":"fail","error_class":"rate_limit_429","http_status":429,"retry_after_ms":2000},"cost":{"latency_ms":210},"decision":{"action":"retry","reason_code":"retryable_rate_limit","mode":"enforce"},"evidence":{"rate_limit_type":"primary","classification_confidence":0.9}}
```
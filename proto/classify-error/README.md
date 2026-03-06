# classify_error (proto)

A small Pitstop primitive for mapping raw failure signals into **behavioral classes**.

The goal is not to preserve every upstream error taxonomy.
The goal is to answer the execution question:

See also: `docs/wait-stop-cap.md`

> **What should the caller do next?**

---

## Why this exists

Many reliability failures come from **misclassification**, not from missing retries.

Examples already captured in the proof library:

- `cap_misclassified_as_cooldown`
  - oversized request treated like a temporary wait condition
- `wait_misclassified_as_stop`
  - temporary provider exhaustion treated like a fatal billing error
- `cooldown_not_consulted_by_selection`
  - cooldown exists, but later logic ignores the semantic class

A small classifier provides a stable behavioral layer between:

```text
raw error / status / headers / provider message
```
and:
```text
retry / stop / shrink / failover / selection
```
---

## Behavioral classes

### WAIT

The condition may resolve with time.

Typical handling:
- bounded retry
- backoff / jitter
- honor Retry-After if present
- do not treat as fatal immediately

Examples:
- 429 with valid Retry-After
- provider-specific temporary usage window exhaustion
- GitHub API rate limiting with reset headers

---

### STOP

The caller should fail immediately.

Typical handling:
- no retry
- surface clear error
- require operator or configuration change

Examples:
- confirmed billing exhaustion
- invalid auth that will not self-heal
- permanent policy refusal

---

### CAP

The request itself must be changed before retrying.

Typical handling:
- trim / summarize / chunk
- reduce payload size
- reserve output tokens
- do not retry unchanged request

Examples:
- context_length_exceeded
- “request too large”
- TPM exceeded because the request is too large

---

### UNKNOWN

The signal is not yet classified confidently.

Typical handling:
- explicit fallback policy
- fail safe
- do not silently assume retryability

---

## Minimal API
```py
def classify_error(
    *,
    status_code: int | None = None,
    provider: str | None = None,
    headers: dict[str, str] | None = None,
    error_code: str | None = None,
    message: str | None = None,
) -> str:
    """
    Classify an execution failure into a behavioral class.

    Returns one of:
    - "WAIT"
    - "STOP"
    - "CAP"
    - "UNKNOWN"
    """
```

---

## First-pass classification rules

Rules are evaluated in order. First match wins.

### Rule 1 — explicit CAP

Return `CAP` if any of the following are true:
- `error_code == "context_length_exceeded"`
- message contains:
  - context_length_exceeded
  - input tokens exceed
  - request too large
  - tokens per minute
  - TPM
  - requested
  - limit

Rationale:
Retrying unchanged requests will fail again.

---

### Rule 2 — explicit STOP

Return `STOP` if:
- the message clearly indicates permanent billing exhaustion
- or the signal is clearly non-retryable and non-capacity-related

Examples:
- billing exhausted
- payment required with confirmed no remaining credits

---

### Rule 3 — provider-specific WAIT

Return `WAIT` if:
- `provider == "anthropic"`
- `status_code == 402`
- the message indicates temporary usage-window exhaustion rather than permanent billing failure

Rationale:
Some providers use status codes that do not directly map to execution semantics.

---

### Rule 4 — explicit cooldown

Return `WAIT` if:
- `Retry-After` header is present and valid
- or `status_code == 429` and no CAP signals are present

Rationale:
The condition is explicitly time-shaped.

---

### Rule 5 — fallback

Return `UNKNOWN` if no rule matches.

Do not silently assume retryability.


## First-pass examples

### Example A — context window exceeded

Input:
```py
classify_error(
    status_code=400,
    error_code="context_length_exceeded",
    message="Input tokens exceed the configured limit",
)
```
Output:
```text
CAP
```
---

### Example B — Retry-After present

Input:
```py
classify_error(
    status_code=429,
    headers={"Retry-After": "2"},
)
```
Output:
```text
WAIT
```
---

### Example C — Anthropic 402 temporary exhaustion

Input:
```py
classify_error(
    status_code=402,
    provider="anthropic",
    message="usage limit reached, please try again later",
)
```
Output:
```text
WAIT
```
---

### Example D — confirmed billing exhaustion

Input:
```py
classify_error(
    status_code=402,
    provider="anthropic",
    message="billing exhausted",
)
```
Output:
```text
STOP
```
---

## Non-goals (v1)

This primitive does not:
- decide retry count
- compute backoff durations
- parse all provider-specific schemas
- decide failover eligibility
- inspect cooldown state

Those belong to later primitives such as:
- `should_retry(...)`
- `next_wait_seconds(...)`
- `eligible_providers(...)`
- `preflight_budget_ok(...)`

---

## Relationship to current proofs

This proto is informed by:
- `proof/archi-cap-vs-429/`
- `proof/plano-429-failover/`
- `proof/openclaw-402-wait-vs-stop/`

It is the first attempt to turn those proofs into a reusable execution primitive.

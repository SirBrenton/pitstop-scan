# CAP vs COOLDOWN: Don't Retry Size Errors

Small operational note extracted from a real failure mode observed in agent pipelines.

Reference discussion:
<https://github.com/archi-physics/archi/issues/497>

---

## Observed Failure Modes

Two different error classes can appear similar in logs but require **very different handling**.

### 1) Context Length Exceeded (CAP)

Example:
```text
400 Bad Request
error: context_length_exceeded
Input tokens exceed the configured limit.
```
Meaning:

The request itself is too large for the model context window. This is a hard capacity violation.

Retrying the same request will always fail.

Correct action:
```text
STOP
→ trim history
→ summarize context
→ chunk input
→ resend smaller request
```
---

### 2. Rate Limit with Retry-After (COOLDOWN)

Example:
```code
429 Too Many Requests
Retry-After: 2
x-ratelimit-*
```
Meaning:

The request is valid but the provider requires a **cooldown window**.

Correct action:
```code
WAIT ≥ Retry-After
→ retry after cooldown
```
---

### 3. Rate Limit Caused by Request Size (CAP-in-disguise)

Example:
```text
429 Too Many Requests
message: request too large for model … tokens per minute
Limit: 8000
Requested: 8024
```
Meaning:

This is **not actually a temporal rate limit**.

The request **exceeds token-per-minute budget** due to its size.

Retrying without modification will fail again.

Correct action:
```text
STOP
→ shrink request
→ resend smaller payload
```
---

## Decision Table

| Signal | Class | Action |
|------|------|------|
| `400 context_length_exceeded` | CAP | STOP → trim / summarize / chunk |
| `429` + `Retry-After` present | COOLDOWN | WAIT ≥ Retry-After |
| `429` message indicates TPM / request too large | CAP | STOP → shrink request |

---

## Guardrail (Preflight Token Budget)

A simple guardrail prevents most CAP failures before the request is sent.

Reserve output tokens and enforce:
```text
estimated_input_tokens <= model_context_limit - reserved_output_tokens
```
If the condition fails:
```text
trim history
summarize context
chunk large inputs
```
Do not send the request and "hope it fits".

---

## Why This Matters

Without separating **CAP vs COOLDOWN**, client retry logic can:

- repeatedly resend oversized prompts
- waste tokens and compute
- create retry storms
- amplify load during rate-limit events

Correct classification prevents useless retries and stabilizes agent pipelines.

---

## Invariant

Retry loops must only operate on **retryable cooldown errors**.

Capacity violations must be **corrected before retrying**.
```text
if error_class == CAP:
stop_and_shrink()

if error_class == COOLDOWN:
wait_then_retry()
```
---

## Summary

Not all `429` responses are cooldown events.

Some are **capacity failures wearing a rate-limit code**.

Clients must distinguish between:
```text
CAP (size violation) → shrink request
COOLDOWN (temporal limit) → wait and retry
```
Treating them the same leads to unnecessary retries and unstable systems.

## Pitstop Signature

**Hazard class:** `cap_misclassified_as_cooldown`

**Observed pattern**

Client retry logic treats all `429` responses as cooldown events.  
When the underlying cause is actually **capacity** (context window or token budget),
the system repeatedly retries requests that cannot succeed.

This leads to:

- wasted tokens and compute
- retry amplification under load
- unstable agent pipelines

**Typical signals**

Logs contain one or more of:

- `context_length_exceeded`
- `Input tokens exceed`
- `Request too large`
- `tokens per minute (TPM): Limit`
- `Requested <n>`

**Invariant**

Retry loops must only operate on **COOLDOWN-class errors**.

Capacity violations (**CAP**) require the request to be **modified before retry**  
(trim / summarize / chunk).

**Optional intent boundary**

If `error_class == CAP`, automatic retry should be disabled.

Systems may require an explicit operator or policy intent (e.g. `SHRINK_AND_RESEND`)
before the request is retried with a smaller payload.

This prevents silent retry loops that repeatedly send oversized requests.
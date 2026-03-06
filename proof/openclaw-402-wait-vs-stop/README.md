# HTTP 402 (Anthropic) — WAIT vs STOP classification

Reference issue:  
`https://github.com/openclaw/openclaw/issues/30484`

---

## Context

OpenClaw users observed repeated **HTTP 402 responses from Anthropic** while using the Claude Max plan.

Despite large remaining quota, the client classified these responses as **billing errors**, resulting in:

- a fatal STOP
- no retry/backoff
- misleading “billing warning” messages

The behavior was confusing because usage would resume normally a few minutes later.

---

## Observed failure chain

The execution path looked like this:
```text
Anthropic returns 402
→ client maps 402 → billing
→ billing classification → fatal STOP
→ execution halts immediately
→ no retry/backoff attempted
```
In the reported cases, these 402 responses appeared to behave like **temporary usage-window exhaustion**, not permanent billing failures.

Users reported that the condition **resolved automatically after a short wait**.

---

## Root cause

The client classified HTTP status **solely by code**, without considering **provider semantics**.

Example logic:

```text
if (status === 402) return "billing"
```
For Anthropic Max-plan usage windows, this classification was incorrect.

---

## Correct semantic boundary

The problem is not “402 vs 429”.

The real boundary is:
```text
WAIT vs STOP
```
**Condition**	                        **Correct class**   **Behavior**
Temporary usage window exhaustion	    WAIT	            bounded retry/backoff
Hard billing / credit exhaustion	    STOP	            fail immediately
Ambiguous provider response	            UNKNOWN	            explicit fallback policy

Execution semantics should determine classification, not raw HTTP status alone.

---

## Decision table

**Signal**	                                        **Class**   **Action**
402 + provider indicates temporary usage window	    WAIT	    retry with bounded backoff
402 + confirmed billing exhaustion	                STOP	    fail clearly
402 ambiguous context	                            UNKNOWN	    explicit policy decision

If `Retry-After` is present, it should be treated as a floor before retry.

---

## Minimal regression test (conceptual)
```text
Given:
provider = anthropic
status = 402
payload indicates temporary usage window exhaustion

Expect:
classification = WAIT
retry/backoff attempted
no fatal billing warning
execution halts only after retry budget exhausted
```

---

## Pitstop Signature

**Hazard class:**
`wait_misclassified_as_stop`

**Observed pattern**

Clients map raw HTTP status codes directly to fatal categories.
Provider-specific semantics convert some responses into **temporary wait conditions**, but the client halts execution immediately.

This leads to:
- false fatal errors
- confusing billing warnings
- premature termination of otherwise recoverable operations

**Typical signals**

Logs contain:
- HTTP 402
- usage remaining still available
- condition resolves automatically after a short delay
- no retry/backoff attempted

**Invariant**

Execution classification must reflect **execution semantics**:
```text
temporary exhaustion → WAIT
permanent exhaustion → STOP
```
Raw HTTP status codes alone are insufficient.

---

## Takeaway

Status codes are not always sufficient to determine execution policy.

Robust systems classify errors using:
- provider context
- payload signals
- execution semantics

rather than relying solely on raw HTTP status mapping.

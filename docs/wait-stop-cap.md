# WAIT vs STOP vs CAP

A small execution model for handling failures in AI + API systems.

Most retry logic is wrong for a simple reason:

it treats very different failures as if they were the same thing.

But operationally, there are three distinct classes.

Failures should be classified by required next action, not by raw status code alone.

---

## 1) WAIT

The operation may succeed later without changing the request.

Examples:

- rate limits
- cooldown windows
- temporary provider throttling
- GitHub API exhaustion that resets shortly

Correct behavior:

```text
wait → retry
```

Typical handling:
- bounded retry
- backoff / jitter
- honor `Retry-After` if present
- do not treat as fatal immediately

---

## 2) CAP

The request itself must change before retrying.

Examples:
- `context_length_exceeded`
- request too large
- token-per-minute overflow caused by request size
- payload exceeds model or API limits

Correct behavior:
```text
shrink → retry
```
Typical handling:
- trim history
- summarize context
- chunk input
- reduce payload size
- reserve output budget

Waiting does not help if the request is structurally too large.

Retrying unchanged requests will fail again.

---

## 3) STOP

The operation cannot succeed without intervention.

Examples:
- confirmed billing exhaustion
- invalid credentials that will not self-heal
- permanent policy refusal
- explicit non-retryable failures

Correct behavior:
```text
stop → surface error
```
Typical handling:
- fail immediately
- surface a clear reason
- require operator or configuration change

Retrying here creates noise, not recovery.

---

## Why this matters

Many reliability failures are really classification failures.

Systems often collapse everything into a single rule:
```text
if error:
    retry()
```
That leads to:
- retry storms
- wasted compute
- false-fatal halts
- confusing user-facing errors
- unstable execution pipelines

The important question is not just:
```text
What HTTP status did I get?
```
It is:
```text
What should the caller do next?
```
Some failures are ambiguous at first; robust systems should use an explicit fallback policy rather than silently assuming retryability.

---

## The model
```text
WAIT → retry
CAP  → shrink
STOP → fail
```
This is a behavioral model, not an upstream error taxonomy.

It exists to help execution systems choose the right next action.

---

## Examples

### Example A — rate-limited request
```text
429 Too Many Requests
`Retry-After`: 2
```
Classification:
```text
WAIT
```
Behavior:
```text
sleep >= `Retry-After`
retry with bounds
```

---

### Example B — oversized prompt
```text
400 `context_length_exceeded`
Input tokens exceed the configured limit
```
Classification:
```text
CAP
```
Behavior:
```text
trim / summarize / shrink
retry modified request
```

---

### Example C — provider-specific temporary exhaustion
```text
402 from provider
message indicates temporary usage-window exhaustion
```
Classification:
```text
WAIT
```
Behavior:
```text
bounded retry / backoff
do not surface as fatal billing immediately
```

---

### Example D — confirmed permanent billing exhaustion
```text
402
billing exhausted
```
Classification:
```text
STOP
```
Behavior:
```text
fail clearly
no retry
```

---

## Where this model helps

This model is useful anywhere execution behavior needs to be governed:
- LLM gateways
- API clients
- retry wrappers
- failover logic
- selection / routing systems
- agent runtimes
- CI helpers that call external APIs

---

## Relationship to Pitstop

This model sits underneath several proof-backed hazards in the repository, including:
- `cap_misclassified_as_cooldown`
- `wait_misclassified_as_stop`
- `cooldown_not_consulted_by_selection`

It also motivates the first proto primitive:
- `proto/classify-error/README.md`

---

## Takeaway

Different failure classes require different behavior.
```text
WAIT → retry
CAP  → shrink
STOP → fail
```
Systems become calmer, cheaper, and more predictable when they get that boundary right.
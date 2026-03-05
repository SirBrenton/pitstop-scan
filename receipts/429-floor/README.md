# 429-floor — Retry-After is a floor (drop-in receipt)

### The failure
Most clients treat `Retry-After` like a suggestion.
They add jitter, they backoff "near" it, or they retry early.
That turns “slow down” into a thundering herd.

### The invariant (what must be true)
- If **HTTP 429** and **Retry-After present+valid** → wait **>= Retry-After**, then retry (budgeted).
- If **HTTP 429** and **Retry-After missing/invalid** → **do not retry** (no guessy backoff).
- For transient **5xx** → budgeted backoff retries are allowed.

### Why this matters
429 is often an upstream protection mechanism. Retrying early:
- increases load at the worst moment
- triggers shared-IP / shared-key stampedes
- causes cascading failures (readiness probes, autoscaling churn, “everything is down”)

### Drop-in artifact
- `policy.py`: a tiny stdlib-only policy you can paste into a Python codebase
- tests: verify the invariant and retry behavior

### Run the tests
From repo root:

```bash
python -m pytest -q receipts/429-floor
```
### Minimal integration sketch

In your retry loop:

1. Parse `Retry-After` from response headers.
2. Gate retries with `should_retry(...)`.
3. Sleep with `compute_sleep_s(...)` (this enforces the Retry-After floor).

Example shape:

```python
retry_after = parse_retry_after(resp.headers.get("Retry-After"))

if should_retry(status_code=resp.status, retry_after_s=retry_after, ...):
    sleep = compute_sleep_s(...)
    time.sleep(sleep)
```
This invariant is one of the guardrails Pitstop Scan will often recommend when 429 hazards appear in a hazard pack.
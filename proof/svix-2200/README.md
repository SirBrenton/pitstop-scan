# svix-2200 — Retry-After / 429 retry semantics

**Source thread:** svix/svix-webhooks `#2200` (“Respect Retry-After on 429/503 responses”).

## What this is
A **minimal modeled receipt set** representing the failure pattern described in the thread (**not production telemetry**).  
Goal: show how Scan classifies the hazard and what guardrails fall out from very small inputs.

## What Scan found (in this pattern)
- **Failure-dominant** signature driven by **429** (rate-limit pressure).
- **High retry pressure** (mean retries per execution is high in this pattern).
- The fix isn’t “add 429 to a list” — it’s **retry semantics correctness**:
  1) `delay = max(backoff, overload_penalty, retry_after)`  
  2) `cap(delay)` (cap the *delay*, not the absolute date)  
  3) **jitter must not undercut** the computed floor  
  4) attempt-budget / schedule-length must still hard-stop even if `Retry-After` is large

## Derived artifacts (safe to share)
- [derived/report.md](./derived/report.md)
- [derived/hazards.csv](./derived/hazards.csv)
- [derived/signatures.csv](./derived/signatures.csv)
- [derived/summary.json](./derived/summary.json)
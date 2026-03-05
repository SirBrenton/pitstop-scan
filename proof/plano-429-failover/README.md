# plano-429-failover

Issue:
https://github.com/katanemo/plano/issues/697

## Context

Discussion about retrying a different model/provider when HTTP 429
(rate limit) is returned.

## Observed proposal

Retry another model when HTTP 429 is received.

Example idea from issue:
"retry to other configured model if 429 is returned"

## Failure mode

Treating 429 as a signal to "try elsewhere" can cause:

- cross-provider thundering herd
- shared-key stampedes
- retry storms across model pools

429 is usually a **cooldown signal**, not a routing signal.

## Pitstop invariant

Retry and failover must be separated.

429 + Retry-After present  
→ wait >= Retry-After before retrying.

429 + Retry-After missing  
→ do not retry (avoid guessy backoff).

Failover should only occur when the error indicates
capacity loss or quota exhaustion, not rate limiting.

## Decision table

| Response | Action |
|--------|-------|
| 429 + Retry-After | sleep >= Retry-After |
| 429 no Retry-After | stop |
| 5xx / timeout | retry with backoff |
| quota exhausted | failover allowed |

## Pitstop Signature

**Hazard class:** `cooldown_ignored_by_selection`

**Observed pattern**

Gateways implement “honor Retry-After” inside the retry loop, but provider/model election
can still reselect a cooling-down provider between attempts.

That turns cooldown into routing thrash:

- repeated reselection of a blocked provider
- herd behavior under load
- “spray traffic until something works” failover

**Invariant**

Cooldown must be consulted by provider selection, not only by the retry loop.

Conceptual shape:

```text
eligible = providers.filter(p => p.cooldown_until <= now)
selected = select(eligible)
```

**Regression test (proof)**

See: `REGRESSION_TEST.md` (A is ineligible until `t >= Retry-After`, while alternates remain eligible).


## Reference receipt

See:

receipts/429-floor
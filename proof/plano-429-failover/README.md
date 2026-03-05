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

## Reference receipt

See:

receipts/429-floor
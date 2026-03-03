# svix-2200 — Retry-After / 429 retry semantics

**Source thread:** svix/svix-webhooks issue `#2200` (“Respect Retry-After on 429/503 responses”).

**What this is:** a *minimal modeled receipt set* representing the failure pattern described in the thread (not production telemetry).

**What Scan found:** failure-dominant 429 signature with high retry pressure; respecting Retry-After as a floor (plus a cap; jitter must not undercut) reduces wasted retries and load.

**Artifacts (derived only):**
- `pack/report.md`
- `pack/hazards.csv`
- `pack/signatures.csv`
- `pack/summary.json`

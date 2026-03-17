# Start Here

Pitstop Scan is a local-first reliability triage tool for **AI + API execution**.

It exists because modern execution stacks still fail in predictable ways:

- retry storms
- misclassified 429s / 402s / auth failures
- wrong failover behavior
- tail-latency blowups
- missing audit trails

The core idea is simple:

```text
execute(intent, budget, policy) -> result, receipt
```

## 1) Read the contract

The execution contract defines the reliability semantics:

* budgets are hard limits
* every attempt emits a receipt
* failures are classified consistently
* cooldown scope is explicit
* receipts are safe to export

→ See [`../EXECUTION_CONTRACT.md`](../EXECUTION_CONTRACT.md)

## 2) Understand the execution model

Not all failures should be retried the same way.

```text
WAIT → retry
CAP  → shrink
STOP → fail
```

→ See [`wait-stop-cap.md`](./wait-stop-cap.md)

## 3) Run Scan

If you already have receipts in `input/exhaust.jsonl`:

```bash
make run
open output/report.md
```

Or run the demo:

```bash
make demo
open output/report.md
```

Scan produces:

* `output/report.md`
* `output/hazards.csv`
* `output/signatures.csv`
* `output/summary.json`

## 4) See the proof-backed hazards

Pitstop includes small proof artifacts derived from real-world issues.

→ See [`../proof/HAZARD_INDEX.md`](../proof/HAZARD_INDEX.md)

Examples include:

* CAP misclassified as cooldown
* cooldown not consulted by selection
* WAIT misclassified as STOP

## 5) See an executable guardrail example

Example receipt/guardrail package:

→ See [`../receipts/429-floor/README.md`](../receipts/429-floor/README.md)

Core invariant:

> Retry-After is a floor, not a suggestion.

## 6) Schema / receipts

The receipt schema is the machine-readable layer underneath Scan.

→ See [`../schemas/decision_event.v1.schema.json`](../schemas/decision_event.v1.schema.json)
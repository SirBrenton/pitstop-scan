# Pitstop RetKit

RetKit makes it easy to share **redacted, contract-shaped receipts** with Pitstop Scan.

It’s a tiny CLI that validates JSONL receipts against the Pitstop receipt schema.

## Why it exists

When someone says “I’m getting 429s/timeouts/weird failover”, the fastest path to a real fix is a small batch of **receipts**.
RetKit turns “send me logs” into “run this validator and share the file.”

## Install / run (repo venv)

From the repo root (with `.venv` active):

```bash
pitstop help
```
## Validate receipts (primary workflow)

Validate a JSONL file (one JSON object per line):
```bash
pitstop validate input/exhaust.jsonl
```
Optional: specify the schema explicitly:
```bash
pitstop validate input/exhaust.jsonl --schema schemas/receipt_event.v1.json
```
If validation passes, the receipts are acceptable for Scan.

## Accepted receipt shapes

RetKit accepts either:
1.	**Canonical** receipts: decision_event.v1 (preferred; maps to pitstop-truth)
2.	**Scan-minimal** receipts: a smaller compat shape accepted by Scan

The validator will reject missing essentials (timestamps, target identifiers, outcome classification, etc.).

## Redaction boundary

Receipts must be metadata-only. Do not include:
- prompts, message content, tool payload bodies, response bodies
- headers, tokens, API keys, cookies
- raw URLs or query strings (use endpoint_norm)

## What to send (prospect-friendly)

If you want me to run Scan and return a hazard pack, send:
- input/exhaust.jsonl (50–200 lines is enough)
- confirmation that pitstop validate input/exhaust.jsonl passes
- optional: the stack/context (provider + SDK + where retries happen)

# Intake

Convert a raw failure blob into a scan-ready artifact pack.

## Why intake exists

Most teams do not start with clean execution receipts.

They start with:
- copied SDK errors
- raw HTTP responses
- issue-thread logs
- partial production failures

`intake` is the bridge from that messy reality to a structured artifact that Pitstop Scan can analyze.

## Command

```bash
python -m pitstop_scan.cli intake --in blob.txt --out output/intake-pack --run-scan
```

## What it produces

The command writes an artifact pack to the output directory you choose:
- raw_scrubbed.txt — scrubbed copy of the input blob
- artifact.json — normalized boundary classification summary
- exhaust.jsonl — scan-compatible receipt
- summary.md — human-readable provisional diagnosis

If --run-scan is included, it also writes:
- derived/ — standard scan outputs (report.md, hazards.csv, signatures.csv, summary.json, etc.)

## Example

Input:
```text
HTTP/2 429
content-type: application/json
{
  "error": {
    "code": 429,
    "message": "Resource exhausted. Please try again later.",
    "status": "RESOURCE_EXHAUSTED"
  }
}
retry-after-ms=11180000
provider=vertexai
```
Output summary:
- HTTP Status: 429
- Class: rate_limit_429
- Decision: STOP
- Likely Boundary: sustained rate limit / long-window exhaustion

## What intake does today

v1 intake performs:
- conservative raw-text scrubbing
- heuristic signal extraction
- provisional classification
- synthetic receipt generation
- optional automatic scan execution

It currently extracts signals such as:
- HTTP status
- Retry-After / retry-after-ms
- provider hints
- model hints
- coarse error class
- provisional decision (retry / stop)

## What intake does not do (yet)

Intake is intentionally narrow.

It does not yet provide:
	•	provider-complete parsing
	•	fully reliable body-semantic classification
	•	formal secret-detection guarantees
	•	economic consequence estimation
	•	streaming ingestion
	•	perfect normalization of arbitrary logs

## Privacy / safety

Raw intake blobs may temporarily contain headers or provider error text.

Before generating a scan-ready receipt, intake applies conservative scrubbing to remove obvious sensitive values such as:
- bearer tokens
- API keys / token-like values
- email addresses
- query strings in URLs
- obvious long secret-like strings

This is a practical v1 boundary, not a formal guarantee.

Review the generated pack before sharing anything externally.

## Relationship to Scan

The outputs of intake are designed to feed directly into Scan.

Flow:
```text
raw blob → intake pack → exhaust.jsonl → scan → hazard pack
```
That means you can start from the ugly failure you already have and still get:
- a structured receipt
- a ranked hazard pack
- a concrete guardrail order

## When to use intake

Use intake when:
- you only have copied logs or pasted failures
- you want a fast first pass
- you do not yet emit structured receipts

Use scan directly when:
- you already have receipt JSONL
- you want full fidelity on real execution evidence

## Minimal logging fields (redactable, no secrets)

Log these on every retry decision:

- request_id (or attempt_id)
- scope_key (provider + endpoint + model)
- http_status
- retry_after_s (parsed)
- attempt
- elapsed_s
- sleep_s (applied)
- max_elapsed_s / max_attempts

### Example (json-ish)

{
  "scope_key": "anthropic:/v1/messages:claude-3.5",
  "http_status": 429,
  "retry_after_s": 12.0,
  "attempt": 2,
  "elapsed_s": 6.4,
  "sleep_s": 12.0,
  "max_elapsed_s": 30.0,
  "max_attempts": 6
}

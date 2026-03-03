import json, hashlib, datetime as dt, re

RAW = "input/svix_2200.raw.jsonl"
OUT = "input/exhaust.jsonl"

BASE_TS = dt.datetime(2026, 3, 3, 14, 0, 0, tzinfo=dt.timezone.utc)

# --- helpers

def mk_receipt_id(obj: dict) -> str:
    base = {
        "execution_id": obj.get("execution_id"),
        "attempt_id": obj.get("attempt_id"),
        "tool_id": obj.get("tool_id"),
        "operation": obj.get("operation"),
        "endpoint_norm": obj.get("endpoint_norm"),
        "status": (obj.get("outcome") or {}).get("status"),
        "http_status": (obj.get("outcome") or {}).get("http_status"),
        "error_class": (obj.get("outcome") or {}).get("error_class"),
    }
    s = json.dumps(base, sort_keys=True, separators=(",", ":"))
    return "r_" + hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]

def parse_retry_after_ms(headers: dict) -> int | None:
    """
    Supports:
      - delta-seconds (int/float)
      - RFC 2822 HTTP-date
    Returns milliseconds, or None if not parseable.
    """
    if not headers:
        return None
    ra = None
    # accept different casings
    for k in ("retry-after", "Retry-After", "RETRY_AFTER"):
        if k in headers:
            ra = headers[k]
            break
    if not ra:
        return None

    # delta seconds (float allowed)
    try:
        sec = float(str(ra).strip())
        if sec < 0:
            return None
        sec_int = int(sec) if sec.is_integer() else int(sec) + 1  # ceil
        return sec_int * 1000
    except Exception:
        pass

    # RFC 2822 date
    try:
        # Python's email.utils can parse RFC2822-ish
        from email.utils import parsedate_to_datetime
        d = parsedate_to_datetime(str(ra).strip())
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        delta = (d.astimezone(dt.timezone.utc) - dt.datetime.now(dt.timezone.utc)).total_seconds()
        if delta < 0:
            return 0
        return int(delta * 1000)
    except Exception:
        return None

def canon_error_class(status: str, error_class: str | None, http_status: int | None) -> str | None:
    if status != "fail":
        return None
    # Map your raw “http/timeout” into Scan’s enums
    if http_status == 429:
        return "rate_limit_429"
    if http_status and 500 <= http_status <= 599:
        return "server_5xx"
    if error_class in ("timeout", "deadline", "context_deadline"):
        return "timeout_deadline"
    if http_status in (401,):
        return "auth_401"
    if http_status in (403,):
        return "auth_403"
    if http_status in (402,):
        return "billing_402"
    if http_status and 400 <= http_status <= 499:
        return "invalid_4xx"
    return "unknown"

def decide_action(raw_decision_action: str, status: str, attempt_budget_exhausted: bool) -> str:
    # Your raw used "ok/stop" which is not valid in schema.
    if status == "ok":
        return "allow"
    if attempt_budget_exhausted:
        return "block"
    # otherwise retry path
    return "retry"

def reason_code(status: str, http_status: int | None, ra_ms: int | None, backoff_ms: int | None, capped: bool, jitter_floor: bool, attempt_budget_exhausted: bool) -> str:
    if status == "ok":
        return "ok"
    if attempt_budget_exhausted:
        return "attempt_budget_exhausted"
    if http_status == 429 and ra_ms is not None:
        # This is the core of the story:
        # did we honor Retry-After as a floor, and did jitter undercut it?
        if jitter_floor:
            # guaranteed never earlier than Retry-After
            return "retry_after_floor_strict"
        return "retry_after_floor_symmetric_jitter_risk"
    if http_status == 429:
        return "rate_limit_429_backoff"
    if http_status == 503 and ra_ms is not None:
        return "server_overload_retry_after"
    if http_status == 503:
        return "server_overload_backoff"
    return "retry_generic"

def derive_backoff_ms(ra_ms: int | None, base_backoff_ms: int, cap_ms: int, strict_floor: bool) -> tuple[int, bool]:
    """
    Compute scheduled delay for demo purposes:
      delay = max(base_backoff_ms, ra_ms) if ra_ms else base_backoff_ms
      delay = min(delay, cap_ms)
    Return: (delay, capped?)
    """
    delay = base_backoff_ms
    if ra_ms is not None:
        delay = max(delay, ra_ms)
    capped = delay > cap_ms
    delay = min(delay, cap_ms)
    return delay, capped

# --- main

def main():
    # demo knobs (tune these to match Svix semantics you want to illustrate)
    BASE_BACKOFF_MS = 30_000        # internal schedule stage (example)
    CAP_MS = 2 * 60 * 60 * 1000     # 2 hours fixed cap
    STRICT_FLOOR = True            # set False to simulate symmetric jitter undercut risk

    with open(RAW, "r") as f, open(OUT, "w") as g:
        i = 0
        for line in f:
            line = line.strip()
            if not line:
                continue
            src = json.loads(line)

            # pull from your raw
            execution_id = src.get("execution_id", "svix-2200-demo")
            attempt_id_raw = src.get("attempt_id")

            # attempt_id must be integer
            try:
                attempt_id = int(attempt_id_raw)
            except Exception:
                attempt_id = i + 1

            target = src.get("target") or {}
            tool_id = target.get("tool_id") or src.get("tool_id") or "svix-webhooks"
            operation = target.get("operation") or src.get("operation") or "deliver"
            endpoint_norm = target.get("endpoint_norm") or src.get("endpoint_norm") or "dest://example"

            outcome = src.get("outcome") or {}
            status = outcome.get("status") or "fail"
            http_status = outcome.get("http_status")
            raw_err_class = outcome.get("error_class")

            # receipt headers
            receipt = src.get("receipt") or {}
            headers = (receipt.get("headers") or {}) if isinstance(receipt, dict) else {}
            ra_ms = parse_retry_after_ms(headers)

            # attempt budget exhausted?
            attempt_budget_exhausted = (receipt.get("note") == "attempt-budget exhausted")

            # compute demo delay semantics
            backoff_ms, capped = derive_backoff_ms(ra_ms, BASE_BACKOFF_MS, CAP_MS, STRICT_FLOOR)

            # jitter floor semantics: if STRICT_FLOOR then jitter can’t undercut RA
            jitter_floor = bool(STRICT_FLOOR)

            canon_err = canon_error_class(status, raw_err_class, http_status)

            # required ts_utc
            ts = (BASE_TS + dt.timedelta(seconds=i)).isoformat().replace("+00:00", "Z")

            # required budget fields
            budget = src.get("budget") or {}
            deadline_ms = int((budget.get("deadline_ms") or 30_000))
            retry_budget = int((budget.get("retry_budget") or 0))
            max_elapsed_ms = int((budget.get("max_elapsed_ms") or 120_000))

            # action + decision fields
            raw_action = (src.get("decision") or {}).get("action", "")
            action = decide_action(raw_action, status, attempt_budget_exhausted)
            rcode = reason_code(status, http_status, ra_ms, backoff_ms, capped, jitter_floor, attempt_budget_exhausted)

            out = {
                "schema_version": "decision_event.v1",
                "ts_utc": ts,
                "execution_id": execution_id,
                "attempt_id": attempt_id,

                "tool_id": tool_id,
                "operation": operation,
                "endpoint_norm": endpoint_norm,

                "budget": {
                    "deadline_ms": deadline_ms,
                    "max_elapsed_ms": max_elapsed_ms,
                    "retry_budget": retry_budget,
                    "token_budget": None,
                },

                "policy": {
                    "mode": "enforce",
                    "fail_behavior": "fail_closed",                    "backoff": {
                        "strategy": "exp",
                        "jitter": True,
                        "respect_retry_after": True,
                    },
                    "concurrency_cap": None,
                    "cooldown": {"enabled": False},
                },

                "outcome": {
                    "status": status,
                    "error_class": canon_err,
                    "http_status": http_status,
                    "retry_after_ms": ra_ms,
                },

                "cost": {
                    "latency_ms": float((src.get("cost") or {}).get("latency_ms", 0)),
                    "backoff_ms": float(backoff_ms) if action == "retry" else None,
                    "tokens_est": None,
                },

                "decision": {
                    "action": action,
                    "reason_code": rcode,
                    "mode": "enforce",
                },

                "evidence": {
                    "classification_confidence": 0.9,
                },

                # keep original raw receipt evidence (allowed by additionalProperties:true)
                "receipt": src.get("receipt"),
            }

            out["receipt_id"] = mk_receipt_id(out)
            g.write(json.dumps(out, separators=(",", ":")) + "\n")
            i += 1

    print(f"wrote {OUT} events={i}")

if __name__ == "__main__":
    main()

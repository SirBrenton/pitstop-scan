from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


# Hard safety boundary: do not allow payload bodies / prompts / raw headers / secrets.
UNSAFE_KEY_PATTERNS = [
    re.compile(r"prompt", re.IGNORECASE),
    re.compile(r"messages?", re.IGNORECASE),
    re.compile(r"payload", re.IGNORECASE),
    re.compile(r"request_body", re.IGNORECASE),
    re.compile(r"response_body", re.IGNORECASE),
    re.compile(r"headers?", re.IGNORECASE),
    re.compile(r"authorization", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"cookie", re.IGNORECASE),
]


def _looks_unsafe_key(k: str) -> bool:
    return any(p.search(k) for p in UNSAFE_KEY_PATTERNS)


def _drop_dotpath(obj: dict[str, Any], dotpath: str) -> None:
    parts = dotpath.split(".")
    cur: Any = obj
    for part in parts[:-1]:
        if not isinstance(cur, dict) or part not in cur:
            return
        cur = cur[part]
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def _normalize_endpoint_norm(v: Any) -> Any:
    # If someone accidentally put a raw URL, strip querystring.
    if not isinstance(v, str):
        return v
    if "?" in v:
        v = v.split("?", 1)[0]
    return v


def scrub_event(ev: dict[str, Any], extra_drop: list[str], keep_keys: list[str] | None, strict: bool) -> dict[str, Any]:
    if keep_keys:
        kept = {k: ev.get(k) for k in keep_keys if k in ev}
        ev = kept

    # Drop unsafe top-level keys by heuristic
    unsafe_found = [k for k in list(ev.keys()) if _looks_unsafe_key(k)]
    if unsafe_found and strict:
        raise ValueError(f"Unsafe keys present: {unsafe_found}")
    for k in unsafe_found:
        ev.pop(k, None)

    # Drop known nested keys if present
    for dp in [
        "request.headers",
        "response.headers",
        "request.body",
        "response.body",
        "outcome.headers",
        "outcome.response_headers",
        "outcome.request_headers",
    ]:
        _drop_dotpath(ev, dp)

    # Apply user-provided drops
    for dp in extra_drop:
        _drop_dotpath(ev, dp)

    # Normalize endpoint_norm
    tgt = ev.get("target")
    if isinstance(tgt, dict) and "endpoint_norm" in tgt:
        tgt["endpoint_norm"] = _normalize_endpoint_norm(tgt.get("endpoint_norm"))

    return ev


def scrub_jsonl(
    in_path: Path,
    out_path: Path | None,
    drop_keys: list[str],
    keep_keys: list[str],
    strict: bool,
) -> int:
    out_f = open(out_path, "w", encoding="utf-8") if out_path else sys.stdout
    n = 0
    with open(in_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                if not isinstance(ev, dict):
                    raise ValueError("JSON line is not an object")
                ev2 = scrub_event(ev, extra_drop=drop_keys, keep_keys=keep_keys or None, strict=strict)
                out_f.write(json.dumps(ev2, ensure_ascii=False) + "\n")
                n += 1
            except Exception as e:
                raise RuntimeError(f"scrub failed on line {line_no}: {e}") from e
    if out_path:
        out_f.close()
    return 0

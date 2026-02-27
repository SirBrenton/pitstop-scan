from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema


def _load_schema(schema_path: Path) -> dict[str, Any]:
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_jsonl(jsonl_path: Path, schema_path: Path, max_errors: int = 20) -> bool:
    schema = _load_schema(schema_path)
    validator = jsonschema.Draft202012Validator(schema)

    errors = 0
    ok = True
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception as e:
                print(f"[INVALID_JSON] line={line_no} err={e}")
                ok = False
                errors += 1
                if errors >= max_errors:
                    return False
                continue

            for err in validator.iter_errors(ev):
                ok = False
                errors += 1
                path = ".".join(str(p) for p in err.path) if err.path else "<root>"
                print(f"[SCHEMA_FAIL] line={line_no} path={path} msg={err.message}")
                if errors >= max_errors:
                    return False

    return ok

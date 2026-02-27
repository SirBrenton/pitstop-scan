import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Schema not found: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in {path}: {e}")


def _build_registry(schemas_dir: Path) -> Registry:
    """
    Preload all schemas in ./schemas into a referencing.Registry keyed by their $id.
    This enables resolution for refs like pitstop://schemas/decision_event.v1.
    """
    reg = Registry()
    if not schemas_dir.exists():
        return reg

    for p in sorted(schemas_dir.glob("*.json*")):
        obj = _load_json(p)
        sid = obj.get("$id")
        if sid:
            reg = reg.with_resource(sid, Resource.from_contents(obj))
    return reg


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield i, json.loads(line)
            except json.JSONDecodeError as e:
                yield i, {"__json_error__": str(e), "__raw__": line}


def validate_jsonl(jsonl_path: Path, schema_path: Path) -> int:
    if not jsonl_path.exists():
        print(f"Input not found: {jsonl_path}", file=sys.stderr)
        return 2

    # Load the root schema (which may contain $ref/oneOf)
    schema = _load_json(schema_path)

    # Build registry from ./schemas so pitstop:// $id refs can resolve
    schemas_dir = Path("schemas")
    reg = _build_registry(schemas_dir)

    # Important: pass registry=reg so Draft202012Validator can resolve $ref
    v = Draft202012Validator(schema, registry=reg)

    total = 0
    bad = 0
    bad_json = 0

    for line_no, obj in _iter_jsonl(jsonl_path):
        total += 1

        if "__json_error__" in obj:
            bad += 1
            bad_json += 1
            print(f"[line {line_no}] invalid json: {obj['__json_error__']}", file=sys.stderr)
            continue

        errs = sorted(v.iter_errors(obj), key=lambda e: (list(e.path), e.message))
        if errs:
            bad += 1
            print(f"[line {line_no}] schema violations:", file=sys.stderr)
            for e in errs[:5]:
                path = ".".join(str(p) for p in e.path) if e.path else "<root>"
                print(f"  - {path}: {e.message}", file=sys.stderr)

    ok = total - bad
    print(f"validated={total} ok={ok} bad={bad} bad_json={bad_json}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    p = argparse.ArgumentParser(
        prog="pitstop",
        description="Pitstop RetKit (receipt ask kit + schema helpers)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("help", help="Show help")

    pv = sub.add_parser("validate", help="Validate receipts JSONL against receipt_event.v1 schema")
    pv.add_argument(
        "jsonl",
        nargs="?",
        default="input/exhaust.jsonl",
        help="Path to receipts JSONL (default: input/exhaust.jsonl)",
    )
    pv.add_argument(
        "--schema",
        default="schemas/receipt_event.v1.json",
        help="Path to schema JSON (default: schemas/receipt_event.v1.json)",
    )

    args = p.parse_args(argv)

    if args.cmd == "help":
        p.print_help()
        return 0

    if args.cmd == "validate":
        return validate_jsonl(Path(args.jsonl), Path(args.schema))

    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
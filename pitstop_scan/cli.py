from __future__ import annotations

import argparse
from pathlib import Path

from .intake import run_intake
from .scan import run_scan


def _scan_cmd(in_path: Path, out_dir: Path) -> int:
    if not in_path.exists():
        print(f"ERROR: missing input file: {in_path}")
        print("Fix: put your JSONL at input/exhaust.jsonl, or run: make demo")
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    run_scan(in_path=in_path, out_dir=out_dir)
    return 0


def _intake_cmd(in_path: Path, out_dir: Path, run_scan_after: bool) -> int:
    if not in_path.exists():
        print(f"ERROR: missing input file: {in_path}")
        return 2
    return run_intake(in_path=in_path, out_dir=out_dir, run_scan_after=run_scan_after)


def _validate_cmd(in_path: Path, schema_path: Path) -> int:
    """
    Validates JSONL against a JSON Schema file.

    Requires: pip install jsonschema (or include it in requirements.txt)
    """
    import json
    from jsonschema import Draft202012Validator

    if not in_path.exists():
        print(f"ERROR: missing input file: {in_path}")
        return 2
    if not schema_path.exists():
        print(f"ERROR: missing schema file: {schema_path}")
        return 2

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    v = Draft202012Validator(schema)

    n = 0
    seen_versions: set[str] = set()

    with in_path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            n += 1
            where = f"{in_path}:{i}"

            try:
                obj = json.loads(line)
            except json.JSONDecodeError as ex:
                print(f"{where}: invalid JSON: {ex}")
                return 2

            if not isinstance(obj, dict):
                print(f"{where}: event must be an object (got {type(obj).__name__})")
                return 2

            errors = sorted(v.iter_errors(obj), key=lambda e: list(e.path))
            if errors:
                e0 = errors[0]
                path = ".".join(str(p) for p in e0.path) if e0.path else "<root>"
                print(f"{where}: schema violation at {path}: {e0.message}")
                return 2

            sv = obj.get("schema_version")
            if isinstance(sv, str):
                seen_versions.add(sv)

    if n == 0:
        print(f"{in_path}: no events found (empty JSONL)")
        return 2

    versions = ", ".join(sorted(seen_versions)) if seen_versions else "<unknown>"
    print(f"OK: validate ({n} events), schema_versions={versions}")
    return 0


def main() -> int:
    """
    Back-compat:
      python -m pitstop_scan.cli --in <jsonl> --out <dir>
    New:
      python -m pitstop_scan.cli scan --in <jsonl> --out <dir>
      python -m pitstop_scan.cli intake --in <raw_blob> --out <dir> [--run-scan]
      python -m pitstop_scan.cli validate --in <jsonl> --schema <schema.json>
    """
    ap = argparse.ArgumentParser(description="Pitstop Scan CLI")
    sub = ap.add_subparsers(dest="cmd")

    # Explicit scan subcommand
    ap_scan = sub.add_parser("scan", help="Run scan on an exhaust JSONL file")
    ap_scan.add_argument("--in", dest="in_path", required=True, help="Path to exhaust.jsonl")
    ap_scan.add_argument("--out", dest="out_dir", required=True, help="Output directory")

    # Intake subcommand
    ap_intake = sub.add_parser(
        "intake",
        help="Convert a raw failure blob into a scan-ready artifact pack",
    )
    ap_intake.add_argument("--in", dest="in_path", required=True, help="Path to raw text/json/log input")
    ap_intake.add_argument("--out", dest="out_dir", required=True, help="Output directory for artifact pack")
    ap_intake.add_argument(
        "--run-scan",
        action="store_true",
        help="Run scan after generating the artifact pack",
    )

    # Validate subcommand
    ap_val = sub.add_parser("validate", help="Validate JSONL against a JSON Schema file")
    ap_val.add_argument("--in", dest="in_path", required=True, help="Path to JSONL file")
    ap_val.add_argument("--schema", dest="schema_path", required=True, help="Path to schema json")

    # Back-compat flags (no subcommand)
    ap.add_argument("--in", dest="in_path_compat", help=argparse.SUPPRESS)
    ap.add_argument("--out", dest="out_dir_compat", help=argparse.SUPPRESS)

    args = ap.parse_args()

    # Back-compat path: no cmd, but --in/--out present => scan
    if args.cmd is None:
        if args.in_path_compat and args.out_dir_compat:
            return _scan_cmd(Path(args.in_path_compat), Path(args.out_dir_compat))
        ap.print_help()
        return 2

    if args.cmd == "scan":
        return _scan_cmd(Path(args.in_path), Path(args.out_dir))

    if args.cmd == "intake":
        return _intake_cmd(Path(args.in_path), Path(args.out_dir), args.run_scan)

    if args.cmd == "validate":
        return _validate_cmd(Path(args.in_path), Path(args.schema_path))

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
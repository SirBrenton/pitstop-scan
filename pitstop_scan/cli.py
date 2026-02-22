from __future__ import annotations

import argparse
from pathlib import Path

from .scan import run_scan


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Pitstop Scan on an exhaust JSONL file.")
    ap.add_argument("--in", dest="in_path", required=True, help="Path to exhaust.jsonl")
    ap.add_argument("--out", dest="out_dir", required=True, help="Output directory")
    args = ap.parse_args()

    in_path = Path(args.in_path)
    out_dir = Path(args.out_dir)

    if not in_path.exists():
        print(f"ERROR: missing input file: {in_path}")
        print("Fix: put your JSONL at input/exhaust.jsonl, or run: make demo")
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    run_scan(in_path=in_path, out_dir=out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
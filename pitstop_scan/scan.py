from __future__ import annotations

import csv
import json
import statistics
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .contracts import validate_event
from .report import render_report


def percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if p <= 0:
        return float(sorted_vals[0])
    if p >= 100:
        return float(sorted_vals[-1])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return float(d0 + d1)


def load_events(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {i}: {e}") from e
            validate_event(obj, line_no=i)
            events.append(obj)
    return events


def write_placeholders(out_dir: Path) -> None:
    # hazards.csv placeholder
    hazards_path = out_dir / "hazards.csv"
    with hazards_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["note"])
        w.writerow(["MVP stub: hazards ranking implemented in pitstop-commons engine; scan repo will delegate."])

    # signatures.csv placeholder
    sig_path = out_dir / "signatures.csv"
    with sig_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["note"])
        w.writerow(["MVP stub: signature clustering implemented in pitstop-commons engine; scan repo will delegate."])


def write_pack(out_dir: Path) -> Path:
    pack_path = out_dir / "pitstop_pack_agg.zip"
    files = ["report.md", "hazards.csv", "signatures.csv", "summary.json"]
    with zipfile.ZipFile(pack_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name in files:
            p = out_dir / name
            if p.exists():
                z.write(p, arcname=name)
    return pack_path


def run_scan(in_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    events = load_events(in_path)

    latencies = [float(e["latency_ms"]) for e in events]
    lat_sorted = sorted(latencies)

    ok = [e for e in events if e.get("status") == "ok"]
    fails = [e for e in events if e.get("status") != "ok"]

    # breach = latency > budget_ms (when present)
    breaches = []
    for e in events:
        b = e.get("budget_ms")
        if b is None:
            continue
        if float(e["latency_ms"]) > float(b):
            breaches.append(e)

    summary = {
        "events": len(events),
        "ok": len(ok),
        "fail": len(fails),
        "ok_rate": (len(ok) / len(events)) if events else 0.0,
        "breach_rate": (len(breaches) / len(events)) if events else 0.0,
        "retries_mean": statistics.mean([float(e.get("retries", 0)) for e in events]) if events else 0.0,
        "latency_ms": {
            "mean": statistics.mean(latencies) if latencies else 0.0,
            "p50": percentile(lat_sorted, 50),
            "p95": percentile(lat_sorted, 95),
            "p99": percentile(lat_sorted, 99),
        },
    }

    # write summary.json
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    # report.md
    report_md = render_report(in_path=in_path, summary=summary)
    (out_dir / "report.md").write_text(report_md, encoding="utf-8")

    # placeholders (until commons delegation)
    write_placeholders(out_dir)

    # pack
    write_pack(out_dir)
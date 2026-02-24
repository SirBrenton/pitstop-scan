from __future__ import annotations

import csv
import json
import statistics
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .report import render_report
from .schema_validate import load_schema, validate_against_schema

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


def load_events(path: Path, *, schema_path: Path) -> List[Dict[str, Any]]:
    # Validate each JSONL line against the canonical receipt schema.
    # This replaces the old ad-hoc "contracts.validate_event" shape checks.
    schema = load_schema(schema_path)
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
            validate_against_schema(obj, schema=schema, line_no=i)
            events.append(obj)
    return events


def _sig_key(e: Dict[str, Any]) -> Tuple[str, str, str, str, str, str]:
    """
    Signature = tool/operation + coarse buckets.
    Missing buckets become "na".
    """
    tool = str(e.get("tool_id", "na"))
    op = str(e.get("operation", "na"))

    ctx = e.get("context_signature") or {}
    # allow either nested buckets or top-level buckets
    env = str(ctx.get("env_bucket") or e.get("env_bucket") or "na")
    region = str(ctx.get("region_bucket") or e.get("region_bucket") or "na")
    conc = str(ctx.get("concurrency_bucket") or e.get("concurrency_bucket") or "na")
    tier = str(ctx.get("tenant_tier") or e.get("tenant_tier") or "na")

    return (tool, op, env, region, conc, tier)


def _is_ok(e: Dict[str, Any]) -> bool:
    out = e.get("outcome") or {}
    return out.get("status") == "ok"


def _is_breach(e: Dict[str, Any]) -> bool:
    b = (e.get("budget") or {}).get("deadline_ms")
    if b is None:
        return False
    cost = e.get("cost") or {}
    return float(cost.get("latency_ms", 0.0)) > float(b)

def _is_budgeted(e: Dict[str, Any]) -> bool:
    return (e.get("budget") or {}).get("deadline_ms") is not None

def _pain_score(count: int, fail_count: int, breach_count: int, p95_ms: float) -> float:
    """
    Simple, explainable ranking heuristic.
    - breaches: high weight
    - failures: medium weight
    - p95 latency: small weight (scaled)
    """
    return (breach_count * 10.0) + (fail_count * 5.0) + (p95_ms / 1000.0)


def compute_signature_rollups(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str, str, str, str, str], List[Dict[str, Any]]] = {}
    for e in events:
        groups.setdefault(_sig_key(e), []).append(e)

    rollups: List[Dict[str, Any]] = []
    for key, evs in groups.items():
        lat = sorted(float((e.get("cost") or {}).get("latency_ms", 0.0)) for e in evs)
        retries = [float((e.get("cost") or {}).get("retries", 0)) for e in evs]
        ok_count = sum(1 for e in evs if _is_ok(e))
        fail_count = len(evs) - ok_count
        budgeted_count = sum(1 for e in evs if _is_budgeted(e))
        breach_count = sum(1 for e in evs if _is_breach(e))

        # error class counts (only for non-ok)
        err_counts: Dict[str, int] = {}
        for e in evs:
            if _is_ok(e):
                continue
            out = e.get("outcome") or {}
            ec = out.get("error_class") or "unknown"
            err_counts[str(ec)] = err_counts.get(str(ec), 0) + 1

        tool, op, env, region, conc, tier = key
        rollups.append(
            {
                "tool": tool,
                "op": op,
                "env": env,
                "region": region,
                "concurrency_bucket": conc,
                "tier": tier,
                "count": len(evs),
                "ok": ok_count,
                "fail": fail_count,
                "ok_rate": (ok_count / len(evs)) if evs else 0.0,
                "budgeted_events": budgeted_count,
                "breach": breach_count,
                "breach_rate": (breach_count / budgeted_count) if budgeted_count else 0.0,
                "retries_mean": statistics.mean(retries) if retries else 0.0,
                "lat_mean": statistics.mean(lat) if lat else 0.0,
                "lat_p50": percentile(lat, 50),
                "lat_p95": percentile(lat, 95),
                "lat_p99": percentile(lat, 99),
                "top_error_class": (max(err_counts.items(), key=lambda kv: kv[1])[0] if err_counts else ""),
                "error_class_counts": err_counts,  # keep in-memory; not written verbatim to CSV
            }
        )

    # hazards ranking = sort by pain score
    for r in rollups:
        r["pain_score"] = _pain_score(r["count"], r["fail"], r["breach"], float(r["lat_p95"]))
    rollups.sort(key=lambda r: float(r["pain_score"]), reverse=True)
    return rollups


def write_signatures_csv(out_dir: Path, rollups: List[Dict[str, Any]]) -> None:
    path = out_dir / "signatures.csv"
    cols = [
        "tool",
        "op",
        "env",
        "region",
        "concurrency_bucket",
        "tier",
        "count",
        "ok",
        "fail",
        "ok_rate",
        "breach",
        "breach_rate",
        "retries_mean",
        "lat_p50",
        "lat_p95",
        "lat_p99",
        "top_error_class",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rollups:
            w.writerow({c: r.get(c, "") for c in cols})


def write_hazards_csv(out_dir: Path, rollups: List[Dict[str, Any]]) -> None:
    """
    hazards.csv is essentially signatures.csv + pain_score (rank).
    Kept separate so humans know what to look at first.
    """
    path = out_dir / "hazards.csv"
    cols = [
        "rank",
        "pain_score",
        "tool",
        "op",
        "env",
        "region",
        "concurrency_bucket",
        "tier",
        "count",
        "fail",
        "budgeted_events",
        "breach",
        "breach_rate",
        "lat_p95",
        "retries_mean",
        "top_error_class",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for i, r in enumerate(rollups, start=1):
            row = {c: r.get(c, "") for c in cols}
            row["rank"] = i
            w.writerow(row)


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

    # Canonical receipt schema lives in-repo (copied from commons for now).
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "decision_event.v1.schema.json"
    events = load_events(in_path, schema_path=schema_path)

    latencies = [float((e.get("cost") or {}).get("latency_ms", 0.0)) for e in events]
    lat_sorted = sorted(latencies)

    ok = [e for e in events if _is_ok(e)]
    fails = [e for e in events if not _is_ok(e)]

    budgeted = [e for e in events if _is_budgeted(e)]
    breaches = [e for e in events if _is_breach(e)]

    rollups = compute_signature_rollups(events)
    top_hazards = rollups[:5]

    # keep summary.json small + stable: only include fields the report needs
    top_hazards_for_report = [
        {
            "tool": h.get("tool"),
            "op": h.get("op"),
            "env": h.get("env"),
            "region": h.get("region"),
            "concurrency_bucket": h.get("concurrency_bucket"),
            "tier": h.get("tier"),
            "count": h.get("count"),
            "fail": h.get("fail"),
            "budgeted_events": h.get("budgeted_events"),
            "breach": h.get("breach"),
            "breach_rate": h.get("breach_rate"),
            "lat_p95": h.get("lat_p95"),
            "retries_mean": h.get("retries_mean"),
            "top_error_class": h.get("top_error_class"),
            "pain_score": h.get("pain_score"),
        }
        for h in top_hazards
    ]

    summary = {
        "events": len(events),
        "ok": len(ok),
        "fail": len(fails),
        "ok_rate": (len(ok) / len(events)) if events else 0.0,
        "budgeted_events": len(budgeted),
        "breach_rate": (len(breaches) / len(budgeted)) if budgeted else 0.0,
        "retries_mean": statistics.mean([float((e.get("cost") or {}).get("retries", 0)) for e in events]) if events else 0.0,
        "latency_ms": {
            "mean": statistics.mean(latencies) if latencies else 0.0,
            "p50": percentile(lat_sorted, 50),
            "p95": percentile(lat_sorted, 95),
            "p99": percentile(lat_sorted, 99),
        },
        # NEW: include top hazards in summary so report can render them
        "top_hazards": top_hazards_for_report,
    }

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    report_md = render_report(in_path=in_path, summary=summary)
    (out_dir / "report.md").write_text(report_md, encoding="utf-8")

    # NEW: real outputs
    write_signatures_csv(out_dir, rollups)
    write_hazards_csv(out_dir, rollups)

    write_pack(out_dir)
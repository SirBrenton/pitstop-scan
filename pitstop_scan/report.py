from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def _fmt_sig(h: Dict[str, Any]) -> str:
    parts = [
        f'{h.get("tool","na")}/{h.get("op","na")}',
        f'env={h.get("env","na")}',
        f'region={h.get("region","na")}',
        f'conc={h.get("concurrency_bucket","na")}',
        f'tier={h.get("tier","na")}',
    ]
    return " ".join(parts)


def _render_top_hazards(top: List[Dict[str, Any]]) -> str:
    if not top:
        return ""

    lines: List[str] = []
    lines.append("## Top hazards (ranked)")
    lines.append("")
    lines.append("> A “hazard” is a signature where failures and/or budget breaches concentrate (highest leverage fixes first).")
    lines.append("")

    for i, h in enumerate(top, start=1):
        count = int(h.get("count", 0) or 0)
        fail = int(h.get("fail", 0) or 0)
        breach = int(h.get("breach", 0) or 0)
        breach_rate = float(h.get("breach_rate", 0.0) or 0.0)
        p95 = float(h.get("lat_p95", 0.0) or 0.0)
        retries_mean = float(h.get("retries_mean", 0.0) or 0.0)
        top_err = str(h.get("top_error_class", "") or "")

        if top_err in ("rate_limit_429",) or top_err.startswith("rate_limit"):
            do = "Do: cap retries + 429 backoff/jitter (don’t brute-force)."
        elif top_err in ("auth_401",) or top_err.startswith("auth"):
            do = "Do: never retry auth failures → refresh creds / escalate."
        elif breach > 0 and breach_rate >= 0.5:
            do = "Do: enforce a hard per-attempt deadline (≈ budget.deadline_ms) + fallback."
        elif fail > 0:
            do = "Do: cap retries + add backoff; inspect error_class mix."
        else:
            do = "Do: monitor; no immediate action."

        line = (
            f"- **#{i}** `{_fmt_sig(h)}` — n={count}, fail={fail}, "
            f"breach={breach} ({pct(breach_rate)}), p95={p95:.0f}ms, "
            f"retries_mean={retries_mean:.2f}"
        )
        if top_err:
            line += f", top_error=`{top_err}`"

        lines.append(line)
        lines.append(f"  - {do}")

    lines.append("")
    lines.append("(See `hazards.csv` for the full ranked list, and `signatures.csv` for rollups.)")
    lines.append("")
    return "\n".join(lines)

def join_blocks(*blocks: str) -> str:
    return "\n".join([b.rstrip() for b in blocks if b.strip()]) + "\n"

def patch_plan_mailto_url() -> str:
    # Keep it clean: clickable email without the “junk”.
    return "mailto:brentondwilliams@gmail.com?subject=Pitstop%20Scan%20Patch%20Plan"


def _render_outcome_line(top_hazards: List[Dict[str, Any]], events: int) -> str:
    """
    Keep it true + useful:
    - points them at the ranked hazards
    - says fixing top few is highest leverage
    """
    n = min(3, len(top_hazards))
    if n == 0:
        return ""

    if events < 20:
        return (
            f"**Outcome:** Start with the top **{n}** hazards below — "
            "they’re the highest-leverage fixes in this sample.\n\n"
        )

    return (
        f"**Outcome:** Start with the top **{n}** hazards below — "
        "fixing these first usually collapses tail latency and retries fastest.\n\n"
    )

def _render_default_guardrails() -> str:
    return "\n".join(
        [
            "",
            "## Default guardrails (baseline)",
            "",
            "Apply these everywhere, then implement the hazard-specific “Do:” actions above in order:",
            "",
            "- **Deadlines:** budget-aligned hard deadline + fallback (don’t block indefinitely).",
            "- **Retry policy:** cap retries; **429 backoff + jitter**; don’t brute-force.",
            "- **Never-retry:** auth failures (401/403) and other non-retriables → refresh/escalate.",
            "",
            "",
        ]
    )

def render_report(in_path: Path, summary: Dict[str, Any]) -> str:
    events = int(summary["events"])
    ok = int(summary["ok"])
    fail = int(summary["fail"])

    lat = summary["latency_ms"]
    ok_rate = float(summary["ok_rate"])
    breach_rate = float(summary["breach_rate"])
    budgeted_events = int(summary.get("budgeted_events", 0) or 0)

    fail_rate = (fail / events) if events else 0.0

    if fail_rate >= 0.5:
        regime = "failure-dominant"
    elif breach_rate >= 0.5:
        regime = "breach-dominant"
    else:
        regime = "mixed"

    top_hazards = summary.get("top_hazards", []) or []
    hazards_block = _render_top_hazards(top_hazards)
    outcome_block = _render_outcome_line(top_hazards, events)

    retries_mean = float(summary.get("retries_mean", 0.0) or 0.0)
    explainer = _render_regime_explainer(
        regime,
        fail_rate=fail_rate,
        breach_rate=breach_rate,
        retries_mean=retries_mean,
    )

    mailto_url = patch_plan_mailto_url()
    default_guardrails = _render_default_guardrails()

    return f"""# Pitstop Scan — Reliability Snapshot (v0)

**Input:** {in_path}
**Result:** **{regime}** in this sample — {explainer}

{outcome_block}## Summary stats
- events: **{events}** (ok={ok}, fail={fail})
- ok_rate: **{pct(ok_rate)}**
- budgeted_events: **{budgeted_events}**
- breach_rate (latency > budget, budgeted events only): **{pct(breach_rate)}**
- retries_mean: **{retries_mean:.3f}**
- latency_ms: mean={float(lat["mean"]):.1f} p50={float(lat["p50"]):.1f} p95={float(lat["p95"]):.1f} p99={float(lat["p99"]):.1f}

{join_blocks(hazards_block, default_guardrails)}
## Share safely (derived outputs only)
...
"""

def _render_regime_explainer(regime: str, *, fail_rate: float, breach_rate: float, retries_mean: float) -> str:
    if regime == "failure-dominant":
        return (
            f"Most pain is **hard failures** (fail_rate={pct(fail_rate)}), not budget breaches "
            f"(breach_rate={pct(breach_rate)}). Retries_mean={retries_mean:.2f}."
        )
    if regime == "breach-dominant":
        return (
            f"Most pain is **budget breaches / tail latency** (breach_rate={pct(breach_rate)}), even when calls succeed. "
            f"fail_rate={pct(fail_rate)}. Retries_mean={retries_mean:.2f}."
        )
    return (
        f"Pain is **mixed** (fail_rate={pct(fail_rate)}, breach_rate={pct(breach_rate)}). "
        f"Retries_mean={retries_mean:.2f}."
    )

    mailto_url = patch_plan_mailto_url()

    default_guardrails = _render_default_guardrails()

    return f"""# Pitstop Scan — Reliability Snapshot (v0)

**Input:** {in_path}
**Result:** **{regime}** in this sample — most pain is latency exceeding budget (even when calls succeed), not hard failures.

{outcome_block}## Summary stats
- events: **{events}** (ok={ok}, fail={fail})
- ok_rate: **{pct(ok_rate)}**
- budgeted_events: **{budgeted_events}**
- breach_rate (latency > budget, budgeted events only): **{pct(breach_rate)}**
- retries_mean: **{float(summary["retries_mean"]):.3f}**
- latency_ms: mean={float(lat["mean"]):.1f} p50={float(lat["p50"]):.1f} p95={float(lat["p95"]):.1f} p99={float(lat["p99"]):.1f}

{join_blocks(hazards_block, default_guardrails)}
## Share safely (derived outputs only)

If you want help, send the **Pitstop Pack** (derived aggregates):

- `output/pitstop_pack_agg.zip` (recommended)
- or: `output/report.md`, `output/hazards.csv`, `output/signatures.csv`, `output/summary.json`

## Optional: 48-hour Patch Plan (human)

Email the pack to:
[brentondwilliams@gmail.com]({mailto_url})

Include:
- Context: [stack]
- Scope: [workflow / service name]
- Goal: [reduce 429s | reduce p99 | fix failover | etc.]

**You get:** a 1-page fix order + copy/paste guardrails mapped to your top hazards.
"""

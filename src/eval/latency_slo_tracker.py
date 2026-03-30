#!/usr/bin/env python3
"""
latency_slo_tracker.py — Tracks inference latency SLOs for OCI Robot Cloud.

Monitors real-time latency against SLO targets per partner tier, produces
SLO burn-rate alerts, and generates weekly compliance reports. Essential for
enterprise contracts requiring <250ms p95 guarantees.

Usage:
    python src/eval/latency_slo_tracker.py --mock --output /tmp/latency_slo_tracker.html
    python src/eval/latency_slo_tracker.py --window 7d --partner agility_robotics
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path


# ── SLO definitions ────────────────────────────────────────────────────────────

@dataclass
class SLOTarget:
    tier: str
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    availability_pct: float   # uptime SLO
    error_budget_pct: float   # 1 - availability


SLO_TIERS = {
    "pilot":      SLOTarget("pilot",      350, 450, 500, 650, 99.0, 1.0),
    "growth":     SLOTarget("growth",     250, 350, 400, 550, 99.5, 0.5),
    "enterprise": SLOTarget("enterprise", 200, 280, 300, 420, 99.9, 0.1),
}

PARTNERS = {
    "agility_robotics": ("enterprise", 0.92),  # tier, health factor
    "figure_ai":        ("growth",     0.85),
    "boston_dynamics":  ("enterprise", 0.78),
    "pilot_customer":   ("pilot",      0.95),
}


@dataclass
class LatencyWindow:
    partner: str
    tier: str
    window_hours: int
    n_requests: int
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    error_rate: float
    availability_pct: float
    slo_p95_target: float
    p95_compliant: bool
    avail_compliant: bool
    error_budget_remaining_pct: float
    burn_rate: float              # how fast error budget being consumed
    alert_level: str              # ok / warning / critical


def simulate_latency_window(partner: str, tier: str, health: float,
                             window_hr: int, seed: int) -> LatencyWindow:
    rng = random.Random(seed)
    slo = SLO_TIERS[tier]

    # Base latency scales with health factor
    base = 200 / health
    p50 = max(80, rng.gauss(base, base * 0.08))
    p90 = p50 * rng.uniform(1.30, 1.50)
    p95 = p50 * rng.uniform(1.45, 1.75)
    p99 = p50 * rng.uniform(1.85, 2.40)

    n_req = int(window_hr * rng.uniform(40, 120))
    error_rate = max(0, rng.gauss(0.008 * (1 / health), 0.003))
    avail = max(98.0, min(100.0, 100.0 - error_rate * 100 * rng.uniform(0.8, 1.2)))

    p95_ok = p95 <= slo.p95_ms
    avail_ok = avail >= slo.availability_pct

    # Error budget: how much of the allowed downtime has been consumed
    downtime_allowed_min = (1 - slo.availability_pct / 100) * window_hr * 60
    downtime_actual_min = (1 - avail / 100) * window_hr * 60
    eb_remaining = max(0.0, 1.0 - downtime_actual_min / max(downtime_allowed_min, 0.01))
    burn_rate = downtime_actual_min / max(downtime_allowed_min, 0.001)

    if burn_rate > 2.0 or not p95_ok:
        alert = "critical"
    elif burn_rate > 1.0 or not avail_ok:
        alert = "warning"
    else:
        alert = "ok"

    return LatencyWindow(
        partner=partner,
        tier=tier,
        window_hours=window_hr,
        n_requests=n_req,
        p50_ms=round(p50, 1),
        p90_ms=round(p90, 1),
        p95_ms=round(p95, 1),
        p99_ms=round(p99, 1),
        error_rate=round(error_rate, 5),
        availability_pct=round(avail, 3),
        slo_p95_target=slo.p95_ms,
        p95_compliant=p95_ok,
        avail_compliant=avail_ok,
        error_budget_remaining_pct=round(eb_remaining * 100, 1),
        burn_rate=round(burn_rate, 3),
        alert_level=alert,
    )


def compute_trend(windows_7d: LatencyWindow, windows_1d: LatencyWindow) -> str:
    delta = windows_1d.p95_ms - windows_7d.p95_ms
    if delta > 30:  return "degrading"
    if delta < -20: return "improving"
    return "stable"


# ── HTML report ────────────────────────────────────────────────────────────────

def render_html(data_7d: list[LatencyWindow], data_1d: list[LatencyWindow]) -> str:
    ALERT_COLORS = {"ok": "#22c55e", "warning": "#f59e0b", "critical": "#ef4444"}
    PARTNER_COLORS = {
        "agility_robotics": "#C74634", "figure_ai": "#3b82f6",
        "boston_dynamics": "#22c55e",  "pilot_customer": "#f59e0b"
    }

    critical_count = sum(1 for w in data_7d if w.alert_level == "critical")
    compliant_count = sum(1 for w in data_7d if w.p95_compliant and w.avail_compliant)
    avg_p95 = sum(w.p95_ms for w in data_7d) / len(data_7d)
    min_budget = min(w.error_budget_remaining_pct for w in data_7d)

    # SVG: p95 latency vs SLO per partner
    w, h = 520, 150
    n = len(data_7d)
    group_w = (w - 40) / n
    max_lat = max(max(w.p95_ms for w in data_7d), max(s.p95_ms for s in SLO_TIERS.values())) * 1.15

    svg = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg += f'<line x1="30" y1="{h-20}" x2="{w}" y2="{h-20}" stroke="#334155" stroke-width="1"/>'

    for i, win in enumerate(data_7d):
        gx = 30 + i * group_w
        slo = SLO_TIERS[win.tier]
        bar_w = group_w * 0.5

        # Actual p95 bar
        bh = win.p95_ms / max_lat * (h - 40)
        col = ALERT_COLORS[win.alert_level]
        svg += (f'<rect x="{gx:.1f}" y="{h-20-bh:.1f}" width="{bar_w:.1f}" '
                f'height="{bh:.1f}" fill="{col}" rx="2" opacity="0.85"/>')
        # SLO target line
        slo_y = h - 20 - slo.p95_ms / max_lat * (h - 40)
        svg += (f'<line x1="{gx:.1f}" y1="{slo_y:.1f}" x2="{gx+group_w*0.8:.1f}" '
                f'y2="{slo_y:.1f}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,2"/>')

        pname = win.partner.replace("_", " ").split()[0][:8]
        svg += (f'<text x="{gx+group_w/2:.1f}" y="{h-4}" fill="{PARTNER_COLORS.get(win.partner,\"#94a3b8\")}" '
                f'font-size="8.5" text-anchor="middle">{pname}</text>')
        svg += (f'<text x="{gx+bar_w/2:.1f}" y="{h-22-bh:.1f}" fill="{col}" '
                f'font-size="8" text-anchor="middle">{win.p95_ms:.0f}</text>')

    svg += '</svg>'

    # SVG: error budget remaining gauge-style bars
    w2, h2 = 380, 110
    svg_budget = f'<svg width="{w2}" height="{h2}" style="background:#0f172a;border-radius:8px">'
    bh2 = (h2 - 20) / len(data_7d) - 4
    for i, win in enumerate(data_7d):
        y = 10 + i * (bh2 + 4)
        pct = win.error_budget_remaining_pct
        bw = pct / 100.0 * (w2 - 130)
        col = "#22c55e" if pct > 50 else "#f59e0b" if pct > 20 else "#ef4444"
        pname = win.partner.replace("_", " ")[:16]
        svg_budget += (f'<rect x="120" y="{y}" width="{bw:.1f}" height="{bh2:.1f}" '
                       f'fill="{col}" rx="2" opacity="0.85"/>')
        svg_budget += (f'<text x="118" y="{y+bh2*0.75:.1f}" fill="#94a3b8" font-size="9" '
                       f'text-anchor="end">{pname}</text>')
        svg_budget += (f'<text x="{123+bw:.1f}" y="{y+bh2*0.75:.1f}" fill="{col}" '
                       f'font-size="9">{pct:.1f}%</text>')
    svg_budget += '</svg>'

    # Main table
    rows = ""
    for w7, w1 in zip(data_7d, data_1d):
        trend = compute_trend(w7, w1)
        trend_sym = {"degrading": "↑", "improving": "↓", "stable": "→"}[trend]
        trend_col = {"degrading": "#ef4444", "improving": "#22c55e", "stable": "#94a3b8"}[trend]
        al_col = ALERT_COLORS[w7.alert_level]
        col = PARTNER_COLORS.get(w7.partner, "#94a3b8")
        slo = SLO_TIERS[w7.tier]
        p95_col = "#22c55e" if w7.p95_compliant else "#ef4444"
        budget_col = "#22c55e" if w7.error_budget_remaining_pct > 50 else "#f59e0b" if w7.error_budget_remaining_pct > 20 else "#ef4444"

        rows += (f'<tr>'
                 f'<td style="color:{col}">{w7.partner.replace("_"," ")}</td>'
                 f'<td style="color:#64748b">{w7.tier}</td>'
                 f'<td style="color:{al_col}">{"●"} {w7.alert_level}</td>'
                 f'<td style="color:#e2e8f0">{w7.p50_ms:.0f}ms</td>'
                 f'<td style="color:{p95_col}">{w7.p95_ms:.0f}ms / {w7.slo_p95_target:.0f}</td>'
                 f'<td style="color:#64748b">{w7.p99_ms:.0f}ms</td>'
                 f'<td style="color:#94a3b8">{w7.availability_pct:.3f}%</td>'
                 f'<td style="color:{budget_col}">{w7.error_budget_remaining_pct:.1f}%</td>'
                 f'<td style="color:#64748b">{w7.burn_rate:.2f}×</td>'
                 f'<td style="color:{trend_col}">{trend_sym} {trend}</td></tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Latency SLO Tracker</title>
<meta http-equiv="refresh" content="60">
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:28px;font-weight:bold}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:4px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Latency SLO Tracker</h1>
<div class="meta">
  {len(data_7d)} partners · 7-day window · auto-refresh 60s · tiers: pilot/growth/enterprise
</div>

<div class="grid">
  <div class="card"><h3>Compliant Partners</h3>
    <div class="big" style="color:{'#22c55e' if compliant_count == len(data_7d) else '#f59e0b'}">
      {compliant_count}/{len(data_7d)}
    </div></div>
  <div class="card"><h3>Critical Alerts</h3>
    <div class="big" style="color:{'#ef4444' if critical_count > 0 else '#22c55e'}">{critical_count}</div></div>
  <div class="card"><h3>Avg p95 Latency</h3>
    <div class="big" style="color:#3b82f6">{avg_p95:.0f}ms</div></div>
  <div class="card"><h3>Min Error Budget</h3>
    <div class="big" style="color:{'#ef4444' if min_budget < 20 else '#22c55e'}">{min_budget:.1f}%</div>
    <div style="color:#64748b;font-size:12px">remaining (7d)</div></div>
</div>

<div class="charts">
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">
      p95 Latency vs SLO (amber = target)
    </h3>
    {svg}
  </div>
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">
      Error Budget Remaining (7d)
    </h3>
    {svg_budget}
  </div>
</div>

<table>
  <tr><th>Partner</th><th>Tier</th><th>Alert</th><th>p50</th><th>p95 / SLO</th>
      <th>p99</th><th>Avail</th><th>Budget</th><th>Burn</th><th>Trend</th></tr>
  {rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  Burn rate >1× = consuming error budget faster than allowed. >2× = critical escalation.<br>
  SLO tiers: pilot p95≤500ms 99.0% · growth p95≤400ms 99.5% · enterprise p95≤300ms 99.9%.<br>
  Feeds sla_compliance_monitor.py for contract credit calculations.
</div>
</body></html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Latency SLO tracker")
    parser.add_argument("--mock",     action="store_true", default=True)
    parser.add_argument("--window",   default="7d")
    parser.add_argument("--partner",  default="all")
    parser.add_argument("--output",   default="/tmp/latency_slo_tracker.html")
    parser.add_argument("--seed",     type=int, default=42)
    args = parser.parse_args()

    print(f"[slo-tracker] {len(PARTNERS)} partners · window={args.window}")
    t0 = time.time()

    data_7d = [simulate_latency_window(p, tier, h, 168, args.seed + i)
               for i, (p, (tier, h)) in enumerate(PARTNERS.items())]
    data_1d = [simulate_latency_window(p, tier, h, 24, args.seed + i + 100)
               for i, (p, (tier, h)) in enumerate(PARTNERS.items())]

    print(f"\n  {'Partner':<22} {'p95 ms':>8}  {'SLO':>6}  {'Budget':>8}  {'Alert'}")
    print(f"  {'─'*22} {'─'*8}  {'─'*6}  {'─'*8}  {'─'*8}")
    for w in data_7d:
        ok = "✓" if w.p95_compliant else "✗"
        print(f"  {w.partner.replace('_',' '):<22} {w.p95_ms:>7.0f}ms  {w.slo_p95_target:>5.0f}  "
              f"{w.error_budget_remaining_pct:>6.1f}%  [{w.alert_level}] {ok}")

    print(f"\n  [{time.time()-t0:.1f}s]\n")

    html = render_html(data_7d, data_1d)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps(
        [{"partner": w.partner, "p95_ms": w.p95_ms, "slo_target": w.slo_p95_target,
          "compliant": w.p95_compliant, "budget_pct": w.error_budget_remaining_pct,
          "alert": w.alert_level} for w in data_7d], indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()

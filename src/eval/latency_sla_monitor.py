"""Inference Latency SLA Monitor — port 8165.

Tracks P50/P95/P99 inference latency against SLA targets with breach
detection and error-budget reporting.
"""

from __future__ import annotations

import math

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as _e:
    raise SystemExit(f"Missing dependency: {_e}. Install fastapi and uvicorn.") from _e

# ---------------------------------------------------------------------------
# SLA targets (ms)
# ---------------------------------------------------------------------------

SLA = {
    "p50":  {"target": 200, "label": "P50"},
    "p95":  {"target": 280, "label": "P95"},
    "p99":  {"target": 300, "label": "P99"},
    "max":  {"target": 500, "label": "Max"},
}

# ---------------------------------------------------------------------------
# Generate 30-day synthetic latency data (deterministic seed)
# ---------------------------------------------------------------------------

def _lcg(seed: int):
    """Simple linear-congruential generator for reproducibility."""
    a, c, m = 1664525, 1013904223, 2**32
    state = seed
    while True:
        state = (a * state + c) % m
        yield state / m  # float in [0,1)


_rng = _lcg(42)


def _next() -> float:
    return next(_rng)


# Build 30-day records
_BREACH_DAYS = {8, 15, 22}  # 1-indexed
DAILY_STATS: list[dict] = []

for _day in range(1, 31):
    _p50 = round(218 + _next() * 16, 1)       # 218–234 ms
    _p95 = round(261 + _next() * 17, 1)       # 261–278 ms
    if _day in _BREACH_DAYS:
        _p99_vals = {8: 312.0, 15: 308.0, 22: 321.0}
        _p99 = _p99_vals[_day]
    else:
        _p99 = round(281 + _next() * 18, 1)   # 281–299 ms
    _max = round(_p99 + 40 + _next() * 80, 1) # p99 + 40–120 ms

    _p99_status = "BREACH" if _p99 > SLA["p99"]["target"] else "PASS"
    _p50_status = "BREACH"  # always above 200ms target
    _p95_status = "PASS" if _p95 <= SLA["p95"]["target"] else "BREACH"
    _max_status = "PASS" if _max <= SLA["max"]["target"] else "BREACH"

    DAILY_STATS.append({
        "day": _day,
        "p50_ms": _p50,
        "p95_ms": _p95,
        "p99_ms": _p99,
        "max_ms": _max,
        "p50_status": _p50_status,
        "p95_status": _p95_status,
        "p99_status": _p99_status,
        "max_status": _max_status,
    })

# 30-day averages
AVG_P50 = round(sum(d["p50_ms"] for d in DAILY_STATS) / 30, 1)
AVG_P95 = round(sum(d["p95_ms"] for d in DAILY_STATS) / 30, 1)
AVG_P99 = round(sum(d["p99_ms"] for d in DAILY_STATS) / 30, 1)
AVG_MAX = round(sum(d["max_ms"] for d in DAILY_STATS) / 30, 1)

P99_BREACH_DAYS = [d["day"] for d in DAILY_STATS if d["p99_status"] == "BREACH"]
P50_BREACH_DAYS = list(range(1, 31))  # all days breach p50

SUMMARY_TABLE = [
    {"metric": "P50",  "target_ms": 200, "actual_ms": AVG_P50, "status": "BREACH", "breach_days": 30},
    {"metric": "P95",  "target_ms": 280, "actual_ms": AVG_P95, "status": "PASS",   "breach_days": 0},
    {"metric": "P99",  "target_ms": 300, "actual_ms": AVG_P99, "status": "PASS",   "breach_days": len(P99_BREACH_DAYS)},
    {"metric": "Max",  "target_ms": 500, "actual_ms": AVG_MAX, "status": "PASS",   "breach_days": 0},
]

ERROR_BUDGET_ANALYSIS = (
    "P99 SLA has 1.8% error budget remaining (target <1% breach rate over 30 days). "
    "3/30 days exceeded the 300ms P99 target (days 8, 15, 22)."
)

P50_ANALYSIS = (
    "P50 SLA requires further optimization. Current 226ms P50 driven by LLM backbone (142ms). "
    "FP8 quantization target would bring to ~170ms P50."
)

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _latency_line_chart_svg() -> str:
    """30-day P50/P95/P99 line chart — 680×240."""
    W, H = 680, 240
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 20, 20, 40
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    N = 30

    SERIES = [
        ("p50_ms",  "#38bdf8",  "P50"),
        ("p95_ms",  "#f59e0b",  "P95"),
        ("p99_ms",  "#C74634",  "P99"),
    ]
    SLA_LINES = [
        (200, "#38bdf860", "SLA P50"),
        (280, "#f59e0b60", "SLA P95"),
        (300, "#C7463460", "SLA P99"),
    ]

    all_vals = [d["p50_ms"] for d in DAILY_STATS] + [d["p99_ms"] for d in DAILY_STATS]
    y_min = 150
    y_max = 380
    y_range = y_max - y_min

    def px(i: int) -> float:
        return PAD_L + i * chart_w / (N - 1)

    def py(v: float) -> float:
        return PAD_T + chart_h * (1 - (v - y_min) / y_range)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # grid + y-axis ticks
    for tick in [200, 250, 300, 350]:
        ty = py(tick)
        lines.append(f'<line x1="{PAD_L}" y1="{ty:.1f}" x2="{W-PAD_R}" y2="{ty:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{ty+4:.1f}" fill="#64748b" font-size="9" text-anchor="end">{tick}</text>')

    # SLA target dashed lines
    for sla_v, sla_c, sla_lbl in SLA_LINES:
        ty = py(sla_v)
        lines.append(f'<line x1="{PAD_L}" y1="{ty:.1f}" x2="{W-PAD_R}" y2="{ty:.1f}" stroke="{sla_c}" stroke-width="1.5" stroke-dasharray="6,3"/>')
        lines.append(f'<text x="{W-PAD_R-2}" y="{ty-3:.1f}" fill="{sla_c}" font-size="8" text-anchor="end">{sla_lbl}</text>')

    # Highlight P99 breach days
    for bd in P99_BREACH_DAYS:
        bx = px(bd - 1)
        lines.append(f'<rect x="{bx-6:.1f}" y="{PAD_T}" width="12" height="{chart_h}" fill="#C7463418"/>')

    # Series lines
    for key, color, label in SERIES:
        vals = [d[key] for d in DAILY_STATS]
        path_d = " ".join(("M" if i == 0 else "L") + f" {px(i):.1f},{py(v):.1f}" for i, v in enumerate(vals))
        lines.append(f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="2"/>')
        # dots at breach days only (p99)
        if key == "p99_ms":
            for bd in P99_BREACH_DAYS:
                i = bd - 1
                lines.append(f'<circle cx="{px(i):.1f}" cy="{py(vals[i]):.1f}" r="4" fill="#C74634" stroke="#fff" stroke-width="1"/>')

    # x-axis day labels (every 5)
    for i in range(0, N, 5):
        lines.append(f'<text x="{px(i):.1f}" y="{PAD_T+chart_h+14:.1f}" fill="#64748b" font-size="8" text-anchor="middle">D{i+1}</text>')

    # legend
    legend_items = [("#38bdf8", "P50"), ("#f59e0b", "P95"), ("#C74634", "P99")]
    lx = PAD_L + 10
    for color, lbl in legend_items:
        lines.append(f'<rect x="{lx}" y="{PAD_T+6}" width="20" height="3" fill="{color}" rx="1"/>')
        lines.append(f'<text x="{lx+24}" y="{PAD_T+12}" fill="{color}" font-size="10">{lbl}</text>')
        lx += 60

    lines.append("</svg>")
    return "".join(lines)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    chart_svg = _latency_line_chart_svg()

    # SLA compliance table rows
    table_rows = ""
    for row in SUMMARY_TABLE:
        s_color = "#22c55e" if row["status"] == "PASS" else "#ef4444"
        margin = row["actual_ms"] - row["target_ms"]
        margin_color = "#22c55e" if margin <= 0 else "#ef4444"
        margin_str = f"+{margin:.1f}" if margin > 0 else f"{margin:.1f}"
        table_rows += f"""
        <tr>
          <td style="color:#f1f5f9;font-weight:600">{row['metric']}</td>
          <td style="color:#94a3b8">{row['target_ms']} ms</td>
          <td style="color:#38bdf8">{row['actual_ms']} ms</td>
          <td style="color:{margin_color};font-weight:600">{margin_str} ms</td>
          <td><span style="color:{s_color};font-weight:700;font-size:12px">{row['status']}</span></td>
          <td style="color:#64748b">{row['breach_days']} / 30</td>
        </tr>"""

    # Daily breach day list
    breach_list = ", ".join(f"Day {d}" for d in P99_BREACH_DAYS)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Latency SLA Monitor — OCI Robot Cloud</title>
<style>
  * {{box-sizing:border-box;margin:0;padding:0}}
  body {{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
  h1 {{font-size:22px;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
  .subtitle {{color:#64748b;font-size:13px;margin-bottom:24px}}
  .badge {{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;margin-right:6px}}
  .badge-blue {{background:#0ea5e940;color:#38bdf8;border:1px solid #38bdf840}}
  .badge-red {{background:#C7463440;color:#C74634;border:1px solid #C7463440}}
  .kpi-row {{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}}
  .kpi {{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;min-width:140px}}
  .kpi-val {{font-size:26px;font-weight:700;color:#38bdf8}}
  .kpi-val.amber {{color:#f59e0b}}
  .kpi-val.red {{color:#C74634}}
  .kpi-val.green {{color:#22c55e}}
  .kpi-lbl {{font-size:11px;color:#64748b;margin-top:2px}}
  .section {{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:20px;margin-bottom:20px}}
  .section-title {{font-size:14px;font-weight:600;color:#94a3b8;margin-bottom:14px;text-transform:uppercase;letter-spacing:0.05em}}
  table {{width:100%;border-collapse:collapse;font-size:13px}}
  th {{color:#64748b;font-weight:600;padding:8px 10px;border-bottom:1px solid #334155;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:0.04em}}
  td {{padding:8px 10px;border-bottom:1px solid #1e293b}}
  tr:last-child td {{border-bottom:none}}
  tr:hover td {{background:#263045}}
  .alert {{background:#C7463420;border:1px solid #C7463460;border-radius:6px;padding:12px 16px;margin-bottom:16px;font-size:13px;color:#fca5a5}}
  .info {{background:#0ea5e920;border:1px solid #38bdf840;border-radius:6px;padding:12px 16px;margin-bottom:16px;font-size:13px;color:#7dd3fc}}
  .footer {{color:#334155;font-size:11px;text-align:center;margin-top:24px}}
</style>
</head>
<body>
<h1>Inference Latency SLA Monitor
  <span class="badge badge-blue">Port 8165</span>
  <span class="badge badge-red">OCI Robot Cloud</span>
</h1>
<div class="subtitle">30-day rolling window &nbsp;|&nbsp; P50/P95/P99 tracking &nbsp;|&nbsp; 1,940-demo genesis_sdg_v3 inference endpoint</div>

<div class="kpi-row">
  <div class="kpi"><div class="kpi-val red">{AVG_P50} ms</div><div class="kpi-lbl">Avg P50 (target 200ms)</div></div>
  <div class="kpi"><div class="kpi-val green">{AVG_P95} ms</div><div class="kpi-lbl">Avg P95 (target 280ms)</div></div>
  <div class="kpi"><div class="kpi-val amber">{AVG_P99} ms</div><div class="kpi-lbl">Avg P99 (target 300ms)</div></div>
  <div class="kpi"><div class="kpi-val green">{AVG_MAX:.1f} ms</div><div class="kpi-lbl">Avg Max (target 500ms)</div></div>
  <div class="kpi"><div class="kpi-val red">{len(P99_BREACH_DAYS)}</div><div class="kpi-lbl">P99 Breach Days</div></div>
  <div class="kpi"><div class="kpi-val amber">1.8%</div><div class="kpi-lbl">P99 Error Budget Left</div></div>
</div>

<div class="alert">P50 SLA BREACH — {AVG_P50}ms avg vs 200ms target. {P50_ANALYSIS}</div>
<div class="info">Error Budget — {ERROR_BUDGET_ANALYSIS}</div>

<div class="section">
  <div class="section-title">30-Day Latency Trend (ms) — Breach Days Highlighted</div>
  {chart_svg}
</div>

<div class="section">
  <div class="section-title">SLA Compliance Summary</div>
  <table>
    <thead>
      <tr>
        <th>Metric</th>
        <th>Target</th>
        <th>30-Day Avg</th>
        <th>Margin</th>
        <th>Status</th>
        <th>Breach Days</th>
      </tr>
    </thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>

<div class="section">
  <div class="section-title">Breach Analysis</div>
  <p style="color:#94a3b8;font-size:13px;margin-bottom:12px"><strong style="color:#f1f5f9">P99 Breach Days:</strong> {breach_list}</p>
  <p style="color:#94a3b8;font-size:13px;margin-bottom:8px"><strong style="color:#f1f5f9">P50 Status:</strong> Chronic breach — all 30 days exceeded 200ms target. LLM backbone accounts for 142ms of total latency. FP8 quantization and prefix caching estimated to bring P50 to ~170ms.</p>
  <p style="color:#94a3b8;font-size:13px"><strong style="color:#f1f5f9">P99 Status:</strong> 3 isolated breach events on days 8, 15, 22. Pattern suggests weekly batch job contention. Investigation: shared GPU memory pressure during nightly data pipeline runs.</p>
</div>

<div class="footer">OCI Robot Cloud &mdash; Latency SLA Monitor &mdash; Port 8165</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

try:
    app = FastAPI(
        title="Latency SLA Monitor",
        description="Inference latency SLA monitor with P99 tracking and breach alerting",
        version="1.0.0",
    )
except NameError:
    raise SystemExit("fastapi not available")


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Dashboard HTML for latency SLA monitor."""
    return _dashboard_html()


@app.get("/stats")
def get_stats():
    """Return full 30-day daily latency statistics."""
    return JSONResponse({"window_days": 30, "daily": DAILY_STATS})


@app.get("/summary")
def get_summary():
    """Return SLA compliance summary."""
    return JSONResponse({
        "averages": {
            "p50_ms": AVG_P50,
            "p95_ms": AVG_P95,
            "p99_ms": AVG_P99,
            "max_ms": AVG_MAX,
        },
        "sla_targets_ms": {k: v["target"] for k, v in SLA.items()},
        "compliance": SUMMARY_TABLE,
        "error_budget": ERROR_BUDGET_ANALYSIS,
        "p50_analysis": P50_ANALYSIS,
    })


@app.get("/breaches")
def get_breaches():
    """Return breach events by metric."""
    return JSONResponse({
        "p50_breaches": {"days": 30, "all_days": True},
        "p99_breaches": {
            "days": len(P99_BREACH_DAYS),
            "breach_day_indices": P99_BREACH_DAYS,
            "details": [
                {"day": d["day"], "p99_ms": d["p99_ms"]}
                for d in DAILY_STATS if d["p99_status"] == "BREACH"
            ],
        },
    })


if __name__ == "__main__":
    try:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8165)
    except ImportError:
        print("uvicorn not installed. Run: pip install fastapi uvicorn")

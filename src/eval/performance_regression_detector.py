"""
performance_regression_detector.py — FastAPI port 8100
Detects performance regressions across GR00T N1.6 policy checkpoints.

Oracle Confidential
"""

import math
import datetime
from typing import List, Dict, Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ---------------------------------------------------------------------------
# Checkpoint registry — sequential, newest last
# ---------------------------------------------------------------------------
CHECKPOINTS: List[Dict[str, Any]] = [
    {
        "id": 1, "name": "bc_500demo",       "timestamp": "2026-01-15",
        "sr": 0.05, "mae": 0.103, "latency_ms": 226, "cost_per_run": 0.43,
        "training_steps": 5000,  "is_prod": False,
    },
    {
        "id": 2, "name": "bc_1000demo",      "timestamp": "2026-01-28",
        "sr": 0.05, "mae": 0.098, "latency_ms": 227, "cost_per_run": 0.43,
        "training_steps": 10000, "is_prod": False,
    },
    {
        "id": 3, "name": "dagger_run1",      "timestamp": "2026-02-03",
        "sr": 0.05, "mae": 0.091, "latency_ms": 228, "cost_per_run": 0.47,
        "training_steps": 15000, "is_prod": False,
    },
    {
        "id": 4, "name": "dagger_run2",      "timestamp": "2026-02-08",
        "sr": 0.10, "mae": 0.082, "latency_ms": 229, "cost_per_run": 0.48,
        "training_steps": 20000, "is_prod": False,
    },
    {
        "id": 5, "name": "dagger_run3",      "timestamp": "2026-02-14",
        "sr": 0.15, "mae": 0.071, "latency_ms": 228, "cost_per_run": 0.49,
        "training_steps": 25000, "is_prod": False,
    },
    {
        "id": 6, "name": "dagger_run4",      "timestamp": "2026-02-20",
        "sr": 0.20, "mae": 0.063, "latency_ms": 226, "cost_per_run": 0.50,
        "training_steps": 30000, "is_prod": False,
    },
    {
        "id": 7, "name": "dagger_run5",      "timestamp": "2026-02-26",
        "sr": 0.05, "mae": 0.089, "latency_ms": 229, "cost_per_run": 0.61,
        "training_steps": 35000, "is_prod": False,
        "note": "regression",
    },
    {
        "id": 8, "name": "dagger_run6",      "timestamp": "2026-03-03",
        "sr": 0.25, "mae": 0.058, "latency_ms": 227, "cost_per_run": 0.52,
        "training_steps": 40000, "is_prod": False,
    },
    {
        "id": 9, "name": "dagger_run7",      "timestamp": "2026-03-08",
        "sr": 0.40, "mae": 0.041, "latency_ms": 225, "cost_per_run": 0.51,
        "training_steps": 45000, "is_prod": False,
    },
    {
        "id": 10, "name": "dagger_run8",     "timestamp": "2026-03-12",
        "sr": 0.55, "mae": 0.028, "latency_ms": 226, "cost_per_run": 0.49,
        "training_steps": 50000, "is_prod": False,
    },
    {
        "id": 11, "name": "dagger_run9",     "timestamp": "2026-03-18",
        "sr": 0.71, "mae": 0.013, "latency_ms": 226, "cost_per_run": 0.43,
        "training_steps": 55000, "is_prod": False,
    },
    {
        "id": 12, "name": "groot_finetune_v2", "timestamp": "2026-03-25",
        "sr": 0.74, "mae": 0.011, "latency_ms": 231, "cost_per_run": 0.47,
        "training_steps": 60000, "is_prod": True,
        "note": "CURRENT PROD",
    },
]

REGRESSION_THRESHOLDS: Dict[str, float] = {
    "sr_drop_pct":         10.0,
    "mae_increase_pct":    15.0,
    "latency_increase_ms": 20.0,
    "cost_increase_pct":   20.0,
}


# ---------------------------------------------------------------------------
# Core analysis functions
# ---------------------------------------------------------------------------

def detect_regressions() -> List[Dict[str, Any]]:
    """Compare each checkpoint to its predecessor; flag metric crossings."""
    regressions = []
    for i in range(1, len(CHECKPOINTS)):
        prev = CHECKPOINTS[i - 1]
        curr = CHECKPOINTS[i]
        flags = []

        if prev["sr"] > 0:
            sr_drop_pct = (prev["sr"] - curr["sr"]) / prev["sr"] * 100.0
        else:
            sr_drop_pct = 0.0
        if sr_drop_pct >= REGRESSION_THRESHOLDS["sr_drop_pct"]:
            flags.append({
                "metric": "success_rate",
                "prev_value": prev["sr"],
                "curr_value": curr["sr"],
                "change_pct": round(-sr_drop_pct, 2),
                "threshold": REGRESSION_THRESHOLDS["sr_drop_pct"],
            })

        if prev["mae"] > 0:
            mae_inc_pct = (curr["mae"] - prev["mae"]) / prev["mae"] * 100.0
        else:
            mae_inc_pct = 0.0
        if mae_inc_pct >= REGRESSION_THRESHOLDS["mae_increase_pct"]:
            flags.append({
                "metric": "mae",
                "prev_value": prev["mae"],
                "curr_value": curr["mae"],
                "change_pct": round(mae_inc_pct, 2),
                "threshold": REGRESSION_THRESHOLDS["mae_increase_pct"],
            })

        lat_inc = curr["latency_ms"] - prev["latency_ms"]
        if lat_inc >= REGRESSION_THRESHOLDS["latency_increase_ms"]:
            flags.append({
                "metric": "latency_ms",
                "prev_value": prev["latency_ms"],
                "curr_value": curr["latency_ms"],
                "change_abs": round(lat_inc, 2),
                "threshold": REGRESSION_THRESHOLDS["latency_increase_ms"],
            })

        if prev["cost_per_run"] > 0:
            cost_inc_pct = (curr["cost_per_run"] - prev["cost_per_run"]) / prev["cost_per_run"] * 100.0
        else:
            cost_inc_pct = 0.0
        if cost_inc_pct >= REGRESSION_THRESHOLDS["cost_increase_pct"]:
            flags.append({
                "metric": "cost_per_run",
                "prev_value": prev["cost_per_run"],
                "curr_value": curr["cost_per_run"],
                "change_pct": round(cost_inc_pct, 2),
                "threshold": REGRESSION_THRESHOLDS["cost_increase_pct"],
            })

        if flags:
            severity = "minor"
            for f in flags:
                if f["metric"] == "success_rate" and abs(f.get("change_pct", 0)) > 25:
                    severity = "major"
                if f["metric"] == "mae" and f.get("change_pct", 0) > 30:
                    severity = "major"
            regressions.append({
                "from_checkpoint": prev["name"],
                "to_checkpoint": curr["name"],
                "timestamp": curr["timestamp"],
                "training_steps": curr["training_steps"],
                "severity": severity,
                "flags": flags,
            })
    return regressions


def trend_analysis() -> Dict[str, Any]:
    """Rolling 3-checkpoint averages; inflection points; overall trend."""
    n = len(CHECKPOINTS)
    rolling_sr  = []
    rolling_mae = []

    for i in range(n):
        start = max(0, i - 2)
        window = CHECKPOINTS[start: i + 1]
        rolling_sr.append(round(sum(c["sr"]  for c in window) / len(window), 4))
        rolling_mae.append(round(sum(c["mae"] for c in window) / len(window), 4))

    inflections = []
    for i in range(1, len(rolling_sr) - 1):
        prev_delta = rolling_sr[i]     - rolling_sr[i - 1]
        next_delta = rolling_sr[i + 1] - rolling_sr[i]
        if prev_delta > 0 and next_delta < 0:
            inflections.append({"checkpoint": CHECKPOINTS[i]["name"], "type": "peak_sr"})
        elif prev_delta < 0 and next_delta > 0:
            inflections.append({"checkpoint": CHECKPOINTS[i]["name"], "type": "trough_sr"})

    first3_sr  = sum(c["sr"]  for c in CHECKPOINTS[:3]) / 3
    last3_sr   = sum(c["sr"]  for c in CHECKPOINTS[-3:]) / 3
    first3_mae = sum(c["mae"] for c in CHECKPOINTS[:3]) / 3
    last3_mae  = sum(c["mae"] for c in CHECKPOINTS[-3:]) / 3

    sr_trend  = last3_sr  - first3_sr
    mae_trend = last3_mae - first3_mae

    if sr_trend > 0.05 and mae_trend < -0.01:
        overall = "improving"
    elif sr_trend < -0.05 or mae_trend > 0.01:
        overall = "degrading"
    else:
        overall = "stable"

    return {
        "overall_trend": overall,
        "rolling_sr":    rolling_sr,
        "rolling_mae":   rolling_mae,
        "inflection_points": inflections,
        "first3_avg_sr":  round(first3_sr, 4),
        "last3_avg_sr":   round(last3_sr, 4),
        "first3_avg_mae": round(first3_mae, 4),
        "last3_avg_mae":  round(last3_mae, 4),
    }


# ---------------------------------------------------------------------------
# SVG chart helpers
# ---------------------------------------------------------------------------

def _chart_dimensions():
    W, H = 600, 200
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 20, 20, 35
    return W, H, PAD_L, PAD_R, PAD_T, PAD_B


def checkpoint_chart_svg() -> str:
    """SVG line chart: x=steps, y=SR (0-100%), Oracle red. Regressions ▼, PROD ★."""
    W, H, PL, PR, PT, PB = _chart_dimensions()
    inner_w = W - PL - PR
    inner_h = H - PT - PB

    steps  = [c["training_steps"] for c in CHECKPOINTS]
    srs    = [c["sr"] * 100 for c in CHECKPOINTS]
    min_x, max_x = steps[0],  steps[-1]
    min_y, max_y = 0,          100

    def px(s): return PL + (s - min_x) / (max_x - min_x) * inner_w
    def py(v): return PT + inner_h - (v - min_y) / (max_y - min_y) * inner_h

    pts = " ".join(f"{px(s):.1f},{py(v):.1f}" for s, v in zip(steps, srs))
    regressions = {r["to_checkpoint"] for r in detect_regressions()}

    dots = []
    for c in CHECKPOINTS:
        x, y = px(c["training_steps"]), py(c["sr"] * 100)
        if c["is_prod"]:
            dots.append(f'<text x="{x:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-size="14" fill="#FBBF24">★</text>')
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#FBBF24" stroke="#0f172a" stroke-width="1"/>')
        elif c["name"] in regressions:
            dots.append(f'<text x="{x:.1f}" y="{y - 5:.1f}" text-anchor="middle" font-size="12" fill="#ef4444">▼</text>')
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#ef4444" stroke="#0f172a" stroke-width="1"/>')
        else:
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#C74634" stroke="#0f172a" stroke-width="1"/>')

    y_ticks = ""
    for v in [0, 25, 50, 75, 100]:
        yp = py(v)
        y_ticks += (f'<line x1="{PL}" y1="{yp:.1f}" x2="{W - PR}" y2="{yp:.1f}" stroke="#334155" stroke-width="0.5"/>'
                    f'<text x="{PL - 6}" y="{yp + 4:.1f}" text-anchor="end" font-size="9" fill="#94a3b8">{v}%</text>')

    x_labels = ""
    for i, c in enumerate(CHECKPOINTS):
        if i % 2 == 0:
            xp = px(c["training_steps"])
            x_labels += f'<text x="{xp:.1f}" y="{H - 5}" text-anchor="middle" font-size="8" fill="#64748b">{c["training_steps"] // 1000}k</text>'

    return (f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="{W}" height="{H}" fill="#1e293b" rx="6"/>'
            f'<text x="{W//2}" y="14" text-anchor="middle" font-size="11" fill="#e2e8f0" font-family="monospace">Success Rate by Checkpoint</text>'
            f'{y_ticks}{x_labels}'
            f'<polyline points="{pts}" fill="none" stroke="#C74634" stroke-width="2.5" stroke-linejoin="round"/>'
            f'{"" .join(dots)}'
            f'<text x="{PL}" y="{H - 22}" font-size="8" fill="#64748b">Steps (thousands)</text>'
            f'<text x="6" y="{PT + inner_h // 2}" font-size="8" fill="#64748b" transform="rotate(-90,6,{PT + inner_h // 2})">SR %</text>'
            f'</svg>')


def mae_chart_svg() -> str:
    """SVG line chart: x=steps, y=MAE, blue line."""
    W, H, PL, PR, PT, PB = _chart_dimensions()
    inner_w = W - PL - PR
    inner_h = H - PT - PB

    steps = [c["training_steps"] for c in CHECKPOINTS]
    maes  = [c["mae"] for c in CHECKPOINTS]
    min_x, max_x = steps[0], steps[-1]
    max_y = math.ceil(max(maes) * 100) / 100
    min_y = 0.0

    def px(s): return PL + (s - min_x) / (max_x - min_x) * inner_w
    def py(v): return PT + inner_h - (v - min_y) / (max_y - min_y) * inner_h

    pts = " ".join(f"{px(s):.1f},{py(v):.1f}" for s, v in zip(steps, maes))
    regressions = {r["to_checkpoint"] for r in detect_regressions()}

    dots = []
    for c in CHECKPOINTS:
        x, y = px(c["training_steps"]), py(c["mae"])
        if c["is_prod"]:
            dots.append(f'<text x="{x:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-size="14" fill="#FBBF24">★</text>')
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#FBBF24" stroke="#0f172a" stroke-width="1"/>')
        elif c["name"] in regressions:
            dots.append(f'<text x="{x:.1f}" y="{y - 5:.1f}" text-anchor="middle" font-size="12" fill="#ef4444">▼</text>')
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#ef4444" stroke="#0f172a" stroke-width="1"/>')
        else:
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#38bdf8" stroke="#0f172a" stroke-width="1"/>')

    y_ticks = ""
    tick_vals = [round(min_y + (max_y - min_y) * i / 4, 3) for i in range(5)]
    for v in tick_vals:
        yp = py(v)
        y_ticks += (f'<line x1="{PL}" y1="{yp:.1f}" x2="{W - PR}" y2="{yp:.1f}" stroke="#334155" stroke-width="0.5"/>'
                    f'<text x="{PL - 6}" y="{yp + 4:.1f}" text-anchor="end" font-size="9" fill="#94a3b8">{v:.3f}</text>')

    x_labels = ""
    for i, c in enumerate(CHECKPOINTS):
        if i % 2 == 0:
            xp = px(c["training_steps"])
            x_labels += f'<text x="{xp:.1f}" y="{H - 5}" text-anchor="middle" font-size="8" fill="#64748b">{c["training_steps"] // 1000}k</text>'

    return (f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="{W}" height="{H}" fill="#1e293b" rx="6"/>'
            f'<text x="{W//2}" y="14" text-anchor="middle" font-size="11" fill="#e2e8f0" font-family="monospace">MAE by Checkpoint (lower = better)</text>'
            f'{y_ticks}{x_labels}'
            f'<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>'
            f'{"" .join(dots)}'
            f'<text x="{PL}" y="{H - 22}" font-size="8" fill="#64748b">Steps (thousands)</text>'
            f'<text x="8" y="{PT + inner_h // 2}" font-size="8" fill="#64748b" transform="rotate(-90,8,{PT + inner_h // 2})">MAE</text>'
            f'</svg>')


# ---------------------------------------------------------------------------
# Dashboard builder
# ---------------------------------------------------------------------------

def build_dashboard() -> str:
    regressions = detect_regressions()
    trend       = trend_analysis()
    sr_svg      = checkpoint_chart_svg()
    mae_svg     = mae_chart_svg()

    alert_html = ""
    for reg in regressions:
        sev_color = "#ef4444" if reg["severity"] == "major" else "#f97316"
        metrics   = ", ".join(f["metric"] for f in reg["flags"])
        alert_html += f"""<div style="border:1px solid {sev_color};border-radius:6px;padding:10px 14px;margin-bottom:8px;background:#1e293b;">
          <span style="color:{sev_color};font-weight:700;text-transform:uppercase;font-size:11px;">&#x26A0; {reg['severity']} regression</span>
          <span style="color:#cbd5e1;font-size:13px;margin-left:10px;">{reg['from_checkpoint']} → <strong style="color:#e2e8f0">{reg['to_checkpoint']}</strong>&nbsp;|&nbsp;{reg['timestamp']}&nbsp;|&nbsp;{metrics}</span>
        </div>"""

    trend_color = {"improving": "#22c55e", "degrading": "#ef4444", "stable": "#94a3b8"}
    tc = trend_color.get(trend["overall_trend"], "#94a3b8")
    chips_html = f"""<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px;">
      <span style="background:{tc}22;color:{tc};border:1px solid {tc};border-radius:20px;padding:4px 14px;font-size:12px;font-weight:600;">Trend: {trend['overall_trend'].upper()}</span>
      <span style="background:#1e293b;color:#94a3b8;border:1px solid #334155;border-radius:20px;padding:4px 14px;font-size:12px;">SR: {trend['first3_avg_sr']*100:.1f}% → {trend['last3_avg_sr']*100:.1f}%</span>
      <span style="background:#1e293b;color:#94a3b8;border:1px solid #334155;border-radius:20px;padding:4px 14px;font-size:12px;">MAE: {trend['first3_avg_mae']:.4f} → {trend['last3_avg_mae']:.4f}</span>
      <span style="background:#1e293b;color:#f59e0b;border:1px solid #f59e0b;border-radius:20px;padding:4px 14px;font-size:12px;">{len(regressions)} regression(s) detected</span>
    </div>"""

    reg_rows = ""
    for reg in regressions:
        sev_color = "#ef4444" if reg["severity"] == "major" else "#f97316"
        metrics   = "; ".join(f"{f['metric']}: {f.get('change_pct', f.get('change_abs', ''))}" for f in reg["flags"])
        reg_rows += f"<tr><td>{reg['from_checkpoint']}</td><td style='color:#e2e8f0;font-weight:600'>{reg['to_checkpoint']}</td><td>{reg['timestamp']}</td><td style='color:{sev_color};font-weight:700'>{reg['severity'].upper()}</td><td style='font-size:11px;color:#94a3b8'>{metrics}</td></tr>"

    reg_names = {r["to_checkpoint"] for r in regressions}
    ck_rows = ""
    for c in CHECKPOINTS:
        prod_badge = ' <span style="color:#FBBF24;font-weight:700">★ PROD</span>' if c["is_prod"] else ""
        reg_badge  = ' <span style="color:#ef4444">▼</span>' if c["name"] in reg_names else ""
        ck_rows += f"<tr{'style=\"background:#172032\"' if c['is_prod'] else ''}><td>{c['training_steps']:,}</td><td style='color:#e2e8f0'>{c['name']}{prod_badge}{reg_badge}</td><td>{c['timestamp']}</td><td style='color:#22c55e'>{c['sr']*100:.0f}%</td><td style='color:#38bdf8'>{c['mae']:.4f}</td><td>{c['latency_ms']} ms</td><td>${c['cost_per_run']:.2f}</td></tr>"

    ts = "width:100%;border-collapse:collapse;font-size:13px;"
    ths = "background:#0f172a;color:#94a3b8;padding:8px 12px;text-align:left;border-bottom:1px solid #334155;font-size:11px;"
    tds = "padding:7px 12px;border-bottom:1px solid #1e293b;color:#cbd5e1;"

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>GR00T Performance Regression Detector</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;font-size:14px;padding:24px}}
h1{{font-size:20px;font-weight:700;color:#e2e8f0;margin-bottom:4px}}h2{{font-size:14px;font-weight:600;color:#94a3b8;margin:20px 0 10px}}
.card{{background:#1e293b;border-radius:8px;padding:18px;margin-bottom:18px}}table{{{ts}}}th{{{ths}}}td{{{tds}}}tr:hover td{{background:#273549}}
.footer{{color:#475569;font-size:11px;text-align:center;margin-top:32px}}</style></head><body>
<h1>&#x1F916; GR00T N1.6 — Performance Regression Detector</h1>
<p style="color:#64748b;font-size:12px;margin-bottom:18px;">Port 8100 &nbsp;|&nbsp; {len(CHECKPOINTS)} checkpoints &nbsp;|&nbsp; Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
<div class="card"><h2 style="margin-top:0">Regression Alerts</h2>{alert_html if alert_html else '<p style="color:#22c55e">No regressions detected.</p>'}</div>
<div class="card"><h2 style="margin-top:0">Trend Summary</h2>{chips_html}</div>
<div class="card"><h2 style="margin-top:0">Charts</h2><div style="display:flex;gap:16px;flex-wrap:wrap;"><div>{sr_svg}</div><div>{mae_svg}</div></div>
<p style="color:#475569;font-size:11px;margin-top:8px;">▼ = regression &nbsp; ★ = current production &nbsp; Red=SR &nbsp; Blue=MAE</p></div>
<div class="card"><h2 style="margin-top:0">Regression History</h2><table><thead><tr><th>From</th><th>To</th><th>Date</th><th>Severity</th><th>Metrics</th></tr></thead>
<tbody>{reg_rows if reg_rows else '<tr><td colspan="5" style="color:#22c55e">No regressions.</td></tr>'}</tbody></table></div>
<div class="card"><h2 style="margin-top:0">All Checkpoints</h2><table><thead><tr><th>Steps</th><th>Name</th><th>Date</th><th>SR</th><th>MAE</th><th>Latency</th><th>Cost/Run</th></tr></thead>
<tbody>{ck_rows}</tbody></table></div>
<p class="footer">Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; GR00T N1.6 Pipeline</p></body></html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="Performance Regression Detector",
        description="Detects regressions across GR00T N1.6 policy checkpoints. Oracle Confidential.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def root(): return build_dashboard()

    @app.get("/regressions")
    def get_regressions(): return JSONResponse(content=detect_regressions())

    @app.get("/checkpoints")
    def get_checkpoints(): return JSONResponse(content=CHECKPOINTS)

    @app.get("/trend")
    def get_trend(): return JSONResponse(content=trend_analysis())


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    regressions = detect_regressions()
    trend       = trend_analysis()
    print("=" * 60)
    print("GR00T N1.6 — Performance Regression Report")
    print("Oracle Confidential")
    print("=" * 60)
    print(f"\nOverall trend: {trend['overall_trend'].upper()}")
    print(f"SR  : {trend['first3_avg_sr']*100:.1f}% → {trend['last3_avg_sr']*100:.1f}%")
    print(f"MAE : {trend['first3_avg_mae']:.4f} → {trend['last3_avg_mae']:.4f}")
    print(f"\nRegressions detected: {len(regressions)}")
    for reg in regressions:
        print(f"\n  [{reg['severity'].upper()}] {reg['from_checkpoint']} → {reg['to_checkpoint']} ({reg['timestamp']})")
        for f in reg["flags"]:
            chg = f.get("change_pct", f.get("change_abs", ""))
            print(f"    - {f['metric']}: {f['prev_value']} → {f['curr_value']}  (Δ {chg})")
    out_path = "/tmp/perf_regression_report.html"
    with open(out_path, "w") as fh:
        fh.write(build_dashboard())
    print(f"\nHTML report saved to {out_path}")
    if HAS_FASTAPI:
        try:
            uvicorn.run(app, host="0.0.0.0", port=8100)
        except Exception as exc:
            print(f"Could not start FastAPI server: {exc}")


if __name__ == "__main__":
    main()

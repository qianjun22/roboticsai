"""Eval Regression Detector v2 — port 8351.

Advanced regression detection with multi-metric and distribution shift detection.
Stdlib-only at module level; FastAPI used if available, else http.server fallback.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

rng = random.Random(42)

EVAL_RUNS = [
    # (run_id, version, date_offset_days_ago, sr_pct, latency_ms, regression, severity, root_cause, resolution_h)
    (1,  "v10", 89, 62.0, 198, False, None,    None,                  None),
    (2,  "v11", 82, 55.5, 201, True,  "HIGH",  "data_aug_bug",        2.0),
    (3,  "v12", 75, 63.0, 197, False, None,    None,                  None),
    (4,  "v13", 68, 64.5, 200, False, None,    None,                  None),
    (5,  "v14", 61, 65.0, 202, False, None,    None,                  None),
    (6,  "v15", 54, 66.5, 199, False, None,    None,                  None),
    (7,  "v16", 47, 67.0, 198, False, None,    None,                  None),
    (8,  "v17", 40, 64.0, 203, True,  "MEDIUM","config_error",        1.0),
    (9,  "v18", 33, 68.5, 201, False, None,    None,                  None),
    (10, "v19", 26, 68.0, 242, True,  "MEDIUM","batch_size_regression",0.5),
    (11, "v20", 19, 70.0, 201, False, None,    None,                  None),
    (12, "v21",  5, 71.5, 199, False, None,    None,                  None),
]

# ROC curve data for regression detector (SR drop thresholds)
ROC_CURVES = {
    "2pp":  [(0.00,0.00),(0.05,0.55),(0.10,0.70),(0.15,0.80),(0.20,0.87),(0.30,0.91),(0.50,0.95),(1.00,1.00)],
    "3pp":  [(0.00,0.00),(0.03,0.60),(0.08,0.75),(0.12,0.83),(0.18,0.89),(0.25,0.93),(0.40,0.97),(1.00,1.00)],
    "5pp":  [(0.00,0.00),(0.02,0.65),(0.05,0.80),(0.09,0.88),(0.14,0.92),(0.20,0.95),(0.35,0.98),(1.00,1.00)],
}
OPTIMAL_POINT = (0.09, 0.91)   # (FPR, TPR) at operating threshold
DETECTOR_AUC  = 0.91

# Regression details
REGRESSIONS = [
    r for r in EVAL_RUNS if r[5]
]

# Computed metrics
total_runs       = len(EVAL_RUNS)
regression_count = sum(1 for r in EVAL_RUNS if r[5])
regression_rate  = round(regression_count / total_runs * 100, 1)
fp_rate          = 0.09
mttd_hours       = round(sum(r[8] for r in EVAL_RUNS if r[8]) / regression_count, 2) if regression_count else 0

# Root cause distribution
root_causes: dict[str, int] = {}
for r in EVAL_RUNS:
    if r[7]:
        root_causes[r[7]] = root_causes.get(r[7], 0) + 1


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_roc_curve() -> str:
    W, H = 560, 420
    pad_l, pad_t, pad_r, pad_b = 60, 40, 40, 60
    cw = W - pad_l - pad_r
    ch = H - pad_t - pad_b

    def px(fpr: float) -> float:
        return pad_l + fpr * cw

    def py(tpr: float) -> float:
        return pad_t + (1 - tpr) * ch

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W/2}" y="22" text-anchor="middle" fill="#f8fafc" font-size="13" font-weight="bold" font-family="sans-serif">Regression Detector ROC Curve</text>')

    # axes
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+ch}" stroke="#475569" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+ch}" x2="{pad_l+cw}" y2="{pad_t+ch}" stroke="#475569" stroke-width="1.5"/>')

    # diagonal chance line
    lines.append(f'<line x1="{px(0)}" y1="{py(0)}" x2="{px(1)}" y2="{py(1)}" stroke="#334155" stroke-dasharray="6,4" stroke-width="1"/>')

    # grid
    for v in [0.2, 0.4, 0.6, 0.8]:
        x = px(v)
        y = py(v)
        lines.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t+ch}" stroke="#1e3a5f" stroke-width="0.8"/>')
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+cw}" y2="{y:.1f}" stroke="#1e3a5f" stroke-width="0.8"/>')
        lines.append(f'<text x="{x:.1f}" y="{pad_t+ch+16}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{v}</text>')
        lines.append(f'<text x="{pad_l-8}" y="{y+3:.1f}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{v}</text>')

    # axis labels
    lines.append(f'<text x="{pad_l+cw/2}" y="{H-8}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="sans-serif">False Positive Rate</text>')
    lines.append(f'<text x="14" y="{pad_t+ch/2}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="sans-serif" transform="rotate(-90,14,{pad_t+ch/2})">True Positive Rate</text>')

    curve_styles = [
        ("2pp",  "#f97316", "2pp drop"),
        ("3pp",  "#38bdf8", "3pp drop (optimal)"),
        ("5pp",  "#22c55e", "5pp drop"),
    ]

    for threshold, color, label in curve_styles:
        pts = ROC_CURVES[threshold]
        d = "M " + " L ".join(f"{px(p[0]):.1f},{py(p[1]):.1f}" for p in pts)
        lw = "2.5" if threshold == "3pp" else "1.8"
        lines.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{lw}" stroke-linejoin="round"/>')

    # optimal operating point
    ox, oy = px(OPTIMAL_POINT[0]), py(OPTIMAL_POINT[1])
    lines.append(f'<circle cx="{ox:.1f}" cy="{oy:.1f}" r="6" fill="#C74634" stroke="#f8fafc" stroke-width="1.5"/>')
    lines.append(f'<text x="{ox+10:.1f}" y="{oy-6:.1f}" fill="#C74634" font-size="10" font-weight="bold" font-family="sans-serif">Optimal (FPR={OPTIMAL_POINT[0]}, TPR={OPTIMAL_POINT[1]})</text>')

    # AUC annotation
    lines.append(f'<text x="{pad_l+cw-10}" y="{pad_t+30}" text-anchor="end" fill="#38bdf8" font-size="12" font-weight="bold" font-family="monospace">AUC = {DETECTOR_AUC}</text>')

    # legend
    ly = H - 18
    for i, (threshold, color, label) in enumerate(curve_styles):
        ox2 = pad_l + i * 170
        lines.append(f'<line x1="{ox2}" y1="{ly}" x2="{ox2+20}" y2="{ly}" stroke="{color}" stroke-width="2"/>')
        lines.append(f'<text x="{ox2+24}" y="{ly+4}" fill="#94a3b8" font-size="10" font-family="sans-serif">{label}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def _svg_regression_timeline() -> str:
    W, H = 820, 340
    pad_l, pad_t, pad_r, pad_b = 60, 60, 30, 50
    cw = W - pad_l - pad_r
    ch = H - pad_t - pad_b

    n = len(EVAL_RUNS)
    run_x = [pad_l + (i / (n - 1)) * cw for i in range(n)]

    # SR values — scaled to chart
    sr_vals  = [r[2] for r in EVAL_RUNS]
    lat_vals = [r[3] for r in EVAL_RUNS]
    sr_min,  sr_max  = 50.0,  80.0
    lat_min, lat_max = 180.0, 260.0

    def sr_y(sr):   return pad_t + ch - (sr  - sr_min)  / (sr_max  - sr_min)  * ch
    def lat_y(lat): return pad_t + ch - (lat - lat_min) / (lat_max - lat_min) * ch

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W/2}" y="22" text-anchor="middle" fill="#f8fafc" font-size="13" font-weight="bold" font-family="sans-serif">Regression Event Timeline — Last 12 Eval Runs</text>')

    # y-axis left (SR)
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+ch}" stroke="#475569" stroke-width="1.5"/>')
    for v in [55, 60, 65, 70, 75]:
        y = sr_y(v)
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+cw}" y2="{y:.1f}" stroke="#1e3a5f" stroke-width="0.8"/>')
        lines.append(f'<text x="{pad_l-8}" y="{y+3:.1f}" text-anchor="end" fill="#38bdf8" font-size="9" font-family="monospace">{v}%</text>')

    # x-axis
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+ch}" x2="{pad_l+cw}" y2="{pad_t+ch}" stroke="#475569" stroke-width="1.5"/>')
    for i, r in enumerate(EVAL_RUNS):
        lines.append(f'<text x="{run_x[i]:.1f}" y="{pad_t+ch+16}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{r[1]}</text>')

    # latency line (right axis)
    lat_path = "M " + " L ".join(f"{run_x[i]:.1f},{lat_y(r[3]):.1f}" for i, r in enumerate(EVAL_RUNS))
    lines.append(f'<path d="{lat_path}" fill="none" stroke="#f97316" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.7"/>')

    # SR line
    sr_path = "M " + " L ".join(f"{run_x[i]:.1f},{sr_y(r[2]):.1f}" for i, r in enumerate(EVAL_RUNS))
    lines.append(f'<path d="{sr_path}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>')

    # dots + regression markers
    for i, r in enumerate(EVAL_RUNS):
        x = run_x[i]
        y = sr_y(r[2])
        is_reg = r[5]
        color  = "#C74634" if is_reg else "#38bdf8"
        r_size = 7 if is_reg else 4
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r_size}" fill="{color}" stroke="#0f172a" stroke-width="1.5"/>')
        if is_reg:
            # vertical drop line
            lines.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t+ch}" stroke="#C74634" stroke-dasharray="3,3" stroke-width="1" opacity="0.6"/>')
            # annotation box
            cause = r[7] or "unknown"
            sev   = r[6] or ""
            res   = f"{r[8]}h fix" if r[8] else ""
            bx = min(x - 60, pad_l + cw - 130)
            by = pad_t - 48
            lines.append(f'<rect x="{bx:.1f}" y="{by}" width="125" height="44" rx="4" fill="#1e293b" stroke="#C74634" stroke-width="1"/>')
            lines.append(f'<text x="{bx+4:.1f}" y="{by+13}" fill="#C74634" font-size="9" font-weight="bold" font-family="sans-serif">{r[1]} — {sev}</text>')
            lines.append(f'<text x="{bx+4:.1f}" y="{by+25}" fill="#94a3b8" font-size="8" font-family="sans-serif">{cause}</text>')
            lines.append(f'<text x="{bx+4:.1f}" y="{by+37}" fill="#22c55e" font-size="8" font-family="sans-serif">{res}</text>')

    # axis labels
    lines.append(f'<text x="{pad_l-40}" y="{pad_t+ch/2}" text-anchor="middle" fill="#38bdf8" font-size="10" font-family="sans-serif" transform="rotate(-90,{pad_l-40},{pad_t+ch/2})">Success Rate %</text>')
    lines.append(f'<text x="{pad_l+cw+10}" y="{pad_t+ch/2}" text-anchor="middle" fill="#f97316" font-size="10" font-family="sans-serif" transform="rotate(90,{pad_l+cw+10},{pad_t+ch/2})">Latency ms</text>')

    # legend
    lx, ly = pad_l, H - 14
    items = [("#38bdf8", "Success Rate"), ("#f97316", "Latency (dashed)"), ("#C74634", "Regression detected")]
    for i, (col, lbl) in enumerate(items):
        ox = lx + i * 210
        lines.append(f'<circle cx="{ox+5}" cy="{ly}" r="4" fill="{col}"/>')
        lines.append(f'<text x="{ox+13}" y="{ly+4}" fill="#94a3b8" font-size="10" font-family="sans-serif">{lbl}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    svg_roc      = _svg_roc_curve()
    svg_timeline = _svg_regression_timeline()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    reg_rows = ""
    for r in EVAL_RUNS:
        if r[5]:
            triggered = "SR drop"
            if r[1] == "v19":
                triggered = "latency +41ms"
            res = f"{r[8]}h" if r[8] else "—"
            reg_rows += f"""<tr>
              <td>{r[1]}</td>
              <td><span class="badge sev-{r[6]}">{r[6]}</span></td>
              <td>{triggered}</td>
              <td>{r[7] or '—'}</td>
              <td style="color:#22c55e">{res}</td>
            </tr>\n"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Eval Regression Detector v2</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1   {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .sub {{ color: #64748b; font-size: .85rem; margin-bottom: 20px; }}
    .kpi-row {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }}
    .kpi  {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
             padding: 14px 20px; min-width: 150px; flex: 1; }}
    .kpi .val {{ font-size: 2rem; font-weight: 700; color: #38bdf8; }}
    .kpi .lbl {{ font-size: .75rem; color: #94a3b8; margin-top: 4px; }}
    .charts {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 24px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
             padding: 16px; overflow-x: auto; }}
    .card h2 {{ font-size: 1rem; color: #cbd5e1; margin-bottom: 12px; }}
    .card-wide {{ flex: 1 1 100%; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .82rem; }}
    th {{ text-align: left; padding: 6px 10px; color: #64748b; border-bottom: 1px solid #334155; }}
    td {{ padding: 6px 10px; border-bottom: 1px solid #1e293b; }}
    tr:hover td {{ background: #0f172a; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: .72rem; font-weight: 600; }}
    .sev-HIGH   {{ background: #450a0a; color: #f87171; }}
    .sev-MEDIUM {{ background: #431407; color: #f97316; }}
    footer {{ color: #475569; font-size: .75rem; margin-top: 16px; }}
  </style>
</head>
<body>
  <h1>Eval Regression Detector v2</h1>
  <div class="sub">Last updated: {ts} &nbsp;|&nbsp; {total_runs} eval runs tracked &nbsp;|&nbsp; port 8351</div>

  <div class="kpi-row">
    <div class="kpi"><div class="val">{DETECTOR_AUC}</div><div class="lbl">Detector AUC</div></div>
    <div class="kpi"><div class="val">{regression_count}</div><div class="lbl">Regressions (90 days)</div></div>
    <div class="kpi"><div class="val">{regression_rate}%</div><div class="lbl">Regression Rate</div></div>
    <div class="kpi"><div class="val">{mttd_hours}h</div><div class="lbl">Mean Time to Detect</div></div>
    <div class="kpi"><div class="val">{fp_rate}</div><div class="lbl">False Positive Rate</div></div>
    <div class="kpi"><div class="val">{len(root_causes)}</div><div class="lbl">Distinct Root Causes</div></div>
  </div>

  <div class="charts">
    <div class="card" style="flex:0 0 auto">
      <h2>ROC Curve — SR Drop Thresholds</h2>
      {svg_roc}
    </div>
    <div class="card card-wide">
      <h2>Regression Event Timeline</h2>
      {svg_timeline}
    </div>
  </div>

  <div class="card" style="margin-bottom:24px">
    <h2>Detected Regressions</h2>
    <table>
      <thead><tr><th>Version</th><th>Severity</th><th>Triggered By</th><th>Root Cause</th><th>Resolution Time</th></tr></thead>
      <tbody>
{reg_rows}
      </tbody>
    </table>
  </div>

  <footer>OCI Robot Cloud Eval Engineering &nbsp;|&nbsp; Confidential</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(title="Eval Regression Detector v2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "eval_regression_v2", "port": 8351}

    @app.get("/api/runs")
    async def api_runs():
        return [
            {"run_id": r[0], "version": r[1], "days_ago": r[2],
             "sr_pct": r[2], "latency_ms": r[3], "regression": r[5],
             "severity": r[6], "root_cause": r[7], "resolution_h": r[8]}
            for r in EVAL_RUNS
        ]

    @app.get("/api/metrics")
    async def api_metrics():
        return {
            "detector_auc": DETECTOR_AUC,
            "total_runs": total_runs,
            "regressions": regression_count,
            "regression_rate_pct": regression_rate,
            "false_positive_rate": fp_rate,
            "mean_time_to_detect_h": mttd_hours,
            "root_cause_distribution": root_causes,
            "optimal_operating_point": {"fpr": OPTIMAL_POINT[0], "tpr": OPTIMAL_POINT[1]},
        }

    @app.get("/api/regressions")
    async def api_regressions():
        return [
            {"version": r[1], "severity": r[6], "root_cause": r[7], "resolution_h": r[8]}
            for r in EVAL_RUNS if r[5]
        ]

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8351)
    else:
        with socketserver.TCPServer(("", 8351), _Handler) as srv:
            print("Eval Regression v2 running on http://0.0.0.0:8351 (stdlib fallback)")
            srv.serve_forever()

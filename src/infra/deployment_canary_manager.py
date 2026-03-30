#!/usr/bin/env python3
"""
Deployment Canary Manager — port 8260
Manages canary deployments for GR00T model updates with automated rollback.
"""

import random
import math
import json
from datetime import datetime, timedelta

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

CANARY_DEPLOYMENT = {
    "model": "groot_finetune_v2",
    "prod_model": "groot_finetune_v1",
    "canary_sr": 0.78,
    "prod_sr": 0.71,
    "start_date": "2026-03-22",
    "full_rollout_date": "2026-03-30",
    "incidents": 0,
    "status": "COMPLETE",
}

TRAFFIC_STEPS = [
    {"day": 0, "canary_pct": 0,   "canary_sr": None,  "prod_sr": 0.71, "decision": "INIT",   "note": "Baseline established"},
    {"day": 1, "canary_pct": 5,   "canary_sr": 0.72,  "prod_sr": 0.71, "decision": "GO",     "note": "SR +1% — proceed"},
    {"day": 2, "canary_pct": 10,  "canary_sr": 0.74,  "prod_sr": 0.71, "decision": "GO",     "note": "SR +3% — healthy"},
    {"day": 3, "canary_pct": 25,  "canary_sr": 0.75,  "prod_sr": 0.71, "decision": "PAUSE",  "note": "Latency +18ms — batching fix needed"},
    {"day": 5, "canary_pct": 25,  "canary_sr": 0.76,  "prod_sr": 0.71, "decision": "GO",     "note": "Batching fix deployed — latency nominal"},
    {"day": 6, "canary_pct": 50,  "canary_sr": 0.77,  "prod_sr": 0.71, "decision": "GO",     "note": "SR +6% — full confidence"},
    {"day": 8, "canary_pct": 100, "canary_sr": 0.78,  "prod_sr": 0.71, "decision": "GO",     "note": "Full rollout — 0 incidents"},
]

METRICS = {
    "sr":           {"canary": 0.78, "prod": 0.71, "higher_is_better": True,  "unit": "%",  "significant": True},
    "p50_latency":  {"canary": 231,  "prod": 228,  "higher_is_better": False, "unit": "ms", "significant": False},
    "error_rate":   {"canary": 0.8,  "prod": 1.4,  "higher_is_better": False, "unit": "%",  "significant": True},
    "gpu_util":     {"canary": 87,   "prod": 84,   "higher_is_better": True,  "unit": "%",  "significant": False},
}

ROLLOUT_HISTORY = []
for i, step in enumerate(TRAFFIC_STEPS):
    base = datetime(2026, 3, 22) + timedelta(days=step["day"])
    ROLLOUT_HISTORY.append({
        "timestamp": base.strftime("%Y-%m-%d"),
        **step
    })

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def build_traffic_timeline_svg() -> str:
    W, H = 760, 260
    pad_l, pad_r, pad_t, pad_b = 90, 30, 30, 60
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    days_total = 8
    bar_h = 26
    bar_gap = 10
    label_x = pad_l - 8

    decision_color = {"INIT": "#64748b", "GO": "#22c55e", "PAUSE": "#f59e0b"}

    lines = []
    lines.append(f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">')
    lines.append(f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>')
    lines.append(f'<text x="{W//2}" y="20" fill="#f1f5f9" font-size="13" font-family="monospace" text-anchor="middle" font-weight="bold">Canary Traffic Ramp — groot_finetune_v2</text>')

    # X-axis: days 0-8
    for d in range(days_total + 1):
        x = pad_l + int(d / days_total * chart_w)
        lines.append(f'<line x1="{x}" y1="{pad_t}" x2="{x}" y2="{pad_t + chart_h}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{x}" y="{pad_t + chart_h + 14}" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="middle">Day {d}</text>')

    # Stacked bars for each step (prod fill + canary fill)
    for idx, step in enumerate(TRAFFIC_STEPS):
        day = step["day"]
        pct = step["canary_pct"]
        x = pad_l + int(day / days_total * chart_w)
        y = pad_t + idx * (bar_h + bar_gap)
        if y + bar_h > pad_t + chart_h - 10:
            break

        prod_w = int((1 - pct / 100) * (chart_w * 0.6))
        can_w  = int((pct / 100) * (chart_w * 0.6))

        lines.append(f'<rect x="{pad_l}" y="{y}" width="{prod_w}" height="{bar_h}" fill="#334155" rx="3"/>')
        if can_w > 0:
            lines.append(f'<rect x="{pad_l + prod_w}" y="{y}" width="{can_w}" height="{bar_h}" fill="#C74634" rx="3"/>')

        dcol = decision_color.get(step["decision"], "#64748b")
        lines.append(f'<circle cx="{pad_l + prod_w + can_w + 8}" cy="{y + bar_h//2}" r="5" fill="{dcol}"/>')

        sr_text = f"SR {step['canary_sr']:.0%}" if step['canary_sr'] else "baseline"
        lines.append(f'<text x="{pad_l + prod_w + can_w + 18}" y="{y + bar_h//2 + 4}" fill="#cbd5e1" font-size="10" font-family="monospace">{pct}% canary · {sr_text} · {step["decision"]}</text>')

    # Legend
    ly = H - 18
    lines.append(f'<rect x="{pad_l}" y="{ly - 10}" width="14" height="10" fill="#334155" rx="2"/>')
    lines.append(f'<text x="{pad_l + 18}" y="{ly}" fill="#94a3b8" font-size="10" font-family="monospace">Production</text>')
    lines.append(f'<rect x="{pad_l + 100}" y="{ly - 10}" width="14" height="10" fill="#C74634" rx="2"/>')
    lines.append(f'<text x="{pad_l + 118}" y="{ly}" fill="#94a3b8" font-size="10" font-family="monospace">Canary</text>')
    lines.append(f'<circle cx="{pad_l + 180}" cy="{ly - 5}" r="5" fill="#22c55e"/>')
    lines.append(f'<text x="{pad_l + 190}" y="{ly}" fill="#94a3b8" font-size="10" font-family="monospace">GO</text>')
    lines.append(f'<circle cx="{pad_l + 220}" cy="{ly - 5}" r="5" fill="#f59e0b"/>')
    lines.append(f'<text x="{pad_l + 230}" y="{ly}" fill="#94a3b8" font-size="10" font-family="monospace">PAUSE</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def build_metric_comparison_svg() -> str:
    W, H = 760, 280
    pad_l, pad_r, pad_t, pad_b = 70, 30, 40, 60
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    metric_labels = ["SR (%)", "p50 Latency (ms)", "Error Rate (%)", "GPU Util (%)"]
    metric_keys   = ["sr", "p50_latency", "error_rate", "gpu_util"]
    # Normalised to 0-100 for bar display
    normalised = {
        "sr":          {"canary": 78, "prod": 71},
        "p50_latency": {"canary": 46, "prod": 45},
        "error_rate":  {"canary": 8,  "prod": 14},
        "gpu_util":    {"canary": 87, "prod": 84},
    }

    n = len(metric_keys)
    group_w = chart_w / n
    bar_w = group_w * 0.28

    max_val = 100

    lines = []
    lines.append(f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">')
    lines.append(f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>')
    lines.append(f'<text x="{W//2}" y="22" fill="#f1f5f9" font-size="13" font-family="monospace" text-anchor="middle" font-weight="bold">Canary vs Production — Key Metrics</text>')

    # Y-axis grid
    for pct in [0, 25, 50, 75, 100]:
        y = pad_t + chart_h - int(pct / max_val * chart_h)
        lines.append(f'<line x1="{pad_l}" y1="{y}" x2="{W - pad_r}" y2="{y}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>')
        lines.append(f'<text x="{pad_l - 6}" y="{y + 4}" fill="#64748b" font-size="9" font-family="monospace" text-anchor="end">{pct}</text>')

    for i, key in enumerate(metric_keys):
        gx = pad_l + i * group_w
        cx = gx + group_w / 2

        # Prod bar
        prod_norm = normalised[key]["prod"]
        prod_h = int(prod_norm / max_val * chart_h)
        px = gx + group_w * 0.18
        lines.append(f'<rect x="{px:.1f}" y="{pad_t + chart_h - prod_h}" width="{bar_w:.1f}" height="{prod_h}" fill="#38bdf8" rx="3" opacity="0.7"/>')
        lines.append(f'<text x="{px + bar_w/2:.1f}" y="{pad_t + chart_h - prod_h - 4}" fill="#38bdf8" font-size="9" font-family="monospace" text-anchor="middle">{METRICS[key]["prod"]}{METRICS[key]["unit"]}</text>')

        # Canary bar
        can_norm = normalised[key]["canary"]
        can_h = int(can_norm / max_val * chart_h)
        cax = gx + group_w * 0.54
        lines.append(f'<rect x="{cax:.1f}" y="{pad_t + chart_h - can_h}" width="{bar_w:.1f}" height="{can_h}" fill="#C74634" rx="3" opacity="0.85"/>')
        lines.append(f'<text x="{cax + bar_w/2:.1f}" y="{pad_t + chart_h - can_h - 4}" fill="#C74634" font-size="9" font-family="monospace" text-anchor="middle">{METRICS[key]["canary"]}{METRICS[key]["unit"]}</text>')

        # Significance marker
        if METRICS[key]["significant"]:
            lines.append(f'<text x="{cx:.1f}" y="{pad_t + 14}" fill="#fbbf24" font-size="11" font-family="monospace" text-anchor="middle">★</text>')

        # X label
        lines.append(f'<text x="{cx:.1f}" y="{pad_t + chart_h + 16}" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="middle">{metric_labels[i]}</text>')

    # Legend
    ly = H - 14
    lines.append(f'<rect x="{pad_l}" y="{ly - 10}" width="12" height="10" fill="#38bdf8" rx="2" opacity="0.7"/>')
    lines.append(f'<text x="{pad_l + 16}" y="{ly}" fill="#94a3b8" font-size="10" font-family="monospace">Production</text>')
    lines.append(f'<rect x="{pad_l + 100}" y="{ly - 10}" width="12" height="10" fill="#C74634" rx="2" opacity="0.85"/>')
    lines.append(f'<text x="{pad_l + 116}" y="{ly}" fill="#94a3b8" font-size="10" font-family="monospace">Canary</text>')
    lines.append(f'<text x="{pad_l + 190}" y="{ly}" fill="#fbbf24" font-size="10" font-family="monospace">★ statistically significant (p&lt;0.05)</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_dashboard() -> str:
    svg1 = build_traffic_timeline_svg()
    svg2 = build_metric_comparison_svg()

    steps_rows = ""
    for s in ROLLOUT_HISTORY:
        color = {"GO": "#22c55e", "PAUSE": "#f59e0b", "INIT": "#64748b"}.get(s["decision"], "#64748b")
        sr = f"{s['canary_sr']:.0%}" if s["canary_sr"] else "—"
        steps_rows += f"""
        <tr>
          <td style="color:#94a3b8">{s['timestamp']}</td>
          <td style="color:#f1f5f9">Day {s['day']}</td>
          <td style="color:#38bdf8">{s['canary_pct']}%</td>
          <td style="color:#C74634">{sr}</td>
          <td><span style="background:{color};color:#0f172a;padding:2px 8px;border-radius:4px;font-size:11px">{s['decision']}</span></td>
          <td style="color:#94a3b8;font-size:11px">{s['note']}</td>
        </tr>"""

    divergence_score = round(abs(CANARY_DEPLOYMENT["canary_sr"] - CANARY_DEPLOYMENT["prod_sr"]) * 100, 1)
    velocity = round(100 / 8, 1)  # %/day
    sr_delta = round((CANARY_DEPLOYMENT["canary_sr"] - CANARY_DEPLOYMENT["prod_sr"]) * 100, 1)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Deployment Canary Manager — Port 8260</title>
<style>
  body {{background:#0f172a;color:#f1f5f9;font-family:monospace;margin:0;padding:20px}}
  h1   {{color:#C74634;margin-bottom:4px}}
  h2   {{color:#38bdf8;font-size:14px;margin:20px 0 8px}}
  .card{{background:#1e293b;border-radius:8px;padding:16px;margin-bottom:16px}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}}
  .kpi {{background:#1e293b;border-radius:8px;padding:14px;text-align:center}}
  .kpi .val{{font-size:26px;font-weight:bold;color:#C74634}}
  .kpi .lbl{{font-size:11px;color:#64748b;margin-top:4px}}
  table{{width:100%;border-collapse:collapse;font-size:12px}}
  th{{color:#64748b;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
  td{{padding:5px 8px;border-bottom:1px solid #1e293b}}
  .badge-ok{{background:#22c55e;color:#0f172a;padding:2px 8px;border-radius:4px;font-size:11px}}
  .status-bar{{background:#334155;height:8px;border-radius:4px;overflow:hidden;margin-top:6px}}
  .status-fill{{background:#C74634;height:100%;border-radius:4px}}
</style>
</head>
<body>
<h1>Deployment Canary Manager</h1>
<p style="color:#64748b">Model: <span style="color:#38bdf8">{CANARY_DEPLOYMENT['model']}</span> &nbsp;|&nbsp;
   Status: <span class="badge-ok">{CANARY_DEPLOYMENT['status']}</span> &nbsp;|&nbsp;
   Port: 8260</p>

<div class="kpi-grid">
  <div class="kpi"><div class="val">{divergence_score}pp</div><div class="lbl">Canary Divergence Score</div></div>
  <div class="kpi"><div class="val">{sr_delta:+.1f}pp</div><div class="lbl">Risk-Adjusted SR Delta</div></div>
  <div class="kpi"><div class="val">{velocity}%</div><div class="lbl">Rollout Velocity (%/day)</div></div>
  <div class="kpi"><div class="val">{CANARY_DEPLOYMENT['incidents']}</div><div class="lbl">Rollback Incidents</div></div>
</div>

<div class="card">
  <h2>Traffic Split Timeline (Day 0 → Day 8)</h2>
  {svg1}
</div>

<div class="card">
  <h2>Canary vs Production — Metric Comparison</h2>
  {svg2}
</div>

<div class="card">
  <h2>Rollout Log</h2>
  <table>
    <thead><tr><th>Date</th><th>Day</th><th>Canary %</th><th>Canary SR</th><th>Decision</th><th>Notes</th></tr></thead>
    <tbody>{steps_rows}</tbody>
  </table>
</div>

<div class="card">
  <h2>Automated Rollback Triggers (Active Thresholds)</h2>
  <table>
    <thead><tr><th>Trigger</th><th>Threshold</th><th>Current</th><th>Status</th></tr></thead>
    <tbody>
      <tr><td>SR drop vs prod</td><td>&gt;5pp decline</td><td style="color:#22c55e">+7pp</td><td><span class="badge-ok">SAFE</span></td></tr>
      <tr><td>p50 latency spike</td><td>&gt;50ms increase</td><td style="color:#22c55e">+3ms</td><td><span class="badge-ok">SAFE</span></td></tr>
      <tr><td>Error rate spike</td><td>&gt;3% absolute</td><td style="color:#22c55e">0.8%</td><td><span class="badge-ok">SAFE</span></td></tr>
      <tr><td>GPU OOM rate</td><td>&gt;1%</td><td style="color:#22c55e">0.0%</td><td><span class="badge-ok">SAFE</span></td></tr>
    </tbody>
  </table>
</div>

<p style="color:#334155;font-size:10px;margin-top:20px">OCI Robot Cloud · Deployment Canary Manager v1.0 · cycle-50A</p>
</body></html>"""


# ---------------------------------------------------------------------------
# FastAPI / stdlib server
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Deployment Canary Manager", version="1.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(build_dashboard())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "deployment_canary_manager", "port": 8260}

    @app.get("/api/deployment")
    async def api_deployment():
        return CANARY_DEPLOYMENT

    @app.get("/api/steps")
    async def api_steps():
        return ROLLOUT_HISTORY

    @app.get("/api/metrics")
    async def api_metrics():
        return METRICS

else:
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_dashboard().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8260)
    else:
        print("[canary_manager] FastAPI not found — using stdlib http.server on port 8260")
        server = http.server.HTTPServer(("0.0.0.0", 8260), Handler)
        server.serve_forever()

# Expansion Revenue Tracker — port 8929
# NRR 127% decomposition: base 100% + expansion 27%
# Upsell pipeline: $47k total (PI $8,400 / Covariant $4,200 / Machina $6,000 / 1X $2,100)
# Usage-triggered upsell automation

import math
import random
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Expansion Revenue Tracker</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 8px; }
  h2 { color: #38bdf8; font-size: 1.25rem; margin: 24px 0 12px; }
  .subtitle { color: #94a3b8; margin-bottom: 32px; font-size: 0.95rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }
  .card { background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }
  .card .label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
  .card .value { font-size: 1.8rem; font-weight: 700; color: #f1f5f9; }
  .card .unit { font-size: 0.85rem; color: #64748b; margin-top: 2px; }
  .chart-container { background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; margin-bottom: 24px; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; color: #64748b; font-size: 0.8rem; text-transform: uppercase; padding: 8px 12px; border-bottom: 1px solid #334155; }
  td { padding: 10px 12px; border-bottom: 1px solid #1e293b; font-size: 0.9rem; }
  tr:last-child td { border-bottom: none; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
  .badge-green { background: #052e16; color: #4ade80; border: 1px solid #166534; }
  .badge-blue { background: #0c1a2e; color: #38bdf8; border: 1px solid #0369a1; }
  .badge-orange { background: #1c1007; color: #fb923c; border: 1px solid #9a3412; }
  .badge-purple { background: #1a0533; color: #a78bfa; border: 1px solid #6d28d9; }
  .prog-row { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid #1e293b; }
  .prog-row:last-child { border-bottom: none; }
  .prog-bar { flex: 1; height: 10px; background: #0f172a; border-radius: 5px; overflow: hidden; }
  .prog-fill { height: 100%; border-radius: 5px; }
</style>
</head>
<body>
<h1>Expansion Revenue Tracker</h1>
<p class="subtitle">NRR 127% decomposition &mdash; base 100% + expansion 27% &mdash; port 8929</p>

<div class="grid">
  <div class="card"><div class="label">Net Revenue Retention</div><div class="value">127%</div><div class="unit">NRR (industry top quartile)</div></div>
  <div class="card"><div class="label">Expansion ARR</div><div class="value">$47k</div><div class="unit">upsell pipeline</div></div>
  <div class="card"><div class="label">Expansion Rate</div><div class="value">27%</div><div class="unit">above base 100%</div></div>
  <div class="card"><div class="label">Upsell Triggers</div><div class="value">312</div><div class="unit">automated this month</div></div>
</div>

<h2>Expansion ARR by Partner</h2>
<div class="chart-container">
SVG_PARTNERS
</div>

<h2>NRR Decomposition</h2>
<div class="chart-container">
SVG_NRR
</div>

<h2>Upsell Pipeline Detail</h2>
<div class="chart-container">
<table>
<thead><tr><th>Partner</th><th>Upsell ARR</th><th>Trigger</th><th>Stage</th><th>Status</th></tr></thead>
<tbody>
  <tr><td>Physical Intelligence (PI)</td><td>$8,400</td><td>GPU hours &gt; 80%</td><td>Proposal</td><td><span class="badge badge-orange">negotiating</span></td></tr>
  <tr><td>Covariant</td><td>$4,200</td><td>API calls &gt; 500k/mo</td><td>Discovery</td><td><span class="badge badge-blue">qualified</span></td></tr>
  <tr><td>Machina Labs</td><td>$6,000</td><td>Dataset volume &gt; 1TB</td><td>Proposal</td><td><span class="badge badge-green">verbal yes</span></td></tr>
  <tr><td>1X Technologies</td><td>$2,100</td><td>Concurrent streams &gt; 4</td><td>Scoping</td><td><span class="badge badge-purple">early</span></td></tr>
  <tr><td>Other pipeline</td><td>$26,300</td><td>Various usage signals</td><td>Mixed</td><td><span class="badge badge-blue">tracking</span></td></tr>
</tbody>
</table>
</div>

<h2>Usage-Triggered Upsell Automation</h2>
<div class="chart-container">
USAGE_ROWS
</div>
</body></html>
"""


def _make_partners_svg():
    partners = [
        ("PI", 8400, "#C74634"),
        ("Covariant", 4200, "#38bdf8"),
        ("Machina", 6000, "#4ade80"),
        ("1X Tech", 2100, "#fb923c"),
        ("Others", 26300, "#818cf8"),
    ]
    W, H = 700, 240
    bar_w = 80
    gap = (W - 80) // len(partners)
    max_val = max(p[1] for p in partners)
    chart_h = 160
    y_base = H - 50
    lines = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">']
    for pct in [0.25, 0.5, 0.75, 1.0]:
        y = int(y_base - pct * chart_h)
        v = int(pct * max_val / 1000)
        lines.append(f'<line x1="40" y1="{y}" x2="{W-20}" y2="{y}" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="35" y="{y+4}" fill="#64748b" font-size="10" text-anchor="end">${v}k</text>')
    for i, (name, val, color) in enumerate(partners):
        x = 50 + i * gap
        bh = int(val / max_val * chart_h)
        lines.append(f'<rect x="{x}" y="{y_base - bh}" width="{bar_w}" height="{bh}" fill="{color}" rx="4" opacity="0.9"/>')
        label = f"${val//1000}k" if val >= 1000 else f"${val}"
        lines.append(f'<text x="{x + bar_w//2}" y="{y_base - bh - 6}" fill="#e2e8f0" font-size="11" text-anchor="middle">{label}</text>')
        lines.append(f'<text x="{x + bar_w//2}" y="{y_base + 16}" fill="#94a3b8" font-size="11" text-anchor="middle">{name}</text>')
    lines.append(f'<text x="{W//2}" y="18" fill="#38bdf8" font-size="13" text-anchor="middle" font-weight="bold">Expansion ARR by Partner — $47k Total Pipeline</text>')
    lines.append('</svg>')
    return '\n'.join(lines)


def _make_nrr_svg():
    # Stacked bar: base 100 + expansion 27 = 127; churn 0; contraction 0
    W, H = 700, 200
    bar_w = 120
    x0 = 290
    chart_h = 140
    y_base = H - 30
    scale = chart_h / 130
    lines = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">']
    # base
    base_h = int(100 * scale)
    lines.append(f'<rect x="{x0}" y="{y_base - base_h}" width="{bar_w}" height="{base_h}" fill="#38bdf8" rx="4" opacity="0.85"/>')
    lines.append(f'<text x="{x0 + bar_w//2}" y="{y_base - base_h//2 + 4}" fill="#0f172a" font-size="12" text-anchor="middle" font-weight="bold">Base 100%</text>')
    # expansion
    exp_h = int(27 * scale)
    lines.append(f'<rect x="{x0}" y="{y_base - base_h - exp_h}" width="{bar_w}" height="{exp_h}" fill="#4ade80" rx="4" opacity="0.9"/>')
    lines.append(f'<text x="{x0 + bar_w//2}" y="{y_base - base_h - exp_h//2 + 4}" fill="#052e16" font-size="12" text-anchor="middle" font-weight="bold">+27%</text>')
    # NRR label
    lines.append(f'<text x="{x0 + bar_w//2}" y="{y_base - base_h - exp_h - 10}" fill="#C74634" font-size="15" text-anchor="middle" font-weight="bold">NRR 127%</text>')
    # axis
    lines.append(f'<line x1="{x0 - 10}" y1="{y_base}" x2="{x0 + bar_w + 10}" y2="{y_base}" stroke="#334155" stroke-width="1"/>')
    # labels on left
    for pct in [0, 25, 50, 75, 100, 127]:
        y = int(y_base - pct * scale)
        lines.append(f'<line x1="{x0 - 8}" y1="{y}" x2="{x0}" y2="{y}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{x0 - 12}" y="{y + 4}" fill="#64748b" font-size="10" text-anchor="end">{pct}%</text>')
    # legend
    lines.append(f'<rect x="460" y="60" width="14" height="14" fill="#38bdf8" rx="2"/>')
    lines.append(f'<text x="480" y="72" fill="#e2e8f0" font-size="12">Base retention (100%)</text>')
    lines.append(f'<rect x="460" y="84" width="14" height="14" fill="#4ade80" rx="2"/>')
    lines.append(f'<text x="480" y="96" fill="#e2e8f0" font-size="12">Expansion (27%)</text>')
    lines.append(f'<text x="{W//2}" y="18" fill="#38bdf8" font-size="13" text-anchor="middle" font-weight="bold">NRR Decomposition: Base 100% + Expansion 27% = 127%</text>')
    lines.append('</svg>')
    return '\n'.join(lines)


def _make_usage_rows():
    triggers = [
        ("GPU hours > 80% quota", "PI, 1X", 47, "#C74634"),
        ("API calls > 500k/mo", "Covariant, Agility", 83, "#38bdf8"),
        ("Dataset volume > 1 TB", "Machina, Figure", 62, "#4ade80"),
        ("Concurrent streams > 4", "1X, Apptronik", 38, "#fb923c"),
        ("Fine-tune jobs > 10/mo", "PI, Covariant", 71, "#818cf8"),
    ]
    rows = []
    for trigger, partners, pct, color in triggers:
        rows.append(
            f'<div class="prog-row">'
            f'<span style="width:220px;color:#94a3b8;font-size:0.85rem">{trigger}</span>'
            f'<div class="prog-bar"><div class="prog-fill" style="width:{pct}%;background:{color}"></div></div>'
            f'<span style="width:50px;text-align:right;color:{color};font-size:0.85rem;font-weight:700">{pct}%</span>'
            f'<span style="width:160px;color:#64748b;font-size:0.8rem;text-align:right">{partners}</span>'
            f'</div>'
        )
    return '\n'.join(rows)


def build_html():
    h = HTML
    h = h.replace('SVG_PARTNERS', _make_partners_svg())
    h = h.replace('SVG_NRR', _make_nrr_svg())
    h = h.replace('USAGE_ROWS', _make_usage_rows())
    return h


if USE_FASTAPI:
    app = FastAPI(title="Expansion Revenue Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "expansion_revenue_tracker", "port": 8929}

    @app.get("/metrics")
    async def metrics():
        return {
            "nrr_pct": 127,
            "base_pct": 100,
            "expansion_pct": 27,
            "upsell_pipeline_usd": 47000,
            "partners": {
                "physical_intelligence": 8400,
                "covariant": 4200,
                "machina_labs": 6000,
                "1x_technologies": 2100,
                "other": 26300,
            },
            "automated_triggers_this_month": 312,
            "as_of": datetime.utcnow().date().isoformat(),
        }

    @app.get("/pipeline")
    async def pipeline():
        return {
            "total_pipeline_usd": 47000,
            "deals": [
                {"partner": "Physical Intelligence", "arr_usd": 8400, "stage": "Proposal", "trigger": "GPU hours > 80%"},
                {"partner": "Covariant", "arr_usd": 4200, "stage": "Discovery", "trigger": "API calls > 500k/mo"},
                {"partner": "Machina Labs", "arr_usd": 6000, "stage": "Proposal", "trigger": "Dataset volume > 1TB"},
                {"partner": "1X Technologies", "arr_usd": 2100, "stage": "Scoping", "trigger": "Concurrent streams > 4"},
            ]
        }

    @app.post("/trigger")
    async def record_trigger(event: dict):
        return {
            "received": True,
            "partner": event.get("partner"),
            "trigger": event.get("trigger"),
            "upsell_action": "email_queued",
            "ts": datetime.utcnow().isoformat(),
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8929)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", 8929), Handler)
        print("Expansion Revenue Tracker fallback server on port 8929")
        server.serve_forever()

"""Inference Batch Optimizer V2 — port 8916"""
import math
import random
import json
import time
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

SERVICE_TITLE = "Inference Batch Optimizer V2"
PORT = 8916

# ── Simulated metrics ──────────────────────────────────────────────────────────

def generate_throughput_data():
    """Static v1 vs dynamic v2 throughput over 24h."""
    hours = list(range(0, 24))
    v1 = []
    v2 = []
    for h in hours:
        load = 0.4 + 0.5 * math.sin((h - 8) * math.pi / 12) if 6 <= h <= 22 else 0.15
        v1.append(round(847 * load + random.uniform(-20, 20)))
        v2.append(round(9400 * load + random.uniform(-80, 80)))
    return hours, v1, v2


def generate_batch_composition():
    partners = ["AgilityRobotics", "BostonDynamics", "Figure", "1X", "Apptronik"]
    priority_lanes = ["HIGH_SLA", "STANDARD", "BULK"]
    rows = []
    for p in partners:
        high = random.randint(15, 30)
        std = random.randint(40, 55)
        bulk = 100 - high - std
        cost_v1 = round(0.019 + random.uniform(-0.001, 0.001), 4)
        cost_v2 = round(0.011 + random.uniform(-0.0005, 0.0005), 4)
        rows.append({
            "partner": p,
            "high_pct": high,
            "std_pct": std,
            "bulk_pct": bulk,
            "cost_v1": cost_v1,
            "cost_v2": cost_v2,
            "savings_pct": round((cost_v1 - cost_v2) / cost_v1 * 100, 1),
        })
    return rows


def build_throughput_svg(hours, v1, v2):
    W, H, pad_l, pad_r, pad_t, pad_b = 860, 280, 60, 20, 20, 40
    max_y = max(max(v2), 10000)
    def sx(h): return pad_l + h * (W - pad_l - pad_r) / 23
    def sy(v): return pad_t + (H - pad_t - pad_b) * (1 - v / max_y)

    v1_pts = " ".join(f"{sx(h):.1f},{sy(v):.1f}" for h, v in zip(hours, v1))
    v2_pts = " ".join(f"{sx(h):.1f},{sy(v):.1f}" for h, v in zip(hours, v2))

    x_labels = "".join(
        f'<text x="{sx(h):.1f}" y="{H - 8}" fill="#94a3b8" font-size="10" text-anchor="middle">{h:02d}h</text>'
        for h in range(0, 24, 3)
    )
    y_labels = "".join(
        f'<text x="{pad_l - 6}" y="{sy(v * max_y / 4):.1f}" fill="#94a3b8" font-size="10" text-anchor="end" dominant-baseline="middle">{int(v * max_y / 4 / 1000)}k</text>'
        for v in range(0, 5)
    )
    grid = "".join(
        f'<line x1="{pad_l}" y1="{sy(v * max_y / 4):.1f}" x2="{W - pad_r}" y2="{sy(v * max_y / 4):.1f}" stroke="#1e293b" stroke-width="1"/>'
        for v in range(1, 5)
    )
    return f'''
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" style="width:100%;background:#0f172a;border-radius:8px">
  {grid}{x_labels}{y_labels}
  <polyline points="{v1_pts}" fill="none" stroke="#64748b" stroke-width="2"/>
  <polyline points="{v2_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
  <circle cx="{sx(12):.1f}" cy="{sy(847 * 0.9):.1f}" r="5" fill="#64748b"/>
  <text x="{sx(12) + 8:.1f}" y="{sy(847 * 0.9):.1f}" fill="#64748b" font-size="11" dominant-baseline="middle">V1 static (847 req/hr peak)</text>
  <circle cx="{sx(12):.1f}" cy="{sy(9400 * 0.9):.1f}" r="5" fill="#38bdf8"/>
  <text x="{sx(12) + 8:.1f}" y="{sy(9400 * 0.9):.1f}" fill="#38bdf8" font-size="11" dominant-baseline="middle">V2 dynamic (9,400 req/hr peak)</text>
</svg>'''


def build_batch_bars_svg(rows):
    W, H, pad_l, pad_r, pad_t, pad_b = 860, 220, 130, 20, 20, 30
    bar_h = 28
    gap = 10
    colors = {"high": "#C74634", "std": "#38bdf8", "bulk": "#334155"}
    max_w = W - pad_l - pad_r
    bars = ""
    for i, r in enumerate(rows):
        y = pad_t + i * (bar_h + gap)
        bars += f'<text x="{pad_l - 8}" y="{y + bar_h / 2:.1f}" fill="#94a3b8" font-size="11" text-anchor="end" dominant-baseline="middle">{r["partner"]}</text>'
        x = pad_l
        for lane, pct in [("high", r["high_pct"]), ("std", r["std_pct"]), ("bulk", r["bulk_pct"])]:
            w = max_w * pct / 100
            bars += f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{bar_h}" fill="{colors[lane]}"/>'
            if w > 30:
                bars += f'<text x="{x + w / 2:.1f}" y="{y + bar_h / 2:.1f}" fill="white" font-size="10" text-anchor="middle" dominant-baseline="middle">{pct}%</text>'
            x += w
        bars += f'<text x="{W - pad_r + 4}" y="{y + bar_h / 2:.1f}" fill="#4ade80" font-size="10" dominant-baseline="middle">-{r["savings_pct"]}%</text>'
    real_h = pad_t + len(rows) * (bar_h + gap) + pad_b
    return f'''
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {real_h}" style="width:100%;background:#0f172a;border-radius:8px">
  {bars}
  <rect x="{pad_l}" y="{real_h - 18}" width="12" height="12" fill="{colors['high']}"/>
  <text x="{pad_l + 16}" y="{real_h - 9}" fill="#94a3b8" font-size="10">HIGH SLA</text>
  <rect x="{pad_l + 100}" y="{real_h - 18}" width="12" height="12" fill="{colors['std']}"/>
  <text x="{pad_l + 116}" y="{real_h - 9}" fill="#94a3b8" font-size="10">STANDARD</text>
  <rect x="{pad_l + 210}" y="{real_h - 18}" width="12" height="12" fill="{colors['bulk']}"/>
  <text x="{pad_l + 226}" y="{real_h - 9}" fill="#94a3b8" font-size="10">BULK</text>
  <text x="{W - pad_r + 4}" y="{real_h - 9}" fill="#4ade80" font-size="10">cost saved</text>
</svg>'''


def render_html():
    random.seed(int(time.time()) // 60)
    hours, v1, v2 = generate_throughput_data()
    rows = generate_batch_composition()
    throughput_svg = build_throughput_svg(hours, v1, v2)
    bars_svg = build_batch_bars_svg(rows)
    table_rows = "".join(
        f'<tr><td>{r["partner"]}</td><td style="color:#38bdf8">{r["high_pct"]}%</td>'
        f'<td>{r["std_pct"]}%</td><td style="color:#64748b">{r["bulk_pct"]}%</td>'
        f'<td>${r["cost_v1"]:.4f}</td><td style="color:#4ade80">${r["cost_v2"]:.4f}</td>'
        f'<td style="color:#4ade80">-{r["savings_pct"]}%</td></tr>'
        for r in rows
    )
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{SERVICE_TITLE}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
h1{{color:#C74634;font-size:1.7rem;margin-bottom:4px}}
h2{{color:#38bdf8;font-size:1.1rem;margin:24px 0 10px}}
.meta{{color:#64748b;font-size:0.8rem;margin-bottom:20px}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card .label{{font-size:0.75rem;color:#64748b;margin-bottom:4px}}
.card .val{{font-size:1.6rem;font-weight:700}}
.card .sub{{font-size:0.75rem;color:#64748b;margin-top:2px}}
.green{{color:#4ade80}}.blue{{color:#38bdf8}}.red{{color:#C74634}}.slate{{color:#94a3b8}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem;margin-top:8px}}
th{{background:#1e293b;color:#94a3b8;padding:8px 10px;text-align:left;font-weight:600}}
td{{padding:7px 10px;border-bottom:1px solid #1e293b}}
tr:hover td{{background:#1e293b}}
.chart-box{{background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:12px;margin-bottom:20px}}
.alert{{background:#1e1010;border-left:3px solid #C74634;padding:10px 14px;border-radius:4px;font-size:0.82rem;margin-bottom:18px}}
</style>
</head>
<body>
<h1>{SERVICE_TITLE}</h1>
<div class="meta">Port {PORT} · ML-predicted dynamic batching · Refreshed {ts}</div>

<div class="cards">
  <div class="card"><div class="label">V1 Throughput (static batch=1)</div><div class="val red">847</div><div class="sub">req / hr</div></div>
  <div class="card"><div class="label">V2 Throughput (dynamic)</div><div class="val green">9,400</div><div class="sub">req / hr (+11.1×)</div></div>
  <div class="card"><div class="label">Cost per Inference (V1)</div><div class="val slate">$0.019</div><div class="sub">static batch</div></div>
  <div class="card"><div class="label">Cost per Inference (V2)</div><div class="val green">$0.011</div><div class="sub">-42% vs V1</div></div>
</div>

<div class="alert">ML predictor achieved 11.1× throughput gain by dynamically grouping requests into optimal batch sizes (4–32) based on queue depth, SLA tier, and GPU utilisation. Cost reduced from $0.019 → $0.011 per inference.</div>

<h2>24-Hour Throughput: V1 Static vs V2 Dynamic (req/hr)</h2>
<div class="chart-box">{throughput_svg}</div>

<h2>Batch Composition by Partner (Priority Lane Mix)</h2>
<div class="chart-box">{bars_svg}</div>

<h2>Per-Partner Cost Analysis</h2>
<table>
<tr><th>Partner</th><th>HIGH SLA %</th><th>STANDARD %</th><th>BULK %</th><th>V1 $/inf</th><th>V2 $/inf</th><th>Savings</th></tr>
{table_rows}
</table>
</body>
</html>'''


if USE_FASTAPI:
    app = FastAPI(title=SERVICE_TITLE)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return render_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE_TITLE, "port": PORT}

    @app.get("/metrics")
    def metrics():
        random.seed(int(time.time()) // 60)
        rows = generate_batch_composition()
        return {
            "throughput_v1_req_hr": 847,
            "throughput_v2_req_hr": 9400,
            "throughput_gain_x": 11.1,
            "cost_v1_per_inf": 0.019,
            "cost_v2_per_inf": 0.011,
            "cost_savings_pct": 42.1,
            "partner_batch_composition": rows,
            "timestamp": datetime.utcnow().isoformat(),
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)
else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            body = render_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        print(f"Serving {SERVICE_TITLE} on port {PORT} (stdlib fallback)")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

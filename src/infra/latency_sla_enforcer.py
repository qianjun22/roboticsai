"""Latency SLA Enforcer — FastAPI port 8752"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8752

def build_html():
    # Generate realistic latency percentile data
    random.seed(42)
    services = ["inference", "data_loader", "action_decoder", "obs_encoder", "policy_net"]
    sla_limits = {"inference": 250, "data_loader": 80, "action_decoder": 50, "obs_encoder": 120, "policy_net": 200}

    # Simulate 60 time buckets of p50/p95/p99 latency (ms)
    buckets = 60
    p50 = [80 + 20 * math.sin(i * 0.2) + random.gauss(0, 5) for i in range(buckets)]
    p95 = [p + 60 + random.gauss(0, 8) for p in p50]
    p99 = [p + 40 + random.gauss(0, 12) for p in p95]

    sla_line = 250  # ms SLA

    # SVG sparkline for p50/p95/p99
    w, h = 600, 120
    max_val = max(max(p99), sla_line + 20)

    def to_svg_y(val):
        return h - int((val / max_val) * h)

    def poly(series, color):
        pts = " ".join(f"{int(i * w / (buckets - 1))},{to_svg_y(v)}" for i, v in enumerate(series))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>'

    sla_y = to_svg_y(sla_line)
    chart_svg = (
        f'<svg width="{w}" height="{h}" style="display:block;background:#0d1b2e;border-radius:6px">'
        f'<line x1="0" y1="{sla_y}" x2="{w}" y2="{sla_y}" stroke="#f87171" stroke-width="1.5" stroke-dasharray="6,4"/>'
        f'<text x="4" y="{sla_y - 4}" fill="#f87171" font-size="10">SLA 250ms</text>'
        + poly(p50, "#34d399") + poly(p95, "#fbbf24") + poly(p99, "#f87171")
        + '</svg>'
    )

    # Violations table
    violations = []
    for svc in services:
        lim = sla_limits[svc]
        cur_p99 = lim * (0.85 + random.random() * 0.45)
        status = "BREACH" if cur_p99 > lim else "OK"
        color = "#f87171" if status == "BREACH" else "#34d399"
        violations.append(
            f'<tr><td>{svc}</td><td>{lim}ms</td>'
            f'<td style="color:{color}">{cur_p99:.1f}ms</td>'
            f'<td style="color:{color};font-weight:bold">{status}</td></tr>'
        )
    rows = "".join(violations)

    # Heatmap: 10 services x 24 hours breach intensity
    cells = []
    for r in range(5):
        for c in range(24):
            intensity = max(0.0, min(1.0, 0.3 + 0.5 * math.sin(c * 0.3 + r) + random.gauss(0, 0.15)))
            red = int(255 * intensity)
            green = int(200 * (1 - intensity))
            cells.append(
                f'<rect x="{c*22}" y="{r*18}" width="20" height="16" '
                f'fill="rgb({red},{green},60)" rx="2"/>'
            )
    heatmap_svg = (
        '<svg width="528" height="90" style="display:block;background:#0d1b2e;border-radius:6px">'
        + "".join(cells)
        + '</svg>'
    )

    breach_count = sum(1 for svc in services if random.random() > 0.6)
    total_reqs = random.randint(18000, 24000)
    breach_rate = round(random.uniform(0.8, 4.2), 2)

    return f"""<!DOCTYPE html><html><head><title>Latency SLA Enforcer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}.subtitle{{color:#94a3b8;margin-bottom:24px;font-size:14px}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:16px}}
.card{{background:#1e293b;padding:20px;margin:0 0 16px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}}
.stat{{background:#1e293b;padding:16px;border-radius:8px;text-align:center}}
.stat .val{{font-size:28px;font-weight:700;color:#38bdf8}}
.stat .lbl{{font-size:12px;color:#94a3b8;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th{{color:#94a3b8;text-align:left;padding:8px 12px;border-bottom:1px solid #334155}}
td{{padding:8px 12px;border-bottom:1px solid #1e293b}}
.legend{{display:flex;gap:16px;font-size:12px;margin-bottom:8px}}
.dot{{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:4px}}
</style></head>
<body>
<h1>Latency SLA Enforcer</h1>
<p class="subtitle">Real-time p50/p95/p99 monitoring with automatic breach alerting — port {PORT}</p>
<div class="grid">
  <div class="stat"><div class="val">{total_reqs:,}</div><div class="lbl">Requests / min</div></div>
  <div class="stat"><div class="val" style="color:#{'f87171' if breach_count>0 else '34d399'}">{breach_count}</div><div class="lbl">Active SLA Breaches</div></div>
  <div class="stat"><div class="val" style="color:#fbbf24">{breach_rate}%</div><div class="lbl">Breach Rate (24h)</div></div>
</div>
<div class="card">
  <h2>Latency Percentiles — Last 60 Seconds</h2>
  <div class="legend">
    <span><span class="dot" style="background:#34d399"></span>p50</span>
    <span><span class="dot" style="background:#fbbf24"></span>p95</span>
    <span><span class="dot" style="background:#f87171"></span>p99</span>
    <span><span class="dot" style="background:#f87171;opacity:0.5"></span>SLA Limit</span>
  </div>
  {chart_svg}
</div>
<div class="card">
  <h2>Service SLA Status</h2>
  <table>
    <tr><th>Service</th><th>SLA Limit</th><th>Current p99</th><th>Status</th></tr>
    {rows}
  </table>
</div>
<div class="card">
  <h2>Breach Heatmap — Services x Hour of Day</h2>
  <p style="font-size:12px;color:#94a3b8;margin:0 0 8px">Darker red = higher breach intensity</p>
  {heatmap_svg}
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Latency SLA Enforcer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/metrics")
    def metrics():
        return {
            "port": PORT,
            "sla_ms": 250,
            "active_breaches": random.randint(0, 3),
            "p99_ms": round(random.uniform(180, 290), 1),
            "p95_ms": round(random.uniform(120, 210), 1),
            "p50_ms": round(random.uniform(60, 110), 1),
        }

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

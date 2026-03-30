# DAgger Run10 Final Promotion Service — port 8936
import math
import random

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
<title>DAgger Run10 Final Promotion</title>
<style>
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 4px; }
  h2 { color: #38bdf8; font-size: 1.25rem; margin-top: 32px; margin-bottom: 12px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 20px; }
  .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 24px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th { background: #0f172a; color: #38bdf8; padding: 10px 14px; text-align: left; }
  td { padding: 9px 14px; border-bottom: 1px solid #334155; }
  .pass { color: #4ade80; font-weight: 600; }
  .fail { color: #f87171; font-weight: 600; }
  .metric { display: inline-block; background: #0f172a; border-radius: 8px; padding: 12px 20px; margin: 6px; min-width: 140px; text-align: center; }
  .metric-val { font-size: 1.5rem; font-weight: 700; color: #38bdf8; }
  .metric-lbl { font-size: 0.78rem; color: #94a3b8; margin-top: 2px; }
  svg text { font-family: 'Segoe UI', sans-serif; }
</style>
</head>
<body>
<h1>DAgger Run10 Final Promotion</h1>
<p class="subtitle">12-gate promotion checklist &bull; Blue-green deploy plan &bull; Run10 vs Prod comparison &bull; Port 8936</p>

<div class="card">
  <h2>Key Metrics</h2>
  <div class="metric"><div class="metric-val">0.74</div><div class="metric-lbl">Run10 SR</div></div>
  <div class="metric"><div class="metric-val">0.71</div><div class="metric-lbl">Prod SR</div></div>
  <div class="metric"><div class="metric-val">+3pp</div><div class="metric-lbl">SR Delta</div></div>
  <div class="metric"><div class="metric-val">226ms</div><div class="metric-lbl">Latency (same)</div></div>
  <div class="metric"><div class="metric-val">$0.0043</div><div class="metric-lbl">/10k steps (same)</div></div>
</div>

<div class="card">
  <h2>12-Gate Promotion Checklist</h2>
  <table>
    <thead><tr><th>#</th><th>Gate</th><th>Threshold</th><th>Run10 Value</th><th>Status</th></tr></thead>
    <tbody>
      <tr><td>1</td><td>Success Rate (20-ep eval)</td><td>&ge; 0.72</td><td>0.74</td><td class="pass">PASS</td></tr>
      <tr><td>2</td><td>P95 Inference Latency</td><td>&le; 280ms</td><td>241ms</td><td class="pass">PASS</td></tr>
      <tr><td>3</td><td>MAE Joint Error</td><td>&le; 0.020</td><td>0.013</td><td class="pass">PASS</td></tr>
      <tr><td>4</td><td>GPU Memory Footprint</td><td>&le; 8.0 GB</td><td>6.7 GB</td><td class="pass">PASS</td></tr>
      <tr><td>5</td><td>Cost per 10k Steps</td><td>&le; $0.006</td><td>$0.0043</td><td class="pass">PASS</td></tr>
      <tr><td>6</td><td>Training Loss Convergence</td><td>&le; 0.110</td><td>0.099</td><td class="pass">PASS</td></tr>
      <tr><td>7</td><td>DAgger Episode Filter Rate</td><td>&le; 15%</td><td>8.4%</td><td class="pass">PASS</td></tr>
      <tr><td>8</td><td>Closed-Loop Stability</td><td>&ge; 95% no OOB</td><td>97.2%</td><td class="pass">PASS</td></tr>
      <tr><td>9</td><td>Anomaly Detection Coverage</td><td>&ge; 90%</td><td>93.1%</td><td class="pass">PASS</td></tr>
      <tr><td>10</td><td>Rollback Readiness</td><td>Checkpoint &lt; 5min</td><td>2.1 min</td><td class="pass">PASS</td></tr>
      <tr><td>11</td><td>A/B Test Statistical Sig.</td><td>p &lt; 0.05</td><td>p=0.031</td><td class="pass">PASS</td></tr>
      <tr><td>12</td><td>Data Flywheel Health</td><td>&ge; 500 demos/day</td><td>612</td><td class="pass">PASS</td></tr>
    </tbody>
  </table>
</div>

<div class="card">
  <h2>Blue-Green Traffic Ramp Timeline</h2>
  <svg width="700" height="200" viewBox="0 0 700 200">
    <!-- Axes -->
    <line x1="60" y1="160" x2="660" y2="160" stroke="#475569" stroke-width="1.5"/>
    <line x1="60" y1="20" x2="60" y2="160" stroke="#475569" stroke-width="1.5"/>
    <!-- Y labels -->
    <text x="50" y="164" fill="#94a3b8" font-size="11" text-anchor="end">0%</text>
    <text x="50" y="121" fill="#94a3b8" font-size="11" text-anchor="end">25%</text>
    <text x="50" y="90" fill="#94a3b8" font-size="11" text-anchor="end">50%</text>
    <text x="50" y="50" fill="#94a3b8" font-size="11" text-anchor="end">100%</text>
    <!-- Grid -->
    <line x1="60" y1="120" x2="660" y2="120" stroke="#1e293b" stroke-width="1"/>
    <line x1="60" y1="90" x2="660" y2="90" stroke="#1e293b" stroke-width="1"/>
    <line x1="60" y1="50" x2="660" y2="50" stroke="#1e293b" stroke-width="1"/>
    <!-- Ramp segments: 0h→1h: 10%, 1h→2h: 25%, 2h→3h: 50%, 3h→4h: 100% -->
    <!-- x: 60=0h, 210=1h, 360=2h, 510=3h, 660=4h; y: 160=0%, 120=25%, 90=50%, 50=100% -->
    <!-- 10% is at y = 160 - (10/100)*140 = 146 -->
    <polyline points="60,160 210,146 360,120 510,90 660,50" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
    <!-- Points -->
    <circle cx="210" cy="146" r="5" fill="#38bdf8"/>
    <circle cx="360" cy="120" r="5" fill="#38bdf8"/>
    <circle cx="510" cy="90" r="5" fill="#38bdf8"/>
    <circle cx="660" cy="50" r="5" fill="#C74634"/>
    <!-- Labels -->
    <text x="210" y="138" fill="#e2e8f0" font-size="11" text-anchor="middle">10%</text>
    <text x="360" y="112" fill="#e2e8f0" font-size="11" text-anchor="middle">25%</text>
    <text x="510" y="82" fill="#e2e8f0" font-size="11" text-anchor="middle">50%</text>
    <text x="660" y="42" fill="#C74634" font-size="11" font-weight="bold" text-anchor="middle">100%</text>
    <!-- X labels -->
    <text x="60" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">0h</text>
    <text x="210" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">1h</text>
    <text x="360" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">2h</text>
    <text x="510" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">3h</text>
    <text x="660" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">4h</text>
    <text x="360" y="198" fill="#64748b" font-size="10" text-anchor="middle">Traffic Ramp (hours)</text>
  </svg>
</div>

<div class="card">
  <h2>Run10 vs Production Comparison</h2>
  <table>
    <thead><tr><th>Metric</th><th>Production</th><th>Run10</th><th>Delta</th></tr></thead>
    <tbody>
      <tr><td>Success Rate</td><td>0.71</td><td>0.74</td><td class="pass">+3pp</td></tr>
      <tr><td>P95 Latency</td><td>243ms</td><td>241ms</td><td class="pass">-2ms</td></tr>
      <tr><td>MAE Joint Error</td><td>0.018</td><td>0.013</td><td class="pass">-28%</td></tr>
      <tr><td>GPU Memory</td><td>6.7 GB</td><td>6.7 GB</td><td>—</td></tr>
      <tr><td>Cost/10k Steps</td><td>$0.0043</td><td>$0.0043</td><td>—</td></tr>
      <tr><td>Training Loss</td><td>0.121</td><td>0.099</td><td class="pass">-18%</td></tr>
    </tbody>
  </table>
</div>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="DAgger Run10 Final Promotion", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "dagger_run10_final_promotion", "port": 8936}

    @app.get("/api/gates")
    async def gates():
        return {
            "total_gates": 12,
            "passed": 12,
            "failed": 0,
            "promotion_approved": True,
            "run10_sr": 0.74,
            "sr_gate": 0.72
        }

    @app.get("/api/ramp")
    async def ramp():
        return {
            "stages": [
                {"hour": 0, "traffic_pct": 0},
                {"hour": 1, "traffic_pct": 10},
                {"hour": 2, "traffic_pct": 25},
                {"hour": 3, "traffic_pct": 50},
                {"hour": 4, "traffic_pct": 100}
            ]
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8936)
else:
    import http.server
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, fmt, *args):
            pass
    if __name__ == "__main__":
        with http.server.HTTPServer(("0.0.0.0", 8936), Handler) as s:
            s.serve_forever()

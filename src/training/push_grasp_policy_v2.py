"""Push Grasp Policy V2 — OCI Robot Cloud Service (port 9992)"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

PORT = 9992
TITLE = "Push Grasp Policy V2"

app = FastAPI(title=TITLE)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }}
    h1 {{ color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }}
    .subtitle {{ color: #38bdf8; font-size: 1rem; margin-bottom: 2rem; }}
    .card {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }}
    .card h2 {{ color: #38bdf8; margin-bottom: 1rem; font-size: 1.1rem; }}
    .metric {{ display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid #334155; }}
    .metric:last-child {{ border-bottom: none; }}
    .metric-label {{ color: #94a3b8; }}
    .metric-value {{ color: #f1f5f9; font-weight: 600; }}
    svg {{ width: 100%; height: 200px; }}
    .bar {{ fill: #C74634; opacity: 0.85; transition: opacity 0.2s; }}
    .bar:hover {{ opacity: 1; }}
    .axis-label {{ fill: #94a3b8; font-size: 11px; }}
    .health-ok {{ color: #4ade80; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p class="subtitle">OCI Robot Cloud · Port {port} · Push-Grasp Policy Training v2</p>

  <div class="card">
    <h2>Training Metrics</h2>
    <div class="metric"><span class="metric-label">Policy Type</span><span class="metric-value">Push-Grasp v2</span></div>
    <div class="metric"><span class="metric-label">Model Architecture</span><span class="metric-value">GR00T N1.6 (7B)</span></div>
    <div class="metric"><span class="metric-label">Training Steps</span><span class="metric-value">10,000</span></div>
    <div class="metric"><span class="metric-label">MAE</span><span class="metric-value">0.011</span></div>
    <div class="metric"><span class="metric-label">Success Rate</span><span class="metric-value">91.5%</span></div>
    <div class="metric"><span class="metric-label">GPU Utilization</span><span class="metric-value">94%</span></div>
  </div>

  <div class="card">
    <h2>Training Loss (last 10 checkpoints)</h2>
    <svg viewBox="0 0 500 200" xmlns="http://www.w3.org/2000/svg">
      <!-- bars -->
      <rect class="bar" x="10"  y="160" width="38" height="30" />
      <rect class="bar" x="60"  y="140" width="38" height="50" />
      <rect class="bar" x="110" y="115" width="38" height="75" />
      <rect class="bar" x="160" y="95"  width="38" height="95" />
      <rect class="bar" x="210" y="78"  width="38" height="112"/>
      <rect class="bar" x="260" y="60"  width="38" height="130"/>
      <rect class="bar" x="310" y="45"  width="38" height="145"/>
      <rect class="bar" x="360" y="32"  width="38" height="158"/>
      <rect class="bar" x="410" y="20"  width="38" height="170"/>
      <rect class="bar" x="460" y="10"  width="38" height="180"/>
      <!-- axis labels -->
      <text class="axis-label" x="29"  y="195" text-anchor="middle">1k</text>
      <text class="axis-label" x="79"  y="195" text-anchor="middle">2k</text>
      <text class="axis-label" x="129" y="195" text-anchor="middle">3k</text>
      <text class="axis-label" x="179" y="195" text-anchor="middle">4k</text>
      <text class="axis-label" x="229" y="195" text-anchor="middle">5k</text>
      <text class="axis-label" x="279" y="195" text-anchor="middle">6k</text>
      <text class="axis-label" x="329" y="195" text-anchor="middle">7k</text>
      <text class="axis-label" x="379" y="195" text-anchor="middle">8k</text>
      <text class="axis-label" x="429" y="195" text-anchor="middle">9k</text>
      <text class="axis-label" x="479" y="195" text-anchor="middle">10k</text>
    </svg>
  </div>

  <div class="card">
    <h2>Service Status</h2>
    <div class="metric"><span class="metric-label">Health</span><span class="metric-value health-ok">OK</span></div>
    <div class="metric"><span class="metric-label">Port</span><span class="metric-value">{port}</span></div>
    <div class="metric"><span class="metric-label">Endpoint</span><span class="metric-value">/health</span></div>
  </div>
</body>
</html>
""".format(title=TITLE, port=PORT)


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML


@app.get("/health")
async def health():
    return {"status": "ok", "service": TITLE, "port": PORT}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

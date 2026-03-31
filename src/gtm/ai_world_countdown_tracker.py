"""AI World Countdown Tracker — OCI Robot Cloud Service (port 9993)"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

PORT = 9993
TITLE = "AI World Countdown Tracker"

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
    .countdown {{ font-size: 3rem; color: #C74634; font-weight: 800; text-align: center; padding: 1.5rem 0; }}
    .countdown span {{ color: #38bdf8; font-size: 1rem; display: block; margin-top: 0.5rem; font-weight: 400; }}
    svg {{ width: 100%; height: 200px; }}
    .bar {{ fill: #38bdf8; opacity: 0.85; transition: opacity 0.2s; }}
    .bar:hover {{ opacity: 1; }}
    .axis-label {{ fill: #94a3b8; font-size: 11px; }}
    .health-ok {{ color: #4ade80; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p class="subtitle">OCI Robot Cloud · Port {port} · GTM Event Readiness Dashboard</p>

  <div class="card">
    <h2>AI World 2026 Countdown</h2>
    <div class="countdown" id="countdown">--d --h --m
      <span>Loading countdown...</span>
    </div>
  </div>

  <div class="card">
    <h2>Milestone Completion (last 10 weeks)</h2>
    <svg viewBox="0 0 500 200" xmlns="http://www.w3.org/2000/svg">
      <!-- bars representing weekly milestone % -->
      <rect class="bar" x="10"  y="170" width="38" height="20" />
      <rect class="bar" x="60"  y="155" width="38" height="35" />
      <rect class="bar" x="110" y="135" width="38" height="55" />
      <rect class="bar" x="160" y="110" width="38" height="80" />
      <rect class="bar" x="210" y="90"  width="38" height="100"/>
      <rect class="bar" x="260" y="68"  width="38" height="122"/>
      <rect class="bar" x="310" y="50"  width="38" height="140"/>
      <rect class="bar" x="360" y="35"  width="38" height="155"/>
      <rect class="bar" x="410" y="18"  width="38" height="172"/>
      <rect class="bar" x="460" y="5"   width="38" height="185"/>
      <!-- axis labels -->
      <text class="axis-label" x="29"  y="195" text-anchor="middle">W1</text>
      <text class="axis-label" x="79"  y="195" text-anchor="middle">W2</text>
      <text class="axis-label" x="129" y="195" text-anchor="middle">W3</text>
      <text class="axis-label" x="179" y="195" text-anchor="middle">W4</text>
      <text class="axis-label" x="229" y="195" text-anchor="middle">W5</text>
      <text class="axis-label" x="279" y="195" text-anchor="middle">W6</text>
      <text class="axis-label" x="329" y="195" text-anchor="middle">W7</text>
      <text class="axis-label" x="379" y="195" text-anchor="middle">W8</text>
      <text class="axis-label" x="429" y="195" text-anchor="middle">W9</text>
      <text class="axis-label" x="479" y="195" text-anchor="middle">W10</text>
    </svg>
  </div>

  <div class="card">
    <h2>GTM Readiness</h2>
    <div class="metric"><span class="metric-label">Demo Environment</span><span class="metric-value">Ready</span></div>
    <div class="metric"><span class="metric-label">Booth Hardware</span><span class="metric-value">Shipped</span></div>
    <div class="metric"><span class="metric-label">Slide Deck</span><span class="metric-value">Final v3</span></div>
    <div class="metric"><span class="metric-label">Press Kit</span><span class="metric-value">Approved</span></div>
    <div class="metric"><span class="metric-label">Leads Pipeline</span><span class="metric-value">$2.1M ARR</span></div>
    <div class="metric"><span class="metric-label">Speaking Slot</span><span class="metric-value">Confirmed</span></div>
  </div>

  <div class="card">
    <h2>Service Status</h2>
    <div class="metric"><span class="metric-label">Health</span><span class="metric-value health-ok">OK</span></div>
    <div class="metric"><span class="metric-label">Port</span><span class="metric-value">{port}</span></div>
    <div class="metric"><span class="metric-label">Endpoint</span><span class="metric-value">/health</span></div>
  </div>

  <script>
    function updateCountdown() {{
      // AI World 2026 target: June 9, 2026
      const target = new Date('2026-06-09T09:00:00Z');
      const now = new Date();
      const diff = target - now;
      if (diff <= 0) {{
        document.getElementById('countdown').innerHTML = 'LIVE NOW! <span>AI World 2026 is happening!</span>';
        return;
      }}
      const days = Math.floor(diff / 86400000);
      const hours = Math.floor((diff % 86400000) / 3600000);
      const mins = Math.floor((diff % 3600000) / 60000);
      document.getElementById('countdown').innerHTML =
        days + 'd ' + hours + 'h ' + mins + 'm<span>until AI World 2026 · June 9, 2026</span>';
    }}
    updateCountdown();
    setInterval(updateCountdown, 60000);
  </script>
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

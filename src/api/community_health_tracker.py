"""Community Health Tracker — port 8987
Tracks GitHub, Discord, and Newsletter community metrics.
"""
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
<title>Community Health Tracker</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.25rem; }
  .subtitle { color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; }
  h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin-bottom: 2rem; }
  .card { background: #1e293b; border-radius: 10px; padding: 1.25rem; border: 1px solid #334155; }
  .card .label { color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }
  .card .value { color: #f1f5f9; font-size: 1.6rem; font-weight: 700; }
  .card .sub { color: #64748b; font-size: 0.8rem; margin-top: 0.2rem; }
  .badge-growth { display: inline-block; background: #064e3b; color: #34d399; border-radius: 4px; font-size: 0.72rem; padding: 0.15rem 0.4rem; margin-left: 0.4rem; font-weight: 600; vertical-align: middle; }
  .panel { background: #1e293b; border-radius: 10px; padding: 1.5rem; border: 1px solid #334155; margin-bottom: 2rem; }
  .channel-row { display: flex; align-items: center; gap: 1rem; padding: 0.7rem 0; border-bottom: 1px solid #334155; }
  .channel-row:last-child { border-bottom: none; }
  .ch-icon { width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; flex-shrink: 0; }
  .ch-github  { background: #1c2a3a; color: #58a6ff; }
  .ch-discord { background: #1e1f3b; color: #818cf8; }
  .ch-news    { background: #1a2e1a; color: #4ade80; }
  .ch-name  { flex: 1; color: #cbd5e1; font-weight: 600; font-size: 0.95rem; }
  .ch-stats { color: #94a3b8; font-size: 0.82rem; line-height: 1.5; text-align: right; }
  .score-wrap { display: flex; align-items: center; gap: 1.5rem; }
  .score-circle { position: relative; flex-shrink: 0; }
  .score-label { color: #94a3b8; font-size: 0.82rem; margin-top: 0.5rem; text-align: center; }
  .breakdown { flex: 1; }
  .bar-row { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.6rem; }
  .bar-name { color: #cbd5e1; font-size: 0.85rem; min-width: 130px; }
  .bar-track { flex: 1; background: #0f172a; border-radius: 4px; height: 10px; overflow: hidden; }
  .bar-fill  { height: 100%; border-radius: 4px; }
  .bar-val  { color: #94a3b8; font-size: 0.8rem; min-width: 32px; text-align: right; }
  svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
  .footer { color: #475569; font-size: 0.78rem; margin-top: 2rem; }
</style>
</head>
<body>
<h1>Community Health Tracker</h1>
<p class="subtitle">GitHub &bull; Discord &bull; Newsletter &mdash; Port 8987</p>

<div class="grid">
  <div class="card">
    <div class="label">GitHub Stars</div>
    <div class="value">847 <span class="badge-growth">+28%/mo</span></div>
    <div class="sub">124 forks &bull; 23 contributors</div>
  </div>
  <div class="card">
    <div class="label">Discord Members</div>
    <div class="value">312 <span class="badge-growth">+28%/mo</span></div>
    <div class="sub">47 DAU &bull; 128 weekly active</div>
  </div>
  <div class="card">
    <div class="label">Newsletter Subs</div>
    <div class="value">1,247 <span class="badge-growth">+28%/mo</span></div>
    <div class="sub">47% open rate &bull; 12% CTR</div>
  </div>
  <div class="card">
    <div class="label">Health Score</div>
    <div class="value">74<span style="font-size:1rem;color:#94a3b8">/100</span></div>
    <div class="sub">composite community index</div>
  </div>
</div>

<div class="panel">
  <h2>Community Channels</h2>
  <div class="channel-row">
    <div class="ch-icon ch-github">&#9733;</div>
    <div class="ch-name">GitHub</div>
    <div class="ch-stats">847 stars &bull; 124 forks &bull; 23 contributors<br>Issues: 38 open / 214 closed &bull; PR merge rate 91%</div>
  </div>
  <div class="channel-row">
    <div class="ch-icon ch-discord">&#9670;</div>
    <div class="ch-name">Discord</div>
    <div class="ch-stats">312 members &bull; 47 DAU &bull; 128 WAU<br>Avg response time 18 min &bull; 6 active channels</div>
  </div>
  <div class="channel-row">
    <div class="ch-icon ch-news">&#9993;</div>
    <div class="ch-name">Newsletter</div>
    <div class="ch-stats">1,247 subscribers &bull; 47% open rate &bull; 12% CTR<br>Bi-weekly cadence &bull; 0.4% unsubscribe rate</div>
  </div>
</div>

<div class="panel">
  <h2>Channel Growth &mdash; Last 8 Weeks</h2>
  <svg width="100%" height="210" viewBox="0 0 700 210" preserveAspectRatio="xMidYMid meet">
    <!-- axes -->
    <line x1="50" y1="10" x2="50" y2="175" stroke="#334155" stroke-width="1"/>
    <line x1="50" y1="175" x2="690" y2="175" stroke="#334155" stroke-width="1"/>
    <!-- y labels -->
    <text x="44" y="14"  fill="#64748b" font-size="10" text-anchor="end">1300</text>
    <text x="44" y="60"  fill="#64748b" font-size="10" text-anchor="end">900</text>
    <text x="44" y="115" fill="#64748b" font-size="10" text-anchor="end">500</text>
    <text x="44" y="175" fill="#64748b" font-size="10" text-anchor="end">0</text>
    <!-- Newsletter line (highest) -->
    <polyline
      points="50,148 148,138 246,125 344,115 442,102 540,88 638,76 690,68"
      fill="none" stroke="#4ade80" stroke-width="2.5" stroke-linejoin="round"/>
    <!-- GitHub stars line -->
    <polyline
      points="50,160 148,152 246,143 344,136 442,128 540,118 638,108 690,100"
      fill="none" stroke="#58a6ff" stroke-width="2.5" stroke-linejoin="round"/>
    <!-- Discord line -->
    <polyline
      points="50,168 148,164 246,160 344,156 442,150 540,145 638,140 690,136"
      fill="none" stroke="#818cf8" stroke-width="2.5" stroke-linejoin="round"/>
    <!-- x labels -->
    <text x="50"  y="190" fill="#64748b" font-size="9" text-anchor="middle">W1</text>
    <text x="148" y="190" fill="#64748b" font-size="9" text-anchor="middle">W2</text>
    <text x="246" y="190" fill="#64748b" font-size="9" text-anchor="middle">W3</text>
    <text x="344" y="190" fill="#64748b" font-size="9" text-anchor="middle">W4</text>
    <text x="442" y="190" fill="#64748b" font-size="9" text-anchor="middle">W5</text>
    <text x="540" y="190" fill="#64748b" font-size="9" text-anchor="middle">W6</text>
    <text x="638" y="190" fill="#64748b" font-size="9" text-anchor="middle">W7</text>
    <text x="690" y="190" fill="#64748b" font-size="9" text-anchor="middle">W8</text>
    <!-- legend -->
    <rect x="55"  y="12" width="10" height="10" fill="#4ade80" rx="2"/>
    <text x="69"  y="21" fill="#e2e8f0" font-size="10">Newsletter</text>
    <rect x="165" y="12" width="10" height="10" fill="#58a6ff" rx="2"/>
    <text x="179" y="21" fill="#e2e8f0" font-size="10">GitHub Stars</text>
    <rect x="285" y="12" width="10" height="10" fill="#818cf8" rx="2"/>
    <text x="299" y="21" fill="#e2e8f0" font-size="10">Discord Members</text>
    <text x="370" y="205" fill="#64748b" font-size="10" text-anchor="middle">member / subscriber count</text>
  </svg>
</div>

<div class="panel">
  <h2>Health Score Breakdown (74/100)</h2>
  <div class="score-wrap">
    <div class="score-circle">
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="42" fill="none" stroke="#334155" stroke-width="10"/>
        <circle cx="50" cy="50" r="42" fill="none" stroke="#38bdf8" stroke-width="10"
          stroke-dasharray="263.9" stroke-dashoffset="68.6"
          stroke-linecap="round" transform="rotate(-90 50 50)"/>
        <text x="50" y="55" fill="#f1f5f9" font-size="22" font-weight="700" text-anchor="middle">74</text>
      </svg>
      <div class="score-label">out of 100</div>
    </div>
    <div class="breakdown">
      <div class="bar-row">
        <span class="bar-name">Engagement Rate</span>
        <div class="bar-track"><div class="bar-fill" style="width:82%;background:#38bdf8"></div></div>
        <span class="bar-val">82</span>
      </div>
      <div class="bar-row">
        <span class="bar-name">Growth Velocity</span>
        <div class="bar-track"><div class="bar-fill" style="width:78%;background:#4ade80"></div></div>
        <span class="bar-val">78</span>
      </div>
      <div class="bar-row">
        <span class="bar-name">Content Quality</span>
        <div class="bar-track"><div class="bar-fill" style="width:70%;background:#fbbf24"></div></div>
        <span class="bar-val">70</span>
      </div>
      <div class="bar-row">
        <span class="bar-name">Retention</span>
        <div class="bar-track"><div class="bar-fill" style="width:68%;background:#f472b6"></div></div>
        <span class="bar-val">68</span>
      </div>
      <div class="bar-row">
        <span class="bar-name">Response Time</span>
        <div class="bar-track"><div class="bar-fill" style="width:74%;background:#a78bfa"></div></div>
        <span class="bar-val">74</span>
      </div>
    </div>
  </div>
</div>

<p class="footer">Community Health Tracker &mdash; OCI Robot Cloud &mdash; cycle-232B</p>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Community Health Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTMLResponse(content=HTML)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "community_health_tracker", "port": 8987}

    @app.get("/metrics")
    async def metrics():
        return {
            "health_score": 74,
            "growth_rate_monthly": 0.28,
            "github": {"stars": 847, "forks": 124, "contributors": 23},
            "discord": {"members": 312, "dau": 47, "wau": 128},
            "newsletter": {"subscribers": 1247, "open_rate": 0.47, "ctr": 0.12},
        }

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8987)
    else:
        print("FastAPI not found — falling back to stdlib HTTPServer on port 8987")
        HTTPServer(("0.0.0.0", 8987), Handler).serve_forever()

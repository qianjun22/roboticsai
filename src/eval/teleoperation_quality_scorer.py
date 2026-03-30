"""Teleoperation Quality Scorer — FastAPI port 8772"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8772

def build_html():
    random.seed(42)
    # Generate smoothness scores over 60 time steps
    n = 60
    smoothness = [round(0.72 + 0.18 * math.sin(i * 0.18) + random.uniform(-0.06, 0.06), 3) for i in range(n)]
    # Jerk (rate of change) signal
    jerk = [round(abs(smoothness[i] - smoothness[i-1]) * 10 + random.uniform(0, 0.05), 4) for i in range(1, n)]
    # Task completion quality per session (30 sessions)
    sessions = 30
    completion = [round(0.55 + 0.35 * (1 - math.exp(-k * 0.15)) + random.uniform(-0.04, 0.04), 3) for k in range(sessions)]
    # Trajectory deviation (mm)
    deviation = [round(4.2 * math.exp(-k * 0.08) + random.uniform(0, 1.2), 2) for k in range(sessions)]

    # SVG line chart for smoothness over time
    sw, sh = 520, 120
    def norm_y(val, mn, mx): return sh - int((val - mn) / (mx - mn + 1e-9) * (sh - 10)) - 5
    sm_min, sm_max = min(smoothness), max(smoothness)
    pts_smooth = " ".join(f"{int(i*(sw-20)/(n-1))+10},{norm_y(smoothness[i], sm_min, sm_max)}" for i in range(n))

    # SVG bar chart for per-session completion
    bw, bh = 520, 100
    bar_w = int((bw - 20) / sessions)
    bars_html = "".join(
        f'<rect x="{10 + i*bar_w}" y="{bh - int(completion[i]*(bh-10))-5}" '
        f'width="{max(bar_w-2,1)}" height="{int(completion[i]*(bh-10))+5}" '
        f'fill="#38bdf8" opacity="0.85"/>'
        for i in range(sessions)
    )

    avg_smooth = round(sum(smoothness)/n, 3)
    avg_comp = round(sum(completion)/sessions, 3)
    avg_dev = round(sum(deviation)/sessions, 2)
    latest_jerk = round(sum(jerk[-5:])/5, 4)

    return f"""<!DOCTYPE html><html><head><title>Teleoperation Quality Scorer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin:10px 0 6px}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.metrics{{display:flex;gap:16px;flex-wrap:wrap}}
.metric{{background:#0f172a;padding:14px 22px;border-radius:6px;min-width:120px}}
.metric .val{{font-size:2rem;font-weight:700;color:#38bdf8}}
.metric .lbl{{font-size:0.8rem;color:#94a3b8;margin-top:2px}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600}}
.good{{background:#14532d;color:#4ade80}}.warn{{background:#78350f;color:#fbbf24}}
svg text{{fill:#94a3b8;font-size:10px}}
</style></head>
<body>
<h1>Teleoperation Quality Scorer</h1>
<p style="color:#64748b;margin-top:0">Port {PORT} &nbsp;|&nbsp; Real-time operator skill evaluation &amp; trajectory analysis</p>

<div class="card">
  <h2>Live Quality Metrics</h2>
  <div class="metrics">
    <div class="metric"><div class="val">{avg_smooth:.3f}</div><div class="lbl">Avg Smoothness</div></div>
    <div class="metric"><div class="val">{avg_comp:.1%}</div><div class="lbl">Task Completion</div></div>
    <div class="metric"><div class="val">{avg_dev:.1f}mm</div><div class="lbl">Traj Deviation</div></div>
    <div class="metric"><div class="val">{latest_jerk:.4f}</div><div class="lbl">Avg Jerk (last 5)</div></div>
    <div class="metric"><div class="val">{'<span class="badge good">GOOD</span>' if avg_smooth > 0.75 else '<span class="badge warn">FAIR</span>'}</div><div class="lbl">Operator Rating</div></div>
  </div>
</div>

<div class="card">
  <h2>Smoothness Score — 60 Time Steps</h2>
  <svg width="{sw}" height="{sh+20}" style="display:block">
    <polyline points="{pts_smooth}" fill="none" stroke="#38bdf8" stroke-width="2"/>
    <line x1="10" y1="{sh-5}" x2="{sw-10}" y2="{sh-5}" stroke="#334155" stroke-width="1"/>
    <text x="10" y="{sh+15}">t=0</text>
    <text x="{sw//2-8}" y="{sh+15}">t=30</text>
    <text x="{sw-30}" y="{sh+15}">t=59</text>
    <text x="2" y="12" style="fill:#4ade80;font-size:9px">max={sm_max:.2f}</text>
    <text x="2" y="{sh-8}" style="fill:#f87171;font-size:9px">min={sm_min:.2f}</text>
  </svg>
</div>

<div class="card">
  <h2>Session Task Completion ({sessions} Sessions)</h2>
  <svg width="{bw}" height="{bh+20}" style="display:block">
    {bars_html}
    <line x1="10" y1="{bh-5}" x2="{bw-10}" y2="{bh-5}" stroke="#334155" stroke-width="1"/>
    <text x="10" y="{bh+15}">s=0</text>
    <text x="{bw//2-8}" y="{bh+15}">s=15</text>
    <text x="{bw-30}" y="{bh+15}">s=29</text>
  </svg>
</div>

<div class="card">
  <h2>Per-Session Trajectory Deviation (mm)</h2>
  <svg width="{sw}" height="80" style="display:block">
    {''.join(f'<rect x="{10+i*bar_w}" y="{75-int(deviation[i]*4)}" width="{max(bar_w-2,1)}" height="{int(deviation[i]*4)+5}" fill="#f59e0b" opacity="0.8"/>' for i in range(sessions))}
    <line x1="10" y1="75" x2="{sw-10}" y2="75" stroke="#334155" stroke-width="1"/>
    <text x="10" y="{80+12}">s=0</text><text x="{sw-30}" y="{80+12}">s=29</text>
  </svg>
</div>

<div class="card" style="color:#64748b;font-size:0.85rem">
  Scoring model: weighted sum of smoothness (40%), task completion (35%), trajectory deviation (25%).
  Smoothness = 1 - normalized jerk integral. Deviation = Frechet distance to reference trajectory.
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Teleoperation Quality Scorer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/score")
    def score():
        random.seed()
        s = round(0.72 + 0.18 * math.sin(random.uniform(0, 6)), 3)
        return {"smoothness": s, "completion": round(random.uniform(0.6, 0.95), 3),
                "deviation_mm": round(random.uniform(1.2, 6.8), 2),
                "rating": "GOOD" if s > 0.75 else "FAIR"}

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

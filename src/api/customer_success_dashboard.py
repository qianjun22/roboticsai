"""Customer Success Dashboard — FastAPI port 8462"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8462

def build_html():
    partners = [
        ("Physical Intelligence", 4.6, [4.2, 4.3, 4.5, 4.6], 82, "EXCELLENT"),
        ("Apptronik",             3.9, [3.6, 3.7, 3.8, 3.9], 67, "GOOD"),
        ("Covariant",             3.7, [3.8, 3.9, 3.7, 3.7], 54, "STABLE"),
        ("1X Technologies",       2.7, [3.2, 3.0, 2.8, 2.7], 41, "AT_RISK"),
        ("Agility Robotics",      3.4, [None, None, 3.2, 3.4], 71, "NEW"),
    ]
    status_colors = {"EXCELLENT": "#22c55e", "GOOD": "#38bdf8", "STABLE": "#94a3b8",
                     "AT_RISK": "#C74634", "NEW": "#f59e0b"}

    # health scores
    score_bars = ""
    for i, (name, score, trend, nps, status) in enumerate(partners):
        y = 15 + i * 42
        w = int(score / 5.0 * 250)
        color = status_colors[status]
        score_bars += f'<rect x="180" y="{y}" width="{w}" height="28" fill="{color}" opacity="0.85" rx="4"/>'
        score_bars += f'<text x="176" y="{y+18}" fill="#94a3b8" font-size="10" text-anchor="end">{name}</text>'
        score_bars += f'<text x="{180+w+6}" y="{y+18}" fill="#e2e8f0" font-size="11" font-weight="bold">{score}/5</text>'
        badge_color = status_colors[status]
        score_bars += f'<text x="{180+w+55}" y="{y+18}" fill="{badge_color}" font-size="9">{status}</text>'

    # NPS distribution bar
    nps_data = [("PI", 82, "#22c55e"), ("Apt", 67, "#38bdf8"), ("Cov", 54, "#94a3b8"),
                ("1X", 41, "#C74634"), ("Agi", 71, "#f59e0b")]
    nps_bars = ""
    for i, (name, nps, color) in enumerate(nps_data):
        x = 30 + i * 90
        h = int(nps / 100 * 130)
        nps_bars += f'<rect x="{x}" y="{145-h}" width="60" height="{h}" fill="{color}" rx="4" opacity="0.85"/>'
        nps_bars += f'<text x="{x+30}" y="160" fill="#94a3b8" font-size="10" text-anchor="middle">{name}</text>'
        nps_bars += f'<text x="{x+30}" y="{145-h-4}" fill="#e2e8f0" font-size="10" text-anchor="middle">NPS {nps}</text>'
    # benchmark lines
    nps_bars += f'<line x1="20" y1="{145-50}" x2="490" y2="{145-50}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>'
    nps_bars += f'<text x="492" y="{145-46}" fill="#f59e0b" font-size="9">NPS 50</text>'

    # 30-day engagement trend (sparklines)
    trend_svg = ""
    trend_labels = ["API Calls", "Demos", "Evals", "Support"]
    trend_data = {
        "Physical Intelligence": [847, 920, 1050, 890, 1100],
        "1X Technologies": [320, 290, 261, 240, 218],
    }
    for pi, (name, vals) in enumerate([("PI", trend_data["Physical Intelligence"]),
                                       ("1X", trend_data["1X Technologies"])]):
        x0 = 20 + pi * 220
        for j in range(1, len(vals)):
            x1 = x0 + (j-1)*42
            x2 = x0 + j*42
            y1 = 70 - vals[j-1]/1200*55
            y2 = 70 - vals[j]/1200*55
            color = "#22c55e" if pi == 0 else "#C74634"
            trend_svg += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="2"/>'
        trend_svg += f'<text x="{x0+84}" y="85" fill="#94a3b8" font-size="10" text-anchor="middle">{name} API calls/30d</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Customer Success Dashboard</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
.warn{{font-size:12px;color:#C74634;margin-top:4px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Customer Success Dashboard — Partner Health</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">3.7/5</div><div class="ml">Platform Avg Health</div></div>
  <div class="m"><div class="mv">PI 4.6</div><div class="ml">Top Partner</div><div class="delta">EXCELLENT — expand</div></div>
  <div class="m"><div class="mv">1X 2.7</div><div class="ml">At-Risk Partner</div><div class="warn">↓ declining trend</div></div>
  <div class="m"><div class="mv">63</div><div class="ml">Platform NPS</div></div>
</div>
<div class="grid">
  <div class="card" style="grid-column:1/3">
    <h3>Partner Health Score (5-dim weighted)</h3>
    <svg viewBox="0 0 590 225" width="100%">
      {score_bars}
    </svg>
  </div>
  <div class="card">
    <h3>NPS by Partner</h3>
    <svg viewBox="0 0 500 175" width="100%">
      <line x1="20" y1="10" x2="20" y2="148" stroke="#334155" stroke-width="1"/>
      <line x1="20" y1="148" x2="490" y2="148" stroke="#334155" stroke-width="1"/>
      {nps_bars}
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Customer Success Dashboard")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

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

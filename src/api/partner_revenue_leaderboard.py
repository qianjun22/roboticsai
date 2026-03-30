"""Partner Revenue Leaderboard — FastAPI port 8454"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8454

def build_html():
    partners = [
        ("Physical Intelligence", 1247, 1820, "#22c55e", "GROWING"),
        ("Apptronik",            612,  980, "#38bdf8", "GROWING"),
        ("Covariant",            489,  710, "#38bdf8", "STABLE"),
        ("1X Technologies",      412,  410, "#f59e0b", "FLAT"),
        ("Agility Robotics",     167,  300, "#94a3b8", "NEW"),
    ]

    # ranked MRR bar
    bars = ""
    for i, (name, mrr, proj, color, tier) in enumerate(partners):
        y = 20 + i * 42
        w_curr = int(mrr / 1400 * 280)
        w_proj = int(proj / 1400 * 280)
        bars += f'<rect x="200" y="{y}" width="{w_proj}" height="28" fill="{color}" opacity="0.2" rx="4"/>'
        bars += f'<rect x="200" y="{y}" width="{w_curr}" height="28" fill="{color}" opacity="0.85" rx="4"/>'
        bars += f'<text x="195" y="{y+18}" fill="#94a3b8" font-size="10" text-anchor="end">{name}</text>'
        bars += f'<text x="{200+w_curr+6}" y="{y+18}" fill="#e2e8f0" font-size="10">${mrr}</text>'
        badge_color = "#22c55e" if tier == "GROWING" else "#f59e0b" if tier == "FLAT" else "#94a3b8"
        bars += f'<text x="{200+w_proj+48}" y="{y+18}" fill="{badge_color}" font-size="9">{tier}</text>'

    # ARR projection scatter
    scatter = ""
    scatter_data = [
        ("PI",  1247*12, 1820*12, "#22c55e"),
        ("Apt", 612*12,  980*12,  "#38bdf8"),
        ("Cov", 489*12,  710*12,  "#38bdf8"),
        ("1X",  412*12,  412*12,  "#f59e0b"),
        ("Agi", 167*12,  300*12,  "#94a3b8"),
    ]
    max_arr = 22000
    for label, curr, proj, color in scatter_data:
        cx = 30 + int(curr / max_arr * 200)
        cy = 180 - int(proj / max_arr * 160)
        r = int(math.sqrt(curr / max_arr) * 15) + 5
        scatter += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" opacity="0.7"/>'
        scatter += f'<text x="{cx}" y="{cy+4}" fill="#0f172a" font-size="9" text-anchor="middle" font-weight="bold">{label}</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Partner Revenue Leaderboard</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:3fr 2fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Partner Revenue Leaderboard — MRR Rankings</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">$2,927</div><div class="ml">Current MRR</div></div>
  <div class="m"><div class="mv">$6,327</div><div class="ml">Jun Target MRR</div></div>
  <div class="m"><div class="mv">127%</div><div class="ml">NRR</div><div class="delta">net revenue retention</div></div>
  <div class="m"><div class="mv">1X</div><div class="ml">Churn Risk</div><div class="delta">$412 ARR at risk</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>MRR Ranking (bar=current, ghost=6-mo projection)</h3>
    <svg viewBox="0 0 600 230" width="100%">
      {bars}
    </svg>
  </div>
  <div class="card">
    <h3>ARR Current vs Projected (bubble=GPU-hrs)</h3>
    <svg viewBox="0 0 260 200" width="100%">
      <line x1="25" y1="10" x2="25" y2="185" stroke="#334155" stroke-width="1"/>
      <line x1="25" y1="185" x2="240" y2="185" stroke="#334155" stroke-width="1"/>
      {scatter}
      <text x="130" y="198" fill="#64748b" font-size="9" text-anchor="middle">Current ARR →</text>
      <text x="12" y="100" fill="#64748b" font-size="9" transform="rotate(-90,12,100)">Proj ARR ↑</text>
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Revenue Leaderboard")
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

"""NVIDIA Go-To-Market Tracker — FastAPI port 8386"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8386

def build_html():
    milestones = [
        ("Greg Pavlik intro", "IN_PROGRESS", 85, "Apr 2026"),
        ("NDA / Co-engineering NDA", "PENDING", 0, "May 2026"),
        ("Technical co-engineering", "BLOCKED", 0, "Jun 2026"),
        ("Preferred-cloud agreement", "BLOCKED", 0, "Jul 2026"),
        ("Design-partner referrals", "PENDING", 0, "Aug 2026"),
        ("GTC 2027 co-presenter", "PLANNED", 0, "Sep 2026"),
        ("Commercial partnership", "PLANNED", 0, "Q1 2027"),
        ("Marketplace listing", "PLANNED", 0, "Q2 2027"),
    ]
    status_color = {"IN_PROGRESS":"#38bdf8","PENDING":"#94a3b8","BLOCKED":"#ef4444","PLANNED":"#6366f1","DONE":"#22c55e"}

    # funnel SVG
    sw, sh = 560, 320
    funnel = f'<svg width="{sw}" height="{sh}">'
    for i, (m, st, pct, dt) in enumerate(milestones):
        y = 10 + i * 36
        w_max = 500
        w = max(int(w_max * (1 - i * 0.08)), 160)
        x = (sw - w) // 2
        col = status_color.get(st, "#94a3b8")
        fill = col if st != "BLOCKED" else "#ef444433"
        funnel += f'<rect x="{x}" y="{y}" width="{w}" height="28" fill="{fill}" rx="4" opacity="0.85"/>'
        funnel += f'<text x="{sw//2}" y="{y+18}" text-anchor="middle" fill="#0f172a" font-size="11" font-weight="bold">{m} — {dt}</text>'
        if st == "BLOCKED":
            funnel += f'<text x="{x+w+4}" y="{y+18}" fill="#ef4444" font-size="10">BLOCKED</text>'
    funnel += '</svg>'

    # co-sell pipeline
    partners = [
        ("Apptronik","enterprise","$1,200/mo","NDA signed","HIGH"),
        ("Physical Intelligence","enterprise","$2,400/mo","pilot active","HIGH"),
        ("1X Technologies","growth","$600/mo","churn risk","MEDIUM"),
        ("Figure AI","starter","$400/mo","evaluating","LOW"),
    ]
    table_rows = "".join([
        f'<tr><td>{p}</td><td>{tier}</td><td style="color:#22c55e">{rev}</td><td>{status}</td>'
        f'<td style="color:{"#22c55e" if pr=="HIGH" else "#f59e0b" if pr=="MEDIUM" else "#94a3b8"}">{pr}</td></tr>'
        for p, tier, rev, status, pr in partners
    ])

    return f"""<!DOCTYPE html>
<html><head><title>NVIDIA GTM Tracker — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8;font-size:14px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;margin:12px 0}}
.stat{{display:inline-block;margin:0 20px;text-align:center}}
.big{{font-size:28px;font-weight:bold;color:#C74634}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:6px 10px;border-bottom:1px solid #334155}}th{{color:#94a3b8}}
</style></head><body>
<h1>NVIDIA Go-To-Market Tracker — Port {PORT}</h1>
<div class="card">
  <div class="stat"><div class="big">1/8</div><div>Milestones Done</div></div>
  <div class="stat"><div class="big" style="color:#ef4444">2</div><div>Blocked</div></div>
  <div class="stat"><div class="big" style="color:#38bdf8">73%</div><div>Probability Score</div></div>
  <div class="stat"><div class="big" style="color:#22c55e">$4.6k</div><div>Co-sell MRR Pipeline</div></div>
</div>
<div class="card">
  <h2>Partnership Funnel</h2>
  {funnel}
</div>
<div class="card">
  <h2>Co-Sell Partner Pipeline</h2>
  <table><tr><th>Partner</th><th>Tier</th><th>Revenue</th><th>Status</th><th>Priority</th></tr>
  {table_rows}
  </table>
</div>
<div class="card">
  <h2>Critical Path</h2>
  <p style="color:#ef4444">⚠ BLOCKED: Preferred-cloud agreement requires Greg Pavlik intro → NVIDIA co-engineering team</p>
  <p style="color:#f59e0b">Action: Schedule intro meeting with Greg Pavlik before April 15, 2026</p>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="NVIDIA GTM Tracker")
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

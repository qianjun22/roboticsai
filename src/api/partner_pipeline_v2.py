"""Partner Pipeline v2 — FastAPI port 8507"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8507

def build_html():
    stages = [
        ("Referral", 18, 100, "#64748b"),
        ("Discovery", 12, 67, "#94a3b8"),
        ("Demo", 8, 44, "#38bdf8"),
        ("Pilot", 3, 17, "#f59e0b"),
        ("Contract", 2, 11, "#a78bfa"),
        ("Onboarding", 2, 11, "#22c55e"),
        ("Scale", 1, 6, "#22c55e"),
        ("Renew", 1, 6, "#22c55e"),
    ]
    
    funnel_svg = ""
    max_count = stages[0][1]
    for i, (name, count, pct, col) in enumerate(stages):
        w = count / max_count * 460 + 40
        x = (500 - w) / 2 + 20
        y = i * 28 + 5
        funnel_svg += f'<rect x="{x:.0f}" y="{y}" width="{w:.0f}" height="20" fill="{col}" opacity="0.75" rx="3"/>'
        funnel_svg += f'<text x="{500/2+20:.0f}" y="{y+14}" text-anchor="middle" fill="white" font-size="10" font-weight="bold">{name} ({count})</text>'
    
    # conversion rates
    conv_rates = []
    for i in range(1, len(stages)):
        prev_count = stages[i-1][1]
        curr_count = stages[i][1]
        rate = curr_count / prev_count * 100
        conv_rates.append((f"{stages[i-1][0]}→{stages[i][0]}", rate))
    
    conv_bars = ""
    for label, rate in conv_rates:
        col = "#22c55e" if rate >= 60 else ("#f59e0b" if rate >= 30 else "#ef4444")
        conv_bars += f'''<div style="display:flex;align-items:center;margin-bottom:5px">
<span style="width:160px;color:#94a3b8;font-size:10px">{label}</span>
<div style="background:#334155;border-radius:2px;height:8px;width:150px">
<div style="background:{col};width:{rate:.0f}%;height:8px;border-radius:2px"></div></div>
<span style="margin-left:6px;color:{col};font-size:10px">{rate:.0f}%</span>
</div>'''
    
    # pipeline value
    arr_at_stage = [0, 0, 0, 47000, 31000, 28000, 19000, 2000]
    total_pipeline = sum(arr_at_stage)
    
    return f"""<!DOCTYPE html><html><head><title>Partner Pipeline v2</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Partner Pipeline v2</h1><span>port {PORT} · 8-stage journey</span></div>
<div class="grid">
<div class="card"><h3>Total Pipeline ARR</h3><div class="stat">${total_pipeline//1000}k</div><div class="sub">across all stages</div></div>
<div class="card"><h3>Demo→Pilot Conv</h3><div class="stat">67%</div><div class="sub">strongest stage · best metric</div></div>
<div class="card"><h3>Partner Journey Funnel</h3>
<svg width="100%" viewBox="0 0 540 230">{funnel_svg}</svg></div>
<div class="card"><h3>Stage Conversion Rates</h3>{conv_bars}</div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Pipeline v2")
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

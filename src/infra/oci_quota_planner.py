"""OCI Quota Planner — FastAPI port 8485"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8485

def build_html():
    resources = [
        ("A100 80GB GPUs", 4, 8, 16, "#C74634"),
        ("vCPUs", 96, 192, 512, "#38bdf8"),
        ("RAM (TB)", 1.5, 3.0, 8.0, "#22c55e"),
        ("NVMe Storage (TB)", 8, 20, 100, "#f59e0b"),
        ("Network (Gbps)", 25, 50, 100, "#a78bfa"),
    ]
    
    bars = ""
    for name, current, requested, limit, col in resources:
        cur_pct = current / limit * 100
        req_pct = requested / limit * 100
        bars += f'''<div style="margin-bottom:14px">
<div style="display:flex;justify-content:space-between;margin-bottom:4px">
<span style="color:#e2e8f0">{name}</span>
<span style="color:#64748b;font-size:12px">current: <span style="color:{col}">{current}</span> → requested: <span style="color:#f59e0b">{requested}</span> / limit: {limit}</span>
</div>
<div style="background:#334155;border-radius:4px;height:10px;position:relative">
<div style="background:{col};width:{cur_pct:.0f}%;height:10px;border-radius:4px;position:absolute"></div>
<div style="background:#f59e0b;width:{req_pct:.0f}%;height:10px;border-radius:4px;opacity:0.4;position:absolute"></div>
</div></div>'''
    
    # approval timeline
    steps_data = [
        ("Submit quota request", 0, 1, "#22c55e"),
        ("OCI team review", 1, 7, "#38bdf8"),
        ("Capacity check", 7, 14, "#f59e0b"),
        ("Approval notification", 14, 21, "#22c55e"),
        ("Provisioning", 21, 28, "#38bdf8"),
    ]
    gantt = ""
    for label, start, end, col in steps_data:
        x = start * 500 / 30
        w = (end - start) * 500 / 30
        y_idx = steps_data.index((label, start, end, col))
        y = y_idx * 22 + 5
        gantt += f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="16" fill="{col}" rx="3" opacity="0.8"/>'
        gantt += f'<text x="{x+4:.1f}" y="{y+11}" fill="white" font-size="10">{label}</text>'
    
    today_line = 3 * 500 / 30
    gantt += f'<line x1="{today_line:.1f}" y1="0" x2="{today_line:.1f}" y2="115" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="4,2"/>'
    
    return f"""<!DOCTYPE html><html><head><title>OCI Quota Planner</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>OCI Quota Planner</h1><span>port {PORT} · AI World Sep 2026</span></div>
<div class="grid">
<div class="card"><h3>Current GPUs</h3><div class="stat">4</div><div class="sub">A100 80GB · 4 regions</div></div>
<div class="card"><h3>Requested</h3><div class="stat">8</div><div class="sub">for June 2026 pilot scale</div></div>
<div class="card"><h3>Lead Time</h3><div class="stat">21d</div><div class="sub">GPU quota approval SLA</div></div>
<div class="card" style="grid-column:span 3"><h3>Quota vs Limit — Current & Requested</h3>{bars}
<div style="font-size:11px;color:#64748b;margin-top:8px"><span style="color:#C74634">■</span> current <span style="color:#f59e0b;margin-left:12px">■</span> requested (transparent overlay)</div></div>
<div class="card" style="grid-column:span 3"><h3>Approval Timeline (30 days)</h3>
<div style="font-size:11px;color:#ef4444;margin-bottom:6px">▲ today (day 3)</div>
<svg width="100%" viewBox="0 0 500 115">{gantt}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Quota Planner")
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

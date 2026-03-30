"""Training Resource Heatmap — FastAPI port 8491"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8491

def build_html():
    hours = list(range(24))
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    # GPU utilization heatmap (7 days x 24 hours)
    heatmap_cells = ""
    for d_idx, day in enumerate(days):
        for h in hours:
            is_weekend = d_idx >= 5
            is_peak = 9 <= h <= 18
            is_contention = d_idx == 3 and h == 14  # Thu 2PM
            
            if is_contention:
                util = 98
                col = "#ef4444"
            elif is_weekend:
                util = 35 + random.uniform(-10, 10)
                col = "#1e3a5f"
            elif is_peak:
                util = 78 + random.uniform(-8, 12)
                col = "#22c55e" if util < 90 else "#f59e0b"
            else:
                util = 48 + random.uniform(-10, 10)
                col = "#334155"
            
            util = max(0, min(100, util))
            opacity = util / 100
            x = h * 20 + 40
            y = d_idx * 18 + 5
            heatmap_cells += f'<rect x="{x}" y="{y}" width="18" height="14" fill="{col}" opacity="{opacity:.2f}" rx="1"/>'
        
        heatmap_cells += f'<text x="36" y="{d_idx*18+15}" text-anchor="end" fill="#64748b" font-size="10">{day}</text>'
    
    for h in [0, 6, 12, 18, 23]:
        x = h * 20 + 49
        heatmap_cells += f'<text x="{x}" y="140" text-anchor="middle" fill="#64748b" font-size="9">{h:02d}h</text>'
    
    # resource contention detection
    contention_periods = [
        ("Thu 2PM", "DAgger + eval overlap", "#ef4444"),
        ("Mon 10AM", "checkpoint + eval overlap", "#f59e0b"),
        ("Fri 3PM", "weekly full eval run", "#f59e0b"),
    ]
    contention_html = ""
    for period, desc, col in contention_periods:
        contention_html += f'<div style="display:flex;align-items:center;margin-bottom:8px"><span style="background:{col};color:#0f172a;padding:1px 6px;border-radius:3px;font-size:11px;margin-right:8px">{period}</span><span style="color:#94a3b8;font-size:12px">{desc}</span></div>'
    
    weekend_waste = 248
    peak_util = 91
    
    return f"""<!DOCTYPE html><html><head><title>Training Resource Heatmap</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Training Resource Heatmap</h1><span>port {PORT} · 4 A100 nodes combined</span></div>
<div class="grid">
<div class="card"><h3>Peak Weekday</h3><div class="stat">{peak_util}%</div><div class="sub">Thu 2PM contention point</div></div>
<div class="card"><h3>Weekend Idle</h3><div class="stat">45%</div><div class="sub">${weekend_waste}/mo savings potential</div></div>
<div class="card"><h3>Contention Events</h3><div class="stat">3</div><div class="sub">this week · auto-schedule fix</div></div>
<div class="card" style="grid-column:span 3"><h3>GPU Utilization Heatmap (7d × 24h)</h3>
<svg width="100%" viewBox="0 0 520 145">{heatmap_cells}</svg>
<div style="font-size:11px;color:#64748b;margin-top:6px"><span style="color:#22c55e">■</span> peak <span style="color:#ef4444;margin-left:12px">■</span> contention <span style="color:#1e3a5f;margin-left:12px">■</span> weekend low</div>
</div>
<div class="card" style="grid-column:span 3"><h3>Contention Periods Detected</h3>{contention_html}
<div style="color:#64748b;font-size:12px;margin-top:8px">Recommendation: stagger DAgger + eval to off-peak hours → save 18% GPU-hrs</div></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Resource Heatmap")
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

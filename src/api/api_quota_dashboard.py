"""API Quota Dashboard — FastAPI port 8362"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8362

PARTNERS = {
    "PI Robotics":  {"api_calls": 89, "gpu_hours": 67, "storage_gb": 41, "tier": "growth"},
    "Apptronik":    {"api_calls": 61, "gpu_hours": 48, "storage_gb": 29, "tier": "growth"},
    "Covariant":    {"api_calls": 74, "gpu_hours": 53, "storage_gb": 35, "tier": "enterprise"},
    "1X Tech":      {"api_calls": 38, "gpu_hours": 31, "storage_gb": 18, "tier": "starter"},
    "Skild":        {"api_calls": 52, "gpu_hours": 42, "storage_gb": 24, "tier": "growth"},
}

def build_html():
    random.seed(21)
    
    # Quota cards for each partner
    cards = ""
    for name, data in PARTNERS.items():
        metrics = [("API calls", data["api_calls"]), ("GPU-hrs", data["gpu_hours"]), ("Storage GB", data["storage_gb"])]
        bars = ""
        for metric, pct in metrics:
            color = "#C74634" if pct >= 90 else "#f59e0b" if pct >= 75 else "#22c55e"
            bars += f"""<div style="margin:4px 0">
<div style="display:flex;justify-content:space-between;font-size:0.75em;color:#94a3b8">
<span>{metric}</span><span style="color:{color}">{pct}%</span></div>
<div style="background:#0f172a;border-radius:3px;height:8px;margin-top:2px">
<div style="width:{pct}%;background:{color};height:8px;border-radius:3px"></div></div></div>"""
        warn = " ⚠️ UPGRADE" if any(v >= 85 for v in [data["api_calls"], data["gpu_hours"]]) else ""
        cards += f"""<div style="background:#0f172a;border-radius:6px;padding:12px">
<div style="font-weight:bold;color:#e2e8f0;margin-bottom:4px">{name}</div>
<div style="font-size:0.7em;color:#64748b;margin-bottom:8px">{data["tier"]}{warn}</div>
{bars}</div>"""

    # 30-day API calls trend (stacked)
    days = list(range(1, 31))
    trend_lines = {}
    for name in PARTNERS:
        base = PARTNERS[name]["api_calls"] * 2
        trend_lines[name] = [round(base + 8 * math.sin(d/4) + random.randint(-5,5)) for d in days]

    colors_list = ["#22c55e", "#38bdf8", "#f59e0b", "#C74634", "#a78bfa"]
    line_svgs = ""
    for i, (name, pts) in enumerate(trend_lines.items()):
        color = colors_list[i % len(colors_list)]
        coords = " ".join(f"{30+d*16},{180-pts[d-1]*0.6}" for d in days)
        line_svgs += f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="1.5" opacity="0.9"/>'
        line_svgs += f'<text x="512" y="{178-trend_lines[name][-1]*0.6}" fill="{color}" font-size="8">{name[:4]}</text>'

    # Alert threshold lines
    alert_svgs = ""
    for threshold, label, color in [(80,"80%","#f59e0b"),(95,"95%","#f97316"),(100,"100%","#C74634")]:
        y = 180 - threshold * 0.6
        alert_svgs += f'<line x1="30" y1="{y}" x2="510" y2="{y}" stroke="{color}" stroke-dasharray="3,3" stroke-width="1" opacity="0.5"/>'
        alert_svgs += f'<text x="515" y="{y+4}" fill="{color}" font-size="8">{label}</text>'

    return f"""<!DOCTYPE html><html><head><title>API Quota Dashboard — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.card{{background:#1e293b;border-radius:8px;padding:16px;margin-top:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>API Quota Dashboard</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">1</div><div style="font-size:0.75em;color:#94a3b8">Near Limit</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">4</div><div style="font-size:0.75em;color:#94a3b8">Healthy</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">89%</div><div style="font-size:0.75em;color:#94a3b8">PI API quota</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#94a3b8">3 types</div><div style="font-size:0.75em;color:#94a3b8">Tracked</div></div>
</div>
<div class="card">
<h2>Per-Partner Quota Utilization (% of monthly limit)</h2>
<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px">{cards}</div>
</div>
<div class="card">
<h2>30-Day API Call Volume Trend (% of quota)</h2>
<svg viewBox="0 0 560 210"><rect width="560" height="210" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="185" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="185" x2="510" y2="185" stroke="#334155" stroke-width="1"/>
{alert_svgs}
{line_svgs}
<text x="260" y="200" fill="#64748b" font-size="9">Day</text>
<text x="32" y="200" fill="#64748b" font-size="8">1</text>
<text x="255" y="200" fill="#64748b" font-size="8">15</text>
<text x="488" y="200" fill="#64748b" font-size="8">30</text>
</svg>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="API Quota Dashboard")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"near_limit":1,"total_partners":5}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type","text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self,*a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0",PORT), Handler).serve_forever()

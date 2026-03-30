"""Subscription Tier Manager — FastAPI port 8414"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8414

def build_html():
    tiers = ["Starter","Growth","Enterprise"]
    prices = [500, 2000, 8000]
    features = {
        "GPU-hrs/mo":["96","384","unlimited"],
        "SLA_uptime":["99.0%","99.5%","99.9%"],
        "Support":["email","email+slack","dedicated CSM"],
        "DAgger_runs":["2/mo","10/mo","unlimited"],
        "Fine_tune":["shared GPU","dedicated GPU","multi-GPU priority"],
        "SDK_access":["standard","standard+eval","full+beta"],
    }
    tier_colors = ["#38bdf8","#f59e0b","#C74634"]

    # Feature matrix SVG
    feat_list = list(features.keys())
    cw5, rh5 = 110, 26
    svg_fm = f'<svg width="{len(tiers)*cw5+140}" height="{len(feat_list)*rh5+60}" style="background:#0f172a">'
    for ti, (tier, price, col) in enumerate(zip(tiers, prices, tier_colors)):
        x = 140+ti*cw5
        svg_fm += f'<rect x="{x}" y="5" width="{cw5-4}" height="40" fill="{col}" rx="4" opacity="0.7"/>'
        svg_fm += f'<text x="{x+cw5//2-2}" y="22" fill="white" font-size="10" text-anchor="middle" font-weight="bold">{tier}</text>'
        svg_fm += f'<text x="{x+cw5//2-2}" y="38" fill="white" font-size="9" text-anchor="middle">${price:,}/mo</text>'
    for fi, feat in enumerate(feat_list):
        svg_fm += f'<text x="135" y="{55+fi*rh5+15}" fill="#94a3b8" font-size="9" text-anchor="end">{feat}</text>'
        for ti, (vals, col) in enumerate(zip([features[feat]], [tier_colors[0]])): pass
        for ti, col in enumerate(tier_colors):
            val = features[feat][ti]
            svg_fm += f'<text x="{140+ti*cw5+cw5//2-2}" y="{55+fi*rh5+15}" fill={"#22c55e" if ti==2 else "#e2e8f0"} font-size="8" text-anchor="middle">{val}</text>'
    svg_fm += '</svg>'

    # Upgrade recommendation per partner
    partners_u = [
        ("PI_Robotics","Growth",0.89,"API quota at 89% → upgrade to Enterprise"),
        ("Apptronik","Starter",0.72,"DAgger quota hit → upgrade to Growth"),
        ("1X_Tech","Growth",0.54,"normal usage"),
        ("Machina_Labs","Starter",0.41,"pilot phase"),
        ("Wandelbots","Starter",0.28,"early onboard"),
    ]
    svg_u = '<svg width="420" height="200" style="background:#0f172a">'
    for pi, (partner, tier, usage, note) in enumerate(partners_u):
        y = 15+pi*36; col = "#C74634" if usage > 0.85 else "#f59e0b" if usage > 0.65 else "#22c55e"
        tier_col = {"Starter":"#38bdf8","Growth":"#f59e0b","Enterprise":"#C74634"}[tier]
        svg_u += f'<rect x="130" y="{y}" width="{int(usage*200)}" height="20" fill="{col}" opacity="0.7" rx="3"/>'
        svg_u += f'<text x="125" y="{y+14}" fill="#94a3b8" font-size="9" text-anchor="end">{partner[:10]}</text>'
        svg_u += f'<text x="{132+int(usage*200)}" y="{y+14}" fill="{col}" font-size="8">{usage:.0%}</text>'
        svg_u += f'<rect x="345" y="{y}" width="60" height="20" fill="{tier_col}" rx="3" opacity="0.7"/>'
        svg_u += f'<text x="375" y="{y+14}" fill="white" font-size="8" text-anchor="middle">{tier}</text>'
        if usage > 0.8:
            svg_u += f'<text x="10" y="{y+14}" fill="#C74634" font-size="7">⚠</text>'
    svg_u += '<text x="230" y="195" fill="#94a3b8" font-size="9" text-anchor="middle">Quota Utilization → Tier</text>'
    svg_u += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Subscription Tier Manager — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Subscription Tier Manager</h1>
<p style="color:#94a3b8">Port {PORT} | 3-tier pricing + partner upgrade recommendations</p>
<div class="grid">
<div class="card"><h2>Tier Feature Matrix</h2>{svg_fm}</div>
<div class="card"><h2>Partner Quota Utilization</h2>{svg_u}
<div style="margin-top:8px">
<div class="stat">$4,200</div><div class="label">Revenue expansion opportunity (PI upgrade → Enterprise)</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">PI: 89% API quota → auto-alert sent for Enterprise upgrade<br>Apptronik: DAgger quota exceeded → Growth recommended<br>Auto-upgrade: trigger at 90% sustained for 3 days<br>Volume discount: 15% at Enterprise, 10% at Growth</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Subscription Tier Manager")
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

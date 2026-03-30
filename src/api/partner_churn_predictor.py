"""Partner Churn Predictor — FastAPI port 8358"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8358

PARTNERS = {
    "PI Robotics": {
        "signals": {"sr_trend": 0.85, "api_activity": 0.92, "csat": 0.94, "billing": 0.98, "engagement": 0.91},
        "risk": "LOW", "arr": 1247, "action": "Expansion — upsell DAgger bundle"
    },
    "Apptronik": {
        "signals": {"sr_trend": 0.72, "api_activity": 0.78, "csat": 0.84, "billing": 0.95, "engagement": 0.76},
        "risk": "LOW", "arr": 623, "action": "Healthy — schedule QBR Q2"
    },
    "Covariant": {
        "signals": {"sr_trend": 0.68, "api_activity": 0.61, "csat": 0.72, "billing": 0.88, "engagement": 0.65},
        "risk": "MEDIUM", "arr": 847, "action": "Watch — support ticket spike, schedule CSM call"
    },
    "1X Tech": {
        "signals": {"sr_trend": 0.31, "api_activity": 0.38, "csat": 0.52, "billing": 0.74, "engagement": 0.35},
        "risk": "CRITICAL", "arr": 847, "action": "URGENT — assign senior CSM, offer DAgger discount"
    },
    "Skild": {
        "signals": {"sr_trend": 0.61, "api_activity": 0.69, "csat": 0.78, "billing": 0.92, "engagement": 0.71},
        "risk": "LOW", "arr": 363, "action": "Stable — monthly check-in sufficient"
    },
}

def build_html():
    risk_colors = {"LOW": "#22c55e", "MEDIUM": "#f59e0b", "HIGH": "#f97316", "CRITICAL": "#C74634"}
    
    cards = ""
    for name, data in PARTNERS.items():
        color = risk_colors[data["risk"]]
        sigs = data["signals"]
        # Radar as simple bar chart
        sig_bars = ""
        for i, (sig, val) in enumerate(sigs.items()):
            bar_color = "#22c55e" if val >= 0.7 else "#f59e0b" if val >= 0.5 else "#C74634"
            w = int(val * 120)
            sig_bars += f'<div style="display:flex;align-items:center;margin:2px 0">'
            sig_bars += f'<div style="width:90px;font-size:0.7em;color:#64748b">{sig.replace("_"," ")}</div>'
            sig_bars += f'<div style="width:{w}px;height:8px;background:{bar_color};border-radius:2px"></div>'
            sig_bars += f'<div style="font-size:0.7em;color:{bar_color};margin-left:4px">{val}</div></div>'

        score = round(sum(sigs.values()) / len(sigs), 2)
        cards += f"""<div style="background:#1e293b;border-radius:8px;padding:16px;border-left:3px solid {color}">
<div style="display:flex;justify-content:space-between;align-items:center">
<div style="font-weight:bold;color:#e2e8f0">{name}</div>
<span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:0.8em">{data["risk"]}</span>
</div>
<div style="color:#64748b;font-size:0.75em;margin:4px 0">ARR: <span style="color:#94a3b8">${data["arr"]}</span> &nbsp; Score: <span style="color:{color}">{score}</span></div>
{sig_bars}
<div style="margin-top:8px;font-size:0.75em;color:{color}">→ {data["action"]}</div>
</div>"""

    total_arr_at_risk = sum(v["arr"] for v in PARTNERS.values() if v["risk"] in ["HIGH","CRITICAL"])
    
    return f"""<!DOCTYPE html><html><head><title>Partner Churn Predictor — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-top:16px}}
</style></head><body>
<h1>Partner Churn Predictor</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">1</div><div style="font-size:0.75em;color:#94a3b8">CRITICAL</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">1</div><div style="font-size:0.75em;color:#94a3b8">MEDIUM</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">3</div><div style="font-size:0.75em;color:#94a3b8">LOW</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">${total_arr_at_risk}</div><div style="font-size:0.75em;color:#94a3b8">ARR at Risk</div></div>
</div>
<div class="grid">{cards}</div>
<div style="background:#1e293b;border-radius:8px;padding:12px;margin-top:16px;font-size:0.8em;color:#64748b">
5 signals: sr_trend (30d slope) | api_activity (calls/d vs baseline) | csat (last 3 tickets) | billing (payment health) | engagement (demo/finetune activity)
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Churn Predictor")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT, "critical": 1, "arr_at_risk": 847}

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

"""Partner Engagement Scorer — FastAPI port 8877"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8877

# 14 engagement signals used in the ML scoring model
SIGNALS = [
    "email_open_rate", "slack_response_time", "demo_attendance", "doc_downloads",
    "api_trial_usage", "support_tickets", "nps_score", "meeting_cadence",
    "champion_activity", "budget_signal", "pilot_scope", "exec_sponsor",
    "integration_depth", "renewal_intent",
]

PARTNERS = [
    {"name": "Acme Robotics",    "score": 0.91, "trend": [0.72, 0.75, 0.79, 0.84, 0.88, 0.91], "tier": "Platinum"},
    {"name": "NovaBots",         "score": 0.83, "trend": [0.65, 0.68, 0.71, 0.76, 0.80, 0.83], "tier": "Gold"},
    {"name": "SkyForge AI",      "score": 0.78, "trend": [0.70, 0.72, 0.74, 0.75, 0.77, 0.78], "tier": "Gold"},
    {"name": "TerraBot Systems", "score": 0.69, "trend": [0.60, 0.62, 0.64, 0.66, 0.67, 0.69], "tier": "Silver"},
    {"name": "Helios Dynamics",  "score": 0.61, "trend": [0.55, 0.57, 0.58, 0.59, 0.60, 0.61], "tier": "Silver"},
    {"name": "Quantum Arm",      "score": 0.54, "trend": [0.51, 0.50, 0.52, 0.53, 0.53, 0.54], "tier": "Bronze"},
    {"name": "IronFleet",        "score": 0.47, "trend": [0.50, 0.49, 0.48, 0.47, 0.46, 0.47], "tier": "Bronze"},
    {"name": "PrismLabs",        "score": 0.39, "trend": [0.42, 0.41, 0.40, 0.39, 0.38, 0.39], "tier": "At-Risk"},
]

TIER_COLOR = {"Platinum": "#C74634", "Gold": "#f59e0b", "Silver": "#94a3b8", "Bronze": "#78716c", "At-Risk": "#ef4444"}

def build_html():
    # Engagement score bar chart
    bars = "".join(
        f'<rect x="{20+i*52}" y="{160-int(p["score"]*140)}" width="38" '
        f'height="{int(p["score"]*140)}" fill="{TIER_COLOR[p[\"tier\"]]}"/>'
        f'<text x="{39+i*52}" y="{155-int(p[\"score\"]*140)}" text-anchor="middle" fill="#e2e8f0" font-size="9">{p[\"score\"]}</text>'
        f'<text x="{39+i*52}" y="177" text-anchor="middle" fill="#94a3b8" font-size="7.5">{p[\"name\"].split()[0]}</text>'
        for i, p in enumerate(PARTNERS)
    )
    # Trend sparklines for top 3 partners
    sparklines = ""
    for idx, p in enumerate(PARTNERS[:3]):
        pts = " ".join(f"{10+j*32},{60-int(v*55)}" for j, v in enumerate(p["trend"]))
        sparklines += (
            f'<text x="10" y="{idx*75+15}" fill="{TIER_COLOR[p[\"tier\"]]}" font-size="11" font-weight="bold">{p[\"name\"]}</text>'
            f'<polyline points="{pts}" transform="translate(0,{idx*75+20})" fill="none" stroke="{TIER_COLOR[p[\"tier\"]]}" stroke-width="2"/>'
            f'<text x="180" y="{idx*75+55}" fill="#94a3b8" font-size="9">Score: {p[\"score\"]} ({p[\"tier\"]})</text>'
        )
    signal_pills = "".join(
        f'<span style="background:#1e3a5f;color:#38bdf8;padding:2px 8px;border-radius:4px;margin:2px;font-size:11px;display:inline-block">{s}</span>'
        for s in SIGNALS
    )
    rows = "".join(
        f"<tr><td>{p['name']}</td><td><strong>{p['score']}</strong></td>"
        f"<td style='color:{TIER_COLOR[p[\"tier\"]]}'>{p['tier']}</td>"
        f"<td>{'▲' if p['trend'][-1] >= p['trend'][-2] else '▼'} {abs(round(p['trend'][-1]-p['trend'][-2],2))}</td></tr>"
        for p in PARTNERS
    )
    return f"""<!DOCTYPE html><html><head><title>Partner Engagement Scorer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:6px 12px;text-align:left;border-bottom:1px solid #334155}}
th{{color:#38bdf8}}.badge{{background:#C74634;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px}}</style></head>
<body><h1>Partner Engagement Scorer</h1>
<p>ML-based partner engagement scoring across <strong>14 signals</strong>. Scores range 0–1; tiers: Platinum &gt; Gold &gt; Silver &gt; Bronze &gt; At-Risk.</p>
<div class="card"><h2>Engagement Scores by Partner</h2>
<svg width="450" height="190">{bars}</svg>
<p>Top partner: <span class="badge">Acme Robotics 0.91</span> &nbsp;|&nbsp; Port: {PORT}</p>
</div>
<div class="card"><h2>Trend Lines — Top 3 Partners (6 months)</h2>
<svg width="220" height="230">{sparklines}</svg>
</div>
<div class="card"><h2>14 Engagement Signals</h2><p>{signal_pills}</p></div>
<div class="card"><h2>All Partners</h2>
<table><tr><th>Partner</th><th>Score</th><th>Tier</th><th>MoM</th></tr>{rows}</table>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Engagement Scorer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/scores")
    def scores(): return {"partners": PARTNERS, "signals": SIGNALS}

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

"""
OCI Robot Cloud — ARR Bridge Report  (port 8681)
cycle-155B
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>ARR Bridge Report — OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}
  h1{color:#C74634;font-size:1.6rem;margin-bottom:4px}
  .subtitle{color:#94a3b8;font-size:.9rem;margin-bottom:28px}
  .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
  .metric{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px;text-align:center}
  .metric .val{font-size:1.8rem;font-weight:700;color:#38bdf8}
  .metric .lbl{font-size:.78rem;color:#94a3b8;margin-top:4px}
  .metric .sub{font-size:.72rem;color:#64748b;margin-top:2px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px}
  .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px}
  .card-wide{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;margin-bottom:24px}
  .card h2,.card-wide h2{color:#38bdf8;font-size:1rem;font-weight:600;margin-bottom:16px;letter-spacing:.04em}
  svg text{font-family:'Segoe UI',system-ui,sans-serif}
  .footer{text-align:center;color:#475569;font-size:.75rem;margin-top:28px}
</style>
</head>
<body>

<h1>ARR Bridge Report</h1>
<p class="subtitle">OCI Robot Cloud · Port 8681 · Q1 2026 → $1M ARR Journey</p>

<!-- KPI metrics -->
<div class="metrics">
  <div class="metric"><div class="val">$35k</div><div class="lbl">Q1 2026 ARR</div><div class="sub">ending balance</div></div>
  <div class="metric"><div class="val">$150k</div><div class="lbl">AI World Target</div><div class="sub">Sep 2026</div></div>
  <div class="metric"><div class="val">$250k</div><div class="lbl">Series A Signal</div><div class="sub">projected Jan 2027</div></div>
  <div class="metric"><div class="val">3</div><div class="lbl">Enterprise Deals</div><div class="sub">needed by GTC 2027</div></div>
</div>

<!-- SVG 1: ARR Bridge Waterfall (full width) -->
<div class="card-wide">
  <h2>Q1 2026 ARR BRIDGE WATERFALL</h2>
  <svg viewBox="0 0 860 300" width="100%" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="varr" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
        <polygon points="0 0,8 3,0 6" fill="#64748b"/>
      </marker>
    </defs>

    <!-- Y axis -->
    <line x1="70" y1="20" x2="70" y2="250" stroke="#334155" stroke-width="1"/>
    <!-- Y labels -->
    <text x="64" y="25"  fill="#64748b" font-size="10" text-anchor="end">$40k</text>
    <text x="64" y="75"  fill="#64748b" font-size="10" text-anchor="end">$30k</text>
    <text x="64" y="125" fill="#64748b" font-size="10" text-anchor="end">$20k</text>
    <text x="64" y="175" fill="#64748b" font-size="10" text-anchor="end">$10k</text>
    <text x="64" y="250" fill="#64748b" font-size="10" text-anchor="end">$0</text>

    <!-- Horizontal gridlines -->
    <line x1="70" x2="840" y1="25"  y2="25"  stroke="#1e293b" stroke-width="1"/>
    <line x1="70" x2="840" y1="75"  y2="75"  stroke="#1e293b" stroke-width="1"/>
    <line x1="70" x2="840" y1="125" y2="125" stroke="#1e293b" stroke-width="1"/>
    <line x1="70" x2="840" y1="175" y2="175" stroke="#1e293b" stroke-width="1"/>
    <line x1="70" x2="840" y1="250" y2="250" stroke="#334155" stroke-width="1"/>

    <!-- Scale: $40k = y:25; $0 = y:250 => 1k = 5.625px; base y for val = 250 - val*5.625 -->

    <!-- BEGIN $0 bar (gray dotted baseline) -->
    <rect x="90"  y="248" width="80" height="2" rx="1" fill="#475569"/>
    <text x="130" y="264" fill="#94a3b8" font-size="11" text-anchor="middle" font-weight="600">Begin</text>
    <text x="130" y="275" fill="#64748b" font-size="10" text-anchor="middle">$0</text>

    <!-- connector line from begin to new_logos bottom -->
    <line x1="170" y1="250" x2="210" y2="250" stroke="#475569" stroke-width="1" stroke-dasharray="3,2"/>

    <!-- NEW LOGOS +$22k → bar from y:250 up 22*5.625=123.75px → top=y:126 -->
    <rect x="210" y="126" width="80" height="124" rx="4" fill="#16a34a" opacity=".85"/>
    <text x="250" y="120" fill="#22c55e" font-size="11" text-anchor="middle" font-weight="600">+$22k</text>
    <text x="250" y="264" fill="#94a3b8" font-size="11" text-anchor="middle" font-weight="600">New Logos</text>
    <text x="250" y="275" fill="#64748b" font-size="10" text-anchor="middle">3 design partners</text>

    <!-- connector from new_logos top to expansion base -->
    <line x1="290" y1="126" x2="330" y2="126" stroke="#475569" stroke-width="1" stroke-dasharray="3,2"/>

    <!-- EXPANSION +$8k → base y:126, height 8*5.625=45px → top=y:81 -->
    <rect x="330" y="81" width="80" height="45" rx="4" fill="#0ea5e9" opacity=".85"/>
    <text x="370" y="75" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="600">+$8k</text>
    <text x="370" y="264" fill="#94a3b8" font-size="11" text-anchor="middle" font-weight="600">Expansion</text>
    <text x="370" y="275" fill="#64748b" font-size="10" text-anchor="middle">seat upgrades</text>

    <!-- connector from expansion top to price_increase base -->
    <line x1="410" y1="81" x2="450" y2="81" stroke="#475569" stroke-width="1" stroke-dasharray="3,2"/>

    <!-- PRICE_INCREASE +$5k → base y:81, height 5*5.625=28px → top=y:53 -->
    <rect x="450" y="53" width="80" height="28" rx="4" fill="#a78bfa" opacity=".85"/>
    <text x="490" y="47" fill="#c4b5fd" font-size="11" text-anchor="middle" font-weight="600">+$5k</text>
    <text x="490" y="264" fill="#94a3b8" font-size="11" text-anchor="middle" font-weight="600">Price Increase</text>
    <text x="490" y="275" fill="#64748b" font-size="10" text-anchor="middle">annual uplift</text>

    <!-- connector from price_increase top to churn base (no churn) -->
    <line x1="530" y1="53" x2="570" y2="53" stroke="#475569" stroke-width="1" stroke-dasharray="3,2"/>

    <!-- CHURN $0 (thin bar) -->
    <rect x="570" y="51" width="80" height="2" rx="1" fill="#ef4444" opacity=".5"/>
    <text x="610" y="46" fill="#fca5a5" font-size="11" text-anchor="middle">$0</text>
    <text x="610" y="264" fill="#94a3b8" font-size="11" text-anchor="middle" font-weight="600">Churn</text>
    <text x="610" y="275" fill="#64748b" font-size="10" text-anchor="middle">none</text>

    <!-- CONTRACTION $0 -->
    <line x1="650" y1="53" x2="690" y2="53" stroke="#475569" stroke-width="1" stroke-dasharray="3,2"/>
    <rect x="690" y="51" width="80" height="2" rx="1" fill="#f97316" opacity=".5"/>
    <text x="730" y="46" fill="#fed7aa" font-size="11" text-anchor="middle">$0</text>
    <text x="730" y="264" fill="#94a3b8" font-size="11" text-anchor="middle" font-weight="600">Contraction</text>
    <text x="730" y="275" fill="#64748b" font-size="10" text-anchor="middle">none</text>

    <!-- ENDING $35k bar -->
    <line x1="770" y1="53" x2="790" y2="53" stroke="#475569" stroke-width="1" stroke-dasharray="3,2"/>
    <rect x="780" y="53" width="55" height="197" rx="4" fill="#C74634" opacity=".9"/>
    <text x="807" y="47" fill="#fca5a5" font-size="11" text-anchor="middle" font-weight="700">$35k</text>
    <text x="807" y="264" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="700">Ending</text>
    <text x="807" y="275" fill="#94a3b8" font-size="10" text-anchor="middle">Q1 ARR</text>

    <!-- Title annotation -->
    <text x="450" y="14" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="600">Q1 2026 ARR Bridge: $0 → $35k</text>
  </svg>
</div>

<div class="grid">
  <!-- SVG 2: ARR by segment donut -->
  <div class="card">
    <h2>ARR BY SEGMENT — CURRENT vs TARGET</h2>
    <svg viewBox="0 0 380 280" width="100%" xmlns="http://www.w3.org/2000/svg">
      <!-- Inner ring: current (r=75, circumference=471.2) -->
      <!-- pilot 60%: dash=282.7 -->
      <circle cx="160" cy="140" r="75" fill="none" stroke="#1e3a5f" stroke-width="28"
        stroke-dasharray="282.7 188.5" stroke-dashoffset="0" transform="rotate(-90 160 140)"/>
      <!-- growth 30%: dash=141.4 offset=-282.7 -->
      <circle cx="160" cy="140" r="75" fill="none" stroke="#0ea5e9" stroke-width="28"
        stroke-dasharray="141.4 329.8" stroke-dashoffset="-282.7" transform="rotate(-90 160 140)"/>
      <!-- enterprise 10%: dash=47.1 offset=-424.1 -->
      <circle cx="160" cy="140" r="75" fill="none" stroke="#C74634" stroke-width="28"
        stroke-dasharray="47.1 424.1" stroke-dashoffset="-424.1" transform="rotate(-90 160 140)"/>

      <!-- Outer ring: target (r=108, circumference=678.6) -->
      <!-- pilot target 20%: 135.7 -->
      <circle cx="160" cy="140" r="108" fill="none" stroke="#1d4ed8" stroke-width="14" opacity=".6"
        stroke-dasharray="135.7 542.9" stroke-dashoffset="0" transform="rotate(-90 160 140)"/>
      <!-- growth target 40%: 271.5 offset=-135.7 -->
      <circle cx="160" cy="140" r="108" fill="none" stroke="#38bdf8" stroke-width="14" opacity=".6"
        stroke-dasharray="271.5 407.1" stroke-dashoffset="-135.7" transform="rotate(-90 160 140)"/>
      <!-- enterprise target 40%: 271.5 offset=-407.2 -->
      <circle cx="160" cy="140" r="108" fill="none" stroke="#ef4444" stroke-width="14" opacity=".6"
        stroke-dasharray="271.5 407.1" stroke-dashoffset="-407.2" transform="rotate(-90 160 140)"/>

      <!-- center labels -->
      <text x="160" y="133" fill="#e2e8f0" font-size="13" text-anchor="middle" font-weight="700">$35k</text>
      <text x="160" y="150" fill="#94a3b8" font-size="10" text-anchor="middle">current ARR</text>

      <!-- Legend -->
      <rect x="284" y="60"  width="10" height="10" rx="2" fill="#1e3a5f"/>
      <text x="298" y="70" fill="#94a3b8" font-size="11">Pilot 60% → 20%</text>
      <rect x="284" y="84"  width="10" height="10" rx="2" fill="#0ea5e9"/>
      <text x="298" y="94" fill="#94a3b8" font-size="11">Growth 30% → 40%</text>
      <rect x="284" y="108" width="10" height="10" rx="2" fill="#C74634"/>
      <text x="298" y="118" fill="#94a3b8" font-size="11">Enterprise 10% → 40%</text>

      <text x="284" y="148" fill="#64748b" font-size="10">Inner: current</text>
      <text x="284" y="162" fill="#64748b" font-size="10">Outer: target</text>

      <text x="20" y="270" fill="#475569" font-size="9">Gap: need 3 enterprise deals to reach target mix</text>
    </svg>
  </div>

  <!-- SVG 3: Path to $1M ARR S-curve -->
  <div class="card">
    <h2>PATH TO $1M ARR — MILESTONES</h2>
    <svg viewBox="0 0 380 280" width="100%" xmlns="http://www.w3.org/2000/svg">
      <!-- Axes -->
      <line x1="50" y1="20" x2="50"  y2="240" stroke="#334155" stroke-width="1.5"/>
      <line x1="50" y1="240" x2="370" y2="240" stroke="#334155" stroke-width="1.5"/>

      <!-- Y axis labels -->
      <text x="46" y="24"  fill="#64748b" font-size="9" text-anchor="end">$1M</text>
      <text x="46" y="76"  fill="#64748b" font-size="9" text-anchor="end">$750k</text>
      <text x="46" y="128" fill="#64748b" font-size="9" text-anchor="end">$500k</text>
      <text x="46" y="180" fill="#64748b" font-size="9" text-anchor="end">$250k</text>
      <text x="46" y="240" fill="#64748b" font-size="9" text-anchor="end">$0</text>

      <!-- Y gridlines -->
      <line x1="50" x2="370" y1="24"  y2="24"  stroke="#1e293b" stroke-width="1"/>
      <line x1="50" x2="370" y1="76"  y2="76"  stroke="#1e293b" stroke-width="1"/>
      <line x1="50" x2="370" y1="128" y2="128" stroke="#1e293b" stroke-width="1"/>
      <line x1="50" x2="370" y1="180" y2="180" stroke="#1e293b" stroke-width="1"/>

      <!-- X axis labels -->
      <text x="50"  y="254" fill="#64748b" font-size="8" text-anchor="middle">Jan'26</text>
      <text x="97"  y="254" fill="#64748b" font-size="8" text-anchor="middle">Q2'26</text>
      <text x="144" y="254" fill="#64748b" font-size="8" text-anchor="middle">Q3'26</text>
      <text x="191" y="254" fill="#64748b" font-size="8" text-anchor="middle">Q4'26</text>
      <text x="238" y="254" fill="#64748b" font-size="8" text-anchor="middle">Q1'27</text>
      <text x="285" y="254" fill="#64748b" font-size="8" text-anchor="middle">Q2'27</text>
      <text x="332" y="254" fill="#64748b" font-size="8" text-anchor="middle">Q3'27</text>
      <text x="370" y="254" fill="#64748b" font-size="8" text-anchor="middle">→</text>

      <!-- S-curve -->
      <polyline points="50,240 97,238 144,208 191,186 238,136 285,84 332,24"
        fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round" opacity=".9"/>

      <!-- shaded area under curve -->
      <polygon points="50,240 97,238 144,208 191,186 238,136 285,84 332,24 332,240"
        fill="#38bdf8" opacity=".07"/>

      <!-- Milestone: Q1 end $35k -->
      <circle cx="60" cy="232" r="5" fill="#94a3b8"/>
      <line x1="60" y1="227" x2="60" y2="195" stroke="#475569" stroke-width="1" stroke-dasharray="3,2"/>
      <rect x="28" y="182" width="70" height="28" rx="4" fill="#1e293b" stroke="#334155" stroke-width="1"/>
      <text x="63" y="194" fill="#e2e8f0" font-size="9" text-anchor="middle" font-weight="600">Q1 End</text>
      <text x="63" y="206" fill="#38bdf8" font-size="9" text-anchor="middle">$35k</text>

      <!-- Milestone: AI World Sep $150k -->
      <circle cx="144" cy="208" r="6" fill="#C74634"/>
      <line x1="144" y1="202" x2="144" y2="165" stroke="#C74634" stroke-width="1" stroke-dasharray="3,2"/>
      <rect x="108" y="150" width="75" height="28" rx="4" fill="#1e293b" stroke="#C74634" stroke-width="1"/>
      <text x="145" y="162" fill="#fca5a5" font-size="9" text-anchor="middle" font-weight="600">AI World</text>
      <text x="145" y="174" fill="#C74634" font-size="9" text-anchor="middle">$150k target</text>

      <!-- Milestone: Series A $250k Jan27 -->
      <circle cx="238" cy="136" r="6" fill="#a78bfa"/>
      <line x1="238" y1="130" x2="238" y2="95" stroke="#a78bfa" stroke-width="1" stroke-dasharray="3,2"/>
      <rect x="200" y="80" width="78" height="28" rx="4" fill="#1e293b" stroke="#a78bfa" stroke-width="1"/>
      <text x="239" y="92" fill="#c4b5fd" font-size="9" text-anchor="middle" font-weight="600">Series A</text>
      <text x="239" y="104" fill="#a78bfa" font-size="9" text-anchor="middle">$250k → Jan'27</text>

      <!-- Milestone: GTC 2027 $480k -->
      <circle cx="270" cy="100" r="6" fill="#22c55e"/>
      <line x1="270" y1="94" x2="270" y2="58" stroke="#22c55e" stroke-width="1" stroke-dasharray="3,2"/>
      <rect x="240" y="44" width="68" height="28" rx="4" fill="#1e293b" stroke="#22c55e" stroke-width="1"/>
      <text x="274" y="56" fill="#86efac" font-size="9" text-anchor="middle" font-weight="600">GTC 2027</text>
      <text x="274" y="68" fill="#22c55e" font-size="9" text-anchor="middle">$480k</text>

      <!-- Milestone: $1M -->
      <circle cx="332" cy="24" r="7" fill="#fbbf24"/>
      <line x1="332" y1="17" x2="332" y2="4" stroke="#fbbf24" stroke-width="1.5"/>
      <text x="332" y="12" fill="#fbbf24" font-size="10" text-anchor="middle" font-weight="700">$1M</text>

      <!-- 3 enterprise deals annotation -->
      <rect x="55" y="24" width="130" height="18" rx="4" fill="#1e293b" stroke="#334155" stroke-width="1"/>
      <text x="120" y="37" fill="#94a3b8" font-size="9" text-anchor="middle">3 enterprise deals needed @ GTC</text>
    </svg>
  </div>
</div>

<div class="footer">OCI Robot Cloud · ARR Bridge Report · Port 8681 · cycle-155B</div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="ARR Bridge Report", version="155B")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "arr_bridge_report",
            "port": 8681,
            "cycle": "155B",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metrics": {
                "q1_2026_arr_usd": 35000,
                "ai_world_target_usd": 150000,
                "series_a_signal_usd": 250000,
                "gtc_2027_projected_usd": 480000,
                "target_arr_usd": 1000000,
                "enterprise_deals_needed": 3,
            },
        }

    @app.get("/arr")
    async def arr_data():
        return {
            "bridge": {
                "beginning": 0,
                "new_logos": 22000,
                "expansion": 8000,
                "price_increase": 5000,
                "churn": 0,
                "contraction": 0,
                "ending": 35000,
            },
            "segments": {
                "current": {"pilot": 0.60, "growth": 0.30, "enterprise": 0.10},
                "target": {"pilot": 0.20, "growth": 0.40, "enterprise": 0.40},
            },
            "milestones": [
                {"label": "Q1 2026 End", "date": "2026-03-31", "arr_usd": 35000},
                {"label": "AI World", "date": "2026-09-15", "arr_usd": 150000},
                {"label": "Series A Signal", "date": "2027-01-15", "arr_usd": 250000},
                {"label": "GTC 2027", "date": "2027-03-20", "arr_usd": 480000},
                {"label": "$1M Target", "date": "2027-07-01", "arr_usd": 1000000},
            ],
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8681)

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json as _json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = _json.dumps({"status": "ok", "port": 8681, "fastapi": False}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        srv = HTTPServer(("0.0.0.0", 8681), Handler)
        print("ARR Bridge Report running on port 8681")
        srv.serve_forever()

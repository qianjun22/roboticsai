"""Partner Logo Wall — FastAPI port 8829"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8829

PARTNERS = [
    # (name, tier, status, revenue_k, domain)
    ("NVIDIA",        "Platinum", "active",  420, "Hardware"),
    ("Boston Dynamics","Platinum", "active",  380, "Robotics"),
    ("Foxconn",       "Platinum", "active",  310, "Manufacturing"),
    ("Siemens",       "Gold",     "active",  210, "Industrial"),
    ("ABB Robotics",  "Gold",     "active",  190, "Robotics"),
    ("Rockwell Auto", "Gold",     "active",  175, "Automation"),
    ("Cognex",        "Gold",     "pilot",   140, "Vision"),
    ("Mujoco/Google", "Gold",     "pilot",   120, "Simulation"),
    ("Universal Robots","Silver", "active",   95, "Robotics"),
    ("Zebra Tech",    "Silver",   "pilot",    80, "Logistics"),
    ("Teradyne",      "Silver",   "pilot",    72, "Testing"),
    ("Omron",         "Silver",   "active",   68, "Automation"),
    ("Yaskawa",       "Silver",   "pending",  55, "Motion"),
    ("KUKA",          "Silver",   "pending",  50, "Robotics"),
    ("Fanuc",         "Silver",   "pending",  48, "CNC"),
    ("Clearpath",     "Bronze",   "pilot",    35, "Mobile"),
    ("Franka Emika",  "Bronze",   "pilot",    30, "Research"),
    ("Realtime Robotics","Bronze","pending",  25, "Planning"),
    ("Covariant",     "Bronze",   "pilot",    22, "AI"),
    ("Vicarious",     "Bronze",   "pending",  18, "AI"),
    ("Osaro",         "Bronze",   "pending",  15, "Pick&Place"),
    ("Berkshire Grey","Bronze",   "pending",  12, "Logistics"),
    ("Kindred",       "Bronze",   "pending",  10, "Fulfillment"),
]

def build_html():
    tier_colors = {"Platinum": "#e2e8f0", "Gold": "#f59e0b", "Silver": "#94a3b8", "Bronze": "#b45309"}
    status_colors = {"active": "#4ade80", "pilot": "#38bdf8", "pending": "#f59e0b"}
    status_bg    = {"active": "#14532d", "pilot": "#0c4a6e", "pending": "#78350f"}

    # --- SVG: partner tier pyramid ---
    svg_w, svg_h = 500, 260
    tiers = [
        ("Platinum", 3,  "#7c3aed", 60,  40),
        ("Gold",     5,  "#b45309", 100, 60),
        ("Silver",   7,  "#475569", 150, 60),
        ("Bronze",   8,  "#1e3a5f", 220, 80),
    ]
    pyramid_rects = ""
    label_y = {"Platinum": 80, "Gold": 130, "Silver": 190, "Bronze": 250}
    widths   = {"Platinum": 160, "Gold": 240, "Silver": 320, "Bronze": 420}
    ys       = {"Platinum": 20,  "Gold": 70,  "Silver": 130, "Bronze": 190}
    heights  = {"Platinum": 44,  "Gold": 52,  "Silver": 52,  "Bronze": 52}
    for tname, count, color, _, __ in tiers:
        w = widths[tname]
        x = (svg_w - w) // 2
        y = ys[tname]
        h = heights[tname]
        tc = tier_colors[tname]
        pyramid_rects += (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{color}" opacity="0.85"/>'
            f'<text x="{svg_w//2}" y="{y + h//2 - 6}" text-anchor="middle" fill="{tc}" font-size="13" font-weight="700">{tname}</text>'
            f'<text x="{svg_w//2}" y="{y + h//2 + 10}" text-anchor="middle" fill="{tc}" font-size="11" opacity="0.8">{count} partners</text>'
        )

    svg = f"""
    <svg width="{svg_w}" height="{svg_h}" style="background:#0f172a;border-radius:6px">
      {pyramid_rects}
      <text x="{svg_w//2}" y="{svg_h - 8}" text-anchor="middle" fill="#64748b" font-size="10">Partner Tier Pyramid — 23 total</text>
    </svg>
    """

    # --- Partner grid cards ---
    cards = ""
    for name, tier, status, rev_k, domain in PARTNERS:
        tc = tier_colors[tier]
        sc = status_colors[status]
        sbg = status_bg[status]
        cards += f"""
        <div class="pcard">
          <div class="pname">{name}</div>
          <div class="pdomain">{domain}</div>
          <div style="margin-top:6px;display:flex;gap:6px;align-items:center;flex-wrap:wrap">
            <span class="badge" style="color:{tc};background:#1e293b;border:1px solid {tc}33">{tier}</span>
            <span class="badge" style="color:{sc};background:{sbg}">{status.upper()}</span>
          </div>
          <div class="prev">${rev_k}K</div>
        </div>"""

    total_rev = sum(p[3] for p in PARTNERS)
    active_count = sum(1 for p in PARTNERS if p[2] == "active")

    return f"""<!DOCTYPE html><html><head><title>Partner Logo Wall</title>
<style>body{{margin:0;padding:20px;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin:0 0 12px 0}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.metrics{{display:flex;gap:20px;flex-wrap:wrap}}
.metric{{background:#0f172a;padding:12px 20px;border-radius:6px;border-left:3px solid #C74634}}
.metric .val{{font-size:1.8em;font-weight:700;color:#38bdf8}}
.metric .lbl{{font-size:0.8em;color:#94a3b8;margin-top:2px}}
.badge{{display:inline-block;padding:2px 7px;border-radius:4px;font-size:0.72em;font-weight:600}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;margin-top:10px}}
.pcard{{background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:12px}}
.pcard:hover{{border-color:#38bdf8;transition:border-color .2s}}
.pname{{font-weight:700;font-size:0.9em;color:#e2e8f0}}
.pdomain{{font-size:0.75em;color:#64748b;margin-top:2px}}
.prev{{font-size:0.8em;color:#4ade80;margin-top:6px;font-weight:600}}
</style></head>
<body>
<h1>Partner Logo Wall</h1>
<p style="color:#64748b;margin-top:0">Port {PORT} — Partner ecosystem grid with integration status and revenue contribution</p>

<div class="card">
  <h2>Ecosystem Metrics</h2>
  <div class="metrics">
    <div class="metric"><div class="val">23</div><div class="lbl">Total Partners</div></div>
    <div class="metric"><div class="val">$2.1M</div><div class="lbl">Pipeline</div></div>
    <div class="metric"><div class="val">{active_count}</div><div class="lbl">Active Integrations</div></div>
    <div class="metric"><div class="val">${total_rev // 1000}K</div><div class="lbl">Rev Contribution</div></div>
  </div>
</div>

<div class="card" style="display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start">
  <div>
    <h2>Tier Pyramid</h2>
    {svg}
  </div>
  <div style="flex:1;min-width:220px">
    <h2>Tier Legend</h2>
    <table style="width:100%;border-collapse:collapse;font-size:0.88em">
      <tr style="color:#64748b;border-bottom:1px solid #334155">
        <th style="text-align:left;padding:5px">Tier</th>
        <th style="text-align:left;padding:5px">Partners</th>
        <th style="text-align:left;padding:5px">Min Rev</th>
      </tr>
      <tr style="border-bottom:1px solid #1e293b">
        <td style="padding:5px;color:#e2e8f0;font-weight:600">Platinum</td><td style="padding:5px">3</td><td style="padding:5px">$300K+</td>
      </tr>
      <tr style="border-bottom:1px solid #1e293b">
        <td style="padding:5px;color:#f59e0b;font-weight:600">Gold</td><td style="padding:5px">5</td><td style="padding:5px">$100K+</td>
      </tr>
      <tr style="border-bottom:1px solid #1e293b">
        <td style="padding:5px;color:#94a3b8;font-weight:600">Silver</td><td style="padding:5px">7</td><td style="padding:5px">$40K+</td>
      </tr>
      <tr>
        <td style="padding:5px;color:#b45309;font-weight:600">Bronze</td><td style="padding:5px">8</td><td style="padding:5px">&lt;$40K</td>
      </tr>
    </table>
    <div style="margin-top:16px">
      <h2>Status Key</h2>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <span class="badge" style="color:#4ade80;background:#14532d">ACTIVE</span>
        <span class="badge" style="color:#38bdf8;background:#0c4a6e">PILOT</span>
        <span class="badge" style="color:#f59e0b;background:#78350f">PENDING</span>
      </div>
    </div>
  </div>
</div>

<div class="card">
  <h2>Partner Directory</h2>
  <div class="grid">
    {cards}
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Logo Wall")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

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

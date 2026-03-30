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

MILESTONES = [
    {"name": "intro",                   "status": "COMPLETE",     "pct": 100},
    {"name": "NDA",                     "status": "COMPLETE",     "pct": 100},
    {"name": "co_engineering",          "status": "IN_PROGRESS",  "pct": 40},
    {"name": "preferred_cloud",         "status": "BLOCKED",      "pct": 0},
    {"name": "design_partner_referral", "status": "PENDING",      "pct": 0},
    {"name": "GTC_talk",                "status": "PENDING",      "pct": 0},
    {"name": "commercial",              "status": "PENDING",      "pct": 0},
    {"name": "revenue",                 "status": "PENDING",      "pct": 0},
]

PARTNERS = [
    {"name": "Wandelbots", "stage": "preferred_cloud", "prob": 0.30, "arr": 24000},
    {"name": "Machina",    "stage": "co_engineering",  "prob": 0.45, "arr": 31000},
    {"name": "Figure AI",  "stage": "NDA",             "prob": 0.60, "arr": 47000},
    {"name": "Agility",   "stage": "intro",            "prob": 0.25, "arr": 18000},
]

def build_html():
    # --- Funnel SVG ---
    svg_w, svg_h = 700, 280
    bar_h = 22
    bar_gap = 10
    label_w = 210
    status_colors = {"COMPLETE": "#22c55e", "IN_PROGRESS": "#38bdf8", "BLOCKED": "#ef4444", "PENDING": "#475569"}
    funnel_bars = ""
    for i, m in enumerate(MILESTONES):
        y = 20 + i * (bar_h + bar_gap)
        max_bar = svg_w - label_w - 80
        filled = max_bar * m["pct"] / 100
        color = status_colors[m["status"]]
        funnel_bars += f'<text x="5" y="{y+16}" fill="#cbd5e1" font-size="12" font-family="monospace">{m["name"]}</text>'
        funnel_bars += f'<rect x="{label_w}" y="{y}" width="{max_bar}" height="{bar_h}" rx="4" fill="#1e293b"/>'
        if filled > 0:
            funnel_bars += f'<rect x="{label_w}" y="{y}" width="{filled:.1f}" height="{bar_h}" rx="4" fill="{color}"/>'
        funnel_bars += f'<text x="{label_w + max_bar + 6}" y="{y+16}" fill="{color}" font-size="11" font-family="monospace">{m["status"]}</text>'
    svg_funnel = f'<svg width="{svg_w}" height="{svg_h}" style="background:#0f172a;border-radius:8px">{funnel_bars}</svg>'

    # --- Partner table SVG ---
    tw, th = 700, 220
    cols = ["Partner", "Stage", "Probability", "ARR Potential"]
    col_x = [10, 160, 330, 490]
    trows = ""
    trows += f'<rect x="0" y="0" width="{tw}" height="{th}" rx="8" fill="#0f172a"/>'
    for ci, ch in enumerate(cols):
        trows += f'<text x="{col_x[ci]+5}" y="22" fill="#94a3b8" font-size="12" font-family="monospace" font-weight="bold">{ch}</text>'
    trows += f'<line x1="0" y1="28" x2="{tw}" y2="28" stroke="#334155" stroke-width="1"/>'
    weighted_arr = sum(p["prob"] * p["arr"] for p in PARTNERS)
    for ri, p in enumerate(PARTNERS):
        ry = 50 + ri * 38
        bg = "#1e293b" if ri % 2 == 0 else "#0f172a"
        trows += f'<rect x="0" y="{ry-16}" width="{tw}" height="36" fill="{bg}"/>'
        trows += f'<text x="{col_x[0]+5}" y="{ry+4}" fill="#f1f5f9" font-size="13" font-family="monospace">{p["name"]}</text>'
        trows += f'<text x="{col_x[1]+5}" y="{ry+4}" fill="#38bdf8" font-size="12" font-family="monospace">{p["stage"]}</text>'
        trows += f'<text x="{col_x[2]+5}" y="{ry+4}" fill="#facc15" font-size="13" font-family="monospace">{int(p["prob"]*100)}%</text>'
        trows += f'<text x="{col_x[3]+5}" y="{ry+4}" fill="#22c55e" font-size="13" font-family="monospace">${p["arr"]:,}</text>'
    svg_table = f'<svg width="{tw}" height="{th}">{trows}</svg>'

    complete = sum(1 for m in MILESTONES if m["status"] == "COMPLETE")
    in_prog  = sum(1 for m in MILESTONES if m["status"] == "IN_PROGRESS")
    pending  = sum(1 for m in MILESTONES if m["status"] == "PENDING")

    return f"""<!DOCTYPE html><html><head><title>NVIDIA GTM Tracker</title>
<style>body{{margin:0;background:#0f172a;color:#f1f5f9;font-family:monospace;padding:24px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:14px;margin:18px 0 8px}}
.stats{{display:flex;gap:24px;margin:16px 0}}.stat{{background:#1e293b;border-radius:8px;padding:12px 20px}}
.stat .val{{font-size:22px;font-weight:bold;color:#38bdf8}}.stat .lbl{{font-size:11px;color:#94a3b8}}
.blocked{{color:#ef4444;background:#1e293b;border-radius:6px;padding:8px 14px;font-size:13px;margin:10px 0}}
</style></head><body>
<h1>NVIDIA Go-To-Market Tracker</h1>
<p style="color:#94a3b8;font-size:13px">Partnership GTM funnel milestones — Port {PORT}</p>
<div class="blocked">BLOCKED: preferred_cloud_agreement — Greg contact needed</div>
<div class="stats">
  <div class="stat"><div class="val">{complete}</div><div class="lbl">Complete</div></div>
  <div class="stat"><div class="val">{in_prog}</div><div class="lbl">In Progress</div></div>
  <div class="stat"><div class="val">{pending}</div><div class="lbl">Pending</div></div>
  <div class="stat"><div class="val">73%</div><div class="lbl">Prob-weighted</div></div>
  <div class="stat"><div class="val">${int(weighted_arr):,}</div><div class="lbl">Weighted ARR</div></div>
</div>
<h2>8-Milestone GTM Funnel</h2>{svg_funnel}
<h2>Co-Sell Partner Pipeline</h2>{svg_table}
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="NVIDIA Go-To-Market Tracker")
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

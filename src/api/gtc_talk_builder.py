"""GTC Talk Builder — FastAPI service on port 8284.

Tracks and assembles GTC 2027 talk submission requirements and demo materials.
Fallback to stdlib http.server if FastAPI/uvicorn not available.
"""

import math
import random
from datetime import date

TODAY = date(2026, 3, 30)
DEADLINE = date(2026, 10, 1)  # GTC 2027 submission deadline
DAYS_LEFT = (DEADLINE - TODAY).days

# Mock data: talk readiness items
READINESS_ITEMS = [
    {"id": "abstract",           "label": "Abstract",            "pct": 100, "critical": False, "status": "DONE"},
    {"id": "demo_video",         "label": "Demo Video",           "pct": 90,  "critical": True,  "status": "IN_PROGRESS"},
    {"id": "results_data",       "label": "Results Data",         "pct": 85,  "critical": True,  "status": "IN_PROGRESS"},
    {"id": "code_release",       "label": "Code Release",         "pct": 70,  "critical": False, "status": "IN_PROGRESS"},
    {"id": "NVIDIA_endorsement", "label": "NVIDIA Endorsement",   "pct": 0,   "critical": True,  "status": "BLOCKED"},
    {"id": "co_presenter",       "label": "Co-Presenter",         "pct": 0,   "critical": True,  "status": "BLOCKED"},
    {"id": "slides",             "label": "Slide Deck",           "pct": 60,  "critical": False, "status": "IN_PROGRESS"},
    {"id": "paper_ref",          "label": "Paper Reference",      "pct": 75,  "critical": False, "status": "IN_PROGRESS"},
    {"id": "live_demo",          "label": "Live Demo Setup",      "pct": 55,  "critical": True,  "status": "IN_PROGRESS"},
    {"id": "media_kit",          "label": "Media Kit",            "pct": 40,  "critical": False, "status": "IN_PROGRESS"},
]

OVERALL_READINESS = 68  # %

# Demo narrative segments (20-min talk)
NARRATIVE_SEGMENTS = [
    {"label": "Intro",             "minutes": 2, "status": "DONE",        "color": "#22c55e"},
    {"label": "Problem",           "minutes": 3, "status": "DONE",        "color": "#22c55e"},
    {"label": "Live Demo",         "minutes": 5, "status": "IN_PROGRESS", "color": "#f59e0b"},
    {"label": "Results",           "minutes": 4, "status": "IN_PROGRESS", "color": "#f59e0b"},
    {"label": "Future Work",       "minutes": 3, "status": "NOT_STARTED", "color": "#64748b"},
    {"label": "NVIDIA Partnership","minutes": 3, "status": "BLOCKED",     "color": "#C74634"},
]

BLOCKERS = [i for i in READINESS_ITEMS if i["status"] == "BLOCKED"]


def render_readiness_svg() -> str:
    """SVG 1: Talk readiness checklist as horizontal progress bars."""
    w, h = 640, 360
    bar_h = 22
    gap = 14
    label_w = 170
    bar_w = 350
    x0 = label_w + 20
    y0 = 20

    rows = []
    for idx, item in enumerate(READINESS_ITEMS):
        y = y0 + idx * (bar_h + gap)
        pct = item["pct"]
        fill_w = int(bar_w * pct / 100)
        bar_color = "#C74634" if item["critical"] else "#38bdf8"
        if pct == 100:
            bar_color = "#22c55e"
        elif item["status"] == "BLOCKED":
            bar_color = "#C74634"

        status_label = item["status"]
        status_color = {"DONE": "#22c55e", "IN_PROGRESS": "#f59e0b",
                        "BLOCKED": "#C74634", "NOT_STARTED": "#64748b"}.get(status_label, "#94a3b8")

        rows.append(f"""
  <!-- row {idx} -->
  <text x="{label_w}" y="{y + bar_h - 6}" text-anchor="end" font-size="11" fill="#cbd5e1" font-family="monospace">{item['label']}</text>
  <rect x="{x0}" y="{y}" width="{bar_w}" height="{bar_h}" rx="4" fill="#1e293b"/>
  <rect x="{x0}" y="{y}" width="{fill_w}" height="{bar_h}" rx="4" fill="{bar_color}" opacity="0.85"/>
  <text x="{x0 + bar_w + 8}" y="{y + bar_h - 6}" font-size="10" fill="{status_color}" font-family="monospace">{pct}% {status_label}</text>
""")

    svg_h = y0 + len(READINESS_ITEMS) * (bar_h + gap) + 10
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{svg_h}" viewBox="0 0 {w} {svg_h}" style="background:#0f172a;border-radius:8px">
  <text x="{w//2}" y="15" text-anchor="middle" font-size="13" fill="#38bdf8" font-family="monospace" font-weight="bold">GTC 2027 Talk Readiness Checklist</text>
  {''.join(rows)}
</svg>"""


def render_narrative_svg() -> str:
    """SVG 2: Demo narrative timeline — 20-min talk flow chart."""
    w, h = 640, 160
    total_min = sum(s["minutes"] for s in NARRATIVE_SEGMENTS)
    x = 20
    y_base = 60
    bar_h = 50
    avail_w = w - 40
    scale = avail_w / total_min

    bars = []
    for seg in NARRATIVE_SEGMENTS:
        seg_w = int(seg["minutes"] * scale)
        bars.append(f"""
  <rect x="{x}" y="{y_base}" width="{seg_w - 2}" height="{bar_h}" rx="4" fill="{seg['color']}" opacity="0.85"/>
  <text x="{x + (seg_w - 2)//2}" y="{y_base + 20}" text-anchor="middle" font-size="10" fill="#0f172a" font-family="monospace" font-weight="bold">{seg['label']}</text>
  <text x="{x + (seg_w - 2)//2}" y="{y_base + 35}" text-anchor="middle" font-size="9" fill="#0f172a" font-family="monospace">{seg['minutes']}m</text>
""")
        x += seg_w

    # legend
    legend_items = [
        ("DONE", "#22c55e"), ("IN_PROGRESS", "#f59e0b"),
        ("BLOCKED", "#C74634"), ("NOT_STARTED", "#64748b"),
    ]
    legend = []
    lx = 20
    for lbl, col in legend_items:
        legend.append(f'<rect x="{lx}" y="125" width="12" height="12" rx="2" fill="{col}"/>')
        legend.append(f'<text x="{lx + 16}" y="136" font-size="9" fill="#94a3b8" font-family="monospace">{lbl}</text>')
        lx += 120

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="background:#0f172a;border-radius:8px">
  <text x="{w//2}" y="20" text-anchor="middle" font-size="13" fill="#38bdf8" font-family="monospace" font-weight="bold">20-Minute Talk Narrative Timeline</text>
  <text x="{w//2}" y="38" text-anchor="middle" font-size="10" fill="#64748b" font-family="monospace">GTC 2027 — OCI Robot Cloud Demo</text>
  {''.join(bars)}
  {''.join(legend)}
</svg>"""


def build_html() -> str:
    svg1 = render_readiness_svg()
    svg2 = render_narrative_svg()
    blockers_html = "".join(
        f'<li style="color:#C74634;font-family:monospace">BLOCKED: {b["label"]}</li>'
        for b in BLOCKERS
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>GTC Talk Builder — OCI Robot Cloud</title>
  <style>
    body {{ background:#0f172a; color:#e2e8f0; font-family:monospace; margin:0; padding:20px; }}
    h1 {{ color:#38bdf8; border-bottom:2px solid #C74634; padding-bottom:8px; }}
    .metrics {{ display:flex; gap:20px; flex-wrap:wrap; margin:20px 0; }}
    .card {{ background:#1e293b; border-radius:8px; padding:16px 24px; min-width:150px; text-align:center; }}
    .card-val {{ font-size:2em; font-weight:bold; color:#38bdf8; }}
    .card-lbl {{ font-size:0.8em; color:#64748b; margin-top:4px; }}
    .card.warn .card-val {{ color:#f59e0b; }}
    .card.danger .card-val {{ color:#C74634; }}
    .card.ok .card-val {{ color:#22c55e; }}
    .section {{ margin:30px 0; }}
    h2 {{ color:#38bdf8; font-size:1em; letter-spacing:2px; text-transform:uppercase; }}
    ul {{ padding-left:20px; }}
    li {{ margin:4px 0; }}
    svg {{ display:block; max-width:100%; }}
    footer {{ color:#334155; font-size:0.75em; margin-top:40px; text-align:center; }}
  </style>
</head>
<body>
  <h1>GTC Talk Builder — OCI Robot Cloud 2027</h1>

  <div class="metrics">
    <div class="card {'ok' if OVERALL_READINESS >= 80 else 'warn' if OVERALL_READINESS >= 50 else 'danger'}">
      <div class="card-val">{OVERALL_READINESS}%</div>
      <div class="card-lbl">Submission Readiness</div>
    </div>
    <div class="card {'ok' if DAYS_LEFT > 90 else 'warn' if DAYS_LEFT > 30 else 'danger'}">
      <div class="card-val">{DAYS_LEFT}</div>
      <div class="card-lbl">Days Until Deadline</div>
    </div>
    <div class="card danger">
      <div class="card-val">{len(BLOCKERS)}</div>
      <div class="card-lbl">Critical Blockers</div>
    </div>
    <div class="card warn">
      <div class="card-val">90%</div>
      <div class="card-lbl">Demo Recording Status</div>
    </div>
    <div class="card">
      <div class="card-val">Oct 2026</div>
      <div class="card-lbl">GTC 2027 Deadline</div>
    </div>
  </div>

  <div class="section">
    <h2>Readiness Checklist</h2>
    {svg1}
  </div>

  <div class="section">
    <h2>Talk Narrative Timeline</h2>
    {svg2}
  </div>

  <div class="section">
    <h2>Critical Blockers</h2>
    <ul>{blockers_html}</ul>
  </div>

  <footer>OCI Robot Cloud — GTC Talk Builder | Port 8284 | Today: {TODAY} | Deadline: {DEADLINE}</footer>
</body>
</html>
"""


try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn

    app = FastAPI(title="GTC Talk Builder", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "gtc_talk_builder", "port": 8284}

    @app.get("/api/readiness")
    def api_readiness():
        return {
            "overall_pct": OVERALL_READINESS,
            "items": READINESS_ITEMS,
            "blockers": BLOCKERS,
            "days_until_deadline": DAYS_LEFT,
            "deadline": str(DEADLINE),
        }

    @app.get("/api/narrative")
    def api_narrative():
        return {"segments": NARRATIVE_SEGMENTS, "total_minutes": 20}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8284)

except ImportError:
    # Fallback: stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            content = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, fmt, *args):
            pass  # silence

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", 8284), Handler)
        print("GTC Talk Builder running on http://0.0.0.0:8284 (stdlib fallback)")
        server.serve_forever()

"""AI World 2026 Demo Planner — OCI Robot Cloud booth demo coordinator.
Port 8342
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math
import json
from datetime import datetime, date

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

DEMO_SEGMENTS = [
    {"id": "intro",              "label": "Intro",               "duration": 2, "status": "APPROVED",   "rehearsals": 5},
    {"id": "live_inference",     "label": "Live Inference",      "duration": 3, "status": "REHEARSED",  "rehearsals": 8},
    {"id": "fine_tune_speedrun", "label": "Fine-Tune Speedrun",  "duration": 4, "status": "REHEARSED",  "rehearsals": 6},
    {"id": "cost_comparison",    "label": "Cost Comparison",     "duration": 2, "status": "APPROVED",   "rehearsals": 4},
    {"id": "partner_testimonial","label": "Partner Testimonial", "duration": 2, "status": "SCRIPTED",   "rehearsals": 2},
    {"id": "call_to_action",     "label": "Call to Action",      "duration": 2, "status": "SCRIPTED",   "rehearsals": 1},
]

REQUIREMENTS = [
    {"id": "robot_hardware",       "label": "Robot Hardware",        "status": "READY",       "owner": "HW Team"},
    {"id": "network_connectivity", "label": "Network Connectivity",   "status": "READY",       "owner": "Infra"},
    {"id": "model_loaded",         "label": "Model Loaded",           "status": "READY",       "owner": "ML Team"},
    {"id": "fallback_video",       "label": "Fallback Video",         "status": "READY",       "owner": "Prod"},
    {"id": "demo_script",          "label": "Demo Script",            "status": "READY",       "owner": "PM"},
    {"id": "booth_design",         "label": "Booth Design",           "status": "READY",       "owner": "Marketing"},
    {"id": "NVIDIA_badge",         "label": "NVIDIA Badge",           "status": "BLOCKED",     "owner": "Partnerships"},
    {"id": "customer_logos",       "label": "Customer Logos",         "status": "IN_PROGRESS", "owner": "Marketing"},
    {"id": "pricing_sheet",        "label": "Pricing Sheet",          "status": "IN_PROGRESS", "owner": "Product"},
    {"id": "oracle_legal",         "label": "Oracle Legal",           "status": "BLOCKED",     "owner": "Legal"},
    {"id": "press_kit",            "label": "Press Kit",              "status": "IN_PROGRESS", "owner": "PR"},
    {"id": "social_content",       "label": "Social Content",         "status": "IN_PROGRESS", "owner": "Marketing"},
]

TARGET_DATE = "2026-09-10"
EVENT_NAME  = "AI World 2026"
LOCATION    = "Las Vegas, NV"


def compute_metrics():
    total = len(REQUIREMENTS)
    ready       = sum(1 for r in REQUIREMENTS if r["status"] == "READY")
    in_progress = sum(1 for r in REQUIREMENTS if r["status"] == "IN_PROGRESS")
    blocked     = sum(1 for r in REQUIREMENTS if r["status"] == "BLOCKED")
    readiness_pct = round(ready / total * 100)

    total_segs = len(DEMO_SEGMENTS)
    rehearsed  = sum(1 for s in DEMO_SEGMENTS if s["status"] in ("REHEARSED", "APPROVED"))
    rehearsal_pct = round(rehearsed / total_segs * 100)

    today = date.today()
    target = date(2026, 9, 10)
    days_left = (target - today).days

    gonogo = "GO" if blocked == 0 and readiness_pct >= 90 else "NO-GO"
    return {
        "readiness_pct": readiness_pct,
        "ready": ready, "in_progress": in_progress, "blocked": blocked,
        "rehearsal_pct": rehearsal_pct,
        "days_left": days_left,
        "gonogo": gonogo,
    }


# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def build_timeline_svg():
    W, H = 860, 220
    total_min = sum(s["duration"] for s in DEMO_SEGMENTS)  # 15

    STATUS_COLOR = {
        "APPROVED":  "#22c55e",
        "REHEARSED": "#38bdf8",
        "SCRIPTED":  "#f59e0b",
    }

    MARGIN_L, MARGIN_R = 10, 10
    TRACK_Y = 80
    TRACK_H = 60
    USABLE_W = W - MARGIN_L - MARGIN_R

    bars = []
    x_cursor = MARGIN_L
    for seg in DEMO_SEGMENTS:
        bw = seg["duration"] / total_min * USABLE_W
        color = STATUS_COLOR.get(seg["status"], "#64748b")
        bars.append((x_cursor, bw, seg, color))
        x_cursor += bw

    rects = []
    for (bx, bw, seg, color) in bars:
        label_short = seg["label"]
        dur_txt = f"{seg['duration']}m"
        rects.append(
            f'<rect x="{bx:.1f}" y="{TRACK_Y}" width="{bw:.1f}" height="{TRACK_H}" '
            f'fill="{color}" rx="4" stroke="#1e293b" stroke-width="1"/>'
        )
        mid_x = bx + bw / 2
        rects.append(
            f'<text x="{mid_x:.1f}" y="{TRACK_Y + 22}" text-anchor="middle" '
            f'font-size="11" fill="#0f172a" font-weight="700">{label_short}</text>'
        )
        rects.append(
            f'<text x="{mid_x:.1f}" y="{TRACK_Y + 38}" text-anchor="middle" '
            f'font-size="10" fill="#0f172a">{dur_txt}</text>'
        )
        rects.append(
            f'<text x="{mid_x:.1f}" y="{TRACK_Y + 54}" text-anchor="middle" '
            f'font-size="9" fill="#0f172a">{seg["status"]}</text>'
        )

    # Legend
    legend_items = [
        ("APPROVED",  "#22c55e"),
        ("REHEARSED", "#38bdf8"),
        ("SCRIPTED",  "#f59e0b"),
    ]
    legend_parts = []
    lx = MARGIN_L
    for label, color in legend_items:
        legend_parts.append(
            f'<rect x="{lx}" y="170" width="14" height="14" fill="{color}" rx="2"/>'
            f'<text x="{lx+18}" y="182" font-size="11" fill="#94a3b8">{label}</text>'
        )
        lx += 120

    inner = "\n".join(rects) + "\n" + "\n".join(legend_parts)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">
  <text x="{W//2}" y="30" text-anchor="middle" font-size="14" font-weight="700" fill="#f8fafc">15-Min Booth Demo Storyboard — {EVENT_NAME}</text>
  <text x="{W//2}" y="52" text-anchor="middle" font-size="11" fill="#94a3b8">Total duration: {total_min} min  |  Target: {TARGET_DATE}</text>
  {inner}
  <text x="{MARGIN_L}" y="210" font-size="10" fill="#475569">* Segment widths proportional to duration</text>
</svg>'''
    return svg


def build_checklist_svg():
    W, H = 860, 340
    STATUS_COLOR = {
        "READY":       "#22c55e",
        "IN_PROGRESS": "#f59e0b",
        "BLOCKED":     "#ef4444",
    }
    STATUS_ICON = {
        "READY":       "✓",
        "IN_PROGRESS": "◑",
        "BLOCKED":     "✗",
    }

    COLS = 3
    ROWS = math.ceil(len(REQUIREMENTS) / COLS)
    COL_W = W // COLS
    ROW_H = (H - 70) // ROWS

    items = []
    for i, req in enumerate(REQUIREMENTS):
        col = i % COLS
        row = i // COLS
        bx = col * COL_W + 12
        by = 60 + row * ROW_H
        color = STATUS_COLOR.get(req["status"], "#64748b")
        icon  = STATUS_ICON.get(req["status"], "?")
        items.append(
            f'<rect x="{bx}" y="{by}" width="{COL_W - 24}" height="{ROW_H - 8}" '
            f'fill="{color}22" stroke="{color}" stroke-width="1.5" rx="5"/>'
        )
        items.append(
            f'<text x="{bx + 10}" y="{by + 20}" font-size="13" fill="{color}" font-weight="700">{icon} {req["label"]}</text>'
        )
        items.append(
            f'<text x="{bx + 10}" y="{by + 36}" font-size="10" fill="#94a3b8">Owner: {req["owner"]}  |  {req["status"]}</text>'
        )

    inner = "\n".join(items)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">
  <text x="{W//2}" y="28" text-anchor="middle" font-size="14" font-weight="700" fill="#f8fafc">Demo Dependency Checklist — 12 Requirements</text>
  <text x="{W//2}" y="48" text-anchor="middle" font-size="11" fill="#94a3b8">Green=READY  Yellow=IN_PROGRESS  Red=BLOCKED</text>
  {inner}
</svg>'''
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html():
    m = compute_metrics()
    timeline_svg  = build_timeline_svg()
    checklist_svg = build_checklist_svg()

    gonogo_color = "#22c55e" if m["gonogo"] == "GO" else "#ef4444"

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI World Demo Planner — OCI Robot Cloud</title>
<style>
  body {{ margin:0; font-family:'Segoe UI',system-ui,sans-serif;
          background:#0f172a; color:#f8fafc; }}
  header {{ background:#C74634; padding:18px 32px; display:flex;
             justify-content:space-between; align-items:center; }}
  header h1 {{ margin:0; font-size:1.4rem; font-weight:700; }}
  header span {{ font-size:.9rem; opacity:.85; }}
  .metrics {{ display:flex; gap:16px; padding:24px 32px; flex-wrap:wrap; }}
  .card {{ background:#1e293b; border-radius:10px; padding:20px 28px;
            flex:1; min-width:160px; }}
  .card .val {{ font-size:2rem; font-weight:800; margin-top:6px; }}
  .card .lbl {{ font-size:.75rem; color:#94a3b8; text-transform:uppercase;
                letter-spacing:.08em; }}
  .section {{ padding:8px 32px 28px; }}
  .section h2 {{ font-size:1rem; color:#38bdf8; margin-bottom:12px; }}
  svg {{ max-width:100%; display:block; }}
  footer {{ text-align:center; padding:16px; font-size:.75rem; color:#475569; }}
</style>
</head>
<body>
<header>
  <h1>AI World 2026 — Demo Planner</h1>
  <span>{LOCATION} &nbsp;|&nbsp; Target: {TARGET_DATE} &nbsp;|&nbsp; {m["days_left"]} days left</span>
</header>

<div class="metrics">
  <div class="card">
    <div class="lbl">Demo Readiness</div>
    <div class="val" style="color:#38bdf8">{m["readiness_pct"]}%</div>
  </div>
  <div class="card">
    <div class="lbl">Rehearsal Completion</div>
    <div class="val" style="color:#22c55e">{m["rehearsal_pct"]}%</div>
  </div>
  <div class="card">
    <div class="lbl">Blocked Items</div>
    <div class="val" style="color:#ef4444">{m["blocked"]}</div>
  </div>
  <div class="card">
    <div class="lbl">In Progress</div>
    <div class="val" style="color:#f59e0b">{m["in_progress"]}</div>
  </div>
  <div class="card">
    <div class="lbl">Sep 10 Go/No-Go</div>
    <div class="val" style="color:{gonogo_color}">{m["gonogo"]}</div>
  </div>
  <div class="card">
    <div class="lbl">Requirements Ready</div>
    <div class="val" style="color:#22c55e">{m["ready"]} / {len(REQUIREMENTS)}</div>
  </div>
</div>

<div class="section">
  <h2>Demo Flow Timeline — 15-Min Storyboard</h2>
  {timeline_svg}
</div>

<div class="section">
  <h2>Dependency Checklist</h2>
  {checklist_svg}
</div>

<footer>OCI Robot Cloud &mdash; AI World Demo Planner &mdash; Port 8342 &mdash; {datetime.utcnow().strftime("%Y-%m-%d %H:%M")} UTC</footer>
</body>
</html>'''
    return html


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="AI World Demo Planner", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "ai_world_demo_planner", "port": 8342}

    @app.get("/api/metrics")
    def api_metrics():
        return compute_metrics()

    @app.get("/api/segments")
    def api_segments():
        return DEMO_SEGMENTS

    @app.get("/api/requirements")
    def api_requirements():
        return REQUIREMENTS

else:
    # Fallback: stdlib http.server
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8342)
    else:
        print("FastAPI not found — starting stdlib server on port 8342")
        HTTPServer(("0.0.0.0", 8342), Handler).serve_forever()

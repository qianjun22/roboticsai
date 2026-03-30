"""
oci_compliance_reporter.py — OCI Robot Cloud  (port 8659)
Compliance framework radar, audit trail timeline, data residency map.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import json
from datetime import datetime, timedelta
import random

# ── colour palette ────────────────────────────────────────────────────────────
BG      = "#0f172a"
SURFACE = "#1e293b"
BORDER  = "#334155"
RED     = "#C74634"
BLUE    = "#38bdf8"
GREEN   = "#4ade80"
AMBER   = "#fbbf24"
PURPLE  = "#a78bfa"
SLATE   = "#94a3b8"
WHITE   = "#f1f5f9"
TEAL    = "#2dd4bf"

# ── compliance data ───────────────────────────────────────────────────────────
FRAMEWORKS = [
    {"name": "GDPR",      "score": 0.94, "color": BLUE},
    {"name": "SOC2",      "score": 0.87, "color": GREEN},
    {"name": "ISO27001",  "score": 0.91, "color": TEAL},
    {"name": "FedRAMP",   "score": 0.78, "color": AMBER},
    {"name": "HIPAA",     "score": 0.82, "color": PURPLE},
]

# ── audit events (deterministic seed) ────────────────────────────────────────
random.seed(42)
EVENT_TYPES = [
    {"type": "access",  "color": BLUE,   "sz": 5},
    {"type": "change",  "color": AMBER,  "sz": 7},
    {"type": "deploy",  "color": GREEN,  "sz": 8},
    {"type": "review",  "color": PURPLE, "sz": 6},
    {"type": "alert",   "color": RED,    "sz": 10},
]

def _gen_events(n=55):
    events = []
    base = datetime(2026, 1, 1)
    for i in range(n):
        day = random.randint(0, 89)
        et  = EVENT_TYPES[random.randint(0, len(EVENT_TYPES) - 1)]
        events.append({"day": day, "type": et["type"], "color": et["color"], "sz": et["sz"]})
    return events

AUDIT_EVENTS = _gen_events()


# ══════════════════════════════════════════════════════════════════════════════
# SVG 1: Compliance radar
# ══════════════════════════════════════════════════════════════════════════════

def _radar_svg() -> str:
    W, H = 480, 420
    cx, cy = W // 2, H // 2 + 10
    R_max  = 155
    n      = len(FRAMEWORKS)
    angles = [math.pi / 2 + i * 2 * math.pi / n for i in range(n)]

    def pt(r, idx):
        a = angles[idx]
        return cx + r * math.cos(a), cy - r * math.sin(a)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:{BG};font-family:monospace">',
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="{WHITE}" '
        f'font-size="13" font-weight="bold">Compliance Framework Radar</text>',
    ]

    # concentric rings (20% / 40% / 60% / 80% / 100%)
    for level in [0.2, 0.4, 0.6, 0.8, 1.0]:
        pts_str = " ".join(f"{pt(R_max*level, i)[0]:.1f},{pt(R_max*level, i)[1]:.1f}"
                           for i in range(n))
        pts_str += f" {pt(R_max*level, 0)[0]:.1f},{pt(R_max*level, 0)[1]:.1f}"
        lines.append(f'<polyline points="{pts_str}" fill="none" stroke="{BORDER}" '
                     f'stroke-width="0.8"/>')
        lx, ly = pt(R_max * level, 0)
        lines.append(f'<text x="{lx+4:.1f}" y="{ly-3:.1f}" fill="{SLATE}" '
                     f'font-size="9">{int(level*100)}%</text>')

    # spokes
    for i in range(n):
        ex, ey = pt(R_max, i)
        lines.append(f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" '
                     f'stroke="{BORDER}" stroke-width="0.8"/>')

    # target polygon (100%)
    target_pts = " ".join(f"{pt(R_max, i)[0]:.1f},{pt(R_max, i)[1]:.1f}" for i in range(n))
    target_pts += f" {pt(R_max, 0)[0]:.1f},{pt(R_max, 0)[1]:.1f}"
    lines.append(f'<polyline points="{target_pts}" fill="{BLUE}" fill-opacity="0.06" '
                 f'stroke="{BLUE}" stroke-width="1" stroke-dasharray="4,3" opacity="0.5"/>')

    # current score polygon
    score_pts = " ".join(
        f"{pt(R_max*fw['score'], i)[0]:.1f},{pt(R_max*fw['score'], i)[1]:.1f}"
        for i, fw in enumerate(FRAMEWORKS)
    )
    score_pts += f" {pt(R_max*FRAMEWORKS[0]['score'], 0)[0]:.1f},{pt(R_max*FRAMEWORKS[0]['score'], 0)[1]:.1f}"
    lines.append(f'<polyline points="{score_pts}" fill="{RED}" fill-opacity="0.18" '
                 f'stroke="{RED}" stroke-width="2"/>')

    # dots and labels
    for i, fw in enumerate(FRAMEWORKS):
        x, y = pt(R_max * fw["score"], i)
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{fw["color"]}" '
                     f'stroke="{BG}" stroke-width="1.5"/>')
        lx, ly = pt(R_max * 1.18, i)
        lines.append(f'<text x="{lx:.1f}" y="{ly+4:.1f}" text-anchor="middle" '
                     f'fill="{fw["color"]}" font-size="11" font-weight="bold">'
                     f'{fw["name"]}</text>')
        lines.append(f'<text x="{lx:.1f}" y="{ly+16:.1f}" text-anchor="middle" '
                     f'fill="{WHITE}" font-size="10">{int(fw["score"]*100)}%</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# SVG 2: Audit trail timeline
# ══════════════════════════════════════════════════════════════════════════════

def _audit_svg() -> str:
    W, H = 600, 320
    PAD  = {"l": 55, "r": 20, "t": 40, "b": 55}
    pw   = W - PAD["l"] - PAD["r"]
    ph   = H - PAD["t"] - PAD["b"]
    DAYS = 90
    ROWS = 4  # stagger rows

    def tx(day):
        return PAD["l"] + day / DAYS * pw

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:{BG};font-family:monospace">',
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="{WHITE}" '
        f'font-size="13" font-weight="bold">Audit Trail — 90-Day Timeline</text>',
        # main axis
        f'<line x1="{PAD["l"]}" y1="{PAD["t"]+ph//2}" x2="{PAD["l"]+pw}" '
        f'y2="{PAD["t"]+ph//2}" stroke="{BORDER}" stroke-width="1.5"/>',
    ]

    # month markers (Jan=0, Apr=90 for 2026-01 to 2026-03)
    for label, day in [("Jan 2026", 0), ("Feb", 31), ("Mar", 59), ("Apr 2026", 90)]:
        x = tx(day)
        lines.append(f'<line x1="{x:.1f}" y1="{PAD["t"]+ph//2-6}" x2="{x:.1f}" '
                     f'y2="{PAD["t"]+ph//2+6}" stroke="{SLATE}" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{PAD["t"]+ph//2+22}" text-anchor="middle" '
                     f'fill="{SLATE}" font-size="10">{label}</text>')

    row_offsets = [-32, -16, 16, 32]
    for i, ev in enumerate(AUDIT_EVENTS):
        x  = tx(ev["day"]) + random.uniform(-2, 2)
        row = i % ROWS
        y  = PAD["t"] + ph // 2 + row_offsets[row]
        r  = ev["sz"] / 2
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" '
                     f'fill="{ev["color"]}" fill-opacity="0.75" '
                     f'stroke="{ev["color"]}" stroke-width="0.5"/>')

    # legend
    lx, ly = PAD["l"] + 4, PAD["t"] + 4
    for et in EVENT_TYPES:
        lines.append(f'<circle cx="{lx+4}" cy="{ly+4}" r="4" fill="{et["color"]}" opacity="0.85"/>')
        lines.append(f'<text x="{lx+12}" y="{ly+8}" fill="{WHITE}" font-size="10">{et["type"]}</text>')
        lx += 72

    lines.append("</svg>")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# SVG 3: Data residency map
# ══════════════════════════════════════════════════════════════════════════════

def _residency_svg() -> str:
    W, H = 560, 340
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:{BG};font-family:monospace">',
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="{WHITE}" '
        f'font-size="13" font-weight="bold">Data Residency Map</text>',
    ]

    # simplified continent shapes ─────────────────────────────────────────────
    # North America
    lines.append(
        f'<rect x="60" y="80" width="180" height="130" rx="8" fill="{SURFACE}" '
        f'stroke="{BORDER}" stroke-width="1.2"/>'
    )
    lines.append(f'<text x="150" y="102" text-anchor="middle" fill="{SLATE}" font-size="10">North America</text>')

    # Europe
    lines.append(
        f'<rect x="295" y="80" width="120" height="100" rx="8" fill="{SURFACE}" '
        f'stroke="{BORDER}" stroke-width="1.2"/>'
    )
    lines.append(f'<text x="355" y="102" text-anchor="middle" fill="{SLATE}" font-size="10">Europe</text>')

    # Asia (outline only)
    lines.append(
        f'<rect x="430" y="80" width="110" height="100" rx="8" fill="{SURFACE}" '
        f'stroke="{BORDER}" stroke-width="1.2" stroke-dasharray="4,3" opacity="0.5"/>'
    )
    lines.append(f'<text x="485" y="102" text-anchor="middle" fill="{SLATE}" font-size="10" opacity="0.5">Asia (future)</text>')

    # Ashburn region box
    lines.append(f'<rect x="75" y="115" width="145" height="80" rx="6" fill="{BLUE}" '
                 f'fill-opacity="0.12" stroke="{BLUE}" stroke-width="1.5"/>')
    lines.append(f'<text x="148" y="140" text-anchor="middle" fill="{BLUE}" '
                 f'font-size="11" font-weight="bold">Ashburn (us-ashburn-1)</text>')
    lines.append(f'<text x="148" y="156" text-anchor="middle" fill="{WHITE}" font-size="10">GR00T_v2 · dagger_r9</text>')
    lines.append(f'<text x="148" y="170" text-anchor="middle" fill="{WHITE}" font-size="10">Training + Inference</text>')
    # GDPR badge
    lines.append(f'<rect x="80" y="180" width="55" height="18" rx="4" fill="{GREEN}" opacity="0.85"/>')
    lines.append(f'<text x="108" y="192" text-anchor="middle" fill="{BG}" font-size="9" font-weight="bold">CCPA ✓</text>')
    lines.append(f'<rect x="140" y="180" width="55" height="18" rx="4" fill="{AMBER}" opacity="0.85"/>')
    lines.append(f'<text x="168" y="192" text-anchor="middle" fill="{BG}" font-size="9" font-weight="bold">FedRAMP</text>')

    # Frankfurt region box
    lines.append(f'<rect x="305" y="115" width="100" height="60" rx="6" fill="{TEAL}" '
                 f'fill-opacity="0.12" stroke="{TEAL}" stroke-width="1.5"/>')
    lines.append(f'<text x="355" y="140" text-anchor="middle" fill="{TEAL}" '
                 f'font-size="11" font-weight="bold">Frankfurt (eu-frankfurt-1)</text>')
    lines.append(f'<text x="355" y="156" text-anchor="middle" fill="{WHITE}" font-size="10">Inference replica</text>')
    lines.append(f'<rect x="318" y="168" width="55" height="18" rx="4" fill="{BLUE}" opacity="0.85"/>')
    lines.append(f'<text x="346" y="180" text-anchor="middle" fill="{BG}" font-size="9" font-weight="bold">GDPR 94%</text>')
    lines.append(f'<rect x="378" y="168" width="55" height="18" rx="4" fill="{GREEN}" opacity="0.85"/>')
    lines.append(f'<text x="406" y="180" text-anchor="middle" fill="{BG}" font-size="9" font-weight="bold">ISO27001</text>')

    # data flow arrow US->EU
    lines.append(f'<defs><marker id="arr" markerWidth="8" markerHeight="6" refX="4" refY="3" orient="auto">'
                 f'<polygon points="0 0, 8 3, 0 6" fill="{AMBER}"/></marker></defs>')
    lines.append(f'<line x1="220" y1="155" x2="304" y2="155" stroke="{AMBER}" stroke-width="1.5" '
                 f'stroke-dasharray="5,3" marker-end="url(#arr)"/>')
    lines.append(f'<text x="262" y="148" text-anchor="middle" fill="{AMBER}" font-size="9">Replication</text>')

    # residency summary
    lines.append(f'<rect x="60" y="270" width="450" height="48" rx="6" fill="{SURFACE}" '
                 f'stroke="{BORDER}" stroke-width="1"/>')
    lines.append(f'<text x="285" y="291" text-anchor="middle" fill="{WHITE}" font-size="11" font-weight="bold">'
                 f'Residency Compliance Summary</text>')
    summary = [
        ("GDPR 94%",    GREEN,  80),
        ("SOC2 87%",    BLUE,  160),
        ("ISO27001 91%",TEAL,  255),
        ("FedRAMP 78%", AMBER, 350),
        ("HIPAA 82%",   PURPLE,440),
    ]
    for label, color, x in summary:
        lines.append(f'<text x="{x}" y="310" fill="{color}" font-size="10" font-weight="bold">{label}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# HTML page
# ══════════════════════════════════════════════════════════════════════════════

def _build_html() -> str:
    radar     = _radar_svg()
    audit     = _audit_svg()
    residency = _residency_svg()

    metrics = [
        ("SOC2 Type II evidence",   "87%",  GREEN),
        ("GDPR residency gap",      "94%",  BLUE),
        ("FedRAMP gov-cloud path",  "78%",  AMBER),
        ("ISO 27001",               "91%",  TEAL),
        ("HIPAA compliance",        "82%",  PURPLE),
    ]
    metric_cards = "".join(
        f'<div style="background:{SURFACE};border:1px solid {BORDER};border-radius:8px;'
        f'padding:14px 18px;min-width:150px">'
        f'<div style="font-size:11px;color:{SLATE};margin-bottom:6px">{lbl}</div>'
        f'<div style="font-size:24px;font-weight:bold;color:{col}">{val}</div>'
        f'</div>'
        for lbl, val, col in metrics
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>OCI Compliance Reporter — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:{BG};color:{WHITE};font-family:monospace;padding:24px}}
  h1{{color:{RED};font-size:20px;margin-bottom:4px}}
  .sub{{color:{SLATE};font-size:12px;margin-bottom:24px}}
  .cards{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:28px}}
  .section{{margin-bottom:32px}}
  .section h2{{color:{BLUE};font-size:14px;margin-bottom:12px;border-bottom:1px solid {BORDER};padding-bottom:6px}}
  svg{{display:block;max-width:100%}}
  footer{{color:{SLATE};font-size:10px;margin-top:32px;border-top:1px solid {BORDER};padding-top:12px}}
</style>
</head>
<body>
<h1>OCI Compliance Reporter</h1>
<div class="sub">OCI Robot Cloud · Compliance &amp; Audit Dashboard · Port 8659 · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>

<div class="cards">{metric_cards}</div>

<div class="section">
  <h2>Compliance Framework Radar</h2>
  {radar}
</div>

<div class="section">
  <h2>Audit Trail — 90-Day Timeline</h2>
  {audit}
</div>

<div class="section">
  <h2>Data Residency Map</h2>
  {residency}
</div>

<footer>oci_compliance_reporter.py · cycle-150A · © 2026 Oracle OCI Robot Cloud</footer>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
# App
# ══════════════════════════════════════════════════════════════════════════════

if USE_FASTAPI:
    app = FastAPI(title="OCI Compliance Reporter", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _build_html()

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "oci_compliance_reporter", "port": 8659})

    @app.get("/api/frameworks")
    async def frameworks():
        return JSONResponse({"frameworks": FRAMEWORKS})

    @app.get("/api/metrics")
    async def metrics():
        return JSONResponse({
            "soc2_evidence_pct": 87,
            "gdpr_residency_pct": 94,
            "fedramp_pct": 78,
            "iso27001_pct": 91,
            "hipaa_pct": 82,
            "audit_events_90d": len(AUDIT_EVENTS),
        })

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "oci_compliance_reporter", "port": 8659}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = _build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


if __name__ == "__main__":
    PORT = 8659
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not available — stdlib HTTPServer on :{PORT}")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

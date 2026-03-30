"""AI World Launch Countdown — FastAPI port 8847"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8847

# Conference target: September 10, 2026
CONF_DATE = "September 10, 2026"
DAYS_REMAINING = 168

# Milestone data: (label, start_month_offset, duration_months, status)
# month 0 = April 2026, month 5 = September 2026
MILESTONES = [
    ("Demo Video Final Cut",      0.0,  0.75, "READY"),
    ("SDK v2.0 Release",          0.0,  1.0,  "READY"),
    ("Cloud Infra Scale Test",    0.5,  1.0,  "IN_PROGRESS"),
    ("Partner Integration Docs",  0.5,  1.25, "READY"),
    ("GR00T v2 Fine-tune",        1.0,  1.5,  "IN_PROGRESS"),
    ("Safety Cert Submission",    1.5,  1.0,  "BLOCKED"),
    ("Booth Hardware Shipping",   2.0,  0.75, "READY"),
    ("Live Demo Rehearsal",       2.5,  0.5,  "IN_PROGRESS"),
    ("Press Briefing Deck",       3.0,  0.75, "READY"),
    ("Regulatory Filing",         3.0,  1.5,  "BLOCKED"),
    ("AI World Keynote Slot",     4.5,  0.25, "READY"),
    ("Post-event Follow-up Plan", 4.75, 0.25, "IN_PROGRESS"),
]

STATUS_COLOR = {
    "READY":       "#22c55e",
    "IN_PROGRESS": "#38bdf8",
    "BLOCKED":     "#ef4444",
}

STATUS_COUNTS = {
    "READY": sum(1 for m in MILESTONES if m[3] == "READY"),
    "IN_PROGRESS": sum(1 for m in MILESTONES if m[3] == "IN_PROGRESS"),
    "BLOCKED": sum(1 for m in MILESTONES if m[3] == "BLOCKED"),
}

def build_gantt_svg():
    """Build an SVG Gantt chart for Apr-Sep 2026 milestones."""
    svg_w, svg_h = 620, 480
    lmargin, rmargin = 185, 20
    tmargin, bmargin = 60, 40
    chart_w = svg_w - lmargin - rmargin
    chart_h = svg_h - tmargin - bmargin
    total_months = 6.0  # Apr through Sep
    row_h = chart_h / len(MILESTONES)
    month_labels = ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]

    out = [f'<svg width="{svg_w}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg">']
    out.append(f'<rect width="{svg_w}" height="{svg_h}" fill="#0f172a" rx="10"/>')

    # Title
    out.append(f'<text x="{svg_w//2}" y="30" text-anchor="middle" font-size="14" font-weight="bold" fill="#C74634">AI World 2026 Milestone Gantt — Apr to Sep</text>')

    # Month column headers
    for i, label in enumerate(month_labels):
        x = lmargin + (i / total_months) * chart_w
        out.append(f'<text x="{x + chart_w/total_months/2:.1f}" y="{tmargin - 10}" text-anchor="middle" font-size="11" fill="#94a3b8">{label}</text>')
        out.append(f'<line x1="{x:.1f}" y1="{tmargin}" x2="{x:.1f}" y2="{tmargin + chart_h}" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>')

    # Rows
    for i, (label, start, dur, status) in enumerate(MILESTONES):
        y = tmargin + i * row_h
        bar_x = lmargin + (start / total_months) * chart_w
        bar_w = max(4, (dur / total_months) * chart_w)
        color = STATUS_COLOR[status]

        # Row background (alternating)
        bg = "#0f172a" if i % 2 == 0 else "#131f30"
        out.append(f'<rect x="0" y="{y:.1f}" width="{svg_w}" height="{row_h:.1f}" fill="{bg}"/>')

        # Milestone label
        out.append(f'<text x="{lmargin - 6}" y="{y + row_h*0.65:.1f}" text-anchor="end" font-size="10" fill="#cbd5e1">{label}</text>')

        # Bar
        out.append(f'<rect x="{bar_x:.1f}" y="{y + row_h*0.2:.1f}" width="{bar_w:.1f}" height="{row_h*0.6:.1f}" rx="3" fill="{color}" fill-opacity="0.85"/>')

        # Status badge
        badge_x = bar_x + bar_w + 4
        out.append(f'<text x="{badge_x:.1f}" y="{y + row_h*0.65:.1f}" font-size="8" fill="{color}">{status}</text>')

    # Conference date marker (month 5 = Sep)
    conf_x = lmargin + (5.3 / total_months) * chart_w
    out.append(f'<line x1="{conf_x:.1f}" y1="{tmargin}" x2="{conf_x:.1f}" y2="{tmargin + chart_h}" stroke="#C74634" stroke-width="2" stroke-dasharray="6,3"/>')
    out.append(f'<text x="{conf_x + 3:.1f}" y="{tmargin + 12}" font-size="9" fill="#C74634">AI World</text>')

    out.append('</svg>')
    return "\n".join(out)


def build_html():
    gantt = build_gantt_svg()

    # Countdown ring (SVG circle progress: 168/365 days remaining → ~46% of year done)
    pct_done = 1.0 - (DAYS_REMAINING / 365.0)
    circ = 2 * math.pi * 54  # r=54
    dash = pct_done * circ
    gap = circ - dash
    countdown_svg = f"""
    <svg width="140" height="140" xmlns="http://www.w3.org/2000/svg">
      <circle cx="70" cy="70" r="54" fill="none" stroke="#1e293b" stroke-width="10"/>
      <circle cx="70" cy="70" r="54" fill="none" stroke="#C74634" stroke-width="10"
              stroke-dasharray="{dash:.1f} {gap:.1f}"
              stroke-dashoffset="{circ/4:.1f}" stroke-linecap="round"/>
      <text x="70" y="64" text-anchor="middle" font-size="26" font-weight="bold" fill="#e2e8f0">{DAYS_REMAINING}</text>
      <text x="70" y="82" text-anchor="middle" font-size="10" fill="#94a3b8">days left</text>
      <text x="70" y="96" text-anchor="middle" font-size="9" fill="#64748b">Sep 10 2026</text>
    </svg>"""

    # Status summary pills
    pills = "".join(
        f'<span style="background:{STATUS_COLOR[s]};color:#0f172a;padding:4px 12px;border-radius:12px;margin:4px;font-weight:bold;font-size:13px;display:inline-block">'
        f'{count} {s}</span>'
        for s, count in STATUS_COUNTS.items()
    )

    return f"""<!DOCTYPE html><html><head><title>AI World Launch Countdown</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 4px}}h2{{color:#38bdf8}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.row{{display:flex;align-items:center;gap:24px;flex-wrap:wrap}}
.meta{{color:#64748b;font-size:13px;padding:0 20px 10px}}</style></head>
<body>
<h1>AI World Launch Countdown</h1>
<p class="meta">Port {PORT} &mdash; Conference: {CONF_DATE}</p>
<div class="card">
  <div class="row">
    <div>{countdown_svg}</div>
    <div>
      <h2 style="margin:0 0 8px">Milestone Status</h2>
      <div>{pills}</div>
      <p style="color:#64748b;font-size:12px;margin-top:10px">
        Total milestones: {len(MILESTONES)} &nbsp;|&nbsp;
        {DAYS_REMAINING} days remaining &nbsp;|&nbsp;
        {int(pct_done*100)}% of year elapsed
      </p>
    </div>
  </div>
</div>
<div class="card">
  <h2>Gantt — Apr to Sep 2026</h2>
  {gantt}
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="AI World Launch Countdown")

    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()

    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

    @app.get("/metrics")
    def metrics():
        return {
            "port": PORT,
            "conference": CONF_DATE,
            "days_remaining": DAYS_REMAINING,
            "milestone_counts": STATUS_COUNTS,
            "milestones": [
                {"label": m[0], "start_month_offset": m[1], "duration_months": m[2], "status": m[3]}
                for m in MILESTONES
            ],
        }


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

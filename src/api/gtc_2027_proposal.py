"""GTC 2027 Proposal — FastAPI port 8857"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8857

def build_html():
    # Gantt chart: submission timeline
    # Milestones: Draft(Apr), NVIDIA Review(May), Submit(Jun), Notify(Aug), Present(Mar 2027)
    # Map to SVG x-axis: Jan 2026=0 ... Mar 2027=14 months
    milestones = [
        ("Draft",          "Apr 2026",  3,  3,  "#34d399", "done"),
        ("NVIDIA Review",  "May 2026",  4,  1,  "#38bdf8", "done"),
        ("Submit",         "Jun 2026",  5,  1,  "#818cf8", "in-progress"),
        ("Notify",         "Aug 2026",  7,  2,  "#f59e0b", "pending"),
        ("Present",        "Mar 2027",  14, 1,  "#C74634", "pending"),
    ]

    # SVG: 600x220, x: month 0(Jan26)..15(Apr27), y: rows
    W, H = 560, 200
    pad_l, pad_r, pad_t, pad_b = 110, 20, 30, 40
    months = 15  # Jan 2026 to Mar 2027 inclusive
    x_scale = (W - pad_l - pad_r) / months

    month_labels = ["Jan","Feb","Mar","Apr","May","Jun",
                    "Jul","Aug","Sep","Oct","Nov","Dec",
                    "Jan","Feb","Mar"]
    year_labels  = ["2026"]*12 + ["2027"]*3

    bar_h = 22
    row_gap = 32

    # grid lines + month labels
    grid = ""
    for i, (ml, yl) in enumerate(zip(month_labels, year_labels)):
        x = pad_l + i * x_scale
        grid += f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{H-pad_b}" stroke="#1e293b" stroke-width="1"/>\n'
        grid += f'<text x="{x+x_scale/2:.1f}" y="{H-pad_b+14}" text-anchor="middle" fill="#475569" font-size="9">{ml}</text>\n'
        if ml == "Jan":
            grid += f'<text x="{x+x_scale/2:.1f}" y="{H-pad_b+24}" text-anchor="middle" fill="#64748b" font-size="9" font-weight="bold">{yl}</text>\n'

    # today marker at month 2 (Mar 2026)
    today_x = pad_l + 2 * x_scale
    grid += f'<line x1="{today_x:.1f}" y1="{pad_t}" x2="{today_x:.1f}" y2="{H-pad_b}" stroke="#f87171" stroke-width="1.5" stroke-dasharray="4,3"/>\n'
    grid += f'<text x="{today_x+2:.1f}" y="{pad_t+10}" fill="#f87171" font-size="9">today</text>\n'

    bars = ""
    for row_i, (name, date, start_month, dur, color, status) in enumerate(milestones):
        y = pad_t + row_i * row_gap
        x = pad_l + start_month * x_scale
        bw = max(dur * x_scale - 2, 6)
        opacity = "0.9" if status == "done" else ("0.75" if status == "in-progress" else "0.45")
        bars += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h}" rx="4" fill="{color}" opacity="{opacity}"/>\n'
        bars += f'<text x="{x + bw/2:.1f}" y="{y + bar_h/2 + 4:.1f}" text-anchor="middle" fill="#0f172a" font-size="9" font-weight="bold">{date}</text>\n'
        # row label
        bars += f'<text x="{pad_l-4:.1f}" y="{y + bar_h/2 + 4:.1f}" text-anchor="end" fill="#cbd5e1" font-size="10">{name}</text>\n'
        # status badge
        badge_color = {"done": "#34d399", "in-progress": "#f59e0b", "pending": "#475569"}.get(status, "#475569")
        bars += f'<text x="{x + bw + 4:.1f}" y="{y + bar_h/2 + 4:.1f}" fill="{badge_color}" font-size="9">{status}</text>\n'

    svg = f"""
<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:640px;background:#0f172a;border-radius:8px">
  {grid}
  {bars}
</svg>"""

    # Readiness checklist
    checklist = [
        (True,  "Abstract drafted (500 words)"),
        (True,  "Technical content: GR00T N1.6 + OCI fine-tune pipeline"),
        (True,  "Demo video ready (1 MB MP4, sim-to-real)"),
        (True,  "Cost comparison slide ($0.43/run OCI vs $4.12 AWS)"),
        (True,  "Performance numbers: MAE 0.013, 8.7× vs baseline"),
        (True,  "Multi-GPU DDP 3.07× throughput validated"),
        (False, "Co-presenter confirmed — BLOCKED: pending Greg Pavlik intro"),
        (True,  "Speaker bio + headshot uploaded"),
        (False, "NVIDIA internal sponsor sign-off"),
    ]
    rows = ""
    for done, item in checklist:
        icon = "✅" if done else "🔴"
        style = "color:#94a3b8" if done else "color:#fca5a5;font-weight:600"
        rows += f'<tr><td>{icon}</td><td style="{style}">{item}</td></tr>\n'

    return f"""<!DOCTYPE html><html><head><title>GTC 2027 Proposal</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:24px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin-top:0}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.metric{{display:inline-block;margin:8px 16px 8px 0}}
.val{{font-size:2em;font-weight:700;color:#38bdf8}}
.lbl{{font-size:0.8em;color:#94a3b8}}
.blocked{{background:#450a0a;border-left:4px solid #f87171;padding:12px 16px;border-radius:4px;margin:12px 0}}
table{{width:100%;border-collapse:collapse}}td{{padding:7px 10px;border-bottom:1px solid #334155;vertical-align:top}}
tr:last-child td{{border-bottom:none}}
</style></head>
<body>
<h1>GTC 2027 Proposal Tracker</h1>
<p style="color:#94a3b8;margin-top:0">Talk: <em>OCI Robot Cloud: Production Robotics Training at Scale — $0.43/run vs $4.12 AWS</em> · port {PORT}</p>

<div class="card">
<h2>Readiness Overview</h2>
<div class="metric"><div class="val">87%</div><div class="lbl">Overall proposal readiness</div></div>
<div class="metric"><div class="val">7/9</div><div class="lbl">Checklist items complete</div></div>
<div class="metric"><div class="val">Jun 2026</div><div class="lbl">Target submission date</div></div>
<div class="metric"><div class="val">Mar 2027</div><div class="lbl">GTC presentation date</div></div>
<div class="blocked">
  <strong style="color:#f87171">BLOCKED:</strong> Co-presenter not yet confirmed — awaiting Greg Pavlik intro.
  This is the only hard blocker before submission.
</div>
</div>

<div class="card">
<h2>Submission Timeline (Gantt)</h2>
{svg}
</div>

<div class="card">
<h2>Submission Checklist</h2>
<table>{rows}</table>
</div>

<div class="card">
<h2>Proposed Talk Details</h2>
<table>
<tr><td style="color:#94a3b8;width:180px">Title</td><td>OCI Robot Cloud: Production Robotics Training at Scale — $0.43/run vs $4.12 AWS</td></tr>
<tr><td style="color:#94a3b8">Track</td><td>Robotics &amp; Autonomous Systems / Cloud Infrastructure</td></tr>
<tr><td style="color:#94a3b8">Format</td><td>40-min talk + 10-min demo</td></tr>
<tr><td style="color:#94a3b8">Speaker</td><td>Jun Qian (Oracle OCI)</td></tr>
<tr><td style="color:#94a3b8">Co-presenter</td><td><span style="color:#fca5a5">TBD — BLOCKED on Greg Pavlik intro</span></td></tr>
<tr><td style="color:#94a3b8">Key demo</td><td>Live GR00T N1.6 fine-tune on A100, sim-to-real transfer, cost dashboard</td></tr>
<tr><td style="color:#94a3b8">Differentiator</td><td>10× cheaper than AWS SageMaker; end-to-end SDG→train→eval pipeline in one click</td></tr>
</table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="GTC 2027 Proposal")
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

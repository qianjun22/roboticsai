"""Board Update Generator — FastAPI port 8805"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8805

def build_html():
    random.seed(55)

    # KPI summary data
    kpis = [
        ("Models Deployed", 47, 38, "#38bdf8"),
        ("Avg Inference Latency", "221ms", "244ms", "#4ade80"),
        ("Fine-tune Jobs (30d)", 312, 289, "#a78bfa"),
        ("Fleet Uptime", "99.94%", "99.87%", "#f59e0b"),
        ("Data Collected (demos)", "2.1M", "1.8M", "#38bdf8"),
        ("Active Robot Fleets", 18, 14, "#4ade80"),
    ]

    kpi_cards = "".join(
        f'<div class="kpi"><div class="kval" style="color:{color}">{cur}</div>'
        f'<div class="klbl">{label}</div>'
        f'<div class="kdelta">prev: {prev}</div></div>'
        for label, cur, prev, color in kpis
    )

    # Monthly throughput bar chart (12 months)
    months = ["Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar"]
    throughput = [random.randint(18, 45) + int(10 * math.sin(i * 0.5 + 1)) for i in range(12)]
    max_t = max(throughput)
    bar_w = 36
    bars = "".join(
        f'<rect x="{20 + i*(bar_w+6)}" y="{140 - int(throughput[i]/max_t*120)}" width="{bar_w}" height="{int(throughput[i]/max_t*120)}"
        fill="#38bdf8" opacity="0.8" rx="3"/>'
        f'<text x="{20 + i*(bar_w+6) + bar_w//2}" y="155" fill="#64748b" font-size="9" text-anchor="middle">{months[i]}</text>'
        f'<text x="{20 + i*(bar_w+6) + bar_w//2}" y="{136 - int(throughput[i]/max_t*120)}" fill="#e2e8f0" font-size="9" text-anchor="middle">{throughput[i]}</text>'
        for i in range(12)
    )

    # Burn-down / milestone timeline (5 milestones)
    milestones = [
        ("GR00T N1.6 GA", "2026-01-15", True),
        ("Isaac Sim SDG v2", "2026-02-28", True),
        ("Multi-GPU DDP", "2026-03-10", True),
        ("Jetson Edge Deploy", "2026-04-30", False),
        ("CoRL Paper Submit", "2026-05-31", False),
    ]
    ms_rows = "".join(
        f'<tr><td>{name}</td><td>{date}</td>'
        f'<td><span class="badge { "ok" if done else "warn" }">{ "Done" if done else "Planned" }</span></td></tr>'
        for name, date, done in milestones
    )

    # Risk radar: 5 axes (SVG polar)
    labels = ["Latency", "Data Gap", "Hardware", "Compliance", "Competition"]
    scores = [random.uniform(0.3, 0.9) for _ in range(5)]
    cx, cy, r = 130, 110, 80
    angles = [math.pi/2 + 2*math.pi*i/5 for i in range(5)]
    # outer pentagon
    outer = " ".join(f"{cx + r*math.cos(a):.1f},{cy - r*math.sin(a):.1f}" for a in angles)
    # risk polygon
    risk = " ".join(f"{cx + scores[i]*r*math.cos(angles[i]):.1f},{cy - scores[i]*r*math.sin(angles[i]):.1f}" for i in range(5))
    # axis lines + labels
    axes = "".join(
        f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx + r*math.cos(a):.1f}" y2="{cy - r*math.sin(a):.1f}" stroke="#334155" stroke-width="1"/>'
        f'<text x="{cx + (r+14)*math.cos(a):.1f}" y="{cy - (r+14)*math.sin(a):.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{labels[i]}</text>'
        for i, a in enumerate(angles)
    )

    # Recent update log
    updates = [
        ("2026-03-29", "GTC 2026 deck QA pass — 12 slides approved", "high"),
        ("2026-03-27", "DAgger run5 5k-step fine-tune complete: MAE 0.013", "high"),
        ("2026-03-24", "Multi-region failover validated: 99.94% uptime SLA", "med"),
        ("2026-03-21", "Safety monitor v2 deployed to 6 OCI instances", "med"),
        ("2026-03-18", "CoRL paper draft reviewed by 3 co-authors", "low"),
    ]
    update_rows = "".join(
        f'<tr><td style="white-space:nowrap">{date}</td>'
        f'<td>{msg}</td>'
        f'<td><span class="badge { "ok" if p=="high" else ("warn" if p=="med" else "") }">{p}</span></td></tr>'
        for date, msg, p in updates
    )

    return f"""<!DOCTYPE html><html><head><title>Board Update Generator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:24px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:12px 0;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.4)}}
.kpi-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:12px 0}}
.kpi{{background:#1e293b;border-radius:8px;padding:14px;text-align:center}}
.kval{{font-size:1.5rem;font-weight:700}}.klbl{{font-size:0.72rem;color:#94a3b8;margin:4px 0 2px}}
.kdelta{{font-size:0.68rem;color:#475569}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{background:#0f172a;color:#94a3b8;text-align:left;padding:7px 10px;font-weight:500}}
td{{padding:7px 10px;border-bottom:1px solid #0f172a}}
tr:hover td{{background:#0f172a}}
.badge{{display:inline-block;padding:2px 9px;border-radius:12px;font-size:0.72rem;font-weight:600}}
.ok{{background:#14532d;color:#4ade80}}.warn{{background:#78350f;color:#fbbf24}}
</style></head><body>
<h1>Board Update Generator</h1>
<p style="color:#64748b;margin:0 0 16px">Port {PORT} &nbsp;|&nbsp; OCI Robot Cloud — Executive Board Dashboard &nbsp;|&nbsp; Q1 2026 Snapshot</p>

<div class="kpi-grid">{kpi_cards}</div>

<div class="card">
  <h2>Fine-tune Job Throughput — Monthly (jobs/month)</h2>
  <svg width="100%" viewBox="0 0 540 165" style="overflow:visible">
    {''.join(f'<line x1="20" x2="520" y1="{140-int(v*1.2)}" y2="{140-int(v*1.2)}" stroke="#1e293b" stroke-width="1"/>' for v in [30,60,90,120])}
    {bars}
    <line x1="20" y1="140" x2="520" y2="140" stroke="#334155" stroke-width="1"/>
  </svg>
</div>

<div class="grid2">
  <div class="card">
    <h2>Milestone Tracker</h2>
    <table><thead><tr><th>Milestone</th><th>Target Date</th><th>Status</th></tr></thead>
    <tbody>{ms_rows}</tbody></table>
  </div>
  <div class="card">
    <h2>Risk Radar</h2>
    <svg width="100%" viewBox="0 0 260 220">
      <polygon points="{outer}" fill="none" stroke="#334155" stroke-width="1"/>
      {axes}
      <polygon points="{risk}" fill="rgba(196,70,52,0.25)" stroke="#C74634" stroke-width="1.5"/>
      {''.join(f'<circle cx="{cx + scores[i]*r*math.cos(angles[i]):.1f}" cy="{cy - scores[i]*r*math.sin(angles[i]):.1f}" r="4" fill="#C74634"/>' for i in range(5))}
    </svg>
  </div>
</div>

<div class="card">
  <h2>Recent Updates</h2>
  <table><thead><tr><th>Date</th><th>Update</th><th>Priority</th></tr></thead>
  <tbody>{update_rows}</tbody></table>
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Board Update Generator")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "board_update_generator"}

    @app.get("/summary")
    def summary():
        return {
            "models_deployed": 47,
            "avg_inference_latency_ms": 221,
            "finetune_jobs_30d": 312,
            "fleet_uptime_pct": 99.94,
            "demos_collected": "2.1M",
            "active_fleets": 18,
            "milestones_complete": 3,
            "milestones_planned": 2,
        }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

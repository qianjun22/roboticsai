"""Enterprise Onboarding Automator — FastAPI port 8779"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8779

def build_html():
    rng = random.Random(99)

    # Onboarding pipeline stages
    stages = ["Account Provisioning", "IAM Role Setup", "Cluster Deploy", "Model Registry Sync",
              "Network Policy", "SDK Install", "API Key Issue", "Health Smoke Test"]
    stage_times = [round(rng.uniform(0.5, 8.0), 2) for _ in stages]       # minutes per stage
    stage_status = [rng.choice(["done", "done", "done", "running", "pending"]) for _ in stages]
    # Force first 5 done, last 3 mixed for realism
    for i in range(5): stage_status[i] = "done"
    stage_status[5] = "running"
    stage_status[6] = "pending"
    stage_status[7] = "pending"

    # Cohort onboarding trend — past 30 days (cumulative)
    daily_new = [int(rng.gauss(4, 1.5)) for _ in range(30)]
    daily_new = [max(0, d) for d in daily_new]
    cumulative = []
    total = 0
    for d in daily_new:
        total += d
        cumulative.append(total)

    chart_w, chart_h = 560, 110
    max_c = cumulative[-1] or 1
    c_points = " ".join(
        f"{int(i / 29 * chart_w)},{int(chart_h - cumulative[i] / max_c * (chart_h - 10) - 4)}"
        for i in range(30)
    )
    # Fill polygon under curve
    fill_points = (
        f"0,{chart_h} " +
        " ".join(f"{int(i / 29 * chart_w)},{int(chart_h - cumulative[i] / max_c * (chart_h - 10) - 4)}" for i in range(30)) +
        f" {chart_w},{chart_h}"
    )

    # Success rate donut (SVG arc)
    success_rate = 0.91
    r, cx, cy = 44, 60, 60
    angle = success_rate * 2 * math.pi
    x1, y1 = cx + r * math.sin(0), cy - r * math.cos(0)
    x2, y2 = cx + r * math.sin(angle), cy - r * math.cos(angle)
    large_arc = 1 if success_rate > 0.5 else 0
    donut_arc = f"M {x1:.1f} {y1:.1f} A {r} {r} 0 {large_arc} 1 {x2:.1f} {y2:.1f}"

    # Active customers table
    orgs = ["AcmeCorp Robotics", "Tier1 Auto GmbH", "SkyManu Inc.", "OmniDex Labs",
            "FutureFab Co.", "NovArm Systems", "IndusMech Ltd"]
    org_stages  = [rng.choice(stages) for _ in orgs]
    org_pct     = [rng.randint(55, 100) for _ in orgs]
    org_pct[-1] = 62  # one in-progress customer
    org_owners  = ["alice", "bob", "carol", "alice", "dave", "bob", "carol"]
    rows = ""
    for o, s, p, ow in zip(orgs, org_stages, org_pct, org_owners):
        color = "#22c55e" if p == 100 else ("#f59e0b" if p >= 80 else "#ef4444")
        bar_w = int(p * 1.2)
        rows += (
            f"<tr><td>{o}</td><td>{s}</td>"
            f"<td><div style='background:#0f172a;border-radius:4px;width:120px;height:10px;display:inline-block'>"
            f"<div style='background:{color};width:{bar_w}px;height:10px;border-radius:4px'></div></div>"
            f" <span style='font-size:11px;color:{color}'>{p}%</span></td>"
            f"<td style='color:#94a3b8'>{ow}</td></tr>"
        )

    # Stage timeline bars (Gantt-style)
    gantt_rows = ""
    x_cursor = 0
    status_colors = {"done": "#22c55e", "running": "#38bdf8", "pending": "#475569"}
    total_time = sum(stage_times)
    gantt_w = 520
    for st, tm, ss in zip(stages, stage_times, stage_status):
        bw = int(tm / total_time * gantt_w)
        color = status_colors[ss]
        gantt_rows += (
            f'<div style="display:flex;align-items:center;margin:4px 0">'
            f'<span style="width:160px;font-size:12px;color:#94a3b8;text-align:right;padding-right:10px">{st}</span>'
            f'<div style="background:#0f172a;border-radius:3px;flex:1;height:18px">'
            f'<div style="background:{color};width:{bw}px;height:18px;border-radius:3px;transition:width 0.3s">'
            f'<span style="font-size:10px;padding:3px 5px;color:#0f172a;font-weight:700">{tm}m</span></div></div>'
            f'<span style="margin-left:8px;font-size:11px;color:{color}">{ss.upper()}</span></div>'
        )

    done_count = stage_status.count("done")
    eta_min    = sum(t for t, s in zip(stage_times, stage_status) if s != "done")

    return f"""<!DOCTYPE html><html><head><title>Enterprise Onboarding Automator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 24px 4px;margin:0;font-size:1.6rem}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
.card{{background:#1e293b;padding:20px;margin:12px;border-radius:8px;box-shadow:0 2px 8px #0004}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#0f172a;padding:8px 12px;text-align:left;color:#94a3b8;font-weight:600}}
td{{padding:7px 12px;border-bottom:1px solid #334155}}
.metric{{display:inline-block;background:#0f172a;border-radius:6px;padding:10px 22px;margin:6px;text-align:center}}
.metric .val{{font-size:1.5rem;font-weight:700;color:#38bdf8}}
.metric .lbl{{font-size:11px;color:#64748b;margin-top:2px}}
</style></head>
<body>
<h1>Enterprise Onboarding Automator</h1>
<p style="color:#64748b;margin:0 24px 16px">Port {PORT} &nbsp;|&nbsp; OCI Robot Cloud customer provisioning pipeline</p>

<div style="display:flex;flex-wrap:wrap;margin:0 12px">
  <div class="metric"><div class="val">{cumulative[-1]}</div><div class="lbl">Total Onboarded (30d)</div></div>
  <div class="metric"><div class="val">{done_count}/{len(stages)}</div><div class="lbl">Pipeline Stages Done</div></div>
  <div class="metric"><div class="val">{eta_min:.1f}m</div><div class="lbl">ETA to Complete</div></div>
  <div class="metric"><div class="val" style="color:#22c55e">{int(success_rate*100)}%</div><div class="lbl">Onboard Success Rate</div></div>
</div>

<div style="display:flex;flex-wrap:wrap">
  <div class="card" style="flex:2;min-width:300px">
    <h2>Cumulative Onboardings — Last 30 Days</h2>
    <svg width="{chart_w}" height="{chart_h + 20}" style="display:block">
      <polygon points="{fill_points}" fill="#38bdf820"/>
      <polyline points="{c_points}" fill="none" stroke="#38bdf8" stroke-width="2"/>
      <line x1="0" y1="{chart_h}" x2="{chart_w}" y2="{chart_h}" stroke="#334155" stroke-width="1"/>
      <text x="4" y="14" fill="#94a3b8" font-size="10">Count</text>
      <text x="{chart_w//2}" y="{chart_h + 16}" fill="#94a3b8" font-size="10" text-anchor="middle">Day 1 → 30</text>
    </svg>
  </div>
  <div class="card" style="flex:1;min-width:180px;text-align:center">
    <h2>Success Rate</h2>
    <svg width="120" height="120" style="display:block;margin:auto">
      <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#1e293b" stroke-width="12"/>
      <path d="{donut_arc}" fill="none" stroke="#22c55e" stroke-width="12" stroke-linecap="round"/>
      <text x="{cx}" y="{cy + 6}" text-anchor="middle" fill="#e2e8f0" font-size="16" font-weight="700">{int(success_rate*100)}%</text>
    </svg>
  </div>
</div>

<div class="card">
  <h2>Current Onboarding Pipeline (Active Customer)</h2>
  {gantt_rows}
</div>

<div class="card">
  <h2>Active Enterprise Customers</h2>
  <table>
    <tr><th>Organization</th><th>Current Stage</th><th>Progress</th><th>Owner</th></tr>
    {rows}
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Enterprise Onboarding Automator")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/pipeline")
    def pipeline():
        stages = ["Account Provisioning", "IAM Role Setup", "Cluster Deploy", "Model Registry Sync",
                  "Network Policy", "SDK Install", "API Key Issue", "Health Smoke Test"]
        statuses = ["done"] * 5 + ["running", "pending", "pending"]
        return {"stages": [{"name": s, "status": st} for s, st in zip(stages, statuses)],
                "done": 5, "total": len(stages)}

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

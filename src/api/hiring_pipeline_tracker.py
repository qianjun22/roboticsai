"""Hiring Pipeline Tracker — FastAPI port 8791"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8791

def build_html():
    random.seed(7)

    # Candidate pipeline stages
    stages = ["Applied", "Screen", "Technical", "Onsite", "Offer", "Hired"]
    stage_counts = [142, 87, 54, 28, 14, 9]
    colors_stages = ["#64748b", "#38bdf8", "#fbbf24", "#a78bfa", "#34d399", "#C74634"]

    # Funnel SVG
    funnel_parts = []
    max_count = stage_counts[0]
    for i, (stage, count, color) in enumerate(zip(stages, stage_counts, colors_stages)):
        bar_w = int(count / max_count * 440)
        x_off = (440 - bar_w) // 2 + 10
        y = i * 32
        pct = count / max_count * 100
        funnel_parts.append(
            f'<rect x="{x_off}" y="{y+2}" width="{bar_w}" height="24" fill="{color}" rx="4" opacity="0.88"/>'
            f'<text x="{x_off + 6}" y="{y+18}" fill="#0f172a" font-size="11" font-weight="bold">{stage}</text>'
            f'<text x="460" y="{y+18}" fill="#e2e8f0" font-size="11">{count} ({pct:.0f}%)  </text>'
        )
    funnel_svg = "\n".join(funnel_parts)

    # Time-to-hire distribution (days) — log-normal like
    bins = list(range(5, 90, 5))
    hire_dist = [int(30 * math.exp(-((b - 35)**2) / (2 * 20**2)) + random.uniform(0, 4)) for b in bins]
    dist_max = max(hire_dist) or 1
    dist_parts = []
    bar_w2 = 16
    for i, (b, h) in enumerate(zip(bins, hire_dist)):
        bar_h = int(h / dist_max * 90)
        x = 20 + i * (bar_w2 + 4)
        y = 100 - bar_h
        dist_parts.append(
            f'<rect x="{x}" y="{y}" width="{bar_w2}" height="{bar_h}" fill="#38bdf8" rx="2" opacity="0.8"/>'
        )
        if i % 3 == 0:
            dist_parts.append(f'<text x="{x+bar_w2//2}" y="115" fill="#64748b" font-size="9" text-anchor="middle">{b}d</text>')
    dist_svg = "\n".join(dist_parts)

    # Role demand radar (6 axes)
    roles = ["Robotics SW", "ML Infra", "Sim Eng", "DevOps", "Research", "PM"]
    demands = [0.92, 0.85, 0.78, 0.60, 0.95, 0.45]
    filled  = [0.70, 0.55, 0.50, 0.58, 0.40, 0.44]
    cx, cy, r = 130, 130, 100
    n = len(roles)
    def radar_pts(vals, radius=100):
        pts = []
        for i, v in enumerate(vals):
            angle = math.pi / 2 - 2 * math.pi * i / n
            px = cx + radius * v * math.cos(angle)
            py = cy - radius * v * math.sin(angle)
            pts.append(f"{px:.1f},{py:.1f}")
        return " ".join(pts)

    # Radar grid
    radar_grid = []
    for level in [0.25, 0.5, 0.75, 1.0]:
        pts = []
        for i in range(n):
            angle = math.pi / 2 - 2 * math.pi * i / n
            px = cx + r * level * math.cos(angle)
            py = cy - r * level * math.sin(angle)
            pts.append(f"{px:.1f},{py:.1f}")
        radar_grid.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="#334155" stroke-width="0.8"/>')
    # Axis lines
    for i, role in enumerate(roles):
        angle = math.pi / 2 - 2 * math.pi * i / n
        px = cx + r * math.cos(angle)
        py = cy - r * math.sin(angle)
        lx = cx + (r + 22) * math.cos(angle)
        ly = cy - (r + 22) * math.sin(angle)
        radar_grid.append(f'<line x1="{cx}" y1="{cy}" x2="{px:.1f}" y2="{py:.1f}" stroke="#334155" stroke-width="0.8"/>')
        radar_grid.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{role}</text>')

    demand_pts = radar_pts(demands)
    filled_pts = radar_pts(filled)
    radar_svg_full = "\n".join(radar_grid)

    # Recruiter load scatter (recruiter ID vs open reqs)
    scatter_pts_svg = []
    for i in range(12):
        open_reqs = random.randint(3, 18)
        days_avg  = 20 + open_reqs * 2.5 + random.gauss(0, 5)
        sx = 40 + open_reqs * 26
        sy = 130 - max(0, min(130, int((days_avg - 20) / 30 * 100)))
        scatter_pts_svg.append(
            f'<circle cx="{sx}" cy="{sy}" r="5" fill="#fbbf24" opacity="0.8"/>'
            f'<title>Recruiter {i+1}: {open_reqs} reqs, {days_avg:.0f}d avg</title>'
        )
    scatter_svg = "\n".join(scatter_pts_svg)

    # Offer acceptance trend (weekly, 12 weeks)
    accept_rates = [0.55 + 0.3 * math.sin(w * 0.7) + random.gauss(0, 0.05) for w in range(12)]
    accept_rates = [max(0.3, min(0.95, v)) for v in accept_rates]
    accept_pts = " ".join(
        f"{20 + i*42:.1f},{120 - accept_rates[i]*100:.1f}" for i in range(12)
    )

    avg_tte = sum(b * h for b, h in zip(bins, hire_dist)) / max(sum(hire_dist), 1)
    offer_accept = sum(accept_rates) / len(accept_rates)
    pipeline_velocity = stage_counts[-1] / max(stage_counts[0], 1) * 100

    return f"""<!DOCTYPE html><html><head><title>Hiring Pipeline Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 0;margin:0;font-size:1.6rem}}
.subtitle{{color:#64748b;padding:4px 20px 16px;font-size:0.85rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 16px 16px}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;padding:0 16px}}
.card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
.card h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
.stat-val{{font-size:2rem;font-weight:700;color:#C74634}}
.stat-label{{color:#64748b;font-size:0.8rem;margin-top:4px}}
.badge{{display:inline-block;padding:3px 10px;border-radius:99px;font-size:0.75rem;background:#1e3a5f;color:#38bdf8;margin:2px}}
svg{{overflow:visible}}
</style></head>
<body>
<h1>Hiring Pipeline Tracker</h1>
<div class="subtitle">OCI Robot Cloud · Talent Acquisition Dashboard · Port {PORT}</div>

<div class="grid3">
  <div class="card">
    <h2>Pipeline Conversion</h2>
    <div class="stat-val">{pipeline_velocity:.1f}%</div>
    <div class="stat-label">applied → hired</div>
    <div style="margin-top:8px"><span class="badge">{stage_counts[0]} applied</span> <span class="badge">{stage_counts[-1]} hired</span></div>
  </div>
  <div class="card">
    <h2>Avg Time to Hire</h2>
    <div class="stat-val">{avg_tte:.0f}d</div>
    <div class="stat-label">calendar days</div>
    <div style="margin-top:8px"><span class="badge">target: 35d</span> <span class="badge">{'ON TRACK' if avg_tte <= 38 else 'OVER'}</span></div>
  </div>
  <div class="card">
    <h2>Offer Acceptance Rate</h2>
    <div class="stat-val">{offer_accept*100:.0f}%</div>
    <div class="stat-label">12-week rolling avg</div>
    <div style="margin-top:8px"><span class="badge">{'HEALTHY' if offer_accept >= 0.65 else 'LOW'}</span> <span class="badge">target: 70%</span></div>
  </div>
</div>

<div class="grid" style="margin-top:16px">
  <div class="card">
    <h2>Hiring Funnel</h2>
    <svg width="100%" viewBox="0 0 530 210" preserveAspectRatio="xMidYMid meet">
      {funnel_svg}
    </svg>
  </div>

  <div class="card">
    <h2>Role Demand vs Filled (Radar)</h2>
    <svg width="100%" viewBox="0 0 260 260" preserveAspectRatio="xMidYMid meet">
      {radar_svg_full}
      <polygon points="{demand_pts}" fill="#C74634" fill-opacity="0.25" stroke="#C74634" stroke-width="2"/>
      <polygon points="{filled_pts}" fill="#34d399" fill-opacity="0.2"  stroke="#34d399" stroke-width="2"/>
      <!-- Legend -->
      <rect x="5" y="248" width="12" height="6" fill="#C74634" opacity="0.8"/>
      <text x="20" y="256" fill="#e2e8f0" font-size="10">Demand</text>
      <rect x="80" y="248" width="12" height="6" fill="#34d399" opacity="0.8"/>
      <text x="95" y="256" fill="#e2e8f0" font-size="10">Filled</text>
    </svg>
  </div>
</div>

<div class="grid">
  <div class="card">
    <h2>Time-to-Hire Distribution</h2>
    <svg width="100%" viewBox="0 0 500 125" preserveAspectRatio="xMidYMid meet">
      <line x1="15" y1="100" x2="485" y2="100" stroke="#334155" stroke-width="1"/>
      <line x1="15" y1="10"  x2="15"  y2="100" stroke="#334155" stroke-width="1"/>
      {dist_svg}
      <text x="250" y="125" fill="#64748b" font-size="10" text-anchor="middle">Days to Hire</text>
    </svg>
  </div>

  <div class="card">
    <h2>Recruiter Load vs Avg Cycle Time</h2>
    <svg width="100%" viewBox="0 0 500 145" preserveAspectRatio="xMidYMid meet">
      <!-- Axis -->
      <line x1="30" y1="5"   x2="30"  y2="135" stroke="#334155" stroke-width="1"/>
      <line x1="30" y1="135" x2="490" y2="135" stroke="#334155" stroke-width="1"/>
      <!-- Grid -->
      <line x1="30" y1="35"  x2="490" y2="35"  stroke="#334155" stroke-width="0.5" stroke-dasharray="4,4"/>
      <line x1="30" y1="68"  x2="490" y2="68"  stroke="#334155" stroke-width="0.5" stroke-dasharray="4,4"/>
      <line x1="30" y1="101" x2="490" y2="101" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,4"/>
      {scatter_svg}
      <!-- Axis labels -->
      <text x="260" y="145" fill="#64748b" font-size="10" text-anchor="middle">Open Reqs per Recruiter</text>
      <text x="10"  y="70"  fill="#64748b" font-size="10" transform="rotate(-90,10,70)">Avg Cycle (d)</text>
      <!-- Trend line rough -->
      <line x1="66" y1="120" x2="490" y2="28" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.6"/>
    </svg>
  </div>
</div>

<div class="grid" style="margin-bottom:16px">
  <div class="card">
    <h2>Weekly Offer Acceptance Trend</h2>
    <svg width="100%" viewBox="0 0 500 135" preserveAspectRatio="xMidYMid meet">
      <line x1="15" y1="5"   x2="15"  y2="125" stroke="#334155" stroke-width="1"/>
      <line x1="15" y1="125" x2="490" y2="125" stroke="#334155" stroke-width="1"/>
      <!-- 70% target line -->
      <line x1="15" y1="55" x2="490" y2="55" stroke="#34d399" stroke-width="1" stroke-dasharray="5,3" opacity="0.6"/>
      <text x="492" y="58" fill="#34d399" font-size="9">70%</text>
      <polyline points="{accept_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
      <!-- Dots -->
      {''.join(f'<circle cx="{20 + i*42:.1f}" cy="{120 - accept_rates[i]*100:.1f}" r="4" fill="#38bdf8"/>' for i in range(12))}
      <text x="255" y="135" fill="#64748b" font-size="10" text-anchor="middle">Week (last 12)</text>
    </svg>
  </div>

  <div class="card">
    <h2>Pipeline Health Summary</h2>
    <table style="width:100%;border-collapse:collapse;font-size:0.85rem">
      <tr style="color:#64748b"><td>Metric</td><td style="text-align:right">Value</td><td style="text-align:right">Status</td></tr>
      <tr style="border-top:1px solid #334155"><td>Total in pipeline</td><td style="text-align:right">{sum(stage_counts)}</td><td style="text-align:right;color:#38bdf8">INFO</td></tr>
      <tr style="border-top:1px solid #334155"><td>Screen pass-rate</td><td style="text-align:right">{stage_counts[1]/stage_counts[0]*100:.0f}%</td><td style="text-align:right;color:#34d399">OK</td></tr>
      <tr style="border-top:1px solid #334155"><td>Tech pass-rate</td><td style="text-align:right">{stage_counts[2]/stage_counts[1]*100:.0f}%</td><td style="text-align:right;color:#{'fbbf24' if stage_counts[2]/stage_counts[1] < 0.7 else '34d399'}">{'WATCH' if stage_counts[2]/stage_counts[1] < 0.7 else 'OK'}</td></tr>
      <tr style="border-top:1px solid #334155"><td>Onsite pass-rate</td><td style="text-align:right">{stage_counts[3]/stage_counts[2]*100:.0f}%</td><td style="text-align:right;color:#34d399">OK</td></tr>
      <tr style="border-top:1px solid #334155"><td>Offer rate</td><td style="text-align:right">{stage_counts[4]/stage_counts[3]*100:.0f}%</td><td style="text-align:right;color:#fbbf24">WATCH</td></tr>
      <tr style="border-top:1px solid #334155"><td>Overall conversion</td><td style="text-align:right">{pipeline_velocity:.1f}%</td><td style="text-align:right;color:#C74634">LIVE</td></tr>
    </table>
  </div>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Hiring Pipeline Tracker")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT, "service": "hiring_pipeline_tracker"}

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

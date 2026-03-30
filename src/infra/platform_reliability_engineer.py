"""Platform Reliability Engineer — FastAPI port 8795"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8795

def build_html():
    random.seed(7)
    T = 72  # 72 hours of data

    # === SLO / Error Budget ===
    slo_target = 99.9  # percent
    # Simulate uptime with occasional dips
    uptime_series = []
    for i in range(T):
        base = 99.95
        dip = 0.0
        # Incidents at hours 12, 38, 61
        for inc_h in [12, 38, 61]:
            dist = abs(i - inc_h)
            if dist <= 2:
                dip += (2 - dist) * random.uniform(0.15, 0.4)
        uptime_series.append(max(97.0, base - dip + random.gauss(0, 0.04)))
    avg_uptime = sum(uptime_series) / len(uptime_series)
    error_budget_used = max(0, (slo_target - avg_uptime) / (100 - slo_target) * 100)
    error_budget_remaining = max(0, 100 - error_budget_used)

    # === Latency Percentiles over 72h ===
    p50 = [max(20, 42 + 8*math.sin(i*0.4) + random.gauss(0, 2)) for i in range(T)]
    p95 = [max(80, 140 + 30*math.sin(i*0.3) + random.gauss(0, 8)) for i in range(T)]
    p99 = [max(200, 380 + 80*math.sin(i*0.25) + random.gauss(0, 20)) for i in range(T)]

    # === Error Rate ===
    error_rate = [max(0, 0.08 + 0.05*math.sin(i*0.5) + random.gauss(0, 0.02)) for i in range(T)]
    # Spike at incidents
    for inc_h in [12, 38, 61]:
        for delta in range(-1, 3):
            idx = inc_h + delta
            if 0 <= idx < T:
                error_rate[idx] = min(5.0, error_rate[idx] + random.uniform(0.8, 2.5))
    avg_error = sum(error_rate) / len(error_rate)

    # === Throughput (RPS) ===
    rps = [max(0, 420 + 180*math.sin(i*math.pi/12) + random.gauss(0, 15)) for i in range(T)]
    peak_rps = max(rps)

    # === SVG: Uptime chart ===
    W, H = 580, 100
    def scale_x(i): return 20 + i * (W - 40) / (T - 1)
    def scale_y(v, vmin, vmax, hmin, hmax): return hmax - (v - vmin) / (vmax - vmin) * (hmax - hmin)

    uptime_path = "M" + " L".join(
        f"{scale_x(i):.1f},{scale_y(uptime_series[i], 97, 100.05, 10, 90):.1f}"
        for i in range(T)
    )
    # SLO line
    slo_y = scale_y(slo_target, 97, 100.05, 10, 90)

    # === SVG: Latency chart ===
    lat_path_p50 = "M" + " L".join(
        f"{scale_x(i):.1f},{scale_y(p50[i], 0, 500, 10, 90):.1f}" for i in range(T)
    )
    lat_path_p95 = "M" + " L".join(
        f"{scale_x(i):.1f},{scale_y(p95[i], 0, 500, 10, 90):.1f}" for i in range(T)
    )
    lat_path_p99 = "M" + " L".join(
        f"{scale_x(i):.1f},{scale_y(p99[i], 0, 500, 10, 90):.1f}" for i in range(T)
    )

    # === SVG: Error rate bars ===
    bar_w = (W - 40) / T
    err_bars = ""
    for i, e in enumerate(error_rate):
        color = "#ef4444" if e > 1.0 else ("#f59e0b" if e > 0.3 else "#22c55e")
        h = min(80, e / 5.0 * 80)
        err_bars += f'<rect x="{scale_x(i) - bar_w*0.4:.1f}" y="{90-h:.1f}" width="{bar_w*0.8:.1f}" height="{h:.1f}" fill="{color}" opacity="0.85"/>'

    # === SVG: RPS area chart ===
    rps_pts = " ".join(
        f"{scale_x(i):.1f},{scale_y(rps[i], 0, 700, 10, 90):.1f}" for i in range(T)
    )
    rps_area = f"M{scale_x(0):.1f},90 " + " L".join(
        f"{scale_x(i):.1f},{scale_y(rps[i], 0, 700, 10, 90):.1f}" for i in range(T)
    ) + f" L{scale_x(T-1):.1f},90 Z"

    # === Error budget gauge (arc) ===
    gauge_pct = error_budget_remaining / 100
    angle = gauge_pct * math.pi
    gx = 80 + 60 * math.cos(math.pi - angle)
    gy = 60 - 60 * math.sin(math.pi - angle)
    large = 1 if angle > math.pi/2 else 0
    gauge_color = "#22c55e" if gauge_pct > 0.5 else ("#f59e0b" if gauge_pct > 0.2 else "#ef4444")

    # === Incidents table rows ===
    incidents = [
        ("H-60", "Inference pod OOM", "P1", "14m", "Resolved"),
        ("H-34", "GPU driver crash (A100-3)", "P2", "8m", "Resolved"),
        ("H-11", "Network partition (zone-b)", "P1", "22m", "Resolved"),
    ]
    inc_rows = ""
    for ts, desc, sev, dur, status in incidents:
        sev_color = "tag-red" if sev == "P1" else "tag-yellow"
        inc_rows += f"""<tr>
          <td style="color:#94a3b8">{ts}</td>
          <td>{desc}</td>
          <td><span class="tag {sev_color}">{sev}</span></td>
          <td style="color:#38bdf8">{dur}</td>
          <td><span class="tag tag-green">{status}</span></td>
        </tr>"""

    # === Service health rows ===
    services = [
        ("GR00T Inference", "8001", "99.97%", "227ms", "green"),
        ("Fine-tune API", "8080", "99.91%", "341ms", "green"),
        ("Data Collection", "8003", "99.88%", "189ms", "yellow"),
        ("Model Registry", "8021", "100.00%", "54ms", "green"),
        ("SDG Pipeline", "8041", "99.76%", "612ms", "yellow"),
        ("Closed-Loop Eval", "8060", "99.94%", "298ms", "green"),
    ]
    svc_rows = ""
    for name, port, up, lat, st in services:
        dot_color = "#22c55e" if st == "green" else "#f59e0b"
        svc_rows += f"""<tr>
          <td><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{dot_color};margin-right:6px"></span>{name}</td>
          <td style="color:#94a3b8">{port}</td>
          <td style="color:#38bdf8">{up}</td>
          <td>{lat}</td>
        </tr>"""

    return f"""<!DOCTYPE html><html><head><title>Platform Reliability Engineer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 4px;margin:0;font-size:1.6rem}}
.subtitle{{color:#94a3b8;padding:0 20px 16px;font-size:0.9rem}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;padding:0 16px 16px}}
.card{{background:#1e293b;padding:16px;border-radius:10px;border:1px solid #334155}}
.full{{grid-column:1/-1}}
.half{{grid-column:span 2}}
.metric{{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid #334155}}
.metric:last-child{{border-bottom:none}}
.val{{font-size:1.3rem;font-weight:700;color:#38bdf8}}
.label{{color:#94a3b8;font-size:0.82rem}}
.tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:600}}
.tag-green{{background:#14532d;color:#86efac}}
.tag-yellow{{background:#451a03;color:#fcd34d}}
.tag-red{{background:#450a0a;color:#fca5a5}}
table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
th{{color:#94a3b8;font-weight:500;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
svg text{{font-family:system-ui}}
.big-num{{font-size:2rem;font-weight:800;color:#22c55e}}
.warn{{color:#f59e0b}}
</style></head>
<body>
<h1>Platform Reliability Engineer</h1>
<div class="subtitle">Port {PORT} · OCI Robot Cloud SRE Dashboard — 72h rolling window</div>
<div class="grid">

  <!-- KPI cards -->
  <div class="card">
    <h2>Availability</h2>
    <div style="text-align:center;padding:8px 0">
      <div class="big-num {'warn' if avg_uptime < slo_target else ''}">{avg_uptime:.3f}%</div>
      <div style="color:#94a3b8;font-size:0.8rem">SLO target: {slo_target}%</div>
    </div>
    <div class="metric"><span class="label">Error Budget Used</span><span class="val {'warn' if error_budget_used > 50 else ''}">{error_budget_used:.1f}%</span></div>
    <div class="metric"><span class="label">Budget Remaining</span><span class="val">{error_budget_remaining:.1f}%</span></div>
  </div>

  <div class="card">
    <h2>Error Budget Gauge</h2>
    <svg width="100%" viewBox="0 0 160 80" style="background:#0f172a;border-radius:6px">
      <!-- Background arc -->
      <path d="M20,70 A60,60 0 0,1 140,70" stroke="#334155" stroke-width="14" fill="none" stroke-linecap="round"/>
      <!-- Filled arc -->
      <path d="M20,70 A60,60 0 {large},1 {gx:.1f},{gy:.1f}" stroke="{gauge_color}" stroke-width="14" fill="none" stroke-linecap="round"/>
      <text x="80" y="58" fill="{gauge_color}" font-size="18" font-weight="700" text-anchor="middle">{error_budget_remaining:.0f}%</text>
      <text x="80" y="74" fill="#94a3b8" font-size="9" text-anchor="middle">remaining</text>
      <text x="20" y="78" fill="#94a3b8" font-size="8" text-anchor="middle">0%</text>
      <text x="140" y="78" fill="#94a3b8" font-size="8" text-anchor="middle">100%</text>
    </svg>
  </div>

  <div class="card">
    <h2>Throughput</h2>
    <div style="text-align:center;padding:8px 0">
      <div class="big-num">{rps[T-1]:.0f}</div>
      <div style="color:#94a3b8;font-size:0.8rem">current RPS</div>
    </div>
    <div class="metric"><span class="label">Peak RPS (72h)</span><span class="val">{peak_rps:.0f}</span></div>
    <div class="metric"><span class="label">Avg Error Rate</span><span class="val {'warn' if avg_error > 0.3 else ''}">{avg_error:.3f}%</span></div>
  </div>

  <!-- Uptime chart -->
  <div class="card full">
    <h2>Uptime % — 72h (SLO: {slo_target}%)</h2>
    <svg width="100%" viewBox="0 0 580 110" style="background:#0f172a;border-radius:6px">
      <!-- Grid -->
      {''.join(f'<line x1="{scale_x(i):.0f}" y1="10" x2="{scale_x(i):.0f}" y2="90" stroke="#1e293b" stroke-width="1"/>' for i in range(0, T, 6))}
      <line x1="20" y1="{slo_y:.1f}" x2="560" y2="{slo_y:.1f}" stroke="#ef4444" stroke-width="1" stroke-dasharray="6,3" opacity="0.7"/>
      <text x="563" y="{slo_y+4:.1f}" fill="#ef4444" font-size="9">SLO</text>
      <!-- Uptime line -->
      <path d="{uptime_path}" stroke="#22c55e" stroke-width="2" fill="none"/>
      <!-- Axes -->
      <line x1="20" y1="10" x2="20" y2="90" stroke="#475569" stroke-width="1"/>
      <line x1="20" y1="90" x2="560" y2="90" stroke="#475569" stroke-width="1"/>
      <text x="4" y="14" fill="#94a3b8" font-size="9">100</text>
      <text x="4" y="90" fill="#94a3b8" font-size="9">97</text>
      <text x="20" y="105" fill="#94a3b8" font-size="9">H-72</text>
      <text x="275" y="105" fill="#94a3b8" font-size="9" text-anchor="middle">H-36</text>
      <text x="555" y="105" fill="#94a3b8" font-size="9">Now</text>
    </svg>
  </div>

  <!-- Latency chart -->
  <div class="card half">
    <h2>Latency Percentiles (ms)</h2>
    <svg width="100%" viewBox="0 0 580 110" style="background:#0f172a;border-radius:6px">
      {''.join(f'<line x1="{scale_x(i):.0f}" y1="10" x2="{scale_x(i):.0f}" y2="90" stroke="#1e293b" stroke-width="1"/>' for i in range(0, T, 6))}
      <path d="{lat_path_p50}" stroke="#22c55e" stroke-width="1.5" fill="none"/>
      <path d="{lat_path_p95}" stroke="#f59e0b" stroke-width="1.5" fill="none"/>
      <path d="{lat_path_p99}" stroke="#ef4444" stroke-width="1.5" fill="none"/>
      <line x1="20" y1="10" x2="20" y2="90" stroke="#475569" stroke-width="1"/>
      <line x1="20" y1="90" x2="560" y2="90" stroke="#475569" stroke-width="1"/>
      <text x="4" y="14" fill="#94a3b8" font-size="9">500</text>
      <text x="4" y="90" fill="#94a3b8" font-size="9">0</text>
      <text x="20" y="105" fill="#94a3b8" font-size="9">H-72</text>
      <text x="555" y="105" fill="#94a3b8" font-size="9">Now</text>
      <!-- Legend -->
      <rect x="390" y="14" width="160" height="48" fill="#1e293b" rx="4" opacity="0.9"/>
      <line x1="398" y1="26" x2="414" y2="26" stroke="#22c55e" stroke-width="2"/>
      <text x="418" y="30" fill="#e2e8f0" font-size="10">p50 ({p50[-1]:.0f}ms)</text>
      <line x1="398" y1="40" x2="414" y2="40" stroke="#f59e0b" stroke-width="2"/>
      <text x="418" y="44" fill="#e2e8f0" font-size="10">p95 ({p95[-1]:.0f}ms)</text>
      <line x1="398" y1="54" x2="414" y2="54" stroke="#ef4444" stroke-width="2"/>
      <text x="418" y="58" fill="#e2e8f0" font-size="10">p99 ({p99[-1]:.0f}ms)</text>
    </svg>
  </div>

  <!-- Error rate -->
  <div class="card">
    <h2>Error Rate % (72h)</h2>
    <svg width="100%" viewBox="0 0 580 110" style="background:#0f172a;border-radius:6px">
      {err_bars}
      <line x1="20" y1="10" x2="20" y2="90" stroke="#475569" stroke-width="1"/>
      <line x1="20" y1="90" x2="560" y2="90" stroke="#475569" stroke-width="1"/>
      <text x="4" y="14" fill="#94a3b8" font-size="9">5%</text>
      <text x="4" y="90" fill="#94a3b8" font-size="9">0%</text>
      <text x="20" y="105" fill="#94a3b8" font-size="9">H-72</text>
      <text x="555" y="105" fill="#94a3b8" font-size="9">Now</text>
    </svg>
  </div>

  <!-- RPS area -->
  <div class="card full">
    <h2>Request Throughput (RPS)</h2>
    <svg width="100%" viewBox="0 0 580 110" style="background:#0f172a;border-radius:6px">
      {''.join(f'<line x1="{scale_x(i):.0f}" y1="10" x2="{scale_x(i):.0f}" y2="90" stroke="#1e293b" stroke-width="1"/>' for i in range(0, T, 6))}
      <defs><linearGradient id="rpsGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4"/><stop offset="100%" stop-color="#38bdf8" stop-opacity="0.02"/></linearGradient></defs>
      <path d="{rps_area}" fill="url(#rpsGrad)"/>
      <polyline points="{rps_pts}" stroke="#38bdf8" stroke-width="2" fill="none"/>
      <line x1="20" y1="10" x2="20" y2="90" stroke="#475569" stroke-width="1"/>
      <line x1="20" y1="90" x2="560" y2="90" stroke="#475569" stroke-width="1"/>
      <text x="4" y="14" fill="#94a3b8" font-size="9">700</text>
      <text x="4" y="90" fill="#94a3b8" font-size="9">0</text>
      <text x="20" y="105" fill="#94a3b8" font-size="9">H-72</text>
      <text x="275" y="105" fill="#94a3b8" font-size="9" text-anchor="middle">H-36</text>
      <text x="555" y="105" fill="#94a3b8" font-size="9">Now</text>
    </svg>
  </div>

  <!-- Incidents -->
  <div class="card full">
    <h2>Incident Log (72h)</h2>
    <table>
      <thead><tr><th>Time</th><th>Description</th><th>Severity</th><th>Duration</th><th>Status</th></tr></thead>
      <tbody>{inc_rows}</tbody>
    </table>
  </div>

  <!-- Service health -->
  <div class="card full">
    <h2>Service Health</h2>
    <table>
      <thead><tr><th>Service</th><th>Port</th><th>Uptime</th><th>Avg Latency</th></tr></thead>
      <tbody>{svc_rows}</tbody>
    </table>
  </div>

</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Platform Reliability Engineer")
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

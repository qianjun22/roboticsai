"""Enterprise SLA Dashboard — FastAPI port 8769"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8769

def build_html():
    random.seed(7)

    # 24-hour uptime trace (percentage, one point per hour)
    hours = list(range(25))
    uptime = []
    for h in hours:
        base = 99.94
        dip = -2.5 * math.exp(-((h - 14) ** 2) / 4)   # brief incident at hour 14
        noise = random.gauss(0, 0.03)
        uptime.append(max(97.0, min(100.0, base + dip + noise)))

    # Latency percentile traces (p50, p95, p99) over 24h — in ms
    p50  = [210 + 30 * math.sin(math.pi * h / 12) + random.gauss(0, 5)  for h in hours]
    p95  = [320 + 55 * math.sin(math.pi * h / 12) + random.gauss(0, 8)  for h in hours]
    p99  = [480 + 90 * math.sin(math.pi * h / 12) + random.gauss(0, 12) for h in hours]

    # SVG helpers
    def sx(h):  return 60 + h * (720 / 24)
    def sy_up(v, lo=96.5, hi=100.05): return 240 - ((v - lo) / (hi - lo)) * 200
    def sy_lat(v, lo=150, hi=620):    return 240 - ((v - lo) / (hi - lo)) * 200

    up_pts  = " ".join(f"{sx(h):.1f},{sy_up(v):.1f}"  for h, v in zip(hours, uptime))
    p50_pts = " ".join(f"{sx(h):.1f},{sy_lat(v):.1f}" for h, v in zip(hours, p50))
    p95_pts = " ".join(f"{sx(h):.1f},{sy_lat(v):.1f}" for h, v in zip(hours, p95))
    p99_pts = " ".join(f"{sx(h):.1f},{sy_lat(v):.1f}" for h, v in zip(hours, p99))

    # Throughput sparkline (requests/sec, sine wave)
    tput = [round(180 + 95 * math.sin(math.pi * h / 12) + random.gauss(0, 8)) for h in hours]
    def sy_tp(v, lo=50, hi=320): return 80 - ((v - lo) / (hi - lo)) * 70
    tput_pts = " ".join(f"{sx(h):.1f},{sy_tp(v):.1f}" for h, v in zip(hours, tput))

    # Error rate per hour (small, spike at hour 14)
    err_rate = [max(0, 0.06 + 1.8 * math.exp(-((h - 14) ** 2) / 3) + random.uniform(0, 0.04)) for h in hours]
    err_bar_html = ""
    for h, e in zip(hours[:-1], err_rate[:-1]):
        bar_h = max(2, e * 80)
        color = "#ef4444" if e > 0.5 else "#f59e0b" if e > 0.15 else "#4ade80"
        err_bar_html += f'<rect x="{sx(h)+2:.1f}" y="{80 - bar_h:.1f}" width="26" height="{bar_h:.1f}" fill="{color}" rx="2"/>'

    # Per-region uptime table
    regions = [
        ("us-ashburn-1",   99.97, 218, 4),
        ("us-phoenix-1",   99.95, 225, 6),
        ("eu-frankfurt-1", 99.93, 245, 7),
        ("ap-tokyo-1",     99.91, 265, 9),
        ("ap-sydney-1",    99.96, 230, 5),
    ]
    region_rows = ""
    for reg, up, lat, errs in regions:
        badge_color = "#166534" if up >= 99.95 else "#854d0e"
        badge_text = "NOMINAL" if up >= 99.95 else "DEGRADED"
        region_rows += f"""
        <tr style="border-bottom:1px solid #334155">
          <td style="padding:10px 12px;color:#e2e8f0">{reg}</td>
          <td style="padding:10px 12px;color:#4ade80;text-align:center">{up:.2f}%</td>
          <td style="padding:10px 12px;color:#38bdf8;text-align:center">{lat} ms</td>
          <td style="padding:10px 12px;text-align:center">{errs}</td>
          <td style="padding:10px 12px;text-align:center">
            <span style="background:{badge_color};color:white;border-radius:4px;padding:2px 8px;font-size:11px">{badge_text}</span>
          </td>
        </tr>"""

    # Summary stats
    avg_uptime = sum(uptime) / len(uptime)
    avg_p50    = sum(p50) / len(p50)
    avg_p99    = sum(p99) / len(p99)
    total_reqs = sum(tput) * 3600  # approx total requests
    sla_target = 99.90
    sla_met    = "YES" if avg_uptime >= sla_target else "NO"
    sla_color  = "#4ade80" if sla_met == "YES" else "#ef4444"

    return f"""<!DOCTYPE html><html><head><title>Enterprise SLA Dashboard</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:20px 24px 4px;font-size:1.5rem}}
.subtitle{{color:#94a3b8;margin:0 24px 20px;font-size:0.85rem}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 20px 20px}}
.card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
.card.wide{{grid-column:span 2}}
.stat-row{{display:flex;gap:16px;padding:0 20px 16px}}
.stat{{background:#1e293b;border-radius:8px;padding:16px 24px;flex:1;border:1px solid #334155}}
.stat .val{{font-size:1.8rem;font-weight:700;color:#C74634}}
.stat .lbl{{font-size:0.75rem;color:#94a3b8;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{padding:8px 12px;text-align:left;color:#94a3b8;font-size:12px;border-bottom:1px solid #475569}}
</style></head>
<body>
<h1>Enterprise SLA Dashboard</h1>
<div class="subtitle">OCI Robot Cloud — Multi-region inference service — port {PORT}</div>

<div class="stat-row">
  <div class="stat"><div class="val">{avg_uptime:.3f}%</div><div class="lbl">24h Avg Uptime</div></div>
  <div class="stat"><div class="val">{avg_p50:.0f} ms</div><div class="lbl">Median Latency (p50)</div></div>
  <div class="stat"><div class="val">{avg_p99:.0f} ms</div><div class="lbl">Tail Latency (p99)</div></div>
  <div class="stat"><div class="val" style="color:{sla_color}">{sla_met}</div><div class="lbl">SLA {sla_target}% Met</div></div>
  <div class="stat"><div class="val">{total_reqs:,.0f}</div><div class="lbl">Total Requests (24h)</div></div>
</div>

<div class="grid">
  <div class="card">
    <h2>Service Uptime — 24 Hours (%)</h2>
    <svg width="100%" viewBox="0 0 840 280" style="overflow:visible">
      {''.join(f'<line x1="60" y1="{40+i*50}" x2="780" y2="{40+i*50}" stroke="#334155" stroke-width="0.5"/>' for i in range(5))}
      {''.join(f'<line x1="{sx(h):.1f}" y1="40" x2="{sx(h):.1f}" y2="240" stroke="#334155" stroke-width="0.5"/>' for h in range(0,25,6))}
      <line x1="60" y1="40" x2="60" y2="240" stroke="#475569" stroke-width="1"/>
      <line x1="60" y1="240" x2="780" y2="240" stroke="#475569" stroke-width="1"/>
      <!-- SLA threshold line at 99.90 -->
      <line x1="60" y1="{sy_up(99.90):.1f}" x2="780" y2="{sy_up(99.90):.1f}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="5,3"/>
      <text x="785" y="{sy_up(99.90)+4:.1f}" fill="#f59e0b" font-size="10">SLA</text>
      <polyline points="{up_pts}" fill="none" stroke="#4ade80" stroke-width="2"/>
      {''.join(f'<circle cx="{sx(h):.1f}" cy="{sy_up(v):.1f}" r="3" fill="#4ade80"/>' for h, v in zip(hours, uptime))}
      <text x="65" y="265" fill="#94a3b8" font-size="10">00:00</text>
      <text x="{sx(6)-10:.0f}" y="265" fill="#94a3b8" font-size="10">06:00</text>
      <text x="{sx(12)-10:.0f}" y="265" fill="#94a3b8" font-size="10">12:00</text>
      <text x="{sx(18)-10:.0f}" y="265" fill="#94a3b8" font-size="10">18:00</text>
      <text x="{sx(24)-20:.0f}" y="265" fill="#94a3b8" font-size="10">24:00</text>
    </svg>
  </div>

  <div class="card">
    <h2>Latency Percentiles — 24 Hours (ms)</h2>
    <svg width="100%" viewBox="0 0 840 280" style="overflow:visible">
      {''.join(f'<line x1="60" y1="{40+i*50}" x2="780" y2="{40+i*50}" stroke="#334155" stroke-width="0.5"/>' for i in range(5))}
      <line x1="60" y1="40" x2="60" y2="240" stroke="#475569" stroke-width="1"/>
      <line x1="60" y1="240" x2="780" y2="240" stroke="#475569" stroke-width="1"/>
      <polyline points="{p50_pts}" fill="none" stroke="#4ade80" stroke-width="2"/>
      <polyline points="{p95_pts}" fill="none" stroke="#f59e0b" stroke-width="2"/>
      <polyline points="{p99_pts}" fill="none" stroke="#ef4444" stroke-width="2"/>
      <!-- Legend -->
      <line x1="600" y1="28" x2="620" y2="28" stroke="#4ade80" stroke-width="2"/>
      <text x="625" y="32" fill="#e2e8f0" font-size="10">p50</text>
      <line x1="660" y1="28" x2="680" y2="28" stroke="#f59e0b" stroke-width="2"/>
      <text x="685" y="32" fill="#e2e8f0" font-size="10">p95</text>
      <line x1="720" y1="28" x2="740" y2="28" stroke="#ef4444" stroke-width="2"/>
      <text x="745" y="32" fill="#e2e8f0" font-size="10">p99</text>
      <text x="65" y="265" fill="#94a3b8" font-size="10">00:00</text>
      <text x="{sx(12)-10:.0f}" y="265" fill="#94a3b8" font-size="10">12:00</text>
      <text x="{sx(24)-20:.0f}" y="265" fill="#94a3b8" font-size="10">24:00</text>
    </svg>
  </div>

  <div class="card">
    <h2>Error Rate per Hour (%)</h2>
    <svg width="100%" viewBox="0 0 840 100" style="overflow:visible">
      <line x1="60" y1="80" x2="780" y2="80" stroke="#475569" stroke-width="1"/>
      {err_bar_html}
      <text x="65" y="96" fill="#94a3b8" font-size="10">00:00</text>
      <text x="{sx(12)-10:.0f}" y="96" fill="#94a3b8" font-size="10">12:00</text>
      <text x="{sx(24)-20:.0f}" y="96" fill="#94a3b8" font-size="10">24:00</text>
      <text x="785" y="84" fill="#94a3b8" font-size="10">Err%</text>
    </svg>
  </div>

  <div class="card">
    <h2>Request Throughput (req/s)</h2>
    <svg width="100%" viewBox="0 0 840 100" style="overflow:visible">
      <line x1="60" y1="80" x2="780" y2="80" stroke="#475569" stroke-width="1"/>
      <line x1="60" y1="10" x2="60" y2="80" stroke="#475569" stroke-width="1"/>
      <polyline points="{tput_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
      <text x="65" y="96" fill="#94a3b8" font-size="10">00:00</text>
      <text x="{sx(12)-10:.0f}" y="96" fill="#94a3b8" font-size="10">12:00</text>
      <text x="{sx(24)-20:.0f}" y="96" fill="#94a3b8" font-size="10">24:00</text>
    </svg>
  </div>

  <div class="card wide">
    <h2>Per-Region Health</h2>
    <table>
      <thead><tr>
        <th>Region</th><th>Uptime</th><th>Avg Latency</th><th>Errors (24h)</th><th>Status</th>
      </tr></thead>
      <tbody>{region_rows}</tbody>
    </table>
  </div>
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Enterprise SLA Dashboard")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/sla")
    def sla_summary():
        random.seed()
        uptime = round(99.94 + random.gauss(0, 0.02), 4)
        return {
            "port": PORT,
            "uptime_24h_pct": uptime,
            "sla_target_pct": 99.90,
            "sla_met": uptime >= 99.90,
            "p50_ms": round(210 + random.gauss(0, 5), 1),
            "p95_ms": round(320 + random.gauss(0, 8), 1),
            "p99_ms": round(480 + random.gauss(0, 12), 1),
            "regions": ["us-ashburn-1", "us-phoenix-1", "eu-frankfurt-1", "ap-tokyo-1", "ap-sydney-1"],
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

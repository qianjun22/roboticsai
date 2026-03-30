"""OCI Network Monitor — FastAPI service on port 8332.

Monitors OCI network fabric health, inter-region bandwidth, and latency
for Robot Cloud deployments.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

import math
import random
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

REGIONS = ["Ashburn", "Phoenix", "Frankfurt"]

REGION_PAIRS = [
    {"pair": "Ashburn↔Phoenix",   "key": "ash_phx", "p50": 62.4,  "p90": 71.2,  "p99": 84.1,  "sla": 80,  "bw_gbps": 1.2,  "prov_gbps": 2.0},
    {"pair": "Ashburn↔Frankfurt",  "key": "ash_fra", "p50": 98.7,  "p90": 109.3, "p99": 121.5, "sla": 100, "bw_gbps": 0.9,  "prov_gbps": 1.5},
    {"pair": "Frankfurt↔Phoenix",  "key": "fra_phx", "p50": 124.0, "p90": 137.8, "p99": 155.2, "sla": 150, "bw_gbps": 0.7,  "prov_gbps": 1.0},
]

PER_REGION = [
    {"region": "Ashburn",   "rx_gbps": 0.82, "tx_gbps": 0.76, "pkt_loss": 0.001, "jitter_ms": 1.2, "status": "healthy"},
    {"region": "Phoenix",   "rx_gbps": 0.61, "tx_gbps": 0.58, "pkt_loss": 0.000, "jitter_ms": 0.9, "status": "healthy"},
    {"region": "Frankfurt", "rx_gbps": 0.74, "tx_gbps": 0.69, "pkt_loss": 0.003, "jitter_ms": 2.1, "status": "degraded"},
]

TOTAL_BW_GBPS = 2.8

# 7-day latency history (daily samples)
def _latency_history():
    """Generate 7-day latency trend data; Frankfurt→Ashburn shows degradation."""
    days = 7
    history = {}
    seed = 42
    rng = random.Random(seed)

    base = {
        "ash_phx": {"p50": 62.4, "p90": 71.2, "p99": 84.1},
        "ash_fra": {"p50": 98.7, "p90": 109.3, "p99": 121.5},
        "fra_phx": {"p50": 124.0, "p90": 137.8, "p99": 155.2},
    }
    # Frankfurt-related pairs show drift: +8.6ms over week
    drift_keys = {"ash_fra": 8.6, "fra_phx": 6.2, "ash_phx": 0.4}

    for key, drift in drift_keys.items():
        series_p50, series_p90, series_p99 = [], [], []
        for d in range(days):
            frac = d / (days - 1)
            p50 = base[key]["p50"] + drift * frac + rng.uniform(-1.5, 1.5)
            p90 = base[key]["p90"] + drift * frac * 1.1 + rng.uniform(-2, 2)
            p99 = base[key]["p99"] + drift * frac * 1.2 + rng.uniform(-2.5, 2.5)
            series_p50.append(round(p50, 1))
            series_p90.append(round(p90, 1))
            series_p99.append(round(p99, 1))
        history[key] = {"p50": series_p50, "p90": series_p90, "p99": series_p99}
    return history

LATENCY_HISTORY = _latency_history()

# SLA breach events index (day, pair_key)
SLA_BREACHES = [
    {"day": 5, "key": "ash_fra", "value": 102.3},
    {"day": 6, "key": "ash_fra", "value": 98.7},
    {"day": 6, "key": "fra_phx", "value": 152.1},
]

# ---------------------------------------------------------------------------
# SVG generation helpers
# ---------------------------------------------------------------------------

def _bw_svg() -> str:
    """SVG 1: Network bandwidth utilization — 3 OCI regions with inter-region pipes."""
    W, H = 640, 340
    bg = "#0f172a"
    oracle_red = "#C74634"
    sky = "#38bdf8"
    green = "#22c55e"
    yellow = "#fbbf24"
    gray = "#64748b"
    white = "#f1f5f9"

    # Region node positions
    nodes = {
        "Ashburn":   (160, 170),
        "Phoenix":   (480, 90),
        "Frankfurt": (480, 260),
    }

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:{bg};border-radius:8px;">')
    lines.append(f'<text x="{W//2}" y="24" fill="{white}" font-size="13" font-family="monospace" text-anchor="middle" font-weight="bold">Inter-Region Bandwidth Utilization</text>')

    # Draw pipe edges
    for pair in REGION_PAIRS:
        r1, r2 = pair["pair"].replace("↔", "|").split("|")
        x1, y1 = nodes[r1]
        x2, y2 = nodes[r2]
        util = pair["bw_gbps"] / pair["prov_gbps"]
        stroke_w = 3 + int(util * 10)  # 3-13px
        color = green if util < 0.6 else (yellow if util < 0.85 else oracle_red)
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{stroke_w}" stroke-opacity="0.8"/>')
        label = f"{pair['bw_gbps']:.1f}/{pair['prov_gbps']:.1f} Gbps"
        util_pct = f"{util*100:.0f}%"
        lines.append(f'<text x="{mx}" y="{my - 8}" fill="{color}" font-size="10" font-family="monospace" text-anchor="middle">{label}</text>')
        lines.append(f'<text x="{mx}" y="{my + 6}" fill="{color}" font-size="10" font-family="monospace" text-anchor="middle">{util_pct}</text>')

    # Draw region nodes
    for region, (x, y) in nodes.items():
        rd = next((r for r in PER_REGION if r["region"] == region), None)
        st_color = green if rd and rd["status"] == "healthy" else oracle_red
        lines.append(f'<circle cx="{x}" cy="{y}" r="36" fill="#1e293b" stroke="{st_color}" stroke-width="2.5"/>')
        lines.append(f'<text x="{x}" y="{y - 4}" fill="{white}" font-size="11" font-family="monospace" text-anchor="middle" font-weight="bold">{region}</text>')
        if rd:
            lines.append(f'<text x="{x}" y="{y + 10}" fill="{sky}" font-size="9" font-family="monospace" text-anchor="middle">RX {rd["rx_gbps"]:.2f}G</text>')
            lines.append(f'<text x="{x}" y="{y + 22}" fill="{sky}" font-size="9" font-family="monospace" text-anchor="middle">TX {rd["tx_gbps"]:.2f}G</text>')
            st_label = rd["status"].upper()
            lines.append(f'<text x="{x}" y="{y + 34}" fill="{st_color}" font-size="9" font-family="monospace" text-anchor="middle">{st_label}</text>')

    # Legend
    lx = 20
    for color, label in [(green, "<60% util"), (yellow, "60-85%"), (oracle_red, ">85%")]:
        lines.append(f'<rect x="{lx}" y="{H-28}" width="12" height="12" fill="{color}"/>')
        lines.append(f'<text x="{lx+15}" y="{H-18}" fill="{gray}" font-size="10" font-family="monospace">{label}</text>')
        lx += 90

    lines.append(f'<text x="{W-10}" y="{H-12}" fill="{gray}" font-size="9" font-family="monospace" text-anchor="end">Total avg: {TOTAL_BW_GBPS} Gbps</text>')
    lines.append('</svg>')
    return '\n'.join(lines)


def _latency_trend_svg() -> str:
    """SVG 2: 7-day network latency trend with SLA breach markers."""
    W, H = 640, 320
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 20, 40, 50
    bg = "#0f172a"
    oracle_red = "#C74634"
    sky = "#38bdf8"
    green = "#22c55e"
    yellow = "#fbbf24"
    gray = "#64748b"
    white = "#f1f5f9"

    days = 7
    CHART_W = W - PAD_L - PAD_R
    CHART_H = H - PAD_T - PAD_B

    # Y range: 50 to 170 ms
    Y_MIN, Y_MAX = 50, 170

    def to_px(val, day_i):
        px_x = PAD_L + (day_i / (days - 1)) * CHART_W
        px_y = PAD_T + (1 - (val - Y_MIN) / (Y_MAX - Y_MIN)) * CHART_H
        return px_x, px_y

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:{bg};border-radius:8px;">')
    lines.append(f'<text x="{W//2}" y="20" fill="{white}" font-size="13" font-family="monospace" text-anchor="middle" font-weight="bold">7-Day Latency Trend (p50/p90/p99)</text>')

    # Grid lines
    for ms in [60, 80, 100, 120, 140, 160]:
        _, gy = to_px(ms, 0)
        lines.append(f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W-PAD_R}" y2="{gy:.1f}" stroke="{gray}" stroke-width="0.5" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{PAD_L-5}" y="{gy+4:.1f}" fill="{gray}" font-size="9" font-family="monospace" text-anchor="end">{ms}</text>')

    # X axis labels (days ago)
    now = datetime.utcnow()
    for d in range(days):
        px_x, _ = to_px(Y_MIN, d)
        day_label = (now - timedelta(days=days - 1 - d)).strftime("%m/%d")
        lines.append(f'<text x="{px_x:.1f}" y="{H-PAD_B+16}" fill="{gray}" font-size="9" font-family="monospace" text-anchor="middle">{day_label}</text>')

    # SLA lines
    sla_lines = [(80, oracle_red, "ASH-PHX SLA"), (100, yellow, "ASH-FRA SLA"), (150, sky, "FRA-PHX SLA")]
    for ms, col, label in sla_lines:
        _, sy = to_px(ms, 0)
        lines.append(f'<line x1="{PAD_L}" y1="{sy:.1f}" x2="{W-PAD_R}" y2="{sy:.1f}" stroke="{col}" stroke-width="1" stroke-dasharray="6,3" stroke-opacity="0.6"/>')
        lines.append(f'<text x="{W-PAD_R-2}" y="{sy-3:.1f}" fill="{col}" font-size="8" font-family="monospace" text-anchor="end">{label}</text>')

    # Draw trend lines per pair
    pair_styles = [
        ("ash_phx", green,       "Ash↔Phx"),
        ("ash_fra", yellow,      "Ash↔Fra"),
        ("fra_phx", sky,         "Fra↔Phx"),
    ]
    percentile_dash = {"p50": "none", "p90": "4,2", "p99": "2,2"}
    percentile_opacity = {"p50": "1", "p90": "0.75", "p99": "0.55"}

    legend_x = PAD_L
    for key, color, label in pair_styles:
        hist = LATENCY_HISTORY[key]
        for pct in ["p50", "p90", "p99"]:
            pts = ["{:.1f},{:.1f}".format(*to_px(hist[pct][d], d)) for d in range(days)]
            dash = percentile_dash[pct]
            op = percentile_opacity[pct]
            lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.8" stroke-dasharray="{dash}" stroke-opacity="{op}"/>')

    # SLA breach markers
    for breach in SLA_BREACHES:
        bx, by = to_px(breach["value"], breach["day"])
        lines.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="5" fill="{oracle_red}" stroke="white" stroke-width="1"/>')
        lines.append(f'<text x="{bx:.1f}" y="{by-8:.1f}" fill="{oracle_red}" font-size="9" font-family="monospace" text-anchor="middle">BREACH</text>')

    # Legend
    lx = PAD_L
    for key, color, label in pair_styles:
        lines.append(f'<rect x="{lx}" y="{H-PAD_B+28}" width="18" height="4" fill="{color}"/>')
        lines.append(f'<text x="{lx+22}" y="{H-PAD_B+34}" fill="{color}" font-size="9" font-family="monospace">{label}</text>')
        lx += 100

    lines.append(f'<text x="{W//2+60}" y="{H-PAD_B+34}" fill="{gray}" font-size="8" font-family="monospace">— p50  -- p90  ·· p99</text>')
    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html() -> str:
    bw_svg = _bw_svg()
    lat_svg = _latency_trend_svg()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    rows = ""
    for pair in REGION_PAIRS:
        util = pair["bw_gbps"] / pair["prov_gbps"]
        margin = pair["sla"] - pair["p50"]
        if margin < 5:
            badge = '<span style="background:#C74634;color:#fff;padding:2px 7px;border-radius:4px;font-size:11px;">BORDERLINE</span>'
        elif margin < 15:
            badge = '<span style="background:#fbbf24;color:#0f172a;padding:2px 7px;border-radius:4px;font-size:11px;">WATCH</span>'
        else:
            badge = '<span style="background:#22c55e;color:#0f172a;padding:2px 7px;border-radius:4px;font-size:11px;">OK</span>'
        rows += f"""
        <tr>
          <td style="color:#f1f5f9;">{pair['pair']}</td>
          <td style="color:#38bdf8;">{pair['p50']} ms</td>
          <td style="color:#94a3b8;">{pair['p90']} ms</td>
          <td style="color:#64748b;">{pair['p99']} ms</td>
          <td style="color:#fbbf24;">{pair['sla']} ms</td>
          <td>{badge}</td>
          <td style="color:#38bdf8;">{pair['bw_gbps']:.1f} / {pair['prov_gbps']:.1f} Gbps ({util*100:.0f}%)</td>
        </tr>"""

    region_rows = ""
    for r in PER_REGION:
        st_color = "#22c55e" if r["status"] == "healthy" else "#C74634"
        region_rows += f"""
        <tr>
          <td style="color:#f1f5f9;">{r['region']}</td>
          <td style="color:#38bdf8;">{r['rx_gbps']:.2f} Gbps</td>
          <td style="color:#38bdf8;">{r['tx_gbps']:.2f} Gbps</td>
          <td style="color:#94a3b8;">{r['pkt_loss']*100:.3f}%</td>
          <td style="color:#fbbf24;">{r['jitter_ms']:.1f} ms</td>
          <td><span style="color:{st_color};font-weight:bold;">{r['status'].upper()}</span></td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OCI Network Monitor — Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Courier New', monospace; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 12px; margin-bottom: 20px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }}
    .card-title {{ color: #38bdf8; font-size: 13px; font-weight: bold; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
    .metric {{ display: flex; justify-content: space-between; margin-bottom: 8px; }}
    .metric-label {{ color: #64748b; font-size: 12px; }}
    .metric-value {{ color: #f1f5f9; font-size: 12px; font-weight: bold; }}
    .alert {{ background: #7f1d1d; border: 1px solid #C74634; border-radius: 6px; padding: 10px 14px; margin-bottom: 16px; color: #fca5a5; font-size: 12px; }}
    .charts {{ display: flex; flex-direction: column; gap: 16px; margin-bottom: 20px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th {{ color: #38bdf8; text-align: left; padding: 6px 10px; border-bottom: 1px solid #334155; }}
    td {{ padding: 6px 10px; border-bottom: 1px solid #1e293b; }}
    .section-title {{ color: #C74634; font-size: 14px; font-weight: bold; margin: 20px 0 10px; text-transform: uppercase; }}
    footer {{ color: #334155; font-size: 10px; margin-top: 24px; text-align: center; }}
  </style>
</head>
<body>
  <h1>OCI Network Monitor</h1>
  <div class="subtitle">Robot Cloud — Inter-Region Network Health  |  {ts}</div>

  <div class="alert">DEGRADATION DETECTED: Frankfurt node showing elevated latency trend (+8ms over 7 days). Ashburn↔Frankfurt nearing SLA boundary (98.7ms / 100ms SLA). Recommend failover evaluation.</div>

  <div class="grid">
    <div class="card">
      <div class="card-title">Network Summary</div>
      <div class="metric"><span class="metric-label">Total Inter-Region BW</span><span class="metric-value">2.8 Gbps avg</span></div>
      <div class="metric"><span class="metric-label">Active Region Pairs</span><span class="metric-value">3</span></div>
      <div class="metric"><span class="metric-label">SLA Breaches (7d)</span><span class="metric-value" style="color:#C74634;">2</span></div>
      <div class="metric"><span class="metric-label">Degraded Regions</span><span class="metric-value" style="color:#fbbf24;">1 (Frankfurt)</span></div>
      <div class="metric"><span class="metric-label">Failover Recommend</span><span class="metric-value" style="color:#C74634;">ASH↔FRA → PHX route</span></div>
    </div>
    <div class="card">
      <div class="card-title">SLA Compliance</div>
      <div class="metric"><span class="metric-label">Ashburn↔Phoenix</span><span class="metric-value" style="color:#22c55e;">62.4ms / 80ms (22% margin)</span></div>
      <div class="metric"><span class="metric-label">Ashburn↔Frankfurt</span><span class="metric-value" style="color:#C74634;">98.7ms / 100ms (1.3% margin)</span></div>
      <div class="metric"><span class="metric-label">Frankfurt↔Phoenix</span><span class="metric-value" style="color:#fbbf24;">124ms / 150ms (17% margin)</span></div>
      <div class="metric"><span class="metric-label">Degradation Trend</span><span class="metric-value" style="color:#fbbf24;">FRA: +8.6ms/wk</span></div>
    </div>
  </div>

  <div class="charts">
    {bw_svg}
    {lat_svg}
  </div>

  <div class="section-title">Inter-Region Pair Details</div>
  <table>
    <thead>
      <tr>
        <th>Pair</th><th>p50</th><th>p90</th><th>p99</th><th>SLA</th><th>Status</th><th>Bandwidth</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <div class="section-title">Per-Region Node Health</div>
  <table>
    <thead>
      <tr>
        <th>Region</th><th>RX</th><th>TX</th><th>Pkt Loss</th><th>Jitter</th><th>Status</th>
      </tr>
    </thead>
    <tbody>{region_rows}</tbody>
  </table>

  <footer>OCI Robot Cloud — Network Monitor v1.0 | Port 8332 | &copy; 2026 Oracle</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(title="OCI Network Monitor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "oci_network_monitor", "port": 8332}

    @app.get("/metrics")
    async def metrics():
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_bw_gbps": TOTAL_BW_GBPS,
            "region_pairs": REGION_PAIRS,
            "per_region": PER_REGION,
            "sla_breaches_7d": len(SLA_BREACHES),
            "failover_recommendation": "Route ASH↔FRA traffic via PHX if latency exceeds 100ms",
        }

    @app.get("/latency-history")
    async def latency_history():
        return {"days": 7, "history": LATENCY_HISTORY}

else:
    # Fallback stdlib HTTP server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"oci_network_monitor","port":8332}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = _html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8332)
    else:
        print("FastAPI not available — using stdlib http.server on port 8332")
        with socketserver.TCPServer(("", 8332), _Handler) as httpd:
            httpd.serve_forever()

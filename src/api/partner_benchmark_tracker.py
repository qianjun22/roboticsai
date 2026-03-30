"""Partner Benchmark Tracker — FastAPI service on port 8223.

Tracks partner robot performance benchmarks over time to demonstrate OCI value.
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
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

PARTNERS = ["Covariant", "Apptronik", "1X", "Physical Intelligence"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]

# Monthly SR per partner (Jan–Jun 2026)
SR_DATA = {
    "Covariant":             [0.51, 0.56, 0.60, 0.65, 0.68, 0.71],
    "Apptronik":             [0.44, 0.50, 0.55, 0.59, 0.63, 0.66],
    "1X":                    [0.41, 0.49, 0.56, 0.63, 0.68, 0.72],  # +31pp
    "Physical Intelligence": [0.58, 0.63, 0.68, 0.74, 0.78, 0.82],  # highest SR
}

# Latency distribution (p25/p50/p75/p90) in ms
LATENCY_DATA = {
    "Covariant":             {"p25": 188, "p50": 221, "p75": 248, "p90": 274},
    "Apptronik":             {"p25": 195, "p50": 230, "p75": 261, "p90": 289},
    "1X":                    {"p25": 181, "p50": 218, "p75": 242, "p90": 265},
    "Physical Intelligence": {"p25": 176, "p50": 212, "p75": 238, "p90": 256},
}

SLA_TARGET_MS = 300  # SLA line

def _metrics():
    # platform lift = average SR gain Jan→Jun across all partners
    lifts = [SR_DATA[p][-1] - SR_DATA[p][0] for p in PARTNERS]
    avg_lift = sum(lifts) / len(lifts)
    top_partner = max(PARTNERS, key=lambda p: SR_DATA[p][-1])
    fastest_growth = max(PARTNERS, key=lambda p: SR_DATA[p][-1] - SR_DATA[p][0])
    median_lat = sorted([LATENCY_DATA[p]["p50"] for p in PARTNERS])
    median_lat_overall = (median_lat[1] + median_lat[2]) / 2
    return {
        "platform_lift_avg_pp": round(avg_lift * 100, 1),
        "top_sr_partner": top_partner,
        "top_sr_value": SR_DATA[top_partner][-1],
        "fastest_growth_partner": fastest_growth,
        "fastest_growth_pp": round((SR_DATA[fastest_growth][-1] - SR_DATA[fastest_growth][0]) * 100, 1),
        "median_latency_ms": round(median_lat_overall, 0),
        "sla_target_ms": SLA_TARGET_MS,
        "all_partners_below_sla": all(LATENCY_DATA[p]["p90"] < SLA_TARGET_MS for p in PARTNERS),
        "retention_signal": "strong",
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

COLOURS = {
    "Covariant":             "#38bdf8",
    "Apptronik":             "#f59e0b",
    "1X":                    "#34d399",
    "Physical Intelligence": "#C74634",
}

def _build_html():
    metrics = _metrics()

    # --- SVG 1: multi-line SR chart ---
    W, H = 580, 290
    PAD = {"l": 50, "r": 20, "t": 36, "b": 50}
    pw = W - PAD["l"] - PAD["r"]
    ph = H - PAD["t"] - PAD["b"]
    n_months = len(MONTHS)
    sr_min, sr_max = 0.35, 0.90

    def tx(i):  return PAD["l"] + (i / (n_months - 1)) * pw
    def ty(sr): return PAD["t"] + ph - ((sr - sr_min) / (sr_max - sr_min)) * ph

    # gridlines
    grids = ""
    for sr_g in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        yg = ty(sr_g)
        grids += f'<line x1="{PAD["l"]}" y1="{yg:.1f}" x2="{PAD["l"]+pw}" y2="{yg:.1f}" stroke="#1e3a5f" stroke-dasharray="4,3"/>'
        grids += f'<text x="{PAD["l"]-6}" y="{yg+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="11">{sr_g:.1f}</text>'

    # x-axis labels
    x_labels = ""
    for i, m in enumerate(MONTHS):
        xp = tx(i)
        x_labels += f'<text x="{xp:.1f}" y="{PAD["t"]+ph+18}" text-anchor="middle" fill="#94a3b8" font-size="11">{m} 2026</text>'
        x_labels += f'<line x1="{xp:.1f}" y1="{PAD["t"]+ph}" x2="{xp:.1f}" y2="{PAD["t"]+ph+5}" stroke="#475569"/>'

    lines_svg = ""
    dots_svg = ""
    legend_svg = ""
    for pi, partner in enumerate(PARTNERS):
        colour = COLOURS[partner]
        pts = " ".join(f"{tx(i):.1f},{ty(v):.1f}" for i, v in enumerate(SR_DATA[partner]))
        lines_svg += f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="2.2"/>'
        for i, v in enumerate(SR_DATA[partner]):
            dots_svg += f'<circle cx="{tx(i):.1f}" cy="{ty(v):.1f}" r="3.5" fill="{colour}"/>'
        # end label
        last_x = tx(n_months - 1) + 5
        last_y = ty(SR_DATA[partner][-1]) + 4
        dots_svg += f'<text x="{last_x:.1f}" y="{last_y:.1f}" fill="{colour}" font-size="10">{SR_DATA[partner][-1]:.2f}</text>'
        # legend
        lx = PAD["l"] + pi * 135
        legend_svg += f'<rect x="{lx}" y="{PAD["t"]-20}" width="12" height="4" fill="{colour}" rx="1"/>'
        legend_svg += f'<text x="{lx+16}" y="{PAD["t"]-14}" fill="#94a3b8" font-size="10">{partner}</text>'

    svg1 = f"""
    <svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px;background:#0f172a;border-radius:8px">
      <text x="{W//2}" y="16" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">Partner Success Rate — Jan to Jun 2026</text>
      {legend_svg}
      {grids}
      {x_labels}
      {lines_svg}
      {dots_svg}
      <text x="14" y="{H//2}" text-anchor="middle" fill="#64748b" font-size="11" transform="rotate(-90,14,{H//2})">Success Rate</text>
    </svg>"""

    # --- SVG 2: box-plot latency ---
    BW, BH = 580, 270
    BPAD = {"l": 50, "r": 20, "t": 36, "b": 50}
    bpw = BW - BPAD["l"] - BPAD["r"]
    bph = BH - BPAD["t"] - BPAD["b"]
    n_p = len(PARTNERS)
    lat_min, lat_max = 160, 320

    def bx(i):  return BPAD["l"] + (i + 0.5) / n_p * bpw
    def by(ms): return BPAD["t"] + bph - ((ms - lat_min) / (lat_max - lat_min)) * bph

    box_w = bpw / n_p * 0.4

    # y gridlines
    b_grids = ""
    for ms_g in [180, 200, 220, 240, 260, 280, 300]:
        yg = by(ms_g)
        b_grids += f'<line x1="{BPAD["l"]}" y1="{yg:.1f}" x2="{BPAD["l"]+bpw}" y2="{yg:.1f}" stroke="{"#C74634" if ms_g == SLA_TARGET_MS else "#1e3a5f"}" stroke-dasharray="{"none" if ms_g == SLA_TARGET_MS else "4,3"}" stroke-width="{1.8 if ms_g == SLA_TARGET_MS else 1}"/>'
        label = f"{ms_g}ms" + (" ← SLA" if ms_g == SLA_TARGET_MS else "")
        b_grids += f'<text x="{BPAD["l"]-6}" y="{yg+4:.1f}" text-anchor="end" fill="{"#C74634" if ms_g == SLA_TARGET_MS else "#94a3b8"}" font-size="10">{label}</text>'

    boxes_svg = ""
    for i, partner in enumerate(PARTNERS):
        ld = LATENCY_DATA[partner]
        colour = COLOURS[partner]
        cx = bx(i)
        y25, y50, y75, y90 = by(ld["p25"]), by(ld["p50"]), by(ld["p75"]), by(ld["p90"])
        # whisker p25→p90
        boxes_svg += f'<line x1="{cx:.1f}" y1="{y25:.1f}" x2="{cx:.1f}" y2="{y90:.1f}" stroke="{colour}" stroke-width="1.5"/>'
        # box p25→p75
        boxes_svg += f'<rect x="{cx-box_w/2:.1f}" y="{y75:.1f}" width="{box_w:.1f}" height="{y25-y75:.1f}" fill="{colour}" opacity="0.3" stroke="{colour}" stroke-width="1.2" rx="2"/>'
        # median line
        boxes_svg += f'<line x1="{cx-box_w/2:.1f}" y1="{y50:.1f}" x2="{cx+box_w/2:.1f}" y2="{y50:.1f}" stroke="{colour}" stroke-width="2.5"/>'
        # p90 cap
        boxes_svg += f'<line x1="{cx-box_w/4:.1f}" y1="{y90:.1f}" x2="{cx+box_w/4:.1f}" y2="{y90:.1f}" stroke="{colour}" stroke-width="1.5"/>'
        # p50 label
        boxes_svg += f'<text x="{cx:.1f}" y="{y50-5:.1f}" text-anchor="middle" fill="{colour}" font-size="10" font-weight="bold">{ld["p50"]}ms</text>'
        # x label
        short = partner.split()[0]
        boxes_svg += f'<text x="{cx:.1f}" y="{BPAD["t"]+bph+18}" text-anchor="middle" fill="#94a3b8" font-size="11">{short}</text>'

    svg2 = f"""
    <svg viewBox="0 0 {BW} {BH}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{BW}px;background:#0f172a;border-radius:8px">
      <text x="{BW//2}" y="22" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">Inference Latency Distribution per Partner (p25/p50/p75/p90)</text>
      {b_grids}
      {boxes_svg}
      <text x="14" y="{BH//2}" text-anchor="middle" fill="#64748b" font-size="11" transform="rotate(-90,14,{BH//2})">Latency (ms)</text>
    </svg>"""

    def card(label, value, sub=""):
        sub_html = f'<div style="color:#64748b;font-size:12px;margin-top:4px">{sub}</div>' if sub else ""
        return f"""
        <div style="background:#1e293b;border-radius:8px;padding:16px 20px;min-width:160px;flex:1">
          <div style="color:#94a3b8;font-size:12px;margin-bottom:6px">{label}</div>
          <div style="color:#38bdf8;font-size:22px;font-weight:bold">{value}</div>
          {sub_html}
        </div>"""

    cards = "".join([
        card("Platform Lift (avg)", f"+{metrics['platform_lift_avg_pp']}pp", "Jan→Jun across all partners"),
        card("Top SR Partner",      metrics["top_sr_partner"], f"SR={metrics['top_sr_value']:.2f}"),
        card("Fastest Growth",      metrics["fastest_growth_partner"], f"+{metrics['fastest_growth_pp']}pp since Jan"),
        card("Median Latency",      f"{int(metrics['median_latency_ms'])}ms", f"SLA <{SLA_TARGET_MS}ms"),
        card("Retention Signal",    metrics["retention_signal"].upper(), "all partners ↑"),
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Partner Benchmark Tracker — Port 8223</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1   {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .sub {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    .cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 28px; }}
    .chart-wrap {{ margin-bottom: 28px; }}
    .chart-title {{ color: #94a3b8; font-size: 13px; margin-bottom: 8px; }}
    footer {{ color: #334155; font-size: 11px; margin-top: 24px; text-align: center; }}
  </style>
</head>
<body>
  <h1>Partner Benchmark Tracker</h1>
  <div class="sub">OCI Robot Cloud · Partner Performance · Port 8223 · Updated {metrics['last_updated']}</div>

  <div class="cards">{cards}</div>

  <div class="chart-wrap">
    <div class="chart-title">Partner Success Rate Progression (Jan–Jun 2026)</div>
    {svg1}
  </div>

  <div class="chart-wrap">
    <div class="chart-title">Inference Latency Distribution — p25/p50/p75/p90 with SLA Target</div>
    {svg2}
  </div>

  <footer>OCI Robot Cloud · cycle-40B · partner_benchmark_tracker.py</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(title="Partner Benchmark Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(_build_html())

    @app.get("/api/metrics")
    async def api_metrics():
        return _metrics()

    @app.get("/api/sr-history")
    async def api_sr_history():
        return {"months": MONTHS, "data": SR_DATA}

    @app.get("/api/latency")
    async def api_latency():
        return {"latency_ms": LATENCY_DATA, "sla_target_ms": SLA_TARGET_MS}

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8223, "service": "partner_benchmark_tracker"}

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            html = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8223)
    else:
        print("FastAPI not available — starting stdlib fallback on port 8223")
        with socketserver.TCPServer(("", 8223), _Handler) as httpd:
            httpd.serve_forever()

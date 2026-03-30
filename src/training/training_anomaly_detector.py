"""
Training Anomaly Detector - Port 8646
OCI Robot Cloud - cycle-147A
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── data ──────────────────────────────────────────────────────────────────────
ANOMALY_EVENTS = [
    {"step": 124, "type": "NaN", "cause": "bad_demo", "resolved": True, "fix": "data filter"},
    {"step": 800, "type": "plateau", "cause": "lr", "resolved": True, "fix": "LR boost"},
    {"step": 2200, "type": "divergence", "cause": "batch", "resolved": True, "fix": "gradient clip"},
    {"step": 3400, "type": "spike", "cause": "data_quality", "resolved": True, "fix": "outlier removal"},
]

ANOMALY_TYPE_COUNTS = {
    "NaN": 3,
    "plateau": 4,
    "spike": 2,
    "slow_conv": 1,
    "oscillation": 2,
}

ROOT_CAUSE_MATRIX = {
    "NaN":        {"lr": 0, "batch": 1, "data_quality": 3, "architecture": 0},
    "plateau":    {"lr": 4, "batch": 1, "data_quality": 0, "architecture": 1},
    "spike":      {"lr": 1, "batch": 0, "data_quality": 2, "architecture": 0},
    "slow_conv":  {"lr": 1, "batch": 0, "data_quality": 0, "architecture": 1},
    "oscillation":{"lr": 2, "batch": 1, "data_quality": 0, "architecture": 0},
}

# ── SVG builders ──────────────────────────────────────────────────────────────

def svg_loss_timeline() -> str:
    W, H = 820, 320
    STEPS = 5000
    PAD = {"l": 70, "r": 30, "t": 40, "b": 60}
    CW = W - PAD["l"] - PAD["r"]
    CH = H - PAD["t"] - PAD["b"]

    def sx(step): return PAD["l"] + step / STEPS * CW
    def sy(loss): return PAD["t"] + CH - loss / 1.4 * CH

    # synthetic loss curve: noisy exponential decay with anomaly bumps
    import math, random
    random.seed(42)
    pts = []
    for s in range(0, 5001, 25):
        base = 0.9 * math.exp(-s / 1800) + 0.08
        noise = random.gauss(0, 0.012)
        # NaN region bump
        if 100 <= s <= 160:
            base += 0.45
        # plateau zone
        if 750 <= s <= 900:
            base += 0.18
        # divergence spike
        if 2150 <= s <= 2280:
            base += 0.35 * math.exp(-((s - 2200) ** 2) / 2000)
        # spike at 3400
        if 3350 <= s <= 3450:
            base += 0.22 * math.exp(-((s - 3400) ** 2) / 800)
        pts.append((s, max(0.05, min(1.35, base + noise))))

    polyline = " ".join(f"{sx(s):.1f},{sy(l):.1f}" for s, l in pts)

    # green shaded normal zones
    normal_zones = [(0, 100), (200, 750), (950, 2100), (2350, 3300), (3500, 5000)]
    zone_rects = ""
    for z0, z1 in normal_zones:
        x0, x1 = sx(z0), sx(z1)
        zone_rects += (
            f'<rect x="{x0:.1f}" y="{PAD["t"]}" width="{x1-x0:.1f}" '
            f'height="{CH}" fill="#16a34a" opacity="0.12"/>'
        )

    # x-axis ticks
    xticks = ""
    for s in range(0, 5001, 500):
        x = sx(s)
        xticks += (
            f'<line x1="{x:.1f}" y1="{PAD["t"]+CH}" x2="{x:.1f}" y2="{PAD["t"]+CH+6}" '
            f'stroke="#475569" stroke-width="1"/>'
            f'<text x="{x:.1f}" y="{PAD["t"]+CH+20}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="11">{s}</text>'
        )

    # y-axis ticks
    yticks = ""
    for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2]:
        y = sy(v)
        yticks += (
            f'<line x1="{PAD["l"]-5}" y1="{y:.1f}" x2="{PAD["l"]}" y2="{y:.1f}" '
            f'stroke="#475569" stroke-width="1"/>'
            f'<line x1="{PAD["l"]}" y1="{y:.1f}" x2="{PAD["l"]+CW}" y2="{y:.1f}" '
            f'stroke="#1e293b" stroke-width="0.5" stroke-dasharray="4,4"/>'
            f'<text x="{PAD["l"]-10}" y="{y+4:.1f}" text-anchor="end" '
            f'fill="#94a3b8" font-size="11">{v:.1f}</text>'
        )

    # anomaly markers
    markers = ""
    for ev in ANOMALY_EVENTS:
        s = ev["step"]
        x = sx(s)
        # find nearest loss value
        idx = min(range(len(pts)), key=lambda i: abs(pts[i][0] - s))
        y = sy(pts[idx][1])
        markers += (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#C74634" stroke="#ff6b6b" stroke-width="1.5"/>'
            f'<line x1="{x:.1f}" y1="{y-8:.1f}" x2="{x:.1f}" y2="{PAD["t"]+5}" '
            f'stroke="#C74634" stroke-width="1" stroke-dasharray="3,3"/>'
            f'<text x="{x:.1f}" y="{PAD["t"]-2}" text-anchor="middle" '
            f'fill="#C74634" font-size="10" font-weight="bold">{ev["type"]}</text>'
        )

    svg = f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;width:100%;max-width:{W}px">
  <text x="{W//2}" y="22" text-anchor="middle" fill="#38bdf8" font-size="14"
        font-family="monospace" font-weight="bold">Loss Anomaly Timeline — run10 (5000 steps)</text>
  {zone_rects}
  <polyline points="{polyline}" fill="none" stroke="#38bdf8" stroke-width="1.8"/>
  {xticks}
  {yticks}
  {markers}
  <!-- axes -->
  <line x1="{PAD["l"]}" y1="{PAD["t"]}" x2="{PAD["l"]}" y2="{PAD["t"]+CH}"
        stroke="#475569" stroke-width="1.5"/>
  <line x1="{PAD["l"]}" y1="{PAD["t"]+CH}" x2="{PAD["l"]+CW}" y2="{PAD["t"]+CH}"
        stroke="#475569" stroke-width="1.5"/>
  <text x="{W//2}" y="{H-6}" text-anchor="middle" fill="#64748b" font-size="11"
        font-family="monospace">Training Step</text>
  <text x="14" y="{H//2}" text-anchor="middle" fill="#64748b" font-size="11"
        font-family="monospace" transform="rotate(-90,14,{H//2})">Loss</text>
  <!-- legend -->
  <rect x="{W-200}" y="40" width="12" height="12" fill="#38bdf8" rx="2"/>
  <text x="{W-183}" y="51" fill="#94a3b8" font-size="10" font-family="monospace">Loss curve</text>
  <circle cx="{W-194}" cy="65" r="5" fill="#C74634"/>
  <text x="{W-183}" y="69" fill="#94a3b8" font-size="10" font-family="monospace">Anomaly event</text>
  <rect x="{W-200}" y="78" width="12" height="12" fill="#16a34a" opacity="0.4" rx="2"/>
  <text x="{W-183}" y="89" fill="#94a3b8" font-size="10" font-family="monospace">Normal zone</text>
</svg>"""
    return svg


def svg_anomaly_type_bar() -> str:
    W, H = 600, 300
    PAD = {"l": 70, "r": 30, "t": 40, "b": 60}
    types = list(ANOMALY_TYPE_COUNTS.keys())
    counts = [ANOMALY_TYPE_COUNTS[t] for t in types]
    max_c = max(counts)
    CW = W - PAD["l"] - PAD["r"]
    CH = H - PAD["t"] - PAD["b"]
    bar_w = CW / len(types) * 0.6
    gap = CW / len(types)
    COLORS = ["#C74634", "#f97316", "#eab308", "#22d3ee", "#a78bfa"]

    bars = ""
    xlabels = ""
    for i, (t, c) in enumerate(zip(types, counts)):
        x = PAD["l"] + i * gap + gap * 0.2
        bh = c / max_c * CH
        y = PAD["t"] + CH - bh
        bars += (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
            f'fill="{COLORS[i]}" rx="3" opacity="0.9"/>'
            f'<text x="{x+bar_w/2:.1f}" y="{y-6:.1f}" text-anchor="middle" '
            f'fill="{COLORS[i]}" font-size="13" font-weight="bold">{c}</text>'
        )
        xlabels += (
            f'<text x="{x+bar_w/2:.1f}" y="{PAD["t"]+CH+18}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="11" font-family="monospace">{t}</text>'
        )

    yticks = ""
    for v in range(0, max_c + 1):
        y = PAD["t"] + CH - v / max_c * CH
        yticks += (
            f'<line x1="{PAD["l"]-5}" y1="{y:.1f}" x2="{PAD["l"]+CW}" y2="{y:.1f}" '
            f'stroke="#1e293b" stroke-width="0.8"/>'
            f'<text x="{PAD["l"]-8}" y="{y+4:.1f}" text-anchor="end" '
            f'fill="#64748b" font-size="10">{v}</text>'
        )

    svg = f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;width:100%;max-width:{W}px">
  <text x="{W//2}" y="22" text-anchor="middle" fill="#38bdf8" font-size="14"
        font-family="monospace" font-weight="bold">Anomaly Type Distribution (all runs)</text>
  {yticks}
  {bars}
  {xlabels}
  <line x1="{PAD["l"]}" y1="{PAD["t"]}" x2="{PAD["l"]}" y2="{PAD["t"]+CH}"
        stroke="#475569" stroke-width="1.5"/>
  <line x1="{PAD["l"]}" y1="{PAD["t"]+CH}" x2="{PAD["l"]+CW}" y2="{PAD["t"]+CH}"
        stroke="#475569" stroke-width="1.5"/>
  <text x="{W//2}" y="{H-8}" text-anchor="middle" fill="#64748b" font-size="11"
        font-family="monospace">Anomaly Type</text>
  <text x="14" y="{H//2}" text-anchor="middle" fill="#64748b" font-size="11"
        font-family="monospace" transform="rotate(-90,14,{H//2})">Count</text>
</svg>"""
    return svg


def svg_root_cause_heatmap() -> str:
    types = list(ROOT_CAUSE_MATRIX.keys())
    causes = ["lr", "batch", "data_quality", "architecture"]
    CELL = 72
    PAD_L, PAD_T = 120, 50
    W = PAD_L + len(causes) * CELL + 20
    H = PAD_T + len(types) * CELL + 40

    max_val = max(v for row in ROOT_CAUSE_MATRIX.values() for v in row.values())

    def color(val):
        if val == 0:
            return "#0f172a"
        t = val / max_val
        # interpolate #1e3a5f → #C74634
        r = int(0x1e + t * (0xC7 - 0x1e))
        g = int(0x3a + t * (0x46 - 0x3a))
        b = int(0x5f + t * (0x34 - 0x5f))
        return f"#{r:02x}{g:02x}{b:02x}"

    cells = ""
    for ri, atype in enumerate(types):
        for ci, cause in enumerate(causes):
            val = ROOT_CAUSE_MATRIX[atype][cause]
            x = PAD_L + ci * CELL
            y = PAD_T + ri * CELL
            fill = color(val)
            cells += (
                f'<rect x="{x}" y="{y}" width="{CELL-2}" height="{CELL-2}" '
                f'fill="{fill}" rx="3"/>'
            )
            if val > 0:
                text_fill = "#ffffff" if val >= max_val * 0.5 else "#94a3b8"
                cells += (
                    f'<text x="{x+CELL//2-1}" y="{y+CELL//2+5}" text-anchor="middle" '
                    f'fill="{text_fill}" font-size="18" font-weight="bold">{val}</text>'
                )

    # row labels
    row_labels = ""
    for ri, atype in enumerate(types):
        y = PAD_T + ri * CELL + CELL // 2 + 4
        row_labels += (
            f'<text x="{PAD_L-8}" y="{y}" text-anchor="end" fill="#94a3b8" '
            f'font-size="12" font-family="monospace">{atype}</text>'
        )

    # col labels
    col_labels = ""
    for ci, cause in enumerate(causes):
        x = PAD_L + ci * CELL + CELL // 2 - 1
        col_labels += (
            f'<text x="{x}" y="{PAD_T-8}" text-anchor="middle" fill="#38bdf8" '
            f'font-size="11" font-family="monospace">{cause}</text>'
        )

    svg = f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;width:100%;max-width:{W}px">
  <text x="{W//2}" y="22" text-anchor="middle" fill="#38bdf8" font-size="14"
        font-family="monospace" font-weight="bold">Root Cause Attribution Heatmap</text>
  <text x="{W//2}" y="37" text-anchor="middle" fill="#64748b" font-size="10"
        font-family="monospace">anomaly type × root cause (frequency)</text>
  {col_labels}
  {row_labels}
  {cells}
</svg>"""
    return svg


# ── HTML page ─────────────────────────────────────────────────────────────────

def build_html() -> str:
    tl = svg_loss_timeline()
    tb = svg_anomaly_type_bar()
    th = svg_root_cause_heatmap()

    stats_rows = ""
    for ev in ANOMALY_EVENTS:
        stats_rows += (
            f"<tr><td>{ev['step']}</td><td>{ev['type']}</td>"
            f"<td>{ev['cause']}</td><td>{ev['fix']}</td>"
            f"<td style='color:#4ade80'>✓ resolved</td></tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Training Anomaly Detector — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:monospace;padding:24px}}
  h1{{color:#38bdf8;font-size:1.4rem;margin-bottom:4px}}
  .sub{{color:#64748b;font-size:.85rem;margin-bottom:24px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px}}
  .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px}}
  .card h2{{color:#C74634;font-size:.95rem;margin-bottom:14px}}
  .full{{grid-column:1/-1}}
  .kpi-row{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}}
  .kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 20px;min-width:140px}}
  .kpi .val{{color:#38bdf8;font-size:1.6rem;font-weight:bold}}
  .kpi .lbl{{color:#64748b;font-size:.75rem;margin-top:2px}}
  table{{width:100%;border-collapse:collapse;font-size:.82rem}}
  th{{color:#38bdf8;border-bottom:1px solid #334155;padding:8px 10px;text-align:left}}
  td{{padding:7px 10px;border-bottom:1px solid #1e293b;color:#cbd5e1}}
  tr:hover td{{background:#1e293b}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.75rem;
           background:#C74634;color:#fff}}
  svg{{display:block}}
</style>
</head>
<body>
<h1>Training Anomaly Detector</h1>
<div class="sub">OCI Robot Cloud · Port 8646 · cycle-147A</div>

<div class="kpi-row">
  <div class="kpi"><div class="val">4</div><div class="lbl">Anomalies in run10</div></div>
  <div class="kpi"><div class="val" style="color:#4ade80">4/4</div><div class="lbl">Resolved</div></div>
  <div class="kpi"><div class="val">12</div><div class="lbl">Total anomalies (all runs)</div></div>
  <div class="kpi"><div class="val">5</div><div class="lbl">Anomaly types tracked</div></div>
  <div class="kpi"><div class="val" style="color:#C74634">data_quality</div><div class="lbl">Top NaN cause</div></div>
  <div class="kpi"><div class="val" style="color:#f97316">lr</div><div class="lbl">Top plateau cause</div></div>
</div>

<div class="grid">
  <div class="card full">
    <h2>Loss Anomaly Timeline</h2>
    {tl}
  </div>
  <div class="card">
    <h2>Anomaly Type Distribution</h2>
    {tb}
  </div>
  <div class="card">
    <h2>Root Cause Attribution Heatmap</h2>
    {th}
  </div>
  <div class="card full">
    <h2>Anomaly Event Log — run10</h2>
    <table>
      <thead><tr><th>Step</th><th>Type</th><th>Root Cause</th><th>Fix Applied</th><th>Status</th></tr></thead>
      <tbody>{stats_rows}</tbody>
    </table>
  </div>
</div>
</body>
</html>"""


# ── app ───────────────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="Training Anomaly Detector", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return build_html()

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "training_anomaly_detector", "port": 8646})

    @app.get("/api/anomalies")
    async def get_anomalies():
        return JSONResponse({
            "run10_anomalies": ANOMALY_EVENTS,
            "type_counts": ANOMALY_TYPE_COUNTS,
            "root_cause_matrix": ROOT_CAUSE_MATRIX,
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8646)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": 8646}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        srv = HTTPServer(("0.0.0.0", 8646), Handler)
        print("Training Anomaly Detector running on :8646")
        srv.serve_forever()

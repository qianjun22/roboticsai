try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    raise ImportError("fastapi and uvicorn are required: pip install fastapi uvicorn")

from datetime import datetime

app = FastAPI(title="OCI Robot Cloud — Training Infra Monitor", version="1.0.0")

# Infrastructure tile data
TILES = [
    {"id": "gpu",      "label": "GPU Utilization",  "value": "91%",    "status": "ok",    "color": "#22c55e", "detail": "A100 × 8, 91% avg"},
    {"id": "cpu",      "label": "CPU Load",          "value": "68%",    "status": "ok",    "color": "#22c55e", "detail": "96-core, 68% avg"},
    {"id": "storage",  "label": "Storage IOPS",      "value": "78%",    "status": "warn",  "color": "#f59e0b", "detail": "NVMe, 78% capacity"},
    {"id": "network",  "label": "Network Util",      "value": "58%",    "status": "ok",    "color": "#22c55e", "detail": "42% headroom"},
    {"id": "jobqueue", "label": "Job Queue p99",     "value": "4.2min", "status": "ok",    "color": "#22c55e", "detail": "Target <10min"},
    {"id": "alerts",   "label": "Infra Failures",    "value": "0",      "status": "ok",    "color": "#22c55e", "detail": "30-day window"},
]

STATUS_CIRCLE = {"ok": "#22c55e", "warn": "#f59e0b", "crit": "#C74634"}

# Job queue depth — 30 days (sampled daily), with DAgger launch spikes
QUEUE_DATA = [
    3, 2, 4, 3, 5, 6, 4, 3, 2, 4,
    14, 12, 9, 6, 4, 3, 2, 3, 4, 5,
    17, 15, 11, 8, 5, 4, 3, 2, 3, 4,
]
DAGGER_LAUNCHES = [10, 20]  # day indices of DAgger launches

# Resource bottleneck heatmap: 6 resources × 24 hours (0-100 saturation)
RESOURCES = ["GPU", "CPU", "Storage", "Network", "JobQueue", "Memory"]
# Saturation matrix [resource][hour 0..23]
import math as _math
_HEATMAP = []
for r_i, res in enumerate(RESOURCES):
    row = []
    for h in range(24):
        if res == "GPU":
            # Peak 9 AM – 5 PM
            base = 35
            peak = 91 if 9 <= h <= 17 else (60 if 7 <= h <= 19 else 35)
            noise = ((_math.sin(r_i * 7 + h * 3) + 1) * 5)
            row.append(min(99, int(peak + noise)))
        elif res == "CPU":
            base = 45
            peak = 68 if 9 <= h <= 17 else (50 if 7 <= h <= 19 else 40)
            noise = ((_math.sin(r_i * 5 + h * 2) + 1) * 4)
            row.append(min(99, int(peak + noise)))
        elif res == "Storage":
            # Peak during checkpoint saves: 2 AM, 6 AM, 2 PM, 6 PM
            peak = 78 if h in (2, 6, 14, 18) else (55 if h in (1, 3, 5, 7, 13, 15, 17, 19) else 38)
            noise = ((_math.sin(r_i * 3 + h) + 1) * 3)
            row.append(min(99, int(peak + noise)))
        elif res == "Network":
            peak = 58 if 9 <= h <= 17 else (40 if 7 <= h <= 19 else 28)
            noise = ((_math.sin(r_i * 4 + h * 4) + 1) * 5)
            row.append(min(99, int(peak + noise)))
        elif res == "JobQueue":
            peak = 65 if 9 <= h <= 11 else (45 if 8 <= h <= 16 else 20)
            noise = ((_math.sin(r_i * 6 + h * 2) + 1) * 4)
            row.append(min(99, int(peak + noise)))
        else:  # Memory
            peak = 72 if 9 <= h <= 17 else (55 if 6 <= h <= 20 else 42)
            noise = ((_math.sin(r_i * 2 + h * 3) + 1) * 4)
            row.append(min(99, int(peak + noise)))
    _HEATMAP.append(row)


def _saturation_color(v: int) -> str:
    """Map 0-100 saturation to heat color."""
    if v >= 85:
        return "#C74634"
    if v >= 70:
        return "#f97316"
    if v >= 50:
        return "#f59e0b"
    if v >= 30:
        return "#38bdf8"
    return "#1e3a5f"


# ─── SVG 1: Infrastructure Health Tiles (2×3 grid) ─────────────────────────────────────────

def _build_health_tiles_svg() -> str:
    W, H = 760, 220
    TILE_W, TILE_H = 220, 82
    COLS, ROWS = 3, 2
    PAD_X, PAD_Y = 24, 40
    GAP_X, GAP_Y = 18, 14

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">'
    ]
    lines.append(f'<text x="14" y="22" fill="#94a3b8" font-size="11" font-weight="bold">'
                 f'Infrastructure Health Overview</text>')

    for i, tile in enumerate(TILES):
        col = i % COLS
        row = i // COLS
        tx = PAD_X + col * (TILE_W + GAP_X)
        ty = PAD_Y + row * (TILE_H + GAP_Y)

        # Tile background
        lines.append(f'<rect x="{tx}" y="{ty}" width="{TILE_W}" height="{TILE_H}" '
                     f'rx="6" fill="#0f172a" stroke="#334155" stroke-width="1"/>')

        # Status circle
        cx_c = tx + 22
        cy_c = ty + TILE_H // 2
        lines.append(f'<circle cx="{cx_c}" cy="{cy_c}" r="9" fill="{tile["color"]}" opacity="0.9"/>')

        # Value
        lines.append(f'<text x="{tx + 44}" y="{ty + 28}" fill="{tile["color"]}" '
                     f'font-size="22" font-weight="700">{tile["value"]}</text>')

        # Label
        lines.append(f'<text x="{tx + 44}" y="{ty + 46}" fill="#94a3b8" font-size="10" '
                     f'font-weight="bold">{tile["label"]}</text>')

        # Detail
        lines.append(f'<text x="{tx + 44}" y="{ty + 62}" fill="#475569" font-size="9">'
                     f'{tile["detail"]}</text>')

        # Status badge
        status_lbl = tile["status"].upper()
        badge_col = STATUS_CIRCLE.get(tile["status"], "#64748b")
        lines.append(f'<rect x="{tx + TILE_W - 44}" y="{ty + 8}" width="36" height="16" '
                     f'rx="8" fill="{badge_col}" opacity="0.2"/>')
        lines.append(f'<text x="{tx + TILE_W - 26}" y="{ty + 20}" fill="{badge_col}" '
                     f'font-size="8" font-weight="bold" text-anchor="middle">{status_lbl}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ─── SVG 2: Job Queue Depth (30-day area chart) ─────────────────────────────────────────────

def _build_queue_depth_svg() -> str:
    W, H = 760, 200
    PAD_L, PAD_R, PAD_T, PAD_B = 48, 20, 30, 36
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B
    n = len(QUEUE_DATA)
    y_max = 22

    def xp(i):
        return PAD_L + i / (n - 1) * inner_w

    def yp(v):
        return PAD_T + inner_h - v / y_max * inner_h

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">'
    ]
    lines.append(f'<text x="14" y="20" fill="#94a3b8" font-size="11" font-weight="bold">'
                 f'Job Queue Depth — 30 Days (p99 = 8 jobs, target &lt;10)</text>')

    # Grid
    for gv in (5, 10, 15, 20):
        gy = yp(gv)
        lines.append(f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{PAD_L + inner_w}" y2="{gy:.1f}" '
                     f'stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{PAD_L - 6}" y="{gy + 4:.1f}" fill="#64748b" font-size="9" '
                     f'text-anchor="end">{gv}</text>')

    # p99 threshold line
    p99_y = yp(8)
    lines.append(f'<line x1="{PAD_L}" y1="{p99_y:.1f}" x2="{PAD_L + inner_w}" y2="{p99_y:.1f}" '
                 f'stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="6,4"/>')
    lines.append(f'<text x="{PAD_L + inner_w - 2}" y="{p99_y - 4:.1f}" fill="#f59e0b" font-size="9" '
                 f'text-anchor="end">p99 = 8</text>')

    # Area fill
    pts_top = " ".join(f"{xp(i):.1f},{yp(v):.1f}" for i, v in enumerate(QUEUE_DATA))
    bottom_right = f"{xp(n-1):.1f},{PAD_T + inner_h}"
    bottom_left = f"{PAD_L},{PAD_T + inner_h}"
    lines.append(f'<polygon points="{pts_top} {bottom_right} {bottom_left}" '
                 f'fill="#38bdf8" opacity="0.18"/>')

    # Line
    path_d = " ".join(
        ("M" if i == 0 else "L") + f"{xp(i):.1f} {yp(v):.1f}"
        for i, v in enumerate(QUEUE_DATA)
    )
    lines.append(f'<path d="{path_d}" fill="none" stroke="#38bdf8" stroke-width="2"/>')

    # Data points + DAgger annotations
    for i, v in enumerate(QUEUE_DATA):
        cx, cy = xp(i), yp(v)
        if i in DAGGER_LAUNCHES:
            lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="#C74634"/>')
            lines.append(f'<text x="{cx:.1f}" y="{cy - 10:.1f}" fill="#C74634" font-size="8" '
                         f'text-anchor="middle">DAgger</text>')
            lines.append(f'<line x1="{cx:.1f}" y1="{PAD_T}" x2="{cx:.1f}" y2="{PAD_T + inner_h}" '
                         f'stroke="#C74634" stroke-width="1" stroke-dasharray="3,4" opacity="0.5"/>')
        else:
            lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="#38bdf8"/>')

    # Axes
    lines.append(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T + inner_h}" '
                 f'stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{PAD_L}" y1="{PAD_T + inner_h}" x2="{PAD_L + inner_w}" '
                 f'y2="{PAD_T + inner_h}" stroke="#475569" stroke-width="1"/>')

    # X-axis ticks every 5 days
    for d in range(0, 31, 5):
        ix = min(d, n - 1)
        dx = xp(ix)
        lines.append(f'<line x1="{dx:.1f}" y1="{PAD_T + inner_h}" x2="{dx:.1f}" '
                     f'y2="{PAD_T + inner_h + 4}" stroke="#475569" stroke-width="1"/>')
        lines.append(f'<text x="{dx:.1f}" y="{PAD_T + inner_h + 16}" fill="#64748b" font-size="9" '
                     f'text-anchor="middle">D{d}</text>')

    # Y label
    lines.append(f'<text x="11" y="{PAD_T + inner_h//2}" fill="#64748b" font-size="9" '
                 f'text-anchor="middle" transform="rotate(-90,11,{PAD_T + inner_h//2})">'
                 f'Jobs in queue</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ─── SVG 3: Resource Bottleneck Heatmap ──────────────────────────────────────────────

def _build_heatmap_svg() -> str:
    n_res = len(RESOURCES)
    n_hrs = 24
    CELL_W, CELL_H = 26, 28
    PAD_L, PAD_R, PAD_T, PAD_B = 78, 20, 30, 30
    W = PAD_L + n_hrs * CELL_W + PAD_R
    H = PAD_T + n_res * CELL_H + PAD_B

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">'
    ]
    lines.append(f'<text x="14" y="20" fill="#94a3b8" font-size="11" font-weight="bold">'
                 f'Resource Bottleneck Heatmap (Saturation %)</text>')

    # Hour labels
    for h in range(n_hrs):
        hx = PAD_L + h * CELL_W + CELL_W // 2
        if h % 3 == 0:
            lines.append(f'<text x="{hx}" y="{PAD_T - 6}" fill="#64748b" font-size="8" '
                         f'text-anchor="middle">{h:02d}h</text>')

    for r_i, res in enumerate(RESOURCES):
        ry = PAD_T + r_i * CELL_H
        # Resource label
        lines.append(f'<text x="{PAD_L - 6}" y="{ry + CELL_H//2 + 4}" fill="#94a3b8" '
                     f'font-size="10" text-anchor="end">{res}</text>')

        for h in range(n_hrs):
            sat = _HEATMAP[r_i][h]
            col = _saturation_color(sat)
            cx = PAD_L + h * CELL_W
            lines.append(f'<rect x="{cx}" y="{ry}" width="{CELL_W - 1}" height="{CELL_H - 1}" '
                         f'rx="2" fill="{col}" opacity="0.85"/>')
            if CELL_W >= 22:
                txt_col = "#e2e8f0" if sat >= 50 else "#475569"
                lines.append(f'<text x="{cx + CELL_W//2 - 1}" y="{ry + CELL_H//2 + 4}" '
                              f'fill="{txt_col}" font-size="7" text-anchor="middle">{sat}</text>')

    # Legend
    lx = PAD_L
    ly = H - 10
    for sat_val, lbl in [(20, "Low"), (45, "Med"), (65, "High"), (80, "Warn"), (90, "Crit")]:
        col = _saturation_color(sat_val)
        lines.append(f'<rect x="{lx}" y="{ly - 9}" width="12" height="12" rx="2" fill="{col}"/>')
        lines.append(f'<text x="{lx + 15}" y="{ly}" fill="#64748b" font-size="8">{lbl}</text>')
        lx += 58

    lines.append('</svg>')
    return "\n".join(lines)


# ─── HTML page ──────────────────────────────────────────────────────────────────────────────

def _build_html() -> str:
    tiles_svg   = _build_health_tiles_svg()
    queue_svg   = _build_queue_depth_svg()
    heatmap_svg = _build_heatmap_svg()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Training Infra Monitor — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
  h1{{color:#38bdf8;font-size:1.4rem;margin-bottom:4px}}
  .subtitle{{color:#64748b;font-size:.85rem;margin-bottom:24px}}
  .kpi-row{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}}
  .kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;min-width:160px}}
  .kpi .val{{font-size:1.6rem;font-weight:700;color:#38bdf8}}
  .kpi .val.warn{{color:#f59e0b}}
  .kpi .val.ok{{color:#22c55e}}
  .kpi .lbl{{font-size:.78rem;color:#64748b;margin-top:2px}}
  .section{{margin-bottom:28px}}
  .section h2{{font-size:.95rem;color:#94a3b8;margin-bottom:10px;border-bottom:1px solid #1e3a5f;padding-bottom:6px}}
  .svg-wrap{{overflow-x:auto}}
  svg{{max-width:100%;height:auto}}
  .insight-box{{background:#1e293b;border-left:3px solid #38bdf8;border-radius:4px;padding:12px 16px;
               font-size:.82rem;color:#94a3b8;margin-top:10px;line-height:1.6}}
  .insight-box strong{{color:#e2e8f0}}
</style>
</head>
<body>
<h1>Training Infrastructure Monitor</h1>
<p class="subtitle">OCI Robot Cloud &mdash; port 8663 &mdash; {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>

<div class="kpi-row">
  <div class="kpi"><div class="val ok">91%</div><div class="lbl">GPU Utilization</div></div>
  <div class="kpi"><div class="val warn">78%</div><div class="lbl">Storage IOPS</div></div>
  <div class="kpi"><div class="val ok">42%</div><div class="lbl">Network Headroom</div></div>
  <div class="kpi"><div class="val ok">4.2 min</div><div class="lbl">p99 Queue Wait (target &lt;10min)</div></div>
  <div class="kpi"><div class="val ok">0</div><div class="lbl">Infra Failures (30d)</div></div>
</div>

<div class="section">
  <h2>Infrastructure Health Overview</h2>
  <div class="svg-wrap">{tiles_svg}</div>
  <div class="insight-box">
    <strong>Status:</strong> All systems nominal. Storage IOPS at <strong>78%</strong> — elevated
    during checkpoint-heavy DAgger runs. GPU utilization holding at <strong>91%</strong> across
    all A100 nodes. Network has <strong>42% headroom</strong> for multi-node scale-out.
    Zero infra-caused job failures in the last <strong>30 days</strong>.
  </div>
</div>

<div class="section">
  <h2>Job Queue Depth — 30 Days</h2>
  <div class="svg-wrap">{queue_svg}</div>
  <div class="insight-box">
    <strong>Pattern:</strong> Queue spikes to 14&ndash;17 jobs at <strong>DAgger launch events</strong>
    (days 10, 20), draining within 2&ndash;3 days. Steady-state queue depth is 2&ndash;5 jobs.
    p99 over the window is <strong>8 jobs</strong> &mdash; well within the &lt;10 job SLO.
    No backlog accumulation trend detected.
  </div>
</div>

<div class="section">
  <h2>Resource Bottleneck Heatmap (6 Resources × 24 Hours)</h2>
  <div class="svg-wrap">{heatmap_svg}</div>
  <div class="insight-box">
    <strong>Hotspots:</strong> GPU peaks 9&nbsp;AM&ndash;5&nbsp;PM (91% saturation) &mdash; aligns
    with scheduled training jobs. Storage peaks at <strong>2 AM, 6 AM, 2 PM, 6 PM</strong> during
    checkpoint saves — consider staggering checkpoints to reduce IOPS contention. Network and
    CPU remain well within capacity throughout the 24-hour cycle.
  </div>
</div>
</body>
</html>"""


# ─── Routes ──────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    return _build_html()


@app.get("/health", response_class=JSONResponse)
def health():
    return {
        "status": "ok",
        "service": "training_infra_monitor",
        "port": 8663,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "metrics": {
            "gpu_utilization_pct": 91,
            "storage_iops_pct": 78,
            "network_headroom_pct": 42,
            "queue_p99_min": 4.2,
            "queue_slo_min": 10,
            "infra_failures_30d": 0,
        },
    }


@app.get("/api/tiles", response_class=JSONResponse)
def api_tiles():
    return {"tiles": TILES}


@app.get("/api/queue", response_class=JSONResponse)
def api_queue():
    return {"queue_depth_30d": QUEUE_DATA, "dagger_launch_days": DAGGER_LAUNCHES, "p99": 8}


@app.get("/api/heatmap", response_class=JSONResponse)
def api_heatmap():
    return {"resources": RESOURCES, "hours": list(range(24)), "saturation": _HEATMAP}


if __name__ == "__main__":
    try:
        uvicorn.run(app, host="0.0.0.0", port=8663)
    except Exception:
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class _H(BaseHTTPRequestHandler):
            def do_GET(self):
                body = _build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        HTTPServer(("0.0.0.0", 8663), _H).serve_forever()

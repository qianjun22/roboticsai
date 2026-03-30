"""Data Annotation Tracker — FastAPI service on port 8288.

Tracks human annotation progress for robot demonstration quality labeling.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

import random
import math
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

ANNOTATORS = [
    "annotator_1", "annotator_2", "annotator_3", "annotator_4", "annotator_5"
]

QUALITY_DIMS = [
    "trajectory_smoothness", "grasp_quality", "success_label", "timing",
    "safety", "completeness", "difficulty", "reproducibility"
]

# Cohen's kappa matrix (annotator x dimension)
# annotator_2 and annotator_4 highest overall; grasp_quality lowest
KAPPA = [
    [0.78, 0.62, 0.81, 0.75, 0.80, 0.77, 0.73, 0.76],  # annotator_1
    [0.88, 0.65, 0.91, 0.87, 0.90, 0.89, 0.85, 0.88],  # annotator_2
    [0.74, 0.59, 0.77, 0.71, 0.75, 0.73, 0.69, 0.72],  # annotator_3
    [0.86, 0.63, 0.89, 0.85, 0.88, 0.87, 0.83, 0.89],  # annotator_4
    [0.76, 0.57, 0.79, 0.74, 0.78, 0.75, 0.71, 0.75],  # annotator_5
]

TOTAL_LABELED = 847
TARGET = 2000
DAILY_THROUGHPUT = 28  # current avg episodes/day
TARGET_DAILY = 38      # needed to hit June target

# Generate 30-day daily annotation counts (seeded for consistency)
random.seed(42)
DAILY_COUNTS = []
for i in range(30):
    base = DAILY_THROUGHPUT
    jitter = random.randint(-6, 12)
    DAILY_COUNTS.append(max(10, base + jitter))

# Rebase so sum == TOTAL_LABELED
raw_sum = sum(DAILY_COUNTS)
DAILY_COUNTS = [int(c * TOTAL_LABELED / raw_sum) for c in DAILY_COUNTS]
diff = TOTAL_LABELED - sum(DAILY_COUNTS)
DAILY_COUNTS[-1] += diff


def running_totals():
    totals = []
    acc = 0
    for c in DAILY_COUNTS:
        acc += c
        totals.append(acc)
    return totals


def june_eta_days():
    """Days needed at current pace to reach TARGET."""
    remaining = TARGET - TOTAL_LABELED
    if DAILY_THROUGHPUT <= 0:
        return None
    return math.ceil(remaining / DAILY_THROUGHPUT)


def low_agreement_dims():
    avg_per_dim = []
    for d in range(len(QUALITY_DIMS)):
        vals = [KAPPA[a][d] for a in range(len(ANNOTATORS))]
        avg_per_dim.append(round(sum(vals) / len(vals), 3))
    return [(QUALITY_DIMS[i], avg_per_dim[i]) for i in range(len(QUALITY_DIMS)) if avg_per_dim[i] < 0.70]


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def svg_throughput_chart() -> str:
    """Bar chart: daily annotated episodes over 30 days with running total."""
    W, H = 700, 260
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 40
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    counts = DAILY_COUNTS
    totals = running_totals()
    max_count = max(counts) * 1.15
    max_total = TARGET * 1.05

    bar_w = chart_w / len(counts) * 0.7
    bar_gap = chart_w / len(counts)

    bars = []
    for i, c in enumerate(counts):
        x = pad_l + i * bar_gap + (bar_gap - bar_w) / 2
        bh = (c / max_count) * chart_h
        y = pad_t + chart_h - bh
        color = "#38bdf8" if c >= DAILY_THROUGHPUT else "#f59e0b"
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
            f'fill="{color}" opacity="0.85" rx="2"/>'
        )

    # Running total line (secondary axis scaled to TARGET)
    points = []
    for i, t in enumerate(totals):
        x = pad_l + i * bar_gap + bar_gap / 2
        y = pad_t + chart_h - (t / max_total) * chart_h
        points.append(f"{x:.1f},{y:.1f}")
    polyline = f'<polyline points="{" ".join(points)}" fill="none" stroke="#C74634" stroke-width="2"/>'

    # Target line
    target_y = pad_t + chart_h - (TARGET / max_total) * chart_h
    target_line = (
        f'<line x1="{pad_l}" y1="{target_y:.1f}" x2="{W - pad_r}" y2="{target_y:.1f}" '
        f'stroke="#C74634" stroke-width="1" stroke-dasharray="6,3" opacity="0.7"/>'
        f'<text x="{W - pad_r - 2}" y="{target_y - 4:.1f}" fill="#C74634" '
        f'font-size="10" text-anchor="end">Target {TARGET}</text>'
    )

    # Axes
    axis = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{W - pad_r}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>'
    )

    # X labels (every 5 days)
    xlabels = ""
    for i in range(0, 30, 5):
        x = pad_l + i * bar_gap + bar_gap / 2
        xlabels += f'<text x="{x:.1f}" y="{pad_t + chart_h + 14}" fill="#94a3b8" font-size="9" text-anchor="middle">D{i+1}</text>'

    # Y label
    ylabel = f'<text x="12" y="{pad_t + chart_h // 2}" fill="#94a3b8" font-size="10" text-anchor="middle" transform="rotate(-90 12 {pad_t + chart_h // 2})">Episodes/day</text>'

    legend = (
        f'<rect x="{pad_l}" y="4" width="10" height="10" fill="#38bdf8" rx="2"/>'
        f'<text x="{pad_l + 14}" y="13" fill="#94a3b8" font-size="10">On/above target</text>'
        f'<rect x="{pad_l + 120}" y="4" width="10" height="10" fill="#f59e0b" rx="2"/>'
        f'<text x="{pad_l + 134}" y="13" fill="#94a3b8" font-size="10">Below target</text>'
        f'<line x1="{pad_l + 220}" y1="9" x2="{pad_l + 234}" y2="9" stroke="#C74634" stroke-width="2"/>'
        f'<text x="{pad_l + 238}" y="13" fill="#94a3b8" font-size="10">Running total</text>'
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b; border-radius:8px;">'
        + axis + target_line + "".join(bars) + polyline + xlabels + ylabel + legend +
        '</svg>'
    )
    return svg


def svg_agreement_heatmap() -> str:
    """5-annotator × 8-dimension Cohen's kappa heatmap."""
    cell_w, cell_h = 72, 36
    pad_l, pad_t = 130, 50
    W = pad_l + cell_w * len(QUALITY_DIMS) + 20
    H = pad_t + cell_h * len(ANNOTATORS) + 30

    def kappa_color(k):
        if k >= 0.80:
            return "#166534"  # dark green
        if k >= 0.70:
            return "#1e40af"  # dark blue
        return "#7f1d1d"      # dark red (low agreement)

    cells = ""
    for r, ann in enumerate(ANNOTATORS):
        for c, dim in enumerate(QUALITY_DIMS):
            k = KAPPA[r][c]
            x = pad_l + c * cell_w
            y = pad_t + r * cell_h
            bg = kappa_color(k)
            text_color = "#fef9c3" if k < 0.70 else "#e2e8f0"
            cells += (
                f'<rect x="{x}" y="{y}" width="{cell_w - 1}" height="{cell_h - 1}" fill="{bg}" rx="2"/>'
                f'<text x="{x + cell_w//2}" y="{y + cell_h//2 + 5}" fill="{text_color}" '
                f'font-size="11" font-weight="bold" text-anchor="middle">{k:.2f}</text>'
            )

    # Column headers (rotated)
    col_headers = ""
    for c, dim in enumerate(QUALITY_DIMS):
        x = pad_l + c * cell_w + cell_w // 2
        y = pad_t - 6
        short = dim.replace("_", " ")
        col_headers += (
            f'<text x="{x}" y="{y}" fill="#94a3b8" font-size="9" text-anchor="middle" '
            f'transform="rotate(-30 {x} {y})">{short}</text>'
        )

    # Row headers
    row_headers = ""
    for r, ann in enumerate(ANNOTATORS):
        y = pad_t + r * cell_h + cell_h // 2 + 4
        row_headers += (
            f'<text x="{pad_l - 6}" y="{y}" fill="#94a3b8" font-size="10" text-anchor="end">{ann}</text>'
        )

    # Legend
    legend = (
        f'<rect x="{pad_l}" y="{H - 22}" width="12" height="12" fill="#166534" rx="2"/>'
        f'<text x="{pad_l + 16}" y="{H - 12}" fill="#94a3b8" font-size="9">κ≥0.80 high</text>'
        f'<rect x="{pad_l + 90}" y="{H - 22}" width="12" height="12" fill="#1e40af" rx="2"/>'
        f'<text x="{pad_l + 106}" y="{H - 12}" fill="#94a3b8" font-size="9">0.70–0.79 mod</text>'
        f'<rect x="{pad_l + 190}" y="{H - 22}" width="12" height="12" fill="#7f1d1d" rx="2"/>'
        f'<text x="{pad_l + 206}" y="{H - 12}" fill="#94a3b8" font-size="9">κ<0.70 low ⚠</text>'
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b; border-radius:8px;">'
        + col_headers + row_headers + cells + legend +
        '</svg>'
    )
    return svg


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def build_html() -> str:
    totals = running_totals()
    eta_days = june_eta_days()
    low_dims = low_agreement_dims()
    avg_kappa = round(sum(KAPPA[a][d] for a in range(5) for d in range(8)) / 40, 3)
    pct_complete = round(TOTAL_LABELED / TARGET * 100, 1)

    chart1 = svg_throughput_chart()
    chart2 = svg_agreement_heatmap()

    low_dim_html = "".join(
        f'<span style="background:#7f1d1d;color:#fef9c3;padding:2px 8px;border-radius:4px;margin:2px;display:inline-block;font-size:12px;">'
        f'{dim} (κ={v})</span>'
        for dim, v in low_dims
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Data Annotation Tracker — Port 8288</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 22px; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
  .metrics {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px 20px; min-width: 160px; }}
  .card .val {{ font-size: 28px; font-weight: 700; color: #38bdf8; }}
  .card .lbl {{ font-size: 11px; color: #64748b; margin-top: 2px; text-transform: uppercase; letter-spacing: .05em; }}
  .card.warn .val {{ color: #f59e0b; }}
  .card.danger .val {{ color: #C74634; }}
  .section {{ margin-bottom: 32px; }}
  .section h2 {{ font-size: 15px; color: #94a3b8; margin-bottom: 12px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
  .chart-wrap {{ overflow-x: auto; }}
  .low-dims {{ margin-top: 10px; }}
  footer {{ margin-top: 32px; color: #334155; font-size: 11px; }}
</style>
</head>
<body>
<h1>Data Annotation Tracker</h1>
<div class="subtitle">OCI Robot Cloud · Robot Demo Quality Labeling · Port 8288</div>

<div class="metrics">
  <div class="card">
    <div class="val">{TOTAL_LABELED}</div>
    <div class="lbl">Episodes Labeled</div>
  </div>
  <div class="card warn">
    <div class="val">{TARGET - TOTAL_LABELED}</div>
    <div class="lbl">Remaining to Target</div>
  </div>
  <div class="card">
    <div class="val">{pct_complete}%</div>
    <div class="lbl">Target Progress</div>
  </div>
  <div class="card {'danger' if DAILY_THROUGHPUT < TARGET_DAILY else ''}">
    <div class="val">{DAILY_THROUGHPUT}</div>
    <div class="lbl">Avg Episodes/Day</div>
  </div>
  <div class="card">
    <div class="val">{TARGET_DAILY}</div>
    <div class="lbl">Required/Day (June)</div>
  </div>
  <div class="card">
    <div class="val">{eta_days}d</div>
    <div class="lbl">ETA at Current Pace</div>
  </div>
  <div class="card">
    <div class="val">{avg_kappa}</div>
    <div class="lbl">Avg Cohen's Kappa</div>
  </div>
  <div class="card {'danger' if low_dims else ''}">
    <div class="val">{len(low_dims)}</div>
    <div class="lbl">Low-Agreement Dims</div>
  </div>
</div>

<div class="section">
  <h2>Annotation Throughput — Daily Episodes (30 days) + Running Total</h2>
  <div class="chart-wrap">{chart1}</div>
  <p style="color:#64748b;font-size:12px;margin-top:8px;">
    Blue bars = on/above target ({TARGET_DAILY}/day). Amber bars = below. Red line = running total toward {TARGET} labeled by June.
  </p>
</div>

<div class="section">
  <h2>Inter-Annotator Agreement Heatmap — Cohen's Kappa (5 annotators × 8 dimensions)</h2>
  <div class="chart-wrap">{chart2}</div>
  <p style="color:#64748b;font-size:12px;margin-top:8px;">
    annotator_2 and annotator_4 show highest agreement (κ=0.89). Dimensions below κ=0.70 flagged for recalibration.
  </p>
  <div class="low-dims">
    <span style="color:#94a3b8;font-size:12px;margin-right:8px;">Low-agreement (&lt;0.70):</span>
    {low_dim_html if low_dim_html else '<span style="color:#22c55e;font-size:12px;">None — all dimensions above threshold</span>'}
  </div>
</div>

<footer>OCI Robot Cloud · Data Annotation Tracker · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</footer>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(
        title="Data Annotation Tracker",
        description="Tracks human annotation progress for robot demo quality labeling",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "data_annotation_tracker", "port": 8288}

    @app.get("/api/metrics")
    def metrics():
        return {
            "total_labeled": TOTAL_LABELED,
            "target": TARGET,
            "pct_complete": round(TOTAL_LABELED / TARGET * 100, 1),
            "daily_throughput": DAILY_THROUGHPUT,
            "target_daily": TARGET_DAILY,
            "eta_days": june_eta_days(),
            "avg_kappa": round(sum(KAPPA[a][d] for a in range(5) for d in range(8)) / 40, 3),
            "low_agreement_dims": low_agreement_dims(),
            "annotators": ANNOTATORS,
            "quality_dimensions": QUALITY_DIMS,
        }

    @app.get("/api/kappa")
    def kappa_matrix():
        return {
            "annotators": ANNOTATORS,
            "dimensions": QUALITY_DIMS,
            "matrix": KAPPA,
        }

    @app.get("/api/daily")
    def daily_counts():
        return {
            "counts": DAILY_COUNTS,
            "running_totals": running_totals(),
        }

else:
    # ---------------------------------------------------------------------------
    # Fallback: stdlib http.server
    # ---------------------------------------------------------------------------
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8288)
    else:
        print("[data_annotation_tracker] fastapi not found — using stdlib http.server on port 8288")
        with socketserver.TCPServer(("", 8288), _Handler) as httpd:
            httpd.serve_forever()

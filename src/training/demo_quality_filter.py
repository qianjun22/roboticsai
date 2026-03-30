"""demo_quality_filter.py — Multi-stage quality filter for teleoperation demonstrations.

FastAPI service on port 8313.
Cycle-63A: OCI Robot Cloud
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random
from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------
random.seed(7)

FILTER_PIPELINE = [
    {"stage": "raw_demos",       "count": 600, "removed": 0,  "pct_removed": 0.0,  "reason": "—",                          "color": "#94a3b8"},
    {"stage": "length_filter",   "count": 547, "removed": 53, "pct_removed": 8.8,  "reason": "Episode too short (<10 frames)","color": "#38bdf8"},
    {"stage": "success_filter",  "count": 489, "removed": 58, "pct_removed": 9.6,  "reason": "Task did not succeed",          "color": "#f59e0b"},
    {"stage": "smoothness_filter","count": 451, "removed": 38, "pct_removed": 6.3, "reason": "Jerk score above threshold",     "color": "#a78bfa"},
    {"stage": "diversity_filter", "count": 421, "removed": 30, "pct_removed": 5.0, "reason": "Near-duplicate of existing demo", "color": "#C74634"},
    {"stage": "final",           "count": 421, "removed": 0,  "pct_removed": 0.0,  "reason": "Accepted",                       "color": "#22d3ee"},
]

STATS = {
    "raw_count": 600,
    "final_count": 421,
    "total_rejected": 179,
    "rejection_rate_pct": 29.8,
    "sr_unfiltered": 0.61,
    "sr_filtered": 0.78,
    "sr_improvement_pp": 17.0,
    "throughput_demos_per_min": 142,
    "avg_quality_score_before": 0.58,
    "avg_quality_score_after": 0.79,
}


def _quality_scores(n: int, rejected: bool) -> List[float]:
    """Generate mock quality score samples."""
    scores = []
    if rejected:
        for _ in range(n):
            # Rejected demos cluster at low quality (<0.5)
            v = random.betavariate(2, 5)
            scores.append(round(min(max(v, 0.0), 1.0), 3))
    else:
        for _ in range(n):
            # Accepted demos peak at 0.7-0.9
            v = random.betavariate(6, 2)
            scores.append(round(min(max(v, 0.0), 1.0), 3))
    return scores


def _histogram(scores: List[float], bins: int = 20) -> List[int]:
    counts = [0] * bins
    for s in scores:
        idx = min(int(s * bins), bins - 1)
        counts[idx] += 1
    return counts


def _svg_funnel() -> str:
    """SVG: Filter pipeline funnel showing demo counts at each stage."""
    W, H = 620, 340
    stages = FILTER_PIPELINE
    n = len(stages)
    PAD_T, PAD_B, PAD_L, PAD_R = 50, 55, 80, 80
    slot_h = (H - PAD_T - PAD_B) / n
    max_count = stages[0]["count"]
    max_bar_w = W - PAD_L - PAD_R

    bars = ""
    for i, s in enumerate(stages):
        bar_w = (s["count"] / max_count) * max_bar_w
        x0 = PAD_L + (max_bar_w - bar_w) / 2
        y0 = PAD_T + i * slot_h + slot_h * 0.15
        bh = slot_h * 0.60
        bars += f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" rx="4" fill="{s["color"]}" opacity="0.85"/>'
        label_x = PAD_L + max_bar_w / 2
        label_y = y0 + bh / 2 + 5
        bars += f'<text x="{label_x:.1f}" y="{label_y:.1f}" fill="#0f172a" font-size="12" font-weight="700" text-anchor="middle">{s["count"]} demos</text>'
        # Stage name left
        bars += f'<text x="{PAD_L - 6}" y="{y0 + bh / 2 + 5:.1f}" fill="#e2e8f0" font-size="9" text-anchor="end">{s["stage"]}</text>'
        # Rejection right
        if s["removed"] > 0:
            bars += (
                f'<text x="{PAD_L + max_bar_w + 6}" y="{y0 + bh / 2 + 5:.1f}" '
                f'fill="#ef4444" font-size="9">-{s["removed"]} ({s["pct_removed"]:.1f}%)</text>'
            )
            bars += (
                f'<text x="{PAD_L + max_bar_w + 6}" y="{y0 + bh / 2 + 16:.1f}" '
                f'fill="#64748b" font-size="8">{s["reason"]}</text>'
            )

    # Connector lines between bars
    connectors = ""
    for i in range(n - 1):
        s1, s2 = stages[i], stages[i + 1]
        w1 = (s1["count"] / max_count) * max_bar_w
        w2 = (s2["count"] / max_count) * max_bar_w
        x1_left = PAD_L + (max_bar_w - w1) / 2
        x1_right = x1_left + w1
        x2_left = PAD_L + (max_bar_w - w2) / 2
        x2_right = x2_left + w2
        y1 = PAD_T + (i + 1) * slot_h * 0.75 + i * slot_h * 0.15
        y2 = PAD_T + (i + 1) * slot_h + (i + 1) * slot_h * 0.15
        connectors += (
            f'<polygon points="{x1_left:.1f},{y1:.1f} {x1_right:.1f},{y1:.1f} {x2_right:.1f},{y2:.1f} {x2_left:.1f},{y2:.1f}" '
            f'fill="{stages[i]["color"]}" opacity="0.20"/>'
        )

    title = f'<text x="{W // 2}" y="30" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">Demo Quality Filter Pipeline — Funnel</text>'
    subtitle = f'<text x="{W // 2}" y="44" fill="#64748b" font-size="9" text-anchor="middle">600 raw → 421 high-quality (29.8% rejection)</text>'

    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">'
        + title + subtitle + connectors + bars
        + "</svg>"
    )


def _svg_histogram() -> str:
    """SVG: Quality score distribution before vs after filtering."""
    W, H = 560, 300
    PAD_L, PAD_R, PAD_T, PAD_B = 50, 20, 40, 50
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B
    bins = 20

    all_before = _quality_scores(600, rejected=False)[:421] + _quality_scores(179, rejected=True)
    after_scores = _quality_scores(421, rejected=False)

    before_hist = _histogram(all_before, bins)
    after_hist = _histogram(after_scores, bins)

    max_count = max(max(before_hist), max(after_hist))
    bar_w = plot_w / bins

    bars_before = ""
    bars_after = ""
    for i in range(bins):
        x = PAD_L + i * bar_w
        h_before = (before_hist[i] / max_count) * plot_h if max_count else 0
        h_after = (after_hist[i] / max_count) * plot_h if max_count else 0
        y_before = PAD_T + plot_h - h_before
        y_after = PAD_T + plot_h - h_after
        bars_before += f'<rect x="{x:.1f}" y="{y_before:.1f}" width="{bar_w * 0.85:.1f}" height="{h_before:.1f}" fill="#64748b" opacity="0.55"/>'
        bars_after += f'<rect x="{x + bar_w * 0.1:.1f}" y="{y_after:.1f}" width="{bar_w * 0.75:.1f}" height="{h_after:.1f}" fill="#C74634" opacity="0.80"/>'

    # Threshold line at 0.5
    thresh_x = PAD_L + 0.5 * plot_w
    threshold = (
        f'<line x1="{thresh_x:.1f}" y1="{PAD_T}" x2="{thresh_x:.1f}" y2="{PAD_T + plot_h}" '
        f'stroke="#ef4444" stroke-width="1.5" stroke-dasharray="5,4"/>'
        f'<text x="{thresh_x + 4}" y="{PAD_T + 16}" fill="#ef4444" font-size="9">filter threshold (0.5)</text>'
    )

    axes = (
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T + plot_h}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{PAD_L}" y1="{PAD_T + plot_h}" x2="{PAD_L + plot_w}" y2="{PAD_T + plot_h}" stroke="#475569" stroke-width="1"/>'
    )

    xticks = ""
    for v in [0.0, 0.25, 0.5, 0.75, 1.0]:
        xx = PAD_L + v * plot_w
        xticks += f'<text x="{xx:.1f}" y="{PAD_T + plot_h + 15}" fill="#94a3b8" font-size="9" text-anchor="middle">{v:.2f}</text>'
        xticks += f'<line x1="{xx:.1f}" y1="{PAD_T + plot_h}" x2="{xx:.1f}" y2="{PAD_T + plot_h + 4}" stroke="#475569" stroke-width="1"/>'

    legend = (
        f'<rect x="{PAD_L + 10}" y="{PAD_T + 10}" width="12" height="10" fill="#64748b" opacity="0.55"/>'
        f'<text x="{PAD_L + 26}" y="{PAD_T + 20}" fill="#94a3b8" font-size="9">Before filtering (n=600)</text>'
        f'<rect x="{PAD_L + 160}" y="{PAD_T + 10}" width="12" height="10" fill="#C74634" opacity="0.80"/>'
        f'<text x="{PAD_L + 176}" y="{PAD_T + 20}" fill="#94a3b8" font-size="9">After filtering (n=421)</text>'
    )

    title = f'<text x="{W // 2}" y="24" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="middle">Quality Score Distribution: Before vs After Filtering</text>'
    xlabel = f'<text x="{PAD_L + plot_w // 2}" y="{H - 6}" fill="#94a3b8" font-size="9" text-anchor="middle">Quality Score</text>'
    ylabel = f'<text x="12" y="{PAD_T + plot_h // 2}" fill="#94a3b8" font-size="9" text-anchor="middle" transform="rotate(-90 12 {PAD_T + plot_h // 2})">Demo Count</text>'

    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">'
        + title + axes + xticks + bars_before + bars_after + threshold + legend + xlabel + ylabel
        + "</svg>"
    )


def _build_html() -> str:
    svg1 = _svg_funnel()
    svg2 = _svg_histogram()

    stage_rows = ""
    for s in FILTER_PIPELINE:
        pct_remain = s["count"] / FILTER_PIPELINE[0]["count"] * 100
        stage_rows += (
            f'<tr style="border-bottom:1px solid #0f172a;">'
            f'<td style="padding:8px 12px;"><span style="color:{s["color"]};">{s["stage"]}</span></td>'
            f'<td style="padding:8px 12px;text-align:right;">{s["count"]}</td>'
            f'<td style="padding:8px 12px;text-align:right;color:#ef4444;">'
            + (f'-{s["removed"]} ({s["pct_removed"]:.1f}%)' if s["removed"] else '—') +
            f'</td>'
            f'<td style="padding:8px 12px;text-align:right;color:#94a3b8;">{pct_remain:.1f}%</td>'
            f'<td style="padding:8px 12px;color:#64748b;">{s["reason"]}</td>'
            f'</tr>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Demo Quality Filter — Port 8313</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .subtitle {{ color: #94a3b8; font-size: 0.85rem; margin-bottom: 24px; }}
    .badge {{ background: #1e3a5f; color: #38bdf8; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-left: 8px; }}
    .section {{ background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
    .section h2 {{ color: #38bdf8; font-size: 1rem; margin-bottom: 14px; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}
    .kpi {{ background: #1e293b; border-radius: 8px; padding: 14px 18px; border-left: 3px solid #C74634; }}
    .kpi .val {{ font-size: 1.7rem; font-weight: 700; color: #C74634; }}
    .kpi .lbl {{ font-size: 0.75rem; color: #94a3b8; margin-top: 2px; }}
    .kpi.blue {{ border-left-color: #38bdf8; }}
    .kpi.blue .val {{ color: #38bdf8; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    th {{ background: #0f172a; color: #94a3b8; padding: 8px 12px; text-align: left; font-weight: 600; }}
    tr:hover {{ background: #0f172a44; }}
    .svgs {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  </style>
</head>
<body>
  <h1>Demo Quality Filter <span class="badge">Port 8313</span></h1>
  <p class="subtitle">Multi-stage quality filter for teleoperation demonstrations before training — OCI Robot Cloud</p>

  <div class="kpi-grid">
    <div class="kpi"><div class="val">29.8%</div><div class="lbl">Overall Rejection Rate (179/600)</div></div>
    <div class="kpi blue"><div class="val">421</div><div class="lbl">Final High-Quality Demos</div></div>
    <div class="kpi"><div class="val">+17pp</div><div class="lbl">SR Improvement (0.61 → 0.78)</div></div>
    <div class="kpi blue"><div class="val">142/min</div><div class="lbl">Filter Throughput</div></div>
  </div>

  <div class="section">
    <h2>SVG 1 — Filter Pipeline Funnel (600 → 421 demos)</h2>
    <div class="svgs">{svg1}</div>
    <p style="color:#64748b;font-size:0.75rem;margin-top:8px;">Each stage narrows the dataset. Largest drop: success_filter (-9.6%). Total pipeline reduces noise by 29.8%.</p>
  </div>

  <div class="section">
    <h2>SVG 2 — Quality Score Distribution (Before vs After Filtering)</h2>
    <div class="svgs">{svg2}</div>
    <p style="color:#64748b;font-size:0.75rem;margin-top:8px;">Rejected demos cluster at scores &lt;0.5. Accepted demos peak 0.7–0.9. Mean quality: 0.58 → 0.79 after filtering.</p>
  </div>

  <div class="section">
    <h2>Filter Stage Breakdown</h2>
    <table>
      <thead><tr>
        <th>Stage</th><th style="text-align:right;">Demos Remaining</th><th style="text-align:right;">Removed</th>
        <th style="text-align:right;">Remaining %</th><th>Rejection Reason</th>
      </tr></thead>
      <tbody>{stage_rows}</tbody>
    </table>
  </div>
</body>
</html>"""


if USE_FASTAPI:
    app = FastAPI(title="Demo Quality Filter", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "demo_quality_filter", "port": 8313}

    @app.get("/api/pipeline")
    async def pipeline():
        return FILTER_PIPELINE

    @app.get("/api/stats")
    async def stats():
        return STATS

else:
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
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
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8313)
    else:
        with socketserver.TCPServer(("", 8313), Handler) as srv:
            print("Serving on http://0.0.0.0:8313 (stdlib fallback)")
            srv.serve_forever()

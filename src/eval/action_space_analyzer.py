"""Action Space Analyzer — FastAPI service on port 8226.

Analyzes GR00T action chunk distribution and coverage for manipulation tasks.
Provides SVG visualizations of chunk centroids and diversity score distribution.
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
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── Reproducible mock data ────────────────────────────────────────────────────
random.seed(42)

NUM_CHUNKS = 500
PHASES = ["reach", "grasp", "lift"]

# Phase proportions: reach 40%, grasp 35%, lift 25%
_phase_counts = {"reach": 200, "grasp": 175, "lift": 125}

# Phase centres in (gripper_delta, ee_z_delta) space
_centres = {
    "reach": (0.05, 0.12),
    "grasp": (0.42, 0.04),   # most clustered
    "lift":  (0.38, 0.55),
}
_spread = {"reach": 0.14, "grasp": 0.06, "lift": 0.11}

def _make_chunks():
    chunks = []
    for phase, n in _phase_counts.items():
        cx, cy = _centres[phase]
        s = _spread[phase]
        for _ in range(n):
            x = cx + random.gauss(0, s)
            y = cy + random.gauss(0, s)
            # diversity score: grasp phase gets lower scores
            if phase == "grasp":
                div = max(0.0, min(1.0, random.gauss(0.38, 0.12)))
            elif phase == "reach":
                div = max(0.0, min(1.0, random.gauss(0.68, 0.14)))
            else:
                div = max(0.0, min(1.0, random.gauss(0.72, 0.13)))
            chunks.append({"phase": phase, "gd": x, "ez": y, "div": div})
    random.shuffle(chunks)
    return chunks

ALL_CHUNKS = _make_chunks()

# Deduplication: mark 18% as deduplicated (mostly from grasp)
DEDUP_THRESHOLD = 0.30
DEDUP_RATE = 0.18
_dedup_candidates = [i for i, c in enumerate(ALL_CHUNKS) if c["div"] < DEDUP_THRESHOLD]
random.shuffle(_dedup_candidates)
_n_dedup = int(NUM_CHUNKS * DEDUP_RATE)
_dedup_set = set(_dedup_candidates[:_n_dedup])
for i, c in enumerate(ALL_CHUNKS):
    c["deduped"] = i in _dedup_set

KEPT_CHUNKS = [c for c in ALL_CHUNKS if not c["deduped"]]

# Key metrics
ACTION_COVERAGE_SCORE = 0.847
PHASE_BALANCE_RATIO = 0.73
CHUNK_DEDUP_RATE = _n_dedup / NUM_CHUNKS
DIVERSITY_MEAN_PRE = sum(c["div"] for c in ALL_CHUNKS) / len(ALL_CHUNKS)
DIVERSITY_MEAN_POST = sum(c["div"] for c in KEPT_CHUNKS) / len(KEPT_CHUNKS)


# ── SVG helpers ───────────────────────────────────────────────────────────────

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _scatter_svg(chunks, width=560, height=380):
    """2D scatter plot: x=gripper_delta, y=ee_z_delta, colour by phase."""
    pad_l, pad_r, pad_t, pad_b = 52, 20, 20, 44
    pw = width - pad_l - pad_r
    ph = height - pad_t - pad_b

    # Data range
    xs = [c["gd"] for c in chunks]
    ys = [c["ez"] for c in chunks]
    xmin, xmax = min(xs) - 0.05, max(xs) + 0.05
    ymin, ymax = min(ys) - 0.05, max(ys) + 0.05

    def tx(v): return pad_l + (v - xmin) / (xmax - xmin) * pw
    def ty(v): return pad_t + ph - (v - ymin) / (ymax - ymin) * ph

    COLORS = {"reach": "#38bdf8", "grasp": "#f59e0b", "lift": "#22c55e"}

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#1e293b;border-radius:8px">')

    # Coverage ellipses per phase
    for phase, colour in COLORS.items():
        pts = [c for c in chunks if c["phase"] == phase]
        if not pts:
            continue
        px = [c["gd"] for c in pts]
        py = [c["ez"] for c in pts]
        mx = sum(px) / len(px)
        my = sum(py) / len(py)
        sx = math.sqrt(sum((v - mx) ** 2 for v in px) / len(px))
        sy = math.sqrt(sum((v - my) ** 2 for v in py) / len(py))
        # 1.5-sigma ellipse
        rx = tx(mx + 1.5 * sx) - tx(mx)
        ry = ty(my - 1.5 * sy) - ty(my)
        lines.append(
            f'<ellipse cx="{tx(mx):.1f}" cy="{ty(my):.1f}" '
            f'rx="{abs(rx):.1f}" ry="{abs(ry):.1f}" '
            f'fill="{colour}" fill-opacity="0.08" stroke="{colour}" '
            f'stroke-width="1.5" stroke-dasharray="4 2"/>'
        )

    # Scatter points
    for c in chunks:
        col = COLORS[c["phase"]]
        opacity = 0.35 if c.get("deduped") else 0.75
        lines.append(
            f'<circle cx="{tx(c["gd"]):.1f}" cy="{ty(c["ez"]):.1f}" r="2.8" '
            f'fill="{col}" fill-opacity="{opacity}"/>'
        )

    # Axes
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+ph}" x2="{pad_l+pw}" y2="{pad_t+ph}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+ph}" stroke="#475569" stroke-width="1"/>')

    # Axis labels
    lines.append(f'<text x="{pad_l + pw//2}" y="{height-6}" fill="#94a3b8" font-size="11" text-anchor="middle" font-family="monospace">Gripper Delta</text>')
    lines.append(f'<text x="12" y="{pad_t + ph//2}" fill="#94a3b8" font-size="11" text-anchor="middle" font-family="monospace" transform="rotate(-90 12 {pad_t+ph//2})">EE Z Delta</text>')

    # Title
    lines.append(f'<text x="{width//2}" y="14" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle" font-family="monospace">Action Chunk Centroids — DAgger Run10 (n=500)</text>')

    # Legend
    legend_items = [("reach", "#38bdf8"), ("grasp", "#f59e0b"), ("lift", "#22c55e")]
    lx = pad_l
    for label, col in legend_items:
        lines.append(f'<rect x="{lx}" y="{height-20}" width="10" height="10" fill="{col}" rx="2"/>')
        lines.append(f'<text x="{lx+13}" y="{height-11}" fill="#94a3b8" font-size="10" font-family="monospace">{label}</text>')
        lx += 72

    lines.append('</svg>')
    return "\n".join(lines)


def _histogram_svg(chunks, kept, width=560, height=320):
    """Histogram of diversity score pre and post deduplication."""
    pad_l, pad_r, pad_t, pad_b = 52, 20, 24, 44
    pw = width - pad_l - pad_r
    ph = height - pad_t - pad_b

    N_BINS = 20
    bin_edges = [i / N_BINS for i in range(N_BINS + 1)]

    def _hist(items):
        counts = [0] * N_BINS
        for c in items:
            b = _clamp(int(c["div"] * N_BINS), 0, N_BINS - 1)
            counts[b] += 1
        return counts

    pre_counts = _hist(chunks)
    post_counts = _hist(kept)
    max_count = max(max(pre_counts), max(post_counts), 1)

    bar_w = pw / N_BINS
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#1e293b;border-radius:8px">')

    # Grid
    for gi in range(0, 6):
        gy = pad_t + ph - gi * ph / 5
        lines.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l+pw}" y2="{gy:.1f}" stroke="#1e3a5f" stroke-width="1"/>')
        val = int(max_count * gi / 5)
        lines.append(f'<text x="{pad_l-4}" y="{gy+4:.1f}" fill="#64748b" font-size="9" text-anchor="end" font-family="monospace">{val}</text>')

    # Pre-dedup bars
    for b, cnt in enumerate(pre_counts):
        bh = cnt / max_count * ph
        bx = pad_l + b * bar_w
        by = pad_t + ph - bh
        lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w*0.45:.1f}" height="{bh:.1f}" fill="#38bdf8" fill-opacity="0.6"/>')

    # Post-dedup bars
    for b, cnt in enumerate(post_counts):
        bh = cnt / max_count * ph
        bx = pad_l + b * bar_w + bar_w * 0.48
        by = pad_t + ph - bh
        lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w*0.45:.1f}" height="{bh:.1f}" fill="#22c55e" fill-opacity="0.7"/>')

    # Diversity threshold line
    thresh_x = pad_l + DEDUP_THRESHOLD * pw
    lines.append(f'<line x1="{thresh_x:.1f}" y1="{pad_t}" x2="{thresh_x:.1f}" y2="{pad_t+ph}" stroke="#C74634" stroke-width="1.5" stroke-dasharray="4 3"/>')
    lines.append(f'<text x="{thresh_x+3:.1f}" y="{pad_t+14}" fill="#C74634" font-size="9" font-family="monospace">dedup threshold</text>')

    # X axis ticks
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+ph}" x2="{pad_l+pw}" y2="{pad_t+ph}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+ph}" stroke="#475569" stroke-width="1"/>')
    for v in [0.0, 0.25, 0.50, 0.75, 1.0]:
        tx = pad_l + v * pw
        lines.append(f'<text x="{tx:.1f}" y="{pad_t+ph+14}" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="monospace">{v:.2f}</text>')

    lines.append(f'<text x="{pad_l+pw//2}" y="{height-6}" fill="#94a3b8" font-size="11" text-anchor="middle" font-family="monospace">Diversity Score</text>')
    lines.append(f'<text x="12" y="{pad_t+ph//2}" fill="#94a3b8" font-size="11" text-anchor="middle" font-family="monospace" transform="rotate(-90 12 {pad_t+ph//2})">Count</text>')
    lines.append(f'<text x="{width//2}" y="16" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle" font-family="monospace">Chunk Diversity Score — Pre vs Post Deduplication</text>')

    # Legend
    lines.append(f'<rect x="{pad_l}" y="{height-20}" width="10" height="10" fill="#38bdf8" fill-opacity="0.6" rx="2"/>')
    lines.append(f'<text x="{pad_l+13}" y="{height-11}" fill="#94a3b8" font-size="10" font-family="monospace">pre-dedup (n={len(chunks)})</text>')
    lines.append(f'<rect x="{pad_l+130}" y="{height-20}" width="10" height="10" fill="#22c55e" fill-opacity="0.7" rx="2"/>')
    lines.append(f'<text x="{pad_l+143}" y="{height-11}" fill="#94a3b8" font-size="10" font-family="monospace">post-dedup (n={len(kept)})</text>')
    lines.append('</svg>')
    return "\n".join(lines)


# ── HTML dashboard ────────────────────────────────────────────────────────────

def build_html():
    scatter = _scatter_svg(ALL_CHUNKS)
    hist = _histogram_svg(ALL_CHUNKS, KEPT_CHUNKS)
    phase_dist = {p: sum(1 for c in ALL_CHUNKS if c["phase"] == p) for p in PHASES}
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Action Space Analyzer — Port 8226</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', monospace; min-height: 100vh; }}
    header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 16px 32px;
              display: flex; align-items: center; gap: 16px; }}
    header h1 {{ font-size: 1.3rem; color: #f8fafc; }}
    header span {{ background: #C74634; color: #fff; font-size: 0.7rem; padding: 2px 8px;
                   border-radius: 4px; letter-spacing: 1px; }}
    .metrics {{ display: flex; gap: 16px; padding: 24px 32px 0; flex-wrap: wrap; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
             padding: 16px 20px; min-width: 160px; flex: 1; }}
    .card .label {{ font-size: 0.72rem; color: #64748b; text-transform: uppercase;
                    letter-spacing: 1px; margin-bottom: 6px; }}
    .card .value {{ font-size: 1.6rem; font-weight: 700; color: #38bdf8; }}
    .card .sub {{ font-size: 0.72rem; color: #64748b; margin-top: 4px; }}
    .charts {{ display: flex; flex-wrap: wrap; gap: 24px; padding: 24px 32px; }}
    .chart-box {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
                  padding: 16px; flex: 1; min-width: 300px; }}
    .chart-box h2 {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 12px;
                     text-transform: uppercase; letter-spacing: 1px; }}
    .phase-table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; margin-top: 8px; }}
    .phase-table th {{ color: #64748b; font-weight: 600; padding: 6px 10px; text-align: left;
                        border-bottom: 1px solid #334155; }}
    .phase-table td {{ padding: 6px 10px; border-bottom: 1px solid #1e293b; }}
    .reach {{ color: #38bdf8; }} .grasp {{ color: #f59e0b; }} .lift {{ color: #22c55e; }}
    footer {{ text-align: center; color: #334155; font-size: 0.7rem; padding: 16px;
              border-top: 1px solid #1e293b; margin-top: 8px; }}
  </style>
</head>
<body>
<header>
  <h1>Action Space Analyzer</h1>
  <span>PORT 8226</span>
  <span style="background:#334155">GR00T CHUNK ANALYSIS</span>
</header>

<div class="metrics">
  <div class="card">
    <div class="label">Action Coverage Score</div>
    <div class="value">{ACTION_COVERAGE_SCORE:.3f}</div>
    <div class="sub">across 500 chunks</div>
  </div>
  <div class="card">
    <div class="label">Phase Balance Ratio</div>
    <div class="value" style="color:#22c55e">{PHASE_BALANCE_RATIO:.2f}</div>
    <div class="sub">reach/grasp/lift</div>
  </div>
  <div class="card">
    <div class="label">Chunk Dedup Rate</div>
    <div class="value" style="color:#C74634">{CHUNK_DEDUP_RATE*100:.0f}%</div>
    <div class="sub">{_n_dedup} of {NUM_CHUNKS} removed</div>
  </div>
  <div class="card">
    <div class="label">Diversity Mean</div>
    <div class="value" style="color:#f59e0b">{DIVERSITY_MEAN_PRE:.2f} → {DIVERSITY_MEAN_POST:.2f}</div>
    <div class="sub">pre → post dedup</div>
  </div>
  <div class="card">
    <div class="label">Chunks Kept</div>
    <div class="value">{len(KEPT_CHUNKS)}</div>
    <div class="sub">high-diversity set</div>
  </div>
</div>

<div class="charts">
  <div class="chart-box">
    <h2>Chunk Centroid Map — Gripper Delta × EE Z Delta</h2>
    {scatter}
    <table class="phase-table" style="margin-top:12px">
      <tr><th>Phase</th><th>Count</th><th>Spread (σ)</th><th>Colour</th></tr>
      <tr><td class="reach">reach</td><td>{phase_dist['reach']}</td><td>±0.14</td><td class="reach">sky blue</td></tr>
      <tr><td class="grasp">grasp</td><td>{phase_dist['grasp']}</td><td>±0.06</td><td class="grasp">amber (most clustered)</td></tr>
      <tr><td class="lift">lift</td><td>{phase_dist['lift']}</td><td>±0.11</td><td class="lift">green</td></tr>
    </table>
  </div>
  <div class="chart-box">
    <h2>Chunk Diversity Score Distribution</h2>
    {hist}
    <p style="font-size:0.78rem;color:#64748b;margin-top:10px">
      Dedup threshold at <span style="color:#C74634">0.30</span> — chunks below are removed.
      Grasp phase dominates the low-diversity tail due to repeated close-approach motions.
    </p>
  </div>
</div>

<footer>OCI Robot Cloud · Action Space Analyzer · port 8226 · GR00T N1.6 DAgger run10</footer>
</body>
</html>"""


# ── FastAPI app ───────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="Action Space Analyzer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/metrics")
    async def metrics():
        return {
            "action_coverage_score": ACTION_COVERAGE_SCORE,
            "phase_balance_ratio": PHASE_BALANCE_RATIO,
            "chunk_dedup_rate": round(CHUNK_DEDUP_RATE, 4),
            "diversity_mean_pre": round(DIVERSITY_MEAN_PRE, 4),
            "diversity_mean_post": round(DIVERSITY_MEAN_POST, 4),
            "total_chunks": NUM_CHUNKS,
            "chunks_kept": len(KEPT_CHUNKS),
            "chunks_deduped": _n_dedup,
            "phase_distribution": {p: sum(1 for c in ALL_CHUNKS if c["phase"] == p) for p in PHASES},
        }

    @app.get("/chunks")
    async def chunks(limit: int = 50, phase: str = None):
        data = ALL_CHUNKS
        if phase:
            data = [c for c in data if c["phase"] == phase]
        return {"chunks": data[:limit], "total": len(data)}

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8226, "service": "action_space_analyzer"}


# ── Stdlib fallback ───────────────────────────────────────────────────────────

class _FallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = build_html().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # suppress default logging


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8226)
    else:
        print("[action_space_analyzer] FastAPI not available — using stdlib HTTP on port 8226")
        HTTPServer(("0.0.0.0", 8226), _FallbackHandler).serve_forever()

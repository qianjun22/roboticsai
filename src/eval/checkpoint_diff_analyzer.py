"""checkpoint_diff_analyzer.py — FastAPI service on port 8208.

Dashboard showing checkpoint comparison: model weights diff between
consecutive checkpoints with per-layer weight change magnitude and
a heatmap of layer-wise divergence.
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

# ── Mock data ───────────────────────────────────────────────────────────────
random.seed(42)

LAYERS = ["embed", "attn_1", "attn_2", "attn_3", "attn_4",
          "ffn_1", "ffn_2", "ffn_3", "ffn_4", "proj_1", "proj_2", "head"]
N_CHECKPOINTS = 8
N_LAYERS = len(LAYERS)

# Simulate weight deltas — early checkpoints have large changes, later ones converge
def _make_deltas():
    deltas = []
    for ck in range(N_CHECKPOINTS):
        decay = math.exp(-ck * 0.35)
        row = []
        for li, _ in enumerate(LAYERS):
            # embed and head change less; attention layers change most early
            layer_factor = 1.4 if "attn" in LAYERS[li] else (0.6 if LAYERS[li] in ("embed", "head") else 1.0)
            noise = random.gauss(0, 0.02)
            val = max(0.0, decay * layer_factor * random.uniform(0.05, 0.45) + noise)
            row.append(round(val, 4))
        deltas.append(row)
    return deltas

DELTAS = _make_deltas()

# Key metrics derived from mock data
def _key_metrics():
    flat = [(LAYERS[li], DELTAS[ck][li], ck) for ck in range(N_CHECKPOINTS) for li in range(N_LAYERS)]
    max_entry = max(flat, key=lambda x: x[1])
    # convergence trend: last 3 checkpoints avg delta vs first 3
    early_avg = sum(sum(DELTAS[ck]) for ck in range(3)) / (3 * N_LAYERS)
    late_avg  = sum(sum(DELTAS[ck]) for ck in range(5, 8)) / (3 * N_LAYERS)
    plateau_ck = 5  # checkpoint index where slope flattened
    return {
        "max_delta_layer": max_entry[0],
        "max_delta_value": round(max_entry[1], 4),
        "max_delta_checkpoint": max_entry[2],
        "convergence_ratio": round(late_avg / early_avg, 3),
        "plateau_checkpoint": plateau_ck,
        "early_avg_delta": round(early_avg, 4),
        "late_avg_delta":  round(late_avg, 4),
    }

METRICS = _key_metrics()

# ── SVG helpers ─────────────────────────────────────────────────────────────
def _svg_line_chart() -> str:
    """Line chart: per-layer weight change magnitude, one line per checkpoint."""
    W, H = 700, 340
    PAD = {"top": 40, "right": 30, "bottom": 60, "left": 60}
    plot_w = W - PAD["left"] - PAD["right"]
    plot_h = H - PAD["top"]  - PAD["bottom"]

    max_val = max(v for row in DELTAS for v in row)

    def sx(li): return PAD["left"] + li * plot_w / (N_LAYERS - 1)
    def sy(v):  return PAD["top"] + plot_h * (1 - v / max_val)

    COLORS = ["#38bdf8", "#818cf8", "#34d399", "#fbbf24",
              "#f87171", "#e879f9", "#fb923c", "#a3e635"]

    lines = []
    for ck in range(N_CHECKPOINTS):
        pts = " ".join(f"{sx(li):.1f},{sy(DELTAS[ck][li]):.1f}" for li in range(N_LAYERS))
        lines.append(f'<polyline points="{pts}" fill="none" stroke="{COLORS[ck]}" stroke-width="2" opacity="0.85"/>')
        # dot at last point for legend anchor
        lx, ly = sx(N_LAYERS - 1), sy(DELTAS[ck][N_LAYERS - 1])
        lines.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="{COLORS[ck]}"/>')

    # axes
    axes = [
        f'<line x1="{PAD["left"]}" y1="{PAD["top"]}" x2="{PAD["left"]}" y2="{PAD["top"]+plot_h}" stroke="#334155" stroke-width="1"/>',
        f'<line x1="{PAD["left"]}" y1="{PAD["top"]+plot_h}" x2="{PAD["left"]+plot_w}" y2="{PAD["top"]+plot_h}" stroke="#334155" stroke-width="1"/>',
    ]

    # x-axis labels
    xlabels = []
    for li, lname in enumerate(LAYERS):
        x = sx(li)
        xlabels.append(f'<text x="{x:.1f}" y="{PAD["top"]+plot_h+18}" text-anchor="middle" font-size="10" fill="#94a3b8" transform="rotate(-35 {x:.1f},{PAD["top"]+plot_h+18})">{lname}</text>')

    # y-axis labels
    ylabels = []
    for i in range(5):
        v = max_val * i / 4
        y = sy(v)
        ylabels.append(f'<text x="{PAD["left"]-8}" y="{y:.1f}" text-anchor="end" font-size="10" fill="#94a3b8" dominant-baseline="middle">{v:.2f}</text>')
        ylabels.append(f'<line x1="{PAD["left"]}" y1="{y:.1f}" x2="{PAD["left"]+plot_w}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1" stroke-dasharray="3,3"/>')

    # legend
    legend = []
    for ck in range(N_CHECKPOINTS):
        lx = PAD["left"] + (ck % 4) * 160
        ly = H - 12 + (ck // 4) * 14
        legend.append(f'<rect x="{lx}" y="{ly-7}" width="12" height="4" fill="{COLORS[ck]}"/>')
        legend.append(f'<text x="{lx+16}" y="{ly}" font-size="10" fill="#cbd5e1">ckpt-{ck}</text>')

    title = f'<text x="{W//2}" y="22" text-anchor="middle" font-size="14" font-weight="bold" fill="#f1f5f9">Per-Layer Weight Change Magnitude (\u0394W) Across Checkpoints</text>'
    ylabel = f'<text x="16" y="{H//2}" text-anchor="middle" font-size="11" fill="#94a3b8" transform="rotate(-90 16 {H//2})">\u0394W magnitude</text>'

    inner = "\n".join(axes + ylabels + xlabels + lines + legend + [title, ylabel])
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">\n{inner}\n</svg>'


def _svg_heatmap() -> str:
    """Heatmap: rows=checkpoints, cols=layers, color intensity=delta magnitude."""
    CELL_W, CELL_H = 52, 34
    PAD_LEFT, PAD_TOP = 70, 50
    W = PAD_LEFT + N_LAYERS * CELL_W + 30
    H = PAD_TOP  + N_CHECKPOINTS * CELL_H + 40

    max_val = max(v for row in DELTAS for v in row)

    def heat_color(v):
        t = v / max_val
        # dark blue → sky blue → orange-red (Oracle)
        if t < 0.5:
            r = int(15  + t * 2 * (56  - 15))
            g = int(23  + t * 2 * (189 - 23))
            b = int(42  + t * 2 * (248 - 42))
        else:
            tt = (t - 0.5) * 2
            r = int(56  + tt * (199 - 56))
            g = int(189 + tt * (70  - 189))
            b = int(248 + tt * (52  - 248))
        return f"rgb({r},{g},{b})"

    cells = []
    for ck in range(N_CHECKPOINTS):
        for li in range(N_LAYERS):
            x = PAD_LEFT + li * CELL_W
            y = PAD_TOP  + ck * CELL_H
            color = heat_color(DELTAS[ck][li])
            cells.append(f'<rect x="{x}" y="{y}" width="{CELL_W-2}" height="{CELL_H-2}" fill="{color}" rx="2"/>')
            cells.append(f'<text x="{x+CELL_W//2-1}" y="{y+CELL_H//2+5}" text-anchor="middle" font-size="9" fill="#0f172a" font-weight="bold">{DELTAS[ck][li]:.2f}</text>')

    # row labels
    row_labels = []
    for ck in range(N_CHECKPOINTS):
        y = PAD_TOP + ck * CELL_H + CELL_H // 2
        row_labels.append(f'<text x="{PAD_LEFT-6}" y="{y+4}" text-anchor="end" font-size="11" fill="#94a3b8">ckpt-{ck}</text>')

    # col labels
    col_labels = []
    for li, lname in enumerate(LAYERS):
        x = PAD_LEFT + li * CELL_W + CELL_W // 2 - 1
        col_labels.append(f'<text x="{x}" y="{PAD_TOP-10}" text-anchor="middle" font-size="10" fill="#94a3b8" transform="rotate(-30 {x} {PAD_TOP-10})">{lname}</text>')

    title = f'<text x="{W//2}" y="22" text-anchor="middle" font-size="14" font-weight="bold" fill="#f1f5f9">Layer-Wise Divergence Heatmap (Checkpoints \u00d7 Layers)</text>'

    inner = "\n".join(cells + row_labels + col_labels + [title])
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">\n{inner}\n</svg>'


# ── HTML page ────────────────────────────────────────────────────────────────
def _build_html() -> str:
    line_svg = _svg_line_chart()
    heat_svg = _svg_heatmap()
    m = METRICS
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Checkpoint Diff Analyzer | Port 8208</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
    h1{{color:#C74634;font-size:1.6rem;margin-bottom:4px}}
    .subtitle{{color:#64748b;font-size:.85rem;margin-bottom:24px}}
    .metrics{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}}
    .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px 22px;min-width:160px}}
    .card .label{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.08em}}
    .card .value{{font-size:1.5rem;font-weight:700;color:#38bdf8;margin-top:4px}}
    .card .value.red{{color:#C74634}}
    .card .value.green{{color:#34d399}}
    .section{{margin-bottom:32px}}
    .section h2{{font-size:1rem;color:#94a3b8;margin-bottom:12px;border-bottom:1px solid #1e293b;padding-bottom:6px}}
    .chart-wrap{{overflow-x:auto}}
    footer{{margin-top:32px;font-size:.75rem;color:#334155;text-align:center}}
  </style>
</head>
<body>
  <h1>Checkpoint Diff Analyzer</h1>
  <div class="subtitle">Port 8208 &nbsp;|&nbsp; {N_CHECKPOINTS} checkpoints &nbsp;&times;&nbsp; {N_LAYERS} layers &nbsp;|&nbsp; OCI Robot Cloud</div>

  <div class="metrics">
    <div class="card">
      <div class="label">Max &#916;W Layer</div>
      <div class="value red">{m['max_delta_layer']}</div>
    </div>
    <div class="card">
      <div class="label">Max &#916;W Value</div>
      <div class="value red">{m['max_delta_value']}</div>
    </div>
    <div class="card">
      <div class="label">At Checkpoint</div>
      <div class="value">ckpt-{m['max_delta_checkpoint']}</div>
    </div>
    <div class="card">
      <div class="label">Convergence Ratio</div>
      <div class="value green">{m['convergence_ratio']}&times;</div>
    </div>
    <div class="card">
      <div class="label">Plateau Starts</div>
      <div class="value">ckpt-{m['plateau_checkpoint']}</div>
    </div>
    <div class="card">
      <div class="label">Early Avg &#916;W</div>
      <div class="value">{m['early_avg_delta']}</div>
    </div>
    <div class="card">
      <div class="label">Late Avg &#916;W</div>
      <div class="value green">{m['late_avg_delta']}</div>
    </div>
  </div>

  <div class="section">
    <h2>Per-Layer Weight Change Magnitude</h2>
    <div class="chart-wrap">{line_svg}</div>
  </div>

  <div class="section">
    <h2>Layer-Wise Divergence Heatmap</h2>
    <div class="chart-wrap">{heat_svg}</div>
  </div>

  <footer>OCI Robot Cloud &mdash; Checkpoint Diff Analyzer &mdash; Port 8208</footer>
</body>
</html>
"""


# ── FastAPI app ──────────────────────────────────────────────────────────────
if USE_FASTAPI:
    app = FastAPI(title="Checkpoint Diff Analyzer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_html()

    @app.get("/api/deltas")
    async def api_deltas():
        return {"checkpoints": N_CHECKPOINTS, "layers": LAYERS, "deltas": DELTAS}

    @app.get("/api/metrics")
    async def api_metrics():
        return METRICS

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "checkpoint_diff_analyzer", "port": 8208}

else:
    # Fallback: stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # suppress default logging
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8208)
    else:
        print("FastAPI not found — falling back to stdlib http.server on port 8208")
        server = HTTPServer(("0.0.0.0", 8208), _Handler)
        print("Serving on http://0.0.0.0:8208")
        server.serve_forever()

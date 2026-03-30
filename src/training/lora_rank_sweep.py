"""LoRA Rank Sweep Service — port 8264

Sweeps LoRA rank configurations to find optimal parameter efficiency for GR00T fine-tuning.
Uses mock data; no heavy ML imports at module level.
"""

import json
import math
import random
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

LORA_CONFIGS = [
    {"rank": 4,   "sr": 0.63, "train_time_h": 1.1,  "params_m": 10.5},
    {"rank": 8,   "sr": 0.71, "train_time_h": 1.6,  "params_m": 21.0},
    {"rank": 16,  "sr": 0.78, "train_time_h": 2.4,  "params_m": 42.0},
    {"rank": 32,  "sr": 0.80, "train_time_h": 4.1,  "params_m": 84.0},
    {"rank": 64,  "sr": 0.81, "train_time_h": 6.3,  "params_m": 168.0},
    {"rank": 128, "sr": 0.81, "train_time_h": 9.1,  "params_m": 336.0},
]

OPTIMAL_RANK = 16


def _efficiency_score(cfg):
    """SR / log2(params_m) — higher is better."""
    return round(cfg["sr"] / math.log2(cfg["params_m"]), 4)


def get_summary():
    best = max(LORA_CONFIGS, key=lambda c: _efficiency_score(c))
    return {
        "optimal_rank": OPTIMAL_RANK,
        "optimal_sr": 0.78,
        "optimal_params_m": 42.0,
        "optimal_train_time_h": 2.4,
        "plateau_rank": 64,
        "efficiency_scores": [
            {"rank": c["rank"], "score": _efficiency_score(c)} for c in LORA_CONFIGS
        ],
        "best_efficiency_rank": best["rank"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_multiline_chart() -> str:
    """Multi-line chart: SR and training time vs LoRA rank (dual y-axis)."""
    W, H = 620, 320
    pad_l, pad_r, pad_t, pad_b = 60, 70, 30, 50
    inner_w = W - pad_l - pad_r
    inner_h = H - pad_t - pad_b

    ranks = [c["rank"] for c in LORA_CONFIGS]
    srs   = [c["sr"]   for c in LORA_CONFIGS]
    times = [c["train_time_h"] for c in LORA_CONFIGS]

    # x positions (log scale)
    log_ranks = [math.log2(r) for r in ranks]
    lmin, lmax = log_ranks[0], log_ranks[-1]
    def xp(r):
        return pad_l + (math.log2(r) - lmin) / (lmax - lmin) * inner_w

    # y for SR (left axis 0.5 – 0.9)
    sr_min, sr_max = 0.50, 0.90
    def ysr(v):
        return pad_t + inner_h - (v - sr_min) / (sr_max - sr_min) * inner_h

    # y for time (right axis 0 – 10h)
    t_min, t_max = 0, 10
    def yt(v):
        return pad_t + inner_h - (v - t_min) / (t_max - t_min) * inner_h

    # polyline points
    sr_pts   = " ".join(f"{xp(r):.1f},{ysr(s):.1f}" for r, s in zip(ranks, srs))
    time_pts = " ".join(f"{xp(r):.1f},{yt(t):.1f}" for r, t in zip(ranks, times))

    # gridlines
    grid = ""
    for v in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]:
        yy = ysr(v)
        grid += f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{W-pad_r}" y2="{yy:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{pad_l-6}" y="{yy+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v:.2f}</text>'
    for v in [2, 4, 6, 8, 10]:
        yy = yt(v)
        grid += f'<text x="{W-pad_r+8}" y="{yy+4:.1f}" fill="#fb923c" font-size="10">{v}h</text>'

    # x axis labels
    x_labels = ""
    for r in ranks:
        xx = xp(r)
        x_labels += f'<text x="{xx:.1f}" y="{pad_t+inner_h+18}" fill="#94a3b8" font-size="10" text-anchor="middle">r={r}</text>'

    # optimal marker
    ox = xp(OPTIMAL_RANK)
    oy = ysr(0.78)
    opt_marker = (
        f'<line x1="{ox:.1f}" y1="{pad_t}" x2="{ox:.1f}" y2="{pad_t+inner_h}" '
        f'stroke="#38bdf8" stroke-width="1" stroke-dasharray="4,3"/>'
        f'<circle cx="{ox:.1f}" cy="{oy:.1f}" r="6" fill="#38bdf8" opacity="0.9"/>'
        f'<text x="{ox+8:.1f}" y="{oy-8:.1f}" fill="#38bdf8" font-size="10">optimal r=16</text>'
    )

    svg = f'''
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;">
  <!-- grid -->
  {grid}
  <!-- axes -->
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+inner_h}" stroke="#334155" stroke-width="1.5"/>
  <line x1="{pad_l}" y1="{pad_t+inner_h}" x2="{W-pad_r}" y2="{pad_t+inner_h}" stroke="#334155" stroke-width="1.5"/>
  <line x1="{W-pad_r}" y1="{pad_t}" x2="{W-pad_r}" y2="{pad_t+inner_h}" stroke="#334155" stroke-width="1.5"/>
  <!-- x labels -->
  {x_labels}
  <!-- SR line -->
  <polyline points="{sr_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
  <!-- Time line -->
  <polyline points="{time_pts}" fill="none" stroke="#fb923c" stroke-width="2.5" stroke-dasharray="6,3"/>
  <!-- optimal marker -->
  {opt_marker}
  <!-- axis labels -->
  <text x="{pad_l-45}" y="{pad_t+inner_h//2}" fill="#38bdf8" font-size="11"
        transform="rotate(-90,{pad_l-45},{pad_t+inner_h//2})">Success Rate</text>
  <text x="{W-pad_r+55}" y="{pad_t+inner_h//2}" fill="#fb923c" font-size="11"
        transform="rotate(90,{W-pad_r+55},{pad_t+inner_h//2})">Train Time</text>
  <text x="{W//2}" y="{H-4}" fill="#94a3b8" font-size="11" text-anchor="middle">LoRA Rank (log scale)</text>
  <!-- legend -->
  <rect x="{pad_l+10}" y="{pad_t+8}" width="12" height="3" fill="#38bdf8"/>
  <text x="{pad_l+26}" y="{pad_t+14}" fill="#38bdf8" font-size="10">Success Rate</text>
  <rect x="{pad_l+110}" y="{pad_t+8}" width="12" height="3" fill="#fb923c"/>
  <text x="{pad_l+126}" y="{pad_t+14}" fill="#fb923c" font-size="10">Train Time</text>
</svg>'''
    return svg


def _svg_pareto() -> str:
    """Pareto frontier scatter: trainable params vs final SR."""
    W, H = 620, 320
    pad_l, pad_r, pad_t, pad_b = 65, 30, 30, 50
    inner_w = W - pad_l - pad_r
    inner_h = H - pad_t - pad_b

    x_min, x_max = 0, 350   # params M
    y_min, y_max = 0.58, 0.84

    def xp(v):
        return pad_l + (v - x_min) / (x_max - x_min) * inner_w

    def yp(v):
        return pad_t + inner_h - (v - y_min) / (y_max - y_min) * inner_h

    # gridlines
    grid = ""
    for v in [0.60, 0.65, 0.70, 0.75, 0.80]:
        yy = yp(v)
        grid += f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{W-pad_r}" y2="{yy:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{pad_l-6}" y="{yy+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v:.2f}</text>'
    for v in [0, 50, 100, 150, 200, 250, 300, 350]:
        xx = xp(v)
        grid += f'<text x="{xx:.1f}" y="{pad_t+inner_h+18}" fill="#94a3b8" font-size="10" text-anchor="middle">{v}M</text>'

    # pareto frontier line (connect optimal points)
    pareto_pts = " ".join(
        f"{xp(c['params_m']):.1f},{yp(c['sr']):.1f}" for c in LORA_CONFIGS
    )

    # dots
    dots = ""
    for c in LORA_CONFIGS:
        cx = xp(c["params_m"])
        cy = yp(c["sr"])
        color = "#C74634" if c["rank"] == OPTIMAL_RANK else "#38bdf8"
        dots += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="{color}" opacity="0.9"/>'
        lx = cx + 9
        ly = cy - 5
        dots += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#e2e8f0" font-size="10">r={c["rank"]}</text>'

    # optimal annotation
    oc = next(c for c in LORA_CONFIGS if c["rank"] == OPTIMAL_RANK)
    ox, oy = xp(oc["params_m"]), yp(oc["sr"])
    annotation = (
        f'<rect x="{ox-2:.1f}" y="{oy-30:.1f}" width="120" height="28" rx="4" '
        f'fill="#1e293b" stroke="#C74634" stroke-width="1"/>'
        f'<text x="{ox+3:.1f}" y="{oy-18:.1f}" fill="#C74634" font-size="10" font-weight="bold">Optimal</text>'
        f'<text x="{ox+3:.1f}" y="{oy-7:.1f}" fill="#94a3b8" font-size="9">r=16 | 0.78 SR | 42M params</text>'
    )

    svg = f'''
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;">
  {grid}
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+inner_h}" stroke="#334155" stroke-width="1.5"/>
  <line x1="{pad_l}" y1="{pad_t+inner_h}" x2="{W-pad_r}" y2="{pad_t+inner_h}" stroke="#334155" stroke-width="1.5"/>
  <polyline points="{pareto_pts}" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.5"/>
  {dots}
  {annotation}
  <text x="{W//2}" y="{H-4}" fill="#94a3b8" font-size="11" text-anchor="middle">Trainable Parameters (M)</text>
  <text x="{pad_l-50}" y="{pad_t+inner_h//2}" fill="#94a3b8" font-size="11"
        transform="rotate(-90,{pad_l-50},{pad_t+inner_h//2})">Success Rate</text>
</svg>'''
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    summary = get_summary()
    chart1  = _svg_multiline_chart()
    chart2  = _svg_pareto()

    rows = "".join(
        f"<tr><td>r={c['rank']}</td><td>{c['sr']:.2f}</td>"
        f"<td>{c['train_time_h']}h</td><td>{c['params_m']}M</td>"
        f"<td>{_efficiency_score(c)}</td>"
        f"{'<td style=color:#C74634;font-weight:700>★ Optimal</td>' if c['rank']==OPTIMAL_RANK else '<td></td>'}"
        f"</tr>"
        for c in LORA_CONFIGS
    )

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>LoRA Rank Sweep — OCI Robot Cloud</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
    h1{{color:#C74634;font-size:1.6rem;margin-bottom:4px}}
    .sub{{color:#94a3b8;font-size:.85rem;margin-bottom:24px}}
    .kpi-row{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}}
    .kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;min-width:150px}}
    .kpi .val{{font-size:1.7rem;font-weight:700;color:#38bdf8}}
    .kpi .lbl{{font-size:.75rem;color:#94a3b8;margin-top:2px}}
    .kpi.accent .val{{color:#C74634}}
    .charts{{display:flex;flex-direction:column;gap:24px;margin-bottom:28px}}
    .chart-box{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px}}
    .chart-box h2{{color:#38bdf8;font-size:.95rem;margin-bottom:12px}}
    table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
    th{{background:#0f172a;color:#94a3b8;font-size:.8rem;padding:10px 14px;text-align:left;border-bottom:1px solid #334155}}
    td{{padding:9px 14px;font-size:.85rem;border-bottom:1px solid #1a2540}}
    tr:hover td{{background:#0f172a}}
    .badge{{display:inline-block;background:#C74634;color:#fff;border-radius:4px;padding:1px 7px;font-size:.75rem}}
    footer{{margin-top:28px;color:#475569;font-size:.75rem;text-align:center}}
  </style>
</head>
<body>
  <h1>LoRA Rank Sweep</h1>
  <div class="sub">GR00T parameter efficiency analysis &mdash; port 8264 &mdash; {summary['timestamp']}</div>

  <div class="kpi-row">
    <div class="kpi accent"><div class="val">r={summary['optimal_rank']}</div><div class="lbl">Optimal Rank</div></div>
    <div class="kpi"><div class="val">{summary['optimal_sr']}</div><div class="lbl">Optimal SR</div></div>
    <div class="kpi"><div class="val">{summary['optimal_params_m']}M</div><div class="lbl">Trainable Params</div></div>
    <div class="kpi"><div class="val">{summary['optimal_train_time_h']}h</div><div class="lbl">Train Time</div></div>
    <div class="kpi"><div class="val">r={summary['plateau_rank']}</div><div class="lbl">SR Plateau Rank</div></div>
    <div class="kpi"><div class="val">+0.03</div><div class="lbl">SR gain r=16→128</div></div>
  </div>

  <div class="charts">
    <div class="chart-box">
      <h2>Success Rate &amp; Training Time vs LoRA Rank</h2>
      {chart1}
    </div>
    <div class="chart-box">
      <h2>Pareto Frontier — Trainable Parameters vs Success Rate</h2>
      {chart2}
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>LoRA Rank</th><th>Success Rate</th><th>Train Time</th>
        <th>Params</th><th>Efficiency Score</th><th>Note</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <footer>OCI Robot Cloud &mdash; LoRA Rank Sweep Service &mdash; port 8264</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="LoRA Rank Sweep",
        description="GR00T LoRA rank configuration sweep for optimal parameter efficiency",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(_build_html())

    @app.get("/api/summary")
    async def api_summary():
        return JSONResponse(get_summary())

    @app.get("/api/configs")
    async def api_configs():
        return JSONResponse(LORA_CONFIGS)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "lora_rank_sweep", "port": 8264}

else:
    # Fallback: stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/summary":
                body = json.dumps(get_summary()).encode()
                ct = "application/json"
            elif self.path == "/health":
                body = json.dumps({"status": "ok", "port": 8264}).encode()
                ct = "application/json"
            else:
                body = _build_html().encode()
                ct = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # silence default logging
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8264)
    else:
        print("[lora_rank_sweep] fastapi not found — using stdlib http.server on port 8264")
        server = HTTPServer(("0.0.0.0", 8264), _Handler)
        print("[lora_rank_sweep] Listening on http://0.0.0.0:8264")
        server.serve_forever()

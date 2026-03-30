"""Object Permanence Tracker — FastAPI service on port 8305.

Tracks object state persistence across task phases to measure
scene understanding in robot manipulation policies.
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

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

EPISODE_LENGTH = 847

# Phase boundaries (step indices)
PHASES = [
    {"name": "reach", "start": 0, "end": 210, "color": "#38bdf8"},
    {"name": "grasp", "start": 210, "end": 390, "color": "#a78bfa"},
    {"name": "transport", "start": 390, "end": 660, "color": "#fbbf24"},
    {"name": "release", "start": 660, "end": 847, "color": "#22c55e"},
]

# Generate smooth cube trajectory
random.seed(42)

def _smooth(base, amp, freq, n, noise=0.008):
    return [base + amp * math.sin(2 * math.pi * freq * i / n) + random.gauss(0, noise) for i in range(n)]

STEPS = list(range(0, EPISODE_LENGTH, 12))  # sample every 12 steps for display
N = len(STEPS)

POS_X = _smooth(0.42, 0.18, 0.9, N, 0.006)
POS_Y = _smooth(0.31, 0.12, 0.8, N, 0.006)
POS_Z_BASE = []
for i, s in enumerate(STEPS):
    if s < 210:
        POS_Z_BASE.append(0.72 + 0.01 * math.sin(i))
    elif s < 390:
        POS_Z_BASE.append(0.72 + (s - 210) / 180 * 0.0)
    elif s < 660:
        POS_Z_BASE.append(0.72 + math.sin(math.pi * (s - 390) / 270) * 0.18)
    else:
        POS_Z_BASE.append(0.72 - (s - 660) / 187 * 0.06)
POS_Z = [z + random.gauss(0, 0.006) for z in POS_Z_BASE]

UNCERTAINTY = []
for i, s in enumerate(STEPS):
    if s < 210:
        UNCERTAINTY.append(0.012 + 0.004 * math.sin(i * 0.5))
    elif s < 390:
        UNCERTAINTY.append(0.018 + 0.006 * math.sin(i * 0.4))
    elif s < 660:
        UNCERTAINTY.append(0.015 + 0.005 * math.cos(i * 0.3))
    else:
        UNCERTAINTY.append(0.010 + 0.003 * math.sin(i * 0.6))

GRASPED = [1 if (210 <= s < 660) else 0 for s in STEPS]
CONTACT = [1 if (190 <= s < 670) else 0 for s in STEPS]

# Permanence benchmark scores
BENCHMARK = [
    {"test": "out_of_view_recovery", "groot_v2": 0.83, "bc_1000": 0.65, "random": 0.12},
    {"test": "occlusion_tracking", "groot_v2": 0.89, "bc_1000": 0.71, "random": 0.15},
    {"test": "multi_object_tracking", "groot_v2": 0.79, "bc_1000": 0.58, "random": 0.11},
    {"test": "target_vs_distractor", "groot_v2": 0.84, "bc_1000": 0.66, "random": 0.18},
    {"test": "re_grasp_after_drop", "groot_v2": 0.61, "bc_1000": 0.48, "random": 0.09},
]

KEY_METRICS = {
    "groot_v2_composite": 0.81,
    "bc_1000_composite": 0.62,
    "random_composite": 0.13,
    "improvement_pct": 30.6,
    "weakest_test": "re_grasp_after_drop",
    "strongest_test": "occlusion_tracking",
    "sr_correlation": 0.73,
    "episode_steps": EPISODE_LENGTH,
}

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_state_timeline() -> str:
    """Object state timeline across 847-step episode."""
    W, H = 820, 260
    pad_l, pad_r, pad_t, pad_b = 68, 20, 36, 44
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    def sx(step):
        return pad_l + step / EPISODE_LENGTH * chart_w

    # Phase shading
    for ph in PHASES:
        x1 = sx(ph["start"])
        x2 = sx(ph["end"])
        lines.append(f'<rect x="{x1:.1f}" y="{pad_t}" width="{x2-x1:.1f}" height="{chart_h}" fill="{ph["color"]}" opacity="0.07"/>')
        mx = (x1 + x2) / 2
        lines.append(f'<text x="{mx:.1f}" y="{pad_t-6}" text-anchor="middle" fill="{ph["color"]}" font-size="10" font-weight="bold">{ph["name"].upper()}</text>')
        lines.append(f'<line x1="{x1:.1f}" y1="{pad_t}" x2="{x1:.1f}" y2="{pad_t+chart_h}" stroke="{ph["color"]}" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>')

    # Three tracks: pos_x/y/z each in a sub-band
    track_h = chart_h / 3
    tracks = [
        ("pos_x", POS_X, "#38bdf8", 0.0, 0.7),
        ("pos_y", POS_Y, "#a78bfa", 0.1, 0.55),
        ("pos_z", POS_Z, "#fbbf24", 0.6, 1.0),
    ]
    for ti, (name, vals, color, vmin, vmax) in enumerate(tracks):
        band_y_top = pad_t + ti * track_h
        band_y_bot = band_y_top + track_h
        band_mid = (band_y_top + band_y_bot) / 2

        def vy(v):
            return band_y_bot - (v - vmin) / (vmax - vmin) * track_h * 0.8 - track_h * 0.1

        # Uncertainty band
        upper_pts = " ".join(f"{sx(STEPS[i]):.1f},{vy(vals[i]+UNCERTAINTY[i]):.1f}" for i in range(N))
        lower_pts = " ".join(f"{sx(STEPS[i]):.1f},{vy(vals[i]-UNCERTAINTY[i]):.1f}" for i in range(N-1, -1, -1))
        lines.append(f'<polygon points="{upper_pts} {lower_pts}" fill="{color}" opacity="0.15"/>')

        # Line
        pts = " ".join(f"{sx(STEPS[i]):.1f},{vy(vals[i]):.1f}" for i in range(N))
        lines.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5"/>')

        # Label
        lines.append(f'<text x="{pad_l-6}" y="{band_mid+4:.1f}" text-anchor="end" fill="{color}" font-size="10">{name}</text>')
        lines.append(f'<line x1="{pad_l}" y1="{band_y_bot:.1f}" x2="{W-pad_r}" y2="{band_y_bot:.1f}" stroke="#334155" stroke-width="0.5"/>')

    # Grasped indicator bar at bottom
    bar_y = H - pad_b + 6
    lines.append(f'<text x="{pad_l-6}" y="{bar_y+8}" text-anchor="end" fill="#22c55e" font-size="9">grasped</text>')
    for i in range(N - 1):
        if GRASPED[i]:
            x1 = sx(STEPS[i])
            x2 = sx(STEPS[i+1])
            lines.append(f'<rect x="{x1:.1f}" y="{bar_y:.1f}" width="{x2-x1:.1f}" height="6" fill="#22c55e" opacity="0.8"/>')

    # X-axis ticks
    for s in range(0, EPISODE_LENGTH+1, 100):
        xp = sx(s)
        lines.append(f'<text x="{xp:.1f}" y="{H-pad_b+20}" text-anchor="middle" fill="#94a3b8" font-size="9">{s}</text>')

    lines.append(f'<text x="{W//2}" y="{H-2}" text-anchor="middle" fill="#64748b" font-size="9">step</text>')
    lines.append(f'<text x="{W//2}" y="16" text-anchor="middle" fill="#e2e8f0" font-size="12" font-weight="bold">Cube State Timeline — Episode ({EPISODE_LENGTH} steps)</text>')
    lines.append('</svg>')
    return '\n'.join(lines)


def svg_permanence_bars() -> str:
    """Object permanence score bar chart."""
    W, H = 820, 280
    pad_l, pad_r, pad_t, pad_b = 180, 30, 40, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    n_tests = len(BENCHMARK)
    bar_group_w = chart_w / n_tests
    bar_w = bar_group_w * 0.22

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # Grid
    for v in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = pad_t + chart_h - v * chart_h
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{W-pad_r}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-6}" y="{y+4:.1f}" text-anchor="end" fill="#64748b" font-size="10">{v:.2f}</text>')

    models = [
        ("groot_v2", "#38bdf8", 0),
        ("bc_1000", "#C74634", 1),
        ("random", "#475569", 2),
    ]

    for ti, bench in enumerate(BENCHMARK):
        group_x = pad_l + ti * bar_group_w
        for mi, (key, color, offset) in enumerate(models):
            val = bench[key]
            bx = group_x + bar_group_w * 0.12 + offset * (bar_w + 3)
            bh = val * chart_h
            by = pad_t + chart_h - bh
            lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" rx="2" opacity="0.9"/>')
            lines.append(f'<text x="{bx+bar_w/2:.1f}" y="{by-4:.1f}" text-anchor="middle" fill="{color}" font-size="9">{val:.2f}</text>')

        # X label
        short = bench["test"].replace("_", "\n")
        label_x = group_x + bar_group_w / 2
        label_lines = bench["test"].replace("_", " ").split(" ")
        for li, word in enumerate(label_lines[:3]):
            lines.append(f'<text x="{label_x:.1f}" y="{pad_t+chart_h+14+li*11:.1f}" text-anchor="middle" fill="#94a3b8" font-size="9">{word}</text>')

    # Legend
    for mi, (key, color, offset) in enumerate(models):
        lx = pad_l + mi * 150
        lines.append(f'<rect x="{lx}" y="10" width="14" height="10" fill="{color}" rx="2"/>')
        label = key.replace("_", " ")
        lines.append(f'<text x="{lx+18}" y="19" fill="{color}" font-size="11">{label}</text>')

    lines.append(f'<text x="{W//2}" y="{H-2}" text-anchor="middle" fill="#64748b" font-size="10">Object Permanence Test Category</text>')
    lines.append(f'<text x="{W//2}" y="26" text-anchor="middle" fill="#e2e8f0" font-size="12" font-weight="bold">Object Permanence Benchmark — GR00T_v2 vs BC_1000 vs Random</text>')
    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    tl = svg_state_timeline()
    pb = svg_permanence_bars()

    bench_rows = ""
    for b in BENCHMARK:
        delta = b["groot_v2"] - b["bc_1000"]
        delta_str = f"+{delta:.2f}" if delta >= 0 else f"{delta:.2f}"
        delta_color = "#22c55e" if delta >= 0 else "#C74634"
        hardest = " ⚠" if b["test"] == KEY_METRICS["weakest_test"] else ""
        best = " ★" if b["test"] == KEY_METRICS["strongest_test"] else ""
        bench_rows += f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td style="padding:8px 12px;color:#e2e8f0">{b['test'].replace('_',' ')}{hardest}{best}</td>
          <td style="padding:8px 12px;color:#38bdf8;font-weight:bold">{b['groot_v2']:.2f}</td>
          <td style="padding:8px 12px;color:#C74634">{b['bc_1000']:.2f}</td>
          <td style="padding:8px 12px;color:#475569">{b['random']:.2f}</td>
          <td style="padding:8px 12px;color:{delta_color};font-weight:bold">{delta_str}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Object Permanence Tracker — Port 8305</title>
<style>
  body{{margin:0;font-family:'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#e2e8f0}}
  h1{{margin:0;font-size:22px;font-weight:700}}
  h2{{font-size:15px;color:#94a3b8;margin:24px 0 10px;text-transform:uppercase;letter-spacing:.06em}}
  .header{{background:#1e293b;border-bottom:2px solid #38bdf8;padding:16px 28px;display:flex;align-items:center;gap:16px}}
  .badge{{background:#0369a1;color:#e0f2fe;border-radius:6px;padding:2px 10px;font-size:12px}}
  .metrics{{display:flex;flex-wrap:wrap;gap:14px;padding:20px 28px}}
  .metric{{background:#1e293b;border-radius:8px;padding:14px 20px;min-width:140px}}
  .metric .val{{font-size:24px;font-weight:700;color:#38bdf8}}
  .metric .lbl{{font-size:11px;color:#64748b;margin-top:2px}}
  .content{{padding:0 28px 28px}}
  table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
  th{{background:#0f172a;padding:9px 12px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase}}
  svg{{display:block;max-width:100%}}
</style>
</head>
<body>
<div class="header">
  <div>
    <div style="display:flex;align-items:center;gap:10px">
      <h1>Object Permanence Tracker</h1>
      <span class="badge">PORT 8305</span>
    </div>
    <div style="color:#64748b;font-size:13px;margin-top:4px">Tracks object state persistence across task phases to measure scene understanding in GR00T policies</div>
  </div>
</div>

<div class="metrics">
  <div class="metric"><div class="val">{KEY_METRICS['groot_v2_composite']:.2f}</div><div class="lbl">GR00T_v2 Composite</div></div>
  <div class="metric"><div class="val" style="color:#C74634">{KEY_METRICS['bc_1000_composite']:.2f}</div><div class="lbl">BC_1000 Composite</div></div>
  <div class="metric"><div class="val" style="color:#22c55e">+{KEY_METRICS['improvement_pct']:.1f}%</div><div class="lbl">vs BC Baseline</div></div>
  <div class="metric"><div class="val" style="color:#fbbf24">{KEY_METRICS['weakest_test'].replace('_',' ')}</div><div class="lbl">Weakest Category</div></div>
  <div class="metric"><div class="val" style="color:#22c55e">{KEY_METRICS['strongest_test'].replace('_',' ')}</div><div class="lbl">Strongest Category</div></div>
  <div class="metric"><div class="val" style="color:#a78bfa">{KEY_METRICS['sr_correlation']:.2f}</div><div class="lbl">SR Correlation</div></div>
</div>

<div class="content">
  <h2>Cube State Timeline — 847-Step Episode</h2>
  <div style="border-radius:8px;overflow:hidden;margin-bottom:22px">{tl}</div>

  <h2>Object Permanence Benchmark</h2>
  <div style="border-radius:8px;overflow:hidden;margin-bottom:22px">{pb}</div>

  <h2>Permanence Score Detail</h2>
  <table>
    <thead><tr>
      <th>Test</th><th>GR00T_v2</th><th>BC_1000</th><th>Random</th><th>Delta</th>
    </tr></thead>
    <tbody>{bench_rows}</tbody>
  </table>
  <div style="color:#64748b;font-size:11px;margin-top:8px">⚠ weakest  ★ strongest  |  Delta = GR00T_v2 − BC_1000</div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Object Permanence Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/benchmark")
    async def api_benchmark():
        return {"benchmark": BENCHMARK, "key_metrics": KEY_METRICS}

    @app.get("/api/episode")
    async def api_episode():
        return {
            "steps": STEPS[:20],
            "pos_x": POS_X[:20],
            "pos_z": POS_Z[:20],
            "grasped": GRASPED[:20],
            "phases": PHASES,
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "object_permanence_tracker", "port": 8305}

else:
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            html = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8305)
    else:
        server = http.server.HTTPServer(("0.0.0.0", 8305), Handler)
        print("Serving on http://0.0.0.0:8305 (stdlib fallback)")
        server.serve_forever()

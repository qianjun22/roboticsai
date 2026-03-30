"""Training Metrics v2 — multi-experiment comparison with statistical tests.
Port 8343
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

random.seed(42)

EXPS = [
    {"name": "BC_1000",       "color": "#f59e0b", "final_loss": 0.187, "sr_mean": 0.42, "sr_ci": 0.05,
     "max_step": 5000, "status": "complete"},
    {"name": "DAgger_r5",     "color": "#38bdf8", "final_loss": 0.143, "sr_mean": 0.60, "sr_ci": 0.06,
     "max_step": 5000, "status": "complete"},
    {"name": "DAgger_r9",     "color": "#818cf8", "final_loss": 0.114, "sr_mean": 0.71, "sr_ci": 0.05,
     "max_step": 5000, "status": "complete"},
    {"name": "GR00T_v2",      "color": "#22c55e", "final_loss": 0.099, "sr_mean": 0.78, "sr_ci": 0.04,
     "max_step": 5000, "status": "complete"},
    {"name": "GR00T_v3",      "color": "#C74634", "final_loss": 0.121, "sr_mean": None,  "sr_ci": None,
     "max_step": 800,  "status": "partial"},
]

# Pairwise t-test results (completed runs only)
PAIRWISE = [
    {"a": "BC_1000",   "b": "DAgger_r5", "p": 0.041, "effect": 0.52, "sig": True},
    {"a": "BC_1000",   "b": "DAgger_r9", "p": 0.009, "effect": 0.81, "sig": True},
    {"a": "BC_1000",   "b": "GR00T_v2",  "p": 0.002, "effect": 1.12, "sig": True},
    {"a": "DAgger_r5", "b": "DAgger_r9", "p": 0.038, "effect": 0.44, "sig": True},
    {"a": "DAgger_r5", "b": "GR00T_v2",  "p": 0.007, "effect": 0.76, "sig": True},
    {"a": "DAgger_r9", "b": "GR00T_v2",  "p": 0.003, "effect": 0.58, "sig": True},
]

MIN_SAMPLE = 25   # recommended minimum n per run


def _loss_curve(exp):
    """Generate a realistic loss curve (list of (step, loss) tuples)."""
    random.seed(hash(exp["name"]) % 10000)
    final = exp["final_loss"]
    steps_total = exp["max_step"]
    n_points = min(50, steps_total // 100 + 1)
    points = []
    for i in range(n_points):
        frac = i / max(n_points - 1, 1)
        step = int(frac * steps_total)
        # exponential decay + noise
        decay = final + (0.55 - final) * math.exp(-4 * frac)
        noise = random.gauss(0, 0.008)
        loss  = max(final * 0.95, decay + noise)
        points.append((step, loss))
    return points


def compute_summary():
    completed = [e for e in EXPS if e["status"] == "complete"]
    best = max(completed, key=lambda e: e["sr_mean"])
    avg_sr = sum(e["sr_mean"] for e in completed) / len(completed)
    sig_pairs = sum(1 for p in PAIRWISE if p["sig"])
    return {
        "best_run": best["name"],
        "best_sr": best["sr_mean"],
        "best_loss": best["final_loss"],
        "avg_sr": round(avg_sr, 3),
        "sig_pairs": sig_pairs,
        "total_pairs": len(PAIRWISE),
        "min_sample": MIN_SAMPLE,
        "projected_sr_v3_low": 0.83,
        "projected_sr_v3_high": 0.86,
    }


# ---------------------------------------------------------------------------
# SVG 1: multi-run training curves
# ---------------------------------------------------------------------------

def build_curves_svg():
    W, H = 860, 300
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 20, 40, 50
    PW = W - PAD_L - PAD_R
    PH = H - PAD_T - PAD_B

    MAX_STEP = 5000
    LOSS_MIN, LOSS_MAX = 0.06, 0.58

    def sx(step):
        return PAD_L + step / MAX_STEP * PW

    def sy(loss):
        frac = (loss - LOSS_MIN) / (LOSS_MAX - LOSS_MIN)
        return PAD_T + PH * (1 - frac)

    elements = []

    # Grid lines
    for tick_loss in [0.1, 0.2, 0.3, 0.4, 0.5]:
        y = sy(tick_loss)
        elements.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L+PW}" y2="{y:.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>')
        elements.append(f'<text x="{PAD_L-6}" y="{y+4:.1f}" text-anchor="end" font-size="10" fill="#64748b">{tick_loss:.1f}</text>')

    for tick_step in [0, 1000, 2000, 3000, 4000, 5000]:
        x = sx(tick_step)
        elements.append(f'<line x1="{x:.1f}" y1="{PAD_T}" x2="{x:.1f}" y2="{PAD_T+PH}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>')
        elements.append(f'<text x="{x:.1f}" y="{PAD_T+PH+16}" text-anchor="middle" font-size="10" fill="#64748b">{tick_step}</text>')

    # Curves
    for exp in EXPS:
        pts = _loss_curve(exp)
        coords = " ".join(f"{sx(s):.1f},{sy(l):.1f}" for s, l in pts)
        dash = "6,4" if exp["status"] == "partial" else "none"
        elements.append(
            f'<polyline points="{coords}" fill="none" stroke="{exp["color"]}" '
            f'stroke-width="2.2" stroke-dasharray="{dash}" stroke-linecap="round"/>'
        )
        # End label
        last_x, last_y = sx(pts[-1][0]), sy(pts[-1][1])
        elements.append(
            f'<text x="{last_x+4:.1f}" y="{last_y+4:.1f}" font-size="10" fill="{exp["color"]}">{exp["name"]}</text>'
        )

    # CI shading for completed runs (approximate 95% band)
    for exp in EXPS:
        if exp["status"] != "complete":
            continue
        pts = _loss_curve(exp)
        ci = 0.012
        upper = " ".join(f"{sx(s):.1f},{sy(l+ci):.1f}" for s, l in pts)
        lower = " ".join(f"{sx(s):.1f},{sy(l-ci):.1f}" for s, l in reversed(pts))
        elements.append(
            f'<polygon points="{upper} {lower}" fill="{exp["color"]}" opacity="0.12"/>'
        )

    # Axes
    elements.append(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+PH}" stroke="#475569" stroke-width="1.5"/>')
    elements.append(f'<line x1="{PAD_L}" y1="{PAD_T+PH}" x2="{PAD_L+PW}" y2="{PAD_T+PH}" stroke="#475569" stroke-width="1.5"/>')
    elements.append(f'<text x="{PAD_L+PW//2}" y="{H-4}" text-anchor="middle" font-size="11" fill="#94a3b8">Training Steps</text>')
    elements.append(f'<text x="14" y="{PAD_T+PH//2}" text-anchor="middle" font-size="11" fill="#94a3b8" transform="rotate(-90,14,{PAD_T+PH//2})">Loss</text>')

    inner = "\n  ".join(elements)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">
  <text x="{W//2}" y="22" text-anchor="middle" font-size="13" font-weight="700" fill="#f8fafc">Multi-Run Training Curves (Loss vs Steps)</text>
  {inner}
  <text x="{W-10}" y="{H-4}" text-anchor="end" font-size="9" fill="#475569">Shaded = 95% CI &nbsp;|&nbsp; Dashed = partial run</text>
</svg>'''
    return svg


# ---------------------------------------------------------------------------
# SVG 2: statistical comparison table
# ---------------------------------------------------------------------------

def build_stats_svg():
    W, H = 860, 290
    COL_WIDTHS = [130, 130, 90, 90, 100, 110, 80]
    HEADERS    = ["Run A", "Run B", "SR(A)", "SR(B)", "p-value", "Effect Size", "Sig?"]

    assert len(COL_WIDTHS) == len(HEADERS)

    ROW_H = 34
    HEADER_H = 38
    TABLE_TOP = 52
    MARGIN_L = 10

    elements = []
    elements.append(
        f'<text x="{W//2}" y="26" text-anchor="middle" font-size="13" font-weight="700" fill="#f8fafc">'
        f'Pairwise Statistical Comparison (Success Rate, n=20/run)</text>'
    )
    elements.append(
        f'<text x="{W//2}" y="44" text-anchor="middle" font-size="10" fill="#94a3b8">'
        f't-test, two-tailed, Welch correction  |  * p&lt;0.05  |  ** p&lt;0.01  |  *** p&lt;0.001</text>'
    )

    # Header row
    cx = MARGIN_L
    for i, (hdr, cw) in enumerate(zip(HEADERS, COL_WIDTHS)):
        elements.append(
            f'<rect x="{cx}" y="{TABLE_TOP}" width="{cw}" height="{HEADER_H}" fill="#C74634" rx="0"/>'
        )
        elements.append(
            f'<text x="{cx+cw//2}" y="{TABLE_TOP+24}" text-anchor="middle" font-size="11" font-weight="700" fill="#fff">{hdr}</text>'
        )
        cx += cw

    # Data rows
    EXP_SR = {e["name"]: (e["sr_mean"], e["sr_ci"]) for e in EXPS if e["sr_mean"] is not None}

    for row_i, pw in enumerate(PAIRWISE):
        ry = TABLE_TOP + HEADER_H + row_i * ROW_H
        bg = "#1e293b" if row_i % 2 == 0 else "#243044"
        elements.append(f'<rect x="{MARGIN_L}" y="{ry}" width="{sum(COL_WIDTHS)}" height="{ROW_H}" fill="{bg}"/>')

        sr_a, ci_a = EXP_SR.get(pw["a"], (None, None))
        sr_b, ci_b = EXP_SR.get(pw["b"], (None, None))

        # Star notation
        p = pw["p"]
        if p < 0.001:
            star = "***"
        elif p < 0.01:
            star = "**"
        elif p < 0.05:
            star = "*"
        else:
            star = "ns"

        sig_color = "#22c55e" if pw["sig"] else "#ef4444"

        cells = [
            pw["a"],
            pw["b"],
            f"{sr_a:.2f}\u00b1{ci_a:.2f}" if sr_a else "—",
            f"{sr_b:.2f}\u00b1{ci_b:.2f}" if sr_b else "—",
            f"{p:.3f} {star}",
            f"d={pw['effect']:.2f}",
            "YES" if pw["sig"] else "NO",
        ]
        cell_colors = ["#f8fafc"] * 6 + [sig_color]

        cx = MARGIN_L
        for cell, cw, color in zip(cells, COL_WIDTHS, cell_colors):
            elements.append(
                f'<text x="{cx+cw//2}" y="{ry+ROW_H//2+5}" text-anchor="middle" '
                f'font-size="10.5" fill="{color}">{cell}</text>'
            )
            cx += cw

    # Bottom note
    bottom_y = TABLE_TOP + HEADER_H + len(PAIRWISE) * ROW_H + 14
    elements.append(
        f'<text x="{MARGIN_L}" y="{bottom_y}" font-size="9" fill="#475569">'
        f'GR00T_v3 (partial, step 800) excluded from pairwise tests. Projected SR: 0.83–0.86.</text>'
    )

    inner = "\n  ".join(elements)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">\n  {inner}\n</svg>'
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html():
    s = compute_summary()
    curves_svg = build_curves_svg()
    stats_svg  = build_stats_svg()

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Training Metrics v2 — OCI Robot Cloud</title>
<style>
  body {{ margin:0; font-family:'Segoe UI',system-ui,sans-serif;
          background:#0f172a; color:#f8fafc; }}
  header {{ background:#C74634; padding:18px 32px; display:flex;
             justify-content:space-between; align-items:center; }}
  header h1 {{ margin:0; font-size:1.4rem; font-weight:700; }}
  header span {{ font-size:.9rem; opacity:.85; }}
  .metrics {{ display:flex; gap:16px; padding:24px 32px; flex-wrap:wrap; }}
  .card {{ background:#1e293b; border-radius:10px; padding:20px 28px;
            flex:1; min-width:160px; }}
  .card .val {{ font-size:2rem; font-weight:800; margin-top:6px; }}
  .card .lbl {{ font-size:.75rem; color:#94a3b8; text-transform:uppercase;
                letter-spacing:.08em; }}
  .section {{ padding:8px 32px 28px; }}
  .section h2 {{ font-size:1rem; color:#38bdf8; margin-bottom:12px; }}
  svg {{ max-width:100%; display:block; }}
  footer {{ text-align:center; padding:16px; font-size:.75rem; color:#475569; }}
</style>
</head>
<body>
<header>
  <h1>Training Metrics v2 — Multi-Experiment Comparison</h1>
  <span>5 runs &nbsp;|&nbsp; 4 completed &nbsp;|&nbsp; 1 partial</span>
</header>

<div class="metrics">
  <div class="card">
    <div class="lbl">Best Run</div>
    <div class="val" style="color:#22c55e">{s["best_run"]}</div>
  </div>
  <div class="card">
    <div class="lbl">Best SR</div>
    <div class="val" style="color:#38bdf8">{s["best_sr"]:.2f}</div>
  </div>
  <div class="card">
    <div class="lbl">Best Loss</div>
    <div class="val" style="color:#38bdf8">{s["best_loss"]}</div>
  </div>
  <div class="card">
    <div class="lbl">Avg SR (completed)</div>
    <div class="val" style="color:#f59e0b">{s["avg_sr"]:.3f}</div>
  </div>
  <div class="card">
    <div class="lbl">Sig. Pairs</div>
    <div class="val" style="color:#22c55e">{s["sig_pairs"]} / {s["total_pairs"]}</div>
  </div>
  <div class="card">
    <div class="lbl">Projected SR (v3)</div>
    <div class="val" style="color:#C74634">{s["projected_sr_v3_low"]:.2f}–{s["projected_sr_v3_high"]:.2f}</div>
  </div>
  <div class="card">
    <div class="lbl">Min Sample Rec.</div>
    <div class="val" style="color:#94a3b8">n={s["min_sample"]}</div>
  </div>
</div>

<div class="section">
  <h2>Multi-Run Training Curves</h2>
  {curves_svg}
</div>

<div class="section">
  <h2>Statistical Comparison Table</h2>
  {stats_svg}
</div>

<footer>OCI Robot Cloud &mdash; Training Metrics v2 &mdash; Port 8343 &mdash; {datetime.utcnow().strftime("%Y-%m-%d %H:%M")} UTC</footer>
</body>
</html>'''
    return html


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Training Metrics v2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "training_metrics_v2", "port": 8343}

    @app.get("/api/summary")
    def api_summary():
        return compute_summary()

    @app.get("/api/experiments")
    def api_experiments():
        return EXPS

    @app.get("/api/pairwise")
    def api_pairwise():
        return PAIRWISE

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8343)
    else:
        print("FastAPI not found — starting stdlib server on port 8343")
        HTTPServer(("0.0.0.0", 8343), Handler).serve_forever()

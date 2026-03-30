"""Latency Predictor — FastAPI service on port 8291.

Predicts inference latency based on model configuration, hardware, and
load conditions. Provides scatter (predicted vs actual) and feature
importance visualisations.
"""

import math
import random
import json
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

random.seed(7)

# Feature importance (sorted descending)
FEATURES = [
    ("GPU utilisation",  0.41),
    ("batch size",       0.28),
    ("model size",       0.14),
    ("request type",     0.08),
    ("VRAM free",        0.05),
    ("sequence length",  0.04),
]

N_REQUESTS = 100
RMSE_MS = 14.0
SLA_PCT = 94.0          # % within ±30 ms

# Generate scatter data: predicted vs actual
def _make_scatter(n: int):
    points = []
    for _ in range(n):
        gpu_util = random.uniform(0.15, 0.98)
        batch = random.choice([1, 2, 4, 8, 16])
        # True latency model
        actual = 80 + 120 * gpu_util + 8 * math.log(batch + 1) + random.gauss(0, 12)
        actual = max(40.0, actual)
        # Predicted with RMSE ~14 ms; outliers at high GPU util
        noise = random.gauss(0, RMSE_MS)
        if gpu_util > 0.85:
            noise += random.gauss(30, 10)   # outlier region
        predicted = actual + noise
        predicted = max(30.0, predicted)
        points.append({
            "actual":    round(actual, 1),
            "predicted": round(predicted, 1),
            "batch":     batch,
            "gpu_util":  round(gpu_util, 3),
            "outlier":   gpu_util > 0.85,
        })
    return points

SCATTER = _make_scatter(N_REQUESTS)

# Recompute empirical RMSE from mock data
_sq_err = sum((p["predicted"] - p["actual"]) ** 2 for p in SCATTER)
EMPIRICAL_RMSE = round(math.sqrt(_sq_err / N_REQUESTS), 1)
_within_sla = sum(1 for p in SCATTER if abs(p["predicted"] - p["actual"]) <= 30)
EMPIRICAL_SLA_PCT = round(100 * _within_sla / N_REQUESTS, 1)
N_OUTLIERS = sum(1 for p in SCATTER if p["outlier"])

ACTUAL_VALS = [p["actual"] for p in SCATTER]
PRED_VALS   = [p["predicted"] for p in SCATTER]
MIN_V = max(0, math.floor(min(min(ACTUAL_VALS), min(PRED_VALS)) / 10) * 10)
MAX_V = math.ceil(max(max(ACTUAL_VALS), max(PRED_VALS)) / 10) * 10

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

BATCH_COLOURS = {1: "#38bdf8", 2: "#34d399", 4: "#fbbf24", 8: "#f87171", 16: "#c084fc"}


def build_scatter_svg() -> str:
    W, H = 520, 420
    pad_l, pad_r, pad_t, pad_b = 60, 30, 40, 60

    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    def sx(v):
        return pad_l + (v - MIN_V) / (MAX_V - MIN_V) * plot_w

    def sy(v):
        return pad_t + plot_h - (v - MIN_V) / (MAX_V - MIN_V) * plot_h

    # Diagonal line (perfect prediction)
    diag = (f'<line x1="{sx(MIN_V):.1f}" y1="{sy(MIN_V):.1f}" '
            f'x2="{sx(MAX_V):.1f}" y2="{sy(MAX_V):.1f}" '
            f'stroke="#475569" stroke-width="1" stroke-dasharray="5,4"/>')

    # ±30 ms SLA band
    band_pts = (
        f"{sx(MIN_V):.1f},{sy(MIN_V+30):.1f} "
        f"{sx(MAX_V-30):.1f},{sy(MAX_V):.1f} "
        f"{sx(MAX_V):.1f},{sy(MAX_V):.1f} "
        f"{sx(MAX_V):.1f},{sy(MAX_V-30):.1f} "
        f"{sx(MIN_V):.1f},{sy(MIN_V):.1f}"
    )
    band = f'<polygon points="{band_pts}" fill="rgba(56,189,248,0.07)" stroke="none"/>'

    circles = []
    for p in SCATTER:
        cx, cy = sx(p["actual"]), sy(p["predicted"])
        colour = BATCH_COLOURS.get(p["batch"], "#e2e8f0")
        r = 4 if p["outlier"] else 3
        stroke = "#f87171" if p["outlier"] else "none"
        circles.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" '
            f'fill="{colour}" fill-opacity="0.75" stroke="{stroke}" stroke-width="1"/>'
        )

    # Axes
    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" stroke="#334155" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" stroke="#334155" stroke-width="1"/>'
    )

    # Tick labels
    ticks_x = "".join(
        f'<text x="{sx(v):.1f}" y="{pad_t+plot_h+14}" text-anchor="middle" fill="#64748b" font-size="9">{v}</text>'
        for v in range(MIN_V, MAX_V + 1, 50)
    )
    ticks_y = "".join(
        f'<text x="{pad_l-6}" y="{sy(v)+4:.1f}" text-anchor="end" fill="#64748b" font-size="9">{v}</text>'
        for v in range(MIN_V, MAX_V + 1, 50)
    )

    # Axis labels
    ax_x = f'<text x="{pad_l + plot_w//2}" y="{H-6}" text-anchor="middle" fill="#94a3b8" font-size="11">Actual latency (ms)</text>'
    ax_y = (f'<text x="14" y="{pad_t + plot_h//2}" text-anchor="middle" fill="#94a3b8" font-size="11" '
            f'transform="rotate(-90 14 {pad_t + plot_h//2})">Predicted latency (ms)</text>')

    # Legend
    legend = "".join(
        f'<rect x="{pad_l + plot_w - 90}" y="{pad_t + 6 + i*14}" width="9" height="9" fill="{c}" rx="2"/>'
        f'<text x="{pad_l + plot_w - 77}" y="{pad_t + 14 + i*14}" fill="#94a3b8" font-size="9">batch={b}</text>'
        for i, (b, c) in enumerate(BATCH_COLOURS.items())
    )

    title = (f'<text x="{W//2}" y="22" text-anchor="middle" fill="#f1f5f9" font-size="13" font-weight="bold">'
             f'Predicted vs Actual Latency (n={N_REQUESTS})</text>')
    subtitle = (f'<text x="{W//2}" y="36" text-anchor="middle" fill="#94a3b8" font-size="10">'
                f'RMSE={EMPIRICAL_RMSE}ms  |  SLA≤30ms: {EMPIRICAL_SLA_PCT}%  |  outliers (GPU>85%): {N_OUTLIERS}</text>')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">'
        f'{title}{subtitle}{diag}{band}{axes}{ticks_x}{ticks_y}{ax_x}{ax_y}'
        f'{"" .join(circles)}{legend}</svg>'
    )
    return svg


def build_importance_svg() -> str:
    W, H = 480, 280
    pad_l, pad_r, pad_t, pad_b = 130, 24, 40, 30
    bar_h = 28
    gap = 10
    max_imp = FEATURES[0][1]
    plot_w = W - pad_l - pad_r

    bars = []
    for i, (name, imp) in enumerate(FEATURES):
        bw = int(imp / max_imp * plot_w)
        y = pad_t + i * (bar_h + gap)
        pct = int(imp * 100)
        # colour gradient: top = Oracle red, bottom = sky blue
        t = i / max(len(FEATURES) - 1, 1)
        r = int(199 * (1 - t) + 56 * t)
        g = int(70 * (1 - t) + 189 * t)
        b = int(52 * (1 - t) + 248 * t)
        fill = f"rgb({r},{g},{b})"
        bars.append(f'<rect x="{pad_l}" y="{y}" width="{bw}" height="{bar_h}" fill="{fill}" rx="3"/>')
        bars.append(
            f'<text x="{pad_l - 6}" y="{y + bar_h//2 + 4}" text-anchor="end" fill="#e2e8f0" font-size="11">{name}</text>'
        )
        bars.append(
            f'<text x="{pad_l + bw + 5}" y="{y + bar_h//2 + 4}" fill="#94a3b8" font-size="10">{pct}%</text>'
        )

    title = (f'<text x="{W//2}" y="22" text-anchor="middle" fill="#f1f5f9" font-size="13" font-weight="bold">'
             f'Latency Feature Importance</text>')
    x_axis = (f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" '
               f'y2="{pad_t + len(FEATURES)*(bar_h+gap)}" stroke="#334155" stroke-width="1"/>')

    needed_h = pad_t + len(FEATURES) * (bar_h + gap) + pad_b
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{needed_h}" style="background:#0f172a;border-radius:8px">'
        f'{title}{x_axis}{"" .join(bars)}</svg>'
    )
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Latency Predictor | OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }}
  header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }}
  header h1 {{ font-size: 1.4rem; color: #f1f5f9; font-weight: 700; }}
  header .badge {{ background: #C74634; color: #fff; padding: 3px 10px; border-radius: 99px; font-size: 0.75rem; font-weight: 600; }}
  .port-badge {{ background: #0369a1; color: #e0f2fe; padding: 3px 10px; border-radius: 99px; font-size: 0.75rem; }}
  .main {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px; }}
  .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 16px; margin-bottom: 32px; }}
  .metric-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px; }}
  .metric-card .label {{ font-size: 0.78rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }}
  .metric-card .value {{ font-size: 1.6rem; font-weight: 700; color: #38bdf8; }}
  .metric-card .sub {{ font-size: 0.78rem; color: #64748b; margin-top: 4px; }}
  .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 24px; margin-bottom: 28px; }}
  .section h2 {{ font-size: 1.05rem; color: #f1f5f9; margin-bottom: 18px; border-left: 3px solid #C74634; padding-left: 10px; }}
  .charts {{ display: flex; flex-wrap: wrap; gap: 24px; align-items: flex-start; }}
  .svg-wrap {{ overflow-x: auto; }}
  .feat-table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
  .feat-table th {{ background: #0f172a; color: #94a3b8; padding: 8px 12px; text-align: left; font-weight: 600; }}
  .feat-table td {{ padding: 8px 12px; border-bottom: 1px solid #0f172a; }}
  .feat-table tr:hover td {{ background: #0f172a33; }}
  .highlight {{ color: #38bdf8; font-weight: 600; }}
  footer {{ text-align: center; padding: 20px; color: #475569; font-size: 0.8rem; }}
</style>
</head>
<body>
<header>
  <h1>Latency Predictor</h1>
  <span class="badge">Infra</span>
  <span class="port-badge">:8291</span>
</header>
<div class="main">
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="label">Prediction RMSE</div>
      <div class="value">{rmse}ms</div>
      <div class="sub">empirical over {n} requests</div>
    </div>
    <div class="metric-card">
      <div class="label">SLA Compliance</div>
      <div class="value">{sla}%</div>
      <div class="sub">within ±30ms of actual</div>
    </div>
    <div class="metric-card">
      <div class="label">Outlier Requests</div>
      <div class="value">{n_outliers}</div>
      <div class="sub">GPU util &gt; 85%</div>
    </div>
    <div class="metric-card">
      <div class="label">Top Predictor</div>
      <div class="value">GPU util</div>
      <div class="sub">importance = 41%</div>
    </div>
  </div>

  <div class="section">
    <h2>Predicted vs Actual Latency Scatter</h2>
    <div class="svg-wrap">{scatter_svg}</div>
  </div>

  <div class="section">
    <h2>Feature Importance</h2>
    <div class="charts">
      <div class="svg-wrap">{importance_svg}</div>
      <table class="feat-table" style="max-width:320px">
        <thead><tr><th>Feature</th><th>Importance</th></tr></thead>
        <tbody>{feat_rows}</tbody>
      </table>
    </div>
  </div>
</div>
<footer>OCI Robot Cloud · Latency Predictor · port 8291 · {ts}</footer>
</body>
</html>
"""


def build_html() -> str:
    feat_rows = "".join(
        f'<tr><td>{name}</td><td class="highlight">{int(imp*100)}%</td></tr>'
        for name, imp in FEATURES
    )
    return HTML_TEMPLATE.format(
        rmse=EMPIRICAL_RMSE,
        n=N_REQUESTS,
        sla=EMPIRICAL_SLA_PCT,
        n_outliers=N_OUTLIERS,
        scatter_svg=build_scatter_svg(),
        importance_svg=build_importance_svg(),
        feat_rows=feat_rows,
        ts=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )


# ---------------------------------------------------------------------------
# FastAPI app  /  stdlib fallback
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Latency Predictor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "latency_predictor", "port": 8291}

    @app.get("/metrics")
    def metrics():
        return {
            "rmse_ms": EMPIRICAL_RMSE,
            "sla_compliance_pct": EMPIRICAL_SLA_PCT,
            "n_outliers": N_OUTLIERS,
            "n_requests": N_REQUESTS,
            "feature_importance": [{"feature": f, "importance": i} for f, i in FEATURES],
        }

    @app.get("/predict")
    def predict(gpu_util: float = 0.5, batch_size: int = 4, model_size: int = 7):
        """Simple rule-based latency estimate (mock)."""
        predicted = 80 + 120 * gpu_util + 8 * math.log(batch_size + 1) + 5 * math.log(model_size + 1)
        confidence = max(0.0, 1.0 - abs(gpu_util - 0.5))
        return {
            "predicted_latency_ms": round(predicted, 1),
            "confidence": round(confidence, 3),
            "within_sla_30ms": confidence > 0.5,
        }

    @app.get("/scatter_data")
    def scatter_data():
        return {"points": SCATTER}

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": 8291}).encode()
                ct = "application/json"
            else:
                body = build_html().encode()
                ct = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8291)
    else:
        print("[latency_predictor] fastapi not found — using stdlib http.server on :8291")
        HTTPServer(("0.0.0.0", 8291), Handler).serve_forever()

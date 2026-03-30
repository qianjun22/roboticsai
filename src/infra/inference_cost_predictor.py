"""inference_cost_predictor.py — FastAPI service on port 8214.

Predicts per-request inference cost based on model size, batch size,
and hardware provider. Serves a dark-theme HTML dashboard with SVG
visualizations showing cost curves and cloud provider comparisons.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

import math
import random
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data helpers
# ---------------------------------------------------------------------------

MODELS = {
    "GR00T-1.5B": {"base_cost": 0.28, "optimal_batch": 4,  "color": "#38bdf8"},
    "GR00T-3B":   {"base_cost": 0.43, "optimal_batch": 8,  "color": "#C74634"},
    "GR00T-7B":   {"base_cost": 0.91, "optimal_batch": 16, "color": "#a78bfa"},
}

PROVIDERS = {
    "OCI A100":   {"multiplier": 1.0,  "color": "#C74634"},
    "AWS p4d":    {"multiplier": 9.6,  "color": "#fb923c"},
    "Azure NDv4": {"multiplier": 7.2,  "color": "#38bdf8"},
}

def cost_at_batch(base_cost: float, optimal_batch: int, batch: int) -> float:
    """Simulate a U-shaped cost curve around the optimal batch size."""
    efficiency = 1.0 + 0.4 * math.log(optimal_batch / max(batch, 1) + 1) \
                     + 0.15 * ((batch - optimal_batch) / optimal_batch) ** 2
    noise = 1.0 + random.uniform(-0.015, 0.015)
    return round(base_cost * efficiency * noise, 4)

def build_cost_table() -> dict:
    """Pre-compute cost/1000 requests for each model × batch."""
    batches = list(range(1, 33))
    table = {}
    for model, cfg in MODELS.items():
        table[model] = [
            cost_at_batch(cfg["base_cost"], cfg["optimal_batch"], b)
            for b in batches
        ]
    return {"batches": batches, "models": table}

def monthly_cost(base_per_1k: float, volume: int) -> float:
    return round(base_per_1k * volume / 1000, 2)

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_line_chart(data: dict) -> str:
    """Line chart: cost/1000 requests vs batch size for 3 model variants."""
    W, H = 560, 280
    pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 50
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    batches = data["batches"]
    all_costs = [c for vals in data["models"].values() for c in vals]
    y_max = max(all_costs) * 1.1
    y_min = 0.0

    def px(b_idx: int) -> float:
        return pad_l + (b_idx / (len(batches) - 1)) * plot_w

    def py(cost: float) -> float:
        return pad_t + plot_h - (cost - y_min) / (y_max - y_min) * plot_h

    lines = []
    for model, costs in data["models"].items():
        color = MODELS[model]["color"]
        pts = " ".join(f"{px(i):.1f},{py(c):.1f}" for i, c in enumerate(costs))
        lines.append(
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="2.5" stroke-linejoin="round"/>'
        )
        # label at last point
        lx = px(len(costs) - 1) + 4
        ly = py(costs[-1])
        lines.append(
            f'<text x="{lx:.0f}" y="{ly:.0f}" fill="{color}" '
            f'font-size="10" dominant-baseline="middle">{model}</text>'
        )

    # Axes
    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" '
        f'stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" '
        f'stroke="#475569" stroke-width="1"/>'
    )
    # X ticks
    xticks = ""
    for i, b in enumerate(batches):
        if b in (1, 4, 8, 16, 24, 32):
            x = px(i)
            xticks += (
                f'<text x="{x:.0f}" y="{pad_t+plot_h+14}" fill="#94a3b8" '
                f'font-size="10" text-anchor="middle">{b}</text>'
            )
    # Y ticks
    yticks = ""
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        cost = y_min + frac * (y_max - y_min)
        y = py(cost)
        yticks += (
            f'<text x="{pad_l-6}" y="{y:.0f}" fill="#94a3b8" '
            f'font-size="10" text-anchor="end" dominant-baseline="middle">${cost:.2f}</text>'
            f'<line x1="{pad_l}" y1="{y:.0f}" x2="{pad_l+plot_w}" y2="{y:.0f}" '
            f'stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>'
        )
    labels = (
        f'<text x="{pad_l + plot_w//2}" y="{H-4}" fill="#64748b" '
        f'font-size="11" text-anchor="middle">Batch Size</text>'
        f'<text transform="rotate(-90)" x="-{pad_t+plot_h//2}" y="14" '
        f'fill="#64748b" font-size="11" text-anchor="middle">$/1000 req</text>'
    )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;max-width:{W}px;background:#1e293b;border-radius:8px">'
        + yticks + axes + "".join(lines) + xticks + labels
        + '</svg>'
    )


def svg_bar_chart(model: str = "GR00T-3B") -> str:
    """Bar chart: OCI A100 vs AWS p4d vs Azure NDv4 at optimal batch."""
    W, H = 440, 240
    pad_l, pad_r, pad_t, pad_b = 70, 20, 20, 50
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    base = MODELS[model]["base_cost"]
    bars = {prov: round(base * cfg["multiplier"], 3) for prov, cfg in PROVIDERS.items()}
    y_max = max(bars.values()) * 1.15

    n = len(bars)
    bar_w = (plot_w - (n - 1) * 12) / n
    svgs = []

    for i, (prov, cost) in enumerate(bars.items()):
        color = PROVIDERS[prov]["color"]
        bh = (cost / y_max) * plot_h
        bx = pad_l + i * (bar_w + 12)
        by = pad_t + plot_h - bh
        svgs.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
            f'fill="{color}" rx="4"/>'
            f'<text x="{bx+bar_w/2:.1f}" y="{by-6:.1f}" fill="{color}" '
            f'font-size="11" text-anchor="middle">${cost:.3f}</text>'
            f'<text x="{bx+bar_w/2:.1f}" y="{pad_t+plot_h+16:.1f}" fill="#94a3b8" '
            f'font-size="10" text-anchor="middle">{prov}</text>'
        )

    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" '
        f'stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" '
        f'stroke="#475569" stroke-width="1"/>'
    )
    yticks = ""
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        cost = frac * y_max
        y = pad_t + plot_h - frac * plot_h
        yticks += (
            f'<text x="{pad_l-6}" y="{y:.0f}" fill="#94a3b8" '
            f'font-size="10" text-anchor="end" dominant-baseline="middle">${cost:.2f}</text>'
            f'<line x1="{pad_l}" y1="{y:.0f}" x2="{pad_l+plot_w}" y2="{y:.0f}" '
            f'stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>'
        )

    title = (
        f'<text x="{W//2}" y="{H-4}" fill="#64748b" font-size="11" '
        f'text-anchor="middle">$/1000 req at optimal batch — {model}</text>'
    )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;max-width:{W}px;background:#1e293b;border-radius:8px">'
        + yticks + axes + "".join(svgs) + title
        + '</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    random.seed(42)
    data = build_cost_table()
    svg1 = svg_line_chart(data)
    svg2 = svg_bar_chart("GR00T-3B")

    oci_base = MODELS["GR00T-3B"]["base_cost"]
    breakeven = MODELS["GR00T-3B"]["optimal_batch"]
    costs = {
        "10k/mo":  monthly_cost(oci_base, 10_000),
        "100k/mo": monthly_cost(oci_base, 100_000),
        "1M/mo":   monthly_cost(oci_base, 1_000_000),
    }
    cost_per_grasp = round(oci_base / 1000 * 1.15, 6)  # ~15% overhead
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    def kpi(label, val, unit=""):
        return (
            f'<div style="background:#1e293b;border-radius:8px;padding:16px 20px;'
            f'min-width:140px;text-align:center">'
            f'<div style="font-size:22px;font-weight:700;color:#38bdf8">{val}{unit}</div>'
            f'<div style="font-size:11px;color:#94a3b8;margin-top:4px">{label}</div></div>'
        )

    kpis = (
        kpi("Breakeven Batch", breakeven, "")
        + kpi("10k req/mo", f"${costs['10k/mo']}", "")
        + kpi("100k req/mo", f"${costs['100k/mo']}", "")
        + kpi("1M req/mo", f"${costs['1M/mo']}", "")
        + kpi("Cost/Grasp", f"${cost_per_grasp}", "")
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Inference Cost Predictor — OCI Robot Cloud</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #e2e8f0;
      font-family: 'Segoe UI', system-ui, sans-serif;
      min-height: 100vh;
      padding: 24px;
    }}
    h1 {{ font-size: 22px; font-weight: 700; color: #f8fafc; }}
    h2 {{ font-size: 15px; font-weight: 600; color: #94a3b8;
          margin: 24px 0 10px; text-transform: uppercase; letter-spacing: .05em; }}
    .badge {{
      background: #C74634;
      color: #fff;
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 999px;
      margin-left: 10px;
      vertical-align: middle;
    }}
    .header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 20px;
    }}
    .ts {{ font-size: 11px; color: #475569; }}
    .kpis {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 24px;
    }}
    .charts {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }}
    .card {{
      background: #1e293b;
      border-radius: 10px;
      padding: 16px;
    }}
    .card-title {{
      font-size: 13px;
      font-weight: 600;
      color: #cbd5e1;
      margin-bottom: 12px;
    }}
    @media (max-width: 700px) {{
      .charts {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>Inference Cost Predictor <span class="badge">port 8214</span></h1>
      <p style="font-size:13px;color:#64748b;margin-top:4px">GR00T model family · OCI A100 baseline</p>
    </div>
    <div class="ts">{ts}</div>
  </div>

  <h2>Key Metrics — GR00T-3B on OCI A100</h2>
  <div class="kpis">{kpis}</div>

  <div class="charts">
    <div class="card">
      <div class="card-title">Cost/1000 Requests vs Batch Size</div>
      {svg1}
    </div>
    <div class="card">
      <div class="card-title">Cloud Provider Comparison at Optimal Batch</div>
      {svg2}
    </div>
  </div>

  <p style="font-size:11px;color:#334155;margin-top:24px;text-align:center">
    OCI Robot Cloud · Inference Cost Predictor · port 8214
  </p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app (with stdlib fallback)
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="Inference Cost Predictor",
        description="Predicts per-request inference cost for GR00T model variants.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "inference_cost_predictor", "port": 8214}

    @app.get("/api/predict")
    async def predict(model: str = "GR00T-3B", batch: int = 8, provider: str = "OCI A100"):
        """Return predicted cost/1000 requests for given configuration."""
        if model not in MODELS:
            return {"error": f"Unknown model. Choose from: {list(MODELS.keys())}"}
        if provider not in PROVIDERS:
            return {"error": f"Unknown provider. Choose from: {list(PROVIDERS.keys())}"}
        base = MODELS[model]["base_cost"]
        opt = MODELS[model]["optimal_batch"]
        mult = PROVIDERS[provider]["multiplier"]
        cost = round(cost_at_batch(base, opt, batch) * mult, 4)
        return {
            "model": model,
            "batch": batch,
            "provider": provider,
            "cost_per_1k_requests": cost,
            "cost_per_request": round(cost / 1000, 7),
            "monthly_10k": monthly_cost(cost, 10_000),
            "monthly_100k": monthly_cost(cost, 100_000),
            "monthly_1M": monthly_cost(cost, 1_000_000),
        }

    @app.get("/api/cost-table")
    async def cost_table():
        random.seed(42)
        return build_cost_table()

else:
    # stdlib fallback
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

        def log_message(self, fmt, *args):  # suppress default logging
            pass


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8214)
    else:
        print("[inference_cost_predictor] FastAPI not found — using stdlib on port 8214")
        with socketserver.TCPServer(("", 8214), _Handler) as srv:
            srv.serve_forever()

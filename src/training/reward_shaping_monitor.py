"""reward_shaping_monitor.py — FastAPI service on port 8212.

Monitors DAgger reward signal components and shaping weights.
Cycle-38A: OCI Robot Cloud reward shaping dashboard.
"""

from __future__ import annotations

import math
import random
import json
from typing import List, Dict, Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

# ---------------------------------------------------------------------------
# Mock data generation (stdlib only — no numpy/pandas/torch)
# ---------------------------------------------------------------------------

def _generate_reward_data(num_episodes: int = 100) -> List[Dict[str, Any]]:
    """Generate realistic DAgger run10 reward component data."""
    random.seed(42)
    episodes = []
    reach_base = 0.15
    grasp_base = 0.08
    lift_base = 0.0
    stability_base = 0.05

    for ep in range(num_episodes):
        t = ep / (num_episodes - 1)  # 0 → 1

        # reach_reward: rises quickly, plateaus
        reach = reach_base + 0.45 * (1 - math.exp(-5 * t)) + random.gauss(0, 0.012)
        reach = max(0.0, min(0.65, reach))

        # grasp_reward: sigmoid rise, starts meaningful around ep 20
        grasp = grasp_base + 0.52 * (1 / (1 + math.exp(-10 * (t - 0.25)))) + random.gauss(0, 0.015)
        grasp = max(0.0, min(0.62, grasp))

        # lift_reward: 0 → 0.65 by ep 80, slow start
        lift = 0.65 * (1 / (1 + math.exp(-12 * (t - 0.4)))) + random.gauss(0, 0.018)
        lift = max(0.0, min(0.70, lift))

        # stability_reward: rises steadily with some noise
        stability = stability_base + 0.30 * t + random.gauss(0, 0.010)
        stability = max(0.0, min(0.40, stability))

        # shaped vs unshaped total
        shaped = reach + grasp + lift + stability
        unshaped = reach * 0.55 + grasp * 0.60 + lift * 0.80 + stability * 0.50

        episodes.append({
            "episode": ep,
            "reach_reward": round(reach, 4),
            "grasp_reward": round(grasp, 4),
            "lift_reward": round(lift, 4),
            "stability_reward": round(stability, 4),
            "shaped_total": round(shaped, 4),
            "unshaped_total": round(unshaped, 4),
        })
    return episodes


REWARD_DATA: List[Dict[str, Any]] = _generate_reward_data(100)


def _compute_metrics() -> Dict[str, Any]:
    last10 = REWARD_DATA[-10:]
    avg_reach = sum(d["reach_reward"] for d in last10) / 10
    avg_grasp = sum(d["grasp_reward"] for d in last10) / 10
    avg_lift = sum(d["lift_reward"] for d in last10) / 10
    avg_stability = sum(d["stability_reward"] for d in last10) / 10
    total = avg_reach + avg_grasp + avg_lift + avg_stability
    balance = 1.0 - (max(avg_reach, avg_grasp, avg_lift, avg_stability) - min(avg_reach, avg_grasp, avg_lift, avg_stability)) / (total + 1e-9)
    terminal_ratio = avg_lift / (total + 1e-9)
    # shaping benefit: shaped advantage at ep60 vs ep99
    ep60 = REWARD_DATA[60]
    ep99 = REWARD_DATA[99]
    benefit_ep60 = ep60["shaped_total"] - ep60["unshaped_total"]
    benefit_ep99 = ep99["shaped_total"] - ep99["unshaped_total"]
    return {
        "component_balance_score": round(balance, 3),
        "terminal_reward_ratio": round(terminal_ratio, 3),
        "shaping_benefit_ep60": round(benefit_ep60, 4),
        "shaping_benefit_ep99": round(benefit_ep99, 4),
        "shaping_decay_schedule": "exponential_0.97_per_episode",
        "dagger_run": "run10",
        "total_episodes": 100,
    }


# ---------------------------------------------------------------------------
# SVG chart builders
# ---------------------------------------------------------------------------

def _svg_stacked_area(data: List[Dict[str, Any]], width: int = 720, height: int = 280) -> str:
    """Stacked area chart: reach + grasp + lift + stability over episodes."""
    pad_l, pad_r, pad_t, pad_b = 52, 20, 20, 40
    W = width - pad_l - pad_r
    H = height - pad_t - pad_b
    n = len(data)

    # Compute stacked y values — bottom-up: reach, grasp, lift, stability
    layers = ["reach_reward", "grasp_reward", "lift_reward", "stability_reward"]
    colors = ["#38bdf8", "#C74634", "#4ade80", "#f59e0b"]
    labels = ["Reach", "Grasp", "Lift", "Stability"]

    max_val = max(sum(d[k] for k in layers) for d in data) * 1.05

    def xp(i):
        return pad_l + i / (n - 1) * W

    def yp(v):
        return pad_t + H - (v / max_val) * H

    # Build cumulative stacks
    stacks: List[List[float]] = []
    for li, layer in enumerate(layers):
        cumulative = []
        for d in data:
            cum = sum(d[layers[j]] for j in range(li + 1))
            cumulative.append(cum)
        stacks.append(cumulative)

    def area_path(top_vals: List[float], bot_vals: List[float]) -> str:
        pts_top = " ".join(f"{xp(i):.1f},{yp(top_vals[i]):.1f}" for i in range(n))
        pts_bot = " ".join(f"{xp(i):.1f},{yp(bot_vals[i]):.1f}" for i in range(n - 1, -1, -1))
        return f"M {pts_top.split()[0]} L {pts_top} L {pts_bot} Z"

    areas = []
    for li in range(len(layers)):
        top = stacks[li]
        bot = stacks[li - 1] if li > 0 else [0.0] * n
        path = area_path(top, bot)
        areas.append(f'<path d="{path}" fill="{colors[li]}" fill-opacity="0.75" />')

    # X axis ticks
    x_ticks = ""
    for ep in range(0, 101, 20):
        xi = xp(ep)
        x_ticks += f'<line x1="{xi:.1f}" y1="{pad_t + H}" x2="{xi:.1f}" y2="{pad_t + H + 5}" stroke="#64748b" />'
        x_ticks += f'<text x="{xi:.1f}" y="{pad_t + H + 18}" text-anchor="middle" fill="#94a3b8" font-size="11">Ep {ep}</text>'

    # Y axis ticks
    y_ticks = ""
    for tick in [0.0, 0.5, 1.0, 1.5]:
        yi = yp(tick)
        if tick <= max_val:
            y_ticks += f'<line x1="{pad_l - 4}" y1="{yi:.1f}" x2="{pad_l + W}" y2="{yi:.1f}" stroke="#1e293b" />'
            y_ticks += f'<text x="{pad_l - 8}" y="{yi + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="11">{tick:.1f}</text>'

    # Legend
    legend = ""
    for li, (lbl, col) in enumerate(zip(labels, colors)):
        lx = pad_l + li * 130
        legend += f'<rect x="{lx}" y="{height - 14}" width="12" height="12" fill="{col}" fill-opacity="0.8" rx="2" />'
        legend += f'<text x="{lx + 16}" y="{height - 4}" fill="#94a3b8" font-size="11">{lbl}</text>'

    svg = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" fill="#0f172a" rx="8" />
  <text x="{width // 2}" y="14" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">Reward Components — DAgger Run10 (Stacked)</text>
  {''.join(areas)}
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + H}" stroke="#475569" stroke-width="1" />
  <line x1="{pad_l}" y1="{pad_t + H}" x2="{pad_l + W}" y2="{pad_t + H}" stroke="#475569" stroke-width="1" />
  {x_ticks}
  {y_ticks}
  {legend}
</svg>"""
    return svg


def _svg_shaping_comparison(data: List[Dict[str, Any]], width: int = 720, height: int = 260) -> str:
    """Line chart: shaped vs unshaped reward — shaping benefit diminishes after ep60."""
    pad_l, pad_r, pad_t, pad_b = 52, 20, 24, 40
    W = width - pad_l - pad_r
    H = height - pad_t - pad_b
    n = len(data)

    all_vals = [d["shaped_total"] for d in data] + [d["unshaped_total"] for d in data]
    min_v = min(all_vals) * 0.9
    max_v = max(all_vals) * 1.05

    def xp(i): return pad_l + i / (n - 1) * W
    def yp(v): return pad_t + H - (v - min_v) / (max_v - min_v) * H

    def polyline(key, color, dash=""):
        pts = " ".join(f"{xp(i):.1f},{yp(data[i][key]):.1f}" for i in range(n))
        da = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"{da} />'

    shaped_line = polyline("shaped_total", "#38bdf8")
    unshaped_line = polyline("unshaped_total", "#C74634", "6,3")

    # Vertical marker at ep60
    x60 = xp(60)
    marker = f'<line x1="{x60:.1f}" y1="{pad_t}" x2="{x60:.1f}" y2="{pad_t + H}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,4" />'
    marker += f'<text x="{x60 + 4:.1f}" y="{pad_t + 14}" fill="#f59e0b" font-size="11">Ep 60\ndiminish</text>'

    # Fill between curves
    fill_pts_top = " ".join(f"{xp(i):.1f},{yp(data[i]['shaped_total']):.1f}" for i in range(n))
    fill_pts_bot = " ".join(f"{xp(i):.1f},{yp(data[i]['unshaped_total']):.1f}" for i in range(n - 1, -1, -1))
    fill_area = f'<path d="M {fill_pts_top.split()[0]} L {fill_pts_top} L {fill_pts_bot} Z" fill="#38bdf8" fill-opacity="0.10" />'

    # Ticks
    x_ticks = ""
    for ep in range(0, 101, 20):
        xi = xp(ep)
        x_ticks += f'<line x1="{xi:.1f}" y1="{pad_t + H}" x2="{xi:.1f}" y2="{pad_t + H + 5}" stroke="#64748b" />'
        x_ticks += f'<text x="{xi:.1f}" y="{pad_t + H + 18}" text-anchor="middle" fill="#94a3b8" font-size="11">Ep {ep}</text>'

    y_ticks = ""
    steps = 5
    for i in range(steps + 1):
        v = min_v + (max_v - min_v) * i / steps
        yi = yp(v)
        y_ticks += f'<line x1="{pad_l}" y1="{yi:.1f}" x2="{pad_l + W}" y2="{yi:.1f}" stroke="#1e293b" />'
        y_ticks += f'<text x="{pad_l - 8}" y="{yi + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="11">{v:.2f}</text>'

    legend = (
        f'<rect x="{pad_l}" y="{height - 14}" width="12" height="3" fill="#38bdf8" />'
        f'<text x="{pad_l + 16}" y="{height - 4}" fill="#94a3b8" font-size="11">Shaped Reward</text>'
        f'<rect x="{pad_l + 140}" y="{height - 14}" width="12" height="3" fill="#C74634" />'
        f'<text x="{pad_l + 156}" y="{height - 4}" fill="#94a3b8" font-size="11">Unshaped Reward</text>'
        f'<line x1="{pad_l + 310}" y1="{height - 12}" x2="{pad_l + 322}" y2="{height - 12}" stroke="#f59e0b" stroke-dasharray="4,3" />'
        f'<text x="{pad_l + 326}" y="{height - 4}" fill="#94a3b8" font-size="11">Shaping Diminish Point</text>'
    )

    svg = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" fill="#0f172a" rx="8" />
  <text x="{width // 2}" y="16" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">Shaped vs Unshaped Reward — Benefit Diminishes After Ep 60</text>
  {fill_area}
  {shaped_line}
  {unshaped_line}
  {marker}
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + H}" stroke="#475569" stroke-width="1" />
  <line x1="{pad_l}" y1="{pad_t + H}" x2="{pad_l + W}" y2="{pad_t + H}" stroke="#475569" stroke-width="1" />
  {x_ticks}
  {y_ticks}
  {legend}
</svg>"""
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    metrics = _compute_metrics()
    svg1 = _svg_stacked_area(REWARD_DATA)
    svg2 = _svg_shaping_comparison(REWARD_DATA)

    metric_cards = ""
    card_data = [
        ("Component Balance", f"{metrics['component_balance_score']:.3f}", "higher = more balanced"),
        ("Terminal Reward Ratio", f"{metrics['terminal_reward_ratio']:.1%}", "lift share of total"),
        ("Shaping Benefit Ep60", f"{metrics['shaping_benefit_ep60']:+.4f}", "shaped advantage at ep 60"),
        ("Shaping Benefit Ep99", f"{metrics['shaping_benefit_ep99']:+.4f}", "shaped advantage at ep 99"),
        ("Decay Schedule", metrics['shaping_decay_schedule'].replace('_', ' '), "per-episode decay rate"),
        ("DAgger Run", metrics['dagger_run'], f"{metrics['total_episodes']} episodes"),
    ]
    for title, value, sub in card_data:
        metric_cards += f"""
        <div class="card">
          <div class="card-label">{title}</div>
          <div class="card-value">{value}</div>
          <div class="card-sub">{sub}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Reward Shaping Monitor — Port 8212</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ font-size: 1.5rem; color: #38bdf8; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
    .badge {{ display: inline-block; background: #C74634; color: #fff; font-size: 0.72rem;
              padding: 2px 8px; border-radius: 4px; margin-left: 10px; vertical-align: middle; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }}
    .card-label {{ font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }}
    .card-value {{ font-size: 1.4rem; font-weight: 700; color: #38bdf8; }}
    .card-sub {{ font-size: 0.72rem; color: #64748b; margin-top: 4px; }}
    .chart-section {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
                      padding: 20px; margin-bottom: 20px; }}
    .chart-title {{ font-size: 0.9rem; color: #94a3b8; margin-bottom: 12px; }}
    .chart-section svg {{ width: 100%; max-width: 720px; display: block; margin: 0 auto; }}
    footer {{ margin-top: 24px; font-size: 0.75rem; color: #334155; text-align: center; }}
  </style>
</head>
<body>
  <h1>Reward Shaping Monitor <span class="badge">PORT 8212</span></h1>
  <div class="subtitle">DAgger run10 — reward component breakdown &amp; shaping benefit analysis — OCI Robot Cloud cycle-38A</div>

  <div class="metrics">{metric_cards}</div>

  <div class="chart-section">
    <div class="chart-title">Stacked Reward Components Over Episodes (Reach / Grasp / Lift / Stability)</div>
    {svg1}
  </div>

  <div class="chart-section">
    <div class="chart-title">Shaped vs Unshaped Reward — Shaping Benefit Diminishes After Episode 60</div>
    {svg2}
  </div>

  <footer>OCI Robot Cloud &mdash; Reward Shaping Monitor v1.0 &mdash; cycle-38A</footer>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# FastAPI app (with stdlib fallback)
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Reward Shaping Monitor",
        description="Monitor DAgger reward signal components and shaping weights",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_build_html())

    @app.get("/api/episodes", response_class=JSONResponse)
    async def get_episodes():
        return JSONResponse(content=REWARD_DATA)

    @app.get("/api/metrics", response_class=JSONResponse)
    async def get_metrics():
        return JSONResponse(content=_compute_metrics())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "reward_shaping_monitor", "port": 8212}

else:
    # Stdlib fallback
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # silence default logs
            pass


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=8212)
    else:
        print("[reward_shaping_monitor] fastapi not found — using stdlib http.server on port 8212")
        with socketserver.TCPServer(("", 8212), _Handler) as srv:
            srv.serve_forever()

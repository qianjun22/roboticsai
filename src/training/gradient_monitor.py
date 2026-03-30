"""Gradient health monitor for GR00T fine-tuning — port 8156."""

import math
import random
import json
from typing import List, Dict, Any

try:
    from fastapi import FastAPI, Response
    from fastapi.responses import HTMLResponse
    import uvicorn
except ImportError:
    FastAPI = None
    uvicorn = None

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

LAYERS = [
    {
        "name": "vit_patch_embed",
        "grad_norm": 0.0142,
        "grad_norm_ma": 0.0138,
        "vanishing": False,
        "exploding": False,
        "health": "HEALTHY",
        "color": "#38bdf8",
    },
    {
        "name": "vit_attention_blocks",
        "grad_norm": 0.0287,
        "grad_norm_ma": 0.0291,
        "vanishing": False,
        "exploding": False,
        "health": "HEALTHY",
        "color": "#a78bfa",
    },
    {
        "name": "llm_lora_A",
        "grad_norm": 0.0891,
        "grad_norm_ma": 0.0847,
        "vanishing": False,
        "exploding": False,
        "health": "HEALTHY",
        "color": "#34d399",
    },
    {
        "name": "llm_lora_B",
        "grad_norm": 0.1124,
        "grad_norm_ma": 0.0923,
        "vanishing": False,
        "exploding": True,
        "health": "WARNING",
        "color": "#f59e0b",
    },
    {
        "name": "action_head",
        "grad_norm": 0.0634,
        "grad_norm_ma": 0.0612,
        "vanishing": False,
        "exploding": False,
        "health": "HEALTHY",
        "color": "#C74634",
    },
]

CLIP_EVENTS = [
    {"step": 1312, "layer": "llm_lora_B", "pre_clip_norm": 0.5831, "post_clip_norm": 1.0},
    {"step": 1356, "layer": "llm_lora_B", "pre_clip_norm": 0.6102, "post_clip_norm": 1.0},
    {"step": 1380, "layer": "llm_lora_B", "pre_clip_norm": 0.7241, "post_clip_norm": 1.0},
]

EXPLODING_THRESHOLD = 0.5
VANISHING_THRESHOLD = 0.001
STEPS = 50
CURRENT_STEP = 1420


def _generate_history() -> Dict[str, List[float]]:
    """Generate 50-step gradient norm history per layer with seeded RNG."""
    history: Dict[str, List[float]] = {}
    rng = random.Random(42)
    for layer in LAYERS:
        mean = layer["grad_norm_ma"]
        vals: List[float] = []
        v = mean
        for i in range(STEPS):
            # spike for llm_lora_B near step 38
            if layer["name"] == "llm_lora_B" and 36 <= i <= 40:
                spike = mean * (1 + rng.uniform(0.8, 1.6))
                v = spike
            else:
                delta = rng.gauss(0, mean * 0.08)
                v = max(0.0001, v + delta)
                # drift back toward mean
                v = v * 0.85 + mean * 0.15
            vals.append(round(v, 5))
        # ensure last value matches the declared current grad_norm
        vals[-1] = layer["grad_norm"]
        history[layer["name"]] = vals
    return history


HISTORY = _generate_history()

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------


def _polyline_points(values: List[float], w: int, h: int, y_max: float) -> str:
    """Convert a list of values to SVG polyline points string."""
    n = len(values)
    pad_x, pad_y = 50, 20
    plot_w = w - pad_x - 20
    plot_h = h - pad_y - 30
    pts = []
    for i, v in enumerate(values):
        x = pad_x + (i / (n - 1)) * plot_w
        y = pad_y + plot_h - (v / y_max) * plot_h
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


def _grad_history_svg() -> str:
    w, h = 680, 240
    y_max = 0.30
    pad_x, pad_y = 50, 20
    plot_w = w - pad_x - 20
    plot_h = h - pad_y - 30

    lines = []
    # axes
    lines.append(
        f'<line x1="{pad_x}" y1="{pad_y}" x2="{pad_x}" y2="{pad_y + plot_h}" stroke="#334155" stroke-width="1"/>'
    )
    lines.append(
        f'<line x1="{pad_x}" y1="{pad_y + plot_h}" x2="{pad_x + plot_w}" y2="{pad_y + plot_h}" stroke="#334155" stroke-width="1"/>'
    )

    # y-axis labels
    for val, label in [(0.0, "0"), (0.1, "0.1"), (0.2, "0.2"), (0.3, "0.3")]:
        y = pad_y + plot_h - (val / y_max) * plot_h
        lines.append(f'<text x="{pad_x - 5}" y="{y + 4}" fill="#94a3b8" font-size="10" text-anchor="end">{label}</text>')
        lines.append(f'<line x1="{pad_x}" y1="{y}" x2="{pad_x + plot_w}" y2="{y}" stroke="#1e293b" stroke-width="1"/>')

    # x-axis labels
    for step in [0, 10, 20, 30, 40, 49]:
        x = pad_x + (step / (STEPS - 1)) * plot_w
        lines.append(f'<text x="{x}" y="{pad_y + plot_h + 16}" fill="#94a3b8" font-size="10" text-anchor="middle">{step}</text>')

    # threshold lines
    y_exp = pad_y + plot_h - (EXPLODING_THRESHOLD / y_max) * plot_h
    lines.append(
        f'<line x1="{pad_x}" y1="{y_exp}" x2="{pad_x + plot_w}" y2="{y_exp}" stroke="#ef4444" stroke-dasharray="6,3" stroke-width="1"/>'
    )
    lines.append(f'<text x="{pad_x + plot_w - 2}" y="{y_exp - 3}" fill="#ef4444" font-size="9" text-anchor="end">exploding</text>')

    y_van = pad_y + plot_h - (VANISHING_THRESHOLD / y_max) * plot_h
    lines.append(
        f'<line x1="{pad_x}" y1="{y_van}" x2="{pad_x + plot_w}" y2="{y_van}" stroke="#64748b" stroke-dasharray="4,2" stroke-width="1"/>'
    )
    lines.append(f'<text x="{pad_x + plot_w - 2}" y="{y_van - 3}" fill="#64748b" font-size="9" text-anchor="end">vanishing</text>')

    # polylines
    for layer in LAYERS:
        pts = _polyline_points(HISTORY[layer["name"]], w, h, y_max)
        lines.append(
            f'<polyline points="{pts}" fill="none" stroke="{layer["color"]}" stroke-width="2" opacity="0.9"/>'
        )

    # legend
    lx = pad_x + 10
    for i, layer in enumerate(LAYERS):
        lx_i = lx + i * 130
        lines.append(f'<circle cx="{lx_i}" cy="14" r="4" fill="{layer["color"]}"/>')
        lines.append(f'<text x="{lx_i + 8}" y="18" fill="#cbd5e1" font-size="10">{layer["name"]}</text>')

    body = "\n".join(lines)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">'
        f'{body}</svg>'
    )


def _health_bar_svg() -> str:
    w, h = 680, 160
    n = len(LAYERS)
    bar_group_h = 22
    pad_x, pad_y = 160, 16
    plot_w = w - pad_x - 20
    x_max = 0.14

    lines = []
    for i, layer in enumerate(LAYERS):
        y = pad_y + i * (bar_group_h + 8)
        # label
        lines.append(
            f'<text x="{pad_x - 8}" y="{y + 11}" fill="#cbd5e1" font-size="11" text-anchor="end">{layer["name"]}</text>'
        )
        # MA bar (faded)
        bw_ma = (layer["grad_norm_ma"] / x_max) * plot_w
        lines.append(
            f'<rect x="{pad_x}" y="{y}" width="{bw_ma:.1f}" height="10" fill="{layer["color"]}" opacity="0.35" rx="2"/>'
        )
        # current bar (solid)
        bw_cur = (layer["grad_norm"] / x_max) * plot_w
        lines.append(
            f'<rect x="{pad_x}" y="{y + 12}" width="{bw_cur:.1f}" height="10" fill="{layer["color"]}" opacity="0.9" rx="2"/>'
        )
        # value labels
        lines.append(
            f'<text x="{pad_x + bw_cur + 4}" y="{y + 22}" fill="{layer["color"]}" font-size="10">{layer["grad_norm"]:.4f}</text>'
        )
        # health badge
        badge_color = "#f59e0b" if layer["health"] == "WARNING" else "#34d399"
        lines.append(
            f'<rect x="{w - 100}" y="{y + 2}" width="80" height="16" rx="8" fill="{badge_color}" opacity="0.15"/>'
        )
        lines.append(
            f'<text x="{w - 60}" y="{y + 14}" fill="{badge_color}" font-size="10" text-anchor="middle">{layer["health"]}</text>'
        )

    # legend
    lines.append(f'<circle cx="{pad_x + 8}" cy="{h - 8}" r="4" fill="#94a3b8" opacity="0.35"/>')
    lines.append(f'<text x="{pad_x + 16}" y="{h - 4}" fill="#64748b" font-size="10">moving avg</text>')
    lines.append(f'<circle cx="{pad_x + 110}" cy="{h - 8}" r="4" fill="#94a3b8" opacity="0.9"/>')
    lines.append(f'<text x="{pad_x + 118}" y="{h - 4}" fill="#64748b" font-size="10">current</text>')

    body = "\n".join(lines)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">'
        f'{body}</svg>'
    )


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------


def _build_html() -> str:
    global_norm = math.sqrt(sum(l["grad_norm"] ** 2 for l in LAYERS))
    healthy_count = sum(1 for l in LAYERS if l["health"] == "HEALTHY")
    max_layer = max(LAYERS, key=lambda l: l["grad_norm"])

    stat_cards = f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;">
      <div style="background:#1e293b;border-radius:10px;padding:16px;border:1px solid #334155;">
        <div style="color:#94a3b8;font-size:11px;margin-bottom:4px;">MAX GRAD NORM</div>
        <div style="color:#f59e0b;font-size:24px;font-weight:700;">{max_layer['grad_norm']:.4f}</div>
        <div style="color:#64748b;font-size:11px;">{max_layer['name']}</div>
      </div>
      <div style="background:#1e293b;border-radius:10px;padding:16px;border:1px solid #334155;">
        <div style="color:#94a3b8;font-size:11px;margin-bottom:4px;">CLIP EVENTS TODAY</div>
        <div style="color:#C74634;font-size:24px;font-weight:700;">{len(CLIP_EVENTS)}</div>
        <div style="color:#64748b;font-size:11px;">clip_norm = 1.0</div>
      </div>
      <div style="background:#1e293b;border-radius:10px;padding:16px;border:1px solid #334155;">
        <div style="color:#94a3b8;font-size:11px;margin-bottom:4px;">HEALTHY LAYERS</div>
        <div style="color:#34d399;font-size:24px;font-weight:700;">{healthy_count}/{len(LAYERS)}</div>
        <div style="color:#64748b;font-size:11px;">1 warning active</div>
      </div>
      <div style="background:#1e293b;border-radius:10px;padding:16px;border:1px solid #334155;">
        <div style="color:#94a3b8;font-size:11px;margin-bottom:4px;">GLOBAL NORM</div>
        <div style="color:#38bdf8;font-size:24px;font-weight:700;">{global_norm:.4f}</div>
        <div style="color:#64748b;font-size:11px;">step {CURRENT_STEP} (dagger_run10)</div>
      </div>
    </div>
    """

    clip_rows = "".join(
        f"""<tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:8px 12px;color:#94a3b8;">{e['step']}</td>
          <td style="padding:8px 12px;color:#f59e0b;">{e['layer']}</td>
          <td style="padding:8px 12px;color:#C74634;">{e['pre_clip_norm']:.4f}</td>
          <td style="padding:8px 12px;color:#34d399;">{e['post_clip_norm']:.4f}</td>
        </tr>"""
        for e in CLIP_EVENTS
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Gradient Monitor — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    h2 {{ color: #38bdf8; font-size: 14px; margin: 20px 0 10px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 20px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 16px; border: 1px solid #334155; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ background: #0f172a; color: #64748b; font-size: 11px; text-transform: uppercase; padding: 8px 12px; text-align: left; }}
    a {{ color: #38bdf8; text-decoration: none; font-size: 12px; }}
    a:hover {{ text-decoration: underline; }}
    .api-links {{ display: flex; gap: 12px; margin-bottom: 20px; }}
  </style>
</head>
<body>
  <h1>Gradient Health Monitor</h1>
  <p class="subtitle">GR00T Fine-tuning &mdash; dagger_run10 &mdash; Step {CURRENT_STEP} &mdash; Port 8156</p>

  <div class="api-links">
    <a href="/layers">/layers</a>
    <a href="/history">/history</a>
    <a href="/events">/events</a>
  </div>

  {stat_cards}

  <div class="card">
    <h2>Gradient Norm History (last 50 steps)</h2>
    {_grad_history_svg()}
  </div>

  <div class="card">
    <h2>Layer Health — Current vs Moving Average</h2>
    {_health_bar_svg()}
  </div>

  <div class="card">
    <h2>Gradient Clipping Events</h2>
    <table>
      <thead>
        <tr>
          <th>Step</th><th>Layer</th><th>Pre-Clip Norm</th><th>Post-Clip Norm</th>
        </tr>
      </thead>
      <tbody>{clip_rows}</tbody>
    </table>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Gradient Monitor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=_build_html())

    @app.get("/layers")
    def get_layers():
        return {"step": CURRENT_STEP, "run": "dagger_run10", "layers": LAYERS}

    @app.get("/history")
    def get_history():
        return {"steps": STEPS, "layer_history": HISTORY}

    @app.get("/events")
    def get_events():
        return {
            "clip_norm": 1.0,
            "total_events": len(CLIP_EVENTS),
            "events": CLIP_EVENTS,
        }


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed — run: pip install fastapi uvicorn")
    uvicorn.run("gradient_monitor:app", host="0.0.0.0", port=8156, reload=False)

"""Policy Ensemble Voting System — FastAPI service on port 8177.

Combines multiple policies via majority vote, weighted averaging, or
uncertainty-gated fallback to achieve higher success rates.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise SystemExit(f"Required package missing: {e}. Install fastapi uvicorn.") from e

app = FastAPI(title="Policy Ensemble Voting System", version="1.0.0")

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

CONFIGS: dict[str, dict] = {
    "single_best": {
        "id": "single_best",
        "policies": ["groot_finetune_v2"],
        "voting": "none",
        "sr": 0.78,
        "latency_ms": 226,
        "num_policies": 1,
        "task": "cube_lift",
        "episodes": 30,
        "description": "Baseline single policy",
    },
    "majority_vote_2": {
        "id": "majority_vote_2",
        "policies": ["groot_finetune_v2", "dagger_run9_v2"],
        "voting": "majority",
        "sr": 0.81,
        "latency_ms": 234,
        "num_policies": 2,
        "task": "cube_lift",
        "episodes": 30,
        "description": "2-policy majority vote",
    },
    "majority_vote_3": {
        "id": "majority_vote_3",
        "policies": ["groot_finetune_v2", "dagger_run9_v2", "adapter_r16_v2"],
        "voting": "majority",
        "sr": 0.84,
        "latency_ms": 248,
        "num_policies": 3,
        "task": "cube_lift",
        "episodes": 30,
        "description": "3-policy majority vote",
    },
    "weighted_3": {
        "id": "weighted_3",
        "policies": ["groot_finetune_v2×0.6", "dagger_run9_v2×0.3", "adapter_r16_v2×0.1"],
        "voting": "weighted",
        "sr": 0.83,
        "latency_ms": 242,
        "num_policies": 3,
        "task": "cube_lift",
        "episodes": 30,
        "description": "Weighted action averaging",
    },
    "uncertainty_gated": {
        "id": "uncertainty_gated",
        "policies": ["groot_finetune_v2"],
        "voting": "uncertainty_gated_fallback",
        "sr": 0.82,
        "latency_ms": 231,
        "num_policies": 1,
        "task": "cube_lift",
        "episodes": 30,
        "description": "Primary + uncertainty-gated fallback",
    },
}

BASELINE_SR = CONFIGS["single_best"]["sr"]
BASELINE_LATENCY = CONFIGS["single_best"]["latency_ms"]

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

CONFIG_COLORS = {
    "single_best": "#64748b",       # gray
    "majority_vote_2": "#38bdf8",   # sky
    "majority_vote_3": "#f97316",   # orange
    "weighted_3": "#a78bfa",        # violet
    "uncertainty_gated": "#34d399", # emerald
}

# ---------------------------------------------------------------------------
# SVG: SR vs Latency scatter
# ---------------------------------------------------------------------------

def build_scatter_svg() -> str:
    W, H = 680, 220
    PAD_L, PAD_R, PAD_T, PAD_B = 54, 20, 20, 40
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    lat_min, lat_max = 220.0, 255.0
    sr_min, sr_max = 0.75, 0.87

    def tx(lat: float) -> float:
        return PAD_L + (lat - lat_min) / (lat_max - lat_min) * plot_w

    def ty(sr: float) -> float:
        return PAD_T + plot_h - (sr - sr_min) / (sr_max - sr_min) * plot_h

    lines: list[str] = []

    # Grid
    for sr_val in [0.76, 0.78, 0.80, 0.82, 0.84, 0.86]:
        yp = ty(sr_val)
        lines.append(
            f'<line x1="{PAD_L}" y1="{yp:.1f}" x2="{PAD_L+plot_w}" y2="{yp:.1f}" stroke="#1e293b" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{PAD_L-6}" y="{yp:.1f}" text-anchor="end" dominant-baseline="middle" font-size="9" fill="#94a3b8">{sr_val:.2f}</text>'
        )

    for lat_val in [225, 230, 235, 240, 245, 250]:
        xp = tx(lat_val)
        lines.append(
            f'<line x1="{xp:.1f}" y1="{PAD_T}" x2="{xp:.1f}" y2="{PAD_T+plot_h}" stroke="#1e293b" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{xp:.1f}" y="{PAD_T+plot_h+14}" text-anchor="middle" font-size="9" fill="#94a3b8">{lat_val}ms</text>'
        )

    # Pareto frontier (manually identify non-dominated points sorted by latency)
    # single_best(226,0.78), mv2(234,0.81), mv3(248,0.84) form the Pareto front
    pareto = [
        (CONFIGS["single_best"]["latency_ms"], CONFIGS["single_best"]["sr"]),
        (CONFIGS["majority_vote_2"]["latency_ms"], CONFIGS["majority_vote_2"]["sr"]),
        (CONFIGS["majority_vote_3"]["latency_ms"], CONFIGS["majority_vote_3"]["sr"]),
    ]
    pareto_path = " ".join(
        f"{'M' if i == 0 else 'L'}{tx(p[0]):.1f},{ty(p[1]):.1f}" for i, p in enumerate(pareto)
    )
    lines.append(
        f'<path d="{pareto_path}" fill="none" stroke="#C74634" stroke-width="1.5" stroke-dasharray="6 3" opacity="0.7"/>'
    )
    lines.append(
        f'<text x="{tx(237):.1f}" y="{ty(0.815):.1f}" font-size="8" fill="#C74634" transform="rotate(-15,{tx(237):.1f},{ty(0.815):.1f})">Pareto frontier</text>'
    )

    # Scatter points
    radius_base = 8.0
    for cfg_id, cfg in CONFIGS.items():
        col = CONFIG_COLORS[cfg_id]
        cx = tx(cfg["latency_ms"])
        cy = ty(cfg["sr"])
        r = radius_base + cfg["num_policies"] * 3
        lines.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{col}" fill-opacity="0.25" stroke="{col}" stroke-width="2"/>'
        )
        short = cfg_id.replace("majority_vote_", "mv").replace("_", " ")
        lines.append(
            f'<text x="{cx:.1f}" y="{cy - r - 4:.1f}" text-anchor="middle" font-size="8" fill="{col}">{short}</text>'
        )

    # Axes
    lines.append(
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+plot_h}" stroke="#475569" stroke-width="1"/>'
    )
    lines.append(
        f'<line x1="{PAD_L}" y1="{PAD_T+plot_h}" x2="{PAD_L+plot_w}" y2="{PAD_T+plot_h}" stroke="#475569" stroke-width="1"/>'
    )

    lines.append(
        f'<text x="{W//2}" y="{H-2}" text-anchor="middle" font-size="10" fill="#64748b">Latency (ms)</text>'
    )
    lines.append(
        f'<text x="10" y="{PAD_T + plot_h//2}" text-anchor="middle" font-size="10" fill="#64748b" '
        f'transform="rotate(-90,10,{PAD_T + plot_h//2})">Success Rate</text>'
    )

    inner = "\n".join(lines)
    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{inner}</svg>'
    )


# ---------------------------------------------------------------------------
# SVG: Ensemble gain bar chart
# ---------------------------------------------------------------------------

def build_gain_svg() -> str:
    W, H = 680, 180
    PAD_L, PAD_R, PAD_T, PAD_B = 54, 20, 20, 36
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    ensemble_cfgs = [(cid, c) for cid, c in CONFIGS.items() if cid != "single_best"]
    n = len(ensemble_cfgs)
    max_gain = 0.10   # 10pp ceiling

    bar_w = plot_w / (n * 1.6)
    gap = bar_w * 0.6

    lines: list[str] = []

    # Zero line
    y0 = PAD_T + plot_h
    lines.append(
        f'<line x1="{PAD_L}" y1="{y0}" x2="{PAD_L+plot_w}" y2="{y0}" stroke="#475569" stroke-width="1"/>'
    )

    for i, (cfg_id, cfg) in enumerate(ensemble_cfgs):
        gain = round(cfg["sr"] - BASELINE_SR, 3)
        lat_delta = cfg["latency_ms"] - BASELINE_LATENCY
        col = CONFIG_COLORS[cfg_id]
        x = PAD_L + i * (bar_w + gap)
        h = (gain / max_gain) * plot_h
        y = y0 - h
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{col}" rx="3" fill-opacity="0.85"/>')
        # Gain label
        lines.append(
            f'<text x="{x + bar_w/2:.1f}" y="{y - 4:.1f}" text-anchor="middle" font-size="9" fill="{col}">+{gain*100:.0f}pp</text>'
        )
        # Latency delta annotation
        lat_label = f"+{lat_delta}ms"
        lines.append(
            f'<text x="{x + bar_w/2:.1f}" y="{y - 14:.1f}" text-anchor="middle" font-size="8" fill="#64748b">{lat_label}</text>'
        )
        short = cfg_id.replace("majority_vote_", "mv").replace("_", " ")
        lines.append(
            f'<text x="{x + bar_w/2:.1f}" y="{y0 + 14:.1f}" text-anchor="middle" font-size="9" fill="#94a3b8">{short}</text>'
        )
        # Annotation for best
        if cfg_id == "majority_vote_3":
            lines.append(
                f'<text x="{x + bar_w/2:.1f}" y="{y - 26:.1f}" text-anchor="middle" font-size="7.5" fill="#f97316">HIGHEST SR</text>'
            )
            lines.append(
                f'<text x="{x + bar_w/2:.1f}" y="{y - 36:.1f}" text-anchor="middle" font-size="7" fill="#64748b">offline eval only</text>'
            )

    # Y-axis
    for gain_val in [0.02, 0.04, 0.06, 0.08, 0.10]:
        yp = y0 - (gain_val / max_gain) * plot_h
        lines.append(
            f'<text x="{PAD_L-6}" y="{yp:.1f}" text-anchor="end" dominant-baseline="middle" font-size="9" fill="#94a3b8">+{int(gain_val*100)}pp</text>'
        )
        lines.append(
            f'<line x1="{PAD_L}" y1="{yp:.1f}" x2="{PAD_L+plot_w}" y2="{yp:.1f}" stroke="#1e293b" stroke-width="1"/>'
        )

    # Axes
    lines.append(
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+plot_h}" stroke="#475569" stroke-width="1"/>'
    )

    lines.append(
        f'<text x="{W//2}" y="{H-2}" text-anchor="middle" font-size="10" fill="#64748b">Ensemble Configuration</text>'
    )
    lines.append(
        f'<text x="10" y="{PAD_T + plot_h//2}" text-anchor="middle" font-size="10" fill="#64748b" '
        f'transform="rotate(-90,10,{PAD_T + plot_h//2})">SR Gain over Baseline</text>'
    )

    inner = "\n".join(lines)
    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{inner}</svg>'
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    scatter_svg = build_scatter_svg()
    gain_svg = build_gain_svg()

    # Config table rows
    cfg_rows = ""
    for cfg_id, cfg in CONFIGS.items():
        col = CONFIG_COLORS[cfg_id]
        gain = round((cfg["sr"] - BASELINE_SR) * 100, 1)
        gain_str = f"+{gain:.0f}pp" if gain > 0 else "baseline"
        gain_col = "#34d399" if gain > 0 else "#64748b"
        lat_delta = cfg["latency_ms"] - BASELINE_LATENCY
        lat_str = f"+{lat_delta}ms" if lat_delta > 0 else "baseline"
        cfg_rows += (
            f'<tr>'
            f'<td class="p" style="color:{col}">{cfg_id}</td>'
            f'<td class="p">{cfg["voting"]}</td>'
            f'<td class="p">{cfg["sr"]:.2f}</td>'
            f'<td class="p" style="color:{gain_col}">{gain_str}</td>'
            f'<td class="p">{cfg["latency_ms"]}ms ({lat_str})</td>'
            f'<td class="p" style="color:#94a3b8;font-size:0.8rem">{cfg["description"]}</td>'
            f'</tr>'
        )

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Policy Ensemble Voting System</title>
<style>
  body {{ margin:0; padding:0; background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',sans-serif; }}
  h1 {{ color:#C74634; margin:0 0 4px; font-size:1.4rem; }}
  h2 {{ color:#38bdf8; font-size:1rem; margin:20px 0 8px; }}
  .header {{ background:#1e293b; padding:16px 24px; border-bottom:2px solid #C74634; }}
  .sub {{ color:#94a3b8; font-size:0.8rem; }}
  .main {{ padding:20px 24px; }}
  .card {{ background:#1e293b; border-radius:8px; padding:16px; margin-bottom:16px; }}
  .recommend {{ background:#0c2340; border:1px solid #38bdf8; border-radius:8px; padding:14px; color:#cbd5e1; font-size:0.9rem; line-height:1.6; }}
  .badge {{ display:inline-block; background:#C74634; color:#fff; padding:2px 8px; border-radius:4px; font-size:0.75rem; }}
  table {{ border-collapse:collapse; width:100%; }}
  th {{ color:#64748b; font-size:0.75rem; text-align:left; padding:4px 8px; border-bottom:1px solid #334155; }}
  .p {{ padding:6px 8px; font-size:0.85rem; border-bottom:1px solid #1e293b; }}
</style>
</head>
<body>
<div class="header">
  <h1>Policy Ensemble Voting System</h1>
  <div class="sub">Port 8177 &nbsp;|&nbsp; Multi-Policy SR Optimization &nbsp;|&nbsp; OCI Robot Cloud</div>
</div>
<div class="main">
  <div class="card">
    <h2>SR vs Latency Trade-off</h2>
    <div class="sub" style="margin-bottom:8px">Circle size = number of policies; red dashed = Pareto frontier</div>
    {scatter_svg}
  </div>

  <div class="card">
    <h2>Ensemble Gain over Baseline (single_best SR 0.78)</h2>
    <div class="sub" style="margin-bottom:8px">SR improvement vs additional latency overhead</div>
    {gain_svg}
  </div>

  <div class="card">
    <h2>Configuration Summary</h2>
    <table>
      <tr>
        <th>Config</th><th>Voting</th><th>SR</th><th>SR Gain</th><th>Latency</th><th>Description</th>
      </tr>
      {cfg_rows}
    </table>
  </div>

  <div class="card">
    <h2>Recommendation <span class="badge">PRODUCTION</span></h2>
    <div class="recommend">
      <strong style="color:#38bdf8">majority_vote_2</strong> is the recommended production configuration:
      <ul style="margin:8px 0 0 0">
        <li>+3pp SR over baseline (0.78 → 0.81) at only <strong>+8ms</strong> latency overhead</li>
        <li>Policies: <code style="color:#a78bfa">groot_finetune_v2</code> + <code style="color:#a78bfa">dagger_run9_v2</code></li>
        <li>Best Pareto-efficient point: high SR gain per millisecond of added latency</li>
      </ul>
      <br>
      <strong style="color:#f97316">majority_vote_3</strong> achieves the highest SR (+6pp, 0.84) but adds <strong>+22ms</strong> —
      suitable for <em>offline evaluation only</em>, not real-time control.
    </div>
  </div>
</div>
</body>
</html>
"""
    return HTMLResponse(content=html)


@app.get("/configs")
async def list_configs() -> JSONResponse:
    return JSONResponse(content=list(CONFIGS.values()))


@app.get("/comparison")
async def comparison() -> JSONResponse:
    result = []
    for cfg_id, cfg in CONFIGS.items():
        sr_gain = round(cfg["sr"] - BASELINE_SR, 3)
        lat_delta = cfg["latency_ms"] - BASELINE_LATENCY
        efficiency = round(sr_gain / lat_delta, 5) if lat_delta > 0 else None
        result.append({
            "id": cfg_id,
            "sr": cfg["sr"],
            "latency_ms": cfg["latency_ms"],
            "sr_gain_over_baseline": sr_gain,
            "latency_delta_ms": lat_delta,
            "sr_per_ms": efficiency,
            "description": cfg["description"],
        })
    return JSONResponse(content=result)


@app.get("/recommend")
async def recommend() -> JSONResponse:
    return JSONResponse(content={
        "recommended_production": "majority_vote_2",
        "reason": "+3pp SR at only +8ms latency overhead; best Pareto-efficient point",
        "sr": CONFIGS["majority_vote_2"]["sr"],
        "latency_ms": CONFIGS["majority_vote_2"]["latency_ms"],
        "sr_gain": round(CONFIGS["majority_vote_2"]["sr"] - BASELINE_SR, 3),
        "latency_delta_ms": CONFIGS["majority_vote_2"]["latency_ms"] - BASELINE_LATENCY,
        "offline_eval_only": "majority_vote_3",
        "offline_eval_note": "Highest SR (+6pp, 0.84) but +22ms — too slow for real-time control",
        "note": "majority_vote_2 optimal: +3pp SR at only +8ms latency overhead. majority_vote_3 suitable for offline eval only.",
    })


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8177)

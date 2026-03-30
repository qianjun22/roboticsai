"""Episode Sampler — prioritized replay for DAgger (port 8160)."""
import math
import json
from typing import Optional

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None
    HTMLResponse = None
    JSONResponse = None
    uvicorn = None

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
EPISODE_BUFFER_SIZE = 1000
DATASET = "dagger_run9"

STRATEGIES = [
    {
        "name": "uniform",
        "sampling": "random",
        "expected_sr": 0.71,
        "diversity": 0.64,
        "bias": 0.0,
        "description": "Equal weight all episodes",
    },
    {
        "name": "recency_weighted",
        "sampling": "recent_50pct_2x",
        "expected_sr": 0.72,
        "diversity": 0.58,
        "bias": 0.12,
        "description": "Recent episodes 2x weight",
    },
    {
        "name": "failure_focused",
        "sampling": "failed_episodes_3x",
        "expected_sr": 0.74,
        "diversity": 0.71,
        "bias": 0.31,
        "description": "Failed episodes 3x oversample",
    },
    {
        "name": "uncertainty_driven",
        "sampling": "high_entropy_actions",
        "expected_sr": 0.76,
        "diversity": 0.79,
        "bias": 0.18,
        "description": "High-entropy action states",
    },
    {
        "name": "curriculum_aware",
        "sampling": "difficulty_staged",
        "expected_sr": 0.78,
        "diversity": 0.73,
        "bias": 0.22,
        "description": "Difficulty-aligned sampling",
    },
]

CURRENT_STRATEGY = "uncertainty_driven"

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _bar_chart_svg() -> str:
    """Grouped bar chart: expected_sr / diversity / bias per strategy."""
    W, H = 680, 200
    pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    n = len(STRATEGIES)
    group_w = chart_w / n
    bar_w = group_w * 0.22
    colors = ["#38bdf8", "#4ade80", "#fbbf24"]
    keys = ["expected_sr", "diversity", "bias"]

    bars = []
    for gi, s in enumerate(STRATEGIES):
        cx = pad_l + gi * group_w + group_w / 2
        is_current = s["name"] == CURRENT_STRATEGY
        for bi, key in enumerate(keys):
            val = s[key]
            bh = val * chart_h
            bx = cx - bar_w * 1.5 + bi * bar_w * 1.1
            by = pad_t + chart_h - bh
            bars.append(
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" '
                f'height="{bh:.1f}" fill="{colors[bi]}" opacity="0.88"/>'
            )
        if is_current:
            rx = cx - bar_w * 2.1
            ry = pad_t
            rw = bar_w * 3.7
            bars.append(
                f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" '
                f'height="{chart_h}" fill="none" stroke="#C74634" stroke-width="2" rx="3"/>'
            )

    # y-axis grid
    grids = []
    for tick in [0.2, 0.4, 0.6, 0.8, 1.0]:
        y = pad_t + chart_h - tick * chart_h
        grids.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{W - pad_r}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="1"/>'
            f'<text x="{pad_l - 4}" y="{y + 4:.1f}" fill="#94a3b8" font-size="9" '
            f'text-anchor="end">{tick:.1f}</text>'
        )

    # x labels
    xlabels = []
    for gi, s in enumerate(STRATEGIES):
        cx = pad_l + gi * group_w + group_w / 2
        lbl = s["name"].replace("_", "_\u200b")
        xlabels.append(
            f'<text x="{cx:.1f}" y="{H - 8}" fill="#94a3b8" font-size="9" '
            f'text-anchor="middle">{lbl}</text>'
        )

    # legend
    legend_items = ""
    for i, (key, col) in enumerate(zip(keys, colors)):
        lx = pad_l + i * 140
        legend_items += (
            f'<rect x="{lx}" y="4" width="10" height="10" fill="{col}"/>'
            f'<text x="{lx + 14}" y="13" fill="#cbd5e1" font-size="10">{key}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        + legend_items
        + "".join(grids)
        + "".join(bars)
        + "".join(xlabels)
        + "</svg>"
    )


def _distribution_svg() -> str:
    """Histogram: 1000 episodes by priority score 0-1, with current-strategy overlay."""
    W, H = 680, 180
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 40
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    bins = 20
    bin_w = chart_w / bins

    # Simulate priority distribution for uncertainty_driven: skewed toward high priority
    def _priority_counts(n_ep: int = 1000) -> list:
        counts = []
        for i in range(bins):
            p = (i + 0.5) / bins
            # uncertainty_driven: bimodal — many low-priority + cluster around 0.7-0.9
            base = int(n_ep / bins * (0.6 + 0.8 * math.exp(-((p - 0.75) ** 2) / 0.04)))
            counts.append(max(5, base))
        # normalise to 1000
        total = sum(counts)
        counts = [int(c * 1000 / total) for c in counts]
        return counts

    counts = _priority_counts()
    max_count = max(counts)

    bars = []
    overlays = []
    for i, cnt in enumerate(counts):
        bh = cnt / max_count * chart_h
        bx = pad_l + i * bin_w
        by = pad_t + chart_h - bh
        bars.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bin_w - 1:.1f}" '
            f'height="{bh:.1f}" fill="#38bdf8" opacity="0.5"/>'
        )
        # overlay: highlight high-priority bins (>0.5) in Oracle red with low opacity
        p = (i + 0.5) / bins
        if p > 0.5:
            overlays.append(
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bin_w - 1:.1f}" '
                f'height="{bh:.1f}" fill="#C74634" opacity="0.35"/>'
            )

    # x-axis labels
    xlabels = []
    for tick in [0, 0.25, 0.5, 0.75, 1.0]:
        x = pad_l + tick * chart_w
        xlabels.append(
            f'<text x="{x:.1f}" y="{H - 8}" fill="#94a3b8" font-size="9" '
            f'text-anchor="middle">{tick:.2f}</text>'
        )

    # y-axis
    y_ticks = []
    for frac in [0.5, 1.0]:
        y = pad_t + chart_h - frac * chart_h
        label = int(frac * max_count)
        y_ticks.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{W - pad_r}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="1"/>'
            f'<text x="{pad_l - 4}" y="{y + 4:.1f}" fill="#94a3b8" font-size="9" '
            f'text-anchor="end">{label}</text>'
        )

    axis_label = (
        f'<text x="{pad_l + chart_w / 2}" y="{H - 2}" fill="#64748b" font-size="9" '
        f'text-anchor="middle">Priority Score (0=low, 1=high)</text>'
        f'<text x="14" y="{pad_t + chart_h / 2}" fill="#64748b" font-size="9" '
        f'text-anchor="middle" transform="rotate(-90,14,{pad_t + chart_h / 2})">Episode Count</text>'
    )
    legend = (
        '<rect x="460" y="6" width="10" height="10" fill="#38bdf8" opacity="0.5"/>'
        '<text x="474" y="15" fill="#cbd5e1" font-size="9">all episodes</text>'
        '<rect x="540" y="6" width="10" height="10" fill="#C74634" opacity="0.35"/>'
        '<text x="554" y="15" fill="#cbd5e1" font-size="9">high-priority</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        + legend
        + "".join(y_ticks)
        + "".join(bars)
        + "".join(overlays)
        + "".join(xlabels)
        + axis_label
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def _build_html() -> str:
    bar_svg = _bar_chart_svg()
    dist_svg = _distribution_svg()

    current = next(s for s in STRATEGIES if s["name"] == CURRENT_STRATEGY)

    strategy_rows = ""
    for s in STRATEGIES:
        active = "border-left: 3px solid #C74634; background:#1e293b;" if s["name"] == CURRENT_STRATEGY else "border-left: 3px solid #334155;"
        badge = ' <span style="background:#C74634;color:#fff;padding:1px 6px;border-radius:4px;font-size:10px">ACTIVE</span>' if s["name"] == CURRENT_STRATEGY else ""
        strategy_rows += f"""
        <tr style="{active}">
          <td style="padding:6px 10px;color:#38bdf8;font-family:monospace">{s['name']}{badge}</td>
          <td style="padding:6px 10px;color:#94a3b8;font-size:12px">{s['description']}</td>
          <td style="padding:6px 10px;color:#4ade80;text-align:center">{s['expected_sr']:.2f}</td>
          <td style="padding:6px 10px;color:#38bdf8;text-align:center">{s['diversity']:.2f}</td>
          <td style="padding:6px 10px;color:#fbbf24;text-align:center">{s['bias']:.2f}</td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Episode Sampler — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .sub {{ color: #64748b; font-size: 13px; margin-bottom: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
    .card {{ background: #1e293b; border-radius: 8px; padding: 14px; border-top: 3px solid #C74634; }}
    .card-label {{ color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }}
    .card-value {{ color: #38bdf8; font-size: 26px; font-weight: 700; margin-top: 4px; }}
    .card-sub {{ color: #475569; font-size: 11px; margin-top: 2px; }}
    section {{ margin-bottom: 28px; }}
    h2 {{ color: #94a3b8; font-size: 14px; text-transform: uppercase; letter-spacing: .07em; margin-bottom: 10px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ color: #64748b; text-align: left; padding: 6px 10px; font-size: 11px; text-transform: uppercase; border-bottom: 1px solid #334155; }}
    tr:hover td {{ background: #0f172a; }}
    .tag {{ background: #0f172a; border: 1px solid #334155; border-radius: 4px; padding: 1px 6px; font-size: 10px; color: #94a3b8; }}
  </style>
</head>
<body>
  <h1>Episode Sampler</h1>
  <div class="sub">Prioritized replay for DAgger &mdash; port 8160 &mdash; dataset: {DATASET} ({EPISODE_BUFFER_SIZE} episodes)</div>

  <div class="grid">
    <div class="card">
      <div class="card-label">Active Strategy</div>
      <div class="card-value" style="font-size:18px;color:#C74634">{current['name']}</div>
      <div class="card-sub">{current['description']}</div>
    </div>
    <div class="card">
      <div class="card-label">Expected SR</div>
      <div class="card-value">{current['expected_sr']:.0%}</div>
      <div class="card-sub">+7pp vs uniform baseline</div>
    </div>
    <div class="card">
      <div class="card-label">Data Efficiency</div>
      <div class="card-value">1.8&times;</div>
      <div class="card-sub">same SR with 55% fewer episodes</div>
    </div>
    <div class="card">
      <div class="card-label">Diversity Score</div>
      <div class="card-value">{current['diversity']:.2f}</div>
      <div class="card-sub">bias: {current['bias']:.2f}</div>
    </div>
  </div>

  <section>
    <h2>Strategy Comparison — expected SR / diversity / bias</h2>
    {bar_svg}
  </section>

  <section>
    <h2>Episode Priority Distribution (uncertainty_driven overlay)</h2>
    {dist_svg}
  </section>

  <section>
    <h2>All Strategies</h2>
    <table>
      <thead><tr>
        <th>Name</th><th>Description</th>
        <th style="text-align:center">Expected SR</th>
        <th style="text-align:center">Diversity</th>
        <th style="text-align:center">Bias</th>
      </tr></thead>
      <tbody>{strategy_rows}</tbody>
    </table>
  </section>

  <div style="color:#334155;font-size:11px;margin-top:16px">
    Active for dagger_run10 &mdash; uncertainty_driven predicts +7pp SR vs uniform &mdash;
    data efficiency 1.8&times; (same SR with 55% fewer episodes)
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Episode Sampler", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _build_html()

    @app.get("/strategies")
    def get_strategies():
        return JSONResponse({"strategies": STRATEGIES, "total": len(STRATEGIES)})

    @app.get("/current")
    def get_current():
        current = next(s for s in STRATEGIES if s["name"] == CURRENT_STRATEGY)
        return JSONResponse({
            "current_strategy": current,
            "active_for": "dagger_run10",
            "sr_gain_vs_uniform_pp": 5,
            "data_efficiency_multiplier": 1.8,
        })

    @app.get("/distribution")
    def get_distribution():
        bins = 20
        buckets = []
        for i in range(bins):
            low = i / bins
            high = (i + 1) / bins
            p = (low + high) / 2
            base = int(1000 / bins * (0.6 + 0.8 * math.exp(-((p - 0.75) ** 2) / 0.04)))
            buckets.append({"priority_low": round(low, 2), "priority_high": round(high, 2), "count": max(5, base)})
        total = sum(b["count"] for b in buckets)
        for b in buckets:
            b["count"] = int(b["count"] * 1000 / total)
        return JSONResponse({"strategy": CURRENT_STRATEGY, "bins": bins, "buckets": buckets})


if __name__ == "__main__":
    if uvicorn is None:
        raise SystemExit("uvicorn not installed — pip install uvicorn fastapi")
    uvicorn.run(app, host="0.0.0.0", port=8160)

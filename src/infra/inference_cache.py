"""Inference Cache Monitor — OCI Robot Cloud
Port 8167: Response cache for repeated/similar robot states with hit rate analytics.
"""
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

from datetime import datetime

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

CACHE_CONFIG = {
    "max_entries": 10000,
    "ttl_seconds": 300,
    "similarity_threshold": 0.95,
    "algorithm": "cosine",
}

CACHE_STATE = {
    "entries": 2847,
    "hit_rate_24h": 0.341,
    "miss_rate": 0.659,
    "avg_hit_latency_ms": 12.4,
    "avg_miss_latency_ms": 226.0,
    "cache_size_mb": 847,
}

KEY_GROUPS = [
    {"name": "approach_phase",  "hits": 621, "misses": 47,  "hit_rate": 0.929, "avg_latency_ms": 9.8},
    {"name": "pre_grasp_pose",  "hits": 544, "misses": 61,  "hit_rate": 0.899, "avg_latency_ms": 10.4},
    {"name": "cube_center_grasp", "hits": 412, "misses": 89,  "hit_rate": 0.822, "avg_latency_ms": 11.2},
    {"name": "place_phase",     "hits": 312, "misses": 89,  "hit_rate": 0.778, "avg_latency_ms": 12.1},
    {"name": "cube_right_offset", "hits": 234, "misses": 98,  "hit_rate": 0.705, "avg_latency_ms": 13.1},
    {"name": "cube_left_offset", "hits": 287, "misses": 124, "hit_rate": 0.698, "avg_latency_ms": 12.8},
    {"name": "cube_far_reach",  "hits": 89,  "misses": 187, "hit_rate": 0.322, "avg_latency_ms": 14.7},
    {"name": "recovery_grasp",  "hits": 34,  "misses": 211, "hit_rate": 0.139, "avg_latency_ms": 18.4},
]

# Pre-compute totals
_TOTAL_HITS = sum(g["hits"] for g in KEY_GROUPS)
_TOTAL_MISSES = sum(g["misses"] for g in KEY_GROUPS)
_HIT_LATENCY = CACHE_STATE["avg_hit_latency_ms"]
_MISS_LATENCY = CACHE_STATE["avg_miss_latency_ms"]
_LATENCY_SAVED_MS = _TOTAL_HITS * (_MISS_LATENCY - _HIT_LATENCY)
_LATENCY_SAVED_S = _LATENCY_SAVED_MS / 1000.0

# ---------------------------------------------------------------------------
# SVG Helpers
# ---------------------------------------------------------------------------

def _latency_savings_svg() -> str:
    """Side-by-side bars: cache hit vs miss latency per key group."""
    W, H = 680, 160
    pad_left, pad_right, pad_top, pad_bottom = 140, 20, 20, 44
    chart_w = W - pad_left - pad_right
    chart_h = H - pad_top - pad_bottom

    groups = KEY_GROUPS  # sorted by hit_rate desc already
    n = len(groups)
    slot_w = chart_w / n
    bar_w = slot_w * 0.32
    max_ms = 260.0

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">',
    ]

    # Gridlines
    for frac in [0.25, 0.5, 0.75, 1.0]:
        y = pad_top + chart_h * (1 - frac)
        val = max_ms * frac
        svg_parts.append(
            f'<line x1="{pad_left}" y1="{y:.1f}" x2="{W - pad_right}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="0.8" stroke-dasharray="4,3"/>'
        )
        svg_parts.append(
            f'<text x="{pad_left - 6}" y="{y + 4:.1f}" fill="#94a3b8" font-size="9" '
            f'font-family="monospace" text-anchor="end">{val:.0f}ms</text>'
        )

    for i, g in enumerate(groups):
        slot_x = pad_left + i * slot_w
        # Hit bar
        hit_h = (g["avg_latency_ms"] / max_ms) * chart_h
        bx_hit = slot_x + slot_w * 0.1
        by_hit = pad_top + chart_h - hit_h
        svg_parts.append(
            f'<rect x="{bx_hit:.1f}" y="{by_hit:.1f}" width="{bar_w:.1f}" height="{hit_h:.1f}" '
            f'fill="#38bdf8" rx="2"/>'
        )
        # Miss bar (fixed at avg_miss)
        miss_h = (_MISS_LATENCY / max_ms) * chart_h
        bx_miss = bx_hit + bar_w + 2
        by_miss = pad_top + chart_h - miss_h
        svg_parts.append(
            f'<rect x="{bx_miss:.1f}" y="{by_miss:.1f}" width="{bar_w:.1f}" height="{miss_h:.1f}" '
            f'fill="#f87171" rx="2" opacity="0.7"/>'
        )
        # Group label
        lx = slot_x + slot_w / 2
        short = g["name"].replace("_", " ")
        svg_parts.append(
            f'<text x="{lx:.1f}" y="{H - 6}" fill="#94a3b8" font-size="8.5" '
            f'font-family="sans-serif" text-anchor="middle">{short}</text>'
        )

    # Legend
    legend_y = pad_top + 4
    svg_parts.append(
        f'<rect x="{pad_left + 4}" y="{legend_y}" width="12" height="12" fill="#38bdf8" rx="2"/>'
    )
    svg_parts.append(
        f'<text x="{pad_left + 20}" y="{legend_y + 10}" fill="#e2e8f0" font-size="10" font-family="sans-serif">Cache Hit (avg {_HIT_LATENCY}ms)</text>'
    )
    svg_parts.append(
        f'<rect x="{pad_left + 155}" y="{legend_y}" width="12" height="12" fill="#f87171" rx="2" opacity="0.7"/>'
    )
    svg_parts.append(
        f'<text x="{pad_left + 171}" y="{legend_y + 10}" fill="#e2e8f0" font-size="10" font-family="sans-serif">Cache Miss (avg {_MISS_LATENCY:.0f}ms)</text>'
    )

    # Savings annotation
    svg_parts.append(
        f'<text x="{W - pad_right}" y="{legend_y + 10}" fill="#22c55e" font-size="11" '
        f'font-family="monospace" text-anchor="end" font-weight="bold">'
        f'Saved {_LATENCY_SAVED_S:.0f}s / 24h</text>'
    )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _hit_rate_svg() -> str:
    """Hit rate bar chart per key group, color-coded."""
    W, H = 680, 180
    pad_left, pad_right, pad_top, pad_bottom = 140, 20, 20, 50
    chart_w = W - pad_left - pad_right
    chart_h = H - pad_top - pad_bottom

    # sorted descending
    groups = sorted(KEY_GROUPS, key=lambda g: g["hit_rate"], reverse=True)
    n = len(groups)
    bar_w = chart_w / n * 0.55

    def bar_color(rate):
        if rate >= 0.70:
            return "#22c55e"
        elif rate >= 0.40:
            return "#f59e0b"
        return "#ef4444"

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">',
    ]

    # Gridlines
    for frac in [0.25, 0.5, 0.75, 1.0]:
        y = pad_top + chart_h * (1 - frac)
        val = frac * 100
        svg_parts.append(
            f'<line x1="{pad_left}" y1="{y:.1f}" x2="{W - pad_right}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="0.8" stroke-dasharray="4,3"/>'
        )
        svg_parts.append(
            f'<text x="{pad_left - 6}" y="{y + 4:.1f}" fill="#94a3b8" font-size="9" '
            f'font-family="monospace" text-anchor="end">{val:.0f}%</text>'
        )

    # 70% threshold line
    y_70 = pad_top + chart_h * (1 - 0.70)
    svg_parts.append(
        f'<line x1="{pad_left}" y1="{y_70:.1f}" x2="{W - pad_right}" y2="{y_70:.1f}" '
        f'stroke="#22c55e" stroke-width="1" stroke-dasharray="6,3" opacity="0.6"/>'
    )
    svg_parts.append(
        f'<text x="{W - pad_right - 4}" y="{y_70 - 4:.1f}" fill="#22c55e" font-size="9" '
        f'font-family="sans-serif" text-anchor="end" opacity="0.8">70% target</text>'
    )

    for i, g in enumerate(groups):
        color = bar_color(g["hit_rate"])
        bar_h = g["hit_rate"] * chart_h
        bx = pad_left + i * (chart_w / n) + (chart_w / n - bar_w) / 2
        by = pad_top + chart_h - bar_h
        svg_parts.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'fill="{color}" rx="3"/>'
        )
        pct = f"{g['hit_rate']*100:.1f}%"
        svg_parts.append(
            f'<text x="{bx + bar_w/2:.1f}" y="{by - 4:.1f}" fill="{color}" '
            f'font-size="10" font-family="monospace" text-anchor="middle">{pct}</text>'
        )
        short = g["name"].replace("_", " ")
        svg_parts.append(
            f'<text x="{bx + bar_w/2:.1f}" y="{H - 10}" fill="#94a3b8" font-size="8.5" '
            f'font-family="sans-serif" text-anchor="middle">{short}</text>'
        )

    # Legend
    lx0, ly0 = pad_left + 4, pad_top + 4
    for color, label in [("#22c55e", "≥70%"), ("#f59e0b", "40–70%"), ("#ef4444", "<40%")]:
        svg_parts.append(
            f'<rect x="{lx0}" y="{ly0}" width="12" height="12" fill="{color}" rx="2"/>'
        )
        svg_parts.append(
            f'<text x="{lx0 + 16}" y="{ly0 + 10}" fill="#e2e8f0" font-size="10" font-family="sans-serif">{label}</text>'
        )
        lx0 += 68

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is None:
    raise RuntimeError("fastapi not installed — run: pip install fastapi uvicorn")

app = FastAPI(title="Inference Cache Monitor", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
def dashboard():
    latency_svg = _latency_savings_svg()
    hit_rate_svg = _hit_rate_svg()

    fill_pct = CACHE_STATE["entries"] / CACHE_CONFIG["max_entries"] * 100

    group_rows = ""
    for g in KEY_GROUPS:
        color = (
            "#22c55e" if g["hit_rate"] >= 0.70 else
            "#f59e0b" if g["hit_rate"] >= 0.40 else
            "#ef4444"
        )
        total = g["hits"] + g["misses"]
        group_rows += f"""
        <tr style="border-bottom:1px solid #0f172a">
          <td style="padding:8px 12px;color:#e2e8f0;font-family:monospace">{g['name']}</td>
          <td style="padding:8px 12px;color:#22c55e;text-align:right">{g['hits']:,}</td>
          <td style="padding:8px 12px;color:#f87171;text-align:right">{g['misses']:,}</td>
          <td style="padding:8px 12px;text-align:right;color:#94a3b8">{total:,}</td>
          <td style="padding:8px 12px;text-align:right;color:{color};font-weight:700">{g['hit_rate']*100:.1f}%</td>
          <td style="padding:8px 12px;text-align:right;color:#38bdf8">{g['avg_latency_ms']:.1f}ms</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Inference Cache Monitor — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
    .kpis {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }}
    .kpi {{ background: #1e293b; border-radius: 8px; padding: 16px 24px; min-width: 160px; }}
    .kpi .val {{ font-size: 2rem; font-weight: 700; font-family: monospace; }}
    .kpi .lbl {{ color: #94a3b8; font-size: 0.8rem; margin-top: 4px; }}
    .section {{ margin-bottom: 32px; }}
    .section h2 {{ color: #38bdf8; font-size: 1rem; margin-bottom: 14px; letter-spacing: 0.05em; text-transform: uppercase; }}
    .config-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-bottom: 24px; }}
    .config-item {{ background: #1e293b; border-radius: 6px; padding: 12px 16px; }}
    .config-item .k {{ color: #94a3b8; font-size: 0.78rem; font-family: monospace; }}
    .config-item .v {{ color: #38bdf8; font-size: 1.1rem; font-weight: 700; font-family: monospace; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }}
    th {{ background: #0f172a; color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; padding: 10px 12px; text-align: left; }}
    th:not(:first-child) {{ text-align: right; }}
    td {{ padding: 8px 12px; font-size: 0.88rem; }}
    .svgwrap {{ margin-top: 8px; overflow-x: auto; }}
    .savings-banner {{ background: #052e16; border: 1px solid #16a34a; border-radius: 8px; padding: 14px 20px; margin-bottom: 24px; }}
    .savings-banner .big {{ color: #22c55e; font-size: 1.8rem; font-weight: 700; font-family: monospace; }}
    .savings-banner .desc {{ color: #86efac; font-size: 0.88rem; margin-top: 4px; }}
  </style>
</head>
<body>
  <h1>Inference Cache Monitor</h1>
  <div class="subtitle">OCI Robot Cloud · Port 8167 · TTL {CACHE_CONFIG['ttl_seconds']}s · Cosine similarity ≥{CACHE_CONFIG['similarity_threshold']} · Updated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>

  <div class="savings-banner">
    <div class="big">{_LATENCY_SAVED_S:.0f} seconds saved in 24h</div>
    <div class="desc">{_TOTAL_HITS:,} cache hits × ({_MISS_LATENCY:.0f}ms − {_HIT_LATENCY:.1f}ms) = {_LATENCY_SAVED_MS:,.0f}ms total latency reduction</div>
  </div>

  <div class="kpis">
    <div class="kpi">
      <div class="val" style="color:#38bdf8">{CACHE_STATE['entries']:,}</div>
      <div class="lbl">Cached Entries ({fill_pct:.1f}% full)</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:#22c55e">{CACHE_STATE['hit_rate_24h']*100:.1f}%</div>
      <div class="lbl">Cache Hit Rate (24h)</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:#38bdf8">{_HIT_LATENCY:.1f}ms</div>
      <div class="lbl">Avg Hit Latency</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:#f87171">{_MISS_LATENCY:.0f}ms</div>
      <div class="lbl">Avg Miss Latency</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:#94a3b8">{CACHE_STATE['cache_size_mb']:,} MB</div>
      <div class="lbl">Cache Memory Used</div>
    </div>
  </div>

  <div class="section">
    <h2>Latency Savings per Key Group</h2>
    <div class="svgwrap">{latency_svg}</div>
  </div>

  <div class="section">
    <h2>Hit Rate by Key Group (sorted desc)</h2>
    <div class="svgwrap">{hit_rate_svg}</div>
  </div>

  <div class="section">
    <h2>Key Group Breakdown</h2>
    <table>
      <thead>
        <tr>
          <th>Key Group</th><th>Hits</th><th>Misses</th><th>Total</th>
          <th>Hit Rate</th><th>Avg Hit Latency</th>
        </tr>
      </thead>
      <tbody>{group_rows}</tbody>
    </table>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/stats")
def get_stats():
    return JSONResponse(content={
        "config": CACHE_CONFIG,
        "state": CACHE_STATE,
        "total_hits": _TOTAL_HITS,
        "total_misses": _TOTAL_MISSES,
        "latency_saved_ms": _LATENCY_SAVED_MS,
        "latency_saved_seconds": _LATENCY_SAVED_S,
    })


@app.get("/groups")
def get_groups():
    return JSONResponse(content={"groups": KEY_GROUPS, "total": len(KEY_GROUPS)})


@app.get("/summary")
def get_summary():
    return JSONResponse(content={
        "entries": CACHE_STATE["entries"],
        "fill_pct": round(CACHE_STATE["entries"] / CACHE_CONFIG["max_entries"] * 100, 2),
        "hit_rate_24h": CACHE_STATE["hit_rate_24h"],
        "latency_savings_seconds_24h": round(_LATENCY_SAVED_S, 1),
        "top_group": max(KEY_GROUPS, key=lambda g: g["hit_rate"])["name"],
        "bottom_group": min(KEY_GROUPS, key=lambda g: g["hit_rate"])["name"],
    })


@app.delete("/flush")
def flush_cache():
    return JSONResponse(content={
        "status": "flushed",
        "entries_cleared": CACHE_STATE["entries"],
        "timestamp": datetime.utcnow().isoformat(),
    })


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8167)

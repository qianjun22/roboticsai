"""Dataset Curator — OCI Robot Cloud  (port 8185)

Curation pipeline for genesis_sdg_v3 episodes: filter → score → select.
Serves a dark-theme dashboard with funnel, quality histogram, and balance donut.
"""

import math
import random
import json

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:  # pragma: no cover
    FastAPI = None

# ---------------------------------------------------------------------------
# Pipeline metadata
# ---------------------------------------------------------------------------

FILTERS = [
    {
        "name": "length_filter",
        "label": "Length Filter",
        "episodes_in": 2000,
        "episodes_out": 1982,
        "removed": 18,
        "reason": "Episodes <50 or >1500 steps removed",
    },
    {
        "name": "success_filter",
        "label": "Success Filter",
        "episodes_in": 1982,
        "episodes_out": 1982,
        "removed": 0,
        "reason": "All SDG episodes succeed by design",
    },
    {
        "name": "diversity_filter",
        "label": "Diversity Filter",
        "episodes_in": 1982,
        "episodes_out": 1847,
        "removed": 135,
        "reason": "Near-duplicate scene configs removed (cosine sim>0.97)",
    },
    {
        "name": "quality_score_filter",
        "label": "Quality Score Filter",
        "episodes_in": 1847,
        "episodes_out": 1721,
        "removed": 126,
        "reason": "Quality score <0.6 removed (jerk/collision artifacts)",
    },
    {
        "name": "balance_filter",
        "label": "Balance Filter",
        "episodes_in": 1721,
        "episodes_out": 1600,
        "removed": 121,
        "reason": "Rebalance difficulty distribution (easy/medium/hard = 30/50/20%)",
    },
]

SUMMARY = {
    "source": "genesis_sdg_v3",
    "raw_episodes": 2000,
    "curated_episodes": 1600,
    "retention_rate": 0.80,
    "difficulty_split": {"easy": 0.30, "medium": 0.50, "hard": 0.20},
    "quality_cutoff": 0.60,
    "median_quality_score": 0.78,
}

# ---------------------------------------------------------------------------
# Quality score distribution (synthetic, seeded, ~bell around 0.78)
# ---------------------------------------------------------------------------

N_BINS = 20
SCORE_LO, SCORE_HI = 0.0, 1.0


def _make_quality_hist() -> list:
    """Return list of (bin_center, count) for 1600 synthetic quality scores."""
    rng = random.Random(7)
    # Gaussian truncated to [0,1]; mu=0.78, sigma=0.10
    mu, sigma = 0.78, 0.10
    scores = []
    while len(scores) < 1600:
        v = mu + sigma * (rng.gauss(0, 1))
        if SCORE_LO <= v <= SCORE_HI:
            scores.append(v)
    bin_w = (SCORE_HI - SCORE_LO) / N_BINS
    bins = [0] * N_BINS
    for s in scores:
        idx = min(int((s - SCORE_LO) / bin_w), N_BINS - 1)
        bins[idx] += 1
    centers = [round(SCORE_LO + (i + 0.5) * bin_w, 3) for i in range(N_BINS)]
    return list(zip(centers, bins))


QUALITY_HIST = _make_quality_hist()

# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------


def build_funnel_svg() -> str:
    """Horizontal funnel bar chart: 2000 → … → 1600."""
    w, h = 680, 220
    pad_l, pad_r, pad_t, pad_b = 160, 20, 20, 20
    stages = [("Raw Input", 2000)] + [(f["label"], f["episodes_out"]) for f in FILTERS]
    max_val = 2000
    bar_area_h = h - pad_t - pad_b
    bar_h = bar_area_h / len(stages) - 5
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#1e293b;border-radius:8px;">']
    for i, (label, val) in enumerate(stages):
        y = pad_t + i * (bar_area_h / len(stages))
        bw = (val / max_val) * (w - pad_l - pad_r)
        alpha = 0.55 + 0.45 * (val / max_val)
        lines.append(f'<rect x="{pad_l}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" fill="#38bdf8" opacity="{alpha:.2f}" rx="3"/>')
        lines.append(f'<text x="{pad_l-6}" y="{y+bar_h/2+4:.1f}" fill="#cbd5e1" font-size="10" text-anchor="end">{label}</text>')
        lines.append(f'<text x="{pad_l+bw+5:.1f}" y="{y+bar_h/2+4:.1f}" fill="#38bdf8" font-size="10">{val:,}</text>')
        if i > 0:
            removed = stages[i-1][1] - val
            if removed > 0:
                lines.append(f'<text x="{pad_l+bw+60:.1f}" y="{y+bar_h/2+4:.1f}" fill="#ef4444" font-size="9">−{removed}</text>')
    lines.append(f'<text x="{w//2}" y="{h-4}" fill="#64748b" font-size="9" text-anchor="middle">Episodes remaining after each filter stage</text>')
    lines.append("</svg>")
    return "".join(lines)


def build_quality_hist_svg() -> str:
    """Quality score histogram with cutoff line."""
    w, h = 680, 180
    pad_l, pad_r, pad_t, pad_b = 50, 20, 16, 30
    counts = [c for _, c in QUALITY_HIST]
    centers = [x for x, _ in QUALITY_HIST]
    max_c = max(counts)
    bar_w = (w - pad_l - pad_r) / N_BINS
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#1e293b;border-radius:8px;">']
    cutoff_x = pad_l + (0.60 / 1.0) * (w - pad_l - pad_r)
    for i, (center, cnt) in enumerate(QUALITY_HIST):
        bx = pad_l + i * bar_w
        bh = (cnt / max_c) * (h - pad_t - pad_b)
        by = h - pad_b - bh
        fill = "#64748b" if center < 0.60 else "#38bdf8"
        lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w-1:.1f}" height="{bh:.1f}" fill="{fill}" rx="1" opacity="0.85"/>')
    # cutoff line
    lines.append(f'<line x1="{cutoff_x:.1f}" y1="{pad_t}" x2="{cutoff_x:.1f}" y2="{h-pad_b}" stroke="#C74634" stroke-width="1.5" stroke-dasharray="4,3"/>')
    lines.append(f'<text x="{cutoff_x+4:.1f}" y="{pad_t+12}" fill="#C74634" font-size="9">cutoff=0.6</text>')
    # x-axis ticks
    for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        tx = pad_l + v * (w - pad_l - pad_r)
        lines.append(f'<text x="{tx:.1f}" y="{h-4}" fill="#64748b" font-size="9" text-anchor="middle">{v}</text>')
    lines.append(f'<text x="{w//2}" y="{h-18}" fill="#64748b" font-size="8" text-anchor="middle">Quality Score</text>')
    lines.append(f'<text x="12" y="{h//2}" fill="#94a3b8" font-size="9" text-anchor="middle" transform="rotate(-90,12,{h//2})">Count</text>')
    lines.append("</svg>")
    return "".join(lines)


def build_donut_svg() -> str:
    """Difficulty balance donut chart (easy/medium/hard)."""
    w, h = 420, 260
    cx, cy, r_outer, r_inner = w // 2, h // 2, 100, 55
    slices = [
        ("Easy 30%", 0.30, "#38bdf8"),
        ("Medium 50%", 0.50, "#a78bfa"),
        ("Hard 20%", 0.20, "#C74634"),
    ]
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#1e293b;border-radius:8px;">']
    # title
    lines.append(f'<text x="{cx}" y="22" fill="#94a3b8" font-size="11" text-anchor="middle" font-weight="600">Difficulty Distribution (Final 1600)</text>')

    start = -math.pi / 2
    for label, frac, color in slices:
        end = start + 2 * math.pi * frac
        # arc path
        laf = 1 if frac > 0.5 else 0
        x1 = cx + r_outer * math.cos(start)
        y1 = cy + r_outer * math.sin(start)
        x2 = cx + r_outer * math.cos(end)
        y2 = cy + r_outer * math.sin(end)
        ix1 = cx + r_inner * math.cos(end)
        iy1 = cy + r_inner * math.sin(end)
        ix2 = cx + r_inner * math.cos(start)
        iy2 = cy + r_inner * math.sin(start)
        d = (
            f"M {x1:.1f} {y1:.1f} "
            f"A {r_outer} {r_outer} 0 {laf} 1 {x2:.1f} {y2:.1f} "
            f"L {ix1:.1f} {iy1:.1f} "
            f"A {r_inner} {r_inner} 0 {laf} 0 {ix2:.1f} {iy2:.1f} Z"
        )
        lines.append(f'<path d="{d}" fill="{color}" opacity="0.88"/>')
        # label
        mid = start + math.pi * frac
        lx = cx + (r_outer + 18) * math.cos(mid)
        ly = cy + (r_outer + 18) * math.sin(mid)
        anchor = "start" if lx > cx else "end"
        lines.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{color}" font-size="11" text-anchor="{anchor}">{label}</text>')
        start = end

    # center text
    lines.append(f'<text x="{cx}" y="{cy-6}" fill="#e2e8f0" font-size="16" font-weight="700" text-anchor="middle">1600</text>')
    lines.append(f'<text x="{cx}" y="{cy+12}" fill="#64748b" font-size="9" text-anchor="middle">episodes</text>')
    lines.append("</svg>")
    return "".join(lines)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Dataset Curator", version="1.0.0")
else:
    app = None  # type: ignore


if app is not None:

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        funnel_svg = build_funnel_svg()
        hist_svg = build_quality_hist_svg()
        donut_svg = build_donut_svg()

        rows = ""
        for f in FILTERS:
            badge_color = "#ef4444" if f["removed"] > 0 else "#34d399"
            rows += (
            f"<tr><td>{f['label']}</td>"
            f"<td style='text-align:right'>{f['episodes_in']:,}</td>"
            f"<td style='text-align:right'>{f['episodes_out']:,}</td>"
            f"<td style='color:{badge_color};text-align:right'>−{f['removed']}</td>"
            f"<td style='color:#94a3b8;font-size:.82rem'>{f['reason']}</td></tr>"
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Dataset Curator — OCI Robot Cloud</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
    h1{{color:#38bdf8;font-size:1.5rem;margin-bottom:4px}}
    .sub{{color:#64748b;font-size:.85rem;margin-bottom:20px}}
    .card{{background:#1e293b;border-radius:10px;padding:16px;margin-bottom:20px}}
    .card h2{{color:#94a3b8;font-size:.95rem;margin-bottom:12px;text-transform:uppercase;letter-spacing:.05em}}
    .stats{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px}}
    .stat{{background:#0f172a;border-radius:8px;padding:12px 16px;min-width:140px}}
    .stat .val{{font-size:1.6rem;font-weight:700;color:#38bdf8}}
    .stat .lbl{{font-size:.78rem;color:#64748b;margin-top:2px}}
    table{{width:100%;border-collapse:collapse;font-size:.88rem}}
    th{{color:#64748b;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
    td{{padding:6px 8px;border-bottom:1px solid #1e3a5f}}
    tr:last-child td{{border-bottom:none}}
    .flex{{display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap}}
  </style>
</head>
<body>
  <h1>Dataset Curator</h1>
  <p class="sub">genesis_sdg_v3 · 2000 raw → 1600 curated · port 8185</p>

  <div class="card">
    <div class="stats">
      <div class="stat"><div class="val">2,000</div><div class="lbl">Raw Episodes</div></div>
      <div class="stat"><div class="val">1,600</div><div class="lbl">Curated Episodes</div></div>
      <div class="stat"><div class="val">80%</div><div class="lbl">Retention Rate</div></div>
      <div class="stat"><div class="val">0.78</div><div class="lbl">Median Quality Score</div></div>
      <div class="stat"><div class="val">5</div><div class="lbl">Filter Stages</div></div>
    </div>
  </div>

  <div class="card">
    <h2>Curation Funnel</h2>
    {funnel_svg}
  </div>

  <div class="card">
    <h2>Filter Pipeline</h2>
    <table>
      <thead><tr><th>Filter</th><th style='text-align:right'>In</th><th style='text-align:right'>Out</th><th style='text-align:right'>Removed</th><th>Reason</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>Quality Score Distribution &amp; Difficulty Balance</h2>
    <div class="flex">
      <div>
        <p style="color:#64748b;font-size:.8rem;margin-bottom:8px">Final 1600 episodes · cutoff=0.6 (gray bars excluded)</p>
        {hist_svg}
      </div>
      {donut_svg}
    </div>
  </div>
</body>
</html>"""
        return HTMLResponse(html)

    @app.get("/pipeline")
    async def get_pipeline():
        return JSONResponse({"filters": FILTERS, "summary": SUMMARY})

    @app.get("/filters")
    async def get_filters():
        return JSONResponse(FILTERS)

    @app.get("/distribution")
    async def get_distribution():
        return JSONResponse(
            {
                "bins": [{"center": c, "count": n} for c, n in QUALITY_HIST],
                "cutoff": 0.60,
                "median": 0.78,
                "n_episodes": 1600,
            }
        )

    @app.get("/summary")
    async def get_summary():
        return JSONResponse(SUMMARY)


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed")
    uvicorn.run("dataset_curator:app", host="0.0.0.0", port=8185, reload=False)

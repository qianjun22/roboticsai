"""SDG Scene Diversity Analyzer — OCI Robot Cloud (port 8198)

Analyzes training data coverage across scene parameters to ensure
the dataset distribution matches the target task distribution.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None
    HTMLResponse = None
    JSONResponse = None
    uvicorn = None

import math
import json

# ---------------------------------------------------------------------------
# Static data — 1600 curated episodes, 5 scene parameters
# ---------------------------------------------------------------------------

SCENE_PARAMS = [
    {
        "name": "cube_position_x",
        "label": "Cube Pos X",
        "range": [-0.3, 0.3],
        "unit": "m",
        "coverage": 0.94,
        "bins": 12,
        "distribution": "near-uniform with slight center bias",
        "bin_counts": [118, 124, 130, 138, 145, 158, 162, 150, 140, 132, 120, 110],
    },
    {
        "name": "cube_position_y",
        "label": "Cube Pos Y",
        "range": [-0.2, 0.2],
        "unit": "m",
        "coverage": 0.91,
        "bins": 8,
        "distribution": "near-uniform",
        "bin_counts": [190, 198, 205, 210, 208, 202, 195, 192],
    },
    {
        "name": "cube_height_z",
        "label": "Cube Height Z",
        "range": [0.41, 0.43],
        "unit": "m",
        "coverage": 0.88,
        "bins": 4,
        "distribution": "concentrated (small range)",
        "bin_counts": [350, 420, 510, 320],
        "gap": True,
    },
    {
        "name": "lighting_intensity",
        "label": "Lighting Intensity",
        "range": [0.3, 1.8],
        "unit": "lux_norm",
        "coverage": 0.82,
        "bins": 6,
        "distribution": "bimodal (bright/dim)",
        "bin_counts": [320, 140, 90, 80, 150, 420],
        "gap": True,
    },
    {
        "name": "background_texture",
        "label": "BG Texture",
        "range": None,
        "unit": "type",
        "n_types": 8,
        "coverage": 0.97,
        "bins": 8,
        "distribution": "uniform across 8 textures",
        "bin_counts": [196, 202, 198, 200, 205, 200, 199, 200],
    },
]

RECOMMENDATIONS = [
    "Increase cube_height_z variance by 5cm range in SDG v4 (current 2cm range is too small).",
    "Add more mid-intensity lighting scenarios to fill the bimodal gap in lighting_intensity.",
    "Maintain current cube_position_x/y diversity — near-uniform coverage is acceptable.",
    "background_texture coverage at 0.97 is excellent; no action needed.",
]

CORRELATION_MATRIX = [
    [1.00, 0.12, 0.05, 0.08, 0.03],
    [0.12, 1.00, 0.07, 0.06, 0.05],
    [0.05, 0.07, 1.00, 0.10, 0.04],
    [0.08, 0.06, 0.10, 1.00, 0.04],
    [0.03, 0.05, 0.04, 0.04, 1.00],
]

PARAM_NAMES_SHORT = ["x_pos", "y_pos", "z_ht", "light", "tex"]

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _coverage_heatmap_svg() -> str:
    """680×280 SVG: 5 rows, each a histogram of episode density with coverage label."""
    W, H = 680, 280
    ROW_H = 44
    PAD_LEFT = 110
    PAD_RIGHT = 20
    PAD_TOP = 18
    BAR_AREA_W = W - PAD_LEFT - PAD_RIGHT

    lines = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
             f'style="background:#0f172a;font-family:monospace">']
    # Title
    lines.append(f'<text x="{W//2}" y="13" text-anchor="middle" '
                 f'fill="#38bdf8" font-size="12" font-weight="bold">'
                 f'Coverage Heatmap — 1600 Episodes</text>')

    for i, p in enumerate(SCENE_PARAMS):
        y_base = PAD_TOP + 6 + i * (ROW_H + 4)
        counts = p["bin_counts"]
        max_c = max(counts)
        n_bins = len(counts)
        bin_w = BAR_AREA_W / n_bins
        is_gap = p.get("gap", False)
        cov = p["coverage"]

        # Row label
        lines.append(f'<text x="{PAD_LEFT - 5}" y="{y_base + ROW_H//2 + 4}" '
                     f'text-anchor="end" fill="#94a3b8" font-size="9">{p["label"]}</text>')

        for j, cnt in enumerate(counts):
            bh = int((cnt / max_c) * (ROW_H - 4))
            bx = PAD_LEFT + j * bin_w
            by = y_base + ROW_H - bh
            fill = "#C74634" if is_gap and (j == 0 or j == n_bins - 1 or cnt < max_c * 0.55) else "#38bdf8"
            lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bin_w - 1:.1f}" '
                         f'height="{bh}" fill="{fill}" opacity="0.85"/>')

        # Coverage label
        cov_color = "#C74634" if cov < 0.90 else "#4ade80"
        lines.append(f'<text x="{PAD_LEFT + BAR_AREA_W + PAD_RIGHT - 2}" '
                     f'y="{y_base + ROW_H//2 + 4}" text-anchor="end" '
                     f'fill="{cov_color}" font-size="10" font-weight="bold">{int(cov*100)}%</text>')

        # Divider
        lines.append(f'<line x1="{PAD_LEFT}" y1="{y_base + ROW_H + 2}" '
                     f'x2="{W - PAD_RIGHT}" y2="{y_base + ROW_H + 2}" '
                     f'stroke="#1e293b" stroke-width="1"/>')

    lines.append('</svg>')
    return "\n".join(lines)


def _radar_svg() -> str:
    """480×320 SVG: radar chart — coverage score per param vs 0.9 target."""
    W, H = 480, 320
    cx, cy = W // 2, H // 2 + 10
    R = 110
    N = len(SCENE_PARAMS)
    TARGET = 0.9

    def polar(angle_deg: float, r: float):
        rad = math.radians(angle_deg - 90)
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    angles = [i * 360 / N for i in range(N)]
    labels = [p["label"] for p in SCENE_PARAMS]
    scores = [p["coverage"] for p in SCENE_PARAMS]

    lines = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
             f'style="background:#0f172a;font-family:monospace">']
    lines.append(f'<text x="{W//2}" y="16" text-anchor="middle" fill="#38bdf8" '
                 f'font-size="12" font-weight="bold">Diversity Score Radar</text>')

    # Grid circles
    for level in [0.25, 0.5, 0.75, 1.0]:
        r = R * level
        lines.append(f'<circle cx="{cx}" cy="{cy}" r="{r:.1f}" fill="none" '
                     f'stroke="#1e3a5f" stroke-width="1"/>')
        lines.append(f'<text x="{cx + 4}" y="{cy - r + 4:.1f}" fill="#475569" '
                     f'font-size="8">{int(level*100)}%</text>')

    # Target circle (0.9, dashed)
    tr = R * TARGET
    lines.append(f'<circle cx="{cx}" cy="{cy}" r="{tr:.1f}" fill="none" '
                 f'stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="6,3"/>')
    lines.append(f'<text x="{cx + tr + 3:.1f}" y="{cy - 3}" fill="#f59e0b" font-size="8">target 90%</text>')

    # Axis lines
    for a in angles:
        x2, y2 = polar(a, R)
        lines.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" '
                     f'stroke="#334155" stroke-width="1"/>')

    # Current shape
    pts_actual = [polar(angles[i], R * scores[i]) for i in range(N)]
    poly_actual = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts_actual)
    lines.append(f'<polygon points="{poly_actual}" fill="#38bdf8" fill-opacity="0.2" '
                 f'stroke="#38bdf8" stroke-width="2"/>')
    for x, y in pts_actual:
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#38bdf8"/>')

    # Labels
    for i, (a, lbl, score) in enumerate(zip(angles, labels, scores)):
        lx, ly = polar(a, R + 18)
        anchor = "middle"
        if lx < cx - 20:
            anchor = "end"
        elif lx > cx + 20:
            anchor = "start"
        color = "#C74634" if score < TARGET else "#94a3b8"
        lines.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
                     f'fill="{color}" font-size="9">{lbl}</text>')
        lines.append(f'<text x="{lx:.1f}" y="{ly + 11:.1f}" text-anchor="{anchor}" '
                     f'fill="{color}" font-size="9" font-weight="bold">{int(score*100)}%</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def _correlation_matrix_svg() -> str:
    """480×280 SVG: 5×5 heatmap of pairwise parameter correlations."""
    W, H = 480, 280
    N = 5
    PAD = 60
    CELL = (min(W, H) - PAD - 20) // N  # ~40

    def corr_color(v: float) -> str:
        # v in [-1, 1]; 0 = neutral dark, 1 = strong blue, -1 = strong red
        if v >= 0:
            t = v
            r = int(56 * (1 - t))
            g = int(189 * (1 - t) + 56 * t)
            b = int(248 * t + 30 * (1 - t))
        else:
            t = -v
            r = int(199 * t + 30 * (1 - t))
            g = int(56 * (1 - t))
            b = int(52 * (1 - t))
        return f"rgb({r},{g},{b})"

    lines = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
             f'style="background:#0f172a;font-family:monospace">']
    lines.append(f'<text x="{W//2}" y="14" text-anchor="middle" fill="#38bdf8" '
                 f'font-size="12" font-weight="bold">Parameter Correlation Matrix</text>')

    for i in range(N):
        for j in range(N):
            x = PAD + j * CELL
            y = 24 + i * CELL
            v = CORRELATION_MATRIX[i][j]
            fill = corr_color(v)
            lines.append(f'<rect x="{x}" y="{y}" width="{CELL - 2}" height="{CELL - 2}" '
                         f'fill="{fill}" rx="2"/>')
            text_fill = "#0f172a" if abs(v) > 0.4 else "#e2e8f0"
            lines.append(f'<text x="{x + CELL//2 - 1}" y="{y + CELL//2 + 4}" '
                         f'text-anchor="middle" fill="{text_fill}" font-size="9">{v:.2f}</text>')

    # Column labels (top)
    for j, lbl in enumerate(PARAM_NAMES_SHORT):
        x = PAD + j * CELL + CELL // 2
        lines.append(f'<text x="{x}" y="22" text-anchor="middle" '
                     f'fill="#94a3b8" font-size="8">{lbl}</text>')

    # Row labels (left)
    for i, lbl in enumerate(PARAM_NAMES_SHORT):
        y = 24 + i * CELL + CELL // 2 + 4
        lines.append(f'<text x="{PAD - 4}" y="{y}" text-anchor="end" '
                     f'fill="#94a3b8" font-size="8">{lbl}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    heatmap = _coverage_heatmap_svg()
    radar = _radar_svg()
    corr = _correlation_matrix_svg()

    param_rows = ""
    for p in SCENE_PARAMS:
        gap_badge = '<span style="background:#C74634;color:#fff;font-size:10px;padding:1px 5px;border-radius:3px;margin-left:6px">GAP</span>' if p.get("gap") else ""
        cov_color = "#C74634" if p["coverage"] < 0.90 else "#4ade80"
        rng = f"{p['range'][0]} – {p['range'][1]} {p['unit']}" if p.get("range") else f"8 texture types"
        param_rows += f"""
        <tr>
          <td style="color:#38bdf8">{p['name']}{gap_badge}</td>
          <td>{rng}</td>
          <td style="color:{cov_color};font-weight:bold">{int(p['coverage']*100)}%</td>
          <td>{p['bins']}</td>
          <td style="color:#94a3b8;font-size:12px">{p['distribution']}</td>
        </tr>"""

    rec_items = "".join(f'<li style="margin:6px 0;color:#94a3b8">{r}</li>' for r in RECOMMENDATIONS)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Scene Diversity Analyzer — OCI Robot Cloud</title>
  <style>
    body {{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
    h1 {{color:#C74634;margin:0 0 4px}}
    h2 {{color:#38bdf8;font-size:14px;margin:18px 0 8px}}
    .badge {{background:#1e3a5f;color:#38bdf8;padding:2px 8px;border-radius:4px;font-size:11px}}
    table {{border-collapse:collapse;width:100%;margin-bottom:12px}}
    th {{text-align:left;color:#475569;font-size:11px;padding:4px 10px;border-bottom:1px solid #1e293b}}
    td {{padding:6px 10px;border-bottom:1px solid #0f172a;font-size:12px}}
    tr:hover td {{background:#1e293b}}
    .grid {{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:12px}}
    .card {{background:#1e293b;border-radius:8px;padding:14px}}
    .stat {{font-size:26px;font-weight:bold;color:#38bdf8}}
    .stat-label {{font-size:11px;color:#64748b}}
    ul {{padding-left:18px;margin:0}}
    .stats-row {{display:flex;gap:24px;margin-bottom:16px}}
  </style>
</head>
<body>
  <h1>SDG Scene Diversity Analyzer</h1>
  <p style="color:#64748b;margin:0 0 16px">Port 8198 &nbsp;|&nbsp; <span class="badge">1600 episodes</span> &nbsp;|&nbsp; <span class="badge">5 parameters</span></p>

  <div class="stats-row">
    <div><div class="stat">0.904</div><div class="stat-label">Mean Coverage</div></div>
    <div><div class="stat" style="color:#f59e0b">2</div><div class="stat-label">Gaps Detected</div></div>
    <div><div class="stat">1600</div><div class="stat-label">Episodes Curated</div></div>
    <div><div class="stat" style="color:#4ade80">3</div><div class="stat-label">Params &ge;90%</div></div>
  </div>

  <h2>Parameter Coverage</h2>
  <table>
    <thead><tr><th>Parameter</th><th>Range</th><th>Coverage</th><th>Bins</th><th>Distribution</th></tr></thead>
    <tbody>{param_rows}</tbody>
  </table>

  <div class="grid">
    <div class="card">
      <h2 style="margin-top:0">Coverage Heatmap</h2>
      {heatmap}
    </div>
    <div class="card">
      <h2 style="margin-top:0">Diversity Score Radar</h2>
      {radar}
    </div>
  </div>

  <div class="card" style="margin-top:16px">
    <h2 style="margin-top:0">Correlation Matrix</h2>
    {corr}
    <p style="color:#64748b;font-size:11px;margin:8px 0 0">x_pos vs y_pos: 0.12 (good — independent); lighting vs texture: 0.04 (good)</p>
  </div>

  <div class="card" style="margin-top:16px">
    <h2 style="margin-top:0">Gap Analysis &amp; Recommendations</h2>
    <ul>{rec_items}</ul>
  </div>

  <p style="color:#1e3a5f;font-size:10px;margin-top:20px">OCI Robot Cloud &copy; 2026 Oracle Corporation</p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(
        title="Scene Diversity Analyzer",
        description="SDG scene parameter coverage analysis for OCI Robot Cloud",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _dashboard_html()

    @app.get("/params")
    def get_params():
        return JSONResponse({
            "total_episodes": 1600,
            "parameters": SCENE_PARAMS,
        })

    @app.get("/diversity-score")
    def diversity_score():
        scores = {p["name"]: p["coverage"] for p in SCENE_PARAMS}
        mean_cov = sum(scores.values()) / len(scores)
        gaps = [p["name"] for p in SCENE_PARAMS if p.get("gap")]
        return JSONResponse({
            "mean_coverage": round(mean_cov, 4),
            "scores": scores,
            "target": 0.90,
            "gaps_detected": gaps,
            "status": "NEEDS_IMPROVEMENT" if gaps else "OK",
        })

    @app.get("/recommendations")
    def recommendations():
        return JSONResponse({"recommendations": RECOMMENDATIONS})

else:
    app = None


if __name__ == "__main__":
    if uvicorn and app:
        uvicorn.run(app, host="0.0.0.0", port=8198)
    else:
        print("FastAPI/uvicorn not installed. Install with: pip install fastapi uvicorn")

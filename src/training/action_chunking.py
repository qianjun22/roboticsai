"""Action Chunking Configuration Optimizer — OCI Robot Cloud
Port: 8149
Optimizes GR00T action chunk size for best SR / latency / smoothness trade-off.
"""

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

import math
from datetime import datetime

# ---------------------------------------------------------------------------
# Chunk size benchmark results
# ---------------------------------------------------------------------------
CONFIGS = [
    {"chunk": 4,  "sr": 0.61, "mae": 0.041, "latency_ms": 189, "smoothness": 0.72, "jitter": 0.18},
    {"chunk": 8,  "sr": 0.68, "mae": 0.034, "latency_ms": 201, "smoothness": 0.79, "jitter": 0.14},
    {"chunk": 12, "sr": 0.74, "mae": 0.028, "latency_ms": 214, "smoothness": 0.83, "jitter": 0.11},
    {"chunk": 16, "sr": 0.78, "mae": 0.023, "latency_ms": 226, "smoothness": 0.87, "jitter": 0.08},
    {"chunk": 24, "sr": 0.76, "mae": 0.025, "latency_ms": 251, "smoothness": 0.84, "jitter": 0.09},
    {"chunk": 32, "sr": 0.71, "mae": 0.031, "latency_ms": 289, "smoothness": 0.81, "jitter": 0.12},
]
PRODUCTION_CHUNK = 16
RECOMMENDATION = (
    "chunk=16 optimal. chunk=24 next best for smoother execution at cost of +25ms latency."
)


def composite_score(c: dict) -> float:
    """0.4*sr + 0.2*(1-mae/0.05) + 0.2*(1-latency/300) + 0.2*smoothness"""
    return (
        0.4 * c["sr"]
        + 0.2 * (1 - c["mae"] / 0.05)
        + 0.2 * (1 - c["latency_ms"] / 300)
        + 0.2 * c["smoothness"]
    )


# ---------------------------------------------------------------------------
# SVG: SR vs Chunk Size line chart 680×220
# ---------------------------------------------------------------------------
def _sr_line_chart() -> str:
    W, H = 680, 220
    PL, PR, PT, PB = 52, 24, 24, 40
    cw = W - PL - PR
    ch = H - PT - PB

    chunks = [c["chunk"] for c in CONFIGS]
    srs = [c["sr"] for c in CONFIGS]
    n = len(chunks)

    def px(i, sr):
        x = PL + i * cw / (n - 1)
        y = PT + ch - sr * ch  # sr in [0,1]
        return x, y

    # Grid lines
    grid = ""
    for v in [0.2, 0.4, 0.6, 0.8, 1.0]:
        _, y = px(0, v)
        grid += f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{PL-4}" y="{y:.1f}" fill="#94a3b8" font-size="10" text-anchor="end" dominant-baseline="middle">{v:.1f}</text>'

    # Dashed vertical at chunk=16 (index 3)
    vx, _ = px(3, 0)
    _, vy_top = px(3, 1.0)
    _, vy_bot = px(3, 0.0)
    dashed = (
        f'<line x1="{vx:.1f}" y1="{vy_top:.1f}" x2="{vx:.1f}" y2="{vy_bot:.1f}" '
        f'stroke="#C74634" stroke-width="1.5" stroke-dasharray="5,4" opacity="0.7"/>'
    )

    # Polyline
    pts = " ".join(f"{px(i, srs[i])[0]:.1f},{px(i, srs[i])[1]:.1f}" for i in range(n))
    line = f'<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>'

    # Circles
    circles = ""
    for i, (chunk, sr) in enumerate(zip(chunks, srs)):
        x, y = px(i, sr)
        if chunk == PRODUCTION_CHUNK:
            # Star marker for peak
            circles += f'<text x="{x:.1f}" y="{y-10:.1f}" fill="#f59e0b" font-size="16" text-anchor="middle">&#9733;</text>'
            circles += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#C74634" stroke="#f1f5f9" stroke-width="1.5"/>'
        else:
            circles += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#38bdf8" stroke="#0f172a" stroke-width="1.5"/>'
        circles += f'<text x="{x:.1f}" y="{H-6}" fill="#94a3b8" font-size="10" text-anchor="middle">{chunk}</text>'

    # Axis labels
    ax_label = (
        f'<text x="{W//2}" y="{H-2}" fill="#64748b" font-size="11" text-anchor="middle">Chunk Size</text>'
        f'<text x="12" y="{PT + ch//2}" fill="#64748b" font-size="11" text-anchor="middle" '
        f'transform="rotate(-90,12,{PT + ch//2})">Success Rate</text>'
    )

    prod_label = f'<text x="{vx+4:.1f}" y="{PT+12}" fill="#C74634" font-size="10">chunk=16 (prod)</text>'

    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#0f172a;border-radius:8px;">'
        f'{grid}{dashed}{line}{circles}{ax_label}{prod_label}'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# SVG: Radar chart 480×320 — 5 axes
# Axes: sr, mae_inv, latency_inv, smoothness, jitter_inv
# ---------------------------------------------------------------------------
def _radar_svg() -> str:
    W, H = 480, 320
    cx, cy, r = W // 2, H // 2 + 10, 110
    AXES = ["SR", "MAE inv", "Lat inv", "Smooth", "Jitter inv"]
    N = len(AXES)

    def axis_angle(i):
        return math.pi / 2 - 2 * math.pi * i / N  # start top, clockwise

    def polar(i, val):
        a = axis_angle(i)
        return cx + val * r * math.cos(a), cy - val * r * math.sin(a)

    # Normalise each config to [0,1] per axis
    def normalise(cfg):
        return [
            cfg["sr"],
            1 - cfg["mae"] / 0.05,
            1 - cfg["latency_ms"] / 300,
            cfg["smoothness"],
            1 - cfg["jitter"] / 0.20,
        ]

    COLORS = ["#38bdf8", "#f59e0b", "#22c55e", "#a855f7", "#f472b6", "#C74634"]

    # Spider web grid (3 rings)
    web = ""
    for ring in [0.33, 0.67, 1.0]:
        pts = " ".join(f"{polar(i, ring)[0]:.1f},{polar(i, ring)[1]:.1f}" for i in range(N))
        pts += f" {polar(0, ring)[0]:.1f},{polar(0, ring)[1]:.1f}"
        web += f'<polyline points="{pts}" fill="none" stroke="#1e293b" stroke-width="1"/>'
    for i in range(N):
        x1, y1 = polar(i, 0)
        x2, y2 = polar(i, 1)
        web += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#1e293b" stroke-width="1"/>'

    # Axis labels
    labels = ""
    for i, name in enumerate(AXES):
        x, y = polar(i, 1.22)
        labels += f'<text x="{x:.1f}" y="{y:.1f}" fill="#94a3b8" font-size="11" text-anchor="middle" dominant-baseline="middle">{name}</text>'

    # Data polygons
    polys = ""
    for j, cfg in enumerate(CONFIGS):
        vals = normalise(cfg)
        pts = " ".join(f"{polar(i, vals[i])[0]:.1f},{polar(i, vals[i])[1]:.1f}" for i in range(N))
        pts += f" {polar(0, vals[0])[0]:.1f},{polar(0, vals[0])[1]:.1f}"
        is_prod = cfg["chunk"] == PRODUCTION_CHUNK
        sw = "2.5" if is_prod else "1.2"
        color = "#C74634" if is_prod else COLORS[j]
        opacity = "0.9" if is_prod else "0.5"
        polys += f'<polyline points="{pts}" fill="{color}" fill-opacity="0.08" stroke="{color}" stroke-width="{sw}" opacity="{opacity}"/>'

    # Legend
    legend = ""
    for j, cfg in enumerate(CONFIGS):
        is_prod = cfg["chunk"] == PRODUCTION_CHUNK
        color = "#C74634" if is_prod else COLORS[j]
        label = f'chunk={cfg["chunk"]}' + (" ★ PROD" if is_prod else "")
        lx = 10 + (j % 3) * 155
        ly = H - 42 + (j // 3) * 18
        legend += f'<rect x="{lx}" y="{ly}" width="10" height="10" fill="{color}"/>'
        legend += f'<text x="{lx+14}" y="{ly+9}" fill="{"#f1f5f9" if is_prod else "#94a3b8"}" font-size="10" font-weight="{"700" if is_prod else "400"}">{label}</text>'

    title = f'<text x="{W//2}" y="18" fill="#cbd5e1" font-size="13" font-weight="600" text-anchor="middle">Multi-Metric Radar — All Chunk Sizes</text>'

    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#0f172a;border-radius:8px;">'
        f'{web}{polys}{labels}{title}{legend}'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
def _dashboard_html(compare_a: int = None, compare_b: int = None) -> str:
    sr_svg = _sr_line_chart()
    radar_svg = _radar_svg()

    # Config table rows
    table_rows = ""
    for c in CONFIGS:
        score = composite_score(c)
        is_prod = c["chunk"] == PRODUCTION_CHUNK
        highlight = 'background:#1a2744;' if is_prod else ''
        prod_badge = ' <span style="background:#C74634;color:#fff;padding:1px 6px;border-radius:10px;font-size:10px;">PROD</span>' if is_prod else ''
        table_rows += (
            f'<tr style="border-bottom:1px solid #1e293b;{highlight}">'
            f'<td style="padding:8px 12px;color:#f1f5f9;font-weight:{"700" if is_prod else "400"};">'
            f'{c["chunk"]}{prod_badge}</td>'
            f'<td style="padding:8px 12px;color:#38bdf8;">{c["sr"]:.2f}</td>'
            f'<td style="padding:8px 12px;color:#94a3b8;">{c["mae"]:.3f}</td>'
            f'<td style="padding:8px 12px;color:#94a3b8;">{c["latency_ms"]}ms</td>'
            f'<td style="padding:8px 12px;color:#94a3b8;">{c["smoothness"]:.2f}</td>'
            f'<td style="padding:8px 12px;color:#94a3b8;">{c["jitter"]:.2f}</td>'
            f'<td style="padding:8px 12px;color:#22c55e;font-weight:600;">{score:.3f}</td>'
            f'</tr>'
        )

    # Optional compare panel
    compare_panel = ""
    if compare_a is not None and compare_b is not None:
        ca = next((c for c in CONFIGS if c["chunk"] == compare_a), None)
        cb = next((c for c in CONFIGS if c["chunk"] == compare_b), None)
        if ca and cb:
            def diff_cell(va, vb, higher_better=True):
                delta = vb - va
                better = delta > 0 if higher_better else delta < 0
                color = "#22c55e" if better else ("#ef4444" if delta != 0 else "#94a3b8")
                sign = "+" if delta > 0 else ""
                return f'<span style="color:{color};">{sign}{delta:.3f}</span>'

            compare_panel = f"""
            <h2>Compare: chunk={compare_a} vs chunk={compare_b}</h2>
            <table style="margin-bottom:24px;">
              <thead><tr><th>Metric</th><th>chunk={compare_a}</th><th>chunk={compare_b}</th><th>Delta</th></tr></thead>
              <tbody>
                <tr style="border-bottom:1px solid #1e293b;">
                  <td style="padding:8px 12px;color:#94a3b8;">Success Rate</td>
                  <td style="padding:8px 12px;color:#f1f5f9;">{ca['sr']:.2f}</td>
                  <td style="padding:8px 12px;color:#f1f5f9;">{cb['sr']:.2f}</td>
                  <td style="padding:8px 12px;">{diff_cell(ca['sr'],cb['sr'])}</td></tr>
                <tr style="border-bottom:1px solid #1e293b;">
                  <td style="padding:8px 12px;color:#94a3b8;">MAE</td>
                  <td style="padding:8px 12px;color:#f1f5f9;">{ca['mae']:.3f}</td>
                  <td style="padding:8px 12px;color:#f1f5f9;">{cb['mae']:.3f}</td>
                  <td style="padding:8px 12px;">{diff_cell(ca['mae'],cb['mae'],False)}</td></tr>
                <tr style="border-bottom:1px solid #1e293b;">
                  <td style="padding:8px 12px;color:#94a3b8;">Latency</td>
                  <td style="padding:8px 12px;color:#f1f5f9;">{ca['latency_ms']}ms</td>
                  <td style="padding:8px 12px;color:#f1f5f9;">{cb['latency_ms']}ms</td>
                  <td style="padding:8px 12px;">{diff_cell(ca['latency_ms'],cb['latency_ms'],False)}</td></tr>
                <tr style="border-bottom:1px solid #1e293b;">
                  <td style="padding:8px 12px;color:#94a3b8;">Smoothness</td>
                  <td style="padding:8px 12px;color:#f1f5f9;">{ca['smoothness']:.2f}</td>
                  <td style="padding:8px 12px;color:#f1f5f9;">{cb['smoothness']:.2f}</td>
                  <td style="padding:8px 12px;">{diff_cell(ca['smoothness'],cb['smoothness'])}</td></tr>
                <tr>
                  <td style="padding:8px 12px;color:#94a3b8;">Composite Score</td>
                  <td style="padding:8px 12px;color:#22c55e;">{composite_score(ca):.3f}</td>
                  <td style="padding:8px 12px;color:#22c55e;">{composite_score(cb):.3f}</td>
                  <td style="padding:8px 12px;">{diff_cell(composite_score(ca),composite_score(cb))}</td></tr>
              </tbody>
            </table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Action Chunking Optimizer — OCI Robot Cloud</title>
<style>
  body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        background:#0f172a;color:#f1f5f9;}}
  h1{{color:#38bdf8;}} h2{{color:#cbd5e1;font-size:16px;margin-top:28px;}}
  table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden;}}
  th{{padding:10px 12px;text-align:left;color:#94a3b8;font-size:12px;
      text-transform:uppercase;background:#0f172a;border-bottom:2px solid #334155;}}
</style>
</head>
<body>
<div style="max-width:1000px;margin:0 auto;padding:24px;">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">
    <div style="width:12px;height:12px;border-radius:50%;background:#C74634;"></div>
    <span style="color:#C74634;font-size:12px;font-weight:600;">OCI ROBOT CLOUD · PORT 8149</span>
  </div>
  <h1 style="margin:0 0 4px;">Action Chunking Optimizer</h1>
  <p style="color:#64748b;margin:0 0 24px;">GR00T inference · chunk size benchmark · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>

  <!-- KPI row -->
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;">
    <div style="background:#1e293b;border-radius:8px;padding:16px;text-align:center;border-left:3px solid #C74634;">
      <div style="font-size:28px;font-weight:700;color:#C74634;">{PRODUCTION_CHUNK}</div>
      <div style="color:#94a3b8;font-size:12px;">Production Chunk</div>
    </div>
    <div style="background:#1e293b;border-radius:8px;padding:16px;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:#38bdf8;">0.78</div>
      <div style="color:#94a3b8;font-size:12px;">Best SR</div>
    </div>
    <div style="background:#1e293b;border-radius:8px;padding:16px;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:#22c55e;">226ms</div>
      <div style="color:#94a3b8;font-size:12px;">Prod Latency</div>
    </div>
    <div style="background:#1e293b;border-radius:8px;padding:16px;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:#a855f7;">{composite_score(next(c for c in CONFIGS if c['chunk']==16)):.3f}</div>
      <div style="color:#94a3b8;font-size:12px;">Composite Score</div>
    </div>
  </div>

  <!-- Recommendation banner -->
  <div style="background:#1a2744;border:1px solid #C74634;border-radius:8px;padding:14px 18px;margin-bottom:24px;">
    <span style="color:#f59e0b;font-weight:700;">Recommendation: </span>
    <span style="color:#f1f5f9;">{RECOMMENDATION}</span>
  </div>

  <h2>SR vs Chunk Size</h2>
  <div style="margin-bottom:24px;">{sr_svg}</div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px;align-items:start;">
    <div>
      <h2>Multi-Metric Radar</h2>
      {radar_svg}
    </div>
    <div>
      <h2>Benchmark Results</h2>
      <table>
        <thead><tr><th>Chunk</th><th>SR</th><th>MAE</th><th>Latency</th><th>Smooth</th><th>Jitter</th><th>Score</th></tr></thead>
        <tbody>{table_rows}</tbody>
      </table>
      <p style="font-size:11px;color:#475569;margin-top:8px;">
        Score = 0.4·SR + 0.2·(1−MAE/0.05) + 0.2·(1−lat/300) + 0.2·smoothness
      </p>
    </div>
  </div>

  {compare_panel}

  <div style="color:#334155;font-size:11px;text-align:center;">OCI Robot Cloud · Action Chunking Optimizer v1.0 · Port 8149</div>
</div>
</body></html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if FastAPI is not None:
    app = FastAPI(title="Action Chunking Optimizer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        a = request.query_params.get("a")
        b = request.query_params.get("b")
        ca = int(a) if a else None
        cb = int(b) if b else None
        return _dashboard_html(ca, cb)

    @app.get("/configs")
    async def get_configs():
        enriched = [
            {**c, "composite_score": round(composite_score(c), 4),
             "production": c["chunk"] == PRODUCTION_CHUNK}
            for c in CONFIGS
        ]
        return {"configs": enriched, "production_chunk": PRODUCTION_CHUNK}

    @app.get("/optimal")
    async def get_optimal():
        best = max(CONFIGS, key=composite_score)
        return {
            "optimal_chunk": best["chunk"],
            "composite_score": round(composite_score(best), 4),
            "metrics": best,
            "recommendation": RECOMMENDATION,
            "production_chunk": PRODUCTION_CHUNK,
            "is_production_optimal": best["chunk"] == PRODUCTION_CHUNK,
        }

    @app.get("/compare")
    async def compare(a: int = 16, b: int = 24):
        ca = next((c for c in CONFIGS if c["chunk"] == a), None)
        cb = next((c for c in CONFIGS if c["chunk"] == b), None)
        if not ca or not cb:
            return JSONResponse(
                status_code=404,
                content={"error": f"chunk size not found; valid: {[c['chunk'] for c in CONFIGS]}"},
            )
        return {
            "a": {**ca, "composite_score": round(composite_score(ca), 4)},
            "b": {**cb, "composite_score": round(composite_score(cb), 4)},
            "delta_sr": round(cb["sr"] - ca["sr"], 4),
            "delta_mae": round(cb["mae"] - ca["mae"], 4),
            "delta_latency_ms": cb["latency_ms"] - ca["latency_ms"],
            "delta_composite": round(composite_score(cb) - composite_score(ca), 4),
            "html_url": f"/?a={a}&b={b}",
        }

if __name__ == "__main__":
    if FastAPI is None:
        raise RuntimeError("fastapi not installed. Run: pip install fastapi uvicorn")
    uvicorn.run(app, host="0.0.0.0", port=8149)

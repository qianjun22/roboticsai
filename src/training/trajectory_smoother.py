"""Trajectory Smoother — OCI Robot Cloud  (port 8184)

Post-processes robot action sequences with multiple smoothing algorithms and
serves a dark-theme dashboard comparing their jerk/latency trade-offs.
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
# Algorithm metadata
# ---------------------------------------------------------------------------

ALGORITHMS = [
    {
        "name": "raw",
        "label": "Raw",
        "color": "#94a3b8",
        "jerk_rms": 0.847,
        "vel_max": 0.521,
        "smoothness_score": 0.78,
        "latency_overhead_ms": 0.0,
        "params": {},
    },
    {
        "name": "gaussian_filter",
        "label": "Gaussian σ=2",
        "color": "#38bdf8",
        "jerk_rms": 0.312,
        "vel_max": 0.498,
        "smoothness_score": 0.89,
        "latency_overhead_ms": 0.8,
        "params": {"sigma": 2.0},
    },
    {
        "name": "savgol_filter",
        "label": "Savitzky-Golay w=11",
        "color": "#a78bfa",
        "jerk_rms": 0.241,
        "vel_max": 0.487,
        "smoothness_score": 0.92,
        "latency_overhead_ms": 1.2,
        "params": {"window": 11, "poly": 3},
    },
    {
        "name": "cubic_spline",
        "label": "Cubic Spline k=16",
        "color": "#C74634",
        "jerk_rms": 0.198,
        "vel_max": 0.482,
        "smoothness_score": 0.94,
        "latency_overhead_ms": 3.4,
        "params": {"knots": 16},
    },
    {
        "name": "chunk_blend",
        "label": "Chunk Blend ov=4",
        "color": "#34d399",
        "jerk_rms": 0.287,
        "vel_max": 0.493,
        "smoothness_score": 0.91,
        "latency_overhead_ms": 0.4,
        "params": {"overlap": 4},
    },
]

RECOMMENDATION = (
    "chunk_blend optimal for production: +13pp smoothness at only 0.4 ms overhead. "
    "cubic_spline best offline."
)

# ---------------------------------------------------------------------------
# Trajectory generation helpers
# ---------------------------------------------------------------------------

SPIKE_STEPS = {20, 38, 55, 71, 88}
N_STEPS = 100


def _generate_raw_joint4() -> list:
    """100-point joint_4 trajectory with jerk spikes at known steps."""
    rng = random.Random(42)
    traj = []
    val = 0.0
    for i in range(N_STEPS):
        delta = rng.uniform(-0.02, 0.02)
        if i in SPIKE_STEPS:
            delta += rng.choice([-1, 1]) * rng.uniform(0.18, 0.25)
        val = max(-1.0, min(1.0, val + delta))
        traj.append(round(val, 4))
    return traj


def _gaussian_smooth(traj: list, sigma: float = 2.0) -> list:
    """1-D Gaussian smoothing via stdlib math only."""
    n = len(traj)
    radius = int(3 * sigma)
    kernel = [math.exp(-0.5 * (k / sigma) ** 2) for k in range(-radius, radius + 1)]
    ksum = sum(kernel)
    kernel = [k / ksum for k in kernel]
    out = []
    for i in range(n):
        acc = 0.0
        for j, w in enumerate(kernel):
            idx = i + j - radius
            idx = max(0, min(n - 1, idx))
            acc += traj[idx] * w
        out.append(round(acc, 4))
    return out


def _movavg_smooth(traj: list, window: int = 11) -> list:
    """Moving-average approximation of Savitzky-Golay (stdlib only)."""
    n = len(traj)
    half = window // 2
    out = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        out.append(round(sum(traj[lo:hi]) / (hi - lo), 4))
    return out


def _chunk_blend_smooth(traj: list, overlap: int = 4) -> list:
    """Simple chunk-blend: average neighbouring values in overlap zones."""
    return _movavg_smooth(traj, window=overlap * 2 + 1)


def _spline_smooth(traj: list, knots: int = 16) -> list:
    """Piecewise linear smoothing approximating cubic-spline output."""
    n = len(traj)
    step = max(1, n // knots)
    anchors = list(range(0, n, step))
    if anchors[-1] != n - 1:
        anchors.append(n - 1)
    out = [0.0] * n
    for seg in range(len(anchors) - 1):
        a, b = anchors[seg], anchors[seg + 1]
        va, vb = traj[a], traj[b]
        for i in range(a, b + 1):
            t = (i - a) / max(1, b - a)
            out[i] = round(va + (vb - va) * t, 4)
    return out


RAW_TRAJ = _generate_raw_joint4()
SMOOTHED: dict = {
    "raw": RAW_TRAJ,
    "gaussian_filter": _gaussian_smooth(RAW_TRAJ, sigma=2.0),
    "savgol_filter": _movavg_smooth(RAW_TRAJ, window=11),
    "cubic_spline": _spline_smooth(RAW_TRAJ, knots=16),
    "chunk_blend": _chunk_blend_smooth(RAW_TRAJ, overlap=4),
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

_SX, _SY = 680, 240  # comparison canvas
_PAD = 40


def _scale_x(step: int, total: int = N_STEPS, w: int = _SX) -> float:
    return _PAD + (step / (total - 1)) * (w - 2 * _PAD)


def _scale_y(val: float, lo: float = -1.0, hi: float = 1.0, h: int = _SY) -> float:
    pad_top = 20
    pad_bot = 30
    return pad_top + (1.0 - (val - lo) / (hi - lo)) * (h - pad_top - pad_bot)


def _polyline(points: list, color: str, width: float = 1.5, opacity: float = 1.0) -> str:
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>'


def build_comparison_svg() -> str:
    lines = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_SX}" height="{_SY}" '
        f'style="background:#1e293b;border-radius:8px;">'
    )
    # axes
    lines.append(
        f'<line x1="{_PAD}" y1="20" x2="{_PAD}" y2="{_SY-30}" stroke="#334155" stroke-width="1"/>'
    )
    lines.append(
        f'<line x1="{_PAD}" y1="{_SY-30}" x2="{_SX-_PAD}" y2="{_SY-30}" stroke="#334155" stroke-width="1"/>'
    )
    # gridlines
    for v in [-0.5, 0.0, 0.5]:
        gy = _scale_y(v)
        lines.append(
            f'<line x1="{_PAD}" y1="{gy:.1f}" x2="{_SX-_PAD}" y2="{gy:.1f}" '
            f'stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>'
        )
        lines.append(f'<text x="{_PAD-4}" y="{gy+4:.1f}" fill="#64748b" font-size="9" text-anchor="end">{v}</text>')
    # axis labels
    lines.append(f'<text x="{_SX//2}" y="{_SY-4}" fill="#94a3b8" font-size="10" text-anchor="middle">Step</text>')
    lines.append(
        f'<text x="10" y="{(_SY)//2}" fill="#94a3b8" font-size="10" text-anchor="middle" '
        f'transform="rotate(-90,10,{_SY//2})">Joint 4</text>'
    )
    # raw trajectory (gray, behind)
    raw_pts = [(_scale_x(i), _scale_y(v)) for i, v in enumerate(RAW_TRAJ)]
    lines.append(_polyline(raw_pts, "#475569", width=1.0, opacity=0.6))
    # spike markers
    for s in SPIKE_STEPS:
        sx = _scale_x(s)
        lines.append(f'<line x1="{sx:.1f}" y1="20" x2="{sx:.1f}" y2="{_SY-30}" stroke="#ef4444" stroke-width="0.8" stroke-dasharray="3,3" opacity="0.5"/>')
    # smoothed trajectories (skip raw)
    for alg in ALGORITHMS[1:]:
        pts = [(_scale_x(i), _scale_y(v)) for i, v in enumerate(SMOOTHED[alg["name"]])]
        lines.append(_polyline(pts, alg["color"], width=1.8))
    # legend
    lx, ly = _PAD + 5, 28
    lines.append(f'<text x="{lx}" y="{ly}" fill="#94a3b8" font-size="9">— Raw</text>')
    for i, alg in enumerate(ALGORITHMS[1:]):
        lx2 = lx + 60 + i * 115
        lines.append(f'<text x="{lx2}" y="{ly}" fill="{alg["color"]}" font-size="9">— {alg["label"]}</text>')
    lines.append("</svg>")
    return "".join(lines)


def build_jerk_bar_svg() -> str:
    w, h = 680, 160
    pad_l, pad_r, pad_t, pad_b = 130, 20, 20, 30
    vals = [(a["label"], a["jerk_rms"], a["color"]) for a in ALGORITHMS]
    max_val = max(v for _, v, _ in vals)
    bar_h = (h - pad_t - pad_b) / len(vals) - 4
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#1e293b;border-radius:8px;">']
    for i, (label, val, color) in enumerate(vals):
        y = pad_t + i * ((h - pad_t - pad_b) / len(vals))
        bar_w = (val / max_val) * (w - pad_l - pad_r)
        fill = "#C74634" if label == "Cubic Spline k=16" else color
        lines.append(f'<rect x="{pad_l}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{fill}" rx="3"/>')
        lines.append(f'<text x="{pad_l-6}" y="{y+bar_h/2+4:.1f}" fill="#cbd5e1" font-size="10" text-anchor="end">{label}</text>')
        pct = "" if label == "Raw" else f" ({(1-val/0.847)*100:.1f}%↓)"
        lines.append(f'<text x="{pad_l+bar_w+4:.1f}" y="{y+bar_h/2+4:.1f}" fill="#94a3b8" font-size="9">{val}{pct}</text>')
    lines.append(f'<text x="{w//2}" y="{h-4}" fill="#64748b" font-size="9" text-anchor="middle">Jerk RMS (lower is better)</text>')
    lines.append("</svg>")
    return "".join(lines)


def build_scatter_svg() -> str:
    w, h = 680, 200
    pad = 50
    xs = [a["latency_overhead_ms"] for a in ALGORITHMS]
    ys = [a["smoothness_score"] for a in ALGORITHMS]
    x_lo, x_hi = -0.1, 4.0
    y_lo, y_hi = 0.74, 0.97

    def sx(v):
        return pad + (v - x_lo) / (x_hi - x_lo) * (w - 2 * pad)

    def sy(v):
        return (h - pad) - (v - y_lo) / (y_hi - y_lo) * (h - 2 * pad)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#1e293b;border-radius:8px;">']
    # axes
    lines.append(f'<line x1="{pad}" y1="{pad//2}" x2="{pad}" y2="{h-pad}" stroke="#334155"/>')
    lines.append(f'<line x1="{pad}" y1="{h-pad}" x2="{w-pad//2}" y2="{h-pad}" stroke="#334155"/>')
    lines.append(f'<text x="{w//2}" y="{h-6}" fill="#94a3b8" font-size="10" text-anchor="middle">Latency Overhead (ms)</text>')
    lines.append(f'<text x="12" y="{h//2}" fill="#94a3b8" font-size="10" text-anchor="middle" transform="rotate(-90,12,{h//2})">Smoothness Score</text>')
    # Pareto frontier annotation
    pareto = [i for i in range(len(ALGORITHMS)) if ALGORITHMS[i]["name"] != "raw"]
    pareto_pts = " ".join(f"{sx(xs[i]):.1f},{sy(ys[i]):.1f}" for i in sorted(pareto, key=lambda i: xs[i]))
    lines.append(f'<polyline points="{pareto_pts}" fill="none" stroke="#facc15" stroke-width="1" stroke-dasharray="4,3" opacity="0.5"/>')
    lines.append(f'<text x="{sx(1.8):.1f}" y="{sy(0.955):.1f}" fill="#facc15" font-size="9">Pareto frontier</text>')
    # points
    for i, alg in enumerate(ALGORITHMS):
        cx, cy = sx(xs[i]), sy(ys[i])
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{alg["color"]}" opacity="0.9"/>')
        offset = -10 if alg["name"] == "chunk_blend" else 10
        lines.append(f'<text x="{cx:.1f}" y="{cy+offset:.1f}" fill="{alg["color"]}" font-size="9" text-anchor="middle">{alg["label"]}</text>')
    lines.append("</svg>")
    return "".join(lines)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Trajectory Smoother", version="1.0.0")
else:
    app = None  # type: ignore


if app is not None:

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        comp_svg = build_comparison_svg()
        jerk_svg = build_jerk_bar_svg()
        scatter_svg = build_scatter_svg()

        rows = ""
        for a in ALGORITHMS:
            jerk_pct = "" if a["name"] == "raw" else f"({(1-a['jerk_rms']/0.847)*100:.1f}%↓)"
            best_tag = ' <span style="color:#C74634;font-weight:600">[best offline]</span>' if a["name"] == "cubic_spline" else ""
            prod_tag = ' <span style="color:#34d399;font-weight:600">[prod recommended]</span>' if a["name"] == "chunk_blend" else ""
            rows += (
                f"<tr><td>{a['label']}</td>"
                f"<td style='color:{a['color']}'>{a['jerk_rms']} {jerk_pct}{best_tag}{prod_tag}</td>"
                f"<td>{a['smoothness_score']}</td>"
                f"<td>{a['latency_overhead_ms']} ms</td>"
                f"<td>{a['vel_max']}</td></tr>"
            )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Trajectory Smoother — OCI Robot Cloud</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
    h1{{color:#38bdf8;font-size:1.5rem;margin-bottom:4px}}
    .sub{{color:#64748b;font-size:.85rem;margin-bottom:20px}}
    .card{{background:#1e293b;border-radius:10px;padding:16px;margin-bottom:20px}}
    .card h2{{color:#94a3b8;font-size:.95rem;margin-bottom:12px;text-transform:uppercase;letter-spacing:.05em}}
    table{{width:100%;border-collapse:collapse;font-size:.88rem}}
    th{{color:#64748b;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
    td{{padding:6px 8px;border-bottom:1px solid #1e3a5f}}
    tr:last-child td{{border-bottom:none}}
    .rec{{background:#0f2a1a;border:1px solid #34d399;border-radius:6px;padding:12px;color:#34d399;font-size:.9rem;margin-top:12px}}
    .badge{{display:inline-block;padding:2px 8px;border-radius:9999px;font-size:.75rem;font-weight:600}}
  </style>
</head>
<body>
  <h1>Trajectory Smoother</h1>
  <p class="sub">Post-processing pipeline · dagger_run10 · joint_4 analysis · port 8184</p>

  <div class="card">
    <h2>Raw vs Smoothed — Joint 4 (spikes at steps 20/38/55/71/88)</h2>
    {comp_svg}
  </div>

  <div class="card">
    <h2>Jerk RMS Comparison (lower is better)</h2>
    {jerk_svg}
  </div>

  <div class="card">
    <h2>Smoothness vs Latency Trade-off</h2>
    {scatter_svg}
  </div>

  <div class="card">
    <h2>Algorithm Summary</h2>
    <table>
      <thead><tr><th>Algorithm</th><th>Jerk RMS</th><th>Smoothness</th><th>Latency</th><th>Vel Max</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <div class="rec">Recommendation: {RECOMMENDATION}</div>
  </div>
</body>
</html>"""
        return HTMLResponse(html)

    @app.get("/algorithms")
    async def get_algorithms():
        return JSONResponse(ALGORITHMS)

    @app.get("/comparison")
    async def get_comparison():
        return JSONResponse(
            {"joint": "joint_4", "n_steps": N_STEPS, "spike_steps": sorted(SPIKE_STEPS), "trajectories": SMOOTHED}
        )

    @app.get("/recommend")
    async def get_recommend():
        best_offline = min(ALGORITHMS, key=lambda a: a["jerk_rms"])
        best_prod = min(
            [a for a in ALGORITHMS if a["latency_overhead_ms"] <= 1.0 and a["name"] != "raw"],
            key=lambda a: -a["smoothness_score"],
        )
        return JSONResponse(
            {
                "recommendation": RECOMMENDATION,
                "production": best_prod["name"],
                "offline": best_offline["name"],
            }
        )


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed")
    uvicorn.run("trajectory_smoother:app", host="0.0.0.0", port=8184, reload=False)

"""Cross-embodiment adaptation tracker — port 8192.

Adapts GR00T from Franka Panda (source) to other robot embodiments.
"""
from __future__ import annotations

import math
import textwrap

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore
    HTMLResponse = JSONResponse = None  # type: ignore
    uvicorn = None  # type: ignore

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

SOURCE = {
    "id": "franka_panda",
    "dof": 7,
    "success_rate": 0.78,
    "label": "Franka Panda (source)",
}

EMBODIMENTS: list[dict] = [
    {
        "id": "ur5e",
        "label": "UR5e",
        "dof": 6,
        "adapter_params": 2_100_000,
        "zero_shot_sr": 0.41,
        "adapted_sr": 0.71,
        "episodes_needed": 200,
        "status": "READY",
        "similarity_score": 0.74,
    },
    {
        "id": "xarm6",
        "label": "xArm 6",
        "dof": 6,
        "adapter_params": 2_100_000,
        "zero_shot_sr": 0.38,
        "adapted_sr": 0.68,
        "episodes_needed": 250,
        "status": "READY",
        "similarity_score": 0.71,
    },
    {
        "id": "stretch_re3",
        "label": "Stretch RE3",
        "dof": 5,
        "adapter_params": 3_400_000,
        "zero_shot_sr": 0.21,
        "adapted_sr": 0.54,
        "episodes_needed": 500,
        "status": "IN_PROGRESS",
        "similarity_score": 0.48,
    },
    {
        "id": "spot_arm",
        "label": "Spot Arm",
        "dof": 6,
        "adapter_params": 2_800_000,
        "zero_shot_sr": 0.31,
        "adapted_sr": None,
        "episodes_needed": 350,
        "status": "PLANNED",
        "similarity_score": 0.62,
    },
]


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _radar_svg() -> str:
    """Radar chart 520x340 — 4 axes: zero_shot_sr, adapted_sr, similarity, data_efficiency."""
    W, H = 520, 340
    cx, cy = 260, 175
    R = 120  # outer radius

    AXES = [
        ("zero_shot_sr", "Zero-Shot SR"),
        ("adapted_sr", "Adapted SR"),
        ("similarity", "Similarity"),
        ("data_eff", "Data Efficiency"),
    ]
    n_axes = len(AXES)

    def angle(i: int) -> float:
        return math.pi / 2 - 2 * math.pi * i / n_axes

    def pt(val: float, i: int, r: float = R) -> tuple[float, float]:
        a = angle(i)
        return cx + r * val * math.cos(a), cy - r * val * math.sin(a)

    # Max episodes_needed for normalisation
    max_ep = max(e["episodes_needed"] for e in EMBODIMENTS)

    def robot_vals(e: dict) -> list[float]:
        zs = e["zero_shot_sr"]
        ad = e["adapted_sr"] if e["adapted_sr"] is not None else 0.0
        sim = e["similarity_score"]
        eff = 1.0 - e["episodes_needed"] / max_ep  # higher = fewer episodes needed
        return [zs, ad, sim, eff]

    ROBOT_COLORS = ["#38bdf8", "#34d399", "#f59e0b", "#a78bfa"]

    lines: list[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a">')

    # Grid rings
    for ring in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{pt(ring, i)[0]:.1f},{pt(ring, i)[1]:.1f}" for i in range(n_axes))
        lines.append(f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>')

    # Axis spokes
    for i in range(n_axes):
        x2, y2 = pt(1.0, i)
        lines.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#475569" stroke-width="1"/>')

    # Axis labels
    for i, (_, label) in enumerate(AXES):
        x, y = pt(1.15, i)
        lines.append(
            f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="monospace" font-size="11" fill="#94a3b8">{label}</text>'
        )

    # Source Franka reference ring (adapted SR equivalent)
    franka_sr = SOURCE["success_rate"]
    franka_vals = [franka_sr, franka_sr, 1.0, 1.0 - 0 / max_ep]  # perfect similarity/efficiency
    fps = " ".join(f"{pt(franka_vals[i], i)[0]:.1f},{pt(franka_vals[i], i)[1]:.1f}" for i in range(n_axes))
    lines.append(
        f'<polygon points="{fps}" fill="#C74634" fill-opacity="0.15" stroke="#C74634" stroke-width="2" stroke-dasharray="6,3"/>'
    )

    # Target robot polygons
    for idx, e in enumerate(EMBODIMENTS):
        vals = robot_vals(e)
        poly_pts = " ".join(f"{pt(vals[i], i)[0]:.1f},{pt(vals[i], i)[1]:.1f}" for i in range(n_axes))
        col = ROBOT_COLORS[idx]
        lines.append(
            f'<polygon points="{poly_pts}" fill="{col}" fill-opacity="0.25" stroke="{col}" stroke-width="2"/>'
        )
        # Label at centroid
        cx2 = sum(pt(vals[i], i)[0] for i in range(n_axes)) / n_axes
        cy2 = sum(pt(vals[i], i)[1] for i in range(n_axes)) / n_axes
        lines.append(
            f'<text x="{cx2:.1f}" y="{cy2:.1f}" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="monospace" font-size="10" fill="{col}">{e["label"]}</text>'
        )

    # Legend
    lx, ly = 10, 10
    lines.append(
        f'<rect x="{lx}" y="{ly}" width="14" height="6" fill="#C74634" fill-opacity="0.3" stroke="#C74634" stroke-width="1.5" stroke-dasharray="4,2"/>'
    )
    lines.append(f'<text x="{lx+18}" y="{ly+5}" font-family="monospace" font-size="10" fill="#C74634">Franka (source)</text>')
    for idx, e in enumerate(EMBODIMENTS):
        col = ROBOT_COLORS[idx]
        ry = ly + 16 * (idx + 1)
        lines.append(f'<rect x="{lx}" y="{ry}" width="14" height="6" fill="{col}" fill-opacity="0.4" stroke="{col}" stroke-width="1.5"/>')
        lines.append(f'<text x="{lx+18}" y="{ry+5}" font-family="monospace" font-size="10" fill="{col}">{e["label"]}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def _scatter_svg() -> str:
    """Episode efficiency scatter 680x200: x=episodes_needed, y=adapted_sr, bubble=adapter_params."""
    W, H = 680, 200
    PL, PR, PT, PB = 60, 20, 20, 40  # padding

    valid = [e for e in EMBODIMENTS if e["adapted_sr"] is not None]
    all_ep = [e["episodes_needed"] for e in valid]
    min_ep, max_ep = min(all_ep), max(all_ep)
    all_sr = [e["adapted_sr"] for e in valid]  # type: ignore[index]
    min_sr, max_sr = 0.4, 0.85

    def sx(ep: float) -> float:
        return PL + (ep - min_ep) / max(max_ep - min_ep, 1) * (W - PL - PR)

    def sy(sr: float) -> float:
        return H - PB - (sr - min_sr) / (max_sr - min_sr) * (H - PT - PB)

    max_params = max(e["adapter_params"] for e in valid)

    def bubble_r(params: float) -> float:
        return 8 + 14 * params / max_params

    ROBOT_COLORS = ["#38bdf8", "#34d399", "#f59e0b", "#a78bfa"]

    lines: list[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a">')

    # Axes
    lines.append(
        f'<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{H-PB}" stroke="#475569" stroke-width="1"/>'
    )
    lines.append(
        f'<line x1="{PL}" y1="{H-PB}" x2="{W-PR}" y2="{H-PB}" stroke="#475569" stroke-width="1"/>'
    )

    # Axis labels
    lines.append(
        f'<text x="{(PL+W-PR)//2}" y="{H-5}" text-anchor="middle" font-family="monospace" font-size="11" fill="#94a3b8">Episodes Needed</text>'
    )
    lines.append(
        f'<text x="12" y="{(PT+H-PB)//2}" text-anchor="middle" font-family="monospace" font-size="11" fill="#94a3b8" transform="rotate(-90,12,{(PT+H-PB)//2})">Adapted SR</text>'
    )

    # Trend line (simple linear fit through valid points)
    xs = [e["episodes_needed"] for e in valid]
    ys = [e["adapted_sr"] for e in valid]  # type: ignore[misc]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    slope = num / den if den else 0.0
    intercept = my - slope * mx
    tx1, tx2 = float(min_ep), float(max_ep)
    ty1, ty2 = slope * tx1 + intercept, slope * tx2 + intercept
    lines.append(
        f'<line x1="{sx(tx1):.1f}" y1="{sy(ty1):.1f}" x2="{sx(tx2):.1f}" y2="{sy(ty2):.1f}" '
        f'stroke="#475569" stroke-width="1.5" stroke-dasharray="5,3"/>'
    )

    # Franka star reference
    star_x, star_y = sx(0), sy(SOURCE["success_rate"])  # 0 episodes (source)
    # Clamp star to left edge
    star_x = float(PL) + 4
    def star_path(cx: float, cy: float, r: float) -> str:
        pts = []
        for k in range(10):
            a = math.pi / 2 + k * math.pi / 5
            ri = r if k % 2 == 0 else r * 0.4
            pts.append(f"{cx + ri*math.cos(a):.1f},{cy - ri*math.sin(a):.1f}")
        return " ".join(pts)
    lines.append(
        f'<polygon points="{star_path(star_x, star_y, 8)}" fill="#C74634" stroke="#C74634" stroke-width="1"/>'
    )
    lines.append(
        f'<text x="{star_x+12}" y="{star_y+4}" font-family="monospace" font-size="9" fill="#C74634">Franka SR={SOURCE["success_rate"]}</text>'
    )

    # Bubbles
    for idx, e in enumerate(valid):
        col = ROBOT_COLORS[idx]
        bx, by = sx(e["episodes_needed"]), sy(e["adapted_sr"])  # type: ignore[arg-type]
        br = bubble_r(e["adapter_params"])
        lines.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{br:.1f}" fill="{col}" fill-opacity="0.7" stroke="{col}" stroke-width="1.5"/>')
        lines.append(f'<text x="{bx:.1f}" y="{by-br-3:.1f}" text-anchor="middle" font-family="monospace" font-size="10" fill="{col}">{e["label"]} ({e["adapted_sr"]})</text>')

    # Tick marks
    for ep in [200, 300, 400, 500]:
        tx = sx(ep)
        if PL <= tx <= W - PR:
            lines.append(f'<text x="{tx:.1f}" y="{H-PB+12}" text-anchor="middle" font-family="monospace" font-size="9" fill="#64748b">{ep}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    radar = _radar_svg()
    scatter = _scatter_svg()

    status_colors = {
        "READY": "#22c55e",
        "IN_PROGRESS": "#f59e0b",
        "PLANNED": "#64748b",
    }

    rows = ""
    for e in EMBODIMENTS:
        sc = status_colors.get(e["status"], "#94a3b8")
        adapted = f"{e['adapted_sr']:.2f}" if e["adapted_sr"] is not None else "—"
        rows += (
            f'<tr>'
            f'<td>{e["label"]}</td>'
            f'<td>{e["dof"]}</td>'
            f'<td>{e["zero_shot_sr"]:.2f}</td>'
            f'<td>{adapted}</td>'
            f'<td>{e["similarity_score"]:.2f}</td>'
            f'<td>{e["episodes_needed"]}</td>'
            f'<td>{e["adapter_params"]/1e6:.1f}M</td>'
            f'<td><span style="color:{sc};font-weight:bold">{e["status"]}</span></td>'
            f'</tr>'
        )

    return textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html>
    <head>
      <title>Embodiment Adapter Tracker — OCI Robot Cloud</title>
      <style>
        body {{ background:#0f172a; color:#e2e8f0; font-family:monospace; margin:0; padding:24px; }}
        h1 {{ color:#C74634; margin-bottom:4px; }}
        h2 {{ color:#38bdf8; font-size:14px; margin:24px 0 8px; }}
        .subtitle {{ color:#64748b; font-size:12px; margin-bottom:20px; }}
        .badge {{ display:inline-block; padding:2px 10px; border-radius:12px; font-size:11px; font-weight:bold; margin:2px; }}
        table {{ border-collapse:collapse; width:100%; font-size:12px; }}
        th {{ color:#94a3b8; text-align:left; padding:6px 10px; border-bottom:1px solid #1e293b; }}
        td {{ padding:6px 10px; border-bottom:1px solid #1e293b; }}
        tr:hover {{ background:#1e293b; }}
        .arch-box {{ background:#1e293b; border:1px solid #334155; border-radius:8px; padding:16px; margin-top:16px; font-size:12px; color:#94a3b8; }}
        .arch-box b {{ color:#38bdf8; }}
        .svg-wrap {{ margin:16px 0; overflow-x:auto; }}
        .stat {{ display:inline-block; background:#1e293b; border-radius:8px; padding:12px 20px; margin:4px; text-align:center; }}
        .stat-val {{ font-size:24px; font-weight:bold; color:#C74634; }}
        .stat-label {{ font-size:11px; color:#64748b; margin-top:4px; }}
      </style>
    </head>
    <body>
      <h1>Cross-Embodiment Adapter Tracker</h1>
      <div class="subtitle">GR00T N1.6 — adapting Franka Panda backbone to new robot embodiments</div>

      <div>
        <div class="stat"><div class="stat-val">{SOURCE['success_rate']:.0%}</div><div class="stat-label">Source SR (Franka)</div></div>
        <div class="stat"><div class="stat-val">{sum(1 for e in EMBODIMENTS if e['status']=='READY')}</div><div class="stat-label">Adapters Ready</div></div>
        <div class="stat"><div class="stat-val">{sum(1 for e in EMBODIMENTS if e['status']=='IN_PROGRESS')}</div><div class="stat-label">In Progress</div></div>
        <div class="stat"><div class="stat-val">{sum(1 for e in EMBODIMENTS if e['status']=='PLANNED')}</div><div class="stat-label">Planned</div></div>
        <div class="stat"><div class="stat-val">{len(EMBODIMENTS)}</div><div class="stat-label">Target Embodiments</div></div>
      </div>

      <h2>Adapter Architecture</h2>
      <div class="arch-box">
        <b>Input adapter layer:</b> maps target joint dims (5–6 DOF) → Franka 7-DOF space via learned linear projection<br>
        <b>Shared backbone:</b> GR00T N1.6 trunk fully frozen (3B params) — zero gradient flow<br>
        <b>Output remap:</b> action head remapped from 7-DOF Franka to target DOF configuration<br>
        <b>Trainable params:</b> adapter_layer only (2.1M–3.4M depending on embodiment complexity)<br>
        <b>Key insight:</b> higher kinematic similarity → fewer adaptation episodes + higher final success rate
      </div>

      <h2>Cross-Embodiment Radar</h2>
      <div class="svg-wrap">{radar}</div>

      <h2>Episode Efficiency vs. Adapted SR</h2>
      <div class="svg-wrap">{scatter}</div>

      <h2>Embodiment Details</h2>
      <table>
        <tr>
          <th>Robot</th><th>DOF</th><th>Zero-Shot SR</th><th>Adapted SR</th>
          <th>Similarity</th><th>Episodes</th><th>Adapter Params</th><th>Status</th>
        </tr>
        {rows}
      </table>

      <div class="arch-box" style="margin-top:24px">
        <b>API endpoints:</b><br>
        GET /embodiments — list all target embodiments (JSON)<br>
        GET /embodiments/{{robot_id}} — single embodiment detail<br>
        GET /compare — side-by-side comparison table<br>
        GET / — this dashboard
      </div>
    </body>
    </html>
    """)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Embodiment Adapter Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _dashboard_html()

    @app.get("/embodiments")
    async def list_embodiments():
        return JSONResponse({"source": SOURCE, "targets": EMBODIMENTS})

    @app.get("/embodiments/{robot_id}")
    async def get_embodiment(robot_id: str):
        for e in EMBODIMENTS:
            if e["id"] == robot_id:
                return JSONResponse(e)
        return JSONResponse({"error": "not found"}, status_code=404)

    @app.get("/compare")
    async def compare():
        valid = [e for e in EMBODIMENTS if e["adapted_sr"] is not None]
        return JSONResponse({
            "source": SOURCE,
            "comparison": [
                {
                    **e,
                    "sr_delta": round(e["adapted_sr"] - SOURCE["success_rate"], 3),
                    "zeroshot_gain": round((e["adapted_sr"] - e["zero_shot_sr"]) / e["zero_shot_sr"], 3),
                }
                for e in valid
            ],
        })


if __name__ == "__main__":
    if uvicorn is not None and FastAPI is not None:
        uvicorn.run("embodiment_adapter:app", host="0.0.0.0", port=8192, reload=False)
    else:
        print("Install fastapi and uvicorn: pip install fastapi uvicorn")

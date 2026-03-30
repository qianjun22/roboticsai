"""Policy Rollout State Visualizer — OCI Robot Cloud — port 8206.

Shows robot state at each step for a single representative episode
(847 steps, cube_lift SUCCESS). Phases: reach / grasp / lift.
"""

import math
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None  # type: ignore
    HTMLResponse = None  # type: ignore
    JSONResponse = None  # type: ignore
    uvicorn = None  # type: ignore

# ---------------------------------------------------------------------------
# Episode data generation
# ---------------------------------------------------------------------------
TOTAL_STEPS = 847
REACH_END = 420
GRASP_END = 620


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _generate_episode():
    """Return list of dicts, one per step, with all 8 state variables."""
    steps = []
    for t in range(TOTAL_STEPS):
        frac = t / (TOTAL_STEPS - 1)
        reach_frac = _clamp(t / REACH_END, 0.0, 1.0)
        grasp_frac = _clamp((t - REACH_END) / (GRASP_END - REACH_END), 0.0, 1.0)
        lift_frac = _clamp((t - GRASP_END) / (TOTAL_STEPS - GRASP_END), 0.0, 1.0)

        # End-effector trajectory
        ee_x = 0.10 + 0.25 * reach_frac + 0.02 * math.sin(t * 0.05)
        ee_y = 0.05 + 0.15 * reach_frac + 0.01 * math.cos(t * 0.07)
        # z descends to cube during reach, holds during grasp, rises during lift
        if t < REACH_END:
            ee_z = 0.40 - 0.20 * reach_frac
        elif t < GRASP_END:
            ee_z = 0.20
        else:
            ee_z = 0.20 + 0.25 * lift_frac

        # Gripper: open during reach, closes during grasp, stays closed
        if t < REACH_END:
            gripper_width = 0.08
        elif t < GRASP_END:
            gripper_width = round(0.08 * (1.0 - grasp_frac), 4)
        else:
            gripper_width = 0.0

        # Cube position: stationary until grasp, then follows ee
        cube_x = 0.35 + 0.005 * math.sin(t * 0.02)
        cube_y = 0.20 + 0.003 * math.cos(t * 0.03)
        if t < GRASP_END:
            cube_z = 0.10
        else:
            cube_z = round(0.10 + 0.25 * lift_frac, 4)

        # Contact force: 0 until grasp, ramp up, steady ~8 N during lift
        if t < REACH_END:
            contact_force = 0.0
        elif t < GRASP_END:
            contact_force = round(8.0 * grasp_frac, 3)
        else:
            contact_force = round(8.0 + 0.5 * math.sin(t * 0.1), 3)

        steps.append({
            "step": t,
            "ee_x": round(ee_x, 4),
            "ee_y": round(ee_y, 4),
            "ee_z": round(ee_z, 4),
            "gripper_width": gripper_width,
            "cube_x": round(cube_x, 4),
            "cube_y": round(cube_y, 4),
            "cube_z": cube_z,
            "contact_force": contact_force,
        })
    return steps


EPISODE = _generate_episode()

PHASES = [
    {"name": "Reach",  "start": 0,        "end": REACH_END - 1, "duration": REACH_END,             "key_event": "EE approaches cube position"},
    {"name": "Grasp",  "start": REACH_END, "end": GRASP_END - 1, "duration": GRASP_END - REACH_END, "key_event": "Gripper closes, contact force rises"},
    {"name": "Lift",   "start": GRASP_END, "end": TOTAL_STEPS - 1, "duration": TOTAL_STEPS - GRASP_END, "key_event": "Cube z rises with EE (SUCCESS)"},
]

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------
W, H_MULTI = 680, 320
H_OVERLAY = 180
PAD = {"l": 54, "r": 16, "t": 14, "b": 28}


def _normalise(values):
    lo, hi = min(values), max(values)
    span = hi - lo or 1e-9
    return [(v - lo) / span for v in values], lo, hi


def _polyline(xs_norm, ys_norm, x0, y0, pw, ph, color, stroke_w=1.5):
    pts = " ".join(
        f"{x0 + n * pw:.1f},{y0 + ph - ys_norm[i] * ph:.1f}"
        for i, n in enumerate(xs_norm)
    )
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linejoin="round"/>'


def _phase_rects(x0, y0, pw, ph, opacity=0.12):
    colors = {"Reach": "#38bdf8", "Grasp": "#f59e0b", "Lift": "#22c55e"}
    out = []
    for ph_info in PHASES:
        x1 = x0 + ph_info["start"] / TOTAL_STEPS * pw
        x2 = x0 + (ph_info["end"] + 1) / TOTAL_STEPS * pw
        out.append(
            f'<rect x="{x1:.1f}" y="{y0:.1f}" width="{x2-x1:.1f}" height="{ph:.1f}" '
            f'fill="{colors[ph_info["name"]]}" opacity="{opacity}"/>'
        )
    return "".join(out)


def _axis_labels(x0, y0, pw, ph, lo, hi, label, color):
    out = []
    for frac in [0, 0.5, 1.0]:
        val = lo + frac * (hi - lo)
        y = y0 + ph - frac * ph
        out.append(
            f'<text x="{x0 - 4}" y="{y:.1f}" fill="#94a3b8" font-size="8" text-anchor="end" dominant-baseline="middle">{val:.2f}</text>'
        )
    out.append(
        f'<text x="{x0 - 36}" y="{y0 + ph/2:.1f}" fill="{color}" font-size="9" text-anchor="middle" '
        f'transform="rotate(-90 {x0-36} {y0+ph/2:.1f})">{label}</text>'
    )
    return "".join(out)


def build_multivariable_svg():
    """4 stacked subplots: ee_xyz, gripper, cube_z, contact_force."""
    # Sample every 4th step for polyline performance
    sample = EPISODE[::4]
    steps_norm = [s["step"] / TOTAL_STEPS for s in sample]

    subplots = [
        {"vars": [("ee_x", "#38bdf8"), ("ee_y", "#7dd3fc"), ("ee_z", "#0ea5e9")], "label": "EE pos (m)"},
        {"vars": [("gripper_width", "#f59e0b")], "label": "Gripper (m)"},
        {"vars": [("cube_z", "#22c55e")], "label": "Cube Z (m)"},
        {"vars": [("contact_force", "#C74634")], "label": "Force (N)"},
    ]

    n_sub = len(subplots)
    avail_h = H_MULTI - PAD["t"] - PAD["b"] - (n_sub - 1) * 8
    sub_h = avail_h // n_sub
    pw = W - PAD["l"] - PAD["r"]
    x0 = PAD["l"]

    svgs = []
    svgs.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H_MULTI}" '
        f'style="background:#0f172a;border-radius:8px;">'
    )
    # Title
    svgs.append(
        f'<text x="{W//2}" y="10" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="bold">'
        f'Episode State — 847 Steps — cube_lift SUCCESS</text>'
    )
    # Phase legend
    legend_items = [("Reach", "#38bdf8"), ("Grasp", "#f59e0b"), ("Lift", "#22c55e")]
    for i, (name, col) in enumerate(legend_items):
        lx = W - 160 + i * 52
        svgs.append(f'<rect x="{lx}" y="3" width="10" height="8" fill="{col}" opacity="0.7"/>')
        svgs.append(f'<text x="{lx+13}" y="10" fill="#94a3b8" font-size="8">{name}</text>')

    for idx, sp in enumerate(subplots):
        y0 = PAD["t"] + idx * (sub_h + 8)
        # Phase background
        svgs.append(_phase_rects(x0, y0, pw, sub_h))
        # Border
        svgs.append(
            f'<rect x="{x0}" y="{y0}" width="{pw}" height="{sub_h}" '
            f'fill="none" stroke="#1e293b" stroke-width="1"/>'
        )
        # Collect all values for normalisation
        all_vals = [s[v] for s in sample for v, _ in sp["vars"]]
        lo_all = min(all_vals)
        hi_all = max(all_vals)
        span = hi_all - lo_all or 1e-9

        for var_name, color in sp["vars"]:
            vals = [s[var_name] for s in sample]
            ys_norm = [(v - lo_all) / span for v in vals]
            svgs.append(_polyline(steps_norm, ys_norm, x0, y0, pw, sub_h, color))

        svgs.append(_axis_labels(x0, y0, pw, sub_h, lo_all, hi_all, sp["label"], sp["vars"][0][1]))

        # Step axis (bottom of last subplot only)
        if idx == n_sub - 1:
            for frac in [0, 0.25, 0.5, 0.75, 1.0]:
                step_val = int(frac * TOTAL_STEPS)
                xp = x0 + frac * pw
                svgs.append(
                    f'<text x="{xp:.1f}" y="{y0 + sub_h + 10}" fill="#64748b" '
                    f'font-size="8" text-anchor="middle">{step_val}</text>'
                )

    svgs.append("</svg>")
    return "".join(svgs)


def build_overlay_svg():
    """ee_z vs cube_z height correlation overlay."""
    sample = EPISODE[::4]
    steps_norm = [s["step"] / TOTAL_STEPS for s in sample]
    pw = W - PAD["l"] - PAD["r"]
    ph = H_OVERLAY - PAD["t"] - PAD["b"]
    x0, y0 = PAD["l"], PAD["t"]

    ee_z_vals = [s["ee_z"] for s in sample]
    cube_z_vals = [s["cube_z"] for s in sample]
    combined = ee_z_vals + cube_z_vals
    lo, hi = min(combined), max(combined)
    span = hi - lo or 1e-9

    ee_norm = [(v - lo) / span for v in ee_z_vals]
    cube_norm = [(v - lo) / span for v in cube_z_vals]

    svgs = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H_OVERLAY}" '
        f'style="background:#0f172a;border-radius:8px;">',
        f'<text x="{W//2}" y="10" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="bold">'
        f'EE-Z vs Cube-Z Height Correlation</text>',
        _phase_rects(x0, y0, pw, ph),
        f'<rect x="{x0}" y="{y0}" width="{pw}" height="{ph}" fill="none" stroke="#1e293b" stroke-width="1"/>',
        _polyline(steps_norm, ee_norm, x0, y0, pw, ph, "#0ea5e9", 2.0),
        _polyline(steps_norm, cube_norm, x0, y0, pw, ph, "#22c55e", 2.0),
        # Annotation at grasp
        f'<line x1="{x0 + GRASP_END/TOTAL_STEPS*pw:.1f}" y1="{y0}" x1="{x0 + GRASP_END/TOTAL_STEPS*pw:.1f}" '
        f'x2="{x0 + GRASP_END/TOTAL_STEPS*pw:.1f}" y2="{y0+ph}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>',
        f'<text x="{x0 + GRASP_END/TOTAL_STEPS*pw + 3:.1f}" y="{y0+12}" fill="#f59e0b" font-size="8">grasp</text>',
        # Legend
        f'<line x1="{W-100}" y1="12" x2="{W-85}" y2="12" stroke="#0ea5e9" stroke-width="2"/>',
        f'<text x="{W-82}" y="15" fill="#94a3b8" font-size="8">EE-Z</text>',
        f'<line x1="{W-55}" y1="12" x2="{W-40}" y2="12" stroke="#22c55e" stroke-width="2"/>',
        f'<text x="{W-37}" y="15" fill="#94a3b8" font-size="8">Cube-Z</text>',
        _axis_labels(x0, y0, pw, ph, lo, hi, "Z (m)", "#0ea5e9"),
        "</svg>"
    ]
    return "".join(svgs)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Rollout Visualizer — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Inter', sans-serif; padding: 24px; }}
  h1 {{ color: #C74634; font-size: 1.4rem; margin-bottom: 4px; }}
  .sub {{ color: #64748b; font-size: 0.85rem; margin-bottom: 20px; }}
  .card {{ background: #1e293b; border-radius: 10px; padding: 16px; margin-bottom: 18px; }}
  .card h2 {{ font-size: 0.95rem; color: #38bdf8; margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ background: #0f172a; color: #94a3b8; padding: 6px 10px; text-align: left; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #0f172a; }}
  tr:last-child td {{ border-bottom: none; }}
  .reach {{ color: #38bdf8; }} .grasp {{ color: #f59e0b; }} .lift {{ color: #22c55e; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }}
  .badge-success {{ background: #14532d; color: #4ade80; }}
  .api {{ font-size: 0.78rem; color: #475569; margin-top: 12px; }}
  .api a {{ color: #38bdf8; text-decoration: none; }}
  svg {{ max-width: 100%; }}
</style>
</head>
<body>
<h1>Policy Rollout State Visualizer</h1>
<div class="sub">OCI Robot Cloud &mdash; Port 8206 &mdash; Single representative episode</div>

<div class="card">
  <h2>Episode Summary &nbsp; <span class="badge badge-success">cube_lift SUCCESS</span></h2>
  <table>
    <tr><th>Phase</th><th>Steps</th><th>Duration</th><th>Key Event</th></tr>
    {phase_rows}
  </table>
</div>

<div class="card">
  <h2>Multi-Variable State Time Series</h2>
  {multi_svg}
</div>

<div class="card">
  <h2>EE-Z vs Cube-Z Height Correlation</h2>
  {overlay_svg}
</div>

<div class="api">
  API endpoints:
  <a href="/episode">/episode</a> &nbsp;
  <a href="/phases">/phases</a> &nbsp;
  <a href="/variables/ee_z">/variables/ee_z</a>
</div>
</body></html>
"""


def _phase_rows_html():
    colors = {"Reach": "reach", "Grasp": "grasp", "Lift": "lift"}
    rows = []
    for ph in PHASES:
        cls = colors[ph["name"]]
        rows.append(
            f'<tr><td class="{cls}">{ph["name"]}</td>'
            f'<td>{ph["start"]}–{ph["end"]}</td>'
            f'<td>{ph["duration"]} steps</td>'
            f'<td>{ph["key_event"]}</td></tr>'
        )
    return "".join(rows)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
if FastAPI is not None:
    app = FastAPI(title="Rollout Visualizer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        html = DASHBOARD_HTML.format(
            phase_rows=_phase_rows_html(),
            multi_svg=build_multivariable_svg(),
            overlay_svg=build_overlay_svg(),
        )
        return HTMLResponse(html)

    @app.get("/episode")
    async def episode():
        return JSONResponse({"total_steps": TOTAL_STEPS, "result": "SUCCESS", "task": "cube_lift", "steps": EPISODE})

    @app.get("/phases")
    async def phases():
        return JSONResponse({"phases": PHASES})

    @app.get("/variables/{var_name}")
    async def variable(var_name: str):
        allowed = {"ee_x", "ee_y", "ee_z", "gripper_width", "cube_x", "cube_y", "cube_z", "contact_force"}
        if var_name not in allowed:
            return JSONResponse({"error": f"Unknown variable '{var_name}'. Valid: {sorted(allowed)}"}, status_code=404)
        return JSONResponse({
            "variable": var_name,
            "total_steps": TOTAL_STEPS,
            "values": [s[var_name] for s in EPISODE],
        })


if __name__ == "__main__":
    if uvicorn is None:
        print("uvicorn not installed — run: pip install fastapi uvicorn")
    else:
        uvicorn.run("rollout_visualizer:app", host="0.0.0.0", port=8206, reload=False)

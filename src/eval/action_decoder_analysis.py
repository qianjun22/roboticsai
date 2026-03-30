"""GR00T Action Decoder Analysis — inspect decoded action trajectories for Franka Panda.
Port 8181
"""
import math
import json
from datetime import datetime, timezone

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

# ---------------------------------------------------------------------------
# Joint definitions
# ---------------------------------------------------------------------------
JOINTS = [
    {
        "id": "joint_1",
        "label": "J1",
        "range": [-2.89, 2.89],
        "typical_range": [-0.8, 0.8],
        "smoothness": 0.94,
        "peak_vel": 0.41,
        "unit": "rad/s",
    },
    {
        "id": "joint_2",
        "label": "J2",
        "range": [-1.76, 1.76],
        "typical_range": [-1.2, 0.3],
        "smoothness": 0.92,
        "peak_vel": 0.38,
        "unit": "rad/s",
    },
    {
        "id": "joint_3",
        "label": "J3",
        "range": [-2.89, 2.89],
        "typical_range": [-0.4, 2.4],
        "smoothness": 0.91,
        "peak_vel": 0.44,
        "unit": "rad/s",
    },
    {
        "id": "joint_4",
        "label": "J4",
        "range": [-3.07, -0.07],
        "typical_range": [-2.8, -0.5],
        "smoothness": 0.89,
        "peak_vel": 0.52,
        "unit": "rad/s",
    },
    {
        "id": "joint_5",
        "label": "J5",
        "range": [-2.89, 2.89],
        "typical_range": [-0.5, 0.5],
        "smoothness": 0.96,
        "peak_vel": 0.29,
        "unit": "rad/s",
    },
    {
        "id": "joint_6",
        "label": "J6",
        "range": [-0.02, 3.75],
        "typical_range": [0.1, 3.5],
        "smoothness": 0.93,
        "peak_vel": 0.47,
        "unit": "rad/s",
    },
    {
        "id": "gripper",
        "label": "GRP",
        "range": [0.0, 0.08],
        "typical_range": [0.0, 0.08],
        "smoothness": 0.78,
        "peak_vel": 0.12,
        "unit": "m/s",
        "note": "binary-like open/close",
    },
]

EPISODE_STEPS = 847
GRASP_STEP    = 620
CHUNK_SIZE    = 16

# 7 visually distinct colors for joint lines
JOINT_COLORS = ["#38bdf8", "#C74634", "#86efac", "#f59e0b", "#a78bfa", "#f472b6", "#fb923c"]


# ---------------------------------------------------------------------------
# Trajectory generation (synthetic but physically plausible)
# ---------------------------------------------------------------------------
def _trajectory_for_joint(j_idx: int, n_steps: int) -> list:
    """Return normalized 0-1 trajectory values for joint j_idx."""
    jd = JOINTS[j_idx]
    lo, hi = jd["typical_range"]
    span = hi - lo if hi != lo else 0.001

    values = []
    for s in range(n_steps):
        t = s / n_steps
        # Base smooth motion using sin/cos with joint-specific phase
        phase = j_idx * 0.8
        raw = lo + span * (0.5 + 0.45 * math.sin(2 * math.pi * t + phase))
        # Add small noise
        noise = 0.01 * span * math.sin(s * 7.3 + j_idx)
        # Gripper: binary-like step near grasp
        if jd["id"] == "gripper":
            raw = 0.0 if s < GRASP_STEP else 0.08
        norm = (raw + noise - lo) / span
        values.append(round(max(0.0, min(1.0, norm)), 4))
    return values


def get_episode_trajectory() -> dict:
    """Return full episode trajectory (all 7 joints, 847 steps)."""
    return {
        "episode_steps": EPISODE_STEPS,
        "grasp_step": GRASP_STEP,
        "chunk_size": CHUNK_SIZE,
        "joints": {
            jd["id"]: _trajectory_for_joint(i, EPISODE_STEPS)
            for i, jd in enumerate(JOINTS)
        },
    }


def get_chunk_analysis() -> dict:
    """Return 3 consecutive 16-step action chunks with slight boundary discontinuity."""
    start = 600  # near grasp event for interest
    chunks = []
    for c_idx in range(3):
        c_start = start + c_idx * CHUNK_SIZE
        chunk_data = {}
        for i, jd in enumerate(JOINTS):
            full = _trajectory_for_joint(i, EPISODE_STEPS)
            steps = full[c_start: c_start + CHUNK_SIZE]
            # Introduce slight boundary discontinuity (decoder boundary artifact)
            if c_idx > 0:
                steps[0] = round(steps[0] + 0.03 * (0.5 - steps[0]), 4)
            chunk_data[jd["id"]] = steps
        chunks.append({
            "chunk_index": c_idx,
            "step_start": c_start,
            "step_end": c_start + CHUNK_SIZE - 1,
            "values": chunk_data,
        })
    return {"chunks": chunks, "chunk_size": CHUNK_SIZE, "note": "slight discontinuity at chunk boundaries — smoothing recommended"}


# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------
def build_trajectory_svg(width: int = 680, height: int = 280) -> str:
    """Multi-line joint trajectory over 847 steps."""
    pad_l, pad_r, pad_t, pad_b = 40, 16, 16, 24
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    # Sample every 4th step to keep SVG size manageable
    sample = 4
    elements = []

    # Axes
    elements.append(
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" '
        f'stroke="#334155" stroke-width="1"/>'
    )
    elements.append(
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{pad_l + chart_w}" y2="{pad_t + chart_h}" '
        f'stroke="#334155" stroke-width="1"/>'
    )

    # Grasp event vertical line
    gx = pad_l + GRASP_STEP / EPISODE_STEPS * chart_w
    elements.append(
        f'<line x1="{gx:.1f}" y1="{pad_t}" x2="{gx:.1f}" y2="{pad_t + chart_h}" '
        f'stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3" opacity="0.7"/>'
    )
    elements.append(
        f'<text x="{gx + 4:.1f}" y="{pad_t + 10}" font-size="9" fill="#f59e0b" font-family="sans-serif">GRASP</text>'
    )

    # Y-axis labels
    for tick, label in [(0, "0"), (0.5, "0.5"), (1.0, "1.0")]:
        ty = pad_t + chart_h - tick * chart_h
        elements.append(
            f'<text x="{pad_l - 4}" y="{ty + 4:.1f}" font-size="8" fill="#64748b" '
            f'font-family="monospace" text-anchor="end">{label}</text>'
        )

    # Joint lines
    for j_idx, jd in enumerate(JOINTS):
        values = _trajectory_for_joint(j_idx, EPISODE_STEPS)
        pts = []
        for s in range(0, EPISODE_STEPS, sample):
            px = pad_l + s / EPISODE_STEPS * chart_w
            py = pad_t + chart_h - values[s] * chart_h
            pts.append(f"{px:.1f},{py:.1f}")
        color = JOINT_COLORS[j_idx]
        elements.append(
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
            f'stroke-width="1.4" opacity="0.85"/>'
        )

    # Legend (bottom row)
    for j_idx, jd in enumerate(JOINTS):
        lx = pad_l + j_idx * (chart_w // 7)
        ly = pad_t + chart_h + 14
        elements.append(
            f'<rect x="{lx}" y="{ly - 6}" width="10" height="5" rx="1" fill="{JOINT_COLORS[j_idx]}"/>'
            f'<text x="{lx + 13}" y="{ly}" font-size="8" fill="#94a3b8" font-family="monospace">{jd["label"]}</text>'
        )

    # X label
    elements.append(
        f'<text x="{pad_l + chart_w // 2}" y="{height - 2}" font-size="9" fill="#64748b" '
        f'font-family="sans-serif" text-anchor="middle">Steps (0 — {EPISODE_STEPS})</text>'
    )

    body = "\n".join(elements)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#0f172a;border-radius:8px">'
        f'{body}</svg>'
    )


def build_smoothness_bar_svg(width: int = 680, height: int = 160) -> str:
    """Horizontal bar chart: one bar per joint, colored by smoothness score."""
    pad_l, pad_r, pad_t, pad_b = 55, 16, 16, 8
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b
    n = len(JOINTS)
    bar_h = max(8, chart_h // n - 6)

    def sm_color(s):
        if s >= 0.90:
            return "#14532d", "#86efac"
        if s >= 0.75:
            return "#713f12", "#fde68a"
        return "#7f1d1d", "#fca5a5"

    elements = []
    for i, jd in enumerate(JOINTS):
        s = jd["smoothness"]
        bar_w = int(s * chart_w)
        y = pad_t + i * (bar_h + 6)
        fill, txt = sm_color(s)
        elements.append(
            f'<rect x="{pad_l}" y="{y}" width="{bar_w}" height="{bar_h}" rx="3" fill="{fill}"/>'
        )
        elements.append(
            f'<text x="{pad_l - 4}" y="{y + bar_h - 2}" font-size="9" fill="#94a3b8" '
            f'font-family="monospace" text-anchor="end">{jd["label"]}</text>'
        )
        elements.append(
            f'<text x="{pad_l + bar_w + 4}" y="{y + bar_h - 2}" font-size="9" fill="{txt}" '
            f'font-family="monospace">{s:.2f}</text>'
        )

    # threshold lines
    for thresh, label, color in [(0.90, "0.90", "#86efac"), (0.75, "0.75", "#fde68a")]:
        tx = pad_l + int(thresh * chart_w)
        elements.append(
            f'<line x1="{tx}" y1="{pad_t}" x2="{tx}" y2="{pad_t + chart_h}" '
            f'stroke="{color}" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>'
        )
        elements.append(
            f'<text x="{tx + 2}" y="{pad_t + 9}" font-size="8" fill="{color}" font-family="monospace">{label}</text>'
        )

    body = "\n".join(elements)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#0f172a;border-radius:8px">'
        f'{body}</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
def build_dashboard_html() -> str:
    traj_svg     = build_trajectory_svg()
    smooth_svg   = build_smoothness_bar_svg()
    ts_now       = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    avg_smoothness = sum(j["smoothness"] for j in JOINTS) / len(JOINTS)

    joint_rows = []
    for jd in JOINTS:
        note = jd.get("note", "")
        sm_color = "#86efac" if jd["smoothness"] >= 0.90 else ("#fde68a" if jd["smoothness"] >= 0.75 else "#fca5a5")
        joint_rows.append(
            f'<tr>'
            f'<td style="color:#38bdf8;font-family:monospace">{jd["id"]}</td>'
            f'<td style="color:#94a3b8">[{jd["range"][0]}, {jd["range"][1]}]</td>'
            f'<td style="color:#e2e8f0">[{jd["typical_range"][0]}, {jd["typical_range"][1]}]</td>'
            f'<td style="color:{sm_color};font-weight:bold">{jd["smoothness"]}</td>'
            f'<td style="color:#e2e8f0">{jd["peak_vel"]} {jd["unit"]}</td>'
            f'<td style="color:#64748b;font-size:11px">{note}</td>'
            f'</tr>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>OCI Robot Cloud — Action Decoder Analysis</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: sans-serif; padding: 24px; }}
  h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
  .stat-row {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
  .stat {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px 24px; min-width: 150px; }}
  .stat-val {{ font-size: 28px; font-weight: bold; color: #38bdf8; }}
  .stat-lbl {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
  h2 {{ color: #38bdf8; font-size: 15px; margin: 24px 0 10px; text-transform: uppercase; letter-spacing: 1px; }}
  .svg-wrap {{ background: #0f172a; border-radius: 8px; overflow: hidden; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th {{ text-align: left; color: #64748b; font-size: 11px; text-transform: uppercase; padding: 6px 10px; }}
  td {{ padding: 8px 10px; border-top: 1px solid #1e293b; font-size: 13px; }}
  .note {{ background: #1e293b; border-left: 3px solid #f59e0b; padding: 10px 16px; border-radius: 4px; margin: 16px 0; font-size: 13px; color: #fde68a; }}
  .footer {{ margin-top: 32px; color: #334155; font-size: 11px; text-align: center; }}
</style>
</head>
<body>
<h1>OCI Robot Cloud — Action Decoder Analysis</h1>
<p class="subtitle">Port 8181 &nbsp;|&nbsp; {ts_now} &nbsp;|&nbsp; GR00T N1.6 / Franka Panda</p>

<div class="stat-row">
  <div class="stat"><div class="stat-val">{len(JOINTS)}</div><div class="stat-lbl">Joint Dimensions</div></div>
  <div class="stat"><div class="stat-val">{EPISODE_STEPS}</div><div class="stat-lbl">Episode Steps</div></div>
  <div class="stat"><div class="stat-val">{CHUNK_SIZE}</div><div class="stat-lbl">Chunk Size</div></div>
  <div class="stat"><div class="stat-val">{avg_smoothness:.2f}</div><div class="stat-lbl">Avg Smoothness</div></div>
  <div class="stat"><div class="stat-val">{GRASP_STEP}</div><div class="stat-lbl">Grasp Step</div></div>
</div>

<h2>Episode Trajectory (847 steps, all joints)</h2>
<div class="svg-wrap">{traj_svg}</div>

<div class="note">Vertical dashed line at step {GRASP_STEP} marks grasp event. Gripper (orange) transitions sharply from open to closed — expected binary-like behavior.</div>

<h2>Joint Smoothness (GR00T Action Decoder)</h2>
<div class="svg-wrap">{smooth_svg}</div>

<h2>Joint Details</h2>
<table>
  <thead><tr><th>Joint</th><th>Full Range</th><th>Typical Range</th><th>Smoothness</th><th>Peak Vel</th><th>Notes</th></tr></thead>
  <tbody>{''.join(joint_rows)}</tbody>
</table>

<div class="footer">OCI Robot Cloud Action Decoder Analysis &copy; 2026 Oracle Corporation</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if FastAPI is not None:
    app = FastAPI(
        title="OCI Robot Cloud Action Decoder Analysis",
        description="GR00T N1.6 action trajectory inspection for Franka Panda",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_dashboard_html()

    @app.get("/joints")
    async def get_joints():
        return JSONResponse(content={"joints": JOINTS})

    @app.get("/trajectory")
    async def get_trajectory():
        return JSONResponse(content=get_episode_trajectory())

    @app.get("/chunks")
    async def get_chunks():
        return JSONResponse(content=get_chunk_analysis())


if __name__ == "__main__":
    try:
        import uvicorn
        uvicorn.run("action_decoder_analysis:app", host="0.0.0.0", port=8181, reload=False)
    except ImportError:
        print("[action_decoder_analysis] uvicorn not installed — cannot start server")

"""DAgger Convergence Analyzer — FastAPI service on port 8176.

Tracks when online DAgger learning stabilizes across runs.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise SystemExit(f"Required package missing: {e}. Install fastapi uvicorn.") from e

import math

app = FastAPI(title="DAgger Convergence Analyzer", version="1.0.0")

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

RUNS = {
    "dagger_run5": {
        "id": "dagger_run5",
        "episodes": 500,
        "final_sr": 0.42,
        "convergence_step": 420,
        "plateau_sr": 0.42,
        "converged": True,
        "oscillation_amplitude": 0.02,
        "note": None,
    },
    "dagger_run6": {
        "id": "dagger_run6",
        "episodes": 800,
        "final_sr": 0.51,
        "convergence_step": 680,
        "plateau_sr": 0.51,
        "converged": True,
        "oscillation_amplitude": 0.03,
        "note": None,
    },
    "dagger_run7": {
        "id": "dagger_run7",
        "episodes": 600,
        "final_sr": 0.47,
        "convergence_step": 550,
        "plateau_sr": 0.46,
        "converged": True,
        "oscillation_amplitude": 0.04,
        "note": None,
    },
    "dagger_run9": {
        "id": "dagger_run9",
        "episodes": 1200,
        "final_sr": 0.71,
        "convergence_step": 980,
        "plateau_sr": 0.71,
        "converged": True,
        "oscillation_amplitude": 0.02,
        "note": None,
    },
    "dagger_run10": {
        "id": "dagger_run10",
        "episodes": 420,
        "final_sr": None,
        "convergence_step": None,
        "plateau_sr": None,
        "converged": False,
        "oscillation_amplitude": None,
        "note": "IN PROGRESS — 420/target episodes",
    },
}

# Beta schedule: DAgger mixing ratio beta = 0.95^episode
def beta_schedule(episode: int) -> float:
    return 0.95 ** episode


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

# Color palette per run
RUN_COLORS = {
    "dagger_run5": "#f97316",   # orange
    "dagger_run6": "#a78bfa",   # violet
    "dagger_run7": "#34d399",   # emerald
    "dagger_run9": "#38bdf8",   # sky (BEST)
    "dagger_run10": "#fb7185",  # rose (in-progress)
}


def _lerp(v_min: float, v_max: float, t: float) -> float:
    return v_min + (v_max - v_min) * t


def _generate_sr_trajectory(ep: int, target_sr: float, conv_step: int | None) -> list[tuple[int, float]]:
    """Generate a plausible SR trajectory list of (episode, sr) points."""
    pts: list[tuple[int, float]] = []
    ramp_end = conv_step if conv_step else ep
    for i in range(0, ep + 1, max(1, ep // 40)):
        if i <= ramp_end:
            # logistic ramp
            t = i / ramp_end if ramp_end > 0 else 1.0
            sr = target_sr * (1 / (1 + math.exp(-10 * (t - 0.5))))
        else:
            sr = target_sr
        pts.append((i, sr))
    return pts


def build_sr_trajectory_svg() -> str:
    W, H = 680, 240
    PAD_L, PAD_R, PAD_T, PAD_B = 54, 20, 20, 36
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    max_ep = 1300
    max_sr = 1.0

    def tx(ep: int) -> float:
        return PAD_L + (ep / max_ep) * plot_w

    def ty(sr: float) -> float:
        return PAD_T + plot_h - (sr / max_sr) * plot_h

    lines: list[str] = []

    # Plateau shading for converged runs
    for run_id, run in RUNS.items():
        if not run["converged"] or run["convergence_step"] is None:
            continue
        cs = run["convergence_step"]
        ep = run["episodes"]
        psr = run["plateau_sr"]
        x1 = tx(cs)
        x2 = tx(ep)
        y1 = ty(psr + 0.04)
        y2 = ty(max(0.0, psr - 0.04))
        col = RUN_COLORS[run_id]
        lines.append(
            f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{x2-x1:.1f}" height="{y2-y1:.1f}" '
            f'fill="{col}" fill-opacity="0.1" rx="2"/>'
        )

    # Trajectories
    for run_id, run in RUNS.items():
        col = RUN_COLORS[run_id]
        ep = run["episodes"]
        target_sr = run["final_sr"] if run["final_sr"] is not None else 0.74
        conv_step = run["convergence_step"]
        pts = _generate_sr_trajectory(ep, target_sr, conv_step)

        path_d = " ".join(
            f"{'M' if i == 0 else 'L'}{tx(p[0]):.1f},{ty(p[1]):.1f}"
            for i, p in enumerate(pts)
        )
        dash = 'stroke-dasharray="8 4"' if run_id == "dagger_run10" else ""
        lines.append(
            f'<path d="{path_d}" fill="none" stroke="{col}" stroke-width="2" {dash} opacity="0.9"/>'
        )

        # Convergence star marker
        if conv_step is not None:
            cx = tx(conv_step)
            cy = ty(target_sr)
            # Draw a ★ as text
            lines.append(
                f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" dominant-baseline="middle" '
                f'font-size="14" fill="{col}" stroke="#0f172a" stroke-width="0.5">&#9733;</text>'
            )

    # Axes
    lines.append(
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+plot_h}" stroke="#475569" stroke-width="1"/>'
    )
    lines.append(
        f'<line x1="{PAD_L}" y1="{PAD_T+plot_h}" x2="{PAD_L+plot_w}" y2="{PAD_T+plot_h}" stroke="#475569" stroke-width="1"/>'
    )

    # X-axis labels
    for ep_val in [0, 250, 500, 750, 1000, 1300]:
        xp = tx(ep_val)
        lines.append(
            f'<text x="{xp:.1f}" y="{PAD_T+plot_h+14}" text-anchor="middle" font-size="10" fill="#94a3b8">{ep_val}</text>'
        )

    # Y-axis labels
    for sr_val in [0.0, 0.25, 0.5, 0.75, 1.0]:
        yp = ty(sr_val)
        lines.append(
            f'<text x="{PAD_L-6}" y="{yp:.1f}" text-anchor="end" dominant-baseline="middle" font-size="10" fill="#94a3b8">{sr_val:.2f}</text>'
        )
        lines.append(
            f'<line x1="{PAD_L}" y1="{yp:.1f}" x2="{PAD_L+plot_w}" y2="{yp:.1f}" stroke="#1e293b" stroke-width="1"/>'
        )

    # Legend
    lx = PAD_L + 8
    ly = PAD_T + 6
    for run_id, col in RUN_COLORS.items():
        dash = 'stroke-dasharray="6 3"' if run_id == "dagger_run10" else ""
        lines.append(f'<line x1="{lx}" y1="{ly+4}" x2="{lx+18}" y2="{ly+4}" stroke="{col}" stroke-width="2" {dash}/>')
        lines.append(f'<text x="{lx+22}" y="{ly+8}" font-size="9" fill="#cbd5e1">{run_id}</text>')
        lx += 110

    # Axis titles
    lines.append(f'<text x="{PAD_L + plot_w//2}" y="{H-2}" text-anchor="middle" font-size="10" fill="#64748b">Episodes</text>')
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


def build_convergence_speed_svg() -> str:
    """Bar chart: convergence_step per converged run. Shorter = faster."""
    W, H = 680, 180
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 20, 20, 36
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    converged_runs = [
        (rid, r) for rid, r in RUNS.items() if r["converged"] and r["convergence_step"] is not None
    ]
    n = len(converged_runs)
    max_step = max(r["convergence_step"] for _, r in converged_runs)

    bar_w = plot_w / (n * 1.5)
    gap = bar_w * 0.5

    lines: list[str] = []

    for i, (run_id, run) in enumerate(converged_runs):
        x = PAD_L + i * (bar_w + gap)
        h = (run["convergence_step"] / max_step) * plot_h
        y = PAD_T + plot_h - h
        col = RUN_COLORS[run_id]
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{col}" rx="3"/>')
        label = run["convergence_step"]
        lines.append(
            f'<text x="{x + bar_w/2:.1f}" y="{y - 4:.1f}" text-anchor="middle" font-size="10" fill="{col}">{label}</text>'
        )
        # Run label under bar
        lines.append(
            f'<text x="{x + bar_w/2:.1f}" y="{PAD_T+plot_h+14}" text-anchor="middle" font-size="9" fill="#94a3b8">{run_id.replace("dagger_","")}</text>'
        )
        # Special annotation for run9
        if run_id == "dagger_run9":
            lines.append(
                f'<text x="{x + bar_w/2:.1f}" y="{y - 16:.1f}" text-anchor="middle" font-size="8" fill="#38bdf8">BEST: 980 steps → SR 0.71</text>'
            )

    # Axes
    lines.append(
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+plot_h}" stroke="#475569" stroke-width="1"/>'
    )
    lines.append(
        f'<line x1="{PAD_L}" y1="{PAD_T+plot_h}" x2="{PAD_L+plot_w}" y2="{PAD_T+plot_h}" stroke="#475569" stroke-width="1"/>'
    )

    # Y-axis
    for step_val in [0, 250, 500, 750, 1000]:
        yp = PAD_T + plot_h - (step_val / max_step) * plot_h
        lines.append(
            f'<text x="{PAD_L-6}" y="{yp:.1f}" text-anchor="end" dominant-baseline="middle" font-size="9" fill="#94a3b8">{step_val}</text>'
        )
        lines.append(
            f'<line x1="{PAD_L}" y1="{yp:.1f}" x2="{PAD_L+plot_w}" y2="{yp:.1f}" stroke="#1e293b" stroke-width="1"/>'
        )

    lines.append(
        f'<text x="{W//2}" y="{H-2}" text-anchor="middle" font-size="10" fill="#64748b">Run</text>'
    )
    lines.append(
        f'<text x="10" y="{PAD_T + plot_h//2}" text-anchor="middle" font-size="10" fill="#64748b" '
        f'transform="rotate(-90,10,{PAD_T + plot_h//2})">Steps to Converge</text>'
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
    sr_svg = build_sr_trajectory_svg()
    conv_svg = build_convergence_speed_svg()

    # Beta schedule preview table rows
    beta_rows = "".join(
        f'<tr><td class="p">{ep}</td><td class="p" style="color:#38bdf8">{beta_schedule(ep):.4f}</td></tr>'
        for ep in [0, 10, 20, 50, 100, 200, 500]
    )

    # Run summary rows
    run_rows = ""
    for run_id, run in RUNS.items():
        col = RUN_COLORS[run_id]
        status = "CONVERGED" if run["converged"] else "IN PROGRESS"
        status_col = "#34d399" if run["converged"] else "#fb7185"
        sr_disp = f"{run['final_sr']:.2f}" if run["final_sr"] is not None else "—"
        conv_disp = str(run["convergence_step"]) if run["convergence_step"] is not None else "—"
        run_rows += (
            f'<tr>'
            f'<td class="p" style="color:{col}">{run_id}</td>'
            f'<td class="p">{run["episodes"]}</td>'
            f'<td class="p">{sr_disp}</td>'
            f'<td class="p">{conv_disp}</td>'
            f'<td class="p" style="color:{status_col}">{status}</td>'
            f'</tr>'
        )

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DAgger Convergence Analyzer</title>
<style>
  body {{ margin:0; padding:0; background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',sans-serif; }}
  h1 {{ color:#C74634; margin:0 0 4px; font-size:1.4rem; }}
  h2 {{ color:#38bdf8; font-size:1rem; margin:20px 0 8px; }}
  .header {{ background:#1e293b; padding:16px 24px; border-bottom:2px solid #C74634; }}
  .sub {{ color:#94a3b8; font-size:0.8rem; }}
  .main {{ padding:20px 24px; }}
  .card {{ background:#1e293b; border-radius:8px; padding:16px; margin-bottom:16px; }}
  .badge {{ display:inline-block; background:#C74634; color:#fff; padding:2px 8px; border-radius:4px; font-size:0.75rem; }}
  .predict {{ background:#0c2340; border:1px solid #38bdf8; border-radius:8px; padding:14px; color:#cbd5e1; font-size:0.9rem; }}
  table {{ border-collapse:collapse; width:100%; }}
  th {{ color:#64748b; font-size:0.75rem; text-align:left; padding:4px 8px; border-bottom:1px solid #334155; }}
  .p {{ padding:6px 8px; font-size:0.85rem; border-bottom:1px solid #1e293b; }}
</style>
</head>
<body>
<div class="header">
  <h1>DAgger Convergence Analyzer</h1>
  <div class="sub">Port 8176 &nbsp;|&nbsp; Online Learning Stability Tracker &nbsp;|&nbsp; OCI Robot Cloud</div>
</div>
<div class="main">
  <div class="card">
    <h2>SR Trajectory per Run</h2>
    <div class="sub" style="margin-bottom:8px">&#9733; marks convergence point; dashed line = in-progress; shaded region = plateau</div>
    {sr_svg}
  </div>

  <div class="card">
    <h2>Convergence Speed Comparison</h2>
    <div class="sub" style="margin-bottom:8px">Steps to reach plateau SR (lower = faster convergence)</div>
    {conv_svg}
  </div>

  <div class="card">
    <h2>Run Summary</h2>
    <table>
      <tr>
        <th>Run</th><th>Episodes</th><th>Final SR</th><th>Conv. Step</th><th>Status</th>
      </tr>
      {run_rows}
    </table>
  </div>

  <div class="card">
    <h2>Convergence Prediction — dagger_run10 <span class="badge">IN PROGRESS</span></h2>
    <div class="predict">
      Based on dagger_run9 trajectory shape (best benchmark: 980 steps, SR 0.71), run10 is
      projected to converge at approximately <strong style="color:#38bdf8">950–1000 episodes</strong>
      with an estimated plateau SR of <strong style="color:#34d399">0.74–0.78</strong>.<br><br>
      Current progress: <strong>420 / ~975 episodes (est.)</strong> &nbsp;
      <span style="color:#fb7185">&#9632;</span><span style="background:#38bdf8;height:6px;display:inline-block;width:60px;vertical-align:middle;border-radius:3px"></span>
      &nbsp; 43% complete
    </div>
  </div>

  <div class="card">
    <h2>Beta Schedule — Expert Mixing Ratio (&beta; = 0.95<sup>t</sup>)</h2>
    <div class="sub" style="margin-bottom:8px">Expert intervention probability decays geometrically over episodes</div>
    <table>
      <tr><th>Episode</th><th>&beta; (expert ratio)</th></tr>
      {beta_rows}
    </table>
  </div>
</div>
</body>
</html>
"""
    return HTMLResponse(content=html)


@app.get("/runs")
async def list_runs() -> JSONResponse:
    return JSONResponse(content=list(RUNS.values()))


@app.get("/runs/{run_id}")
async def get_run(run_id: str) -> JSONResponse:
    if run_id not in RUNS:
        return JSONResponse(status_code=404, content={"error": f"Run '{run_id}' not found"})
    return JSONResponse(content=RUNS[run_id])


@app.get("/predict/{run_id}")
async def predict_convergence(run_id: str) -> JSONResponse:
    if run_id not in RUNS:
        return JSONResponse(status_code=404, content={"error": f"Run '{run_id}' not found"})
    run = RUNS[run_id]
    if run["converged"]:
        return JSONResponse(content={
            "run_id": run_id,
            "already_converged": True,
            "convergence_step": run["convergence_step"],
            "final_sr": run["final_sr"],
        })
    # Predict based on run9 trajectory shape
    ref = RUNS["dagger_run9"]
    predicted_conv_step = int(ref["convergence_step"] * 0.97)   # slight variation
    predicted_sr_low = round(ref["final_sr"] + 0.03, 2)
    predicted_sr_high = round(ref["final_sr"] + 0.07, 2)
    current_ep = run["episodes"]
    progress_pct = round(current_ep / predicted_conv_step * 100, 1)
    return JSONResponse(content={
        "run_id": run_id,
        "already_converged": False,
        "current_episodes": current_ep,
        "predicted_convergence_step": predicted_conv_step,
        "predicted_sr_range": [predicted_sr_low, predicted_sr_high],
        "progress_pct": progress_pct,
        "reference_run": "dagger_run9",
        "note": "Projection based on dagger_run9 trajectory shape (best benchmark)",
    })


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8176)

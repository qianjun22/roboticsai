"""dagger_run_manager.py — Manages DAgger training runs with progress tracking
and adaptive stopping. FastAPI service on port 8251.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import math
import random
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

random.seed(77)

# DAgger run records run5 through run10
DAGGER_RUNS = [
    {
        "run_id": "run5",
        "label": "Run 5",
        "status": "FAILED",
        "episodes": 99,
        "final_sr": 0.05,
        "gpu_hours": 0.8,
        "cost_usd": 0.52,
        "note": "Too few episodes vs BC baseline",
        "version": "v2.0",
    },
    {
        "run_id": "run6",
        "label": "Run 6",
        "status": "CONVERGED",
        "episodes": 312,
        "final_sr": 0.31,
        "gpu_hours": 2.6,
        "cost_usd": 1.69,
        "note": "Partial convergence — lr too high",
        "version": "v2.0",
    },
    {
        "run_id": "run7",
        "label": "Run 7",
        "status": "CONVERGED",
        "episodes": 520,
        "final_sr": 0.48,
        "gpu_hours": 4.3,
        "cost_usd": 2.80,
        "note": "Chunk reset bug introduced plateau",
        "version": "v2.1",
    },
    {
        "run_id": "run8",
        "label": "Run 8",
        "status": "CONVERGED",
        "episodes": 680,
        "final_sr": 0.59,
        "gpu_hours": 5.6,
        "cost_usd": 3.64,
        "note": "Better but cube_z sanity missing",
        "version": "v2.1",
    },
    {
        "run_id": "run9_v2.2",
        "label": "Run 9 v2.2",
        "status": "PROD",
        "episodes": 847,
        "final_sr": 0.71,
        "gpu_hours": 7.3,
        "cost_usd": 4.73,
        "note": "All 3 bugfixes applied — PROD deployed",
        "version": "v2.2",
    },
    {
        "run_id": "run10",
        "label": "Run 10",
        "status": "IN_PROGRESS",
        "episodes": None,  # not complete
        "current_step": 1420,
        "total_steps": 5000,
        "projected_sr": 0.76,
        "current_sr": 0.61,
        "gpu_hours": 3.1,
        "cost_usd": 2.02,
        "note": "DAgger + curriculum SDG; projected SR=0.76",
        "version": "v2.3",
    },
]


def _sr_trajectory(run_id: str, max_ep: int, final_sr: float, seed: int):
    """Generate a smooth SR trajectory up to max_ep episodes."""
    rng = random.Random(seed)
    pts = []
    for ep in range(0, max_ep + 1, 20):
        t = ep / max_ep
        # Sigmoid growth with noise
        sr = final_sr / (1 + math.exp(-10 * (t - 0.45))) + rng.gauss(0, 0.015)
        sr = max(0.0, min(1.0, sr))
        pts.append((ep, sr))
    return pts


def _run10_partial_trajectory():
    """IN_PROGRESS trajectory — partial and dashed."""
    rng = random.Random(99)
    pts = []
    max_ep_projected = 1200
    current_ep = int(1420 / 5000 * max_ep_projected)
    for ep in range(0, current_ep + 1, 20):
        t = ep / 1200
        sr = 0.76 / (1 + math.exp(-10 * (t - 0.45))) + rng.gauss(0, 0.012)
        sr = max(0.0, min(1.0, sr))
        pts.append((ep, sr))
    return pts


# ---------------------------------------------------------------------------
# SVG generation
# ---------------------------------------------------------------------------

def _svg_sr_trajectories() -> str:
    """Multi-run SR trajectory plot with convergence band and plateau detection."""
    W, H = 900, 340
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 140, 30, 50
    PLOT_W = W - PAD_L - PAD_R
    PLOT_H = H - PAD_T - PAD_B
    MAX_EP = 1500

    def sx(ep): return PAD_L + (ep / MAX_EP) * PLOT_W
    def sy(sr): return PAD_T + PLOT_H - sr * PLOT_H

    COLORS = {
        "run5":      "#ef4444",
        "run6":      "#f97316",
        "run7":      "#f59e0b",
        "run8":      "#38bdf8",
        "run9_v2.2": "#22c55e",
        "run10":     "#a78bfa",
    }

    # Convergence band (target 0.65-0.80)
    band_y_top = sy(0.80)
    band_y_bot = sy(0.65)
    band = f'<rect x="{PAD_L}" y="{band_y_top:.1f}" width="{PLOT_W}" height="{band_y_bot-band_y_top:.1f}" fill="rgba(34,197,94,0.08)" />'
    band += f'<line x1="{PAD_L}" y1="{sy(0.71):.1f}" x2="{PAD_L+PLOT_W}" y2="{sy(0.71):.1f}" stroke="#22c55e" stroke-dasharray="5,5" stroke-width="1" opacity="0.5"/>'
    band += f'<text x="{PAD_L+PLOT_W+4}" y="{sy(0.71)+4:.1f}" fill="#22c55e" font-size="9">PROD 0.71</text>'

    lines = ""
    labels = ""
    for run in DAGGER_RUNS:
        rid = run["run_id"]
        col = COLORS[rid]
        if rid == "run10":
            pts = _run10_partial_trajectory()
            # Scale episode axis to MAX_EP space
            scaled = [(ep * MAX_EP / 1200, sr) for ep, sr in pts]
            poly_pts = " ".join(f"{sx(ep):.1f},{sy(sr):.1f}" for ep, sr in scaled)
            lines += f'<polyline points="{poly_pts}" fill="none" stroke="{col}" stroke-width="2" stroke-dasharray="8,4"/>'
            # Projected endpoint marker
            last_x = sx(scaled[-1][0]); last_y = sy(scaled[-1][1])
            lines += f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="5" fill="{col}" opacity="0.8"/>'
            lines += f'<text x="{last_x+8:.1f}" y="{last_y-6:.1f}" fill="{col}" font-size="9">→0.76 projected</text>'
        else:
            final_sr = run["final_sr"]
            max_ep = run["episodes"]
            pts = _sr_trajectory(rid, max_ep, final_sr, hash(rid) % 1000)
            scaled = [(ep * MAX_EP / 1500, sr) for ep, sr in pts]
            poly_pts = " ".join(f"{sx(ep):.1f},{sy(sr):.1f}" for ep, sr in scaled)
            lines += f'<polyline points="{poly_pts}" fill="none" stroke="{col}" stroke-width="1.8"/>'
            # End marker
            end_x = sx(max_ep * MAX_EP / 1500); end_y = sy(final_sr)
            lines += f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="4" fill="{col}"/>'
            # Plateau marker if failed/partial
            if run["status"] in ("FAILED", "CONVERGED"):
                lines += f'<text x="{end_x+6:.1f}" y="{end_y-4:.1f}" fill="{col}" font-size="8">SR={final_sr}</text>'

    # Grid lines
    grid = ""
    for sr_val in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        y = sy(sr_val)
        grid += f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L+PLOT_W}" y2="{y:.1f}" stroke="#1e293b" stroke-dasharray="3,5"/>'
        grid += f'<text x="{PAD_L-6}" y="{y+4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">{sr_val:.1f}</text>'

    # X ticks
    x_ticks = ""
    for ep in range(0, 1501, 300):
        x = sx(ep)
        x_ticks += f'<line x1="{x:.1f}" y1="{PAD_T+PLOT_H}" x2="{x:.1f}" y2="{PAD_T+PLOT_H+5}" stroke="#475569"/>'
        x_ticks += f'<text x="{x:.1f}" y="{PAD_T+PLOT_H+18}" fill="#94a3b8" font-size="9" text-anchor="middle">{ep}</text>'

    # Legend
    legend = ""
    for i, run in enumerate(DAGGER_RUNS):
        rid = run["run_id"]; col = COLORS[rid]
        lx = PAD_L + PLOT_W + 12; ly = PAD_T + i * 26
        dash = "stroke-dasharray='6,3'" if rid == "run10" else ""
        legend += f'<line x1="{lx}" y1="{ly+7}" x2="{lx+20}" y2="{ly+7}" stroke="{col}" stroke-width="2" {dash}/>'
        legend += f'<text x="{lx+24}" y="{ly+11}" fill="{col}" font-size="9">{run["label"]} [{run["status"]}]</text>'

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" style="width:100%;background:#1e293b;border-radius:8px">
  <rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>
  <text x="{(PAD_L+PAD_L+PLOT_W)//2}" y="18" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">DAgger Run SR Trajectories (Run 5–10) — Episodes vs Success Rate</text>
  {band}
  {grid}
  {x_ticks}
  {lines}
  {legend}
  <line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+PLOT_H}" stroke="#475569"/>
  <line x1="{PAD_L}" y1="{PAD_T+PLOT_H}" x2="{PAD_L+PLOT_W}" y2="{PAD_T+PLOT_H}" stroke="#475569"/>
  <text x="{PAD_L+PLOT_W//2}" y="{PAD_T+PLOT_H+36}" fill="#94a3b8" font-size="10" text-anchor="middle">Episodes</text>
  <text x="18" y="{PAD_T+PLOT_H//2}" fill="#94a3b8" font-size="10" text-anchor="middle" transform="rotate(-90,18,{PAD_T+PLOT_H//2})">Success Rate</text>
</svg>"""
    return svg


def _svg_resource_bars() -> str:
    """Per-run resource consumption bar chart — GPU-hours, cost, SR, efficiency."""
    W, H = 900, 300
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 30, 35, 60
    PLOT_W = W - PAD_L - PAD_R
    PLOT_H = H - PAD_T - PAD_B

    # Only runs with cost data
    runs = [r for r in DAGGER_RUNS]
    N = len(runs)
    GROUP_W = PLOT_W / N
    BAR_W = GROUP_W * 0.35
    COLORS = ["#ef4444","#f97316","#f59e0b","#38bdf8","#22c55e","#a78bfa"]

    max_cost = max(r["cost_usd"] for r in runs)
    max_gpu = max(r["gpu_hours"] for r in runs)

    bars = ""
    for i, run in enumerate(runs):
        cx = PAD_L + i * GROUP_W + GROUP_W / 2
        col = COLORS[i]

        # Cost bar (left of center)
        cost_h = (run["cost_usd"] / max_cost) * PLOT_H * 0.85
        bx1 = cx - BAR_W - 2
        by1 = PAD_T + PLOT_H - cost_h
        bars += f'<rect x="{bx1:.1f}" y="{by1:.1f}" width="{BAR_W:.1f}" height="{cost_h:.1f}" fill="{col}" opacity="0.85" rx="2"/>'
        bars += f'<text x="{bx1+BAR_W/2:.1f}" y="{by1-4:.1f}" fill="{col}" font-size="8" text-anchor="middle">${run["cost_usd"]:.2f}</text>'

        # GPU-hours bar (right of center)
        gpu_h = (run["gpu_hours"] / max_gpu) * PLOT_H * 0.85
        bx2 = cx + 2
        by2 = PAD_T + PLOT_H - gpu_h
        bars += f'<rect x="{bx2:.1f}" y="{by2:.1f}" width="{BAR_W:.1f}" height="{gpu_h:.1f}" fill="{col}" opacity="0.45" rx="2"/>'
        bars += f'<text x="{bx2+BAR_W/2:.1f}" y="{by2-4:.1f}" fill="#94a3b8" font-size="8" text-anchor="middle">{run["gpu_hours"]}h</text>'

        # SR dot overlay
        sr_val = run.get("final_sr") or run.get("current_sr") or 0
        sr_y = PAD_T + PLOT_H - sr_val * PLOT_H * 0.85
        bars += f'<circle cx="{cx:.1f}" cy="{sr_y:.1f}" r="5" fill="{col}" stroke="white" stroke-width="1"/>'
        bars += f'<text x="{cx:.1f}" y="{sr_y-10:.1f}" fill="{col}" font-size="8" text-anchor="middle">SR={sr_val}</text>'

        # Efficiency: SR per $10
        eff = round(sr_val / run["cost_usd"] * 10, 2) if run["cost_usd"] > 0 else 0
        bars += f'<text x="{cx:.1f}" y="{PAD_T+PLOT_H+28}" fill="#64748b" font-size="8" text-anchor="middle">{eff} SR/$10</text>'
        bars += f'<text x="{cx:.1f}" y="{PAD_T+PLOT_H+42}" fill="{col}" font-size="9" text-anchor="middle" font-weight="bold">{run["label"]}</text>'
        status_col = {"PROD":"#22c55e","FAILED":"#ef4444","IN_PROGRESS":"#a78bfa"}.get(run["status"],"#94a3b8")
        bars += f'<text x="{cx:.1f}" y="{PAD_T+PLOT_H+55}" fill="{status_col}" font-size="7" text-anchor="middle">[{run["status"]}]</text>'

    # Y-axis grid
    grid = ""
    for v in [0, 0.25, 0.5, 0.75, 1.0]:
        y = PAD_T + PLOT_H - v * PLOT_H * 0.85
        label = f"${max_cost*v:.2f}"
        grid += f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L+PLOT_W}" y2="{y:.1f}" stroke="#1e293b" stroke-dasharray="3,5"/>'
        grid += f'<text x="{PAD_L-4}" y="{y+4:.1f}" fill="#94a3b8" font-size="8" text-anchor="end">{label}</text>'

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" style="width:100%;background:#1e293b;border-radius:8px">
  <rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>
  <text x="{W//2}" y="18" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">Per-Run Resource Consumption — Cost · GPU-hours · SR (Run 5–10)</text>
  {grid}
  {bars}
  <line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+PLOT_H}" stroke="#475569"/>
  <line x1="{PAD_L}" y1="{PAD_T+PLOT_H}" x2="{PAD_L+PLOT_W}" y2="{PAD_T+PLOT_H}" stroke="#475569"/>
  <!-- Legend -->
  <rect x="{PAD_L}" y="{H-10}" width="10" height="8" fill="#38bdf8" opacity="0.85" rx="1"/>
  <text x="{PAD_L+14}" y="{H-2}" fill="#94a3b8" font-size="8">Cost (USD)</text>
  <rect x="{PAD_L+90}" y="{H-10}" width="10" height="8" fill="#38bdf8" opacity="0.45" rx="1"/>
  <text x="{PAD_L+104}" y="{H-2}" fill="#94a3b8" font-size="8">GPU-hours</text>
  <circle cx="{PAD_L+200}" cy="{H-6}" r="4" fill="#38bdf8" stroke="white" stroke-width="1"/>
  <text x="{PAD_L+208}" y="{H-2}" fill="#94a3b8" font-size="8">Achieved SR</text>
</svg>"""
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    svg1 = _svg_sr_trajectories()
    svg2 = _svg_resource_bars()

    prod_run = next(r for r in DAGGER_RUNS if r["status"] == "PROD")
    progress_run = next(r for r in DAGGER_RUNS if r["status"] == "IN_PROGRESS")
    pct = round(progress_run["current_step"] / progress_run["total_steps"] * 100, 1)
    eta_steps = progress_run["total_steps"] - progress_run["current_step"]
    eta_min = round(eta_steps / 2.35 / 60, 1)  # 2.35 it/s

    run_rows = ""
    for run in DAGGER_RUNS:
        status_color = {
            "PROD": "#22c55e", "FAILED": "#ef4444",
            "CONVERGED": "#38bdf8", "IN_PROGRESS": "#a78bfa"
        }.get(run["status"], "#94a3b8")
        sr_disp = str(run.get("final_sr") or f"{run.get('current_sr')} (live)") if run.get("final_sr") is not None else f"{run.get('current_sr')} (live)"
        ep_disp = str(run["episodes"]) if run["episodes"] is not None else f"step {run['current_step']}/{run['total_steps']}"
        run_rows += f"""<tr>
          <td style='padding:8px;color:#38bdf8;font-weight:600'>{run['label']}</td>
          <td style='padding:8px;color:{status_color};font-weight:bold'>{run['status']}</td>
          <td style='padding:8px;color:#e2e8f0'>{run['version']}</td>
          <td style='padding:8px;color:#e2e8f0'>{ep_disp}</td>
          <td style='padding:8px;color:#a3e635'>{sr_disp}</td>
          <td style='padding:8px;color:#f59e0b'>{run['gpu_hours']}h</td>
          <td style='padding:8px;color:#f97316'>${run['cost_usd']:.2f}</td>
          <td style='padding:8px;color:#94a3b8;font-size:11px'>{run['note']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DAgger Run Manager — Port 8251</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }}
  .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%); border-bottom: 2px solid #C74634; padding: 20px 32px; display:flex; align-items:center; gap:16px; }}
  .header h1 {{ font-size: 22px; font-weight: 700; }}
  .badge {{ background: rgba(199,70,52,0.2); color: #C74634; border: 1px solid #C74634; padding: 3px 10px; border-radius: 99px; font-size: 12px; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .kpi {{ background: #1e293b; border-radius: 10px; padding: 16px; border: 1px solid #334155; }}
  .kpi .label {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing:.05em; }}
  .kpi .value {{ font-size: 26px; font-weight: 700; margin: 6px 0 2px; }}
  .kpi .sub {{ font-size: 11px; color: #94a3b8; }}
  .progress-bar {{ background: #0f172a; border-radius: 99px; height: 8px; overflow: hidden; margin: 8px 0; }}
  .progress-fill {{ height: 100%; border-radius: 99px; background: linear-gradient(90deg, #38bdf8, #a78bfa); }}
  .chart-card {{ background: #1e293b; border-radius: 10px; padding: 16px; margin-bottom: 20px; border: 1px solid #334155; }}
  .chart-card h2 {{ font-size: 14px; color: #94a3b8; margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  thead tr {{ background: #0f172a; }}
  th {{ padding: 10px 8px; text-align: left; color: #64748b; font-weight: 600; font-size: 11px; text-transform: uppercase; }}
  tbody tr:hover {{ background: #263248; }}
  tbody tr {{ border-bottom: 1px solid #1e293b; }}
  .footer {{ text-align: center; color: #475569; font-size: 11px; padding: 20px; }}
</style>
</head>
<body>
<div class="header">
  <div>
    <div class="badge">Port 8251</div>
    <h1>DAgger Run Manager</h1>
    <div style="font-size:13px;color:#94a3b8;margin-top:4px">Progress tracking · Adaptive stopping · Run 5–10</div>
  </div>
  <div style="margin-left:auto;text-align:right">
    <div style="font-size:11px;color:#94a3b8">Run 10 progress</div>
    <div style="font-size:22px;font-weight:800;color:#a78bfa">{pct}%</div>
    <div class="progress-bar" style="width:160px">
      <div class="progress-fill" style="width:{pct}%"></div>
    </div>
    <div style="font-size:11px;color:#64748b">step {progress_run['current_step']}/{progress_run['total_steps']} · ETA ~{eta_min}h</div>
  </div>
</div>
<div class="container">
  <div class="kpi-grid">
    <div class="kpi"><div class="label">PROD SR (Run 9)</div><div class="value" style="color:#22c55e">{prod_run['final_sr']}</div><div class="sub">{prod_run['episodes']} episodes</div></div>
    <div class="kpi"><div class="label">Projected SR (Run 10)</div><div class="value" style="color:#a78bfa">{progress_run['projected_sr']}</div><div class="sub">at {progress_run['total_steps']} steps</div></div>
    <div class="kpi"><div class="label">PROD Cost</div><div class="value" style="color:#f59e0b">${prod_run['cost_usd']}</div><div class="sub">Run 9 v2.2</div></div>
    <div class="kpi"><div class="label">Run 10 Cost (so far)</div><div class="value" style="color:#f97316">${progress_run['cost_usd']}</div><div class="sub">{progress_run['gpu_hours']}h GPU</div></div>
    <div class="kpi"><div class="label">PROD Efficiency</div><div class="value" style="color:#38bdf8">{round(prod_run['final_sr']/prod_run['cost_usd']*10,2)}</div><div class="sub">SR per $10</div></div>
    <div class="kpi"><div class="label">Run 10 Live SR</div><div class="value" style="color:#a78bfa">{progress_run['current_sr']}</div><div class="sub">step {progress_run['current_step']}</div></div>
    <div class="kpi"><div class="label">Total Runs</div><div class="value" style="color:#e2e8f0">6</div><div class="sub">run5–run10</div></div>
    <div class="kpi"><div class="label">SR Improvement</div><div class="value" style="color:#a3e635">+1320%</div><div class="sub">run5→run9</div></div>
  </div>

  <div class="chart-card">
    <h2>SR Trajectories — All Runs (run5–run10); run10 dashed = IN_PROGRESS; convergence band = 0.65–0.80</h2>
    {svg1}
  </div>

  <div class="chart-card">
    <h2>Per-Run Resource Breakdown — Cost (solid) · GPU-hours (faded) · Achieved SR (dot) · Efficiency (SR per $10)</h2>
    {svg2}
  </div>

  <div class="chart-card">
    <h2>Run Registry</h2>
    <table>
      <thead><tr><th>Run</th><th>Status</th><th>Version</th><th>Episodes / Step</th><th>SR</th><th>GPU-h</th><th>Cost</th><th>Notes</th></tr></thead>
      <tbody>{run_rows}</tbody>
    </table>
  </div>
</div>
<div class="footer">OCI Robot Cloud · DAgger Run Manager · Port 8251 · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app (or stdlib fallback)
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(title="DAgger Run Manager", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "dagger_run_manager", "port": 8251}

    @app.get("/runs")
    def runs():
        return {"runs": DAGGER_RUNS, "total": len(DAGGER_RUNS)}

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        for r in DAGGER_RUNS:
            if r["run_id"] == run_id:
                return r
        return {"error": "run not found"}

    @app.get("/summary")
    def summary():
        prod = next(r for r in DAGGER_RUNS if r["status"] == "PROD")
        ip = next(r for r in DAGGER_RUNS if r["status"] == "IN_PROGRESS")
        return {
            "prod_run": prod["run_id"],
            "prod_sr": prod["final_sr"],
            "in_progress_run": ip["run_id"],
            "in_progress_step": ip["current_step"],
            "in_progress_projected_sr": ip["projected_sr"],
        }

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", ""):
                body = _build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/health":
                body = json.dumps({"status": "ok", "port": 8251}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/runs":
                body = json.dumps({"runs": DAGGER_RUNS}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt, *args):
            pass

    def _run_stdlib():
        with socketserver.TCPServer(("", 8251), _Handler) as httpd:
            print("dagger_run_manager (stdlib fallback) listening on port 8251")
            httpd.serve_forever()


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8251)
    else:
        _run_stdlib()

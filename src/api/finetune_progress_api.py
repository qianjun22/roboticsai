"""finetune_progress_api.py
Partner-facing fine-tune job progress API for OCI Robot Cloud.
Usage: python finetune_progress_api.py
       uvicorn finetune_progress_api:app --port 8187
Endpoints: GET / (dashboard), /jobs, /jobs/{job_id}, /jobs/{job_id}/metrics, /summary
"""
from __future__ import annotations
import json, math
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, List, Optional

PORT: int = 8187

# ── Static job data ───────────────────────────────────────────────────────────

@dataclass
class FinetuneJob:
    job_id: str
    partner: str
    model_base: str
    dataset: str
    status: str                    # COMPLETED | RUNNING | QUEUED
    steps_done: int
    target_steps: int
    pct_complete: float
    sr_before: Optional[float]     # success-rate before fine-tune
    sr_after:  Optional[float]     # success-rate after fine-tune
    mae:       Optional[float]
    duration_h: Optional[float]
    cost_usd:  float
    submitted: str
    est_completion: Optional[str] = None
    est_start:      Optional[str] = None


JOBS: List[FinetuneJob] = [
    FinetuneJob(
        job_id="job_pi_001", partner="physical_intelligence",
        model_base="groot_finetune_v2", dataset="pi_real_demos_v1",
        status="COMPLETED", steps_done=5000, target_steps=5000, pct_complete=100.0,
        sr_before=0.78, sr_after=0.81, mae=0.021, duration_h=2.4, cost_usd=7.34,
        submitted="2026-03-28",
    ),
    FinetuneJob(
        job_id="job_pi_002", partner="physical_intelligence",
        model_base="groot_finetune_v2", dataset="pi_real_demos_v2",
        status="RUNNING", steps_done=2840, target_steps=5000, pct_complete=56.8,
        sr_before=0.78, sr_after=None, mae=None, duration_h=None, cost_usd=4.17,
        submitted="2026-03-30", est_completion="2026-03-30T18:00Z",
    ),
    FinetuneJob(
        job_id="job_apt_001", partner="apptronik",
        model_base="dagger_run9_v2", dataset="apt_demos_v1",
        status="COMPLETED", steps_done=3000, target_steps=3000, pct_complete=100.0,
        sr_before=0.64, sr_after=0.68, mae=0.034, duration_h=1.6, cost_usd=4.90,
        submitted="2026-03-27",
    ),
    FinetuneJob(
        job_id="job_onex_001", partner="1x_technologies",
        model_base="groot_finetune_v2", dataset="onex_demos_v1",
        status="QUEUED", steps_done=0, target_steps=3000, pct_complete=0.0,
        sr_before=None, sr_after=None, mae=None, duration_h=None, cost_usd=0.0,
        submitted="2026-03-30", est_start="2026-03-31T09:00Z",
    ),
]

JOBS_BY_ID: Dict[str, FinetuneJob] = {j.job_id: j for j in JOBS}

STATUS_COLORS: Dict[str, str] = {
    "COMPLETED": "#22c55e",
    "RUNNING":   "#38bdf8",
    "QUEUED":    "#64748b",
}

PARTNER_COLORS: Dict[str, str] = {
    "physical_intelligence": "#38bdf8",
    "apptronik":             "#f59e0b",
    "1x_technologies":       "#22c55e",
}

# ── Synthetic loss-curve generator ────────────────────────────────────────────

def _loss_history(job: FinetuneJob, num_points: int = 20) -> List[Dict]:
    """Return synthetic loss history sampled at evenly-spaced checkpoints."""
    if job.steps_done == 0:
        return []
    steps = [int(job.steps_done * i / (num_points - 1)) for i in range(num_points)]
    steps[0] = max(1, steps[0])
    history = []
    init_loss = 0.48
    for s in steps:
        # Exponential decay + small noise (deterministic via hash)
        t = s / job.target_steps
        noise = (hash(f"{job.job_id}_{s}") % 100 - 50) / 50 * 0.008
        loss = init_loss * math.exp(-3.5 * t) + 0.06 + noise
        loss = max(0.04, round(loss, 4))
        history.append({"step": s, "loss": loss})
    return history


# ── SVG generators ────────────────────────────────────────────────────────────

def _svg_progress_bars(w: int = 680, h: int = 200) -> str:
    """Horizontal progress bars per job: status-coloured fill, cost annotation."""
    pad_l, pad_r, pad_t, pad_b = 140, 110, 20, 20
    bar_h = 26
    bar_gap = 14
    cw = w - pad_l - pad_r

    bars = []
    for idx, job in enumerate(JOBS):
        y = pad_t + idx * (bar_h + bar_gap)
        pct = min(job.pct_complete, 100.0)
        fill_w = pct * cw / 100
        color = STATUS_COLORS[job.status]

        # Background track
        bars.append(f"<rect x='{pad_l}' y='{y}' width='{cw}' height='{bar_h}' fill='#1e293b' rx='4'/>")

        if job.status == "RUNNING":
            # Animated progress bar via SVG animate
            bars.append(
                f"<rect x='{pad_l}' y='{y}' width='{fill_w:.1f}' height='{bar_h}' fill='{color}' rx='4' opacity='0.9'>"
                f"<animate attributeName='opacity' values='0.9;0.5;0.9' dur='1.6s' repeatCount='indefinite'/>"
                f"</rect>"
            )
        elif fill_w > 0:
            bars.append(f"<rect x='{pad_l}' y='{y}' width='{fill_w:.1f}' height='{bar_h}' fill='{color}' rx='4'/>")

        # Label: job_id on the left
        bars.append(
            f"<text x='{pad_l - 8}' y='{y + bar_h // 2 + 4}' fill='#cbd5e1' font-size='10' text-anchor='end'>{job.job_id}</text>"
        )
        # Pct label inside/outside bar
        pct_label_x = pad_l + fill_w + 6 if fill_w < cw - 40 else pad_l + fill_w - 6
        pct_anchor  = "start" if fill_w < cw - 40 else "end"
        pct_color   = "#94a3b8" if fill_w < cw - 40 else "#0f172a"
        bars.append(
            f"<text x='{pct_label_x:.1f}' y='{y + bar_h // 2 + 4}' fill='{pct_color}' "
            f"font-size='10' text-anchor='{pct_anchor}'>{pct:.0f}%</text>"
        )
        # Cost annotation on the right
        cost_str = f"${job.cost_usd:.2f}" if job.cost_usd > 0 else "$0.00"
        bars.append(
            f"<text x='{pad_l + cw + 8}' y='{y + bar_h // 2 + 4}' fill='#f59e0b' font-size='10'>{cost_str}</text>"
        )

    total_h = pad_t + len(JOBS) * (bar_h + bar_gap) + pad_b

    # Status legend
    legend = "".join(
        f"<rect x='{8 + i * 120}' y='4' width='10' height='8' fill='{STATUS_COLORS[s]}'/>"
        f"<text x='{22 + i * 120}' y='12' fill='#cbd5e1' font-size='9'>{s}</text>"
        for i, s in enumerate(STATUS_COLORS)
    )

    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{total_h}' "
        f"style='background:#0f172a;border-radius:6px'>"
        f"{legend}{''.join(bars)}</svg>"
    )


def _svg_sr_improvement(w: int = 680, h: int = 180) -> str:
    """Before/after SR grouped bar chart for completed jobs."""
    completed = [j for j in JOBS if j.status == "COMPLETED"]
    n = len(completed)
    if n == 0:
        return f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}'></svg>"

    pad_l, pad_r, pad_t, pad_b = 48, 20, 20, 36
    ch = h - pad_t - pad_b
    cw = w - pad_l - pad_r

    group_w = cw / n
    bar_w   = group_w * 0.30
    max_sr  = 1.0

    def y_top(sr: float) -> float:
        return pad_t + ch * (1 - sr / max_sr)

    def bar_h_px(sr: float) -> float:
        return ch * sr / max_sr

    bars = []
    for idx, job in enumerate(completed):
        gx = pad_l + idx * group_w + group_w * 0.1
        # Before bar (sky blue)
        if job.sr_before is not None:
            bx = gx
            bars.append(
                f"<rect x='{bx:.1f}' y='{y_top(job.sr_before):.1f}' "
                f"width='{bar_w:.1f}' height='{bar_h_px(job.sr_before):.1f}' "
                f"fill='#38bdf8' opacity='0.85' rx='2'/>"
                f"<text x='{bx + bar_w/2:.1f}' y='{y_top(job.sr_before) - 4:.1f}' "
                f"fill='#38bdf8' font-size='9' text-anchor='middle'>{job.sr_before:.0%}</text>"
            )
        # After bar (Oracle red)
        if job.sr_after is not None:
            ax = gx + bar_w + 6
            bars.append(
                f"<rect x='{ax:.1f}' y='{y_top(job.sr_after):.1f}' "
                f"width='{bar_w:.1f}' height='{bar_h_px(job.sr_after):.1f}' "
                f"fill='#C74634' opacity='0.9' rx='2'/>"
                f"<text x='{ax + bar_w/2:.1f}' y='{y_top(job.sr_after) - 4:.1f}' "
                f"fill='#C74634' font-size='9' text-anchor='middle'>{job.sr_after:.0%}</text>"
            )
        # Group label
        label_x = gx + bar_w
        bars.append(
            f"<text x='{label_x:.1f}' y='{h - 4}' fill='#94a3b8' font-size='9' text-anchor='middle'>"
            f"{job.partner.replace('_', ' ')}</text>"
        )

    # Y grid lines
    grid = "".join(
        f"<line x1='{pad_l}' y1='{y_top(v):.1f}' x2='{w - pad_r}' y2='{y_top(v):.1f}' "
        f"stroke='#1e293b' stroke-width='1'/>"
        f"<text x='{pad_l - 4}' y='{y_top(v) + 3:.1f}' fill='#475569' font-size='8' text-anchor='end'>{v:.0%}</text>"
        for v in [0.0, 0.25, 0.5, 0.75, 1.0]
    )

    legend = (
        "<rect x='8' y='4' width='10' height='8' fill='#38bdf8'/>"
        "<text x='22' y='12' fill='#cbd5e1' font-size='9'>Before fine-tune</text>"
        "<rect x='140' y='4' width='10' height='8' fill='#C74634'/>"
        "<text x='154' y='12' fill='#cbd5e1' font-size='9'>After fine-tune</text>"
    )

    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' "
        f"style='background:#0f172a;border-radius:6px'>"
        f"{grid}{legend}{''.join(bars)}</svg>"
    )


# ── HTML dashboard builder ────────────────────────────────────────────────────

def _stat_card(label: str, value: str, color: str) -> str:
    return (
        f"<div class='card'>"
        f"<div class='val' style='color:{color}'>{value}</div>"
        f"<div class='lbl'>{label}</div>"
        f"</div>"
    )


def _build_dashboard_html() -> str:
    total_jobs  = len(JOBS)
    running     = sum(1 for j in JOBS if j.status == "RUNNING")
    completed   = sum(1 for j in JOBS if j.status == "COMPLETED")
    queued      = sum(1 for j in JOBS if j.status == "QUEUED")
    total_billed = sum(j.cost_usd for j in JOBS)

    stat_cards = "".join([
        _stat_card("Total Jobs",     str(total_jobs),         "#38bdf8"),
        _stat_card("Running",        str(running),            "#38bdf8"),
        _stat_card("Completed",      str(completed),          "#22c55e"),
        _stat_card("Queued",         str(queued),             "#64748b"),
        _stat_card("Total Billed",   f"${total_billed:.2f}", "#f59e0b"),
    ])

    job_rows = "".join(
        f"<tr>"
        f"<td>{j.job_id}</td>"
        f"<td style='color:{PARTNER_COLORS.get(j.partner, "#888")}'>{j.partner}</td>"
        f"<td>{j.model_base}</td>"
        f"<td>{j.dataset}</td>"
        f"<td><span style='background:{STATUS_COLORS[j.status]};color:#0f172a;"
        f"padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold'>{j.status}</span></td>"
        f"<td>{j.steps_done:,} / {j.target_steps:,}</td>"
        f"<td>{j.pct_complete:.1f}%</td>"
        f"<td>{j.sr_after if j.sr_after is not None else '—'}</td>"
        f"<td>{j.mae if j.mae is not None else '—'}</td>"
        f"<td style='color:#f59e0b'>${j.cost_usd:.2f}</td>"
        f"</tr>"
        for j in JOBS
    )

    svg_bars = _svg_progress_bars()
    svg_sr   = _svg_sr_improvement()

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset='UTF-8'/>
  <title>OCI Robot Cloud — Fine-Tune Progress</title>
  <style>
    body   {{ background:#0f172a; color:#e2e8f0; font-family:monospace; padding:24px; margin:0 }}
    h1     {{ color:#C74634; margin-bottom:4px }}
    h2     {{ color:#38bdf8; font-size:14px; margin:24px 0 8px }}
    .cards {{ display:flex; gap:12px; flex-wrap:wrap; margin:16px 0 }}
    .card  {{ background:#1e293b; border-radius:8px; padding:14px 20px; min-width:120px }}
    .card .val {{ font-size:22px; font-weight:bold; color:#f8fafc }}
    .card .lbl {{ font-size:11px; color:#64748b; margin-top:4px }}
    table  {{ border-collapse:collapse; width:100%; margin-bottom:16px }}
    th     {{ background:#1e293b; color:#C74634; padding:8px 10px; text-align:left; font-size:12px }}
    td     {{ padding:6px 10px; border-bottom:1px solid #1e293b; font-size:12px }}
    tr:hover td {{ background:#1a2744 }}
    footer {{ color:#334155; font-size:11px; margin-top:28px }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Fine-Tune Job Progress</h1>
  <p style='color:#64748b;font-size:12px'>Port {PORT} | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} | {total_jobs} jobs</p>

  <div class='cards'>{stat_cards}</div>

  <h2>Job Progress</h2>
  {svg_bars}

  <h2>Success Rate Improvement (Completed Jobs)</h2>
  {svg_sr}

  <h2>Job Details</h2>
  <table>
    <tr><th>Job ID</th><th>Partner</th><th>Base Model</th><th>Dataset</th><th>Status</th><th>Steps</th><th>%</th><th>SR</th><th>MAE</th><th>Cost</th></tr>
    {job_rows}
  </table>

  <footer>Oracle Cloud Infrastructure | OCI Robot Cloud | finetune_progress_api.py | Port {PORT}</footer>
</body>
</html>"""


# ── FastAPI app ───────────────────────────────────────────────────────────────

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse

    app = FastAPI(
        title="OCI Robot Cloud — Fine-Tune Progress API",
        version="1.0.0",
        description="Partner-facing fine-tune job status and metrics.",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return _build_dashboard_html()

    @app.get("/jobs")
    def get_jobs():
        return JSONResponse([asdict(j) for j in JOBS])

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str):
        if job_id not in JOBS_BY_ID:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        return JSONResponse(asdict(JOBS_BY_ID[job_id]))

    @app.get("/jobs/{job_id}/metrics")
    def get_job_metrics(job_id: str):
        if job_id not in JOBS_BY_ID:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        job = JOBS_BY_ID[job_id]
        return JSONResponse({
            "job_id":       job.job_id,
            "partner":      job.partner,
            "status":       job.status,
            "steps_done":   job.steps_done,
            "target_steps": job.target_steps,
            "pct_complete": job.pct_complete,
            "loss_history": _loss_history(job),
            "sr_before":    job.sr_before,
            "sr_after":     job.sr_after,
            "mae":          job.mae,
        })

    @app.get("/summary")
    def get_summary():
        total_billed = sum(j.cost_usd for j in JOBS)
        return JSONResponse({
            "total_jobs":   len(JOBS),
            "running":      sum(1 for j in JOBS if j.status == "RUNNING"),
            "completed":    sum(1 for j in JOBS if j.status == "COMPLETED"),
            "queued":       sum(1 for j in JOBS if j.status == "QUEUED"),
            "total_billed_usd": round(total_billed, 2),
            "partners":     list({j.partner for j in JOBS}),
        })

except ImportError:
    app = None


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    sep = "=" * 72
    print(sep)
    print("OCI Robot Cloud — Fine-Tune Progress API")
    print(f"Port {PORT}  |  {len(JOBS)} jobs")
    print(sep)

    total_billed = sum(j.cost_usd for j in JOBS)
    running   = sum(1 for j in JOBS if j.status == "RUNNING")
    completed = sum(1 for j in JOBS if j.status == "COMPLETED")
    queued    = sum(1 for j in JOBS if j.status == "QUEUED")
    print(f"\nRunning: {running}  Completed: {completed}  Queued: {queued}  Total billed: ${total_billed:.2f}")

    print(f"\n{'Job ID':<16} {'Partner':<26} {'Status':<12} {'Steps':>12} {'%':>6} {'Cost':>8}")
    print("-" * 84)
    for j in JOBS:
        print(
            f"{j.job_id:<16} {j.partner:<26} {j.status:<12} "
            f"{j.steps_done:>6,}/{j.target_steps:<6,} {j.pct_complete:>5.1f}% ${j.cost_usd:>6.2f}"
        )

    print("\nSuccess Rate Improvement (completed):")
    for j in JOBS:
        if j.status == "COMPLETED" and j.sr_before is not None and j.sr_after is not None:
            delta = (j.sr_after - j.sr_before) * 100
            print(f"  {j.job_id}: {j.sr_before:.0%} → {j.sr_after:.0%}  (+{delta:.1f}pp)  MAE={j.mae}")
    print(sep)


if __name__ == "__main__":
    main()

"""Offline Eval Pipeline Orchestrator — OCI Robot Cloud  (port 8201)

Batch-evaluates multiple GR00T checkpoints in parallel and tracks results.
"""

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None  # type: ignore
    HTTPException = None  # type: ignore
    HTMLResponse = None  # type: ignore
    JSONResponse = None  # type: ignore
    uvicorn = None  # type: ignore

import math
import json
from typing import Optional

# ---------------------------------------------------------------------------
# Static data store
# ---------------------------------------------------------------------------

CURRENT_PRODUCTION_SR = 0.76  # pre-groot-v2-step5000 baseline

BATCHES = {
    "eval_batch_001": {
        "batch_id": "eval_batch_001",
        "created": "2026-03-29T14:00:00Z",
        "estimated_duration_min": 48,
        "estimated_cost_usd": 1.84,
        "checkpoints": [
            {
                "ckpt_id": "ckpt_groot_v2_step3000",
                "step": 3000,
                "status": "COMPLETED",
                "sr": 0.71,
                "mae": 0.027,
                "episodes_done": 20,
                "episodes_total": 20,
                "cost_usd": 0.44,
            },
            {
                "ckpt_id": "ckpt_groot_v2_step4000",
                "step": 4000,
                "status": "COMPLETED",
                "sr": 0.75,
                "mae": 0.025,
                "episodes_done": 20,
                "episodes_total": 20,
                "cost_usd": 0.46,
            },
            {
                "ckpt_id": "ckpt_groot_v2_step5000",
                "step": 5000,
                "status": "COMPLETED",
                "sr": 0.78,
                "mae": 0.023,
                "episodes_done": 20,
                "episodes_total": 20,
                "cost_usd": 0.48,
            },
            {
                "ckpt_id": "ckpt_groot_v3_step2000",
                "step": 2000,
                "status": "RUNNING",
                "sr": None,
                "mae": None,
                "episodes_done": 12,
                "episodes_total": 20,
                "cost_usd": 0.46,  # estimated
            },
        ],
    }
}


def _best_checkpoint(batch: dict) -> Optional[dict]:
    completed = [c for c in batch["checkpoints"] if c["status"] == "COMPLETED"]
    if not completed:
        return None
    return max(completed, key=lambda c: c["sr"])


def _promotion_recommendation(batch: dict) -> str:
    best = _best_checkpoint(batch)
    if best is None:
        return "No completed checkpoints yet."
    if best["sr"] > CURRENT_PRODUCTION_SR + 0.02:
        return (
            f"RECOMMEND promotion: {best['ckpt_id']} (SR={best['sr']}) "
            f"exceeds production by {best['sr']-CURRENT_PRODUCTION_SR:.2f}"
        )
    return (
        f"{best['ckpt_id']} already PRODUCTION — await groot_v3 completion"
    )


# ---------------------------------------------------------------------------
# SVG: SR vs step line chart  (680 × 220)
# ---------------------------------------------------------------------------

def _sr_line_svg(batch: dict) -> str:
    W, H = 680, 220
    PAD_L, PAD_R, PAD_T, PAD_B = 64, 40, 28, 44
    cw = W - PAD_L - PAD_R
    ch = H - PAD_T - PAD_B

    completed = [c for c in batch["checkpoints"] if c["status"] == "COMPLETED"]
    running   = [c for c in batch["checkpoints"] if c["status"] == "RUNNING"]

    steps = [c["step"] for c in completed]
    srs   = [c["sr"]   for c in completed]

    min_step, max_step = (min(steps), max(steps)) if steps else (0, 5000)
    min_sr,   max_sr   = 0.60, 0.85

    def sx(step):
        return PAD_L + (step - min_step) / max(max_step - min_step, 1) * cw

    def sy(sr):
        return PAD_T + ch - (sr - min_sr) / max(max_sr - min_sr, 0.01) * ch

    # Grid lines
    grid = ""
    for sr_tick in [0.60, 0.65, 0.70, 0.75, 0.80, 0.85]:
        y = sy(sr_tick)
        grid += f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W-PAD_R}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>\n'
        grid += f'<text x="{PAD_L-6}" y="{y+4:.1f}" text-anchor="end" fill="#475569" font-size="10" font-family="monospace">{sr_tick:.2f}</text>\n'

    for s_tick in [3000, 4000, 5000]:
        x = sx(s_tick)
        grid += f'<line x1="{x:.1f}" y1="{PAD_T}" x2="{x:.1f}" y2="{H-PAD_B}" stroke="#1e293b" stroke-width="1"/>\n'
        grid += f'<text x="{x:.1f}" y="{H-PAD_B+14}" text-anchor="middle" fill="#475569" font-size="10" font-family="monospace">{s_tick}</text>\n'

    # Line path
    path_d = ""
    for i, (step, sr) in enumerate(zip(steps, srs)):
        cmd = "M" if i == 0 else "L"
        path_d += f"{cmd}{sx(step):.1f},{sy(sr):.1f} "

    path_el = f'<path d="{path_d.strip()}" fill="none" stroke="#C74634" stroke-width="2.5"/>\n' if path_d else ""

    # Dots + star on best
    best = _best_checkpoint(batch)
    dots = ""
    for c in completed:
        x, y = sx(c["step"]), sy(c["sr"])
        is_best = best and c["ckpt_id"] == best["ckpt_id"]
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{"#38bdf8" if is_best else "#C74634"}" stroke="#0f172a" stroke-width="1.5"/>\n'
        if is_best:
            dots += f'<text x="{x:.1f}" y="{y-10:.1f}" text-anchor="middle" fill="#38bdf8" font-size="14">★</text>\n'
        dots += f'<text x="{x+6:.1f}" y="{y-8:.1f}" fill="#94a3b8" font-size="9" font-family="monospace">{c["sr"]}</text>\n'

    # Running checkpoint dashed line extension
    dashed = ""
    if running and steps:
        last_step, last_sr = steps[-1], srs[-1]
        for rc in running:
            rx, ry = sx(rc["step"]), sy(last_sr)  # project at same SR (unknown)
            dashed += (f'<line x1="{sx(last_step):.1f}" y1="{sy(last_sr):.1f}" '
                       f'x2="{rx:.1f}" y2="{ry:.1f}" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="5,4"/>\n')
            dashed += f'<circle cx="{rx:.1f}" cy="{ry:.1f}" r="4" fill="none" stroke="#38bdf8" stroke-width="1.5"/>\n'
            dashed += f'<text x="{rx+6:.1f}" y="{ry-8:.1f}" fill="#38bdf8" font-size="9" font-family="monospace">running…</text>\n'

    # Axes
    axes = (
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{H-PAD_B}" stroke="#475569" stroke-width="1"/>\n'
        f'<line x1="{PAD_L}" y1="{H-PAD_B}" x2="{W-PAD_R}" y2="{H-PAD_B}" stroke="#475569" stroke-width="1"/>\n'
        f'<text x="{PAD_L + cw//2}" y="{H-4}" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace">Checkpoint Step</text>\n'
        f'<text x="14" y="{PAD_T + ch//2}" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace" transform="rotate(-90,14,{PAD_T + ch//2})">Success Rate</text>\n'
    )

    title = f'<text x="{W//2}" y="16" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace" font-weight="bold">SR vs Checkpoint Step — eval_batch_001</text>\n'

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'style="background:#1e293b;border-radius:8px">\n'
            f'{title}{grid}{path_el}{dashed}{dots}{axes}\n</svg>')


# ---------------------------------------------------------------------------
# SVG: parallel eval status bars  (680 × 140)
# ---------------------------------------------------------------------------

def _status_bars_svg(batch: dict) -> str:
    W, H = 680, 140
    ckpts = batch["checkpoints"]
    n = len(ckpts)
    row_h = (H - 20) / n
    BAR_X, BAR_MAX_W = 200, 380

    STATUS_COLOR = {"COMPLETED": "#22c55e", "RUNNING": "#38bdf8", "QUEUED": "#475569"}

    rows = ""
    for i, c in enumerate(ckpts):
        y = 10 + i * row_h
        pct = c["episodes_done"] / c["episodes_total"]
        bar_w = pct * BAR_MAX_W
        color = STATUS_COLOR.get(c["status"], "#475569")
        # pulse animation for RUNNING
        anim = ""
        if c["status"] == "RUNNING":
            anim = f' opacity="0.85"><animate attributeName="opacity" values="0.5;1;0.5" dur="1.6s" repeatCount="indefinite"/>'
            color_close = ""
        else:
            anim = ">"
            color_close = ""

        rows += (
            f'<text x="8" y="{y+14:.1f}" fill="#94a3b8" font-size="10" font-family="monospace">{c["ckpt_id"]}</text>\n'
            f'<rect x="{BAR_X}" y="{y+4:.1f}" width="{BAR_MAX_W}" height="14" rx="3" fill="#334155"/>\n'
            f'<rect x="{BAR_X}" y="{y+4:.1f}" width="{bar_w:.1f}" height="14" rx="3" fill="{color}"{anim}</rect>\n'
            f'<text x="{BAR_X+BAR_MAX_W+8}" y="{y+15:.1f}" fill="#64748b" font-size="10" font-family="monospace">{c["episodes_done"]}/{c["episodes_total"]} ep</text>\n'
        )

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'style="background:#1e293b;border-radius:8px">\n{rows}</svg>')


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    batch = BATCHES["eval_batch_001"]
    sr_svg = _sr_line_svg(batch)
    bar_svg = _status_bars_svg(batch)
    recommendation = _promotion_recommendation(batch)
    best = _best_checkpoint(batch)

    table_rows = ""
    for c in batch["checkpoints"]:
        status_color = {"COMPLETED": "#22c55e", "RUNNING": "#38bdf8", "QUEUED": "#94a3b8"}.get(c["status"], "#94a3b8")
        sr_str = f"{c['sr']}" if c["sr"] is not None else "—"
        mae_str = f"{c['mae']}" if c["mae"] is not None else "—"
        star = " ★" if best and c["ckpt_id"] == best["ckpt_id"] else ""
        table_rows += (
            f'<tr>'
            f'<td>{c["ckpt_id"]}{star}</td>'
            f'<td>{c["step"]}</td>'
            f'<td style="color:{status_color}">{c["status"]}</td>'
            f'<td style="color:#38bdf8">{sr_str}</td>'
            f'<td>{mae_str}</td>'
            f'<td>{c["episodes_done"]}/{c["episodes_total"]}</td>'
            f'<td>${c["cost_usd"]:.2f}</td>'
            f'</tr>\n'
        )

    rec_color = "#22c55e" if "RECOMMEND" in recommendation else "#38bdf8"

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Offline Eval Pipeline — OCI Robot Cloud</title>
<style>
  body{{margin:0;padding:24px;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;line-height:1.6}}
  h1{{color:#C74634;font-size:1.4rem;margin-bottom:4px}}
  h2{{color:#C74634;font-size:.95rem;text-transform:uppercase;letter-spacing:.08em;border-bottom:1px solid #1e293b;padding-bottom:4px;margin-top:28px}}
  .subtitle{{color:#64748b;font-size:.88rem;margin-bottom:24px}}
  .stat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}}
  .stat{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px}}
  .stat-val{{font-size:1.6rem;font-weight:700;color:#38bdf8}}
  .stat-lbl{{font-size:.78rem;color:#64748b;margin-top:2px}}
  .svg-wrap{{margin:12px 0;overflow-x:auto}}
  table{{border-collapse:collapse;width:100%;margin-top:8px}}
  th,td{{padding:7px 10px;border:1px solid #1e293b;font-size:.84rem}}
  th{{background:#1e293b;color:#94a3b8;text-align:left}}
  td{{color:#cbd5e1}}
  .rec{{background:#1e293b;border:1px solid #334155;border-radius:6px;padding:14px;margin-top:16px;color:{rec_color};font-size:.9rem}}
  .ep{{background:#0f172a;border:1px solid #334155;border-radius:6px;padding:12px;font-size:.82rem;color:#64748b;margin-top:24px}}
</style></head>
<body>
<h1>Offline Eval Pipeline</h1>
<div class="subtitle">OCI Robot Cloud · Port 8201 · Batch checkpoint evaluation orchestrator</div>

<div class="stat-grid">
  <div class="stat"><div class="stat-val">4</div><div class="stat-lbl">Checkpoints</div></div>
  <div class="stat"><div class="stat-val">80</div><div class="stat-lbl">Total Episodes</div></div>
  <div class="stat"><div class="stat-val">{batch['estimated_duration_min']}m</div><div class="stat-lbl">Est. Duration</div></div>
  <div class="stat"><div class="stat-val">${batch['estimated_cost_usd']}</div><div class="stat-lbl">Est. Cost</div></div>
</div>

<h2>SR vs Checkpoint Step</h2>
<div class="svg-wrap">{sr_svg}</div>

<h2>Parallel Eval Status</h2>
<div class="svg-wrap">{bar_svg}</div>

<h2>Batch Summary — eval_batch_001</h2>
<table>
  <tr><th>Checkpoint</th><th>Step</th><th>Status</th><th>SR</th><th>MAE</th><th>Episodes</th><th>Cost</th></tr>
  {table_rows}
</table>

<div class="rec"><b>Auto-Promotion:</b> {recommendation}</div>

<div class="ep">
  <b style="color:#94a3b8">Endpoints</b><br>
  GET /batches — list all batches<br>
  GET /batches/{{batch_id}} — batch metadata<br>
  GET /batches/{{batch_id}}/results — full results JSON<br>
  POST /batches/create — create new eval batch
</div>
</body></html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(
        title="Offline Eval Pipeline",
        description="Batch-evaluates multiple GR00T checkpoints in parallel",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _dashboard_html()

    @app.get("/batches")
    def list_batches():
        return [
            {
                "batch_id": bid,
                "checkpoints": len(b["checkpoints"]),
                "estimated_cost_usd": b["estimated_cost_usd"],
                "created": b["created"],
            }
            for bid, b in BATCHES.items()
        ]

    @app.get("/batches/{batch_id}")
    def get_batch(batch_id: str):
        if batch_id not in BATCHES:
            raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
        b = BATCHES[batch_id]
        best = _best_checkpoint(b)
        return {
            **b,
            "best_checkpoint": best["ckpt_id"] if best else None,
            "promotion_recommendation": _promotion_recommendation(b),
        }

    @app.get("/batches/{batch_id}/results")
    def get_results(batch_id: str):
        if batch_id not in BATCHES:
            raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
        b = BATCHES[batch_id]
        completed = [c for c in b["checkpoints"] if c["status"] == "COMPLETED"]
        return {
            "batch_id": batch_id,
            "completed_checkpoints": len(completed),
            "total_checkpoints": len(b["checkpoints"]),
            "best": _best_checkpoint(b),
            "promotion_recommendation": _promotion_recommendation(b),
            "checkpoints": b["checkpoints"],
        }

    @app.post("/batches/create", status_code=201)
    def create_batch(batch: dict):
        """Create a new eval batch. Body: {batch_id, checkpoints: [{ckpt_id, step}]}"""
        bid = batch.get("batch_id")
        if not bid:
            raise HTTPException(status_code=400, detail="batch_id required")
        if bid in BATCHES:
            raise HTTPException(status_code=409, detail=f"Batch '{bid}' already exists")
        ckpts = batch.get("checkpoints", [])
        BATCHES[bid] = {
            "batch_id": bid,
            "created": "2026-03-30T00:00:00Z",
            "estimated_duration_min": len(ckpts) * 12,
            "estimated_cost_usd": round(len(ckpts) * 0.46, 2),
            "checkpoints": [
                {
                    "ckpt_id": c["ckpt_id"],
                    "step": c.get("step", 0),
                    "status": "QUEUED",
                    "sr": None,
                    "mae": None,
                    "episodes_done": 0,
                    "episodes_total": c.get("episodes_total", 20),
                    "cost_usd": 0.0,
                }
                for c in ckpts
            ],
        }
        return {"batch_id": bid, "status": "QUEUED", "checkpoints": len(ckpts)}


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed — pip install uvicorn fastapi")
    uvicorn.run("offline_eval_pipeline:app", host="0.0.0.0", port=8201, reload=False)

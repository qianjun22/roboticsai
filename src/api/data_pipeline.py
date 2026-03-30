"""Data Pipeline Tracker — FastAPI port 8133

Status dashboard for the 5-stage SDG → LeRobot → OCI data pipeline.
"""

import json
from typing import Dict, Any, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse
    import uvicorn
except ImportError:  # pragma: no cover
    raise ImportError("Install fastapi and uvicorn: pip install fastapi uvicorn")

app = FastAPI(title="Data Pipeline Tracker", version="1.0.0")

# ---------------------------------------------------------------------------
# Stage data
# ---------------------------------------------------------------------------

STAGES: Dict[str, Dict[str, Any]] = {
    "genesis_sdg": {
        "id": "genesis_sdg",
        "label": "Genesis SDG",
        "status": "COMPLETED",
        "throughput": 847,
        "throughput_unit": "demos/hr",
        "total_demos": 2000,
        "duration": 2.4,
        "output_gb": 9.8,
        "depends_on": None,
        "order": 0,
    },
    "data_validation": {
        "id": "data_validation",
        "label": "Data Validation",
        "status": "COMPLETED",
        "throughput": 1200,
        "throughput_unit": "demos/hr",
        "pass_rate": 0.97,
        "rejected": 60,
        "duration": 1.7,
        "depends_on": "genesis_sdg",
        "order": 1,
    },
    "augmentation": {
        "id": "augmentation",
        "label": "Augmentation",
        "status": "RUNNING",
        "throughput": 523,
        "throughput_unit": "demos/hr",
        "augmented": 1340,
        "augmented_total": 1940,
        "eta": 1.8,
        "duration": 2.6,
        "depends_on": "data_validation",
        "order": 2,
    },
    "lerobotformat": {
        "id": "lerobotformat",
        "label": "LeRobot Format",
        "status": "PENDING",
        "throughput": None,
        "throughput_unit": "demos/hr",
        "est_duration": 0.8,
        "depends_on": "augmentation",
        "order": 3,
    },
    "upload_to_oci": {
        "id": "upload_to_oci",
        "label": "Upload to OCI",
        "status": "PENDING",
        "throughput": None,
        "throughput_unit": "demos/hr",
        "est_duration": 0.3,
        "depends_on": "lerobotformat",
        "order": 4,
    },
}

STATUS_COLOR = {
    "COMPLETED": "#4ade80",
    "RUNNING": "#38bdf8",
    "PENDING": "#475569",
}

# ---------------------------------------------------------------------------
# SVG: Pipeline DAG
# ---------------------------------------------------------------------------

def _dag_svg() -> str:
    """680x160 SVG with 5 boxes + connecting arrows."""
    W, H = 680, 160
    n = len(STAGES)
    box_w, box_h = 108, 56
    gap = (W - n * box_w) // (n + 1)
    boxes_y = (H - box_h) // 2

    ordered = sorted(STAGES.values(), key=lambda s: s["order"])
    boxes_x = [gap + i * (box_w + gap) for i in range(n)]

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px;">']

    # Arrows
    for i in range(n - 1):
        x1 = boxes_x[i] + box_w
        x2 = boxes_x[i + 1]
        my = boxes_y + box_h // 2
        status_next = ordered[i + 1]["status"]
        arrow_color = "#334155" if status_next == "PENDING" else "#64748b"
        parts.append(
            f'<line x1="{x1}" y1="{my}" x2="{x2}" y2="{my}" '
            f'stroke="{arrow_color}" stroke-width="2" marker-end="url(#arr)"/>'
        )

    # Arrow marker def
    parts.insert(1,
        '<defs><marker id="arr" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">'
        '<path d="M0,0 L0,6 L6,3 z" fill="#64748b"/></marker></defs>'
    )

    # Boxes
    for i, stage in enumerate(ordered):
        x = boxes_x[i]
        color = STATUS_COLOR[stage["status"]]
        border = color

        # Pulsing animation for RUNNING
        anim = ""
        if stage["status"] == "RUNNING":
            anim = (
                f'<animate attributeName="opacity" values="1;0.55;1" '
                f'dur="1.6s" repeatCount="indefinite"/>'
            )

        # Key metric text
        if stage["status"] == "COMPLETED":
            metric = f"{stage.get('throughput', '')} demos/hr"
        elif stage["status"] == "RUNNING":
            aug = stage.get("augmented", 0)
            tot = stage.get("augmented_total", 1)
            metric = f"{aug}/{tot} done"
        else:
            metric = f"est {stage.get('est_duration', '?')}h"

        parts.append(
            f'<rect x="{x}" y="{boxes_y}" width="{box_w}" height="{box_h}" '
            f'rx="6" fill="#0f172a" stroke="{border}" stroke-width="2">{anim}</rect>'
            f'<text x="{x + box_w//2}" y="{boxes_y + 18}" fill="{color}" '
            f'font-size="11" font-weight="600" text-anchor="middle">{stage["label"]}</text>'
            f'<text x="{x + box_w//2}" y="{boxes_y + 32}" fill="#94a3b8" '
            f'font-size="9" text-anchor="middle">{stage["status"]}</text>'
            f'<text x="{x + box_w//2}" y="{boxes_y + 46}" fill="#64748b" '
            f'font-size="9" text-anchor="middle">{metric}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# SVG: Throughput bar chart
# ---------------------------------------------------------------------------

def _throughput_svg() -> str:
    """680x180 bar chart — throughput for stages with data."""
    W, H = 680, 180
    PAD_L, PAD_R, PAD_T, PAD_B = 120, 20, 18, 30
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B

    active = [
        s for s in sorted(STAGES.values(), key=lambda s: s["order"])
        if s["throughput"] is not None
    ]
    if not active:
        return "<svg width='680' height='180' style='background:#1e293b;border-radius:8px;'/>"

    max_tp = max(s["throughput"] for s in active)
    bar_h = chart_h // len(active) - 8

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">'
    ]

    for i, stage in enumerate(active):
        y = PAD_T + i * (chart_h // len(active))
        bar_len = (stage["throughput"] / max_tp) * chart_w
        color = STATUS_COLOR[stage["status"]]
        parts.append(
            f'<text x="{PAD_L - 6}" y="{y + bar_h//2 + 4}" fill="#94a3b8" '
            f'font-size="10" text-anchor="end">{stage["label"]}</text>'
            f'<rect x="{PAD_L}" y="{y}" width="{bar_len:.1f}" height="{bar_h}" '
            f'rx="3" fill="{color}"/>'
            f'<text x="{PAD_L + bar_len + 6}" y="{y + bar_h//2 + 4}" '
            f'fill="#cbd5e1" font-size="10">{stage["throughput"]} demos/hr</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def _stage_table_html() -> str:
    ordered = sorted(STAGES.values(), key=lambda s: s["order"])
    rows = ""
    for stage in ordered:
        color = STATUS_COLOR[stage["status"]]
        badge = (
            f'<span style="background:{color}22;color:{color};border:1px solid {color};'
            f'border-radius:4px;padding:1px 7px;font-size:11px;">'
            f'{stage["status"]}</span>'
        )
        tp = f"{stage['throughput']} demos/hr" if stage["throughput"] else "—"
        if stage["status"] == "COMPLETED":
            dur = f"{stage.get('duration', '?')}h elapsed"
        elif stage["status"] == "RUNNING":
            dur = f"{stage.get('duration', '?')}h elapsed / ETA {stage.get('eta', '?')}h"
        else:
            dur = f"est {stage.get('est_duration', '?')}h"
        dep = stage["depends_on"] or "—"
        rows += (
            f"<tr><td>{stage['label']}</td><td>{badge}</td>"
            f"<td>{tp}</td><td>{dur}</td><td>{dep}</td></tr>"
        )
    return rows


# ---------------------------------------------------------------------------
# Dashboard HTML template
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Data Pipeline Tracker — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Inter', 'Segoe UI', sans-serif; padding: 24px; }}
  h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
  .sub {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
  .cards {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }}
  .card {{ background: #1e293b; border-radius: 10px; padding: 16px 22px; min-width: 150px; flex: 1; }}
  .card-label {{ color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }}
  .card-value {{ color: #38bdf8; font-size: 26px; font-weight: 700; margin-top: 4px; }}
  .card-unit {{ color: #94a3b8; font-size: 12px; }}
  .section {{ background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 24px; }}
  .section-title {{ color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ color: #64748b; font-weight: 500; text-align: left; padding: 8px 10px; border-bottom: 1px solid #334155; }}
  td {{ padding: 9px 10px; border-bottom: 1px solid #0f172a; color: #cbd5e1; }}
  tr:last-child td {{ border-bottom: none; }}
</style>
</head>
<body>
<h1>Data Pipeline Tracker</h1>
<p class="sub">OCI Robot Cloud &mdash; port 8133 &mdash; {ts}</p>

<div class="cards">
  <div class="card"><div class="card-label">Total Demos</div><div class="card-value">2,000</div><div class="card-unit">generated</div></div>
  <div class="card"><div class="card-label">Validated</div><div class="card-value">1,940</div><div class="card-unit">97% pass rate</div></div>
  <div class="card"><div class="card-label">Augmented</div><div class="card-value">1,340</div><div class="card-unit">of 1,940 (69%)</div></div>
  <div class="card"><div class="card-label">Pipeline</div><div class="card-value">3/5</div><div class="card-unit">stages complete</div></div>
</div>

<div class="section">
  <div class="section-title">Pipeline DAG</div>
  {dag_svg}
</div>

<div class="section">
  <div class="section-title">Throughput by Stage</div>
  {throughput_svg}
</div>

<div class="section">
  <div class="section-title">Stage Details</div>
  <table>
    <thead><tr><th>Stage</th><th>Status</th><th>Throughput</th><th>Duration / ETA</th><th>Depends On</th></tr></thead>
    <tbody>{stage_rows}</tbody>
  </table>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    import datetime
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    html = DASHBOARD_HTML.format(
        ts=ts,
        dag_svg=_dag_svg(),
        throughput_svg=_throughput_svg(),
        stage_rows=_stage_table_html(),
    )
    return HTMLResponse(content=html)


@app.get("/stages")
async def list_stages():
    ordered = sorted(STAGES.values(), key=lambda s: s["order"])
    return {"stages": ordered, "count": len(ordered)}


@app.get("/stages/{stage_id}")
async def get_stage(stage_id: str):
    if stage_id not in STAGES:
        raise HTTPException(status_code=404, detail=f"Stage '{stage_id}' not found")
    return STAGES[stage_id]


@app.get("/summary")
async def summary():
    completed = sum(1 for s in STAGES.values() if s["status"] == "COMPLETED")
    running = sum(1 for s in STAGES.values() if s["status"] == "RUNNING")
    pending = sum(1 for s in STAGES.values() if s["status"] == "PENDING")
    return {
        "total_stages": len(STAGES),
        "completed": completed,
        "running": running,
        "pending": pending,
        "total_demos": 2000,
        "validated_demos": 1940,
        "augmented_demos": 1340,
        "pass_rate": 0.97,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("data_pipeline:app", host="0.0.0.0", port=8133, reload=True)

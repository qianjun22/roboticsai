"""\nOCI Robot Cloud — Pipeline Orchestrator Dashboard\nPort 8120 | Manages full GR00T training pipelines (SDG → finetune → eval → promote)\n"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise SystemExit(f"Required dependency missing: {e}. Install with: pip install fastapi uvicorn")

import json
from datetime import datetime

app = FastAPI(title="OCI Robot Cloud — Pipeline Orchestrator", version="1.0.0")

# ---------------------------------------------------------------------------
# Static pipeline data
# ---------------------------------------------------------------------------

STAGE_NAMES = ["genesis_sdg", "format_convert", "groot_finetune", "eval", "promote"]

PIPELINES = {
    "sdg_to_prod_v1": {
        "name": "sdg_to_prod_v1",
        "status": "COMPLETED",
        "started": "2026-03-20T08:14:00Z",
        "finished": "2026-03-20T11:24:00Z",
        "gpu_hours": 3.2,
        "cost_usd": 9.79,
        "output_sr": 0.78,
        "eta_min": None,
        "stages": [
            {"name": "genesis_sdg",     "status": "DONE",        "pct": 100},
            {"name": "format_convert",  "status": "DONE",        "pct": 100},
            {"name": "groot_finetune",  "status": "DONE",        "pct": 100},
            {"name": "eval",            "status": "DONE",        "pct": 100},
            {"name": "promote",         "status": "DONE",        "pct": 100},
        ],
    },
    "dagger_run10_pipeline": {
        "name": "dagger_run10_pipeline",
        "status": "RUNNING",
        "started": "2026-03-30T06:45:00Z",
        "finished": None,
        "gpu_hours": None,
        "cost_usd": None,
        "output_sr": None,
        "eta_min": 82,
        "stages": [
            {"name": "genesis_sdg",     "status": "DONE",        "pct": 100},
            {"name": "format_convert",  "status": "DONE",        "pct": 100},
            {"name": "groot_finetune",  "status": "IN_PROGRESS", "pct": 34},
            {"name": "eval",            "status": "PENDING",     "pct": 0},
            {"name": "promote",         "status": "PENDING",     "pct": 0},
        ],
    },
    "ablation_reward_v3": {
        "name": "ablation_reward_v3",
        "status": "QUEUED",
        "started": None,
        "finished": None,
        "gpu_hours": None,
        "cost_usd": None,
        "output_sr": None,
        "eta_min": 165,
        "stages": [
            {"name": "genesis_sdg",     "status": "PENDING",     "pct": 0},
            {"name": "format_convert",  "status": "PENDING",     "pct": 0},
            {"name": "groot_finetune",  "status": "PENDING",     "pct": 0},
            {"name": "eval",            "status": "PENDING",     "pct": 0},
            {"name": "promote",         "status": "PENDING",     "pct": 0},
        ],
    },
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

STATUS_COLOR = {
    "DONE":        "#22c55e",   # green
    "IN_PROGRESS": "#38bdf8",   # sky blue
    "PENDING":     "#475569",   # gray
}

STAGE_LABELS = {
    "genesis_sdg":    "Genesis\nSDG",
    "format_convert": "Format\nConvert",
    "groot_finetune": "GR00T\nFinetune",
    "eval":           "Eval",
    "promote":        "Promote",
}


def _stage_label(name: str) -> str:
    return STAGE_LABELS.get(name, name)


def build_pipeline_svg(stages: list) -> str:
    """700x180 horizontal stage flow diagram."""
    W, H = 700, 180
    n = len(stages)
    box_w, box_h = 96, 52
    gap = 18
    total = n * box_w + (n - 1) * gap
    x0 = (W - total) // 2
    cy = H // 2

    rects = []
    arrows = []
    for i, stage in enumerate(stages):
        sx = x0 + i * (box_w + gap)
        color = STATUS_COLOR.get(stage["status"], "#475569")
        pct = stage["pct"]
        label_lines = _stage_label(stage["name"]).split("\n")

        # progress fill (inner rect)
        fill_w = int(box_w * pct / 100)
        rects.append(
            f'<rect x="{sx}" y="{cy - box_h//2}" width="{box_w}" height="{box_h}" '
            f'rx="8" fill="#1e293b" stroke="{color}" stroke-width="2"/>'
        )
        if fill_w > 0:
            rects.append(
                f'<rect x="{sx}" y="{cy - box_h//2}" width="{fill_w}" height="{box_h}" '
                f'rx="8" fill="{color}" opacity="0.18"/>'
            )

        # stage label
        ty = cy - 8 if len(label_lines) == 2 else cy + 5
        for li, line in enumerate(label_lines):
            rects.append(
                f'<text x="{sx + box_w//2}" y="{ty + li*16}" '
                f'text-anchor="middle" fill="{color}" font-size="11" font-family="monospace">{line}</text>'
            )

        # pct badge
        if stage["status"] == "IN_PROGRESS":
            rects.append(
                f'<text x="{sx + box_w//2}" y="{cy + box_h//2 - 6}" '
                f'text-anchor="middle" fill="{color}" font-size="10" font-family="monospace">{pct}%</text>'
            )
        elif stage["status"] == "DONE":
            rects.append(
                f'<text x="{sx + box_w//2}" y="{cy + box_h//2 - 6}" '
                f'text-anchor="middle" fill="{color}" font-size="10" font-family="monospace">\u2713</text>'
            )

        # arrow to next
        if i < n - 1:
            ax = sx + box_w
            arrows.append(
                f'<line x1="{ax}" y1="{cy}" x2="{ax + gap}" y2="{cy}" '
                f'stroke="#334155" stroke-width="2" marker-end="url(#arr)"/>'
            )

    inner = "\n".join(arrows + rects)
    return f'''<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#334155"/>
    </marker>
  </defs>
  <rect width="{W}" height="{H}" fill="#0f172a" rx="10"/>
  {inner}
</svg>'''


# ---------------------------------------------------------------------------
# HTML dashboard helpers
# ---------------------------------------------------------------------------

STATUS_BADGE = {
    "COMPLETED":   ('<span style="background:#16a34a;color:#fff;padding:2px 10px;border-radius:12px;font-size:12px;">COMPLETED</span>', "#22c55e"),
    "RUNNING":     ('<span style="background:#0284c7;color:#fff;padding:2px 10px;border-radius:12px;font-size:12px;">RUNNING</span>',    "#38bdf8"),
    "QUEUED":      ('<span style="background:#78350f;color:#fef3c7;padding:2px 10px;border-radius:12px;font-size:12px;">QUEUED</span>',  "#f59e0b"),
    "FAILED":      ('<span style="background:#991b1b;color:#fff;padding:2px 10px;border-radius:12px;font-size:12px;">FAILED</span>',    "#ef4444"),
}


def _badge(status: str) -> str:
    return STATUS_BADGE.get(status, (f'<span>{status}</span>', "#94a3b8"))[0]


def _border(status: str) -> str:
    return STATUS_BADGE.get(status, ("", "#334155"))[1]


def _val(v, fmt="{}", fallback="\u2014"):
    return fmt.format(v) if v is not None else fallback


def pipeline_card(p: dict) -> str:
    svg = build_pipeline_svg(p["stages"])
    border = _border(p["status"])
    badge = _badge(p["status"])
    sr = f"{int(p['output_sr']*100)}% SR" if p["output_sr"] is not None else ""
    gpu = _val(p["gpu_hours"], "{:.1f} GPU-hrs")
    cost = _val(p["cost_usd"], "${:.2f}")
    eta = f"ETA {p['eta_min']} min" if p["eta_min"] else ""
    started = p["started"][:10] if p["started"] else "\u2014"

    meta_items = [x for x in [sr, gpu, cost, eta, f"Started {started}"] if x]
    meta_html = " &nbsp;\u00b7&nbsp; ".join(meta_items)

    return f'''
<div style="background:#1e293b;border:1px solid {border};border-radius:12px;padding:24px;margin-bottom:20px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
    <span style="font-family:monospace;font-size:16px;color:#f1f5f9;">{p["name"]}</span>
    {badge}
  </div>
  <div style="color:#94a3b8;font-size:12px;margin-bottom:16px;">{meta_html}</div>
  {svg}
</div>'''


def build_dashboard_html() -> str:
    pl = list(PIPELINES.values())
    running   = sum(1 for p in pl if p["status"] == "RUNNING")
    completed = sum(1 for p in pl if p["status"] == "COMPLETED")
    queued    = sum(1 for p in pl if p["status"] == "QUEUED")
    total_cost = sum(p["cost_usd"] for p in pl if p["cost_usd"] is not None)
    total_gpu  = sum(p["gpu_hours"] for p in pl if p["gpu_hours"] is not None)

    cards_html = "\n".join(pipeline_card(p) for p in pl)

    stat_cards = f'''
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px;">
  <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px;text-align:center;">
    <div style="font-size:28px;font-weight:700;color:#38bdf8;">{running}</div>
    <div style="color:#94a3b8;font-size:13px;margin-top:4px;">Running</div>
  </div>
  <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px;text-align:center;">
    <div style="font-size:28px;font-weight:700;color:#22c55e;">{completed}</div>
    <div style="color:#94a3b8;font-size:13px;margin-top:4px;">Completed</div>
  </div>
  <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px;text-align:center;">
    <div style="font-size:28px;font-weight:700;color:#f59e0b;">{queued}</div>
    <div style="color:#94a3b8;font-size:13px;margin-top:4px;">Queued</div>
  </div>
  <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px;text-align:center;">
    <div style="font-size:28px;font-weight:700;color:#C74634;">${total_cost:.2f}</div>
    <div style="color:#94a3b8;font-size:13px;margin-top:4px;">{total_gpu:.1f} GPU-hrs (7d)</div>
  </div>
</div>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>OCI Robot Cloud \u2014 Pipeline Orchestrator</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0;}}
    body{{background:#0f172a;color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh;}}
    .header{{background:#1e293b;border-bottom:2px solid #C74634;padding:18px 32px;display:flex;align-items:center;justify-content:space-between;}}
    .logo{{color:#C74634;font-weight:700;font-size:18px;letter-spacing:.5px;}}
    .subtitle{{color:#94a3b8;font-size:13px;margin-top:2px;}}
    .main{{padding:32px;max-width:900px;margin:0 auto;}}
    h2{{color:#38bdf8;font-size:15px;text-transform:uppercase;letter-spacing:1px;margin-bottom:16px;}}
    .footer{{text-align:center;color:#475569;font-size:11px;padding:24px;border-top:1px solid #1e293b;margin-top:16px;}}
  </style>
</head>
<body>
<div class="header">
  <div>
    <div class="logo">OCI Robot Cloud &mdash; Pipeline Orchestrator</div>
    <div class="subtitle">Full GR00T training pipeline management &nbsp;|&nbsp; Port 8120</div>
  </div>
  <div style="color:#94a3b8;font-size:12px;">{datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</div>
</div>
<div class="main">
  <h2 style="margin-top:24px;">Last 7 Days Overview</h2>
  {stat_cards}
  <h2>Pipeline Runs</h2>
  {cards_html}
</div>
<div class="footer">Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud Pipeline Orchestrator &nbsp;|&nbsp; Port 8120</div>
</body>
</html>'''


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return build_dashboard_html()


@app.get("/pipelines")
async def list_pipelines():
    return JSONResponse({"pipelines": list(PIPELINES.values()), "count": len(PIPELINES)})


@app.get("/pipelines/{name}")
async def get_pipeline(name: str):
    p = PIPELINES.get(name)
    if p is None:
        return JSONResponse({"error": f"Pipeline '{name}' not found"}, status_code=404)
    return JSONResponse(p)


@app.get("/stats")
async def stats():
    pl = list(PIPELINES.values())
    return JSONResponse({
        "running":   sum(1 for p in pl if p["status"] == "RUNNING"),
        "completed": sum(1 for p in pl if p["status"] == "COMPLETED"),
        "queued":    sum(1 for p in pl if p["status"] == "QUEUED"),
        "total_cost_usd": round(sum(p["cost_usd"] for p in pl if p["cost_usd"] is not None), 2),
        "total_gpu_hours": round(sum(p["gpu_hours"] for p in pl if p["gpu_hours"] is not None), 2),
    })


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "service": "pipeline_orchestrator", "port": 8120})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    try:
        uvicorn.run(app, host="0.0.0.0", port=8120, log_level="info")
    except Exception as exc:
        raise SystemExit(f"Failed to start server: {exc}")


if __name__ == "__main__":
    main()

"""Demo Script Runner — FastAPI service on port 8178.

Live demo orchestrator for conference/partner demos.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise ImportError("Install fastapi and uvicorn: pip install fastapi uvicorn") from e

app = FastAPI(title="OCI Robot Cloud — Demo Script Runner", version="1.0.0")

# ---------------------------------------------------------------------------
# Static demo data
# ---------------------------------------------------------------------------
DEMO_SCRIPTS: dict[str, dict] = {
    "quick_inference": {
        "id": "quick_inference",
        "name": "30-Second Inference Demo",
        "duration_s": 30,
        "steps": ["Load model", "Send obs", "Get action", "Execute"],
        "status": "READY",
        "last_run": "2026-03-30T14:22Z",
        "success": True,
        "note": None,
    },
    "sdg_to_finetune": {
        "id": "sdg_to_finetune",
        "name": "5-Minute SDG→Fine-tune",
        "duration_s": 300,
        "steps": ["Generate 50 demos", "Validate", "Train 100 steps", "Eval SR"],
        "status": "READY",
        "last_run": "2026-03-29T16:00Z",
        "success": True,
        "note": None,
    },
    "dagger_loop": {
        "id": "dagger_loop",
        "name": "DAgger Online Loop (2min)",
        "duration_s": 120,
        "steps": [
            "Run policy",
            "Collect failures",
            "Expert label",
            "Fine-tune 50 steps",
        ],
        "status": "READY",
        "last_run": "2026-03-28T11:00Z",
        "success": True,
        "note": None,
    },
    "cost_comparison": {
        "id": "cost_comparison",
        "name": "OCI vs AWS Cost Demo",
        "duration_s": 60,
        "steps": [
            "Show OCI $0.43/run",
            "Show AWS $4.14/run",
            "9.6× savings calculator",
        ],
        "status": "READY",
        "last_run": "2026-03-30T10:00Z",
        "success": True,
        "note": None,
    },
    "full_pipeline": {
        "id": "full_pipeline",
        "name": "Full Pipeline (10min)",
        "duration_s": 600,
        "steps": [
            "SDG→Validate→Augment→Finetune→Eval",
            "Live SR improvement",
        ],
        "status": "IN_PROGRESS",
        "last_run": None,
        "success": None,
        "note": "Integrating DAgger step",
    },
}

# Pre-flight checklist items
PREFLIGHT: list[dict] = [
    {"item": "inference_server UP", "ok": True},
    {"item": "model loaded", "ok": True},
    {"item": "demo data ready", "ok": True},
    {"item": "OCI connectivity", "ok": True},
    {"item": "screen share ready", "ok": True},
    {"item": "backup slides", "ok": True},
]

# Simulated run history: (script_id, day_offset_from_today, success)
# day_offset 0 = today, 6 = 6 days ago
_HISTORY_RAW: list[tuple[str, int, bool]] = [
    ("quick_inference", 0, True),
    ("quick_inference", 1, True),
    ("quick_inference", 2, True),
    ("quick_inference", 3, True),
    ("quick_inference", 4, False),
    ("quick_inference", 5, True),
    ("sdg_to_finetune", 0, True),
    ("sdg_to_finetune", 1, True),
    ("sdg_to_finetune", 3, False),
    ("sdg_to_finetune", 5, True),
    ("dagger_loop", 0, True),
    ("dagger_loop", 2, True),
    ("dagger_loop", 4, True),
    ("cost_comparison", 0, True),
    ("cost_comparison", 1, True),
    ("cost_comparison", 2, True),
    ("cost_comparison", 3, True),
    ("cost_comparison", 5, True),
    ("cost_comparison", 6, False),
]

_run_log: list[dict] = []  # in-memory triggered runs


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _build_timeline_svg() -> str:
    """Build a 680×160 timeline SVG: x=last 7 days, y=5 demo scripts."""
    W, H = 680, 160
    MARGIN_LEFT = 160
    MARGIN_RIGHT = 20
    MARGIN_TOP = 20
    MARGIN_BOT = 30

    script_ids = list(DEMO_SCRIPTS.keys())  # 5 scripts
    n_scripts = len(script_ids)
    n_days = 7  # 0..6 (0=today, 6=6 days ago displayed left→right reversed)

    plot_w = W - MARGIN_LEFT - MARGIN_RIGHT
    plot_h = H - MARGIN_TOP - MARGIN_BOT

    x_step = plot_w / (n_days - 1)  # spacing between day columns
    y_step = plot_h / (n_scripts - 1) if n_scripts > 1 else plot_h

    # Build lookup: (script_id, day_offset) -> success | None
    run_lookup: dict[tuple[str, int], bool] = {}
    for sid, day_off, ok in _HISTORY_RAW:
        run_lookup[(sid, day_off)] = ok

    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace;">'
    )

    # Grid lines (horizontal)
    for i, sid in enumerate(script_ids):
        y = MARGIN_TOP + i * y_step
        lines.append(
            f'<line x1="{MARGIN_LEFT}" y1="{y:.1f}" '
            f'x2="{W - MARGIN_RIGHT}" y2="{y:.1f}" '
            f'stroke="#1e293b" stroke-width="1"/>'
        )
        # Script label
        label = DEMO_SCRIPTS[sid]["name"]
        lines.append(
            f'<text x="{MARGIN_LEFT - 8}" y="{y + 4:.1f}" '
            f'fill="#94a3b8" font-size="10" text-anchor="end">{label}</text>'
        )

    # X-axis day labels (oldest on left, today on right)
    for d in range(n_days):
        x = MARGIN_LEFT + (n_days - 1 - d) * x_step  # d=6 → leftmost
        label = f"-{d}d" if d > 0 else "today"
        lines.append(
            f'<text x="{x:.1f}" y="{H - 8}" fill="#475569" '
            f'font-size="9" text-anchor="middle">{label}</text>'
        )

    # Dots
    for i, sid in enumerate(script_ids):
        y = MARGIN_TOP + i * y_step
        for d in range(n_days):
            x = MARGIN_LEFT + (n_days - 1 - d) * x_step
            result = run_lookup.get((sid, d))
            if result is True:
                color = "#22c55e"  # green
            elif result is False:
                color = "#ef4444"  # red
            else:
                color = "#334155"  # gray (no run)
            lines.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" '
                f'fill="{color}" opacity="0.9"/>'
            )

    # Legend
    lx = MARGIN_LEFT
    ly = H - MARGIN_BOT - 4
    for color, label in [("#22c55e", "Success"), ("#ef4444", "Fail"), ("#334155", "Not run")]:
        lines.append(f'<circle cx="{lx + 6}" cy="{ly}" r="5" fill="{color}"/>')
        lines.append(
            f'<text x="{lx + 15}" y="{ly + 4}" fill="#94a3b8" font-size="9">{label}</text>'
        )
        lx += 70

    lines.append("</svg>")
    return "\n".join(lines)


def _build_readiness_grid_html() -> str:
    """5×1 horizontal cards with status badge."""
    cards: list[str] = []
    for sid, s in DEMO_SCRIPTS.items():
        badge_color = "#22c55e" if s["status"] == "READY" else "#f59e0b"
        last = s["last_run"] or "Never"
        mins = s["duration_s"] // 60
        secs = s["duration_s"] % 60
        dur_label = f"{mins}m {secs}s" if mins else f"{secs}s"
        note_html = f'<div style="color:#94a3b8;font-size:11px;margin-top:4px">{s["note"]}</div>' if s["note"] else ""
        cards.append(
            f'<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;'
            f'padding:14px 16px;flex:1;min-width:120px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
            f'<span style="color:#e2e8f0;font-size:12px;font-weight:600">{s["name"]}</span>'
            f'<span style="background:{badge_color};color:#fff;font-size:10px;'
            f'border-radius:4px;padding:2px 6px">{s["status"]}</span></div>'
            f'<div style="color:#38bdf8;font-size:11px">Duration: {dur_label}</div>'
            f'<div style="color:#64748b;font-size:10px;margin-top:2px">Last: {last}</div>'
            f'{note_html}</div>'
        )
    return (
        '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:24px;">'
        + "".join(cards)
        + "</div>"
    )


def _build_preflight_html() -> str:
    items: list[str] = []
    for p in PREFLIGHT:
        icon = "✓" if p["ok"] else "✗"
        color = "#22c55e" if p["ok"] else "#ef4444"
        items.append(
            f'<div style="display:flex;align-items:center;gap:8px;padding:6px 0;'
            f'border-bottom:1px solid #1e293b;">'
            f'<span style="color:{color};font-weight:700">{icon}</span>'
            f'<span style="color:#e2e8f0;font-size:13px">{p["item"]}</span></div>'
        )
    return (
        '<div style="background:#1e293b;border-radius:8px;padding:16px;margin-bottom:24px;">'
        '<div style="color:#38bdf8;font-size:13px;font-weight:700;margin-bottom:10px;">Pre-Flight Checklist</div>'
        + "".join(items)
        + "</div>"
    )


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

def _build_dashboard_html() -> str:
    timeline_svg = _build_timeline_svg()
    readiness_html = _build_readiness_grid_html()
    preflight_html = _build_preflight_html()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OCI Robot Cloud — Demo Script Runner</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    h2 {{ color: #38bdf8; font-size: 15px; margin-bottom: 12px; margin-top: 8px; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; margin-bottom: 20px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ color: #94a3b8; text-align: left; padding: 8px; border-bottom: 1px solid #334155; }}
    td {{ padding: 8px; border-bottom: 1px solid #1e293b; }}
    .port {{ color: #64748b; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Demo Script Runner</h1>
  <div class="subtitle">Port 8178 &nbsp;|&nbsp; Last refresh: {now} UTC &nbsp;|&nbsp; <span class="port">Conference &amp; Partner Demo Orchestrator</span></div>

  <h2>Demo Readiness Grid</h2>
  {readiness_html}

  {preflight_html}

  <h2>Run Timeline (Last 7 Days)</h2>
  <div style="margin-bottom:24px;overflow-x:auto;">
    {timeline_svg}
  </div>

  <h2>All Demo Scripts</h2>
  <div class="card">
    <table>
      <thead>
        <tr><th>ID</th><th>Name</th><th>Duration</th><th>Status</th><th>Last Run</th><th>Steps</th></tr>
      </thead>
      <tbody>
        {''.join(
            f'<tr>'
            f'<td style="color:#38bdf8">{sid}</td>'
            f'<td style="color:#e2e8f0">{s["name"]}</td>'
            f'<td style="color:#94a3b8">{s["duration_s"]}s</td>'
            f'<td><span class="badge" style="background:{"#22c55e" if s["status"]=="READY" else "#f59e0b"};color:#fff">{s["status"]}</span></td>'
            f'<td style="color:#64748b;font-size:11px">{s["last_run"] or "—"}</td>'
            f'<td style="color:#94a3b8;font-size:11px">{" → ".join(s["steps"])}</td>'
            f'</tr>'
            for sid, s in DEMO_SCRIPTS.items()
        )}
      </tbody>
    </table>
  </div>

  <div style="color:#334155;font-size:11px;margin-top:24px;">OCI Robot Cloud Demo Runner v1.0 — POST /run/{{id}} to trigger a demo</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    """Render the demo script runner dashboard."""
    return _build_dashboard_html()


@app.get("/scripts")
def list_scripts() -> JSONResponse:
    """Return all demo scripts."""
    return JSONResponse(content=list(DEMO_SCRIPTS.values()))


@app.get("/scripts/{script_id}")
def get_script(script_id: str) -> JSONResponse:
    """Return a single demo script by ID."""
    if script_id not in DEMO_SCRIPTS:
        raise HTTPException(status_code=404, detail=f"Script '{script_id}' not found")
    return JSONResponse(content=DEMO_SCRIPTS[script_id])


@app.post("/run/{script_id}")
def trigger_run(script_id: str) -> JSONResponse:
    """Trigger a demo script run (simulated)."""
    if script_id not in DEMO_SCRIPTS:
        raise HTTPException(status_code=404, detail=f"Script '{script_id}' not found")
    script = DEMO_SCRIPTS[script_id]
    run_record = {
        "script_id": script_id,
        "name": script["name"],
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "estimated_duration_s": script["duration_s"],
        "status": "RUNNING",
    }
    _run_log.append(run_record)
    return JSONResponse(content=run_record, status_code=202)


@app.get("/history")
def get_history() -> JSONResponse:
    """Return in-memory run log (triggered this session)."""
    return JSONResponse(content=_run_log)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8178)

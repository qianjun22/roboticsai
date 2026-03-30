"""Pre-deployment validation suite for GR00T production promotion — port 8183."""

import json
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore
    HTMLResponse = None  # type: ignore
    JSONResponse = None  # type: ignore
    uvicorn = None  # type: ignore

# ---------------------------------------------------------------------------
# Validation data
# ---------------------------------------------------------------------------

CHECKS: list[dict[str, Any]] = [
    # Phase 1 — Correctness
    {
        "phase": 1, "phase_name": "Correctness",
        "id": "action_range_check",
        "status": "PASS",
        "description": "All 7 joints within limits for 100 random states",
        "value": "100/100 in-range",
        "target": "100/100",
    },
    {
        "phase": 1, "phase_name": "Correctness",
        "id": "determinism_check",
        "status": "PASS",
        "description": "Same obs produces same action (seed=42, 20 trials)",
        "value": "20/20 identical",
        "target": "20/20",
    },
    {
        "phase": 1, "phase_name": "Correctness",
        "id": "nan_inf_check",
        "status": "PASS",
        "description": "No NaN/Inf in outputs for 1000 inputs",
        "value": "0 anomalies",
        "target": "0",
    },
    {
        "phase": 1, "phase_name": "Correctness",
        "id": "dtype_check",
        "status": "PASS",
        "description": "Output dtype matches expected fp32",
        "value": "torch.float32",
        "target": "torch.float32",
    },
    # Phase 2 — Performance
    {
        "phase": 2, "phase_name": "Performance",
        "id": "latency_p99_check",
        "status": "PASS",
        "description": "p99 latency under 300ms SLA",
        "value": "287ms",
        "target": "<300ms",
    },
    {
        "phase": 2, "phase_name": "Performance",
        "id": "throughput_check",
        "status": "PASS",
        "description": "Sustained throughput above 3.0 req/s",
        "value": "4.41 req/s",
        "target": ">3.0 req/s",
    },
    {
        "phase": 2, "phase_name": "Performance",
        "id": "memory_check",
        "status": "PASS",
        "description": "GPU memory under 40GB target",
        "value": "12.5GB",
        "target": "<40GB",
    },
    # Phase 3 — Safety
    {
        "phase": 3, "phase_name": "Safety",
        "id": "velocity_limit_check",
        "status": "PASS",
        "description": "Max joint velocity under 2.5 rad/s",
        "value": "0.52 rad/s",
        "target": "<2.5 rad/s",
    },
    {
        "phase": 3, "phase_name": "Safety",
        "id": "collision_check",
        "status": "PASS",
        "description": "Zero collisions in 50 test episodes",
        "value": "0 collisions",
        "target": "0",
    },
    {
        "phase": 3, "phase_name": "Safety",
        "id": "recovery_behavior_check",
        "status": "WARNING",
        "description": "Recovery success rate below 40% target — known issue",
        "value": "21%",
        "target": ">40%",
    },
    # Phase 4 — Integration
    {
        "phase": 4, "phase_name": "Integration",
        "id": "api_contract_check",
        "status": "PASS",
        "description": "/predict response schema matches v2.0 spec",
        "value": "schema v2.0 valid",
        "target": "v2.0 spec",
    },
    {
        "phase": 4, "phase_name": "Integration",
        "id": "rollback_readiness_check",
        "status": "PASS",
        "description": "Previous checkpoint restorable in <30s",
        "value": "18.3s restore",
        "target": "<30s",
    },
]

VERDICT: dict[str, Any] = {
    "verdict": "CONDITIONAL_PASS",
    "pass_count": 11,
    "warning_count": 1,
    "fail_count": 0,
    "total": 12,
    "notes": [
        "11/12 checks PASS",
        "1 WARNING: recovery_behavior_check (21% < 40%) — known issue, tracked in JIRA ROB-441",
        "Approved for production promotion by OCI Robot Cloud team",
    ],
}

# Per-phase summary
def _phase_summary() -> list[dict[str, Any]]:
    phases: dict[int, dict[str, Any]] = {}
    for c in CHECKS:
        ph = c["phase"]
        if ph not in phases:
            phases[ph] = {"phase": ph, "name": c["phase_name"], "pass": 0, "warning": 0, "fail": 0, "total": 0}
        phases[ph]["total"] += 1
        if c["status"] == "PASS":
            phases[ph]["pass"] += 1
        elif c["status"] == "WARNING":
            phases[ph]["warning"] += 1
        else:
            phases[ph]["fail"] += 1
    return list(phases.values())


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _phase_rings_svg() -> str:
    """680×180 — 4 semicircle gauges for per-phase pass rates."""
    W, H = 680, 180
    phases = _phase_summary()
    n = len(phases)
    cx_step = W / n
    cx_base = cx_step / 2
    cy = 110
    r = 58
    stroke_w = 14

    parts: list[str] = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
                        f'style="background:#0f172a;font-family:system-ui,monospace;">']

    for i, ph in enumerate(phases):
        cx = cx_base + i * cx_step
        rate = ph["pass"] / ph["total"]
        warn_rate = ph["warning"] / ph["total"]

        # Semicircle arc (top half, left→right = 0%→100%)
        # Start angle = 180deg (left), end = 0deg (right), sweep left-to-right
        # We draw the background arc first, then the fill arc
        # Using SVG arc: semicircle from (-r,0) to (r,0) around cx,cy
        def arc_path(frac: float, offset_frac: float = 0.0) -> str:
            # Semicircle: angles from π to 0 (left to right)
            # frac=1.0 → full semicircle
            import math as _math
            start_ang = _math.pi  # 180 deg = leftmost point
            sweep_ang = _math.pi * frac
            end_ang = start_ang - sweep_ang
            off_ang = start_ang - _math.pi * offset_frac

            x1 = cx + r * _math.cos(off_ang)
            y1 = cy + r * _math.sin(off_ang)
            x2 = cx + r * _math.cos(end_ang - _math.pi * offset_frac)
            y2 = cy + r * _math.sin(end_ang - _math.pi * offset_frac)
            large = 1 if sweep_ang > _math.pi else 0
            return f"M {x1:.1f} {y1:.1f} A {r} {r} 0 {large} 1 {x2:.1f} {y2:.1f}"

        # Background track
        bx1 = cx - r
        bx2 = cx + r
        parts.append(
            f'<path d="M {bx1:.1f} {cy} A {r} {r} 0 0 1 {bx2:.1f} {cy}" '
            f'fill="none" stroke="#1e293b" stroke-width="{stroke_w}" stroke-linecap="round"/>'
        )

        # Pass arc (green/blue)
        import math as _math
        pass_end_ang = _math.pi - _math.pi * rate
        px1, py1 = cx - r, cy
        px2 = cx + r * _math.cos(pass_end_ang)
        py2 = cy + r * _math.sin(pass_end_ang)
        large_pass = 1 if rate > 0.5 else 0
        if rate > 0:
            color = "#34d399" if rate == 1.0 else ("#f59e0b" if warn_rate > 0 else "#38bdf8")
            parts.append(
                f'<path d="M {px1:.1f} {py1:.1f} A {r} {r} 0 {large_pass} 1 {px2:.1f} {py2:.1f}" '
                f'fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round"/>'
            )

        # Center text
        pct = int(rate * 100)
        status_color = "#34d399" if rate == 1.0 else "#f59e0b"
        parts.append(
            f'<text x="{cx:.1f}" y="{cy + 6}" font-size="20" font-weight="700" '
            f'fill="{status_color}" text-anchor="middle">{pct}%</text>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{cy + 22}" font-size="10" fill="#64748b" text-anchor="middle">'
            f'{ph["pass"]}/{ph["total"]} pass</text>'
        )
        # Phase label below
        parts.append(
            f'<text x="{cx:.1f}" y="{H - 10}" font-size="11" font-weight="600" '
            f'fill="#94a3b8" text-anchor="middle">Phase {ph["phase"]}: {ph["name"]}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def _status_icon(status: str) -> str:
    if status == "PASS":
        return '<span style="color:#34d399;font-size:14px;">&#10003;</span>'
    if status == "WARNING":
        return '<span style="color:#f59e0b;font-size:14px;">&#9888;</span>'
    return '<span style="color:#C74634;font-size:14px;">&#10007;</span>'


def _status_badge(status: str) -> str:
    colors = {"PASS": "#34d399", "WARNING": "#f59e0b", "FAIL": "#C74634"}
    c = colors.get(status, "#64748b")
    return (
        f'<span style="background:{c}22;color:{c};border:1px solid {c}55;'
        f'border-radius:4px;padding:1px 7px;font-size:10px;font-weight:600;">'
        f'{status}</span>'
    )


def _phase_badge(phase_name: str) -> str:
    phase_colors = {
        "Correctness": "#38bdf8",
        "Performance": "#818cf8",
        "Safety": "#fb923c",
        "Integration": "#a78bfa",
    }
    c = phase_colors.get(phase_name, "#64748b")
    return (
        f'<span style="background:{c}22;color:{c};border:1px solid {c}55;'
        f'border-radius:4px;padding:1px 7px;font-size:10px;font-weight:600;">'
        f'{phase_name}</span>'
    )


def _checks_table_html() -> str:
    rows = "".join(
        f'<tr style="border-bottom:1px solid #1e293b;">'
        f'<td style="padding:8px 10px;">{_phase_badge(c["phase_name"])}</td>'
        f'<td style="padding:8px 10px;font-size:12px;color:#e2e8f0;font-family:monospace;">{c["id"]}</td>'
        f'<td style="padding:8px 10px;">{_status_icon(c["status"])} {_status_badge(c["status"])}</td>'
        f'<td style="padding:8px 10px;font-size:12px;color:#94a3b8;">{c["value"]}</td>'
        f'<td style="padding:8px 10px;font-size:12px;color:#475569;">{c["target"]}</td>'
        f'<td style="padding:8px 10px;font-size:11px;color:#64748b;">{c["description"]}</td>'
        f'</tr>'
        for c in CHECKS
    )
    return (
        '<table style="width:100%;border-collapse:collapse;font-family:system-ui,monospace;">'
        '<thead><tr style="background:#1e293b;">'
        '<th style="padding:8px 10px;font-size:11px;color:#64748b;text-align:left;">Phase</th>'
        '<th style="padding:8px 10px;font-size:11px;color:#64748b;text-align:left;">Check</th>'
        '<th style="padding:8px 10px;font-size:11px;color:#64748b;text-align:left;">Status</th>'
        '<th style="padding:8px 10px;font-size:11px;color:#64748b;text-align:left;">Value</th>'
        '<th style="padding:8px 10px;font-size:11px;color:#64748b;text-align:left;">Target</th>'
        '<th style="padding:8px 10px;font-size:11px;color:#64748b;text-align:left;">Description</th>'
        '</tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )


def _dashboard_html() -> str:
    rings_svg = _phase_rings_svg()
    table = _checks_table_html()
    v = VERDICT
    verdict_color = "#f59e0b" if v["verdict"] == "CONDITIONAL_PASS" else (
        "#34d399" if v["verdict"] == "PASS" else "#C74634"
    )
    notes_html = "".join(
        f'<li style="color:#94a3b8;font-size:12px;margin-bottom:4px;">{n}</li>'
        for n in v["notes"]
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Deployment Validator</title>
<style>
  body{{background:#0f172a;color:#e2e8f0;font-family:system-ui,monospace;margin:0;padding:20px;}}
  h1{{color:#C74634;font-size:20px;margin-bottom:4px;}}
  .sub{{color:#64748b;font-size:12px;margin-bottom:24px;}}
  .verdict-box{{background:#1e293b;border-radius:10px;padding:20px 24px;margin-bottom:24px;
    border-left:4px solid {verdict_color};}}
  .verdict-label{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.08em;}}
  .verdict-value{{font-size:28px;font-weight:700;color:{verdict_color};margin:4px 0 8px;}}
  .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:24px;}}
  .card{{background:#1e293b;border-radius:10px;padding:16px;}}
  .metric{{font-size:26px;font-weight:700;}}
  .label{{font-size:11px;color:#64748b;margin-top:2px;}}
  .section{{margin-bottom:28px;}}
  .section h2{{font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;}}
  svg{{border-radius:8px;overflow:hidden;}}
</style>
</head>
<body>
<h1>Deployment Validator</h1>
<div class="sub">Pre-production promotion suite &nbsp;|&nbsp; GR00T groot_finetune_v2 &nbsp;|&nbsp; port 8183</div>

<div class="verdict-box">
  <div class="verdict-label">Overall Verdict</div>
  <div class="verdict-value">{v['verdict']}</div>
  <ul style="margin:0;padding-left:18px;">{notes_html}</ul>
</div>

<div class="grid">
  <div class="card"><div class="metric" style="color:#34d399;">{v['pass_count']}</div><div class="label">PASS</div></div>
  <div class="card"><div class="metric" style="color:#f59e0b;">{v['warning_count']}</div><div class="label">WARNING</div></div>
  <div class="card"><div class="metric" style="color:#C74634;">{v['fail_count']}</div><div class="label">FAIL</div></div>
</div>

<div class="section">
  <h2>Phase Completion</h2>
  {rings_svg}
</div>

<div class="section">
  <h2>Validation Checks (12 total)</h2>
  {table}
</div>
</body></html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Deployment Validator", version="1.0.0")
else:
    app = None  # type: ignore


if app is not None:
    @app.get("/", response_class=HTMLResponse)  # type: ignore[misc]
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(_dashboard_html())

    @app.get("/checks")  # type: ignore[misc]
    async def checks() -> JSONResponse:
        return JSONResponse({"checks": CHECKS, "phase_summary": _phase_summary()})

    @app.get("/verdict")  # type: ignore[misc]
    async def verdict() -> JSONResponse:
        return JSONResponse(VERDICT)

    @app.get("/report")  # type: ignore[misc]
    async def report() -> JSONResponse:
        return JSONResponse({
            "verdict": VERDICT,
            "phase_summary": _phase_summary(),
            "checks": CHECKS,
        })


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed — pip install uvicorn fastapi")
    uvicorn.run("deployment_validator:app", host="0.0.0.0", port=8183, reload=False)

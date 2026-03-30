"""Partner Onboarding Tracker — FastAPI service on port 8179.

Guides new robotics companies through onboarding to first fine-tune.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise ImportError("Install fastapi and uvicorn: pip install fastapi uvicorn") from e

app = FastAPI(title="OCI Robot Cloud — Partner Onboarding Tracker", version="1.0.0")

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

STAGES: list[dict] = [
    {
        "id": "stage_1_intro_call",
        "label": "Intro Call",
        "partners_completed": 5,
        "partners_in_stage": 0,
        "conversion_rate": 1.0,
        "avg_days": 1.2,
    },
    {
        "id": "stage_2_technical_eval",
        "label": "Technical Eval",
        "partners_completed": 4,
        "partners_in_stage": 1,
        "conversion_rate": 0.80,
        "avg_days": 7.4,
    },
    {
        "id": "stage_3_data_upload",
        "label": "Data Upload",
        "partners_completed": 4,
        "partners_in_stage": 0,
        "conversion_rate": 1.0,
        "avg_days": 3.1,
    },
    {
        "id": "stage_4_first_finetune",
        "label": "First Fine-tune",
        "partners_completed": 4,
        "partners_in_stage": 0,
        "conversion_rate": 1.0,
        "avg_days": 1.8,
    },
    {
        "id": "stage_5_eval_results",
        "label": "Eval Results",
        "partners_completed": 4,
        "partners_in_stage": 0,
        "conversion_rate": 1.0,
        "avg_days": 2.4,
    },
    {
        "id": "stage_6_paid_contract",
        "label": "Paid Contract",
        "partners_completed": 3,
        "partners_in_stage": 1,
        "conversion_rate": 0.75,
        "avg_days": 18.6,
    },
]

ACTIVE_PARTNERS: list[dict] = [
    {
        "id": "figure_ai",
        "name": "Figure AI",
        "current_stage": "stage_2_technical_eval",
        "stage_label": "Technical Eval",
        "days_in_stage": 3,
        "note": "Running GR00T inference benchmark on their humanoid arm dataset",
    },
    {
        "id": "agility_robotics",
        "name": "Agility Robotics",
        "current_stage": "stage_6_paid_contract",
        "stage_label": "Paid Contract",
        "days_in_stage": 12,
        "note": "Negotiating enterprise tier; legal review in progress",
    },
]

METRICS: dict = {
    "total_partners_entered": 5,
    "partners_converted_to_paid": 3,
    "overall_conversion_rate": 0.60,
    "avg_days_intro_to_first_finetune": 13.7,
    "avg_days_intro_to_paid": 34.5,
}


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _build_funnel_svg() -> str:
    """680×260 horizontal funnel chart — trapezoids narrowing by cumulative conversion."""
    W, H = 680, 260
    MARGIN_LEFT = 20
    MARGIN_RIGHT = 20
    MARGIN_TOP = 30
    MARGIN_BOT = 50

    n = len(STAGES)
    plot_w = W - MARGIN_LEFT - MARGIN_RIGHT
    seg_w = plot_w / n

    # Compute cumulative survival from start
    survival: list[float] = []
    cum = 1.0
    for s in STAGES:
        cum *= s["conversion_rate"]
        survival.append(cum)

    # Max bar half-height (at 100% survival)
    max_half = (H - MARGIN_TOP - MARGIN_BOT) / 2
    center_y = MARGIN_TOP + max_half

    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace;">'
    )

    # Title
    lines.append(
        f'<text x="{W//2}" y="18" fill="#38bdf8" font-size="12" '
        f'text-anchor="middle" font-weight="bold">Partner Onboarding Funnel</text>'
    )

    # Draw trapezoids
    prev_half = max_half  # entry height at 100%
    for i, (stage, surv) in enumerate(zip(STAGES, survival)):
        x0 = MARGIN_LEFT + i * seg_w
        x1 = x0 + seg_w
        cur_half = max_half * surv

        # Trapezoid points: top-left, top-right, bottom-right, bottom-left
        tl = (x0, center_y - prev_half)
        tr = (x1, center_y - cur_half)
        br = (x1, center_y + cur_half)
        bl = (x0, center_y + prev_half)

        pts = f"{tl[0]:.1f},{tl[1]:.1f} {tr[0]:.1f},{tr[1]:.1f} {br[0]:.1f},{br[1]:.1f} {bl[0]:.1f},{bl[1]:.1f}"
        # Shade alternating slightly
        fill = "#166534" if i % 2 == 0 else "#15803d"
        lines.append(f'<polygon points="{pts}" fill="{fill}" stroke="#0f172a" stroke-width="1.5"/>')

        # Stage label (centered horizontally in segment, below funnel)
        lx = x0 + seg_w / 2
        ly = center_y + max_half + 16
        lines.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" '
            f'font-size="9" text-anchor="middle">{stage["label"]}</text>'
        )

        # Partner count inside trapezoid
        cnt = stage["partners_completed"]
        mid_x = (x0 + x1) / 2
        lines.append(
            f'<text x="{mid_x:.1f}" y="{center_y + 5:.1f}" fill="#fff" '
            f'font-size="11" text-anchor="middle" font-weight="bold">{cnt}</text>'
        )

        # Conversion rate between stages (except last)
        if i < n - 1:
            cr = STAGES[i + 1]["conversion_rate"]
            cx = x1
            lines.append(
                f'<text x="{cx:.1f}" y="{center_y - cur_half - 6:.1f}" '
                f'fill="#f59e0b" font-size="9" text-anchor="middle">{int(cr*100)}%</text>'
            )

        prev_half = cur_half

    # Legend
    lines.append(
        f'<text x="{MARGIN_LEFT}" y="{H - 8}" fill="#475569" font-size="9">'
        f"Number inside = partners completed stage | % = conversion to next stage</text>"
    )

    lines.append("</svg>")
    return "\n".join(lines)


def _build_ttv_svg() -> str:
    """680×180 cumulative time-to-value bar chart."""
    W, H = 680, 180
    MARGIN_LEFT = 130
    MARGIN_RIGHT = 60
    MARGIN_TOP = 30
    MARGIN_BOT = 30

    # Cumulative days milestones
    milestones: list[tuple[str, float]] = [
        ("Intro Call done", 1.2),
        ("Tech Eval done", 1.2 + 7.4),
        ("Data Uploaded", 1.2 + 7.4 + 3.1),
        ("First Fine-tune", 1.2 + 7.4 + 3.1 + 1.8),
        ("Eval Results", 1.2 + 7.4 + 3.1 + 1.8 + 2.4),
        ("Paid Contract", 34.5),
    ]
    max_val = max(v for _, v in milestones)

    plot_w = W - MARGIN_LEFT - MARGIN_RIGHT
    plot_h = H - MARGIN_TOP - MARGIN_BOT
    bar_h = plot_h / len(milestones) * 0.6
    y_step = plot_h / len(milestones)

    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace;">'
    )
    lines.append(
        f'<text x="{W//2}" y="18" fill="#38bdf8" font-size="12" '
        f'text-anchor="middle" font-weight="bold">Cumulative Days to Milestone (avg)</text>'
    )

    for i, (label, days) in enumerate(milestones):
        bar_w = (days / max_val) * plot_w
        x = MARGIN_LEFT
        y = MARGIN_TOP + i * y_step + (y_step - bar_h) / 2

        lines.append(
            f'<rect x="{x}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'fill="#38bdf8" opacity="0.75" rx="2"/>'
        )
        # Label left
        lines.append(
            f'<text x="{x - 6}" y="{y + bar_h/2 + 4:.1f}" fill="#94a3b8" '
            f'font-size="10" text-anchor="end">{label}</text>'
        )
        # Value right
        lines.append(
            f'<text x="{x + bar_w + 6:.1f}" y="{y + bar_h/2 + 4:.1f}" fill="#e2e8f0" '
            f'font-size="10" text-anchor="start">{days:.1f}d</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

def _build_dashboard_html() -> str:
    funnel_svg = _build_funnel_svg()
    ttv_svg = _build_ttv_svg()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    # Active partners cards
    partner_cards: list[str] = []
    for p in ACTIVE_PARTNERS:
        partner_cards.append(
            f'<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;'
            f'padding:14px 16px;flex:1;min-width:240px;">'
            f'<div style="color:#e2e8f0;font-size:14px;font-weight:700;margin-bottom:6px">{p["name"]}</div>'
            f'<div style="color:#38bdf8;font-size:12px;margin-bottom:4px">Stage: {p["stage_label"]}</div>'
            f'<div style="color:#94a3b8;font-size:11px">Days in stage: {p["days_in_stage"]}</div>'
            f'<div style="color:#64748b;font-size:11px;margin-top:6px">{p["note"]}</div>'
            f'</div>'
        )

    # Metrics row
    metric_items = [
        ("Partners Entered", str(METRICS["total_partners_entered"]), "#38bdf8"),
        ("Converted to Paid", str(METRICS["partners_converted_to_paid"]), "#22c55e"),
        ("Overall Conversion", f'{int(METRICS["overall_conversion_rate"]*100)}%', "#f59e0b"),
        ("Days → First Fine-tune", f'{METRICS["avg_days_intro_to_first_finetune"]}d', "#a78bfa"),
        ("Days → Paid", f'{METRICS["avg_days_intro_to_paid"]}d', "#C74634"),
    ]
    metrics_html = "".join(
        f'<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;'
        f'padding:12px 16px;flex:1;min-width:110px;text-align:center;">'
        f'<div style="color:{color};font-size:22px;font-weight:700">{val}</div>'
        f'<div style="color:#64748b;font-size:11px;margin-top:4px">{label}</div></div>'
        for label, val, color in metric_items
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OCI Robot Cloud — Partner Onboarding Tracker</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    h2 {{ color: #38bdf8; font-size: 15px; margin-bottom: 12px; margin-top: 8px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; margin-bottom: 20px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ color: #94a3b8; text-align: left; padding: 8px; border-bottom: 1px solid #334155; }}
    td {{ padding: 8px; border-bottom: 1px solid #1e293b; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Partner Onboarding Tracker</h1>
  <div class="subtitle">Port 8179 &nbsp;|&nbsp; Last refresh: {now} UTC &nbsp;|&nbsp; Intro → Paid Contract pipeline</div>

  <h2>Success Metrics</h2>
  <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:24px;">
    {metrics_html}
  </div>

  <h2>Onboarding Funnel</h2>
  <div style="margin-bottom:24px;overflow-x:auto;">
    {funnel_svg}
  </div>

  <h2>Time-to-Value (Cumulative Days)</h2>
  <div style="margin-bottom:24px;overflow-x:auto;">
    {ttv_svg}
  </div>

  <h2>Active Partners</h2>
  <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px;">
    {''.join(partner_cards)}
  </div>

  <h2>Stage Details</h2>
  <div class="card">
    <table>
      <thead>
        <tr>
          <th>Stage</th><th>Label</th><th>Completed</th>
          <th>In Stage</th><th>Conversion</th><th>Avg Days</th>
        </tr>
      </thead>
      <tbody>
        {''.join(
            f'<tr>'
            f'<td style="color:#38bdf8;font-size:11px">{s["id"]}</td>'
            f'<td style="color:#e2e8f0">{s["label"]}</td>'
            f'<td style="color:#22c55e;text-align:center">{s["partners_completed"]}</td>'
            f'<td style="color:#f59e0b;text-align:center">{s["partners_in_stage"]}</td>'
            f'<td style="color:#a78bfa;text-align:center">{int(s["conversion_rate"]*100)}%</td>'
            f'<td style="color:#94a3b8;text-align:center">{s["avg_days"]}d</td>'
            f'</tr>'
            for s in STAGES
        )}
      </tbody>
    </table>
  </div>

  <div style="color:#334155;font-size:11px;margin-top:24px;">OCI Robot Cloud Partner Onboarding v1.0 — GET /stages | /funnel | /partners/{{id}}/stage</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    """Render the partner onboarding dashboard."""
    return _build_dashboard_html()


@app.get("/stages")
def list_stages() -> JSONResponse:
    """Return all onboarding stages."""
    return JSONResponse(content=STAGES)


@app.get("/funnel")
def get_funnel() -> JSONResponse:
    """Return funnel summary with cumulative conversion rates."""
    cum = 1.0
    funnel: list[dict] = []
    for s in STAGES:
        cum *= s["conversion_rate"]
        funnel.append(
            {
                "id": s["id"],
                "label": s["label"],
                "cumulative_conversion": round(cum, 4),
                "partners_completed": s["partners_completed"],
                "avg_days": s["avg_days"],
            }
        )
    return JSONResponse(
        content={
            "stages": funnel,
            "metrics": METRICS,
            "active_partners": ACTIVE_PARTNERS,
        }
    )


@app.get("/partners/{partner_id}/stage")
def get_partner_stage(partner_id: str) -> JSONResponse:
    """Return current onboarding stage for a specific partner."""
    for p in ACTIVE_PARTNERS:
        if p["id"] == partner_id:
            return JSONResponse(content=p)
    raise HTTPException(
        status_code=404,
        detail=f"Partner '{partner_id}' not found. Active partners: {[p['id'] for p in ACTIVE_PARTNERS]}",
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8179)

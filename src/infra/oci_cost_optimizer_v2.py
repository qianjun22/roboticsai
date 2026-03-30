"""OCI Cost Optimizer v2 — Advanced Spot & Preemptible Workload Planning
Port 8197: Optimize OCI spend via spot instances, scheduling, and tiering.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None
    HTMLResponse = None
    JSONResponse = None
    uvicorn = None

import math

app = FastAPI(title="OCI Cost Optimizer v2", version="2.0.0") if FastAPI else None

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

CURRENT_MONTHLY = 3182.84  # actual March 2026

STRATEGIES = [
    {
        "id": "spot_instances_sdg",
        "description": "Use preemptible A100s for SDG generation (fault-tolerant)",
        "savings_pct": 0.42,
        "monthly_saving": 134.71,
        "risk": "LOW",
        "implementation": "Add --preemptible flag to SDG jobs",
    },
    {
        "id": "spot_instances_hpo",
        "description": "HPO trials fault-tolerant by design",
        "savings_pct": 0.52,
        "monthly_saving": 121.95,
        "risk": "LOW",
        "implementation": "Optuna trials restart from best checkpoint",
    },
    {
        "id": "schedule_shift",
        "description": "Shift HPO/SDG to off-peak (00:00-08:00 UTC)",
        "savings_pct": 0.15,
        "monthly_saving": 47.74,
        "risk": "LOW",
        "implementation": "Cron-based job scheduling",
    },
    {
        "id": "batch_consolidation",
        "description": "Consolidate 4 small eval jobs into 1 batch eval",
        "savings_pct": 0.28,
        "monthly_saving": 28.41,
        "risk": "MEDIUM",
        "implementation": "Batch eval script (scripts/batch_eval.sh)",
    },
    {
        "id": "right_size_eval",
        "description": "Downgrade phoenix-eval to A100_40GB for eval-only workloads",
        "savings_pct": 0.33,
        "monthly_saving": 19.07,
        "risk": "LOW",
        "implementation": "Already A100_40GB — maximize eval scheduling density",
    },
    {
        "id": "storage_tiering",
        "description": "Archive datasets >30d to OCI Infrequent Access (0.5× cost)",
        "savings_pct": 0.40,
        "monthly_saving": 6.19,
        "risk": "NONE",
        "implementation": "Object lifecycle policy",
    },
]

TOTAL_SAVINGS = 358.07
OPTIMIZED_MONTHLY = 2824.77

# Implementation priority order (lowest risk + highest ROI first)
PRIORITY_ORDER = [
    "spot_instances_sdg",
    "spot_instances_hpo",
    "storage_tiering",
    "schedule_shift",
    "right_size_eval",
    "batch_consolidation",
]

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _savings_bar_svg() -> str:
    """680×200 horizontal bar chart sorted by monthly saving."""
    W, H = 680, 200
    pad_l, pad_r, pad_t, pad_b = 170, 100, 24, 28
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    sorted_s = sorted(STRATEGIES, key=lambda s: s["monthly_saving"], reverse=True)
    n = len(sorted_s)
    bar_h = plot_h / n * 0.6
    gap = plot_h / n
    max_saving = sorted_s[0]["monthly_saving"]

    risk_colors = {"NONE": "#34d399", "LOW": "#38bdf8", "MEDIUM": "#f59e0b", "HIGH": "#C74634"}

    bars = ""
    for i, s in enumerate(sorted_s):
        cy = pad_t + i * gap + gap / 2
        bw = s["monthly_saving"] / max_saving * plot_w
        col = "#C74634" if i == 0 else risk_colors.get(s["risk"], "#38bdf8")
        bars += (
            f'<rect x="{pad_l}" y="{cy - bar_h/2:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" fill="{col}" rx="3" opacity="0.9"/>'
            f'<text x="{pad_l - 6}" y="{cy + 4:.0f}" fill="#cbd5e1" font-size="10" text-anchor="end" font-family="monospace">{s["id"][:20]}</text>'
            f'<text x="{pad_l + bw + 6:.0f}" y="{cy + 4:.0f}" fill="#e2e8f0" font-size="10" font-family="monospace">${s["monthly_saving"]:.2f}</text>'
        )
        # Risk badge
        rc = risk_colors.get(s["risk"], "#94a3b8")
        bars += f'<text x="{W - pad_r + 4}" y="{cy + 4:.0f}" fill="{rc}" font-size="9" font-family="monospace">{s["risk"]}</text>'

    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" stroke="#334155" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" stroke="#334155" stroke-width="1"/>'
    )
    title = f'<text x="{pad_l}" y="{pad_t-8}" fill="#e2e8f0" font-size="11" font-family="monospace">Savings opportunity by strategy ($/mo)</text>'

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:6px">'
        + title + axes + bars +
        '</svg>'
    )


def _donut_svg() -> str:
    """420×260 side-by-side donuts: current vs optimized cost."""
    W, H = 420, 260
    cx1, cx2 = 110, 310
    cy = 130
    r_outer, r_inner = 80, 50

    # Full circles (simplified — just two filled arcs representing cost)
    # Current: full red ring; Optimized: proportionally smaller arc in blue
    pct_saved = TOTAL_SAVINGS / CURRENT_MONTHLY  # ~11.2%
    pct_remain = 1 - pct_saved

    def _arc_path(cx, cy, r, start_angle, end_angle):
        """SVG arc path string (degrees, clockwise from top)."""
        sa = math.radians(start_angle - 90)
        ea = math.radians(end_angle - 90)
        x1 = cx + r * math.cos(sa)
        y1 = cy + r * math.sin(sa)
        x2 = cx + r * math.cos(ea)
        y2 = cy + r * math.sin(ea)
        large = 1 if (end_angle - start_angle) > 180 else 0
        return f"M {x1:.2f},{y1:.2f} A {r},{r} 0 {large},1 {x2:.2f},{y2:.2f}"

    def _donut_segment(cx, cy, r_out, r_in, a_start, a_end, fill):
        sa = math.radians(a_start - 90)
        ea = math.radians(a_end - 90)
        large = 1 if (a_end - a_start) > 180 else 0
        ox1 = cx + r_out * math.cos(sa); oy1 = cy + r_out * math.sin(sa)
        ox2 = cx + r_out * math.cos(ea); oy2 = cy + r_out * math.sin(ea)
        ix1 = cx + r_in * math.cos(ea);  iy1 = cy + r_in * math.sin(ea)
        ix2 = cx + r_in * math.cos(sa);  iy2 = cy + r_in * math.sin(sa)
        d = (f"M {ox1:.2f},{oy1:.2f} A {r_out},{r_out} 0 {large},1 {ox2:.2f},{oy2:.2f} "
             f"L {ix1:.2f},{iy1:.2f} A {r_in},{r_in} 0 {large},0 {ix2:.2f},{iy2:.2f} Z")
        return f'<path d="{d}" fill="{fill}"/>'

    # Current donut — full ring in dark red
    donut1 = _donut_segment(cx1, cy, r_outer, r_inner, 0, 360 - 0.01, "#C74634")
    donut1 += f'<text x="{cx1}" y="{cy-8}" fill="#fff" font-size="13" font-weight="700" text-anchor="middle" font-family="monospace">${CURRENT_MONTHLY:,.2f}</text>'
    donut1 += f'<text x="{cx1}" y="{cy+10}" fill="#94a3b8" font-size="10" text-anchor="middle" font-family="monospace">current</text>'
    donut1 += f'<text x="{cx1}" y="{cy-68}" fill="#e2e8f0" font-size="11" text-anchor="middle" font-family="sans-serif">March 2026</text>'

    # Optimized donut — remaining portion in blue, savings in green
    remain_angle = pct_remain * 360
    donut2 = _donut_segment(cx2, cy, r_outer, r_inner, 0, remain_angle, "#38bdf8")
    donut2 += _donut_segment(cx2, cy, r_outer, r_inner, remain_angle, 360 - 0.01, "#34d399")
    donut2 += f'<text x="{cx2}" y="{cy-8}" fill="#fff" font-size="13" font-weight="700" text-anchor="middle" font-family="monospace">${OPTIMIZED_MONTHLY:,.2f}</text>'
    donut2 += f'<text x="{cx2}" y="{cy+10}" fill="#94a3b8" font-size="10" text-anchor="middle" font-family="monospace">optimized</text>'
    donut2 += f'<text x="{cx2}" y="{cy-68}" fill="#e2e8f0" font-size="11" text-anchor="middle" font-family="sans-serif">Projected</text>'

    # Savings label
    savings_lbl = (
        f'<text x="{W//2}" y="{H-12}" fill="#34d399" font-size="12" font-weight="700" text-anchor="middle" font-family="monospace">'
        f'Save ${TOTAL_SAVINGS:.2f}/mo ({pct_saved:.1%} reduction)</text>'
    )
    # Arrow
    arrow = f'<text x="{W//2}" y="{cy+6}" fill="#64748b" font-size="20" text-anchor="middle">→</text>'

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:6px">'
        + donut1 + donut2 + arrow + savings_lbl +
        '</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    bar_svg = _savings_bar_svg()
    donut_svg = _donut_svg()

    risk_badge = {
        "NONE": '<span style="background:#34d399;color:#0f172a;padding:1px 7px;border-radius:4px;font-size:11px">NONE</span>',
        "LOW": '<span style="background:#38bdf8;color:#0f172a;padding:1px 7px;border-radius:4px;font-size:11px">LOW</span>',
        "MEDIUM": '<span style="background:#f59e0b;color:#0f172a;padding:1px 7px;border-radius:4px;font-size:11px">MEDIUM</span>',
        "HIGH": '<span style="background:#C74634;color:#fff;padding:1px 7px;border-radius:4px;font-size:11px">HIGH</span>',
    }

    strat_map = {s["id"]: s for s in STRATEGIES}
    plan_rows = ""
    for rank, sid in enumerate(PRIORITY_ORDER, 1):
        s = strat_map[sid]
        plan_rows += (
            f"<tr>"
            f"<td style='color:#64748b;text-align:center'>{rank}</td>"
            f"<td style='color:#38bdf8;font-family:monospace'>{s['id']}</td>"
            f"<td style='color:#cbd5e1'>{s['description']}</td>"
            f"<td style='color:#34d399'>${s['monthly_saving']:.2f}</td>"
            f"<td>{risk_badge[s['risk']]}</td>"
            f"<td style='color:#94a3b8;font-size:12px'>{s['implementation']}</td>"
            f"</tr>\n"
        )

    strat_rows = ""
    for s in sorted(STRATEGIES, key=lambda x: x["monthly_saving"], reverse=True):
        strat_rows += (
            f"<tr>"
            f"<td style='color:#38bdf8;font-family:monospace'>{s['id']}</td>"
            f"<td style='color:#cbd5e1'>{s['description']}</td>"
            f"<td style='color:#e2e8f0'>{s['savings_pct']:.0%}</td>"
            f"<td style='color:#34d399'>${s['monthly_saving']:.2f}</td>"
            f"<td>{risk_badge[s['risk']]}</td>"
            f"</tr>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>OCI Cost Optimizer v2 — OCI Robot Cloud</title>
<style>
  body {{ margin:0; background:#0f172a; color:#e2e8f0; font-family:system-ui,sans-serif; }}
  .header {{ background:linear-gradient(135deg,#1e293b,#0f172a); border-bottom:2px solid #C74634; padding:20px 32px; }}
  .header h1 {{ margin:0; font-size:22px; color:#fff; }}
  .header p {{ margin:4px 0 0; color:#94a3b8; font-size:13px; }}
  .badge-port {{ background:#C74634; color:#fff; border-radius:4px; padding:2px 10px; font-size:12px; margin-left:12px; }}
  .content {{ padding:28px 32px; max-width:960px; }}
  h2 {{ color:#38bdf8; font-size:15px; margin:28px 0 10px; text-transform:uppercase; letter-spacing:.05em; }}
  table {{ width:100%; border-collapse:collapse; background:#1e293b; border-radius:8px; overflow:hidden; font-size:13px; }}
  th {{ background:#334155; color:#94a3b8; padding:8px 12px; text-align:left; font-weight:600; font-size:11px; text-transform:uppercase; }}
  td {{ padding:8px 12px; border-top:1px solid #334155; }}
  tr:hover td {{ background:#243044; }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:24px; }}
  .kpi {{ background:#1e293b; border:1px solid #334155; border-radius:8px; padding:16px 20px; }}
  .kpi .val {{ font-size:26px; font-weight:700; color:#38bdf8; }}
  .kpi .lbl {{ font-size:11px; color:#64748b; text-transform:uppercase; margin-top:4px; }}
  .svg-box {{ background:#0f172a; border:1px solid #1e293b; border-radius:8px; padding:12px; margin-bottom:20px; overflow-x:auto; }}
  .svg-row {{ display:flex; gap:20px; align-items:flex-start; flex-wrap:wrap; }}
  .insight {{ background:#1e293b; border-left:3px solid #C74634; border-radius:0 6px 6px 0; padding:10px 16px; margin:16px 0; font-size:13px; color:#cbd5e1; }}
</style>
</head>
<body>
<div class="header">
  <h1>OCI Cost Optimizer v2 <span class="badge-port">:8197</span></h1>
  <p>OCI Robot Cloud · March 2026 actual spend · 6 optimization strategies · Advanced spot &amp; preemptible planning</p>
</div>
<div class="content">
  <div class="kpi-grid">
    <div class="kpi"><div class="val" style="color:#C74634">${CURRENT_MONTHLY:,.2f}</div><div class="lbl">Current monthly (Mar 2026)</div></div>
    <div class="kpi"><div class="val" style="color:#34d399">${OPTIMIZED_MONTHLY:,.2f}</div><div class="lbl">Projected optimized</div></div>
    <div class="kpi"><div class="val" style="color:#38bdf8">${TOTAL_SAVINGS:.2f}</div><div class="lbl">Monthly savings</div></div>
    <div class="kpi"><div class="val">{TOTAL_SAVINGS/CURRENT_MONTHLY:.1%}</div><div class="lbl">Cost reduction</div></div>
  </div>

  <h2>Savings Opportunities &amp; Cost Comparison</h2>
  <div class="svg-row">
    <div class="svg-box" style="flex:2">{bar_svg}</div>
    <div class="svg-box" style="flex:1">{donut_svg}</div>
  </div>

  <h2>All Strategies</h2>
  <table>
    <tr><th>Strategy</th><th>Description</th><th>Savings %</th><th>$/mo</th><th>Risk</th></tr>
    {strat_rows}
  </table>

  <h2>Implementation Plan (Priority Order)</h2>
  <div class="insight"><strong>Start with spot_instances_sdg + spot_instances_hpo</strong> — highest ROI ($256.66/mo combined), lowest risk, zero code changes to model training logic.</div>
  <table>
    <tr><th>#</th><th>Strategy</th><th>Description</th><th>$/mo</th><th>Risk</th><th>How</th></tr>
    {plan_rows}
  </table>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

if app:
    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _build_html()

    @app.get("/strategies")
    def get_strategies():
        return JSONResponse(content=STRATEGIES)

    @app.get("/summary")
    def get_summary():
        return JSONResponse(content={
            "current_monthly_usd": CURRENT_MONTHLY,
            "optimized_monthly_usd": OPTIMIZED_MONTHLY,
            "total_savings_usd": TOTAL_SAVINGS,
            "savings_pct": round(TOTAL_SAVINGS / CURRENT_MONTHLY, 4),
            "strategy_count": len(STRATEGIES),
            "period": "March 2026",
        })

    @app.get("/plan")
    def get_plan():
        strat_map = {s["id"]: s for s in STRATEGIES}
        ordered = []
        for rank, sid in enumerate(PRIORITY_ORDER, 1):
            s = dict(strat_map[sid])
            s["priority_rank"] = rank
            ordered.append(s)
        return JSONResponse(content={
            "implementation_order": ordered,
            "rationale": "Sorted by risk-adjusted ROI: lowest risk + highest monthly saving first",
            "quick_wins": ["spot_instances_sdg", "spot_instances_hpo", "storage_tiering"],
        })


if __name__ == "__main__":
    if uvicorn:
        uvicorn.run("oci_cost_optimizer_v2:app", host="0.0.0.0", port=8197, reload=False)
    else:
        print("uvicorn not installed — pip install fastapi uvicorn")

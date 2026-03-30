"""Design partner relationship dashboard — FastAPI port 8136."""

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

import math
from typing import Optional

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

PARTNERS = {
    "physical_intelligence": {
        "id": "physical_intelligence",
        "name": "Physical Intelligence",
        "tier": "enterprise",
        "status": "ACTIVE",
        "gpu_hrs_used": 142.4,
        "fine_tune_runs": 8,
        "sr_latest": 0.74,
        "monthly_spend": 1847.20,
        "contact": "dario@physicalintelligence.ai",
        "joined": "2026-01-15",
    },
    "apptronik": {
        "id": "apptronik",
        "name": "Apptronik",
        "tier": "growth",
        "status": "ACTIVE",
        "gpu_hrs_used": 67.8,
        "fine_tune_runs": 4,
        "sr_latest": 0.61,
        "monthly_spend": 876.50,
        "contact": "jeff@apptronik.com",
        "joined": "2026-02-01",
    },
    "figure_ai": {
        "id": "figure_ai",
        "name": "Figure AI",
        "tier": "enterprise",
        "status": "NEGOTIATING",
        "gpu_hrs_used": 0,
        "fine_tune_runs": 0,
        "sr_latest": 0.0,
        "monthly_spend": 0,
        "contact": "brett@figure.ai",
        "joined": None,
    },
    "1x_technologies": {
        "id": "1x_technologies",
        "name": "1X Technologies",
        "tier": "starter",
        "status": "ACTIVE",
        "gpu_hrs_used": 23.1,
        "fine_tune_runs": 2,
        "sr_latest": 0.48,
        "monthly_spend": 298.86,
        "contact": "bernt@1x.tech",
        "joined": "2026-02-20",
    },
    "agility_robotics": {
        "id": "agility_robotics",
        "name": "Agility Robotics",
        "tier": "growth",
        "status": "PILOT",
        "gpu_hrs_used": 12.4,
        "fine_tune_runs": 1,
        "sr_latest": 0.39,
        "monthly_spend": 160.28,
        "contact": "damion@agilityrobotics.com",
        "joined": "2026-03-10",
    },
}

CURRENT_MRR = 3182.84
POTENTIAL_FIGURE_AI = 5000.00
POTENTIAL_MRR = CURRENT_MRR + POTENTIAL_FIGURE_AI

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _revenue_bar_chart() -> str:
    """Revenue bar chart SVG 680x180, sorted by spend desc (active partners)."""
    active = [
        p for p in PARTNERS.values()
        if p["status"] == "ACTIVE" and p["monthly_spend"] > 0
    ]
    active.sort(key=lambda p: p["monthly_spend"], reverse=True)

    W, H = 680, 180
    pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    max_val = max(p["monthly_spend"] for p in active)
    n = len(active)
    bar_gap = 12
    bar_w = (chart_w - bar_gap * (n - 1)) / n

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # y-axis grid lines
    for frac in [0.25, 0.5, 0.75, 1.0]:
        y = pad_t + chart_h - frac * chart_h
        val = frac * max_val
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{W-pad_r}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{y+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10" font-family="monospace">${val:.0f}</text>')

    # bars
    for i, p in enumerate(active):
        bh = (p["monthly_spend"] / max_val) * chart_h
        x = pad_l + i * (bar_w + bar_gap)
        y = pad_t + chart_h - bh
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="#C74634" rx="3"/>')
        label = p["name"].split()[0]
        lx = x + bar_w / 2
        lines.append(f'<text x="{lx:.1f}" y="{H-pad_b+14}" text-anchor="middle" fill="#cbd5e1" font-size="11" font-family="sans-serif">{label}</text>')
        lines.append(f'<text x="{lx:.1f}" y="{y-4:.1f}" text-anchor="middle" fill="#f8fafc" font-size="10" font-family="monospace">${p["monthly_spend"]:.0f}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def _sr_bar_chart() -> str:
    """SR comparison horizontal bar chart SVG 680x180, sorted by sr_latest."""
    partners = sorted(PARTNERS.values(), key=lambda p: p["sr_latest"], reverse=True)

    W, H = 680, 180
    pad_l, pad_r, pad_t, pad_b = 150, 60, 12, 12
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    n = len(partners)
    row_h = chart_h / n
    bar_h = row_h * 0.55

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # x-axis ticks
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        x = pad_l + frac * chart_w
        lines.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{H-pad_b}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{H-pad_b+10}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">{frac:.0%}</text>')

    for i, p in enumerate(partners):
        bw = p["sr_latest"] * chart_w
        y = pad_t + i * row_h + (row_h - bar_h) / 2
        lines.append(f'<rect x="{pad_l}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" fill="#38bdf8" rx="2"/>')
        label = p["name"]
        lines.append(f'<text x="{pad_l-6}" y="{y+bar_h/2+4:.1f}" text-anchor="end" fill="#cbd5e1" font-size="11" font-family="sans-serif">{label}</text>')
        vx = pad_l + bw + 4
        lines.append(f'<text x="{vx:.1f}" y="{y+bar_h/2+4:.1f}" fill="#f8fafc" font-size="11" font-family="monospace">{p["sr_latest"]:.0%}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Badge helpers
# ---------------------------------------------------------------------------

TIER_COLORS = {
    "enterprise": ("#854d0e", "#fde68a"),   # bg, text
    "growth": ("#0c4a6e", "#7dd3fc"),
    "starter": ("#1e293b", "#94a3b8"),
}

STATUS_COLORS = {
    "ACTIVE": ("#14532d", "#86efac"),
    "PILOT": ("#1e3a5f", "#93c5fd"),
    "NEGOTIATING": ("#451a03", "#fed7aa"),
}


def _badge(text: str, bg: str, fg: str) -> str:
    return (f'<span style="background:{bg};color:{fg};padding:2px 8px;'
            f'border-radius:9999px;font-size:11px;font-weight:600">{text}</span>')


def _partner_card(p: dict) -> str:
    tier_bg, tier_fg = TIER_COLORS.get(p["tier"], ("#1e293b", "#94a3b8"))
    st_bg, st_fg = STATUS_COLORS.get(p["status"], ("#1e293b", "#94a3b8"))
    joined_str = p["joined"] if p["joined"] else "—"
    sr_pct = f"{p['sr_latest']:.0%}" if p["sr_latest"] > 0 else "—"
    spend_str = f"${p['monthly_spend']:,.2f}" if p["monthly_spend"] > 0 else "$0"
    return f"""<div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <span style="color:#f1f5f9;font-size:16px;font-weight:700">{p['name']}</span>
    <div style="display:flex;gap:6px">
      {_badge(p['tier'].upper(), tier_bg, tier_fg)}
      {_badge(p['status'], st_bg, st_fg)}
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:10px">
    <div><div style="color:#64748b;font-size:11px">GPU Hrs</div><div style="color:#38bdf8;font-size:18px;font-weight:700">{p['gpu_hrs_used']}</div></div>
    <div><div style="color:#64748b;font-size:11px">Fine-Tune Runs</div><div style="color:#38bdf8;font-size:18px;font-weight:700">{p['fine_tune_runs']}</div></div>
    <div><div style="color:#64748b;font-size:11px">Success Rate</div><div style="color:#C74634;font-size:18px;font-weight:700">{sr_pct}</div></div>
    <div><div style="color:#64748b;font-size:11px">Monthly Spend</div><div style="color:#f8fafc;font-size:18px;font-weight:700">{spend_str}</div></div>
  </div>
  <div style="color:#94a3b8;font-size:12px">Contact: <a href="mailto:{p['contact']}" style="color:#38bdf8">{p['contact']}</a> &nbsp;|&nbsp; Joined: {joined_str}</div>
</div>"""


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def _build_html() -> str:
    revenue_svg = _revenue_bar_chart()
    sr_svg = _sr_bar_chart()
    cards_html = "\n".join(_partner_card(p) for p in PARTNERS.values())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>OCI Robot Cloud — Partner Dashboard</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: system-ui, sans-serif; padding: 32px; }}
    h1 {{ font-size: 24px; font-weight: 800; color: #f8fafc; margin-bottom: 4px; }}
    h2 {{ font-size: 14px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: .08em; margin: 28px 0 12px; }}
    .grid-3 {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; margin-bottom: 24px; }}
    .stat-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; }}
    .stat-label {{ color: #64748b; font-size: 12px; margin-bottom: 6px; }}
    .stat-value {{ font-size: 28px; font-weight: 800; }}
    .oracle-red {{ color: #C74634; }}
    .sky {{ color: #38bdf8; }}
    .green {{ color: #4ade80; }}
    .partners-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 24px; }}
    .chart-box {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; margin-bottom: 24px; }}
    .pipeline {{ background: linear-gradient(135deg,#1e293b,#0f172a); border:1px solid #C74634; border-radius:10px; padding:20px; margin-bottom:24px; }}
    .footer {{ color:#475569; font-size:11px; text-align:center; margin-top:32px; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud &mdash; Partner Dashboard</h1>
  <p style="color:#64748b;margin-bottom:24px">Design partner relationships &amp; commercial pipeline</p>

  <div class="grid-3">
    <div class="stat-card">
      <div class="stat-label">Current MRR</div>
      <div class="stat-value oracle-red">${CURRENT_MRR:,.2f}</div>
      <div style="color:#64748b;font-size:12px;margin-top:4px">3 active partners</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Potential MRR (+ Figure AI)</div>
      <div class="stat-value sky">${POTENTIAL_MRR:,.2f}</div>
      <div style="color:#64748b;font-size:12px;margin-top:4px">If Figure AI converts</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Avg Success Rate (Active)</div>
      <div class="stat-value green">61%</div>
      <div style="color:#64748b;font-size:12px;margin-top:4px">Across 3 active partners</div>
    </div>
  </div>

  <div class="pipeline">
    <div style="color:#f59e0b;font-weight:700;margin-bottom:8px">&#9733; Pipeline Opportunity</div>
    <div style="display:flex;gap:40px;align-items:center">
      <div><div style="color:#64748b;font-size:12px">Current MRR</div><div style="color:#f8fafc;font-size:20px;font-weight:700">${CURRENT_MRR:,.2f}</div></div>
      <div style="color:#334155;font-size:24px">+</div>
      <div><div style="color:#64748b;font-size:12px">Figure AI (est.)</div><div style="color:#f59e0b;font-size:20px;font-weight:700">${POTENTIAL_FIGURE_AI:,.2f}</div></div>
      <div style="color:#334155;font-size:24px">=</div>
      <div><div style="color:#64748b;font-size:12px">Total Potential</div><div style="color:#4ade80;font-size:24px;font-weight:800">${POTENTIAL_MRR:,.2f}/mo</div></div>
    </div>
  </div>

  <h2>Monthly Revenue by Partner</h2>
  <div class="chart-box">{revenue_svg}</div>

  <h2>Success Rate Comparison</h2>
  <div class="chart-box">{sr_svg}</div>

  <h2>Partner Cards</h2>
  <div class="partners-grid">
{cards_html}
  </div>

  <div class="footer">OCI Robot Cloud &mdash; Partner Dashboard &mdash; Port 8136</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Partner Dashboard", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_build_html())

    @app.get("/partners")
    async def list_partners():
        return JSONResponse(content=list(PARTNERS.values()))

    @app.get("/partners/{partner_id}")
    async def get_partner(partner_id: str):
        p = PARTNERS.get(partner_id)
        if not p:
            raise HTTPException(status_code=404, detail="Partner not found")
        return JSONResponse(content=p)

    @app.get("/summary")
    async def summary():
        active = [p for p in PARTNERS.values() if p["status"] == "ACTIVE"]
        avg_sr = sum(p["sr_latest"] for p in active) / len(active) if active else 0
        return JSONResponse(content={
            "total_partners": len(PARTNERS),
            "active_partners": len(active),
            "current_mrr": CURRENT_MRR,
            "potential_mrr": POTENTIAL_MRR,
            "avg_success_rate_active": round(avg_sr, 3),
            "total_gpu_hrs": sum(p["gpu_hrs_used"] for p in PARTNERS.values()),
            "total_fine_tune_runs": sum(p["fine_tune_runs"] for p in PARTNERS.values()),
        })


if __name__ == "__main__":
    if FastAPI is None:
        raise RuntimeError("fastapi not installed. Run: pip install fastapi uvicorn")
    uvicorn.run("partner_dashboard:app", host="0.0.0.0", port=8136, reload=True)

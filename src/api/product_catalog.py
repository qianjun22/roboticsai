"""OCI Robot Cloud — Product Catalog & Pricing  (port 8172)"""
from __future__ import annotations

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as _e:
    raise SystemExit(f"Missing dependency: {_e}.  Run: pip install fastapi uvicorn") from _e

app = FastAPI(title="OCI Robot Cloud — Product Catalog", version="1.0.0")

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

TIERS: dict[str, dict] = {
    "starter": {
        "price_per_gpu_hr": 3.46,
        "fine_tune_price": 80,
        "eval_price": 0.25,
        "storage_gb_price": 0.05,
        "sla_uptime": 99.0,
        "support": "community",
        "max_concurrent_jobs": 1,
        "description": "Single robot, getting started",
    },
    "growth": {
        "price_per_gpu_hr": 3.26,
        "fine_tune_price": 65,
        "eval_price": 0.20,
        "storage_gb_price": 0.04,
        "sla_uptime": 99.5,
        "support": "business_hours",
        "max_concurrent_jobs": 3,
        "description": "Small fleet, active development",
    },
    "enterprise": {
        "price_per_gpu_hr": 3.06,
        "fine_tune_price": 50,
        "eval_price": 0.15,
        "storage_gb_price": 0.03,
        "sla_uptime": 99.9,
        "support": "24x7",
        "max_concurrent_jobs": 10,
        "description": "Full fleet, production ready",
    },
}

ADDONS: dict[str, dict] = {
    "dagger_online_learning": {
        "price_per_run": 120,
        "description": "DAgger online improvement loop (500 steps)",
    },
    "sdg_generation": {
        "price_per_1000_demos": 45,
        "description": "Genesis SDG synthetic data generation",
    },
    "jetson_deploy_package": {
        "price_one_time": 200,
        "description": "Student model distillation + Jetson packaging",
    },
    "nvidia_certified_eval": {
        "price_per_run": 150,
        "description": "NVIDIA Isaac Sim certified evaluation suite",
    },
    "priority_support_ticket": {
        "price_per_ticket": 75,
        "description": "4-hour response SLA engineering support",
    },
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _pricing_comparison_svg() -> str:
    """680x220 three-column tier comparison table SVG."""
    cols = ["Feature", "Starter", "Growth", "Enterprise"]
    rows = [
        ("GPU $/hr",        "$3.46",  "$3.26",  "$3.06"),
        ("Fine-tune / run", "$80",    "$65",    "$50"),
        ("Eval / run",      "$0.25",  "$0.20",  "$0.15"),
        ("Storage $/GB",    "$0.05",  "$0.04",  "$0.03"),
        ("SLA uptime",      "99.0%",  "99.5%",  "99.9%"),
        ("Support",         "Community", "Biz hrs", "24×7"),
        ("Concurrent jobs", "1",      "3",      "10"),
    ]

    W, H = 680, 220
    COL_W = [180, 140, 140, 140]
    ROW_H = 24
    HEADER_H = 30
    X_OFFSETS = [10, 210, 360, 510]

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace">',
    ]

    # Header background
    lines.append(f'<rect x="0" y="0" width="{W}" height="{HEADER_H}" fill="#1e293b"/>')
    # Enterprise column highlight
    lines.append(f'<rect x="{X_OFFSETS[3]}" y="0" width="{COL_W[3]}" height="{H}" fill="#1a0a07" opacity="0.6"/>')

    for ci, (label, x) in enumerate(zip(cols, X_OFFSETS)):
        colour = "#C74634" if ci == 3 else "#f8fafc"
        weight = "bold"
        lines.append(f'<text x="{x+6}" y="20" fill="{colour}" font-size="13" font-weight="{weight}">{label}</text>')

    for ri, row in enumerate(rows):
        y = HEADER_H + ri * ROW_H
        bg = "#1e293b" if ri % 2 == 0 else "#0f172a"
        lines.append(f'<rect x="0" y="{y}" width="{W}" height="{ROW_H}" fill="{bg}"/>')
        for ci, (cell, x) in enumerate(zip(row, X_OFFSETS)):
            if ci == 3:
                colour = "#C74634"
            elif ci == 0:
                colour = "#94a3b8"
            else:
                colour = "#e2e8f0"
            lines.append(
                f'<text x="{x+6}" y="{y+16}" fill="{colour}" font-size="12">{cell}</text>'
            )

    # Grid lines
    for ri in range(len(rows) + 1):
        y = HEADER_H + ri * ROW_H
        lines.append(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="#334155" stroke-width="1"/>')
    for x in X_OFFSETS[1:]:
        lines.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{H}" stroke="#334155" stroke-width="1"/>')

    lines.append("</svg>")
    return "\n".join(lines)


def _cost_calculator_html() -> str:
    """Returns an HTML snippet with cost breakdown and breakeven analysis."""
    # 1000 fine-tune steps = 1 fine-tune run; GPU time ~ 1000/2.35 * (1/3600) * 8 GPUs
    steps = 1000
    gpu_hrs_per_run = round(steps / 2.35 / 3600 * 8, 3)  # ~0.001 h, effectively minimal
    rows = []
    for name, t in TIERS.items():
        gpu_cost = round(t["price_per_gpu_hr"] * gpu_hrs_per_run, 4)
        ft_cost = t["fine_tune_price"]
        total = round(gpu_cost + ft_cost, 2)
        rows.append((name.capitalize(), t["price_per_gpu_hr"], ft_cost, total))

    # Breakeven vs DGX on-prem ($400k amortised over 5yr = $6,667/mo)
    dgx_monthly = 400_000 / 60
    breakeven_months_growth = round(dgx_monthly / (TIERS["growth"]["fine_tune_price"] * 10), 1)

    html = "<table style='width:100%;border-collapse:collapse;font-size:13px;color:#e2e8f0'>"
    html += "<tr style='background:#1e293b'><th style='padding:6px 10px;text-align:left'>Tier</th>"
    html += "<th>GPU $/hr</th><th>Fine-tune cost</th><th>Total (1k steps)</th></tr>"
    for name, gpu_hr, ft, total in rows:
        html += f"<tr><td style='padding:5px 10px'>{name}</td><td>${gpu_hr}</td><td>${ft}</td><td style='color:#38bdf8'>${total}</td></tr>"
    html += "</table>"
    html += f"<p style='margin-top:10px;font-size:12px;color:#94a3b8'>"
    html += f"On-prem DGX amortised: <strong style='color:#f8fafc'>~${dgx_monthly:,.0f}/mo</strong> &nbsp;|&nbsp; "
    html += f"OCI Growth tier break-even vs DGX: <strong style='color:#38bdf8'>~{breakeven_months_growth} months</strong></p>"
    return html


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    svg = _pricing_comparison_svg()
    calc = _cost_calculator_html()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OCI Robot Cloud — Product Catalog</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
  h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
  h2 {{ color: #38bdf8; font-size: 15px; margin: 20px 0 10px; }}
  .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
  .card {{ background: #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
  .tier-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 20px; }}
  .tier-card {{ background: #1e293b; border-radius: 8px; padding: 14px; border: 1px solid #334155; }}
  .tier-card.enterprise {{ border-color: #C74634; }}
  .tier-name {{ font-size: 15px; font-weight: bold; color: #f8fafc; margin-bottom: 6px; }}
  .tier-desc {{ font-size: 12px; color: #94a3b8; margin-bottom: 10px; }}
  .price-big {{ font-size: 24px; color: #38bdf8; font-weight: bold; }}
  .price-unit {{ font-size: 11px; color: #64748b; }}
  .addon-row {{ display: flex; justify-content: space-between; padding: 7px 0; border-bottom: 1px solid #334155; font-size: 13px; }}
  .addon-price {{ color: #38bdf8; white-space: nowrap; padding-left: 12px; }}
  .endpoint {{ background: #0f172a; border-left: 3px solid #C74634; padding: 6px 10px; font-size: 12px; color: #94a3b8; margin-bottom: 6px; border-radius: 0 4px 4px 0; }}
  .endpoint span {{ color: #38bdf8; }}
</style>
</head>
<body>
<h1>OCI Robot Cloud</h1>
<p class="subtitle">Product Catalog &amp; Pricing &nbsp;·&nbsp; Port 8172 &nbsp;·&nbsp; v1.0.0</p>

<div class="tier-grid">
  {''.join(f'''
  <div class="tier-card{' enterprise' if k == 'enterprise' else ''}">
    <div class="tier-name">{k.capitalize()}</div>
    <div class="tier-desc">{v['description']}</div>
    <div class="price-big">${v['price_per_gpu_hr']}</div>
    <div class="price-unit">per GPU hr</div>
    <div style="margin-top:8px;font-size:12px;color:#94a3b8">
      Fine-tune: <span style="color:#e2e8f0">${v['fine_tune_price']}/run</span> &nbsp;
      Eval: <span style="color:#e2e8f0">${v['eval_price']}/run</span><br>
      SLA: <span style="color:#e2e8f0">{v['sla_uptime']}%</span> &nbsp;
      Jobs: <span style="color:#e2e8f0">{v['max_concurrent_jobs']}</span> &nbsp;
      Support: <span style="color:#e2e8f0">{v['support']}</span>
    </div>
  </div>''' for k, v in TIERS.items())}
</div>

<div class="card">
  <h2>Tier Comparison</h2>
  {svg}
</div>

<div class="card">
  <h2>Add-On Services</h2>
  {''.join(f'''<div class="addon-row"><span><strong>{k}</strong> — {v['description']}</span>
  <span class="addon-price">${list(v.values())[0]}</span></div>''' for k, v in ADDONS.items())}
</div>

<div class="card">
  <h2>Cost Calculator — 1,000 Fine-Tune Steps</h2>
  {calc}
</div>

<div class="card">
  <h2>API Endpoints</h2>
  <div class="endpoint"><span>GET /</span> — This dashboard</div>
  <div class="endpoint"><span>GET /tiers</span> — All service tiers (JSON)</div>
  <div class="endpoint"><span>GET /addons</span> — Add-on services (JSON)</div>
  <div class="endpoint"><span>GET /estimate?tier=growth&amp;gpu_hrs=50&amp;fine_tune_runs=4</span> — Cost estimate</div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return _dashboard_html()


@app.get("/tiers")
def get_tiers() -> JSONResponse:
    return JSONResponse(content=TIERS)


@app.get("/addons")
def get_addons() -> JSONResponse:
    return JSONResponse(content=ADDONS)


@app.get("/estimate")
def get_estimate(
    tier: str = Query(default="growth", description="Tier name: starter | growth | enterprise"),
    gpu_hrs: float = Query(default=50.0, description="GPU hours"),
    fine_tune_runs: int = Query(default=4, description="Number of fine-tune runs"),
    eval_runs: int = Query(default=0, description="Number of eval runs"),
    storage_gb: float = Query(default=0.0, description="Storage in GB"),
) -> JSONResponse:
    if tier not in TIERS:
        return JSONResponse(status_code=400, content={"error": f"Unknown tier '{tier}'"})
    t = TIERS[tier]
    gpu_cost = round(gpu_hrs * t["price_per_gpu_hr"], 2)
    ft_cost = round(fine_tune_runs * t["fine_tune_price"], 2)
    eval_cost = round(eval_runs * t["eval_price"], 2)
    storage_cost = round(storage_gb * t["storage_gb_price"], 2)
    total = round(gpu_cost + ft_cost + eval_cost + storage_cost, 2)
    return JSONResponse(content={
        "tier": tier,
        "inputs": {
            "gpu_hrs": gpu_hrs,
            "fine_tune_runs": fine_tune_runs,
            "eval_runs": eval_runs,
            "storage_gb": storage_gb,
        },
        "breakdown": {
            "gpu_compute": gpu_cost,
            "fine_tuning": ft_cost,
            "evaluation": eval_cost,
            "storage": storage_cost,
        },
        "total_usd": total,
        "sla_uptime_pct": t["sla_uptime"],
    })


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8172)

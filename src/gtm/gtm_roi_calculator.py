"""gtm_roi_calculator.py — Customer ROI calculator for OCI Robot Cloud (port 10013).

Helps GTM and sales teams demonstrate economic value of OCI Robot Cloud to
potential customers across pick-and-place, assembly, and quality inspection
use cases.
"""

import json
import math
from typing import Any, Dict, List

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10013
SERVICE_NAME = "gtm_roi_calculator"

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

BENCHMARKS: List[Dict[str, Any]] = [
    {
        "use_case": "pick_and_place",
        "display_name": "Pick & Place",
        "avg_baseline_sr": 0.62,
        "avg_oci_sr": 0.91,
        "labor_cost_per_hour_usd": 28.50,
        "robot_hours_per_day": 20,
        "oci_cloud_cost_per_month_usd": 430,
        "roi_multiple": 641,
        "annual_savings_usd": 276000,
        "time_to_value_months": 4,
        "description": "High-mix bin picking with 29pp SR lift via GR00T fine-tuning.",
    },
    {
        "use_case": "assembly",
        "display_name": "Assembly",
        "avg_baseline_sr": 0.54,
        "avg_oci_sr": 0.86,
        "labor_cost_per_hour_usd": 34.00,
        "robot_hours_per_day": 18,
        "oci_cloud_cost_per_month_usd": 590,
        "roi_multiple": 512,
        "annual_savings_usd": 341000,
        "time_to_value_months": 5,
        "description": "Precision assembly lines; 32pp SR lift; reduced defect rework cost.",
    },
    {
        "use_case": "quality_inspection",
        "display_name": "Quality Inspection",
        "avg_baseline_sr": 0.71,
        "avg_oci_sr": 0.95,
        "labor_cost_per_hour_usd": 42.00,
        "robot_hours_per_day": 22,
        "oci_cloud_cost_per_month_usd": 520,
        "roi_multiple": 389,
        "annual_savings_usd": 203000,
        "time_to_value_months": 3,
        "description": "Vision-guided QC; 24pp SR lift; 60% reduction in false rejects.",
    },
]

BENCHMARK_MAP = {b["use_case"]: b for b in BENCHMARKS}


def _calc_roi(
    use_case: str,
    current_sr: float,
    target_volume: int,
) -> Dict[str, Any]:
    bm = BENCHMARK_MAP.get(use_case)
    if bm is None:
        use_case = "pick_and_place"
        bm = BENCHMARK_MAP[use_case]

    # Clamp inputs
    current_sr = max(0.01, min(0.99, current_sr))
    target_volume = max(1, min(1_000_000, target_volume))

    projected_sr = min(0.97, max(current_sr, bm["avg_oci_sr"]))
    sr_lift_pp = (projected_sr - current_sr) * 100

    # Revenue impact: each SR point at target_volume tasks/day
    tasks_gained_daily = target_volume * (projected_sr - current_sr)
    # Assume each task is worth $0.50 in direct value (conservative)
    task_value_usd = 0.50
    revenue_impact_annual = tasks_gained_daily * task_value_usd * 365

    # Labor savings: SR improvement reduces manual intervention
    labor_saved_hours_daily = tasks_gained_daily * 0.004  # 0.004 hr/task
    labor_savings_annual = labor_saved_hours_daily * bm["labor_cost_per_hour_usd"] * 365

    # Cloud cost
    oci_cost_annual = bm["oci_cloud_cost_per_month_usd"] * 12

    total_annual_savings = labor_savings_annual + revenue_impact_annual
    roi_multiple = round(total_annual_savings / max(oci_cost_annual, 1), 1)

    # Time-to-value: scale with how far current_sr is from baseline
    sr_gap = bm["avg_oci_sr"] - current_sr
    ttv_months = bm["time_to_value_months"]
    if sr_gap > 0.30:
        ttv_months = min(ttv_months + 2, 12)
    elif sr_gap < 0.10:
        ttv_months = max(ttv_months - 1, 1)

    return {
        "use_case": use_case,
        "current_sr": round(current_sr, 4),
        "projected_sr": round(projected_sr, 4),
        "sr_lift_pp": round(sr_lift_pp, 2),
        "target_volume_daily": target_volume,
        "roi_multiple": roi_multiple,
        "annual_savings_usd": round(total_annual_savings),
        "time_to_value_months": ttv_months,
        "breakdown": {
            "labor_savings_annual_usd": round(labor_savings_annual),
            "revenue_impact_annual_usd": round(revenue_impact_annual),
            "oci_cloud_cost_annual_usd": round(oci_cost_annual),
            "net_annual_benefit_usd": round(total_annual_savings - oci_cost_annual),
        },
    }


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

def _html_dashboard() -> str:
    chart_w, chart_h = 540, 220
    bar_w = 60
    group_gap = (chart_w - len(BENCHMARKS) * bar_w * 2) / (len(BENCHMARKS) + 1)
    max_roi = max(b["roi_multiple"] for b in BENCHMARKS)
    y_origin = chart_h - 30
    scale = (chart_h - 50) / max_roi

    bars_svg = ""
    for i, bm in enumerate(BENCHMARKS):
        x_center = group_gap * (i + 1) + bar_w * i * 2 + bar_w
        # ROI bar (sky blue)
        h_roi = bm["roi_multiple"] * scale
        x_b = x_center - bar_w / 2
        bars_svg += (
            f'<rect x="{x_b:.1f}" y="{y_origin - h_roi:.1f}" '
            f'width="{bar_w:.1f}" height="{h_roi:.1f}" fill="#38bdf8" rx="3"/>'
            f'<text x="{x_b + bar_w/2:.1f}" y="{y_origin - h_roi - 5:.1f}" '
            f'fill="#38bdf8" font-size="10" text-anchor="middle">{bm["roi_multiple"]}×</text>'
            f'<text x="{x_b + bar_w/2:.1f}" y="{chart_h - 8:.1f}" '
            f'fill="#94a3b8" font-size="9" text-anchor="middle">{bm["display_name"]}</text>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GTM ROI Calculator — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 32px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 28px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 20px; }}
    .card h2 {{ color: #38bdf8; font-size: 1rem; margin-bottom: 14px; }}
    .stat {{ display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 0.88rem; }}
    .stat .val {{ color: #f1f5f9; font-weight: 600; }}
    .highlight {{ color: #38bdf8; }}
    .warn {{ color: #C74634; }}
    .big {{ font-size: 2rem; font-weight: 700; color: #38bdf8; }}
    .big-label {{ font-size: 0.78rem; color: #64748b; margin-top: 2px; }}
    .big-wrap {{ text-align: center; padding: 10px 0; }}
    .big-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
    th {{ color: #64748b; text-align: left; padding: 6px 8px; border-bottom: 1px solid #334155; }}
    td {{ padding: 6px 8px; border-bottom: 1px solid #1e293b; }}
    .chart-wrap {{ background: #1e293b; border-radius: 10px; padding: 20px; }}
    .chart-wrap h2 {{ color: #38bdf8; font-size: 1rem; margin-bottom: 12px; }}
    footer {{ color: #334155; font-size: 0.75rem; margin-top: 24px; }}
  </style>
</head>
<body>
  <h1>GTM ROI Calculator</h1>
  <p class="subtitle">Customer ROI for OCI Robot Cloud · Port {PORT}</p>

  <div class="grid">
    <div class="card">
      <h2>Pick &amp; Place Highlights</h2>
      <div class="big-grid">
        <div class="big-wrap"><div class="big">641×</div><div class="big-label">ROI Multiple</div></div>
        <div class="big-wrap"><div class="big" style="color:#C74634">$276K</div><div class="big-label">Labor Savings / yr</div></div>
        <div class="big-wrap"><div class="big">4 mo</div><div class="big-label">Time to Value</div></div>
      </div>
      <div class="stat" style="margin-top:14px"><span>Baseline SR</span><span class="val warn">62%</span></div>
      <div class="stat"><span>OCI SR</span><span class="val highlight">91%</span></div>
      <div class="stat"><span>SR Lift</span><span class="val">+29 pp</span></div>
      <div class="stat"><span>OCI Cost / mo</span><span class="val">$430</span></div>
    </div>
    <div class="card">
      <h2>Use Case Benchmarks</h2>
      <table>
        <thead>
          <tr><th>Use Case</th><th>ROI</th><th>Savings/yr</th><th>TTV</th></tr>
        </thead>
        <tbody>
          {''.join(f'<tr><td>{b["display_name"]}</td><td class="highlight">{b["roi_multiple"]}×</td><td style="color:#C74634">${b["annual_savings_usd"]:,}</td><td>{b["time_to_value_months"]} mo</td></tr>' for b in BENCHMARKS)}
        </tbody>
      </table>
    </div>
  </div>

  <div class="chart-wrap">
    <h2>ROI Multiple by Use Case</h2>
    <svg width="{chart_w}" height="{chart_h}" style="display:block;overflow:visible">
      <line x1="0" y1="{y_origin}" x2="{chart_w}" y2="{y_origin}" stroke="#334155" stroke-width="1"/>
      {bars_svg}
    </svg>
  </div>

  <footer>OCI Robot Cloud · gtm_roi_calculator · /health · /gtm/roi (POST) · /gtm/benchmarks (GET)</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="GTM ROI Calculator",
        description="Customer ROI calculator for OCI Robot Cloud GTM and sales teams.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _html_dashboard()

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "service": SERVICE_NAME, "port": PORT})

    @app.get("/gtm/benchmarks")
    def benchmarks():
        return JSONResponse({"benchmarks": BENCHMARKS, "count": len(BENCHMARKS)})

    @app.post("/gtm/roi")
    async def roi(payload: dict):
        use_case = payload.get("use_case", "pick_and_place")
        current_sr = float(payload.get("current_sr", 0.62))
        target_volume = int(payload.get("target_volume", 1000))
        result = _calc_roi(use_case, current_sr, target_volume)
        return JSONResponse(result)


# ---------------------------------------------------------------------------
# Fallback: stdlib HTTP server
# ---------------------------------------------------------------------------

else:
    class _Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: str, ctype: str = "application/json"):
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/":
                self._send(200, _html_dashboard(), "text/html")
            elif self.path == "/health":
                self._send(200, json.dumps({"status": "ok", "service": SERVICE_NAME, "port": PORT}))
            elif self.path == "/gtm/benchmarks":
                self._send(200, json.dumps({"benchmarks": BENCHMARKS, "count": len(BENCHMARKS)}))
            else:
                self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):
            if self.path == "/gtm/roi":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                result = _calc_roi(
                    body.get("use_case", "pick_and_place"),
                    float(body.get("current_sr", 0.62)),
                    int(body.get("target_volume", 1000)),
                )
                self._send(200, json.dumps(result))
            else:
                self._send(404, json.dumps({"error": "not found"}))

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[fallback] Serving on http://0.0.0.0:{PORT} (stdlib HTTPServer)")
        HTTPServer(("0.0.0.0", PORT), _Handler).serve_forever()

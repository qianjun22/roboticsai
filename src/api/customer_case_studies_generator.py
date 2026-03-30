"""Customer Case Studies Generator — FastAPI port 8801"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8801

CASES = [
    {
        "customer": "Aethon Logistics",
        "industry": "Warehouse Automation",
        "use_case": "Bin-picking & palletization with GR00T-N1.6 on OCI A100",
        "before_oee": 61,
        "after_oee": 89,
        "cycle_time_s": 3.8,
        "error_rate_before": 4.2,
        "error_rate_after": 0.31,
        "roi_months": 7,
        "robots": 24,
        "region": "US-East",
        "status": "Production",
    },
    {
        "customer": "Solara Manufacturing",
        "industry": "Electronics Assembly",
        "use_case": "PCB micro-placement fine-tuned with 800 demos via OCI SDG",
        "before_oee": 54,
        "after_oee": 83,
        "cycle_time_s": 1.9,
        "error_rate_before": 6.7,
        "error_rate_after": 0.18,
        "roi_months": 5,
        "robots": 12,
        "region": "EU-Frankfurt",
        "status": "Production",
    },
    {
        "customer": "NovaMed Devices",
        "industry": "Medical Device Assembly",
        "use_case": "Sterile catheter assembly with sim-to-real validation pipeline",
        "before_oee": 48,
        "after_oee": 77,
        "cycle_time_s": 5.2,
        "error_rate_before": 8.1,
        "error_rate_after": 0.42,
        "roi_months": 10,
        "robots": 8,
        "region": "AP-Tokyo",
        "status": "Pilot",
    },
    {
        "customer": "Cerulean Foods",
        "industry": "Food & Beverage",
        "use_case": "Deformable object handling (dough, packaging) via DAgger curriculum",
        "before_oee": 57,
        "after_oee": 81,
        "cycle_time_s": 2.6,
        "error_rate_before": 3.9,
        "error_rate_after": 0.55,
        "roi_months": 8,
        "robots": 16,
        "region": "US-West",
        "status": "Production",
    },
    {
        "customer": "Vertex Automotive",
        "industry": "Automotive Tier-1",
        "use_case": "Bolt-torque insertion + QC vision with multi-task policy distillation",
        "before_oee": 66,
        "after_oee": 92,
        "cycle_time_s": 4.4,
        "error_rate_before": 2.8,
        "error_rate_after": 0.09,
        "roi_months": 6,
        "robots": 40,
        "region": "EU-Munich",
        "status": "Production",
    },
]

def _sparkline_svg(values, width=120, height=32, color="#38bdf8"):
    mn, mx = min(values), max(values)
    span = mx - mn or 1
    pts = [
        (int(i * (width - 4) / (len(values) - 1)) + 2,
         int((1 - (v - mn) / span) * (height - 4)) + 2)
        for i, v in enumerate(values)
    ]
    poly = " ".join(f"{x},{y}" for x, y in pts)
    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="1.5"/>'
        f'<circle cx="{pts[-1][0]}" cy="{pts[-1][1]}" r="2.5" fill="{color}"/>'
        "</svg>"
    )

def _radial_gauge_svg(pct, label, size=90):
    """Arc gauge 0-100. pct = 0..100"""
    cx, cy, r = size // 2, size // 2, size // 2 - 8
    start_angle = math.pi * 0.75
    sweep = math.pi * 1.5
    end_angle = start_angle + sweep * (pct / 100)
    # Track arc (full)
    def arc_path(a1, a2, rr):
        x1 = cx + rr * math.cos(a1)
        y1 = cy + rr * math.sin(a1)
        x2 = cx + rr * math.cos(a2)
        y2 = cy + rr * math.sin(a2)
        large = 1 if (a2 - a1) > math.pi else 0
        return f"M {x1:.1f},{y1:.1f} A {rr},{rr} 0 {large} 1 {x2:.1f},{y2:.1f}"
    track = arc_path(start_angle, start_angle + sweep, r)
    fill = arc_path(start_angle, end_angle, r)
    color = "#4ade80" if pct >= 80 else ("#facc15" if pct >= 60 else "#f87171")
    return (
        f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">'
        f'<path d="{track}" stroke="#334155" stroke-width="7" fill="none"/>'
        f'<path d="{fill}" stroke="{color}" stroke-width="7" fill="none" stroke-linecap="round"/>'
        f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" fill="{color}" font-size="13" font-weight="700">{pct}%</text>'
        f'<text x="{cx}" y="{cy + 16}" text-anchor="middle" fill="#64748b" font-size="7">{label}</text>'
        "</svg>"
    )

def _roi_waterfall_svg(cases, width=460, height=140):
    """Horizontal bars: ROI months per case"""
    max_m = max(c["roi_months"] for c in cases)
    bh = (height - 20) // len(cases) - 4
    bars = []
    colors = ["#38bdf8", "#818cf8", "#a78bfa", "#34d399", "#f472b6"]
    for i, c in enumerate(cases):
        bw = int(c["roi_months"] / max_m * (width - 110))
        y = i * (bh + 4) + 2
        bars.append(
            f'<rect x="90" y="{y}" width="{bw}" height="{bh}" fill="{colors[i % len(colors)]}" rx="3" opacity="0.85"/>'
            f'<text x="85" y="{y + bh - 2}" text-anchor="end" fill="#94a3b8" font-size="9">{c["customer"].split()[0]}</text>'
            f'<text x="{90 + bw + 4}" y="{y + bh - 2}" fill="#e2e8f0" font-size="9">{c["roi_months"]}mo</text>'
        )
    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{width}" height="{height}" fill="#0f172a" rx="6"/>'
        + "".join(bars)
        + "</svg>"
    )

def _error_rate_comparison_svg(cases, width=460, height=150):
    n = len(cases)
    group_w = (width - 20) // n
    bar_w = group_w // 3
    svgs = []
    for i, c in enumerate(cases):
        x_base = i * group_w + 10
        max_e = c["error_rate_before"]
        # Before bar
        bh_b = int(c["error_rate_before"] / max_e * (height - 30))
        bh_a = int(c["error_rate_after"] / max_e * (height - 30))
        x_b = x_base + 2
        x_a = x_base + bar_w + 4
        svgs.append(
            f'<rect x="{x_b}" y="{height - 20 - bh_b}" width="{bar_w}" height="{bh_b}" fill="#f87171" rx="2" opacity="0.8"/>'
            f'<rect x="{x_a}" y="{height - 20 - bh_a}" width="{bar_w}" height="{bh_a}" fill="#4ade80" rx="2" opacity="0.8"/>'
            f'<text x="{x_base + bar_w}" y="{height - 6}" text-anchor="middle" fill="#64748b" font-size="8">{c["customer"].split()[0]}</text>'
            f'<text x="{x_b + bar_w//2}" y="{height - 22 - bh_b}" text-anchor="middle" fill="#fca5a5" font-size="7">{c["error_rate_before"]}%</text>'
            f'<text x="{x_a + bar_w//2}" y="{height - 22 - bh_a}" text-anchor="middle" fill="#86efac" font-size="7">{c["error_rate_after"]}%</text>'
        )
    legend = (
        f'<rect x="10" y="4" width="10" height="8" fill="#f87171" rx="1"/>'
        f'<text x="24" y="12" fill="#fca5a5" font-size="8">Before</text>'
        f'<rect x="70" y="4" width="10" height="8" fill="#4ade80" rx="1"/>'
        f'<text x="84" y="12" fill="#86efac" font-size="8">After</text>'
    )
    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{width}" height="{height}" fill="#0f172a" rx="6"/>'
        + legend + "".join(svgs)
        + "</svg>"
    )

def build_html():
    random.seed()

    total_robots = sum(c["robots"] for c in CASES)
    avg_oee_gain = sum(c["after_oee"] - c["before_oee"] for c in CASES) / len(CASES)
    avg_roi = sum(c["roi_months"] for c in CASES) / len(CASES)
    avg_error_reduction = sum(
        (1 - c["error_rate_after"] / c["error_rate_before"]) * 100 for c in CASES
    ) / len(CASES)

    roi_svg = _roi_waterfall_svg(CASES)
    err_svg = _error_rate_comparison_svg(CASES)

    # OEE sparklines (simulated trajectory)
    def oee_traj(before, after, n=12):
        return [
            before + (after - before) * (1 - math.exp(-3 * t / n)) + random.gauss(0, 0.5)
            for t in range(n)
        ]

    case_cards = ""
    status_colors = {"Production": "#4ade80", "Pilot": "#facc15", "POC": "#f472b6"}
    for c in CASES:
        sc = status_colors.get(c["status"], "#94a3b8")
        oee_spark = _sparkline_svg(oee_traj(c["before_oee"], c["after_oee"]), color="#38bdf8")
        gauge_b = _radial_gauge_svg(c["before_oee"], "Before", size=80)
        gauge_a = _radial_gauge_svg(c["after_oee"], "After", size=80)
        oee_delta = c["after_oee"] - c["before_oee"]
        err_delta = round((1 - c["error_rate_after"] / c["error_rate_before"]) * 100, 1)
        case_cards += f"""
        <div class='case-card'>
          <div style='display:flex;align-items:center;gap:10px;margin-bottom:10px'>
            <div>
              <div style='font-size:1rem;font-weight:700;color:#e2e8f0'>{c['customer']}</div>
              <div style='font-size:.75rem;color:#94a3b8'>{c['industry']} · {c['region']}</div>
            </div>
            <span style='margin-left:auto;background:{sc}22;color:{sc};border:1px solid {sc};font-size:.65rem;padding:2px 8px;border-radius:10px'>{c['status']}</span>
          </div>
          <p style='font-size:.78rem;color:#cbd5e1;margin:0 0 10px'>{c['use_case']}</p>
          <div style='display:flex;gap:10px;align-items:center'>
            {gauge_b}{gauge_a}
            <div style='flex:1'>
              <div style='font-size:.72rem;color:#64748b'>OEE Trend</div>
              {oee_spark}
              <div style='font-size:.72rem;color:#64748b;margin-top:4px'>OEE +{oee_delta}pp · Error ↓{err_delta}% · ROI {c['roi_months']}mo · {c['robots']} robots</div>
            </div>
          </div>
        </div>"""

    return f"""<!DOCTYPE html><html lang='en'><head>
<meta charset='UTF-8'/><title>Customer Case Studies Generator</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
  header{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:16px}}
  h1{{margin:0;font-size:1.4rem;color:#C74634;letter-spacing:.03em}}
  .badge{{background:#C74634;color:#fff;font-size:.7rem;padding:2px 8px;border-radius:12px;font-weight:700}}
  .main{{max-width:1200px;margin:auto;padding:20px}}
  .kpi-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
  .kpi{{background:#1e293b;padding:16px;border-radius:10px;border:1px solid #334155;text-align:center}}
  .kpi-val{{font-size:1.8rem;font-weight:700;color:#38bdf8}}
  .kpi-lbl{{font-size:.73rem;color:#64748b;margin-top:2px}}
  .charts{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}}
  .card{{background:#1e293b;padding:18px;border-radius:10px;border:1px solid #334155}}
  h2{{margin:0 0 12px;font-size:.95rem;color:#38bdf8}}
  .cases{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
  .case-card{{background:#1e293b;padding:16px;border-radius:10px;border:1px solid #334155}}
  .pill{{display:inline-block;background:#0f172a;border:1px solid #334155;border-radius:6px;padding:3px 9px;font-size:.72rem;color:#7dd3fc;margin:2px}}
</style></head><body>
<header>
  <h1>Customer Case Studies Generator</h1>
  <span class='badge'>Port {PORT}</span>
  <span style='margin-left:auto;font-size:.8rem;color:#64748b'>OCI Robot Cloud — Sales Enablement</span>
</header>
<div class='main'>
  <div class='kpi-row'>
    <div class='kpi'><div class='kpi-val'>{len(CASES)}</div><div class='kpi-lbl'>Active Case Studies</div></div>
    <div class='kpi'><div class='kpi-val'>{total_robots}</div><div class='kpi-lbl'>Total Robots Deployed</div></div>
    <div class='kpi'><div class='kpi-val'>+{avg_oee_gain:.0f}pp</div><div class='kpi-lbl'>Avg OEE Improvement</div></div>
    <div class='kpi'><div class='kpi-val'>{avg_roi:.1f}mo</div><div class='kpi-lbl'>Avg Payback Period</div></div>
  </div>
  <div class='charts'>
    <div class='card'>
      <h2>Payback Period by Customer (months)</h2>
      {roi_svg}
    </div>
    <div class='card'>
      <h2>Error Rate: Before vs After Deployment</h2>
      {err_svg}
      <p style='font-size:.72rem;color:#64748b;margin:6px 0 0'>Avg defect reduction: {avg_error_reduction:.1f}%</p>
    </div>
  </div>
  <h2 style='color:#38bdf8;margin-bottom:12px'>Case Study Library</h2>
  <div class='cases'>{case_cards}</div>
  <div style='margin-top:18px;display:flex;gap:6px;flex-wrap:wrap'>
    <span class='pill'>GR00T-N1.6</span><span class='pill'>OCI A100</span>
    <span class='pill'>DAgger</span><span class='pill'>Isaac Sim SDG</span>
    <span class='pill'>Sim-to-Real Validation</span><span class='pill'>Multi-task Distillation</span>
    <span class='pill'>LeRobot Dataset</span><span class='pill'>Cosmos World Model</span>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Customer Case Studies Generator")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "customer_case_studies_generator"}

    @app.get("/cases")
    def list_cases():
        return {"count": len(CASES), "cases": [{"customer": c["customer"], "industry": c["industry"], "roi_months": c["roi_months"]} for c in CASES]}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a):
        pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"Serving customer_case_studies_generator on http://0.0.0.0:{PORT}")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

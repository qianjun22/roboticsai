"""Technical Win Rate Analyzer — FastAPI port 8815"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8815

def build_html():
    random.seed(99)

    # Competitors
    competitors = ["AWS RoboMaker", "Azure Robot", "GCP AutoML", "Covariant AI", "Physical Intel."]
    categories = ["Inference Speed", "Fine-tune Cost", "Multi-task", "Sim-to-Real", "SDK Ease", "Uptime SLA"]

    # OCI win rates per competitor per category (0..1)
    win_matrix = []
    for ci, comp in enumerate(competitors):
        row = []
        for cat in categories:
            base = 0.55 + ci * 0.04 + random.gauss(0, 0.06)
            row.append(min(0.97, max(0.28, base)))
        win_matrix.append(row)

    # Win rate over time (12 months)
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    time_series = {}
    for ci, comp in enumerate(competitors):
        rates = []
        base_wr = 0.48 + ci * 0.03
        for m in range(12):
            t = m / 11
            wr = base_wr + 0.18 * t + 0.04 * math.sin(t * math.pi * 3) + random.gauss(0, 0.015)
            rates.append(min(0.96, max(0.3, wr)))
        time_series[comp] = rates

    # Overall win rate per competitor (weighted avg)
    overall = {comp: sum(win_matrix[ci]) / len(categories) for ci, comp in enumerate(competitors)}
    overall_oci = sum(overall.values()) / len(competitors)

    # Deal pipeline
    n_deals = 18
    deal_names = [
        "Toyota MFG Line A", "BMW Spot Clone", "Foxconn Assembly", "Tesla Body Shop",
        "Amazon Sort Ctr", "DHL Warehouse", "Siemens PLM", "Bosch Weld Bot",
        "Hyundai Cell 3", "TSMC Wafer Fab", "Nike Sole Auto", "Airbus Rivet",
        "Lockheed Weld", "SpaceX Harness", "Nvidia Demo Lab", "Meta AI HW",
        "Apple AMS", "Waymo Depot"
    ]
    deal_stages = ["Discovery", "POC", "Eval", "Negotiation", "Closed-Won"]
    stage_colors = ["#475569", "#0ea5e9", "#f59e0b", "#a78bfa", "#22c55e"]
    deals = []
    for i, name in enumerate(deal_names[:n_deals]):
        stage_idx = min(4, int(random.betavariate(2, 1.5) * 5))
        win_prob = 0.2 + stage_idx * 0.18 + random.gauss(0, 0.04)
        value = random.randint(80, 850) * 1000
        comp = random.choice(competitors)
        deals.append({"name": name, "stage": deal_stages[stage_idx], "stage_idx": stage_idx,
                       "win_prob": min(0.97, max(0.1, win_prob)), "value": value, "comp": comp})

    total_pipeline = sum(d["value"] for d in deals)
    weighted_pipeline = sum(d["value"] * d["win_prob"] for d in deals)
    closed_won = sum(d["value"] for d in deals if d["stage"] == "Closed-Won")

    # SVG: Win rate over time (multi-line, 640x200)
    tw, th = 640, 200
    pad = 44
    colors_ts = ["#38bdf8", "#f59e0b", "#C74634", "#a78bfa", "#22c55e"]

    def tx(i): return pad + (i / 11) * (tw - 2 * pad)
    def ty(v): return th - pad - (v - 0.25) / 0.75 * (th - 2 * pad)

    ts_lines = ""
    for ci, comp in enumerate(competitors):
        pts = " ".join(f"{tx(m):.1f},{ty(v):.1f}" for m, v in enumerate(time_series[comp]))
        ts_lines += f'<polyline points="{pts}" fill="none" stroke="{colors_ts[ci]}" stroke-width="2" opacity="0.85"/>'
        # Last point dot
        last_x, last_y = tx(11), ty(time_series[comp][11])
        ts_lines += f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="4" fill="{colors_ts[ci]}"/>'

    # 50% reference line
    ref_y = ty(0.5)
    ts_lines += f'<line x1="{pad}" y1="{ref_y:.1f}" x2="{tw - pad}" y2="{ref_y:.1f}" stroke="#64748b" stroke-width="1" stroke-dasharray="5,3"/>'
    ts_lines += f'<text x="{tw - pad + 3}" y="{ref_y + 4:.1f}" fill="#64748b" font-size="9">50%</text>'

    month_labels = "".join(f'<text x="{tx(i):.1f}" y="{th - pad + 14}" fill="#94a3b8" font-size="9" text-anchor="middle">{m}</text>'
                           for i, m in enumerate(months))
    grid_lines = "".join(f'<line x1="{pad}" y1="{ty(0.25 + k * 0.25):.1f}" x2="{tw - pad}" y2="{ty(0.25 + k * 0.25):.1f}" stroke="#1e293b" stroke-width="1"/>'
                         for k in range(4))

    # SVG: Category radar / bar chart per competitor (600x180)
    bar_w2, bar_h2 = 600, 180
    n_cats = len(categories)
    group_w = (bar_w2 - 2 * pad) / n_cats
    bar_inner = group_w * 0.8 / len(competitors)
    cat_bars = ""
    for ci, comp in enumerate(competitors):
        for catj, cat in enumerate(categories):
            wr = win_matrix[ci][catj]
            bh = wr * (bar_h2 - 2 * pad)
            bx = pad + catj * group_w + ci * bar_inner
            by = bar_h2 - pad - bh
            cat_bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_inner * 0.85:.1f}" height="{bh:.1f}" fill="{colors_ts[ci]}" opacity="0.82" rx="1"/>'

    cat_labels = "".join(f'<text x="{pad + j * group_w + group_w / 2:.1f}" y="{bar_h2 - pad + 13}" fill="#94a3b8" font-size="8" text-anchor="middle">{cat[:8]}</text>'
                         for j, cat in enumerate(categories))

    # SVG: Pipeline funnel (400x180)
    stage_counts = [sum(1 for d in deals if d["stage"] == s) for s in deal_stages]
    stage_values = [sum(d["value"] for d in deals if d["stage"] == s) for s in deal_stages]
    fw, fh = 400, 160
    fpad = 10
    max_count = max(stage_counts) or 1
    bar_gap = 8
    fn_bars = len(deal_stages)
    bar_height_f = (fh - 2 * fpad - (fn_bars - 1) * bar_gap) / fn_bars
    funnel_svg = ""
    for si, (s, cnt, val) in enumerate(zip(deal_stages, stage_counts, stage_values)):
        bw = (cnt / max_count) * (fw - 120)
        bx = (fw - 120 - bw) / 2
        by = fpad + si * (bar_height_f + bar_gap)
        funnel_svg += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bar_height_f:.1f}" fill="{stage_colors[si]}" rx="3" opacity="0.9"/>'
        funnel_svg += f'<text x="{fw - 118}" y="{by + bar_height_f * 0.65:.1f}" fill="#e2e8f0" font-size="10">{s}: {cnt} (${val/1e6:.1f}M)</text>'

    # Legend
    legend_html = "".join(f'<span style="margin-right:14px"><span style="display:inline-block;width:12px;height:12px;background:{colors_ts[ci]};border-radius:2px;vertical-align:middle;margin-right:4px"></span>{comp}</span>'
                          for ci, comp in enumerate(competitors))

    return f"""<!DOCTYPE html><html><head><title>Technical Win Rate Analyzer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 5px;margin:0;font-size:1.6rem}}
h2{{color:#38bdf8;margin:0 0 10px;font-size:1.05rem}}
.subtitle{{color:#94a3b8;padding:0 20px 14px;font-size:0.88rem}}
.card{{background:#1e293b;padding:18px;margin:10px;border-radius:8px;border:1px solid #334155}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.stat-row{{display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap}}
.stat{{background:#0f172a;border-radius:6px;padding:11px 16px;border-left:3px solid #38bdf8}}
.stat-val{{font-size:1.45rem;font-weight:700;color:#f1f5f9}}
.stat-lbl{{font-size:0.72rem;color:#94a3b8;margin-top:2px}}
.legend{{font-size:0.76rem;color:#cbd5e1;margin-bottom:10px;line-height:2}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{color:#94a3b8;text-align:left;padding:6px 8px;border-bottom:1px solid #334155;font-weight:500}}
td{{padding:5px 8px;border-bottom:1px solid #1e293b}}
tr:hover td{{background:#0f172a}}
.badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:0.72rem;font-weight:600}}
</style></head>
<body>
<h1>Technical Win Rate Analyzer</h1>
<div class="subtitle">OCI Robot Cloud vs. Competitors — Real-time competitive intelligence — Port {PORT}</div>

<div class="card">
  <div class="stat-row">
    <div class="stat" style="border-color:#22c55e"><div class="stat-val">{overall_oci:.1%}</div><div class="stat-lbl">Overall Win Rate</div></div>
    <div class="stat" style="border-color:#f59e0b"><div class="stat-val">${total_pipeline/1e6:.1f}M</div><div class="stat-lbl">Total Pipeline</div></div>
    <div class="stat" style="border-color:#38bdf8"><div class="stat-val">${weighted_pipeline/1e6:.1f}M</div><div class="stat-lbl">Risk-Adj. Pipeline</div></div>
    <div class="stat" style="border-color:#22c55e"><div class="stat-val">${closed_won/1e6:.1f}M</div><div class="stat-lbl">Closed-Won ARR</div></div>
    <div class="stat" style="border-color:#C74634"><div class="stat-val">{n_deals}</div><div class="stat-lbl">Active Deals</div></div>
  </div>
</div>

<div class="card">
  <h2>Win Rate Trend vs. Competitors (12 Months)</h2>
  <div class="legend">{legend_html}</div>
  <svg width="{tw}" height="{th}">
    {grid_lines}
    <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{th - pad}" stroke="#475569" stroke-width="1.5"/>
    <line x1="{pad}" y1="{th - pad}" x2="{tw - pad}" y2="{th - pad}" stroke="#475569" stroke-width="1.5"/>
    {ts_lines}
    {month_labels}
    <text x="{pad - 6}" y="{ty(0.25):.1f}" fill="#94a3b8" font-size="9" text-anchor="end">25%</text>
    <text x="{pad - 6}" y="{ty(0.75):.1f}" fill="#94a3b8" font-size="9" text-anchor="end">75%</text>
    <text x="{pad - 6}" y="{ty(1.0):.1f}" fill="#94a3b8" font-size="9" text-anchor="end">100%</text>
  </svg>
</div>

<div class="card">
  <h2>Win Rate by Category &amp; Competitor</h2>
  <div class="legend">{legend_html}</div>
  <svg width="{bar_w2}" height="{bar_h2}">
    <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{bar_h2 - pad}" stroke="#475569" stroke-width="1.5"/>
    <line x1="{pad}" y1="{bar_h2 - pad}" x2="{bar_w2 - pad}" y2="{bar_h2 - pad}" stroke="#475569" stroke-width="1.5"/>
    {cat_bars}
    {cat_labels}
    <!-- 50% line -->
    <line x1="{pad}" y1="{bar_h2 - pad - 0.5 * (bar_h2 - 2 * pad):.1f}" x2="{bar_w2 - pad}" y2="{bar_h2 - pad - 0.5 * (bar_h2 - 2 * pad):.1f}" stroke="#64748b" stroke-width="1" stroke-dasharray="4,3"/>
  </svg>
</div>

<div class="grid2">
  <div class="card">
    <h2>Deal Pipeline Funnel</h2>
    <svg width="{fw}" height="{fh}">
      {funnel_svg}
    </svg>
  </div>

  <div class="card">
    <h2>Active Deals</h2>
    <table>
      <tr><th>Account</th><th>Stage</th><th>Win%</th><th>Value</th></tr>
      {''.join(f'<tr><td>{d["name"]}</td><td><span class="badge" style="background:{stage_colors[d["stage_idx"]]}22;color:{stage_colors[d["stage_idx"]]}">{d["stage"]}</span></td><td style="color:{"#22c55e" if d["win_prob"] > 0.65 else "#f59e0b" if d["win_prob"] > 0.4 else "#ef4444'}">{d["win_prob"]:.0%}</td><td>${d["value"]/1e3:.0f}K</td></tr>' for d in sorted(deals, key=lambda x: -x["value"])[:10])}
    </table>
    <div style="font-size:0.73rem;color:#64748b;margin-top:6px">Showing top 10 deals by value. {n_deals} total active.</div>
  </div>
</div>

<div class="card" style="margin:10px">
  <h2>Competitive Positioning Summary</h2>
  <p style="color:#cbd5e1;line-height:1.6;margin:0">
    OCI Robot Cloud maintains a <strong style="color:#22c55e">{overall_oci:.1%} overall win rate</strong> across {len(competitors)} tracked competitors.
    Strongest advantage in <strong style="color:#38bdf8">Inference Speed</strong> and <strong style="color:#38bdf8">Fine-tune Cost</strong> due to A100 cluster pricing.
    Fastest-growing win rate: <strong style="color:#f1f5f9">{max(competitors, key=lambda c: time_series[c][-1] - time_series[c][0])}</strong> displacement (+{max(time_series[c][-1] - time_series[c][0] for c in competitors):.1%} YoY).
    Risk-adjusted pipeline coverage: <strong style="color:#a78bfa">{weighted_pipeline / total_pipeline:.1%}</strong>.
  </p>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Technical Win Rate Analyzer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

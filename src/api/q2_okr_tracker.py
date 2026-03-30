"""Q2 OKR Tracker — FastAPI port 8827"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8827

def build_html():
    random.seed(77)

    # Q2 Objectives and Key Results
    okrs = [
        {
            "objective": "Launch OCI Robot Cloud GA",
            "owner": "Jun Qian",
            "krs": [
                {"kr": "Onboard 5 design partners", "target": 5, "current": 3, "unit": "partners"},
                {"kr": "Achieve 99.9% inference uptime", "target": 99.9, "current": 99.4, "unit": "%"},
                {"kr": "Reduce cold-start latency to <300ms", "target": 300, "current": 227, "unit": "ms", "lower_is_better": True},
            ]
        },
        {
            "objective": "Fine-tuning Pipeline at Scale",
            "owner": "ML Infra",
            "krs": [
                {"kr": "Support 1000+ demo fine-tune jobs", "target": 1000, "current": 1000, "unit": "demos"},
                {"kr": "Achieve MAE < 0.02 on LIBERO tasks", "target": 0.02, "current": 0.013, "unit": "MAE", "lower_is_better": True},
                {"kr": "Multi-GPU DDP > 3x throughput", "target": 3.0, "current": 3.07, "unit": "x"},
            ]
        },
        {
            "objective": "Expand Embodiment Support",
            "owner": "Platform Eng",
            "krs": [
                {"kr": "GR00T N1.6 production deployment", "target": 1, "current": 1, "unit": "model"},
                {"kr": "Isaac Sim SDG pipeline validated", "target": 1, "current": 1, "unit": "pipeline"},
                {"kr": "Jetson Orin edge deploy tested", "target": 3, "current": 2, "unit": "devices"},
            ]
        },
        {
            "objective": "Revenue & Pipeline Growth",
            "owner": "GTM",
            "krs": [
                {"kr": "Pipeline ARR $500K+", "target": 500, "current": 420, "unit": "$K ARR"},
                {"kr": "CoRL paper accepted", "target": 1, "current": 0, "unit": "paper"},
                {"kr": "Demo video views > 10K", "target": 10000, "current": 7240, "unit": "views"},
            ]
        },
    ]

    def pct(kr):
        if kr.get("lower_is_better"):
            if kr["current"] <= kr["target"]:
                return 100
            return max(0, int(100 - (kr["current"] - kr["target"]) / kr["target"] * 100))
        return min(100, int(kr["current"] / kr["target"] * 100))

    def bar_color(p):
        if p >= 100: return "#34d399"
        if p >= 70: return "#38bdf8"
        if p >= 40: return "#fbbf24"
        return "#f87171"

    # Build OKR cards
    obj_colors = ["#38bdf8", "#818cf8", "#34d399", "#fbbf24"]
    cards_html = ""
    all_pcts = []
    for oi, obj in enumerate(okrs):
        krs_html = ""
        obj_pcts = []
        for kr in obj["krs"]:
            p = pct(kr)
            obj_pcts.append(p)
            all_pcts.append(p)
            bc = bar_color(p)
            disp_cur = kr["current"]
            disp_tgt = kr["target"]
            krs_html += f"""
            <div style="margin:10px 0">
              <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span style="font-size:0.85rem;color:#cbd5e1">{kr['kr']}</span>
                <span style="font-size:0.8rem;color:#64748b">{disp_cur} / {disp_tgt} {kr['unit']}</span>
              </div>
              <div style="background:#0f172a;border-radius:4px;height:10px;width:100%">
                <div style="background:{bc};height:10px;border-radius:4px;width:{p}%;transition:width 0.3s"></div>
              </div>
              <div style="text-align:right;font-size:0.75rem;color:{bc};margin-top:2px">{p}%</div>
            </div>"""
        avg_obj = int(sum(obj_pcts) / len(obj_pcts))
        cards_html += f"""
        <div class="card" style="border-left:4px solid {obj_colors[oi]}">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <h2 style="color:{obj_colors[oi]};margin:0">{obj['objective']}</h2>
            <div style="text-align:right">
              <div style="font-size:1.5rem;font-weight:bold;color:{bar_color(avg_obj)}">{avg_obj}%</div>
              <div style="font-size:0.7rem;color:#64748b">{obj['owner']}</div>
            </div>
          </div>
          {krs_html}
        </div>"""

    overall = int(sum(all_pcts) / len(all_pcts))

    # Weekly progress sparkline (simulate 13 weeks Q2 progress)
    weeks = list(range(1, 14))
    week_scores = [max(10, min(100, int(overall * (w / 13) + 5 * math.sin(w * 0.9) + random.gauss(0, 3)))) for w in weeks]
    week_scores[-1] = overall

    spark_w, spark_h = 520, 80
    max_s = max(week_scores) or 1
    points = []
    for i, s in enumerate(week_scores):
        x = int(i * spark_w / (len(weeks) - 1))
        y = spark_h - int(s / 100 * spark_h)
        points.append((x, y))

    polyline = " ".join(f"{x},{y}" for x, y in points)
    area_pts = f"0,{spark_h} " + polyline + f" {spark_w},{spark_h}"

    dots_svg = ""
    for i, (x, y) in enumerate(points):
        dots_svg += f'<circle cx="{x}" cy="{y}" r="3" fill="#38bdf8"/>'
        if i % 3 == 0:
            dots_svg += f'<text x="{x}" y="{spark_h+14}" text-anchor="middle" font-size="9" fill="#64748b">W{weeks[i]}</text>'

    sparkline_svg = f"""
    <svg width="{spark_w}" height="{spark_h+20}" style="display:block">
      <polygon points="{area_pts}" fill="#38bdf8" opacity="0.15"/>
      <polyline points="{polyline}" fill="none" stroke="#38bdf8" stroke-width="2"/>
      {dots_svg}
    </svg>"""

    # Radar-like chart for 4 objectives using SVG polar
    cx, cy, r = 150, 150, 110
    obj_pct_avgs = []
    for obj in okrs:
        ps = [pct(kr) for kr in obj["krs"]]
        obj_pct_avgs.append(sum(ps) / len(ps))

    n = len(okrs)
    radar_pts = []
    for i, p in enumerate(obj_pct_avgs):
        angle = math.pi / 2 - i * 2 * math.pi / n
        rx = cx + (p / 100) * r * math.cos(angle)
        ry = cy - (p / 100) * r * math.sin(angle)
        radar_pts.append((rx, ry))

    radar_poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in radar_pts)

    # Grid rings
    grid_svg = ""
    for ring in [0.25, 0.5, 0.75, 1.0]:
        ring_pts = []
        for i in range(n):
            angle = math.pi / 2 - i * 2 * math.pi / n
            rx = cx + ring * r * math.cos(angle)
            ry = cy - ring * r * math.sin(angle)
            ring_pts.append(f"{rx:.1f},{ry:.1f}")
        grid_svg += f'<polygon points="{" ".join(ring_pts)}" fill="none" stroke="#334155" stroke-width="1"/>'

    axis_svg = ""
    labels_svg = ""
    label_names = ["Launch", "Pipeline", "Embodi.", "Revenue"]
    for i in range(n):
        angle = math.pi / 2 - i * 2 * math.pi / n
        ex = cx + r * math.cos(angle)
        ey = cy - r * math.sin(angle)
        lx = cx + (r + 18) * math.cos(angle)
        ly = cy - (r + 18) * math.sin(angle)
        axis_svg += f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#475569" stroke-width="1"/>'
        labels_svg += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="11" fill="{obj_colors[i]}">{label_names[i]}</text>'

    radar_svg = f"""
    <svg width="300" height="300" style="display:block">
      {grid_svg}{axis_svg}
      <polygon points="{radar_poly}" fill="#38bdf8" opacity="0.25" stroke="#38bdf8" stroke-width="2"/>
      {labels_svg}
      <text x="{cx}" y="{cy+140}" text-anchor="middle" font-size="12" fill="#64748b">OKR Radar — Q2 2026</text>
    </svg>"""

    return f"""<!DOCTYPE html><html><head><title>Q2 OKR Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 24px 0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:12px;border-radius:8px;border:1px solid #334155}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px}}
.stat{{background:#1e293b;padding:16px;border-radius:8px;border:1px solid #334155;text-align:center}}
.stat-val{{font-size:2rem;font-weight:bold;color:#38bdf8}}
.stat-lbl{{font-size:0.75rem;color:#64748b;margin-top:4px}}
.subtitle{{color:#64748b;padding:4px 24px 16px;font-size:0.85rem}}
</style></head>
<body>
<h1>Q2 OKR Tracker</h1>
<div class="subtitle">OCI Robot Cloud — Q2 2026 Objectives &amp; Key Results</div>

<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;margin:12px">
  <div class="stat"><div class="stat-val" style="color:{bar_color(overall)}">{overall}%</div><div class="stat-lbl">Overall Progress</div></div>
  <div class="stat"><div class="stat-val">{len(okrs)}</div><div class="stat-lbl">Objectives</div></div>
  <div class="stat"><div class="stat-val">{sum(len(o['krs']) for o in okrs)}</div><div class="stat-lbl">Key Results</div></div>
  <div class="stat"><div class="stat-val" style="color:#34d399">{sum(1 for p in all_pcts if p >= 100)}</div><div class="stat-lbl">KRs Complete</div></div>
</div>

<div class="card">
  <h2>Weekly Progress Trend (Q2 Weeks 1-13)</h2>
  {sparkline_svg}
</div>

<div class="grid2">
  <div class="card" style="display:flex;flex-direction:column;align-items:center">
    <h2 style="align-self:flex-start">Objective Radar</h2>
    {radar_svg}
  </div>
  <div style="display:flex;flex-direction:column;gap:0">
    {cards_html}
  </div>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Q2 OKR Tracker")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "q2_okr_tracker"}

    @app.get("/okrs")
    def get_okrs():
        return [
            {"objective": "Launch OCI Robot Cloud GA", "owner": "Jun Qian", "progress": 88},
            {"objective": "Fine-tuning Pipeline at Scale", "owner": "ML Infra", "progress": 98},
            {"objective": "Expand Embodiment Support", "owner": "Platform Eng", "progress": 89},
            {"objective": "Revenue & Pipeline Growth", "owner": "GTM", "progress": 65},
        ]

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

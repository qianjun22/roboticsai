"""Partner Success Scorecard — FastAPI port 8749"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8749

PARTNERS = [
    "Agility Robotics", "Boston Dynamics", "Apptronik",
    "Sanctuary AI", "1X Technologies", "Fourier Intelligence",
    "Unitree", "Figure AI"
]

METRICS = ["Deployment Health", "API Adoption", "Training Usage", "Support Score", "Revenue Growth"]

def gen_partner_data():
    random.seed(77)
    partners = []
    for i, name in enumerate(PARTNERS):
        scores = {m: round(50 + random.random() * 48, 1) for m in METRICS}
        overall = round(sum(scores.values()) / len(scores), 1)
        mrr = round(1200 + random.random() * 8800, 0)
        tier = "Gold" if overall >= 85 else ("Silver" if overall >= 70 else "Bronze")
        partners.append({"name": name, "scores": scores, "overall": overall, "mrr": mrr, "tier": tier})
    partners.sort(key=lambda p: -p["overall"])
    return partners

def tier_color(tier):
    return {"Gold": "#fbbf24", "Silver": "#94a3b8", "Bronze": "#c2783c"}.get(tier, "#64748b")

def gen_leaderboard_svg(partners):
    """Horizontal stacked-ish bar per partner showing overall score."""
    W, H = 520, 220
    max_score = 100
    bar_h = 18
    gap = 8
    bars = []
    for i, p in enumerate(partners):
        y = 10 + i * (bar_h + gap)
        bar_w = (p["overall"] / max_score) * (W - 170)
        color = tier_color(p["tier"])
        short = p["name"].split()[0]
        bars.append(
            f'<rect x="120" y="{y}" width="{bar_w:.1f}" height="{bar_h}" rx="3" fill="{color}" opacity="0.85"/>'
            f'<text x="115" y="{y+13}" fill="#cbd5e1" font-size="10" text-anchor="end">{short}</text>'
            f'<text x="{120+bar_w+5:.1f}" y="{y+13}" fill="#94a3b8" font-size="10">{p["overall"]}</text>'
        )
    return (
        f'<svg width="{W}" height="{H}" style="background:#0f172a;border-radius:6px">'
        + ''.join(bars)
        + f'<text x="10" y="{H-4}" fill="#94a3b8" font-size="11">Partner Overall Score (sorted)</text>'
        + '</svg>'
    )

def gen_radar_svg(partner):
    """Radar chart for a single partner across all metrics."""
    CX, CY, R = 200, 160, 110
    n = len(METRICS)
    rings = [25, 50, 75, 100]
    parts = []
    for rv in rings:
        rr = R * rv / 100
        pts = []
        for i in range(n):
            angle = 2 * math.pi * i / n - math.pi / 2
            pts.append(f"{CX + rr * math.cos(angle):.1f},{CY + rr * math.sin(angle):.1f}")
        parts.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="#334155" stroke-width="1"/>')
    data_pts = []
    for i, m in enumerate(METRICS):
        angle = 2 * math.pi * i / n - math.pi / 2
        dr = R * partner["scores"][m] / 100
        data_pts.append(f"{CX + dr * math.cos(angle):.1f},{CY + dr * math.sin(angle):.1f}")
        label_r = R + 20
        lx = CX + label_r * math.cos(angle)
        ly = CY + label_r * math.sin(angle)
        short = m.split()[0]
        parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{short}</text>')
    color = tier_color(partner["tier"])
    parts.append(f'<polygon points="{" ".join(data_pts)}" fill="{color}33" stroke="{color}" stroke-width="2"/>')
    for pt in data_pts:
        x, y = pt.split(",")
        parts.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')
    return (
        f'<svg width="400" height="310" style="background:#0f172a;border-radius:6px">'
        + ''.join(parts)
        + f'<text x="10" y="300" fill="#94a3b8" font-size="11">Metric Breakdown: {partner["name"]}</text>'
        + '</svg>'
    )

def gen_mrr_trend_svg(partners):
    """Line chart: MRR over simulated 12 months for top 3 partners."""
    W, H = 520, 180
    months = 12
    colors = ["#38bdf8", "#f472b6", "#4ade80"]
    lines = []
    for j, p in enumerate(partners[:3]):
        pts = []
        base = p["mrr"]
        random.seed(j * 13 + 5)
        val = base * 0.6
        for i in range(months):
            val = val * (1 + 0.04 + random.random() * 0.04 - 0.01)
            x = 30 + i * (W - 60) / (months - 1)
            y = H - 20 - (val / (base * 1.2)) * (H - 40)
            pts.append(f"{x:.1f},{y:.1f}")
        lines.append(
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{colors[j]}" stroke-width="2.2"/>'
            f'<text x="{float(pts[-1].split(",")[0])+4:.1f}" y="{float(pts[-1].split(",")[1]):.1f}" '
            f'fill="{colors[j]}" font-size="9">{p["name"].split()[0]}</text>'
        )
    return (
        f'<svg width="{W}" height="{H}" style="background:#0f172a;border-radius:6px">'
        + ''.join(lines)
        + f'<text x="10" y="{H-2}" fill="#94a3b8" font-size="11">MRR Trend (12mo, top 3 partners)</text>'
        + '</svg>'
    )

def build_html():
    partners = gen_partner_data()
    top = partners[0]
    leaderboard_svg = gen_leaderboard_svg(partners)
    radar_svg = gen_radar_svg(top)
    mrr_svg = gen_mrr_trend_svg(partners)
    total_mrr = sum(p["mrr"] for p in partners)
    gold_count = sum(1 for p in partners if p["tier"] == "Gold")
    rows = "".join(
        f'<tr><td>{p["name"]}</td>'
        f'<td style="color:{tier_color(p[\"tier\"])}">{p["tier"]}</td>'
        f'<td>{p["overall"]}</td>'
        f'<td>${p["mrr"]:,.0f}</td>'
        + "".join(f'<td>{p["scores"][m]}</td>' for m in METRICS)
        + '</tr>'
        for p in partners
    )
    metric_headers = "".join(f'<th>{m.split()[0]}</th>' for m in METRICS)
    return f"""<!DOCTYPE html><html><head><title>Partner Success Scorecard</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin-top:0}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
.stat{{background:#0f172a;padding:12px 18px;border-radius:6px;text-align:center}}
.stat .val{{font-size:1.9em;font-weight:700;color:#38bdf8}}
.stat .lbl{{font-size:0.78em;color:#64748b}}
table{{width:100%;border-collapse:collapse;font-size:0.85em}}
th{{background:#0f172a;padding:8px;text-align:left;color:#94a3b8}}
td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
tr:hover td{{background:#172033}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
</style></head>
<body>
<h1>Partner Success Scorecard</h1>
<p style="color:#64748b;margin-top:0">Port {PORT} — OCI Robot Cloud partner health &amp; revenue analytics</p>
<div class="grid">
  <div class="card"><div class="stat"><div class="val">{len(partners)}</div><div class="lbl">Active Partners</div></div></div>
  <div class="card"><div class="stat"><div class="val">{gold_count}</div><div class="lbl">Gold Tier</div></div></div>
  <div class="card"><div class="stat"><div class="val">${total_mrr:,.0f}</div><div class="lbl">Total MRR</div></div></div>
  <div class="card"><div class="stat"><div class="val">{top["overall"]}</div><div class="lbl">Top Score ({top["name"].split()[0]})</div></div></div>
</div>
<div class="card"><h2>Partner Leaderboard</h2>{leaderboard_svg}</div>
<div class="two-col">
  <div class="card"><h2>Top Partner Radar — {top["name"]}</h2>{radar_svg}</div>
  <div class="card"><h2>MRR Trend</h2>{mrr_svg}</div>
</div>
<div class="card"><h2>Full Scorecard</h2>
<table><tr><th>Partner</th><th>Tier</th><th>Overall</th><th>MRR</th>{metric_headers}</tr>
{rows}</table></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Success Scorecard")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/partners")
    def list_partners():
        return {"partners": gen_partner_data()}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a):
        pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

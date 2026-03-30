"""Partner Metrics v2 — FastAPI port 8354"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8354

PARTNERS = ["PI Robotics", "Apptronik", "Covariant", "1X Tech", "Skild"]
KPIS = ["SR", "Latency(ms)", "Cost/run($)", "Demos", "API calls/d", "CSAT", "Retention", "Expansion"]

DATA = {
    "PI Robotics":  [0.82, 226, 0.43, 312, 847, 4.7, 0.94, "EXPAND"],
    "Apptronik":    [0.68, 231, 0.44, 187, 623, 4.2, 0.89, "STABLE"],
    "Covariant":    [0.74, 228, 0.43, 241, 712, 4.4, 0.91, "STABLE"],
    "1X Tech":      [0.61, 239, 0.46, 94,  382, 3.8, 0.73, "WATCH"],
    "Skild":        [0.69, 234, 0.45, 143, 481, 4.1, 0.86, "STABLE"],
}

TREND = {
    "PI Robotics": "+3pp", "Apptronik": "+4pp", "Covariant": "+2pp",
    "1X Tech": "-2pp", "Skild": "+1pp"
}

def build_html():
    rows = ""
    for p, vals in DATA.items():
        status = vals[7]
        color = {"EXPAND": "#22c55e", "STABLE": "#38bdf8", "WATCH": "#f59e0b", "CHURN": "#C74634"}[status]
        trend_color = "#22c55e" if TREND[p].startswith("+") else "#C74634"
        rows += f"""<tr>
<td style="padding:8px;color:#e2e8f0">{p}</td>
<td style="padding:8px;color:#22c55e;font-weight:bold">{vals[0]}</td>
<td style="padding:8px;color:#38bdf8">{vals[1]}</td>
<td style="padding:8px;color:#94a3b8">${vals[2]}</td>
<td style="padding:8px;color:#94a3b8">{vals[3]}</td>
<td style="padding:8px;color:#94a3b8">{vals[4]}</td>
<td style="padding:8px;color:#94a3b8">{vals[5]}/5</td>
<td style="padding:8px;color:{trend_color}">{TREND[p]} SR</td>
<td style="padding:8px"><span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:0.8em">{status}</span></td>
</tr>"""

    # Sparkline data for 30-day SR trend per partner
    def sparkline(base, trend_dir, seed):
        random.seed(seed)
        pts = []
        v = base - 0.06 if trend_dir > 0 else base + 0.06
        for i in range(30):
            v = max(0.4, min(0.9, v + trend_dir*0.003 + random.uniform(-0.01,0.01)))
            pts.append(v)
        return pts

    sparklines = {
        "PI Robotics": sparkline(0.82, 1, 1),
        "Apptronik": sparkline(0.68, 1, 2),
        "Covariant": sparkline(0.74, 1, 3),
        "1X Tech": sparkline(0.61, -1, 4),
        "Skild": sparkline(0.69, 0.5, 5),
    }

    spark_svgs = ""
    for idx, (p, pts) in enumerate(sparklines.items()):
        color = "#C74634" if p == "1X Tech" else "#22c55e"
        coords = " ".join(f"{10+i*8},{50-pts[i]*50}" for i in range(30))
        spark_svgs += f"""<div style="background:#0f172a;border-radius:6px;padding:10px">
<div style="color:#94a3b8;font-size:0.8em;margin-bottom:4px">{p}</div>
<svg viewBox="0 50 250 55" style="width:100%;height:40px">
<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="1.5"/>
<line x1="10" y1="{50-sparklines[p][-1]*50}" x2="242" y2="{50-sparklines[p][-1]*50}" stroke="{color}" stroke-dasharray="2,2" stroke-width="0.5"/>
</svg>
<div style="color:{color};font-size:0.85em;font-weight:bold">{TREND[p]} <span style="color:#64748b">/ 30d</span></div>
</div>"""

    return f"""<!DOCTYPE html><html><head><title>Partner Metrics v2 — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.card{{background:#1e293b;border-radius:8px;padding:16px;margin-top:16px}}
table{{width:100%;border-collapse:collapse}}
th{{padding:8px;text-align:left;color:#64748b;font-size:0.8em;border-bottom:1px solid #334155}}
tr:hover td{{background:#1e293b}}</style></head><body>
<h1>Partner Metrics v2</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center">
<div style="font-size:2em;font-weight:bold;color:#22c55e">5</div>
<div style="font-size:0.75em;color:#94a3b8">Active Partners</div></div>
<div style="text-align:center">
<div style="font-size:2em;font-weight:bold;color:#22c55e">0.71</div>
<div style="font-size:0.75em;color:#94a3b8">Platform Avg SR</div></div>
<div style="text-align:center">
<div style="font-size:2em;font-weight:bold;color:#38bdf8">127%</div>
<div style="font-size:0.75em;color:#94a3b8">NRR</div></div>
<div style="text-align:center">
<div style="font-size:2em;font-weight:bold;color:#f59e0b">1</div>
<div style="font-size:0.75em;color:#94a3b8">WATCH</div></div>
</div>
<div class="card">
<h2>Partner KPI Scorecard</h2>
<table><thead><tr>
<th>Partner</th><th>SR</th><th>Latency</th><th>Cost/run</th><th>Demos</th><th>API/d</th><th>CSAT</th><th>SR Trend</th><th>Status</th>
</tr></thead><tbody>{rows}</tbody></table>
</div>
<div class="card">
<h2>30-Day SR Trend by Partner</h2>
<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px">
{spark_svgs}
</div>
</div>
<div class="card" style="font-size:0.8em;color:#64748b">
1X Tech: SR declining -2pp / flat API usage — churn risk signal. PI: leading 4/8 KPIs, expansion ready.
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Metrics v2")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT, "partners": 5, "avg_sr": 0.71}

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

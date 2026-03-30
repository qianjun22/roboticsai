"""Deployment Metrics v2 — FastAPI port 8510"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8510

def build_html():
    dora_metrics = [
        ("Lead Time", 4.2, "hrs", "elite (<1d)", "↓ improving", "#22c55e"),
        ("Deploy Freq", 4.0, "/wk", "high (1/wk+)", "↑ improving", "#22c55e"),
        ("MTTR", 8.0, "min", "elite (<1hr)", "↓ improving", "#22c55e"),
        ("Change Fail %", 4.7, "%", "medium (<15%)", "→ stable", "#38bdf8"),
    ]
    
    dora_cards = ""
    for name, val, unit, tier, trend, col in dora_metrics:
        dora_cards += f'''<div class="card">
<h3>{name}</h3>
<div class="stat">{val}{unit}</div>
<div class="sub">{tier}</div>
<div style="color:{col};font-size:12px;margin-top:6px">{trend}</div>
</div>'''
    
    # 8-week rolling trend per metric
    weeks = list(range(8))
    metrics_trend = [
        ("Lead Time (hrs)", [18, 14, 10, 8, 6.2, 5.1, 4.4, 4.2], "#22c55e"),
        ("Deploy/wk", [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0], "#38bdf8"),
        ("MTTR (hrs→min/60)", [2.3, 1.8, 1.2, 0.5, 0.3, 0.2, 0.15, 0.13], "#f59e0b"),
        ("ChangeFailPct", [12, 9, 8, 7, 6, 5, 5, 4.7], "#a78bfa"),
    ]
    
    trend_svgs = ""
    for name, vals, col in metrics_trend:
        mn, mx = min(vals), max(vals)
        pts = []
        for i, v in enumerate(vals):
            x = i * 500 / 7
            y = 80 - (v - mn) / (mx - mn + 0.01) * 80
            pts.append(f"{x:.1f},{y:.1f}")
        trend_svgs += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="2"/>'
    
    legend = "".join([f'<span style="color:{c}">— {n.split("(")[0].strip()}</span><span style="margin-right:10px"> </span>' for n,_,c in metrics_trend])
    
    # maturity score
    maturity_score = 8.2
    maturity_dims = [
        ("CI/CD automation", 9.1, "#22c55e"),
        ("Test coverage", 8.4, "#22c55e"),
        ("Deployment speed", 8.8, "#22c55e"),
        ("Observability", 7.9, "#38bdf8"),
        ("Rollback speed", 8.6, "#22c55e"),
        ("Change safety", 6.8, "#f59e0b"),
    ]
    
    maturity_bars = ""
    for dim, score, col in maturity_dims:
        maturity_bars += f'''<div style="display:flex;align-items:center;margin-bottom:6px">
<span style="width:160px;color:#e2e8f0;font-size:12px">{dim}</span>
<div style="background:#334155;border-radius:2px;height:8px;width:150px">
<div style="background:{col};width:{score*10:.0f}%;height:8px;border-radius:2px"></div></div>
<span style="margin-left:8px;color:{col};font-size:12px">{score:.1f}/10</span>
</div>'''
    
    return f"""<!DOCTYPE html><html><head><title>Deployment Metrics v2</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:32px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:11px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Deployment Metrics v2</h1><span>port {PORT} · DORA metrics</span></div>
<div class="grid">{dora_cards}
<div class="card" style="grid-column:span 4"><h3>8-Week Rolling Trend</h3>
<div style="font-size:11px;margin-bottom:8px">{legend}</div>
<svg width="100%" viewBox="0 0 500 80">{trend_svgs}</svg></div>
<div class="card" style="grid-column:span 2"><h3>CI/CD Maturity Score: {maturity_score}/10</h3>
<div style="font-size:11px;color:#22c55e;margin-bottom:8px">Elite performer across 5/6 dimensions</div>
{maturity_bars}</div>
<div class="card" style="grid-column:span 2"><h3>Recent Deploys (Mar 2026)</h3>
<div style="font-size:13px;line-height:1.9;color:#94a3b8">
<div><span style="color:#22c55e">✓</span> Mar-28: dagger_run10 step 1420 checkpoint (auto)</div>
<div><span style="color:#22c55e">✓</span> Mar-25: groot_finetune_v2 staging → PROD canary (5%)</div>
<div><span style="color:#22c55e">✓</span> Mar-22: api_gateway v2.1.3 patch (p99 fix)</div>
<div><span style="color:#22c55e">✓</span> Mar-20: eval harness v1.8 + new LIBERO tasks</div>
</div></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Deployment Metrics v2")
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

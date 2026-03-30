"""Revenue Attribution — FastAPI port 8501"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8501

def build_html():
    channels = [
        ("NVIDIA referral", 1680, "#22c55e", 2.8),
        ("OCI blog/docs", 524, "#38bdf8", 1.2),
        ("GTC talk (planned)", 0, "#64748b", 0),
        ("Direct outreach", 482, "#f59e0b", 0.9),
        ("Word of mouth", 241, "#a78bfa", 1.4),
    ]
    total_mrr = sum(c[1] for c in channels)
    
    bars = ""
    max_mrr = max(c[1] for c in channels if c[1] > 0)
    for name, mrr, col, ltv_mult in channels:
        w = mrr / max_mrr * 100 if mrr > 0 else 0
        ltv_str = f"{ltv_mult:.1f}×" if ltv_mult > 0 else "—"
        bars += f'''<div style="margin-bottom:10px">
<div style="display:flex;justify-content:space-between;margin-bottom:3px">
<span style="color:{col}">{name}</span>
<span style="color:#94a3b8;font-size:12px">${mrr:,}/mo MRR · LTV {ltv_mult:.1f}×</span>
</div>
<div style="background:#334155;border-radius:3px;height:10px">
<div style="background:{col};width:{w:.0f}%;height:10px;border-radius:3px"></div>
</div></div>'''
    
    # CAC by channel scatter
    cac_data = [
        ("NVIDIA referral", 840, 5880, "#22c55e"),
        ("OCI blog", 120, 1248, "#38bdf8"),
        ("Direct", 680, 1404, "#f59e0b"),
        ("Word of mouth", 0, 840, "#a78bfa"),
    ]
    cac_svg = ""
    for name, cac, ltv, col in cac_data:
        x = cac / 1000 * 300 + 20
        y = 120 - ltv / 6000 * 100
        cac_svg += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="8" fill="{col}" opacity="0.8"/>'
        cac_svg += f'<text x="{x+10:.0f}" y="{y+4:.0f}" fill="{col}" font-size="9">{name}</text>'
    cac_svg += f'<line x1="20" y1="120" x2="320" y2="20" stroke="#334155" stroke-width="1" stroke-dasharray="4,2"/>'
    cac_svg += f'<text x="160" y="130" text-anchor="middle" fill="#64748b" font-size="9">CAC ($0–$1k)</text>'
    cac_svg += f'<text x="5" y="70" fill="#64748b" font-size="9" transform="rotate(-90,5,70)">LTV</text>'
    
    # forecast bar
    forecast_months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    nvidia_share = [0, 0, 1260, 1680, 2100, 4200]
    other_share = [2927, 3200, 3500, 3800, 4200, 4800]
    
    forecast_svg = ""
    max_val = max(n+o for n,o in zip(nvidia_share, other_share))
    for i, (ns, os) in enumerate(zip(nvidia_share, other_share)):
        x = i * 80 + 20
        total = ns + os
        other_h = os / max_val * 100
        nvidia_h = ns / max_val * 100
        forecast_svg += f'<rect x="{x}" y="{100-other_h:.0f}" width="50" height="{other_h:.0f}" fill="#38bdf8" opacity="0.8"/>'
        forecast_svg += f'<rect x="{x}" y="{100-other_h-nvidia_h:.0f}" width="50" height="{nvidia_h:.0f}" fill="#22c55e" opacity="0.8"/>'
        forecast_svg += f'<text x="{x+25}" y="112" text-anchor="middle" fill="#64748b" font-size="9">{forecast_months[i]}</text>'
    
    return f"""<!DOCTYPE html><html><head><title>Revenue Attribution</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Revenue Attribution</h1><span>port {PORT} · channel performance</span></div>
<div class="grid">
<div class="card"><h3>Total MRR</h3><div class="stat">${total_mrr:,}</div><div class="sub">Mar 2026 baseline</div></div>
<div class="card"><h3>NVIDIA LTV Mult</h3><div class="stat">2.8×</div><div class="sub">vs direct outreach 0.9×</div></div>
<div class="card"><h3>MRR by Channel</h3>{bars}</div>
<div class="card"><h3>CAC vs LTV by Channel</h3>
<svg width="100%" viewBox="0 0 330 135">{cac_svg}</svg></div>
<div class="card" style="grid-column:span 2"><h3>MRR Forecast (NVIDIA-driven vs Other)</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:8px"><span style="color:#22c55e">■</span> NVIDIA-referred <span style="color:#38bdf8;margin-left:8px">■</span> Other channels</div>
<svg width="100%" viewBox="0 0 500 120">{forecast_svg}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Revenue Attribution")
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

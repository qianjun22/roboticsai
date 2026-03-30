"""AI World ROI Calculator — FastAPI port 8372"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8372

def build_html():
    # Waterfall stages
    waterfall = [
        ("Event cost", -8000, "#C74634"),
        ("Demo leads (12)", 0, "#64748b"),
        ("Pipeline value", 36000, "#f59e0b"),
        ("Pilot conversions (3)", 0, "#64748b"),
        ("ARR yr1", 47000, "#22c55e"),
        ("Net ROI", 39000, "#22c55e"),
    ]
    
    # Build waterfall SVG
    wf_bars = ""
    cumulative = 0
    for i, (label, val, color) in enumerate(waterfall):
        if val == 0: continue
        x = 40 + i * 90
        if val > 0:
            y_start = 160 - cumulative/350
            bar_h = val/350
            wf_bars += f'<rect x="{x}" y="{y_start - bar_h}" width="70" height="{bar_h}" fill="{color}" opacity="0.8" rx="2"/>'
            wf_bars += f'<text x="{x+35}" y="{y_start - bar_h - 5}" text-anchor="middle" fill="{color}" font-size="8">${val//1000}k</text>'
            cumulative += val
        else:
            bar_h = abs(val)/350
            y_start = 160 - cumulative/350
            wf_bars += f'<rect x="{x}" y="{y_start}" width="70" height="{bar_h}" fill="{color}" opacity="0.8" rx="2"/>'
            wf_bars += f'<text x="{x+35}" y="{y_start + bar_h + 10}" text-anchor="middle" fill="{color}" font-size="8">-${abs(val)//1000}k</text>'
            cumulative += val
        wf_bars += f'<text x="{x+35}" y="185" text-anchor="middle" fill="#64748b" font-size="7" transform="rotate(-30,{x+35},185)">{label[:12]}</text>'

    # 3-scenario projection (monthly revenue)
    months = list(range(0, 13))
    conservative = [round(max(0, -8000 + 3900*m), 0) for m in months]
    base = [round(max(0, -8000 + 4700*m), 0) for m in months]
    optimistic = [round(max(0, -8000 + 7200*m), 0) for m in months]
    
    scale = 0.002
    pts_c = " ".join(f"{30+m*38},{200-min(conservative[i],60000)*scale}" for i,m in enumerate(months))
    pts_b = " ".join(f"{30+m*38},{200-min(base[i],60000)*scale}" for i,m in enumerate(months))
    pts_o = " ".join(f"{30+m*38},{200-min(optimistic[i],60000)*scale}" for i,m in enumerate(months))

    # Break-even line
    be_month_base = 8000/4700
    be_x = 30 + be_month_base*38

    return f"""<!DOCTYPE html><html><head><title>AI World ROI Calculator — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>AI World ROI Calculator</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">5.9×</div><div style="font-size:0.75em;color:#94a3b8">ROI (base case)</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">$47k</div><div style="font-size:0.75em;color:#94a3b8">Yr1 ARR</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">4 mo</div><div style="font-size:0.75em;color:#94a3b8">Break-even</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">$8k</div><div style="font-size:0.75em;color:#94a3b8">Investment</div></div>
</div>
<div class="grid">
<div class="card"><h2>Investment → Revenue Waterfall</h2>
<svg viewBox="0 0 580 200"><rect width="580" height="200" fill="#0f172a" rx="4"/>
<line x1="30" y1="160" x2="560" y2="160" stroke="#334155" stroke-width="1"/>
{wf_bars}
</svg></div>
<div class="card"><h2>3-Scenario Projection (12 months)</h2>
<svg viewBox="0 0 510 220"><rect width="510" height="220" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="200" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="200" x2="500" y2="200" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="200" x2="500" y2="200" stroke="#334155" stroke-width="1"/>
<!-- break-even line -->
<line x1="{be_x}" y1="10" x2="{be_x}" y2="200" stroke="#22c55e" stroke-dasharray="3,3" stroke-width="1" opacity="0.5"/>
<text x="{be_x+3}" y="18" fill="#22c55e" font-size="8">break-even</text>
<polyline points="{pts_c}" fill="none" stroke="#64748b" stroke-width="1.5"/>
<polyline points="{pts_b}" fill="none" stroke="#22c55e" stroke-width="2"/>
<polyline points="{pts_o}" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
<text x="430" y="50" fill="#38bdf8" font-size="8">optimistic</text>
<text x="430" y="80" fill="#22c55e" font-size="8">base</text>
<text x="430" y="120" fill="#64748b" font-size="8">conservative</text>
<text x="240" y="215" fill="#64748b" font-size="9">Month post-AI World</text>
</svg></div>
</div>
<div class="card" style="margin-top:16px;font-size:0.8em;color:#64748b">
Assumptions: 12 qualified leads → 3 pilots (25% conversion) → $1,247/mo avg ARR. Base case 5.9× ROI in yr1. Break-even month 4 (Oct 2026).
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="AI World ROI Calculator")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"roi_multiple":5.9,"breakeven_months":4,"yr1_arr":47000}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type","text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self,*a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0",PORT), Handler).serve_forever()

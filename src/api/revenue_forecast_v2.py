"""Revenue Forecast v2 — FastAPI port 8418"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8418

def build_html():
    # S-curve ARR model: months 0-23 (Jan 2026 - Dec 2027)
    months = list(range(24))
    month_labels = ["J26","F","M","A","M","J","J","A","S","O","N","D",
                    "J27","F","M","A","M","J","J","A","S","O","N","D"]

    def s_curve(t, inflection, scale, base=0):
        return base + scale / (1 + math.exp(-0.4*(t - inflection)))

    base_case = [s_curve(m, 8, 19000) + random.uniform(-200,200) for m in months]
    cons_case = [s_curve(m, 10, 12000) + random.uniform(-150,150) for m in months]
    opt_case  = [s_curve(m, 7, 35000) + random.uniform(-300,300) for m in months]

    max_arr = 37000
    svg_s = '<svg width="420" height="220" style="background:#0f172a">'
    svg_s += '<line x1="50" y1="10" x2="50" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_s += '<line x1="50" y1="170" x2="400" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(5):
        yv = i*9000; y = 170-yv/max_arr*150
        svg_s += f'<text x="45" y="{y+4}" fill="#94a3b8" font-size="7" text-anchor="end">${yv//1000}k</text>'
        svg_s += f'<line x1="50" y1="{y}" x2="400" y2="{y}" stroke="#1e293b" stroke-width="1"/>'
    for mi, label in enumerate(month_labels):
        x = 50+mi*15
        if mi % 3 == 0:
            svg_s += f'<text x="{x}" y="183" fill="#94a3b8" font-size="7" text-anchor="middle">{label}</text>'
    # Vertical marker for AI World Sep 2026 (month 8)
    ai_world_x = 50+8*15
    svg_s += f'<line x1="{ai_world_x}" y1="10" x2="{ai_world_x}" y2="170" stroke="#C74634" stroke-width="1" stroke-dasharray="4,3"/>'
    svg_s += f'<text x="{ai_world_x+3}" y="22" fill="#C74634" font-size="7">AI World</text>'
    # Plot scenarios
    for arr_data, col, dash in [(opt_case,"#22c55e",""),
                                 (base_case,"#38bdf8",""),
                                 (cons_case,"#94a3b8","4,3")]:
        pts = [(50+mi*15, 170-v/max_arr*150) for mi, v in enumerate(arr_data)]
        for j in range(len(pts)-1):
            x1,y1=pts[j]; x2,y2=pts[j+1]
            ds = f' stroke-dasharray="{dash}"' if dash else ''
            svg_s += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="1.5"{ds}/>'
    svg_s += '<rect x="250" y="12" width="8" height="6" fill="#22c55e"/><text x="262" y="18" fill="#22c55e" font-size="7">optimistic</text>'
    svg_s += '<rect x="250" y="24" width="8" height="6" fill="#38bdf8"/><text x="262" y="30" fill="#38bdf8" font-size="7">base case</text>'
    svg_s += '<rect x="250" y="36" width="8" height="6" fill="#94a3b8"/><text x="262" y="42" fill="#94a3b8" font-size="7">conservative</text>'
    svg_s += '</svg>'

    # Cohort expansion waterfall
    cohorts = [
        ("PI_pilot\u2192growth","$1,247","$2,100","#22c55e"),
        ("Apt_pilot\u2192growth","$847","$1,500","#38bdf8"),
        ("1X_pilot\u2192std","$847","$1,200","#f59e0b"),
        ("Machina_new","$0","$1,247","#C74634"),
        ("AI_World_cohort","$0","$8,400","#a78bfa"),
    ]
    svg_w2 = '<svg width="380" height="200" style="background:#0f172a">'
    svg_w2 += '<text x="190" y="18" fill="#94a3b8" font-size="9" text-anchor="middle">ARR Expansion: Current \u2192 Sep 2026</text>'
    running2 = 2927
    for ci, (label, current, target, col) in enumerate(cohorts):
        y = 30+ci*32
        cur_v = int(current.replace("$","").replace(",",""))
        tgt_v = int(target.replace("$","").replace(",",""))
        delta = tgt_v - cur_v
        # Current bar
        w_cur = int(cur_v/500*1.5) if cur_v > 0 else 0
        svg_w2 += f'<rect x="150" y="{y}" width="{min(w_cur,100)}" height="14" fill="#475569" opacity="0.7" rx="2"/>'
        # Delta bar
        w_del = int(delta/500*1.5)
        svg_w2 += f'<rect x="{150+min(w_cur,100)}" y="{y}" width="{min(w_del,180)}" height="14" fill="{col}" opacity="0.8" rx="2"/>'
        svg_w2 += f'<text x="145" y="{y+11}" fill="#94a3b8" font-size="8" text-anchor="end">{label[:15]}</text>'
        svg_w2 += f'<text x="{152+min(w_cur,100)+min(w_del,180)}" y="{y+11}" fill="{col}" font-size="8">+${delta:,}</text>'
    svg_w2 += f'<text x="190" y="195" fill="#38bdf8" font-size="9" text-anchor="middle">Sep target: $19k MRR / $228k ARR</text>'
    svg_w2 += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Revenue Forecast v2 \u2014 Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Revenue Forecast v2</h1>
<p style="color:#94a3b8">Port {PORT} | S-curve ARR model + cohort expansion waterfall</p>
<div class="grid">
<div class="card"><h2>ARR S-Curve (Jan 2026 \u2013 Dec 2027)</h2>{svg_s}</div>
<div class="card"><h2>Cohort Expansion to Sep 2026</h2>{svg_w2}
<div style="margin-top:8px">
<div class="stat">$19k</div><div class="label">Sep 2026 base MRR target (AI World inflection)</div>
<div class="stat" style="color:#22c55e;margin-top:8px">$47k</div><div class="label">Dec 2026 MRR (optimistic, 3 AI World cohorts)</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">AI World Sep cohort = biggest inflection (+$8.4k/mo new)<br>PI upgrade \u2192 Enterprise adds $853/mo<br>NRR target 127% (expansion exceeds churn)<br>Dec 2027: $47k/mo base / $84k optimistic</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Revenue Forecast v2")
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

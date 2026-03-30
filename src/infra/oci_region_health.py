"""OCI Region Health — FastAPI port 8415"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8415

def build_html():
    regions = [
        {"name":"Ashburn","role":"PRIMARY","score":94,"gpu_util":91,"latency_ms":12,"gpu_vram":"71.2/80GB","status":"HEALTHY"},
        {"name":"Phoenix","role":"SECONDARY","score":88,"gpu_util":62,"latency_ms":47,"gpu_vram":"41.8/40GB","status":"WATCH"},
        {"name":"Frankfurt","role":"DR","score":91,"gpu_util":71,"latency_ms":63,"gpu_vram":"28.4/40GB","status":"HEALTHY"},
    ]
    region_colors = {"HEALTHY":"#22c55e","WATCH":"#f59e0b","DEGRADED":"#C74634"}

    # Region status cards
    svg_r = '<svg width="420" height="190" style="background:#0f172a">'
    for ri, reg in enumerate(regions):
        x = 10+ri*140; col = region_colors[reg["status"]]
        svg_r += f'<rect x="{x}" y="10" width="130" height="168" fill="#1e293b" rx="6" stroke="{col}" stroke-width="1.5"/>'
        svg_r += f'<text x="{x+65}" y="30" fill="white" font-size="11" text-anchor="middle" font-weight="bold">{reg["name"]}</text>'
        svg_r += f'<text x="{x+65}" y="46" fill="#94a3b8" font-size="8" text-anchor="middle">{reg["role"]}</text>'
        # Score gauge
        score_angle = reg["score"]/100*math.pi
        cx2, cy2, r2 = x+65, 90, 28
        svg_r += f'<path d="M {cx2-r2} {cy2} A {r2} {r2} 0 0 1 {cx2+r2} {cy2}" fill="none" stroke="#1e293b" stroke-width="6"/>'
        ex = cx2+r2*math.cos(math.pi-score_angle); ey = cy2-r2*math.sin(score_angle)
        svg_r += f'<path d="M {cx2-r2:.1f} {cy2} A {r2} {r2} 0 0 1 {ex:.1f} {ey:.1f}" fill="none" stroke="{col}" stroke-width="6"/>'
        svg_r += f'<text x="{cx2}" y="{cy2+6}" fill="{col}" font-size="13" text-anchor="middle" font-weight="bold">{reg["score"]}</text>'
        svg_r += f'<text x="{x+65}" y="122" fill="#94a3b8" font-size="8" text-anchor="middle">GPU util: {reg["gpu_util"]}%</text>'
        svg_r += f'<text x="{x+65}" y="135" fill="#94a3b8" font-size="8" text-anchor="middle">Latency: {reg["latency_ms"]}ms</text>'
        svg_r += f'<text x="{x+65}" y="148" fill={"#f59e0b" if "40GB" in reg["gpu_vram"] and reg["gpu_util"]>60 else "#94a3b8"} font-size="7" text-anchor="middle">{reg["gpu_vram"]} VRAM</text>'
        svg_r += f'<text x="{x+65}" y="165" fill="{col}" font-size="8" text-anchor="middle">{reg["status"]}</text>'
    svg_r += '</svg>'

    # Cross-region latency heatmap (6 pairs)
    pairs = [("Ash↔Pho",47),("Ash↔Fra",63),("Pho↔Fra",98),("Ash→Pho",44),("Ash→Fra",61),("Pho→Fra",95)]
    svg_lat = '<svg width="380" height="200" style="background:#0f172a">'
    for pi, (pair, lat) in enumerate(pairs):
        y = 15+pi*28; col = "#C74634" if lat > 90 else "#f59e0b" if lat > 60 else "#22c55e"
        w = int(lat/100*260)
        svg_lat += f'<rect x="90" y="{y}" width="{w}" height="20" fill="{col}" opacity="0.8" rx="3"/>'
        svg_lat += f'<text x="85" y="{y+14}" fill="#94a3b8" font-size="9" text-anchor="end">{pair}</text>'
        svg_lat += f'<text x="{92+w}" y="{y+14}" fill="{col}" font-size="9">{lat}ms{"  ⚠ near SLA" if lat>90 else ""}</text>'
    # SLA threshold line
    sla_x = 90 + 100/100*260
    svg_lat += f'<line x1="{sla_x:.0f}" y1="10" x2="{sla_x:.0f}" y2="185" stroke="#C74634" stroke-width="1" stroke-dasharray="4,3"/>'
    svg_lat += f'<text x="{sla_x+3:.0f}" y="20" fill="#C74634" font-size="7">SLA 100ms</text>'
    svg_lat += '<text x="220" y="195" fill="#94a3b8" font-size="9" text-anchor="middle">Cross-Region Latency (ms)</text>'
    svg_lat += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>OCI Region Health — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>OCI Region Health</h1>
<p style="color:#94a3b8">Port {PORT} | Ashburn (primary) / Phoenix (secondary) / Frankfurt (DR)</p>
<div class="card" style="margin-bottom:16px"><h2>Region Status</h2>{svg_r}
<div style="color:#f59e0b;font-size:11px">⚠ Phoenix GPU VRAM: 41.8/40GB — memory overcommit, reduce batch size</div>
</div>
<div class="grid">
<div class="card"><h2>Cross-Region Latency</h2>{svg_lat}</div>
<div class="card">
<div class="stat">98ms</div><div class="label">Phoenix↔Frankfurt latency (near 100ms SLA threshold)</div>
<div class="stat" style="color:#22c55e;margin-top:12px">94/88/91</div><div class="label">Ashburn / Phoenix / Frankfurt health scores</div>
<div style="margin-top:12px;color:#94a3b8;font-size:11px">SLA breach predictor: Phoenix↔Frankfurt at 97% risk<br>Incident history: 3 incidents last 90 days<br>Planned: Frankfurt node upgrade Q3 2026<br>Automated failover: Ashburn → Phoenix in 15s</div>
</div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Region Health")
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

"""Gripper Calibration Checker — FastAPI port 8409"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8409

def build_html():
    axes = ["x_pos","y_pos","z_pos","roll","pitch","yaw"]
    errors_mm = [1.1, 0.8, 1.4, None, None, None]
    errors_deg = [None, None, None, 0.6, 0.9, 0.7]
    units = ["mm","mm","mm","°","°","°"]
    thresholds_mm = [2.0, 2.0, 2.0, None, None, None]
    thresholds_deg = [None, None, None, 1.5, 1.5, 1.5]

    svg_e = '<svg width="360" height="200" style="background:#0f172a">'
    svg_e += '<line x1="50" y1="10" x2="50" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_e += '<line x1="50" y1="170" x2="340" y2="170" stroke="#475569" stroke-width="1"/>'
    bw5 = 40; max_val = 2.5
    for i, (axis, emm, edeg, unit) in enumerate(zip(axes, errors_mm, errors_deg, units)):
        x = 55 + i*48; err = emm if emm is not None else edeg
        thresh = (thresholds_mm[i] if thresholds_mm[i] else thresholds_deg[i])
        h = err/max_val*140; y = 170-h
        col = "#22c55e" if err < thresh*0.7 else "#f59e0b" if err < thresh else "#C74634"
        svg_e += f'<rect x="{x}" y="{y:.0f}" width="{bw5}" height="{h:.0f}" fill="{col}" opacity="0.85"/>'
        svg_e += f'<text x="{x+bw5//2}" y="{y-3:.0f}" fill="{col}" font-size="9" text-anchor="middle">{err}{unit}</text>'
        svg_e += f'<text x="{x+bw5//2}" y="183" fill="#94a3b8" font-size="8" text-anchor="middle">{axis}</text>'
        # Threshold line
        ty = 170 - thresh/max_val*140
        svg_e += f'<line x1="{x}" y1="{ty:.0f}" x2="{x+bw5}" y2="{ty:.0f}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="3,2"/>'
    svg_e += '<text x="190" y="197" fill="#94a3b8" font-size="9" text-anchor="middle">6-DoF Calibration Error per Axis (dashed = threshold)</text>'
    svg_e += '</svg>'

    # Drift over time (3 robots, 60 days)
    svg_dr = '<svg width="360" height="200" style="background:#0f172a">'
    svg_dr += '<line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_dr += '<line x1="40" y1="170" x2="340" y2="170" stroke="#475569" stroke-width="1"/>'
    robots3 = ["PI_Franka","Apt_Apollo","1X_custom"]
    rcolors = ["#22c55e","#38bdf8","#f59e0b"]
    recalib_day = [None, None, 42]
    for ri, (rob, rcol, recal) in enumerate(zip(robots3, rcolors, recalib_day)):
        pts = []
        base_drift = 0.3 + ri*0.3
        for day in range(61):
            drift = base_drift + day*0.02 + random.uniform(-0.05, 0.05)
            if recal and day >= recal: drift = 0.4 + (day-recal)*0.02
            x = 40+(day/60)*290; y = 170-drift/3.0*140
            pts.append((x,y))
        for j in range(len(pts)-1):
            x1,y1=pts[j]; x2,y2=pts[j+1]
            svg_dr += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{rcol}" stroke-width="1.5"/>'
        if recal:
            rx = 40+(recal/60)*290
            svg_dr += f'<line x1="{rx:.0f}" y1="10" x2="{rx:.0f}" y2="170" stroke="white" stroke-width="1" stroke-dasharray="4,3"/>'
            svg_dr += f'<text x="{rx+3:.0f}" y="25" fill="white" font-size="8">recalibrated d{recal}</text>'
        svg_dr += f'<text x="345" y="{pts[-1][1]+4:.0f}" fill="{rcol}" font-size="8">{rob[:8]}</text>'
    # Threshold line
    ty2 = 170 - 2.0/3.0*140
    svg_dr += f'<line x1="40" y1="{ty2:.0f}" x2="340" y2="{ty2:.0f}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>'
    svg_dr += '<text x="190" y="190" fill="#94a3b8" font-size="9" text-anchor="middle">Days Since Last Calibration</text>'
    svg_dr += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Gripper Calibration Checker — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Gripper Calibration Checker</h1>
<p style="color:#94a3b8">Port {PORT} | 6-DoF error per axis + drift tracking across robot fleet</p>
<div class="grid">
<div class="card"><h2>6-DoF Calibration Error</h2>{svg_e}
<div class="stat">1.2mm / 0.7°</div><div class="label">Avg position / orientation error</div></div>
<div class="card"><h2>Calibration Drift Over Time</h2>{svg_dr}
<div style="margin-top:8px">
<div class="stat" style="color:#f59e0b">Day 42</div><div class="label">1X recalibration triggered (z_pos drift)</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">Auto-flag when drift &gt; 2mm/1.5°<br>Recommend recal every 30 days or 500 cycles<br>PI Franka most stable: 0.3mm/day drift<br>Calibration procedure: 15min robot downtime</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Gripper Calibration Checker")
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

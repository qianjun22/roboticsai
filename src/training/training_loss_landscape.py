"""Training Loss Landscape — FastAPI port 8442"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8442

def build_html():
    # 2D loss surface: lr (x) vs batch_size (y)
    lrs_log = [-5.0, -4.5, -4.0, -3.5, -3.0, -2.5, -2.0]  # log10 values
    batch_sizes = [4, 8, 16, 32, 64]
    
    # Loss surface with flat/sharp minima
    def landscape_loss(lr_log, batch):
        # Minimum around lr=3e-5, batch=16
        lr_dist = (lr_log - (-4.5))**2
        b_dist = (math.log2(batch) - math.log2(16))**2
        base = 0.15 + 0.8*lr_dist + 0.3*b_dist
        # Sharp minima at certain regions
        sharp = 0.3*math.exp(-((lr_log+3.5)**2)/0.05 - (math.log2(batch)-5)**2/0.3)
        return min(3.0, base + random.uniform(-0.02, 0.02) - sharp)

    cw14 = 44; rh14 = 28
    svg_landscape = f'<svg width="{len(lrs_log)*cw14+80}" height="{len(batch_sizes)*rh14+60}" style="background:#0f172a">'
    for li, lr in enumerate(lrs_log):
        svg_landscape += f'<text x="{80+li*cw14+22}" y="18" fill="#94a3b8" font-size="8" text-anchor="middle">1e{lr:.0f}</text>'
    for bi, bs in enumerate(batch_sizes):
        svg_landscape += f'<text x="75" y="{36+bi*rh14+16}" fill="#94a3b8" font-size="9" text-anchor="end">bs={bs}</text>'
        for li, lr in enumerate(lrs_log):
            loss = landscape_loss(lr, bs)
            g = int(200*(1-loss/3.0)); r = int(200*loss/3.0); b_col = 80
            svg_landscape += f'<rect x="{80+li*cw14}" y="{30+bi*rh14}" width="{cw14-2}" height="{rh14-2}" fill="rgb({r},{g},{b_col})" opacity="0.85"/>'
            if loss < 0.25:
                svg_landscape += f'<text x="{80+li*cw14+22}" y="{30+bi*rh14+16}" fill="white" font-size="7" text-anchor="middle">\u2605{loss:.2f}</text>'
            else:
                svg_landscape += f'<text x="{80+li*cw14+22}" y="{30+bi*rh14+16}" fill="white" font-size="7" text-anchor="middle">{loss:.2f}</text>'
    svg_landscape += '</svg>'

    # Optimization trajectory
    traj_lrs = [-4.8+i*0.1+random.gauss(0,0.02) for i in range(25)]
    traj_bs_log = [4.2-i*0.05+random.gauss(0,0.05) for i in range(25)]
    
    svg_traj2 = '<svg width="360" height="200" style="background:#0f172a">'
    svg_traj2 += '<line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_traj2 += '<line x1="40" y1="170" x2="340" y2="170" stroke="#475569" stroke-width="1"/>'
    # Flat minima region (dashed box)
    fm_x = 40+(-4.7+5)*340/3; fm_w = 0.6*340/3
    fm_y = 170-4.5*140/6; fm_h = 0.8*140/6
    svg_traj2 += f'<rect x="{fm_x:.0f}" y="{fm_y:.0f}" width="{fm_w:.0f}" height="{fm_h:.0f}" fill="#22c55e" fill-opacity="0.1" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="4,3"/>'
    svg_traj2 += f'<text x="{fm_x+fm_w//2:.0f}" y="{fm_y-4:.0f}" fill="#22c55e" font-size="7">flat minimum (good generalization)</text>'
    # Sharp minima region
    sm_x = 40+(-3.6+5)*340/3; sm_w = 0.4*340/3; sm_y = 170-5.5*140/6; sm_h = 0.5*140/6
    svg_traj2 += f'<rect x="{sm_x:.0f}" y="{sm_y:.0f}" width="{sm_w:.0f}" height="{sm_h:.0f}" fill="#C74634" fill-opacity="0.1" stroke="#C74634" stroke-width="1.5" stroke-dasharray="4,3"/>'
    svg_traj2 += f'<text x="{sm_x+sm_w//2:.0f}" y="{sm_y-4:.0f}" fill="#C74634" font-size="7">sharp min (sim2real gap)</text>'
    # Plot trajectory
    traj_pts = [(40+(lr+5)*340/3, 170-bs*140/6) for lr, bs in zip(traj_lrs, traj_bs_log)]
    for j in range(len(traj_pts)-1):
        x1,y1=traj_pts[j]; x2,y2=traj_pts[j+1]
        alpha = 0.4+j*0.02
        svg_traj2 += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#38bdf8" stroke-width="1.5" opacity="{min(1.0,alpha):.2f}"/>'
    svg_traj2 += f'<circle cx="{traj_pts[-1][0]:.0f}" cy="{traj_pts[-1][1]:.0f}" r="5" fill="#38bdf8"/>'
    svg_traj2 += '<text x="190" y="190" fill="#94a3b8" font-size="9" text-anchor="middle">Adam Trajectory (LR \u00d7 log2(batch))</text>'
    svg_traj2 += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Training Loss Landscape \u2014 Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Training Loss Landscape</h1>
<p style="color:#94a3b8">Port {PORT} | 2D loss surface (LR \u00d7 batch) + Adam optimization trajectory</p>
<div class="grid">
<div class="card"><h2>Loss Surface Contour (\u2605=flat minimum)</h2>{svg_landscape}</div>
<div class="card"><h2>Optimization Trajectory</h2>{svg_traj2}
<div style="margin-top:8px">
<div class="stat">lr=3e-5, bs=16</div><div class="label">Optimal flat minimum (\u2605 on heatmap)</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">Flat minima \u2192 better sim2real generalization<br>Sharp minima at lr=3e-4/bs=64: higher val SR but fails real<br>SAM optimizer (sharpness-aware): +0.03 SR on real robot<br>Trajectory enters flat minimum at iter ~180</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Loss Landscape")
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

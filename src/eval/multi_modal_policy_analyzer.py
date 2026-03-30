"""Multi-Modal Policy Analyzer — FastAPI port 8373"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8373

def build_html():
    # Modality ablation
    configs = [
        ("wrist_only", 0.69, 226, "#f59e0b"),
        ("overhead_only", 0.62, 224, "#C74634"),
        ("proprio_only", 0.51, 219, "#C74634"),
        ("wrist+overhead", 0.78, 228, "#22c55e"),
        ("wrist+proprio", 0.73, 227, "#f59e0b"),
        ("wrist+overhead+FT", 0.81, 231, "#22c55e"),
        ("full (all 4)", 0.82, 233, "#22c55e"),
    ]
    
    ablation_bars = ""
    for i, (name, sr, lat, color) in enumerate(configs):
        y = 20 + i * 28
        sr_w = int(sr * 220)
        ablation_bars += f'<text x="155" y="{y+13}" text-anchor="end" fill="#94a3b8" font-size="9">{name}</text>'
        ablation_bars += f'<rect x="160" y="{y}" width="{sr_w}" height="20" fill="{color}" opacity="0.8" rx="2"/>'
        ablation_bars += f'<text x="{165+sr_w}" y="{y+13}" fill="{color}" font-size="9">SR={sr} | {lat}ms</text>'

    # Attention weights per modality across phases
    phases = ["Reach", "Grasp", "Lift"]
    modalities = ["wrist_rgb", "overhead", "proprio", "force_torque"]
    attention_by_phase = [
        [0.41, 0.31, 0.19, 0.09],  # reach
        [0.38, 0.28, 0.17, 0.17],  # grasp
        [0.35, 0.24, 0.21, 0.20],  # lift
    ]
    
    attn_cells = ""
    for pi, (phase, weights) in enumerate(zip(phases, attention_by_phase)):
        for mi, (mod, w) in enumerate(zip(modalities, weights)):
            intensity = int(w * 255)
            fill = f"#{intensity:02x}{max(0,intensity-50):02x}{max(0,intensity-100):02x}"
            x = 100 + mi * 80
            y = 30 + pi * 55
            attn_cells += f'<rect x="{x}" y="{y}" width="76" height="48" fill="{fill}" opacity="0.8" rx="2"/>'
            attn_cells += f'<text x="{x+38}" y="{y+28}" text-anchor="middle" fill="#fff" font-size="11" font-weight="bold">{w:.2f}</text>'
        attn_cells += f'<text x="90" y="{55+pi*55}" text-anchor="end" fill="#94a3b8" font-size="9">{phase}</text>'
    for mi, mod in enumerate(modalities):
        attn_cells += f'<text x="{138+mi*80}" y="22" text-anchor="middle" fill="#94a3b8" font-size="8">{mod[:8]}</text>'

    return f"""<!DOCTYPE html><html><head><title>Multi-Modal Policy Analyzer — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Multi-Modal Policy Analyzer</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">0.78</div><div style="font-size:0.75em;color:#94a3b8">dual-cam SR</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">0.69</div><div style="font-size:0.75em;color:#94a3b8">wrist-only SR</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">+3pp</div><div style="font-size:0.75em;color:#94a3b8">FT for contact</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">wrist_rgb</div><div style="font-size:0.75em;color:#94a3b8">Dominant (0.41)</div></div>
</div>
<div class="grid">
<div class="card"><h2>Modality Ablation Study</h2>
<svg viewBox="0 0 580 210"><rect width="580" height="210" fill="#0f172a" rx="4"/>
{ablation_bars}
</svg></div>
<div class="card"><h2>Attention by Modality × Phase</h2>
<svg viewBox="0 0 430 210"><rect width="430" height="210" fill="#0f172a" rx="4"/>
{attn_cells}
</svg>
<div style="font-size:0.75em;color:#64748b;margin-top:4px">Force-torque attention rises from 0.09→0.20 during grasp/lift — critical for slip detection</div>
</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Multi-Modal Policy Analyzer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"dual_cam_sr":0.78,"wrist_only_sr":0.69}

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

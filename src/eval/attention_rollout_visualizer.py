"""Attention Rollout Visualizer — FastAPI port 8508"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8508

def build_html():
    layers = list(range(1, 13))
    
    # per-token saliency at final layer
    tokens = [
        ("cube_pos", 0.38, "#C74634"),
        ("wrist_patch_4", 0.29, "#22c55e"),
        ("ee_velocity", 0.18, "#38bdf8"),
        ("wrist_patch_7", 0.09, "#22c55e"),
        ("joint_5", 0.04, "#f59e0b"),
        ("overhead_patch_2", 0.02, "#64748b"),
    ]
    
    token_bars = ""
    for token, sal, col in tokens:
        token_bars += f'''<div style="display:flex;align-items:center;margin-bottom:6px">
<span style="width:140px;color:#e2e8f0;font-size:12px;font-family:monospace">{token}</span>
<div style="background:#334155;border-radius:2px;height:10px;width:200px">
<div style="background:{col};width:{sal*100:.0f}%;height:10px;border-radius:2px"></div></div>
<span style="margin-left:8px;color:{col};font-size:12px">{sal:.2f}</span>
</div>'''
    
    # attention rollout heatmap across layers
    # Token importance grows toward the action head
    heatmap = ""
    token_names = ["cube", "wrist1", "wrist2", "ee_vel", "j_ang", "overhead"]
    for layer_i in range(12):
        for tok_j, (tok_name, base_sal, col) in enumerate(tokens):
            # later layers concentrate attention on important tokens
            layer_frac = layer_i / 11
            importance = base_sal * (0.5 + 0.5 * layer_frac) + random.uniform(-0.02, 0.02)
            importance = max(0, min(1, importance))
            x = tok_j * 55 + 5
            y = layer_i * 16 + 5
            heatmap += f'<rect x="{x}" y="{y}" width="50" height="12" fill="{col}" opacity="{importance:.2f}" rx="2"/>'
        # layer label
        heatmap += f'<text x="340" y="{layer_i*16+14}" fill="#64748b" font-size="9">L{layer_i+1}</text>'
    
    # phase-based attention shift
    phases = ["reach", "pre-grasp", "contact", "grasped", "lifting"]
    wrist_attn = [0.21, 0.34, 0.42, 0.38, 0.31]
    cube_attn = [0.18, 0.28, 0.35, 0.29, 0.24]
    
    wrist_pts = []
    cube_pts = []
    for i, (w, c) in enumerate(zip(wrist_attn, cube_attn)):
        x = i * 120 + 10
        yw = 100 - w * 200
        yc = 100 - c * 200
        wrist_pts.append(f"{x:.0f},{yw:.1f}")
        cube_pts.append(f"{x:.0f},{yc:.1f}")
    
    phase_svg = f'<polyline points="{" ".join(wrist_pts)}" fill="none" stroke="#22c55e" stroke-width="2"/>'
    phase_svg += f'<polyline points="{" ".join(cube_pts)}" fill="none" stroke="#C74634" stroke-width="2" stroke-dasharray="5,3"/>'
    for i, phase in enumerate(phases):
        x = i * 120 + 10
        phase_svg += f'<text x="{x}" y="115" fill="#64748b" font-size="8" transform="rotate(-15,{x},115)">{phase}</text>'
    
    return f"""<!DOCTYPE html><html><head><title>Attention Rollout Visualizer</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Attention Rollout Visualizer</h1><span>port {PORT} · 12-layer GR00T</span></div>
<div class="grid">
<div class="card"><h3>Top Token</h3><div class="stat">cube_pos</div><div class="sub">saliency 0.38 · action head</div></div>
<div class="card"><h3>Wrist Attn Peak</h3><div class="stat">0.42</div><div class="sub">at contact phase · 3.1× baseline</div></div>
<div class="card"><h3>Per-Token Saliency (Layer 12)</h3>{token_bars}</div>
<div class="card"><h3>Cross-Layer Attention Heatmap</h3>
<div style="font-size:10px;color:#64748b;margin-bottom:4px">{" | ".join(t[:5] for t,_,_ in tokens)}</div>
<svg width="100%" viewBox="0 0 360 197">{heatmap}</svg></div>
<div class="card" style="grid-column:span 2"><h3>Task Phase Attention Shift</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:8px"><span style="color:#22c55e">—</span> wrist_rgb <span style="color:#C74634;margin-left:8px">- -</span> cube_pos</div>
<svg width="100%" viewBox="0 0 510 125">{phase_svg}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Attention Rollout Visualizer")
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

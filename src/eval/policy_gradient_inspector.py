"""Policy Gradient Inspector — FastAPI port 8393"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8393

LAYERS = [
    ("vit_enc_0", 0.41, "vit_encoder"), ("vit_enc_1", 0.38, "vit_encoder"),
    ("vit_enc_2", 0.35, "vit_encoder"), ("vit_enc_3", 0.29, "vit_encoder"),
    ("lora_A_0",  0.51, "lora_adapter"),("lora_A_1",  0.48, "lora_adapter"),
    ("lora_A_2",  0.52, "lora_adapter"),("lora_A_3",  0.47, "lora_adapter"),
    ("lora_B_0",  0.89, "lora_adapter"),("lora_B_1",  0.84, "lora_adapter"),
    ("lora_B_2",  0.81, "lora_adapter"),("lora_B_3",  0.76, "lora_adapter"),
    ("act_head_0",0.92, "action_head"), ("act_head_1",0.87, "action_head"),
    ("act_head_2",0.79, "action_head"), ("act_head_3",0.71, "action_head"),
]

VANISHING_STEPS = [147, 283, 412]
CLIP_STEPS = [23,47,68,91,112,134,158,176,195,213,234,252,271,290,311,329,
              348,367,388,407,431,456,473,492,511,535]

def layer_color(norm, group):
    if norm < 0.10: return "#C74634"  # vanishing
    if norm < 0.30: return "#f59e0b"  # low
    return "#22c55e"  # normal

def make_timeline(norms_top3, names_top3, colors):
    """Generate trajectory timeline for top-3 layers over 1420 steps."""
    steps = 1420
    random.seed(42)
    trajectories = []
    for base_norm in norms_top3:
        traj = []
        val = base_norm * 0.3
        for s in range(steps):
            noise = random.gauss(0, 0.02)
            if s < 500:
                val = val + (base_norm - val) * 0.01 + noise
            else:
                val = base_norm + noise * 0.5
            val = max(0.0, val)
            traj.append(val)
        trajectories.append(traj)
    return trajectories

def build_html():
    # Bar chart: layer-wise gradient norms
    bw, bh = 680, 380
    bar_parts = [f'<svg width="{bw}" height="{bh}" style="background:#1e293b;border-radius:8px">']
    bar_parts.append('<text x="10" y="22" fill="#e2e8f0" font-size="13" font-weight="bold">Layer-wise Gradient Norms (12 layers, 4 groups)</text>')
    group_colors = {"vit_encoder": "#38bdf8", "lora_adapter": "#a78bfa", "action_head": "#C74634"}
    prev_group = None
    for i, (name, norm, group) in enumerate(LAYERS):
        y = 34 + i * 21
        bar_w = int(norm * 380)
        col = layer_color(norm, group)
        if group != prev_group:
            bar_parts.append(f'<text x="10" y="{y+12}" fill="{group_colors[group]}" font-size="9" font-weight="bold">{group}</text>')
            prev_group = group
        bar_parts.append(f'<rect x="160" y="{y}" width="{bar_w}" height="15" fill="{col}" rx="2" opacity="0.85"/>')
        bar_parts.append(f'<text x="155" y="{y+11}" fill="#94a3b8" font-size="9" text-anchor="end">{name}</text>')
        bar_parts.append(f'<text x="{160+bar_w+4}" y="{y+11}" fill="#e2e8f0" font-size="9">{norm:.2f}</text>')
    bar_parts.append('<text x="10" y="375" fill="#64748b" font-size="9">green=normal  amber=low  red=vanishing</text>')
    bar_parts.append('</svg>')
    bar_svg = "".join(bar_parts)

    # Timeline SVG: top-3 layers (lora_B_0=0.89, act_head_0=0.92, act_head_1=0.87)
    top3 = [("act_head_0", 0.92, "#C74634"), ("lora_B_0", 0.89, "#22c55e"), ("act_head_1", 0.87, "#f59e0b")]
    steps_total = 1420
    trajs = make_timeline([t[1] for t in top3], [t[0] for t in top3], [t[2] for t in top3])
    tw, th, tpx, tpy, tpw, tph = 680, 280, 55, 30, 590, 210
    tl_parts = [f'<svg width="{tw}" height="{th}" style="background:#1e293b;border-radius:8px">']
    tl_parts.append('<text x="10" y="22" fill="#e2e8f0" font-size="13" font-weight="bold">Gradient Norm Trajectory (1420 steps, top-3 layers)</text>')
    tl_parts.append(f'<line x1="{tpx}" y1="{tpy}" x2="{tpx}" y2="{tpy+tph}" stroke="#475569" stroke-width="1"/>')
    tl_parts.append(f'<line x1="{tpx}" y1="{tpy+tph}" x2="{tpx+tpw}" y2="{tpy+tph}" stroke="#475569" stroke-width="1"/>')
    sample = 60  # sample every N steps for SVG size
    for (lname, base, col), traj in zip(top3, trajs):
        pts_list = []
        for s in range(0, steps_total, sample):
            x = tpx + s / steps_total * tpw
            y = tpy + tph - min(traj[s] / 1.1, 1.0) * tph
            pts_list.append(f"{x:.1f},{y:.1f}")
        tl_parts.append(f'<polyline points="{" ".join(pts_list)}" fill="none" stroke="{col}" stroke-width="1.5"/>')
        last_y = tpy + tph - min(base / 1.1, 1.0) * tph
        tl_parts.append(f'<text x="{tpx+tpw+4}" y="{last_y+4:.1f}" fill="{col}" font-size="9">{lname}</text>')
    # clip events (red dots)
    for cs in CLIP_STEPS:
        cx = tpx + cs / steps_total * tpw
        tl_parts.append(f'<circle cx="{cx:.1f}" cy="{tpy+tph-8}" r="2" fill="#C74634" opacity="0.7"/>')
    # stable line at step 800
    sx = tpx + 800 / steps_total * tpw
    tl_parts.append(f'<line x1="{sx:.1f}" y1="{tpy}" x2="{sx:.1f}" y2="{tpy+tph}" stroke="#22c55e" stroke-width="1" stroke-dasharray="4,3"/>')
    tl_parts.append(f'<text x="{sx+2:.1f}" y="{tpy+12}" fill="#22c55e" font-size="9">stable @800</text>')
    tl_parts.append('<text x="10" y="272" fill="#64748b" font-size="9">red dots = gradient clip events</text>')
    tl_parts.append('</svg>')
    tl_svg = "".join(tl_parts)

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Policy Gradient Inspector — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:sans-serif;margin:0;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:14px;margin:16px 0 8px}}
.stats{{display:flex;gap:16px;flex-wrap:wrap;margin:12px 0}}
.stat{{background:#1e293b;border-radius:8px;padding:12px 20px;min-width:160px}}
.stat .val{{font-size:24px;font-weight:bold;color:#C74634}}
.stat .lbl{{font-size:11px;color:#94a3b8;margin-top:2px}}</style></head><body>
<h1>Policy Gradient Inspector</h1>
<p style="color:#94a3b8;margin-top:0">Gradient flow through GR00T policy network layers — Port {PORT}</p>
<div class="stats">
  <div class="stat"><div class="val">3</div><div class="lbl">Vanishing Events (steps 147/283/412)</div></div>
  <div class="stat"><div class="val">68%</div><div class="lbl">Useful Gradient @ action_head</div></div>
  <div class="stat"><div class="val">0.89</div><div class="lbl">Peak Norm (lora_B)</div></div>
  <div class="stat"><div class="val">26</div><div class="lbl">Clip Events (clip=1.0)</div></div>
  <div class="stat"><div class="val">800</div><div class="lbl">Stable After Step</div></div>
</div>
<h2>Layer-wise Gradient Norms</h2>{bar_svg}
<h2>Gradient Norm Trajectory</h2>{tl_svg}
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Gradient Inspector")
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

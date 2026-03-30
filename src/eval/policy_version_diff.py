"""Policy Version Diff — FastAPI port 8376"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8376

def build_html():
    random.seed(41)
    layers = [
        "visual_encoder.layer1", "visual_encoder.layer2", "visual_encoder.layer3",
        "visual_encoder.layer4", "cross_attn.q_proj", "cross_attn.k_proj",
        "cross_attn.v_proj", "action_head.fc1", "action_head.fc2", "action_head.out",
        "policy_head.norm", "policy_head.fc",
    ]
    
    # Weight delta magnitudes (v2.2 → v3)
    deltas = [round(abs(random.gauss(0, 1)) * random.uniform(0.01, 0.15), 4) for _ in layers]
    deltas[7] = 0.142  # action_head.fc1 highest change
    deltas[8] = 0.118  # action_head.fc2
    deltas[4] = 0.089  # cross_attn
    
    # Heatmap: sorted by delta magnitude
    sorted_idx = sorted(range(len(layers)), key=lambda i: deltas[i], reverse=True)
    
    heatmap_bars = ""
    for rank, idx in enumerate(sorted_idx):
        layer = layers[idx]
        delta = deltas[idx]
        color_intensity = int(min(255, delta * 1800))
        bar_color = f"#{color_intensity:02x}{max(0,color_intensity-60):02x}{max(0,color_intensity-120):02x}"
        risk = "HIGH" if delta > 0.1 else "MED" if delta > 0.05 else "LOW"
        risk_color = "#C74634" if risk == "HIGH" else "#f59e0b" if risk == "MED" else "#22c55e"
        w = int(delta * 2200)
        y = 15 + rank * 24
        heatmap_bars += f'<text x="195" y="{y+14}" text-anchor="end" fill="#94a3b8" font-size="8">{layer[:22]}</text>'
        heatmap_bars += f'<rect x="200" y="{y}" width="{w}" height="18" fill="{bar_color}" opacity="0.85" rx="2"/>'
        heatmap_bars += f'<text x="{205+w}" y="{y+13}" fill="{bar_color}" font-size="8">\u0394{delta:.4f}</text>'
        heatmap_bars += f'<text x="490" y="{y+13}" fill="{risk_color}" font-size="7">{risk}</text>'

    # SR delta waterfall contributions
    contributions = [
        ("Reward shaping v3", +0.04, "#22c55e"),
        ("300 real demos", +0.06, "#22c55e"),
        ("LoRA rank 16\u219224", +0.02, "#22c55e"),
        ("DR config v4", +0.03, "#22c55e"),
        ("New tokenizer", -0.01, "#C74634"),
        ("Arch change", +0.01, "#22c55e"),
        ("Net SR delta", +0.15, "#38bdf8"),
    ]
    
    waterfall = ""
    cumul = 0.71  # starting from run9/v2.2
    for i, (label, delta, color) in enumerate(contributions[:-1]):
        x = 30 + i * 72
        y_base = 120 - cumul * 100
        bar_h = abs(delta) * 100
        if delta >= 0:
            waterfall += f'<rect x="{x}" y="{y_base - bar_h}" width="60" height="{bar_h}" fill="{color}" opacity="0.8" rx="2"/>'
            waterfall += f'<text x="{x+30}" y="{y_base-bar_h-4}" text-anchor="middle" fill="{color}" font-size="8">+{delta:.2f}</text>'
        else:
            waterfall += f'<rect x="{x}" y="{y_base}" width="60" height="{bar_h}" fill="{color}" opacity="0.8" rx="2"/>'
            waterfall += f'<text x="{x+30}" y="{y_base+bar_h+10}" text-anchor="middle" fill="{color}" font-size="8">{delta:.2f}</text>'
        waterfall += f'<text x="{x+30}" y="155" text-anchor="middle" fill="#64748b" font-size="7" transform="rotate(-30,{x+30},155)">{label[:10]}</text>'
        cumul += delta
    # Net bar
    x = 30 + 6 * 72
    waterfall += f'<rect x="{x}" y="{120-cumul*100}" width="60" height="{(cumul-0.71)*100}" fill="#38bdf8" opacity="0.7" rx="2"/>'
    waterfall += f'<text x="{x+30}" y="{115-cumul*100}" text-anchor="middle" fill="#38bdf8" font-size="9">v3={cumul:.2f}</text>'

    return f"""<!DOCTYPE html><html><head><title>Policy Version Diff \u2014 Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.card{{background:#1e293b;border-radius:8px;padding:16px;margin-top:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Policy Version Diff (v2.2 \u2192 v3)</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">+0.15</div><div style="font-size:0.75em;color:#94a3b8">SR Delta</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">2</div><div style="font-size:0.75em;color:#94a3b8">HIGH risk layers</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">action_head</div><div style="font-size:0.75em;color:#94a3b8">Most changed</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">0.86</div><div style="font-size:0.75em;color:#94a3b8">v3 target SR</div></div>
</div>
<div class="card">
<h2>Layer-wise Weight Delta (v2.2 \u2192 v3)</h2>
<svg viewBox="0 0 560 310"><rect width="560" height="310" fill="#0f172a" rx="4"/>
{heatmap_bars}
<text x="510" y="14" fill="#64748b" font-size="8">risk</text>
</svg></div>
<div class="card">
<h2>SR Contribution Waterfall</h2>
<svg viewBox="0 0 560 175"><rect width="560" height="175" fill="#0f172a" rx="4"/>
<line x1="20" y1="120" x2="540" y2="120" stroke="#334155" stroke-width="1"/>
<text x="20" y="133" fill="#64748b" font-size="8">SR=0.71</text>
{waterfall}
</svg></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Version Diff")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"sr_delta":0.15,"high_risk_layers":2}

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

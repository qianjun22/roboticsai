"""Semantic Policy Tagger — FastAPI port 8484"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8484

def build_html():
    policies = [
        ("dagger_run9_v2.2", ["dagger", "franka", "pick_place", "sr_high", "production"]),
        ("groot_finetune_v2", ["groot_n1.6", "franka", "multi_task", "sr_high", "staging"]),
        ("bc_baseline_v2", ["behavioral_cloning", "franka", "pick_place", "sr_medium"]),
        ("offline_rl", ["cql", "franka", "pick_place", "sr_medium", "experimental"]),
        ("contrastive_policy", ["contrastive", "franka", "multi_task", "sr_medium"]),
    ]
    
    tag_counts = {}
    for _, tags in policies:
        for t in tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    
    top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:10]
    
    tag_bars = ""
    for tag, count in top_tags:
        w = count / max(tag_counts.values()) * 100
        col = "#38bdf8" if count > 2 else "#64748b"
        tag_bars += f'''<div style="display:flex;align-items:center;margin-bottom:6px">
<span style="width:160px;color:#e2e8f0;font-size:12px">{tag}</span>
<div style="background:#334155;border-radius:3px;height:8px;width:200px">
<div style="background:{col};width:{w:.0f}%;height:8px;border-radius:3px"></div></div>
<span style="margin-left:8px;color:{col};font-size:12px">{count}</span>
</div>'''
    
    policy_rows = ""
    for name, tags in policies:
        tag_html = " ".join([f'<span style="background:#1e3a5f;color:#38bdf8;padding:1px 6px;border-radius:3px;font-size:11px;margin-right:3px">{t}</span>' for t in tags])
        policy_rows += f'<tr><td style="color:#e2e8f0">{name}</td><td>{tag_html}</td></tr>'
    
    cooccur = [[0]*6 for _ in range(6)]
    tag_names = ["dagger", "franka", "pick_place", "sr_high", "multi_task", "production"]
    cells = ""
    for i in range(6):
        for j in range(6):
            v = random.uniform(0.2, 1.0) if i != j else 1.0
            opacity = v
            x = j * 52 + 5
            y = i * 52 + 5
            cells += f'<rect x="{x}" y="{y}" width="48" height="48" fill="#38bdf8" opacity="{opacity:.2f}" rx="3"/>'
            lv = f"{v:.2f}"
            cells += f'<text x="{x+24}" y="{y+28}" text-anchor="middle" fill="white" font-size="10">{lv}</text>'
    
    return f"""<!DOCTYPE html><html><head><title>Semantic Policy Tagger</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{text-align:left;color:#64748b;padding:6px 0;border-bottom:1px solid #334155}}
td{{padding:6px 0;border-bottom:1px solid #1e293b}}</style></head>
<body>
<div class="hdr"><h1>Semantic Policy Tagger</h1><span>port {PORT} · {len(policies)} policies tagged</span></div>
<div class="grid">
<div class="card"><h3>Total Policies</h3><div class="stat">{len(policies)}</div><div class="sub">{sum(len(t) for _,t in policies)} tags assigned</div></div>
<div class="card"><h3>Unique Tags</h3><div class="stat">{len(tag_counts)}</div><div class="sub">taxonomy depth 4 levels</div></div>
<div class="card"><h3>Tag Frequency</h3>{tag_bars}</div>
<div class="card"><h3>Tag Co-occurrence Heatmap</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:8px">{" | ".join(tag_names)}</div>
<svg width="100%" viewBox="0 0 317 317">{cells}</svg></div>
<div class="card" style="grid-column:span 2"><h3>Policy Tag Index</h3>
<table><tr><th>Policy</th><th>Tags</th></tr>{policy_rows}</table></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Semantic Policy Tagger")
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

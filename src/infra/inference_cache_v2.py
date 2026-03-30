"""Inference Cache v2 — FastAPI port 8495"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8495

def build_html():
    # cache tiers
    tiers = [
        ("L1: VRAM", "2 GB", 847, 0.71, "#22c55e", "sub-ms hit latency"),
        ("L2: SSD", "40 GB", 2341, 0.21, "#38bdf8", "8ms hit latency"),
        ("L3: Object Store", "∞", 8741, 0.08, "#f59e0b", "45ms hit latency"),
    ]
    
    tier_rows = ""
    for name, size, entries, hit_rate, col, desc in tiers:
        tier_rows += f'<tr><td style="color:{col}">{name}</td><td>{size}</td><td>{entries:,}</td><td style="color:{col}">{hit_rate*100:.0f}%</td><td style="color:#64748b;font-size:11px">{desc}</td></tr>'
    
    total_hit_rate = sum(t[3] for t in tiers)
    
    # hit rate trend for 3 strategies
    strategies = [
        ("LRU", [45 + i*0.5 + random.uniform(-3,3) for i in range(30)], "#64748b"),
        ("LFU", [52 + i*0.4 + random.uniform(-3,3) for i in range(30)], "#38bdf8"),
        ("Adaptive", [58 + i*0.43 + random.uniform(-2,2) for i in range(30)], "#22c55e"),
    ]
    
    strategy_svgs = ""
    for name, rates, col in strategies:
        pts = []
        for i, v in enumerate(rates):
            x = i * 500 / 29
            y = 80 - (v - 40) / 40 * 80
            pts.append(f"{x:.1f},{y:.1f}")
        strategy_svgs += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="2"/>'
    
    legend = "".join([f'<span style="color:{c}">— {n}</span><span style="margin-right:12px"> </span>' for n,_,c in strategies])
    
    # cold start comparison
    cold_bar_w = 1840 / 2000 * 300
    warm_bar_w = 226 / 2000 * 300
    
    return f"""<!DOCTYPE html><html><head><title>Inference Cache v2</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{text-align:left;color:#64748b;padding:6px 0;border-bottom:1px solid #334155}}
td{{padding:6px 0;border-bottom:1px solid #1e293b}}</style></head>
<body>
<div class="hdr"><h1>Inference Cache v2</h1><span>port {PORT} · 3-tier cache</span></div>
<div class="grid">
<div class="card"><h3>L1 Hit Rate</h3><div class="stat">71%</div><div class="sub">adaptive eviction policy</div></div>
<div class="card"><h3>Cold Start</h3><div class="stat">1840ms</div><div class="sub">→ 226ms with full warmup</div></div>
<div class="card"><h3>Daily Savings</h3><div class="stat">$12</div><div class="sub">GPU idle time eliminated</div></div>
<div class="card" style="grid-column:span 3"><h3>Cache Tier Configuration</h3>
<table><tr><th>Tier</th><th>Size</th><th>Entries</th><th>Hit Rate</th><th>Latency</th></tr>{tier_rows}</table>
<div style="margin-top:12px;font-size:12px;color:#64748b">Combined effective hit rate: <span style="color:#22c55e">{total_hit_rate*100:.0f}%</span></div></div>
<div class="card" style="grid-column:span 2"><h3>Cache Strategy Comparison (30 days)</h3>
<div style="font-size:11px;margin-bottom:8px">{legend}</div>
<svg width="100%" viewBox="0 0 500 80">{strategy_svgs}</svg></div>
<div class="card"><h3>Cold vs Warm Start</h3>
<div style="margin-top:8px">
<div style="color:#64748b;font-size:12px;margin-bottom:6px">Cold start (no cache)</div>
<div style="background:#334155;border-radius:3px;height:14px;margin-bottom:8px">
<div style="background:#ef4444;width:{cold_bar_w/3:.0f}%;height:14px;border-radius:3px"></div></div>
<div style="color:#64748b;font-size:12px;margin-bottom:6px">Warm start (full cache)</div>
<div style="background:#334155;border-radius:3px;height:14px">
<div style="background:#22c55e;width:{warm_bar_w/3:.0f}%;height:14px;border-radius:3px"></div></div>
<div style="margin-top:8px;font-size:11px;color:#64748b"><span style="color:#ef4444">1840ms</span> → <span style="color:#22c55e">226ms</span> · 8.1× speedup</div>
</div></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Inference Cache v2")
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

"""Eval Batch Scheduler — FastAPI port 8511"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8511

def build_html():
    # pending eval queue
    pending_evals = [
        ("DAgger_run10_step1420", "dagger", "PI", 8.5, "high", "#ef4444"),
        ("groot_v2_regression", "regression", "all", 4.2, "high", "#ef4444"),
        ("BC_baseline_refresh", "benchmark", "internal", 3.8, "medium", "#f59e0b"),
        ("UR5e_embodiment_test", "embodiment", "Apt", 6.1, "medium", "#f59e0b"),
        ("sim2real_gap_v3", "sim2real", "internal", 5.4, "medium", "#f59e0b"),
        ("pi_partner_quarterly", "partner", "PI", 2.9, "low", "#38bdf8"),
        ("covariant_eval", "partner", "Covariant", 3.1, "low", "#38bdf8"),
        ("safety_audit_eval", "safety", "all", 7.2, "high", "#ef4444"),
    ]
    
    queue_rows = ""
    for name, eval_type, partner, cost, priority, col in pending_evals:
        queue_rows += f'<tr><td style="color:{col};font-size:11px">{name}</td><td style="color:#64748b;font-size:11px">{eval_type}</td><td>{partner}</td><td>${cost:.1f}</td><td><span style="background:{col};color:#0f172a;padding:1px 5px;border-radius:3px;font-size:10px">{priority}</span></td></tr>'
    
    total_individual = sum(e[3] for e in pending_evals)
    total_batched = total_individual * 0.33
    
    # 7-day eval calendar heatmap
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    eval_types = ["dagger", "regression", "partner", "safety"]
    heatmap = ""
    for d_idx in range(7):
        for e_idx, etype in enumerate(eval_types):
            is_scheduled = random.random() > 0.4
            col = {"dagger": "#ef4444", "regression": "#f59e0b", "partner": "#38bdf8", "safety": "#a78bfa"}[etype]
            x = d_idx * 68 + 10
            y = e_idx * 20 + 5
            opacity = 0.8 if is_scheduled else 0.1
            heatmap += f'<rect x="{x}" y="{y}" width="60" height="16" fill="{col}" opacity="{opacity:.1f}" rx="2"/>'
            if is_scheduled:
                heatmap += f'<text x="{x+30}" y="{y+11}" text-anchor="middle" fill="white" font-size="8">{etype[:3]}</text>'
        heatmap += f'<text x="{d_idx*68+40}" y="92" text-anchor="middle" fill="#64748b" font-size="9">{days[d_idx]}</text>'
    
    for e_idx, etype in enumerate(eval_types):
        col = {"dagger": "#ef4444", "regression": "#f59e0b", "partner": "#38bdf8", "safety": "#a78bfa"}[etype]
        heatmap += f'<text x="490" y="{e_idx*20+15}" fill="{col}" font-size="8">{etype}</text>'
    
    # batching savings
    savings_pct = (total_individual - total_batched) / total_individual * 100
    
    return f"""<!DOCTYPE html><html><head><title>Eval Batch Scheduler</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{text-align:left;color:#64748b;padding:5px 0;border-bottom:1px solid #334155}}
td{{padding:5px 2px;border-bottom:1px solid #1e293b}}</style></head>
<body>
<div class="hdr"><h1>Eval Batch Scheduler</h1><span>port {PORT} · {len(pending_evals)} evals queued</span></div>
<div class="grid">
<div class="card"><h3>Queue Depth</h3><div class="stat">{len(pending_evals)}</div><div class="sub">pending evaluations</div></div>
<div class="card"><h3>Batch Savings</h3><div class="stat">{savings_pct:.0f}%</div><div class="sub">${total_individual:.1f} → ${total_batched:.1f} batched</div></div>
<div class="card"><h3>Eval Queue</h3>
<table><tr><th>Name</th><th>Type</th><th>Partner</th><th>Cost</th><th>Priority</th></tr>{queue_rows}</table></div>
<div class="card"><h3>7-Day Eval Calendar</h3>
<svg width="100%" viewBox="0 0 490 100">{heatmap}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Eval Batch Scheduler")
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

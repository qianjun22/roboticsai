"""GR00T N2 Readiness — FastAPI port 8889"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8889

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    # 8-item readiness checklist
    checklist = [
        ("A100/H100 GPU Quota (H2 2026)", 85, "In Progress"),
        ("GR00T N2 Model Weights Access", 60, "Pending NVIDIA NDA"),
        ("7B Parameter Inference Infra", 90, "Ready"),
        ("Fine-Tuning Pipeline (LeRobot)", 95, "Ready"),
        ("Data Flywheel (1000+ demos)", 80, "In Progress"),
        ("Multi-Task Eval Harness", 100, "Complete"),
        ("OCI Networking / VCN Config", 75, "In Progress"),
        ("Safety Monitor Integration", 70, "In Progress"),
    ]
    checklist_html = ""
    for item, pct, status in checklist:
        color = "#22c55e" if status == "Complete" or status == "Ready" else ("#f59e0b" if "Progress" in status else "#ef4444")
        checklist_html += f"""
        <div style='margin:8px 0'>
          <div style='display:flex;justify-content:space-between'><span>{item}</span><span style='color:{color}'>{status} ({pct}%)</span></div>
          <div style='background:#334155;border-radius:4px;height:10px;margin-top:4px'>
            <div style='background:{color};width:{pct}%;height:10px;border-radius:4px'></div>
          </div>
        </div>"""
    overall = round(sum(p for _, p, _ in checklist) / len(checklist), 1)
    # N1.6 vs N2 comparison
    comparison = [
        ("Parameters", "1.6B", "7B"),
        ("SR (LIBERO Spatial)", "0.72", "0.91 (projected)"),
        ("Inference Latency", "227ms", "~380ms"),
        ("Fine-Tune VRAM", "6.7 GB", "~28 GB"),
        ("Multi-task Generalization", "Moderate", "High"),
        ("Language Grounding", "Basic", "Advanced (LLM backbone)"),
        ("Cross-Embodiment", "Limited", "Full"),
        ("OCI Availability", "Now", "H2 2026"),
    ]
    cmp_rows = "".join(f"<tr><td style='padding:4px 12px'>{attr}</td><td style='padding:4px 12px;color:#94a3b8'>{n1}</td><td style='padding:4px 12px;color:#38bdf8;font-weight:bold'>{n2}</td></tr>" for attr, n1, n2 in comparison)
    return f"""<!DOCTYPE html><html><head><title>GR00T N2 Readiness</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}th{{background:#334155;color:#38bdf8;padding:6px 12px}}tr:nth-child(even){{background:#263044}}</style></head>
<body><h1>GR00T N2 Readiness</h1>
<p style='margin:10px;color:#94a3b8'>OCI readiness assessment for GR00T N2 (7B params, H2 2026) | Projected SR = 0.91</p>
<div class='card'><h2>Overall Readiness: {overall}%</h2>
<div style='background:#334155;border-radius:6px;height:16px'>
  <div style='background:#C74634;width:{overall}%;height:16px;border-radius:6px'></div>
</div></div>
<div class='card'><h2>8-Item Readiness Checklist</h2>{checklist_html}</div>
<div class='card'><h2>N1.6 vs N2 Capability Comparison</h2>
<table><tr><th>Attribute</th><th>GR00T N1.6 (Current)</th><th>GR00T N2 (Target)</th></tr>{cmp_rows}</table></div>
<div class='card'><h2>Metrics</h2>
<svg width='450' height='180'>{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="GR00T N2 Readiness")
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

"""Scene Graph Builder — FastAPI port 8538"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8538

def build_html():
    # Simple node-edge graph visualization
    nodes = [("cube", 200, 100, "#38bdf8"), ("table", 200, 200, "#C74634"), ("gripper", 320, 150, "#22c55e"), ("bin", 80, 180, "#f59e0b"), ("shelf", 340, 260, "#38bdf8")]
    edges = [(0,1,"on"), (0,2,"grasped_by"), (1,3,"beside"), (1,4,"supports")]
    edge_lines = "".join(f'<line x1="{nodes[a][1]}" y1="{nodes[a][2]}" x2="{nodes[b][1]}" y2="{nodes[b][2]}" stroke="#334155" stroke-width="2"/><text x="{(nodes[a][1]+nodes[b][1])//2}" y="{(nodes[a][2]+nodes[b][2])//2-5}" fill="#64748b" font-size="9" text-anchor="middle">{rel}</text>' for a,b,rel in edges)
    node_circles = "".join(f'<circle cx="{x}" cy="{y}" r="20" fill="{c}"/><text x="{x}" y="{y+4}" fill="#0f172a" font-size="10" text-anchor="middle">{n}</text>' for n,x,y,c in nodes)
    return f"""<!DOCTYPE html><html><head><title>Scene Graph Builder</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Scene Graph Builder</h1><span style="color:#64748b">Spatial scene graphs | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">8.4</div><div class="lbl">Avg Objects/Scene</div></div>
<div class="card"><div class="metric">24</div><div class="lbl">Spatial Relation Types</div></div>
<div class="card"><div class="metric">+0.06pp</div><div class="lbl">SR vs Raw Image</div></div>
<div class="card"><div class="metric">1,000</div><div class="lbl">Training Scenes</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">EXAMPLE SCENE GRAPH</div>
<svg width="100%" height="310" viewBox="0 0 430 310">
<rect width="430" height="310" fill="#0f172a"/>
{edge_lines}{node_circles}
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Scene Graph Builder")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI: uvicorn.run(app, host="0.0.0.0", port=PORT)
    else: HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

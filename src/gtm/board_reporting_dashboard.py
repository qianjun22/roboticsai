"""Board Reporting Dashboard — FastAPI port 9979"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 9979

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(
        f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>'
        for i, v in enumerate(data)
    )
    return f"""<!DOCTYPE html><html><head><title>Board Reporting Dashboard — Port {PORT}</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
h1{{color:#C74634;padding:20px}}svg{{display:block;margin:20px}}</style></head>
<body><h1>Board Reporting Dashboard — Port {PORT}</h1>
<svg width="430" height="180" style="background:#1e293b;border-radius:8px">{bars}</svg>
<p style="padding:20px;color:#38bdf8">status: operational | port: {PORT}</p></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Board Reporting Dashboard")
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

"""Sim Asset Generator — FastAPI service (port 10196).

Procedural sim asset generation: objects, textures, lighting, scenes.
"""

import json
import time
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10196
SERVICE_NAME = "sim_asset_generator"

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="Sim Asset Generator", version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME,
                             "timestamp": datetime.utcnow().isoformat() + "Z"})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(_build_dashboard())

    @app.post("/sim/generate_object")
    def generate_object(object_type: str = "rigid", variant_seed: int = 0):
        """Stub: generate a new object variant procedurally."""
        return JSONResponse({
            "status": "queued",
            "object_type": object_type,
            "variant_seed": variant_seed,
            "estimated_seconds": 120,
            "asset_id": f"obj_{object_type}_{variant_seed}_{int(time.time())}",
            "note": "Generation queued — 2 min for new rigid variant"
        })

    @app.get("/sim/asset_library")
    def asset_library():
        """Stub: return current asset library statistics."""
        return JSONResponse({
            "library": {
                "rigid_objects": 2000,
                "deformable_objects": 200,
                "tools": 150,
                "containers": 300,
                "environments": 50
            },
            "generation_speed": {
                "new_object_variant_sec": 120,
                "texture_sec": 0.3,
                "full_scene_sec": 45
            },
            "speedup_vs_manual": "100x",
            "total_assets": 2700
        })

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_dashboard() -> str:
    bars = [
        ("Rigid Objects", 2000, 2200),
        ("Containers",    300,  2200),
        ("Deformable",    200,  2200),
        ("Tools",         150,  2200),
        ("Environments",   50,  2200),
    ]
    bar_items = ""
    for label, value, max_val in bars:
        width = int(value / max_val * 340)
        bar_items += f"""
        <g>
          <text x="130" y="{{y}}" fill="#94a3b8" font-size="12" text-anchor="end">{label}</text>
          <rect x="140" y="{{yr}}" width="{width}" height="18" fill="#38bdf8" rx="3"/>
          <text x="{140 + width + 6}" y="{{y}}" fill="#e2e8f0" font-size="12">{value:,}</text>
        </g>"""

    # Build SVG with proper y coordinates
    svg_rows = ""
    for i, (label, value, max_val) in enumerate(bars):
        y_text = 58 + i * 36
        y_rect = y_text - 14
        width = int(value / max_val * 340)
        svg_rows += f'<text x="130" y="{y_text}" fill="#94a3b8" font-size="12" text-anchor="end">{label}</text>\n'
        svg_rows += f'<rect x="140" y="{y_rect}" width="{width}" height="18" fill="#38bdf8" rx="3"/>\n'
        svg_rows += f'<text x="{140 + width + 6}" y="{y_text}" fill="#e2e8f0" font-size="12">{value:,}</text>\n'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Sim Asset Generator — Port {PORT}</title>
  <style>
    body {{ margin:0; background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',sans-serif; }}
    .header {{ background:#C74634; padding:18px 32px; display:flex; align-items:center; gap:16px; }}
    .header h1 {{ margin:0; font-size:1.4rem; letter-spacing:.5px; }}
    .badge {{ background:#0f172a; color:#38bdf8; border-radius:6px; padding:3px 10px; font-size:.8rem; font-weight:700; }}
    .container {{ max-width:860px; margin:32px auto; padding:0 24px; }}
    .card {{ background:#1e293b; border-radius:12px; padding:24px; margin-bottom:24px; }}
    .card h2 {{ margin:0 0 16px; font-size:1rem; color:#38bdf8; text-transform:uppercase; letter-spacing:1px; }}
    .stats {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }}
    .stat {{ background:#0f172a; border-radius:8px; padding:16px; text-align:center; }}
    .stat .val {{ font-size:1.8rem; font-weight:700; color:#C74634; }}
    .stat .lbl {{ font-size:.75rem; color:#94a3b8; margin-top:4px; }}
    svg text {{ font-family:'Segoe UI',sans-serif; }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>Sim Asset Generator</h1>
      <div style="color:#fecaca;font-size:.85rem;margin-top:4px">Procedural generation — objects, textures, lighting, scenes</div>
    </div>
    <div class="badge">PORT {PORT}</div>
  </div>
  <div class="container">
    <div class="stats">
      <div class="stat"><div class="val">2,700</div><div class="lbl">Total Assets</div></div>
      <div class="stat"><div class="val">100x</div><div class="lbl">Faster than Manual</div></div>
      <div class="stat"><div class="val">0.3s</div><div class="lbl">Texture Gen Speed</div></div>
    </div>
    <div class="card" style="margin-top:24px">
      <h2>Asset Library</h2>
      <svg width="520" height="200" style="display:block;margin:0 auto">
        <text x="260" y="20" fill="#94a3b8" font-size="11" text-anchor="middle">Asset Count by Category</text>
        {svg_rows}
      </svg>
    </div>
    <div class="card">
      <h2>Generation Speed</h2>
      <div class="stats">
        <div class="stat"><div class="val">2 min</div><div class="lbl">New Object Variant</div></div>
        <div class="stat"><div class="val">0.3 s</div><div class="lbl">Texture Synthesis</div></div>
        <div class="stat"><div class="val">45 s</div><div class="lbl">Full Scene</div></div>
      </div>
    </div>
    <div class="card">
      <h2>Endpoints</h2>
      <ul style="color:#94a3b8;line-height:2">
        <li><code style="color:#38bdf8">GET  /health</code> — Health check</li>
        <li><code style="color:#38bdf8">GET  /sim/asset_library</code> — Asset library stats</li>
        <li><code style="color:#38bdf8">POST /sim/generate_object</code> — Queue object generation</li>
      </ul>
    </div>
  </div>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Fallback HTTP server
# ---------------------------------------------------------------------------

def _run_fallback():
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = _build_dashboard().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
        def log_message(self, fmt, *args):
            pass

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"[{SERVICE_NAME}] fallback HTTP server on port {PORT}")
        httpd.serve_forever()

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_fallback()

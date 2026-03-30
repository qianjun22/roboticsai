"""Contact Geometry Analyzer — FastAPI port 8796"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8796

def build_html():
    random.seed(42)
    # Generate contact patch geometry data
    n_points = 36
    # Elliptical contact patch (Hertzian contact model)
    a = 0.042  # semi-major axis (m)
    b = 0.028  # semi-minor axis (m)
    patch_points = []
    for i in range(n_points + 1):
        theta = 2 * math.pi * i / n_points
        x = 200 + 150 * a / 0.05 * math.cos(theta)
        y = 200 + 150 * b / 0.05 * math.sin(theta)
        patch_points.append(f"{x:.1f},{y:.1f}")
    patch_poly = " ".join(patch_points)

    # Pressure distribution (parabolic Hertzian)
    p0 = 4.2  # peak pressure MPa
    pressure_bars = []
    cx, cy_base = 200, 330
    for i in range(20):
        t = (i - 9.5) / 9.5
        p = p0 * max(0, 1 - t*t)
        bh = int(p / p0 * 80)
        bx = cx - 95 + i * 10
        g = int(56 + (p / p0) * 180)
        pressure_bars.append(
            f'<rect x="{bx}" y="{330 - bh}" width="8" height="{bh}" fill="rgb(56,{g},180)" rx="1"/>'
        )

    # Normal force history (sine + noise)
    force_pts = []
    for i in range(60):
        t = i / 59
        f = 12.5 + 3.0 * math.sin(2 * math.pi * t * 2.3) + random.gauss(0, 0.4)
        fx = 50 + i * 8
        fy = 480 - int((f / 20.0) * 100)
        force_pts.append(f"{fx},{fy}")
    force_poly = " ".join(force_pts)

    # Slip velocity vectors
    slip_arrows = []
    for i in range(5):
        for j in range(5):
            sx = 60 + i * 70
            sy = 560 + j * 50
            mag = random.uniform(0.002, 0.018)
            angle = random.uniform(-math.pi/4, math.pi/4)
            dx = mag / 0.02 * 25 * math.cos(angle)
            dy = mag / 0.02 * 25 * math.sin(angle)
            spd = int(mag / 0.02 * 255)
            color = f"rgb({spd},180,{255-spd})"
            slip_arrows.append(
                f'<line x1="{sx}" y1="{sy}" x2="{sx+dx:.1f}" y2="{sy+dy:.1f}" stroke="{color}" stroke-width="2" marker-end="url(#arr)"/>'
            )

    # Contact normal estimation stats
    normals = [(random.gauss(0, 0.03), random.gauss(0, 0.03)) for _ in range(40)]
    normal_dots = "".join(
        f'<circle cx="{700 + nx*400:.1f}" cy="{130 - ny*400:.1f}" r="3" fill="#38bdf8" opacity="0.75"/>'
        for nx, ny in normals
    )
    # Mean normal
    mn_x = sum(n[0] for n in normals) / len(normals)
    mn_y = sum(n[1] for n in normals) / len(normals)

    metrics = [
        ("Contact Area", f"{math.pi * a * b * 1e4:.2f} cm²"),
        ("Peak Pressure", f"{p0:.1f} MPa"),
        ("Normal Force", "12.5 N"),
        ("Friction Coeff", "0.42"),
        ("Slip RMS", "6.3 mm/s"),
        ("Patch Aspect", f"{a/b:.2f}"),
    ]
    metric_cards = "".join(
        f'<div class="metric"><div class="mlabel">{lbl}</div><div class="mval">{val}</div></div>'
        for lbl, val in metrics
    )

    return f"""<!DOCTYPE html><html><head><title>Contact Geometry Analyzer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0}}h2{{color:#38bdf8;font-size:14px;margin:6px 0}}
.card{{background:#1e293b;padding:16px;margin:10px 0;border-radius:8px;border:1px solid #334155}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.metrics{{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}}
.metric{{background:#0f172a;border:1px solid #334155;border-radius:6px;padding:10px 16px;min-width:120px}}
.mlabel{{font-size:11px;color:#94a3b8}}.mval{{font-size:20px;font-weight:700;color:#38bdf8}}
.sub{{font-size:12px;color:#64748b;margin-bottom:12px}}
</style></head>
<body>
<h1>Contact Geometry Analyzer</h1>
<p class="sub">Port {PORT} — Hertzian contact mechanics, patch estimation, pressure mapping</p>
<div class="metrics">{metric_cards}</div>
<div class="grid">
<div class="card">
<h2>Contact Patch (Hertzian Ellipse)</h2>
<svg width="400" height="260" style="display:block;margin:auto">
  <defs><radialGradient id="pg" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="#C74634" stop-opacity="0.9"/>
    <stop offset="100%" stop-color="#7c3aed" stop-opacity="0.2"/>
  </radialGradient></defs>
  <rect width="400" height="260" fill="#0f172a" rx="6"/>
  <polygon points="{patch_poly}" fill="url(#pg)" stroke="#C74634" stroke-width="2"/>
  <line x1="200" y1="10" x2="200" y2="250" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>
  <line x1="10" y1="200" x2="390" y2="200" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>
  <text x="210" y="25" fill="#94a3b8" font-size="10">a={a*100:.1f}cm</text>
  <text x="310" y="195" fill="#94a3b8" font-size="10">b={b*100:.1f}cm</text>
</svg>
</div>
<div class="card">
<h2>Pressure Distribution (Hertzian)</h2>
<svg width="400" height="180" style="display:block;margin:auto">
  <rect width="400" height="180" fill="#0f172a" rx="6"/>
  {''.join(pressure_bars)}
  <line x1="10" y1="330" x2="390" y2="330" stroke="#475569" stroke-width="1"/>
  <text x="180" y="170" fill="#94a3b8" font-size="10">Position across patch</text>
  <text x="12" y="260" fill="#94a3b8" font-size="9">p₀={p0}MPa</text>
</svg>
</div>
</div>
<div class="card">
<h2>Normal Force History (60 samples)</h2>
<svg width="100%" height="130" viewBox="0 0 530 130" style="display:block">
  <rect width="530" height="130" fill="#0f172a" rx="6"/>
  <polyline points="{force_poly}" fill="none" stroke="#38bdf8" stroke-width="2"/>
  <line x1="50" y1="30" x2="50" y2="110" stroke="#475569" stroke-width="1"/>
  <line x1="50" y1="110" x2="530" y2="110" stroke="#475569" stroke-width="1"/>
  <text x="55" y="125" fill="#64748b" font-size="9">t=0</text>
  <text x="490" y="125" fill="#64748b" font-size="9">t=1s</text>
  <text x="2" y="50" fill="#64748b" font-size="9">20N</text>
  <text x="2" y="110" fill="#64748b" font-size="9">0N</text>
</svg>
</div>
<div class="grid">
<div class="card">
<h2>Slip Velocity Field</h2>
<svg width="380" height="310" style="display:block;margin:auto">
  <defs><marker id="arr" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
    <path d="M0,0 L6,3 L0,6 Z" fill="#38bdf8"/></marker></defs>
  <rect width="380" height="310" fill="#0f172a" rx="6"/>
  {''.join(slip_arrows)}
  <text x="10" y="298" fill="#64748b" font-size="9">slip velocity (mm/s) — color: magnitude</text>
</svg>
</div>
<div class="card">
<h2>Estimated Contact Normals</h2>
<svg width="380" height="310" style="display:block;margin:auto">
  <rect width="380" height="310" fill="#0f172a" rx="6"/>
  <circle cx="700" cy="130" r="80" fill="none" stroke="#334155" stroke-width="1"/>
  <circle cx="700" cy="130" r="40" fill="none" stroke="#334155" stroke-width="1" stroke-dasharray="3,2"/>
  {normal_dots}
  <line x1="{700 + mn_x*400:.1f}" y1="{130 - mn_y*400:.1f}"
        x2="{700 + mn_x*400 - 6:.1f}" y2="{130 - mn_y*400:.1f}"
        stroke="#C74634" stroke-width="2"/>
  <text x="620" y="290" fill="#64748b" font-size="9">Normal distribution on unit sphere (stereographic)</text>
</svg>
</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Contact Geometry Analyzer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/patch")
    def patch_info():
        a, b = 0.042, 0.028
        return {
            "semi_major_m": a,
            "semi_minor_m": b,
            "area_cm2": round(math.pi * a * b * 1e4, 4),
            "aspect_ratio": round(a / b, 3),
            "peak_pressure_mpa": 4.2,
        }

    @app.get("/metrics")
    def metrics():
        return {
            "contact_area_cm2": 0.369,
            "peak_pressure_mpa": 4.2,
            "normal_force_n": 12.5,
            "friction_coeff": 0.42,
            "slip_rms_mm_s": 6.3,
            "patch_aspect": 1.5,
        }

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a):
        pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

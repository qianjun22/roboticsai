"""Sim Randomization v3 — FastAPI port 8392"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8392

PARAMS = [
    ("friction_coeff", 0.89), ("lighting_intensity", 0.84), ("texture_variance", 0.79),
    ("cube_mass", 0.71), ("camera_angle", 0.68), ("table_height", 0.61),
    ("gripper_stiffness", 0.58), ("env_background", 0.52), ("joint_damping", 0.47),
    ("cube_size", 0.41), ("floor_color", 0.31), ("ambient_light", 0.28),
]

DR_V1 = [0.61] * 20
DR_V2 = [0.61 + (0.07 * min(i, 8) / 8) for i in range(1, 21)]
DR_V3_RAW = [0.61 + (0.17 * (1 - math.exp(-0.3 * i))) for i in range(1, 21)]
DR_V3 = [min(v, 0.78) for v in DR_V3_RAW]

COVERAGE = [
    [0.91,0.88,0.85,0.82,0.79,0.76,0.73,0.71],
    [0.89,0.87,0.84,0.81,0.78,0.75,0.72,0.68],
    [0.86,0.83,0.81,0.78,0.75,0.72,0.65,0.52],
    [0.84,0.82,0.79,0.76,0.73,0.68,0.55,0.41],
    [0.81,0.79,0.76,0.73,0.70,0.61,0.48,0.35],
    [0.78,0.75,0.73,0.70,0.65,0.54,0.42,0.28],
    [0.74,0.71,0.69,0.65,0.58,0.45,0.31,0.18],
    [0.69,0.66,0.62,0.57,0.49,0.38,0.22,0.09],
]

def build_html():
    # Bar chart SVG: 12-param sensitivity
    bw, bh = 620, 340
    bar_svg_parts = [f'<svg width="{bw}" height="{bh}" style="background:#1e293b;border-radius:8px">']
    bar_svg_parts.append('<text x="10" y="22" fill="#e2e8f0" font-size="13" font-weight="bold">DR Parameter Sensitivity (sorted)</text>')
    for i, (name, score) in enumerate(PARAMS):
        y = 38 + i * 24
        bar_w = int(score * 380)
        color = "#C74634" if score >= 0.75 else ("#f59e0b" if score >= 0.50 else "#38bdf8")
        bar_svg_parts.append(f'<rect x="170" y="{y}" width="{bar_w}" height="17" fill="{color}" rx="3"/>')
        bar_svg_parts.append(f'<text x="165" y="{y+13}" fill="#94a3b8" font-size="10" text-anchor="end">{name}</text>')
        bar_svg_parts.append(f'<text x="{170+bar_w+5}" y="{y+13}" fill="#e2e8f0" font-size="10">{score:.2f}</text>')
    bar_svg_parts.append('</svg>')
    bar_svg = "".join(bar_svg_parts)

    # Line chart SVG: DR convergence
    lw, lh, px, py, pw, ph = 620, 280, 50, 30, 530, 220
    line_svg_parts = [f'<svg width="{lw}" height="{lh}" style="background:#1e293b;border-radius:8px">']
    line_svg_parts.append('<text x="10" y="22" fill="#e2e8f0" font-size="13" font-weight="bold">Adaptive DR Convergence (SR vs Iteration)</text>')
    # axes
    line_svg_parts.append(f'<line x1="{px}" y1="{py}" x2="{px}" y2="{py+ph}" stroke="#475569" stroke-width="1"/>')
    line_svg_parts.append(f'<line x1="{px}" y1="{py+ph}" x2="{px+pw}" y2="{py+ph}" stroke="#475569" stroke-width="1"/>')
    for label, sr_vals, color, dash in [("v1",DR_V1,"#64748b","4,4"),("v2",DR_V2,"#38bdf8","4,2"),("v3",DR_V3,"#C74634","")]:
        pts = " ".join(f"{px + i*(pw/19):.1f},{py+ph - (sr_vals[i]-0.55)/(0.30)*ph:.1f}" for i in range(20))
        sd = f' stroke-dasharray="{dash}"' if dash else ""
        line_svg_parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"{sd}/>')
        line_svg_parts.append(f'<text x="{px+pw+4}" y="{py+ph - (sr_vals[-1]-0.55)/(0.30)*ph + 4:.1f}" fill="{color}" font-size="10">DR_{label}</text>')
    # plateau marker
    iter14_x = px + 13 * (pw / 19)
    line_svg_parts.append(f'<line x1="{iter14_x:.1f}" y1="{py}" x2="{iter14_x:.1f}" y2="{py+ph}" stroke="#fbbf24" stroke-width="1" stroke-dasharray="3,3"/>')
    line_svg_parts.append(f'<text x="{iter14_x+2:.1f}" y="{py+12}" fill="#fbbf24" font-size="9">plateau iter14</text>')
    line_svg_parts.append('</svg>')
    line_svg = "".join(line_svg_parts)

    # Heatmap SVG
    hw, hh, cs = 380, 280, 30
    hmap_parts = [f'<svg width="{hw}" height="{hh}" style="background:#1e293b;border-radius:8px">']
    hmap_parts.append('<text x="10" y="22" fill="#e2e8f0" font-size="13" font-weight="bold">Simulation Coverage Heatmap</text>')
    for r in range(8):
        for c in range(8):
            v = COVERAGE[r][c]
            color = ("#16a34a" if v >= 0.7 else ("#f59e0b" if v >= 0.4 else "#C74634"))
            x, y = 20 + c * cs, 35 + r * cs
            hmap_parts.append(f'<rect x="{x}" y="{y}" width="{cs-2}" height="{cs-2}" fill="{color}" rx="2" opacity="{v:.2f}"/>')
            hmap_parts.append(f'<text x="{x+cs//2-1}" y="{y+cs//2+4}" fill="white" font-size="7" text-anchor="middle">{v:.0%}</text>')
    hmap_parts.append('</svg>')
    hmap_svg = "".join(hmap_parts)

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Sim Randomization v3 — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:sans-serif;margin:0;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:14px;margin:16px 0 8px}}
.stats{{display:flex;gap:16px;flex-wrap:wrap;margin:12px 0}}
.stat{{background:#1e293b;border-radius:8px;padding:12px 20px;min-width:160px}}
.stat .val{{font-size:24px;font-weight:bold;color:#C74634}}
.stat .lbl{{font-size:11px;color:#94a3b8;margin-top:2px}}
.row{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px}}</style></head><body>
<h1>Sim Randomization v3</h1>
<p style="color:#94a3b8;margin-top:0">Adaptive domain randomization v3 for sim-to-real transfer — Port {PORT}</p>
<div class="stats">
  <div class="stat"><div class="val">0.78</div><div class="lbl">DR_v3 Success Rate</div></div>
  <div class="stat"><div class="val">0.61</div><div class="lbl">DR_v1 Baseline SR</div></div>
  <div class="stat"><div class="val">+67%</div><div class="lbl">Coverage Improvement</div></div>
  <div class="stat"><div class="val">$0.14</div><div class="lbl">Cost / 1k Demo Frames</div></div>
  <div class="stat"><div class="val">84%</div><div class="lbl">Grid Cells Covered</div></div>
</div>
<h2>Parameter Sensitivity (DR_v3)</h2>{bar_svg}
<div class="row" style="margin-top:16px">
  <div><h2>Convergence Curves</h2>{line_svg}</div>
  <div><h2>Coverage Heatmap (8x8)</h2>{hmap_svg}</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Sim Randomization v3")
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

"""Sensor Noise Simulator — FastAPI port 8742"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8742

# Sensor noise models
NOISE_MODELS = [
    ("IMU Gyroscope",     0.002, 0.0005, "#38bdf8"),
    ("IMU Accelerometer", 0.015, 0.003,  "#34d399"),
    ("LIDAR Range",       0.008, 0.001,  "#f472b6"),
    ("Depth Camera",      0.025, 0.006,  "#fb923c"),
    ("Force/Torque",      0.004, 0.0008, "#a78bfa"),
    ("Encoder",           0.001, 0.0002, "#facc15"),
]

def gaussian(mu, sigma):
    # Box-Muller transform — no numpy needed
    u1 = random.random() or 1e-12
    u2 = random.random()
    return mu + sigma * math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)

def generate_time_series(n, base_sigma, drift_rate, seed_offset):
    """Simulate sensor readings with Gaussian noise + slow drift."""
    pts = []
    drift = 0.0
    for i in range(n):
        drift += gaussian(0, drift_rate)
        val = gaussian(drift, base_sigma)
        pts.append(val)
    return pts

def polyline_svg(pts, x0, y0, w, h, color, stroke=1.5):
    """Map a list of floats to an SVG polyline inside a bounding box."""
    lo, hi = min(pts), max(pts)
    span = hi - lo or 1e-9
    coords = []
    for i, v in enumerate(pts):
        x = x0 + (i / (len(pts) - 1)) * w
        y = y0 + h - ((v - lo) / span) * h
        coords.append(f"{x:.1f},{y:.1f}")
    return (f'<polyline points="{" ".join(coords)}" '
            f'fill="none" stroke="{color}" stroke-width="{stroke}" '
            f'stroke-linejoin="round"/>')

def histogram_svg(pts, x0, y0, w, h, color, bins=20):
    """Draw a histogram of pts as SVG rects."""
    lo, hi = min(pts), max(pts)
    span = hi - lo or 1e-9
    counts = [0] * bins
    for v in pts:
        b = min(int((v - lo) / span * bins), bins - 1)
        counts[b] += 1
    mx = max(counts) or 1
    bar_w = w / bins
    rects = []
    for i, c in enumerate(counts):
        bh = (c / mx) * h
        rx = x0 + i * bar_w
        ry = y0 + h - bh
        rects.append(
            f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{bar_w - 1:.1f}" '
            f'height="{bh:.1f}" fill="{color}" opacity="0.75"/>'
        )
    return "".join(rects)

def build_html():
    N = 120
    rows_html = []
    stat_cards = []
    svg_charts = []

    for idx, (name, sigma, drift, color) in enumerate(NOISE_MODELS):
        pts = generate_time_series(N, sigma, drift, idx)
        mean_v = sum(pts) / N
        variance = sum((v - mean_v) ** 2 for v in pts) / N
        std_v = math.sqrt(variance)
        snr = 10 * math.log10(abs(mean_v) / std_v + 1e-12) if std_v else 99
        rms = math.sqrt(sum(v ** 2 for v in pts) / N)

        # Time-series sparkline
        svg_ts = (
            f'<svg width="320" height="80" style="display:block">'
            f'{polyline_svg(pts, 4, 4, 312, 72, color)}'
            f'</svg>'
        )
        # Histogram
        svg_hist = (
            f'<svg width="200" height="80" style="display:block">'
            f'{histogram_svg(pts, 4, 4, 192, 72, color)}'
            f'</svg>'
        )
        rows_html.append(
            f'<tr style="border-bottom:1px solid #334155">'
            f'<td style="padding:8px 12px;color:{color};font-weight:600">{name}</td>'
            f'<td style="padding:8px 12px">{svg_ts}</td>'
            f'<td style="padding:8px 12px">{svg_hist}</td>'
            f'<td style="padding:8px 12px;font-family:monospace">{sigma:.4f}</td>'
            f'<td style="padding:8px 12px;font-family:monospace">{std_v:.4f}</td>'
            f'<td style="padding:8px 12px;font-family:monospace">{snr:.1f} dB</td>'
            f'<td style="padding:8px 12px;font-family:monospace">{rms:.4f}</td>'
            f'</tr>'
        )
        stat_cards.append(
            f'<div class="card" style="border-left:3px solid {color}">'
            f'<div style="color:{color};font-weight:700;font-size:0.9rem">{name}</div>'
            f'<div style="font-size:1.6rem;margin:6px 0">&sigma; = {std_v:.4f}</div>'
            f'<div style="color:#94a3b8;font-size:0.8rem">SNR {snr:.1f} dB &nbsp;|&nbsp; RMS {rms:.4f}</div>'
            f'</div>'
        )

    # Noise floor comparison bar chart
    bar_svg_parts = []
    bar_w, bar_gap = 60, 18
    chart_h = 140
    max_sigma = max(s for _, s, _, _ in NOISE_MODELS)
    for i, (name, sigma, _, color) in enumerate(NOISE_MODELS):
        bh = (sigma / max_sigma) * (chart_h - 20)
        bx = 40 + i * (bar_w + bar_gap)
        by = chart_h - bh
        label = name.split()[0]
        bar_svg_parts.append(
            f'<rect x="{bx}" y="{by:.1f}" width="{bar_w}" height="{bh:.1f}" '
            f'fill="{color}" rx="3"/>'
            f'<text x="{bx + bar_w/2:.0f}" y="{by - 4:.0f}" text-anchor="middle" '
            f'fill="{color}" font-size="11" font-family="monospace">{sigma:.4f}</text>'
            f'<text x="{bx + bar_w/2:.0f}" y="{chart_h + 16}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="10">{label}</text>'
        )
    total_bar_w = 40 + len(NOISE_MODELS) * (bar_w + bar_gap)
    noise_floor_svg = (
        f'<svg width="{total_bar_w}" height="{chart_h + 30}">'
        + "".join(bar_svg_parts)
        + f'<line x1="30" y1="{chart_h}" x2="{total_bar_w}" y2="{chart_h}" '
        f'stroke="#475569" stroke-width="1"/>'
        + "</svg>"
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Sensor Noise Simulator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 24px 4px;font-size:1.5rem}}
.subtitle{{color:#94a3b8;padding:0 24px 16px;font-size:0.85rem}}
.section{{padding:0 24px 24px}}
.cards{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:24px}}
.card{{background:#1e293b;padding:16px 20px;border-radius:8px;min-width:180px;flex:1}}
table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
th{{background:#0f172a;color:#94a3b8;text-align:left;padding:10px 12px;font-size:0.78rem;text-transform:uppercase;letter-spacing:0.05em}}
td{{vertical-align:middle}}
.badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:0.75rem;background:#1e3a5f;color:#38bdf8}}
</style></head>
<body>
<h1>Sensor Noise Simulator</h1>
<div class="subtitle">OCI Robot Cloud &mdash; Real-time sensor noise modelling &nbsp;|&nbsp; Port {PORT}</div>

<div class="section">
  <div class="cards">{''.join(stat_cards)}</div>
</div>

<div class="section">
  <div class="card">
    <h2 style="color:#38bdf8;margin-top:0">Noise Floor Comparison (&sigma;)</h2>
    {noise_floor_svg}
  </div>
</div>

<div class="section">
  <div class="card" style="overflow-x:auto">
    <h2 style="color:#38bdf8;margin-top:0">Per-Sensor Time Series &amp; Distribution</h2>
    <table>
      <tr>
        <th>Sensor</th><th>Time Series (120 samples)</th><th>Noise Distribution</th>
        <th>Nominal &sigma;</th><th>Measured &sigma;</th><th>SNR</th><th>RMS</th>
      </tr>
      {''.join(rows_html)}
    </table>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Sensor Noise Simulator")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "sensors": len(NOISE_MODELS)}

    @app.get("/api/noise")
    def api_noise():
        results = {}
        for name, sigma, drift, _ in NOISE_MODELS:
            pts = generate_time_series(120, sigma, drift, 0)
            mean_v = sum(pts) / 120
            var = sum((v - mean_v) ** 2 for v in pts) / 120
            results[name] = {
                "nominal_sigma": sigma,
                "measured_sigma": math.sqrt(var),
                "rms": math.sqrt(sum(v ** 2 for v in pts) / 120),
            }
        return results

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

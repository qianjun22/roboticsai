"""Workspace Mapping Service — FastAPI port 8740"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8740

def build_html():
    # Generate workspace occupancy grid (12x8) with gaussian-like hotspots
    random.seed(42)
    cols, rows = 12, 8
    # Two hotspot centers
    centers = [(3.5, 2.5), (8.5, 5.5)]
    def heat(c, r):
        v = 0.0
        for cx, cy in centers:
            d2 = (c - cx)**2 + (r - cy)**2
            v += math.exp(-d2 / 4.0)
        noise = random.uniform(-0.05, 0.05)
        return min(1.0, max(0.0, v + noise))

    cells = []
    for r in range(rows):
        for c in range(cols):
            cells.append(heat(c, r))

    # Color scale: low=dark blue, mid=teal, high=orange-red (Oracle)
    def cell_color(v):
        if v < 0.33:
            r2 = int(15 + v * 3 * 30)
            g2 = int(23 + v * 3 * 60)
            b2 = int(100 + v * 3 * 80)
        elif v < 0.66:
            t = (v - 0.33) / 0.33
            r2 = int(45 + t * 130)
            g2 = int(83 + t * 107)
            b2 = int(180 - t * 130)
        else:
            t = (v - 0.66) / 0.34
            r2 = int(175 + t * 24)
            g2 = int(190 - t * 120)
            b2 = int(50 - t * 30)
        return f"rgb({r2},{g2},{b2})"

    cell_w, cell_h = 46, 36
    svg_w = cols * cell_w + 60
    svg_h = rows * cell_h + 60

    grid_rects = ""
    for idx, v in enumerate(cells):
        c = idx % cols
        r = idx // cols
        x = 40 + c * cell_w
        y = 30 + r * cell_h
        color = cell_color(v)
        pct = int(v * 100)
        grid_rects += f'<rect x="{x}" y="{y}" width="{cell_w-2}" height="{cell_h-2}" fill="{color}" rx="3" opacity="0.92"/>'
        if cell_w >= 40:
            grid_rects += f'<text x="{x + cell_w//2 - 2}" y="{y + cell_h//2 + 5}" fill="#e2e8f0" font-size="10" text-anchor="middle">{pct}%</text>'

    # Robot arm reachability arc — sinusoidal sweep
    arc_points = []
    arm_cx, arm_cy = 40 + 3 * cell_w, 30 + 6 * cell_h
    for deg in range(0, 181, 6):
        angle = math.radians(deg)
        reach_inner = 60
        reach_outer = 140 + 20 * math.sin(math.radians(deg * 2))
        xi = arm_cx + reach_inner * math.cos(angle)
        yi = arm_cy - reach_inner * math.sin(angle)
        xo = arm_cx + reach_outer * math.cos(angle)
        yo = arm_cy - reach_outer * math.sin(angle)
        arc_points.append((xi, yi, xo, yo))

    arc_lines = ""
    for xi, yi, xo, yo in arc_points:
        arc_lines += f'<line x1="{xi:.1f}" y1="{yi:.1f}" x2="{xo:.1f}" y2="{yo:.1f}" stroke="#C74634" stroke-width="1" opacity="0.4"/>'

    # Joint angle timeline — sine wave per joint
    timeline_w, timeline_h = 560, 100
    tl_x0, tl_y0 = 30, 20
    joint_paths = ""
    joint_colors = ["#38bdf8", "#C74634", "#34d399", "#fbbf24", "#a78bfa", "#f472b6"]
    n_pts = 80
    for j in range(6):
        phase = j * math.pi / 3
        freq = 1.0 + j * 0.3
        pts = []
        for i in range(n_pts):
            t = i / (n_pts - 1)
            angle_val = math.sin(2 * math.pi * freq * t + phase) * 0.8 + random.uniform(-0.05, 0.05)
            px = tl_x0 + t * timeline_w
            py = tl_y0 + timeline_h / 2 - angle_val * (timeline_h / 2 - 8)
            pts.append(f"{px:.1f},{py:.1f}")
        path_d = "M " + " L ".join(pts)
        joint_paths += f'<path d="{path_d}" fill="none" stroke="{joint_colors[j]}" stroke-width="1.5" opacity="0.85"/>'
        label_x = tl_x0 + timeline_w + 6
        label_y = tl_y0 + timeline_h / 2 + j * 0
        joint_paths += f'<text x="{label_x:.0f}" y="{tl_y0 + 8 + j * 14}" fill="{joint_colors[j]}" font-size="10">J{j+1}</text>'

    # Collision distance over time
    coll_pts = []
    for i in range(60):
        t = i / 59
        d = 0.35 + 0.25 * math.sin(2 * math.pi * 1.3 * t) + 0.1 * math.sin(2 * math.pi * 4 * t) + random.uniform(-0.02, 0.02)
        coll_pts.append(max(0.05, d))
    safe_thresh = 0.20
    coll_svg_w, coll_svg_h = 560, 80
    coll_path_pts = []
    for i, d in enumerate(coll_pts):
        px = 30 + i / 59 * coll_svg_w
        py = 10 + (1.0 - d / 0.70) * (coll_svg_h - 20)
        coll_path_pts.append(f"{px:.1f},{py:.1f}")
    coll_path = "M " + " L ".join(coll_path_pts)
    thresh_y = 10 + (1.0 - safe_thresh / 0.70) * (coll_svg_h - 20)

    # Stats
    avg_occ = sum(cells) / len(cells)
    max_occ = max(cells)
    hotspot_count = sum(1 for v in cells if v > 0.6)
    avg_reach = 100 + 10 * math.pi  # rough avg arc
    min_clearance = min(coll_pts)

    return f"""<!DOCTYPE html><html><head><title>Workspace Mapping Service</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
.subtitle{{color:#64748b;font-size:0.85rem;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}
.card{{background:#1e293b;padding:20px;border-radius:10px;border:1px solid #334155}}
h2{{color:#38bdf8;margin:0 0 12px 0;font-size:1rem;text-transform:uppercase;letter-spacing:0.05em}}
.stat-row{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:14px}}
.stat{{background:#0f172a;border-radius:8px;padding:10px 16px;min-width:120px}}
.stat-val{{font-size:1.5rem;font-weight:700;color:#C74634}}
.stat-lbl{{font-size:0.75rem;color:#64748b;margin-top:2px}}
svg{{display:block;overflow:visible}}
.badge{{display:inline-block;background:#C74634;color:#fff;border-radius:4px;padding:2px 8px;font-size:0.75rem;margin-left:8px}}
</style></head>
<body>
<h1>Workspace Mapping Service <span class="badge">PORT {PORT}</span></h1>
<div class="subtitle">Robot workspace occupancy, reachability envelope &amp; joint kinematics — OCI Robot Cloud</div>

<div class="stat-row">
  <div class="stat"><div class="stat-val">{avg_occ*100:.1f}%</div><div class="stat-lbl">Avg Occupancy</div></div>
  <div class="stat"><div class="stat-val">{max_occ*100:.0f}%</div><div class="stat-lbl">Peak Cell</div></div>
  <div class="stat"><div class="stat-val">{hotspot_count}</div><div class="stat-lbl">Hotspot Cells (&gt;60%)</div></div>
  <div class="stat"><div class="stat-val">{avg_reach:.0f}mm</div><div class="stat-lbl">Avg Reach Radius</div></div>
  <div class="stat"><div class="stat-val">{min_clearance*100:.1f}cm</div><div class="stat-lbl">Min Clearance</div></div>
</div>

<div class="grid">
  <div class="card" style="grid-column:span 2">
    <h2>Workspace Occupancy Heatmap ({cols}&times;{rows} Grid)</h2>
    <svg width="{svg_w}" height="{svg_h}">
      {grid_rects}
      {arc_lines}
      <!-- axis labels -->
      {''.join(f'<text x="{40 + c * cell_w + cell_w//2}" y="22" fill="#64748b" font-size="10" text-anchor="middle">{c}</text>' for c in range(cols))}
      {''.join(f'<text x="18" y="{30 + r * cell_h + cell_h//2 + 4}" fill="#64748b" font-size="10" text-anchor="middle">{r}</text>' for r in range(rows))}
      <text x="{svg_w//2}" y="{svg_h - 6}" fill="#94a3b8" font-size="11" text-anchor="middle">Column (0.5m per cell)</text>
      <text x="10" y="{svg_h//2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90 10 {svg_h//2})">Row</text>
      <!-- legend -->
      <defs><linearGradient id="lg" x1="0" x2="1" y1="0" y2="0">
        <stop offset="0%" stop-color="rgb(15,23,100)"/>
        <stop offset="50%" stop-color="rgb(45,170,100)"/>
        <stop offset="100%" stop-color="rgb(199,70,52)"/>
      </linearGradient></defs>
      <rect x="{svg_w - 130}" y="8" width="120" height="12" fill="url(#lg)" rx="3"/>
      <text x="{svg_w - 130}" y="32" fill="#64748b" font-size="9">0%</text>
      <text x="{svg_w - 20}" y="32" fill="#64748b" font-size="9" text-anchor="end">100%</text>
    </svg>
  </div>

  <div class="card" style="grid-column:span 2">
    <h2>Joint Angle Trajectories (6-DOF, Last 5s)</h2>
    <svg width="{timeline_w + 80}" height="{timeline_h + 60}">
      <rect x="30" y="20" width="{timeline_w}" height="{timeline_h}" fill="#0f172a" rx="4"/>
      <!-- grid lines -->
      {''.join(f'<line x1="30" y1="{20 + i * timeline_h // 4}" x2="{30 + timeline_w}" y2="{20 + i * timeline_h // 4}" stroke="#334155" stroke-width="0.5"/>' for i in range(5))}
      <line x1="30" y1="{20 + timeline_h // 2}" x2="{30 + timeline_w}" y2="{20 + timeline_h // 2}" stroke="#475569" stroke-width="1" stroke-dasharray="4,4"/>
      {joint_paths}
      <text x="{30 + timeline_w // 2}" y="{20 + timeline_h + 18}" fill="#64748b" font-size="11" text-anchor="middle">Time (0 → 5s)</text>
      <text x="14" y="{20 + timeline_h // 2 + 4}" fill="#64748b" font-size="10" text-anchor="middle" transform="rotate(-90 14 {20 + timeline_h // 2})">rad</text>
    </svg>
  </div>

  <div class="card" style="grid-column:span 2">
    <h2>Minimum Collision Clearance (m)</h2>
    <svg width="{coll_svg_w + 80}" height="{coll_svg_h + 40}">
      <rect x="30" y="10" width="{coll_svg_w}" height="{coll_svg_h}" fill="#0f172a" rx="4"/>
      <!-- safe threshold line -->
      <line x1="30" y1="{thresh_y:.1f}" x2="{30 + coll_svg_w}" y2="{thresh_y:.1f}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="6,3"/>
      <text x="{30 + coll_svg_w + 4}" y="{thresh_y + 4:.1f}" fill="#f59e0b" font-size="10">safe</text>
      <!-- fill area below threshold = danger -->
      <path d="{coll_path} L {30 + coll_svg_w:.1f},{coll_svg_h + 10} L 30,{coll_svg_h + 10} Z" fill="#C74634" opacity="0.08"/>
      <path d="{coll_path}" fill="none" stroke="#34d399" stroke-width="2"/>
      <text x="{30 + coll_svg_w // 2}" y="{coll_svg_h + 30}" fill="#64748b" font-size="11" text-anchor="middle">Time steps</text>
    </svg>
  </div>
</div>

<div style="color:#475569;font-size:0.75rem;margin-top:20px">
  OCI Robot Cloud · Workspace Mapping Service · port {PORT} · 2026
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Workspace Mapping Service")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

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

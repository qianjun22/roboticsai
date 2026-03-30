"""
oci_networking_dashboard.py — port 8649
OCI Robot Cloud | cycle-147B
Inter-region networking: Sankey bandwidth, latency heatmap, packet loss trend.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def svg_sankey_bandwidth() -> str:
    """Bidirectional Sankey-style bandwidth diagram for 3 OCI regions."""
    W, H = 520, 320
    # Node positions (cx, cy)
    nodes = {
        "Ashburn":   (130, 160),
        "Phoenix":   (390, 80),
        "Frankfurt": (390, 240),
    }
    # Links: (from, to, gbps)
    links = [
        ("Ashburn", "Phoenix",   4.2),
        ("Ashburn", "Frankfurt", 2.8),
        ("Phoenix", "Frankfurt", 1.4),
    ]
    max_gbps = 4.2
    max_width = 22

    def node_color(name):
        return {"Ashburn": "#38bdf8", "Phoenix": "#C74634", "Frankfurt": "#a855f7"}[name]

    # Build arrow paths (bidirectional = two offset parallel lines)
    arrows = ""
    labels = ""
    for src, dst, gbps in links:
        sx, sy = nodes[src]
        dx, dy = nodes[dst]
        w = max(3, int(max_width * gbps / max_gbps))
        # perpendicular offset for bidirectional separation
        dx_vec = dx - sx
        dy_vec = dy - sy
        length = math.sqrt(dx_vec ** 2 + dy_vec ** 2)
        px = -dy_vec / length * (w / 2 + 2)
        py = dx_vec / length * (w / 2 + 2)

        # forward arrow (src→dst)
        arrows += (
            f'<line x1="{sx + px:.1f}" y1="{sy + py:.1f}" '
            f'x2="{dx + px:.1f}" y2="{dy + py:.1f}" '
            f'stroke="{node_color(src)}" stroke-width="{w}" stroke-opacity="0.75" '
            f'stroke-linecap="round"/>'
        )
        # reverse arrow (dst→src)
        arrows += (
            f'<line x1="{dx - px:.1f}" y1="{dy - py:.1f}" '
            f'x2="{sx - px:.1f}" y2="{sy - py:.1f}" '
            f'stroke="{node_color(dst)}" stroke-width="{w}" stroke-opacity="0.75" '
            f'stroke-linecap="round"/>'
        )
        # bandwidth label at midpoint
        mx = (sx + dx) / 2
        my = (sy + dy) / 2
        labels += (
            f'<rect x="{mx - 22:.1f}" y="{my - 10:.1f}" width="44" height="18" '
            f'rx="4" fill="#0f172a" fill-opacity="0.85"/>'
            f'<text x="{mx:.1f}" y="{my + 4:.1f}" fill="#facc15" font-size="11" '
            f'font-weight="600" text-anchor="middle">{gbps}G</text>'
        )

    # Nodes
    node_svg = ""
    for name, (cx, cy) in nodes.items():
        col = node_color(name)
        node_svg += (
            f'<circle cx="{cx}" cy="{cy}" r="34" fill="#1e293b" stroke="{col}" stroke-width="2.5"/>'
            f'<text x="{cx}" y="{cy + 4}" fill="{col}" font-size="12" font-weight="700" '
            f'text-anchor="middle">{name}</text>'
        )

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
        style="background:#1e293b;border-radius:8px;width:100%;max-width:{W}px">
  <text x="{W//2}" y="20" fill="#e2e8f0" font-size="13" font-weight="600"
    text-anchor="middle">Inter-Region Bandwidth (bidirectional)</text>
  {arrows}
  {labels}
  {node_svg}
  <!-- legend -->
  <rect x="10" y="{H-42}" width="12" height="12" rx="2" fill="#38bdf8" fill-opacity="0.75"/>
  <text x="26" y="{H-32}" fill="#94a3b8" font-size="10">Ashburn origin</text>
  <rect x="10" y="{H-26}" width="12" height="12" rx="2" fill="#C74634" fill-opacity="0.75"/>
  <text x="26" y="{H-16}" fill="#94a3b8" font-size="10">Phoenix origin</text>
  <rect x="110" y="{H-42}" width="12" height="12" rx="2" fill="#a855f7" fill-opacity="0.75"/>
  <text x="126" y="{H-32}" fill="#94a3b8" font-size="10">Frankfurt origin</text>
  <text x="{W-10}" y="{H-16}" fill="#64748b" font-size="9" text-anchor="end">Arrow thickness ∝ bandwidth</text>
</svg>"""


def svg_latency_heatmap() -> str:
    """3×3 latency matrix heatmap with p50/p90/p99."""
    W, H = 520, 260
    regions = ["Ashburn", "Phoenix", "Frankfurt"]
    # [row][col] = (p50, p90, p99)  — diagonal = local
    data = [
        # Ashburn row
        [("0ms", "0ms", "0ms"),   ("22ms", "27ms", "34ms"), ("72ms", "81ms", "98ms")],
        # Phoenix row
        [("22ms", "27ms", "34ms"), ("0ms", "0ms", "0ms"),   ("95ms", "108ms", "121ms")],
        # Frankfurt row
        [("72ms", "81ms", "98ms"), ("95ms", "108ms", "121ms"), ("0ms", "0ms", "0ms")],
    ]
    # SLA amber check: p99 >= 95ms
    def cell_color(p50, p90, p99):
        if p99 == "0ms":
            return "#0f172a"   # diagonal
        val = int(p99.replace("ms", ""))
        if val >= 95:
            return "#78350f"   # amber/warning
        return "#1e3a5f"       # normal blue

    col_w = (W - 120) // 3
    row_h = (H - 70) // 3
    pad_l = 110
    pad_t = 50

    cells = ""
    for ri, row in enumerate(data):
        for ci, (p50, p90, p99) in enumerate(row):
            x = pad_l + ci * col_w
            y = pad_t + ri * row_h
            bg = cell_color(p50, p90, p99)
            amber = p99 != "0ms" and int(p99.replace("ms", "")) >= 95
            border = "#f59e0b" if amber else "#334155"
            cells += (
                f'<rect x="{x}" y="{y}" width="{col_w}" height="{row_h}" '
                f'fill="{bg}" stroke="{border}" stroke-width="{2 if amber else 1}"/>'
            )
            if p99 == "0ms":
                cells += (
                    f'<text x="{x + col_w//2}" y="{y + row_h//2 + 4}" '
                    f'fill="#334155" font-size="11" text-anchor="middle">—</text>'
                )
            else:
                cells += (
                    f'<text x="{x + col_w//2}" y="{y + 16}" fill="#94a3b8" font-size="9" text-anchor="middle">p50 {p50}</text>'
                    f'<text x="{x + col_w//2}" y="{y + 28}" fill="#94a3b8" font-size="9" text-anchor="middle">p90 {p90}</text>'
                    f'<text x="{x + col_w//2}" y="{y + 42}" fill="{"#fbbf24" if amber else "#e2e8f0"}" '
                    f'font-size="10" font-weight="700" text-anchor="middle">p99 {p99}</text>'
                )
                if amber:
                    cells += (
                        f'<text x="{x + col_w//2}" y="{y + 56}" fill="#f59e0b" font-size="9" '
                        f'text-anchor="middle">⚠ near SLA</text>'
                    )

    # Column headers
    headers = ""
    for ci, name in enumerate(regions):
        x = pad_l + ci * col_w + col_w // 2
        headers += (
            f'<text x="{x}" y="40" fill="#38bdf8" font-size="11" font-weight="600" text-anchor="middle">{name}</text>'
        )
    # Row headers
    row_headers = ""
    for ri, name in enumerate(regions):
        y = pad_t + ri * row_h + row_h // 2 + 4
        row_headers += (
            f'<text x="{pad_l - 6}" y="{y}" fill="#38bdf8" font-size="11" font-weight="600" text-anchor="end">{name}</text>'
        )

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
        style="background:#1e293b;border-radius:8px;width:100%;max-width:{W}px">
  <text x="{W//2}" y="18" fill="#e2e8f0" font-size="13" font-weight="600" text-anchor="middle">Latency Matrix (p50 / p90 / p99)</text>
  {headers}
  {row_headers}
  {cells}
  <rect x="10" y="{H-22}" width="12" height="12" rx="2" fill="#78350f" stroke="#f59e0b" stroke-width="1.5"/>
  <text x="26" y="{H-12}" fill="#f59e0b" font-size="10">p99 ≥ 95ms — near SLA (100ms target)</text>
</svg>"""


def svg_packet_loss() -> str:
    """30-day packet loss trend for 3 regions, all below 0.003% target."""
    W, H = 520, 300
    pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 45

    days = list(range(1, 31))
    import math as _m

    def loss_series(seed, noise_amp, base):
        _m.sin  # ensure imported
        return [
            max(0.0, base + noise_amp * _m.sin(d * seed + seed) + 0.0003 * _m.cos(d * 2.3 * seed))
            for d in days
        ]

    series = {
        "Ashburn":   (loss_series(1.1, 0.0004, 0.0010), "#38bdf8"),
        "Phoenix":   (loss_series(2.3, 0.0003, 0.0008), "#C74634"),
        "Frankfurt": (loss_series(0.7, 0.0005, 0.0015), "#a855f7"),
    }
    max_val = 0.0040

    def px(d):
        return pad_l + ((d - 1) / 29) * (W - pad_l - pad_r)

    def py(v):
        return pad_t + (1 - v / max_val) * (H - pad_t - pad_b)

    y_target = py(0.003)
    target_line = (
        f'<line x1="{pad_l}" y1="{y_target:.1f}" x2="{W - pad_r}" y2="{y_target:.1f}" '
        f'stroke="#facc15" stroke-width="1.5" stroke-dasharray="6,4"/>'
        f'<text x="{W - pad_r - 4}" y="{y_target - 5:.1f}" fill="#facc15" font-size="10" text-anchor="end">0.003% SLA</text>'
    )

    y_ticks = ""
    for v in [0.000, 0.001, 0.002, 0.003, 0.004]:
        yp = py(v)
        y_ticks += (
            f'<line x1="{pad_l - 4}" y1="{yp:.1f}" x2="{pad_l}" y2="{yp:.1f}" '
            f'stroke="#94a3b8" stroke-width="1"/>'
            f'<text x="{pad_l - 6}" y="{yp + 4:.1f}" fill="#94a3b8" font-size="9" '
            f'text-anchor="end">{v:.3f}%</text>'
        )
    x_ticks = ""
    for d in [1, 5, 10, 15, 20, 25, 30]:
        xp = px(d)
        x_ticks += (
            f'<line x1="{xp:.1f}" y1="{H - pad_b}" x2="{xp:.1f}" y2="{H - pad_b + 4}" '
            f'stroke="#94a3b8" stroke-width="1"/>'
            f'<text x="{xp:.1f}" y="{H - pad_b + 15}" fill="#94a3b8" font-size="10" '
            f'text-anchor="middle">D{d}</text>'
        )

    lines_svg = ""
    legend = ""
    lx = pad_l
    for name, (vals, color) in series.items():
        pts = " ".join(f"{px(d):.1f},{py(v):.1f}" for d, v in zip(days, vals))
        lines_svg += (
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>'
        )
        legend += (
            f'<line x1="{lx}" y1="{H - 10}" x2="{lx + 18}" y2="{H - 10}" '
            f'stroke="{color}" stroke-width="2"/>'
            f'<text x="{lx + 22}" y="{H - 6}" fill="#94a3b8" font-size="10">{name}</text>'
        )
        lx += 110

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
        style="background:#1e293b;border-radius:8px;width:100%;max-width:{W}px">
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{H-pad_b}" stroke="#475569" stroke-width="1"/>
  <line x1="{pad_l}" y1="{H-pad_b}" x2="{W-pad_r}" y2="{H-pad_b}" stroke="#475569" stroke-width="1"/>
  {y_ticks}
  {x_ticks}
  {target_line}
  {lines_svg}
  {legend}
  <text x="{(pad_l + W - pad_r)//2}" y="14" fill="#e2e8f0" font-size="13" font-weight="600"
    text-anchor="middle">Packet Loss — 30-Day Trend</text>
  <text x="{(pad_l + W - pad_r)//2}" y="{H - 25}" fill="#94a3b8" font-size="11" text-anchor="middle">Day</text>
  <text x="12" y="{(pad_t + H - pad_b)//2}" fill="#94a3b8" font-size="11" text-anchor="middle"
    transform="rotate(-90,12,{(pad_t + H - pad_b)//2})">Loss (%)</text>
</svg>"""


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    svg1 = svg_sankey_bandwidth()
    svg2 = svg_latency_heatmap()
    svg3 = svg_packet_loss()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>OCI Networking Dashboard — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;padding:24px}}
  h1{{color:#38bdf8;font-size:1.6rem;font-weight:700;margin-bottom:4px}}
  .subtitle{{color:#94a3b8;font-size:.875rem;margin-bottom:24px}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px;margin-bottom:28px}}
  .card{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px}}
  .card h2{{color:#38bdf8;font-size:1rem;font-weight:600;margin-bottom:14px}}
  .metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}}
  .metric{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px}}
  .metric .label{{color:#94a3b8;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}}
  .metric .value{{color:#C74634;font-size:1.4rem;font-weight:700}}
  .metric .value.amber{{color:#f59e0b}}
  .metric .sub{{color:#64748b;font-size:.75rem;margin-top:4px}}
  footer{{color:#475569;font-size:.75rem;margin-top:28px;text-align:center}}
  .badge{{display:inline-block;background:#C74634;color:#fff;font-size:.7rem;font-weight:700;
          padding:2px 8px;border-radius:999px;margin-left:8px;vertical-align:middle}}
</style>
</head>
<body>
<h1>OCI Networking Dashboard <span class="badge">Port 8649</span></h1>
<p class="subtitle">OCI Robot Cloud · Inter-Region Bandwidth · Latency Matrix · Packet Loss</p>

<div class="grid">
  <div class="card"><h2>Inter-Region Bandwidth (Sankey)</h2>{svg1}</div>
  <div class="card"><h2>Latency Matrix Heatmap</h2>{svg2}</div>
  <div class="card"><h2>Packet Loss — 30-Day Trend</h2>{svg3}</div>
</div>

<div class="metrics">
  <div class="metric">
    <div class="label">Ashburn ↔ Phoenix</div>
    <div class="value">4.2 Gbps</div>
    <div class="sub">28ms p50 latency</div>
  </div>
  <div class="metric">
    <div class="label">Ashburn ↔ Frankfurt</div>
    <div class="value">2.8 Gbps</div>
    <div class="sub">72ms p50 latency</div>
  </div>
  <div class="metric">
    <div class="label">Phoenix ↔ Frankfurt</div>
    <div class="value">1.4 Gbps</div>
    <div class="sub">95ms p50 latency</div>
  </div>
  <div class="metric">
    <div class="label">Frankfurt p99 Latency</div>
    <div class="value amber">98ms</div>
    <div class="sub">⚠ SLA target 100ms</div>
  </div>
  <div class="metric">
    <div class="label">SD-WAN Savings</div>
    <div class="value">-12ms</div>
    <div class="sub">Frankfurt path optimization</div>
  </div>
  <div class="metric">
    <div class="label">Avg Packet Loss</div>
    <div class="value">0.002%</div>
    <div class="sub">All regions below 0.003% SLA</div>
  </div>
</div>

<footer>OCI Robot Cloud · cycle-147B · oci_networking_dashboard · port 8649</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="OCI Networking Dashboard", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "oci_networking_dashboard", "port": 8649})

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8649)

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "oci_networking_dashboard", "port": 8649}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", 8649), Handler)
        print("Serving on port 8649")
        server.serve_forever()

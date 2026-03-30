"""Temporal Attention Visualizer — FastAPI port 8760"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8760

def build_html():
    random.seed(42)
    # Generate attention weights across 16 timesteps x 8 heads
    T = 16
    H = 8
    attn = [[round(abs(math.sin(t * 0.7 + h * 1.3) * math.cos(h * 0.4 + t * 0.2)) + random.uniform(0, 0.15), 3)
             for h in range(H)] for t in range(T)]
    # Normalize each row to sum to 1
    for t in range(T):
        row_sum = sum(attn[t])
        attn[t] = [round(v / row_sum, 3) for v in attn[t]]

    # Build SVG heatmap (T rows x H cols)
    cell_w, cell_h = 50, 28
    svg_w = H * cell_w + 60
    svg_h = T * cell_h + 50
    heatmap_cells = []
    for t in range(T):
        for h in range(H):
            val = attn[t][h]
            # Map 0..0.25 -> blue(30) to red(220) hue
            intensity = min(int(val * 1020), 255)
            r = intensity
            g = max(0, 120 - intensity // 2)
            b = max(0, 200 - intensity)
            x = 50 + h * cell_w
            y = 20 + t * cell_h
            heatmap_cells.append(
                f'<rect x="{x}" y="{y}" width="{cell_w-2}" height="{cell_h-2}" '
                f'fill="rgb({r},{g},{b})" opacity="0.85" rx="2"/>'
            )
            if val > 0.16:
                heatmap_cells.append(
                    f'<text x="{x+cell_w//2}" y="{y+cell_h//2+4}" text-anchor="middle" '
                    f'font-size="9" fill="#fff">{val:.2f}</text>'
                )
    # Head labels
    head_labels = ''.join(
        f'<text x="{50 + h*cell_w + cell_w//2}" y="15" text-anchor="middle" font-size="10" fill="#94a3b8">H{h+1}</text>'
        for h in range(H)
    )
    # Timestep labels
    ts_labels = ''.join(
        f'<text x="45" y="{20 + t*cell_h + cell_h//2 + 4}" text-anchor="end" font-size="9" fill="#64748b">t{t}</text>'
        for t in range(T)
    )

    # Entropy per timestep (attention diversity metric)
    entropies = []
    for t in range(T):
        ent = -sum(v * math.log(v + 1e-9) for v in attn[t])
        entropies.append(round(ent, 3))
    max_ent = max(entropies)
    ent_svg_w, ent_svg_h = 420, 100
    ent_points = [
        f"{30 + i * (ent_svg_w - 40) // (T-1)},{ent_svg_h - 15 - int((entropies[i]/max_ent) * (ent_svg_h - 30))}"
        for i in range(T)
    ]
    ent_polyline = ' '.join(ent_points)
    ent_area = f'M {ent_points[0]} ' + ' '.join(f'L {p}' for p in ent_points[1:]) + f' L {30 + (T-1)*(ent_svg_w-40)//(T-1)},{ent_svg_h-15} L 30,{ent_svg_h-15} Z'

    # Policy action prediction confidence over time
    conf = [round(0.55 + 0.35 * abs(math.sin(t * 0.45 + 0.8)) + random.uniform(-0.05, 0.05), 3) for t in range(T)]
    conf_points = [
        f"{30 + i*(ent_svg_w-40)//(T-1)},{ent_svg_h - 15 - int(conf[i]*(ent_svg_h-30))}"
        for i in range(T)
    ]
    conf_polyline = ' '.join(conf_points)

    rows = ''.join(
        f'<tr><td style="color:#94a3b8">t{t}</td>'
        f'<td style="color:#38bdf8">{entropies[t]:.3f}</td>'
        f'<td style="color:#4ade80">{conf[t]:.3f}</td>'
        f'<td style="background:linear-gradient(90deg,#C74634 {int(max(attn[t])*100)}%,#1e293b 0%);padding-left:6px;border-radius:3px">{max(attn[t]):.3f}</td>'
        f'</tr>'
        for t in range(T)
    )

    return f"""<!DOCTYPE html><html><head><title>Temporal Attention Visualizer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:1rem;margin:16px 0 8px}}
.card{{background:#1e293b;padding:20px;margin:12px 0;border-radius:10px;border:1px solid #334155}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
table{{border-collapse:collapse;width:100%;font-size:0.82rem}}
th{{color:#64748b;font-weight:600;padding:6px 10px;border-bottom:1px solid #334155;text-align:left}}
td{{padding:5px 10px;border-bottom:1px solid #1e293b}}
.badge{{display:inline-block;background:#0f172a;border:1px solid #334155;border-radius:4px;padding:2px 8px;font-size:0.75rem;color:#94a3b8;margin:2px}}
.stat{{font-size:1.8rem;font-weight:700;color:#C74634}}
.sub{{font-size:0.78rem;color:#64748b;margin-top:2px}}
</style></head>
<body>
<h1>Temporal Attention Visualizer</h1>
<p style="color:#64748b;margin:0">GR00T N1.6 — Action Chunk Decoder | Policy: PickAndPlace_v3 | Port {PORT}</p>

<div class="grid">
  <div class="card">
    <h2>Summary Statistics</h2>
    <div style="display:flex;gap:24px;flex-wrap:wrap">
      <div><div class="stat">{T}</div><div class="sub">Timesteps</div></div>
      <div><div class="stat">{H}</div><div class="sub">Attention Heads</div></div>
      <div><div class="stat">{round(sum(entropies)/T,3)}</div><div class="sub">Avg Entropy</div></div>
      <div><div class="stat">{round(sum(conf)/T,3)}</div><div class="sub">Avg Confidence</div></div>
    </div>
    <div style="margin-top:12px">
      {''.join(f'<span class="badge">Head {h+1}: {round(sum(attn[t][h] for t in range(T))/T,3)}</span>' for h in range(H))}
    </div>
  </div>
  <div class="card">
    <h2>Entropy &amp; Confidence Over Time</h2>
    <svg width="{ent_svg_w}" height="{ent_svg_h}" style="display:block">
      <defs>
        <linearGradient id="eg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4"/>
          <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.02"/>
        </linearGradient>
      </defs>
      <path d="{ent_area}" fill="url(#eg)"/>
      <polyline points="{ent_polyline}" fill="none" stroke="#38bdf8" stroke-width="2"/>
      <polyline points="{conf_polyline}" fill="none" stroke="#4ade80" stroke-width="1.5" stroke-dasharray="4,3"/>
      <text x="{ent_svg_w-80}" y="20" font-size="10" fill="#38bdf8">— Entropy</text>
      <text x="{ent_svg_w-80}" y="34" font-size="10" fill="#4ade80">-- Confidence</text>
      <line x1="30" y1="{ent_svg_h-15}" x2="{ent_svg_w-10}" y2="{ent_svg_h-15}" stroke="#334155" stroke-width="1"/>
    </svg>
  </div>
</div>

<div class="card">
  <h2>Attention Weight Heatmap — {T} Timesteps × {H} Heads</h2>
  <svg width="{svg_w}" height="{svg_h}" style="display:block;overflow:visible">
    {head_labels}
    {ts_labels}
    {''.join(heatmap_cells)}
  </svg>
  <div style="margin-top:8px;font-size:0.75rem;color:#64748b">
    Color intensity = attention weight magnitude. Highlighted cells exceed mean threshold (0.16).
  </div>
</div>

<div class="card">
  <h2>Per-Timestep Detail</h2>
  <table>
    <tr><th>Step</th><th>Entropy</th><th>Action Conf</th><th>Peak Head Weight</th></tr>
    {rows}
  </table>
</div>

<div style="color:#475569;font-size:0.72rem;margin-top:16px">
  Model: GR00T N1.6 &nbsp;|&nbsp; Checkpoint: step_5000 &nbsp;|&nbsp; Task: cube_lift_v2 &nbsp;|&nbsp; Device: A100 80GB
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Temporal Attention Visualizer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/api/attention")
    def attention_data():
        random.seed(42)
        T, H = 16, 8
        attn = [[round(abs(math.sin(t * 0.7 + h * 1.3) * math.cos(h * 0.4 + t * 0.2)) + random.uniform(0, 0.15), 3)
                 for h in range(H)] for t in range(T)]
        for t in range(T):
            row_sum = sum(attn[t])
            attn[t] = [round(v / row_sum, 3) for v in attn[t]]
        return {"timesteps": T, "heads": H, "attention": attn}

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

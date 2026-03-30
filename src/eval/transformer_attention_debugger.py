"""Transformer Attention Debugger — FastAPI port 8800"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8800

# Reproducible seed for consistent demo data
random.seed(42)

def _attention_matrix(n=8):
    """Simulate softmax attention weights for an n-head, n-token scenario."""
    rows = []
    for i in range(n):
        raw = [math.exp(random.gauss(0, 1)) for _ in range(n)]
        total = sum(raw)
        rows.append([v / total for v in raw])
    return rows

def _entropy(row):
    return -sum(p * math.log(p + 1e-9) for p in row)

def _build_heatmap_svg(matrix, size=240):
    n = len(matrix)
    cell = size // n
    rects = []
    for i, row in enumerate(matrix):
        for j, val in enumerate(row):
            intensity = int(val * 255)
            r = intensity
            g = max(0, 180 - intensity)
            b = 200
            x, y = j * cell, i * cell
            rects.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'fill="rgb({r},{g},{b})" opacity="0.85">'
                f'<title>head[{i}][{j}]={val:.3f}</title></rect>'
            )
    return (
        f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(rects)
        + "</svg>"
    )

def _build_entropy_bar_svg(entropies, width=420, height=140):
    n = len(entropies)
    max_e = max(entropies) or 1
    bar_w = width // n - 4
    bars = []
    for i, e in enumerate(entropies):
        bh = int((e / max_e) * (height - 24))
        x = i * (bar_w + 4) + 2
        y = height - bh - 20
        hue = int(200 + i * 20)
        bars.append(
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" '
            f'fill="hsl({hue},70%,55%)" rx="3"/>'
            f'<text x="{x + bar_w//2}" y="{height - 4}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="9">H{i}</text>'
            f'<text x="{x + bar_w//2}" y="{y - 3}" text-anchor="middle" '
            f'fill="#e2e8f0" font-size="8">{e:.2f}</text>'
        )
    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{width}" height="{height}" fill="#0f172a" rx="6"/>'
        + "".join(bars)
        + "</svg>"
    )

def _build_loss_curve_svg(steps=40, width=420, height=140):
    # Simulated training loss with attention regularization term
    losses = []
    for t in range(steps):
        base = 2.5 * math.exp(-t * 0.08)
        noise = random.gauss(0, 0.04)
        losses.append(max(0.05, base + noise))
    max_l = max(losses)
    pts = []
    for i, l in enumerate(losses):
        x = int(i * (width - 20) / (steps - 1)) + 10
        y = int((1 - l / max_l) * (height - 30)) + 10
        pts.append((x, y))
    polyline = " ".join(f"{x},{y}" for x, y in pts)
    # Gradient fill
    fill_pts = f"10,{height - 20} " + polyline + f" {width - 10},{height - 20}"
    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        f'<defs><linearGradient id="lg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4"/>'
        f'<stop offset="100%" stop-color="#38bdf8" stop-opacity="0.02"/></linearGradient></defs>'
        f'<rect width="{width}" height="{height}" fill="#0f172a" rx="6"/>'
        f'<polygon points="{fill_pts}" fill="url(#lg)"/>'
        f'<polyline points="{polyline}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
        f'<text x="10" y="{height - 5}" fill="#64748b" font-size="9">Step 0</text>'
        f'<text x="{width - 40}" y="{height - 5}" fill="#64748b" font-size="9">Step {steps * 100}</text>'
        + "".join(
            f'<circle cx="{x}" cy="{y}" r="2" fill="#7dd3fc"/>'
            for x, y in pts[::5]
        )
        + "</svg>"
    )

def build_html():
    random.seed()
    num_heads = 8
    num_layers = 6
    tokens = ["[CLS]", "pick", "the", "cube", "from", "shelf", "[SEP]", "[PAD]"]

    matrices = [_attention_matrix(num_heads) for _ in range(num_layers)]
    entropies_per_layer = [[_entropy(row) for row in m] for m in matrices]
    mean_entropies = [sum(e) / len(e) for e in entropies_per_layer]

    # Layer 3 heatmap (most informative for demo)
    heatmap_svg = _build_heatmap_svg(matrices[3], size=256)
    entropy_svg = _build_entropy_bar_svg(entropies_per_layer[3])
    loss_svg = _build_loss_curve_svg(steps=40)

    layer_rows = ""
    for i, me in enumerate(mean_entropies):
        bar_pct = int(me / math.log(num_heads) * 100)
        layer_rows += (
            f"<tr><td>Layer {i}</td>"
            f"<td><div style='background:#334155;border-radius:4px;height:12px;width:200px'>"
            f"<div style='background:#38bdf8;height:12px;width:{bar_pct}%;border-radius:4px'></div></div></td>"
            f"<td style='padding-left:8px'>{me:.3f}</td></tr>"
        )

    token_header = "".join(f"<th style='padding:4px 8px;color:#94a3b8'>{t}</th>" for t in tokens)
    attn_row = matrices[3][0]  # head-0 of layer-3
    attn_cells = "".join(
        f"<td style='padding:4px 8px;background:rgba(56,189,248,{v:.2f});border-radius:3px;text-align:center'>{v:.2f}</td>"
        for v in attn_row
    )

    stats = {
        "Model": "GR00T-N1.6 (6L, 8H, 512D)",
        "Sequence Length": str(num_heads),
        "Avg Entropy (L3)": f"{mean_entropies[3]:.3f} nats",
        "Sparsity (L3, H0)": f"{sum(1 for v in matrices[3][0] if v < 0.05)} / {num_heads} heads < 0.05",
        "Max Attention": f"{max(matrices[3][0]):.3f}",
        "Status": "<span style='color:#4ade80'>NOMINAL</span>",
    }
    stat_rows = "".join(
        f"<tr><td style='color:#94a3b8;padding:4px 12px 4px 0'>{k}</td>"
        f"<td style='font-weight:600'>{v}</td></tr>"
        for k, v in stats.items()
    )

    return f"""<!DOCTYPE html><html lang='en'><head>
<meta charset='UTF-8'/><title>Transformer Attention Debugger</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
  header{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:16px}}
  h1{{margin:0;font-size:1.4rem;color:#C74634;letter-spacing:.03em}}
  .badge{{background:#C74634;color:#fff;font-size:.7rem;padding:2px 8px;border-radius:12px;font-weight:700}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px;max-width:1100px;margin:auto}}
  .card{{background:#1e293b;padding:20px;border-radius:10px;border:1px solid #334155}}
  .full{{grid-column:1/-1}}
  h2{{margin:0 0 14px;font-size:1rem;color:#38bdf8}}
  h3{{margin:0 0 10px;font-size:.85rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
  table{{border-collapse:collapse;width:100%;font-size:.82rem}}
  .pill{{display:inline-block;background:#0f172a;border:1px solid #334155;border-radius:6px;padding:4px 10px;font-size:.78rem;color:#7dd3fc}}
</style></head><body>
<header>
  <h1>Transformer Attention Debugger</h1>
  <span class='badge'>Port {PORT}</span>
  <span style='margin-left:auto;font-size:.8rem;color:#64748b'>OCI Robot Cloud — Eval Suite</span>
</header>
<div class='grid'>
  <div class='card'>
    <h2>Layer 3 — Head Attention Heatmap</h2>
    <h3>Tokens: {' · '.join(tokens)}</h3>
    {heatmap_svg}
    <p style='font-size:.75rem;color:#64748b;margin-top:8px'>Rows = query positions, Cols = key positions. Darker blue = higher attention weight.</p>
  </div>
  <div class='card'>
    <h2>Model Statistics</h2>
    <table>{stat_rows}</table>
    <hr style='border-color:#334155;margin:14px 0'/>
    <h3>Layer 3 · Head 0 — Attention Distribution</h3>
    <table><tr>{token_header}</tr><tr>{attn_cells}</tr></table>
  </div>
  <div class='card'>
    <h2>Per-Head Entropy — Layer 3</h2>
    <p style='font-size:.75rem;color:#64748b;margin:0 0 10px'>Shannon entropy of attention distributions. Low = focused, High = diffuse.</p>
    {entropy_svg}
  </div>
  <div class='card'>
    <h2>Attention Loss Curve (Training)</h2>
    <p style='font-size:.75rem;color:#64748b;margin:0 0 10px'>Cross-entropy + attention entropy regularization over 4,000 steps.</p>
    {loss_svg}
  </div>
  <div class='card full'>
    <h2>Mean Head Entropy by Layer</h2>
    <p style='font-size:.75rem;color:#64748b;margin:0 0 12px'>Uniform max entropy = {math.log(num_heads):.3f} nats ({num_heads} heads)</p>
    <table>{layer_rows}</table>
    <div style='margin-top:14px;display:flex;gap:8px;flex-wrap:wrap'>
      <span class='pill'>6 Layers</span><span class='pill'>8 Heads</span>
      <span class='pill'>512 Hidden Dim</span><span class='pill'>Action Chunk = 16</span>
      <span class='pill'>Causal Mask</span><span class='pill'>RoPE Encoding</span>
    </div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Transformer Attention Debugger")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "transformer_attention_debugger"}

    @app.get("/attention/{layer}")
    def get_attention(layer: int = 3):
        m = _attention_matrix(8)
        return {"layer": layer, "matrix": m, "entropy": [_entropy(r) for r in m]}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a):
        pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"Serving transformer_attention_debugger on http://0.0.0.0:{PORT}")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

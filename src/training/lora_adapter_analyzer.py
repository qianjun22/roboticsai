# LoRA Adapter Analyzer — port 8620
# OCI Robot Cloud | cycle-140B

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8620


def build_html() -> str:
    # --- SVG 1: LoRA weight delta per layer bar chart ---
    layers = [
        ("L1",  "tokenizer",   0.12),
        ("L2",  "tokenizer",   0.15),
        ("L3",  "attention",   0.28),
        ("L4",  "attention",   0.33),
        ("L5",  "attention",   0.37),
        ("L6",  "ffn",         0.42),
        ("L7",  "ffn",         0.48),
        ("L8",  "ffn",         0.51),
        ("L9",  "attention",   0.55),
        ("L10", "attention",   0.61),
        ("L11", "ffn",         0.72),
        ("L12", "action_head", 0.89),
    ]
    type_colors = {
        "tokenizer":   "#6366f1",
        "attention":   "#38bdf8",
        "ffn":         "#34d399",
        "action_head": "#C74634",
    }
    bar_w = 38
    bar_gap = 10
    chart_h = 180
    chart_w = len(layers) * (bar_w + bar_gap) + 40
    bars_svg = ""
    for i, (lbl, ltype, val) in enumerate(layers):
        x = 30 + i * (bar_w + bar_gap)
        bh = int(val * chart_h)
        y = 10 + (chart_h - bh)
        color = type_colors[ltype]
        bars_svg += (
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" fill="{color}" rx="3"/>'
            f'<text x="{x + bar_w//2}" y="{y - 5}" text-anchor="middle" fill="#e2e8f0" font-size="10">{val:.2f}</text>'
            f'<text x="{x + bar_w//2}" y="{10 + chart_h + 14}" text-anchor="middle" fill="#94a3b8" font-size="10">{lbl}</text>'
        )
    legend_items = [("tokenizer", "#6366f1"), ("attention", "#38bdf8"), ("ffn", "#34d399"), ("action_head", "#C74634")]
    legend_svg = ""
    for li, (lt, lc) in enumerate(legend_items):
        lx = 30 + li * 120
        legend_svg += (
            f'<rect x="{lx}" y="220" width="12" height="12" fill="{lc}" rx="2"/>'
            f'<text x="{lx + 16}" y="231" fill="#94a3b8" font-size="11">{lt}</text>'
        )
    svg1 = f"""
    <svg width="{chart_w}" height="260" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">
      <text x="{chart_w//2}" y="28" text-anchor="middle" fill="#C74634" font-size="14" font-weight="bold">LoRA Weight Delta per Layer</text>
      {bars_svg}
      {legend_svg}
      <line x1="30" y1="{10 + chart_h}" x2="{chart_w - 10}" y2="{10 + chart_h}" stroke="#334155" stroke-width="1"/>
    </svg>
    """

    # --- SVG 2: LoRA vs full fine-tune convergence curves ---
    steps = list(range(0, 5001, 500))
    lora_loss  = [1.82, 1.41, 1.09, 0.87, 0.71, 0.60, 0.52, 0.46, 0.42, 0.39, 0.38]
    full_loss  = [1.82, 1.35, 1.01, 0.78, 0.62, 0.51, 0.44, 0.40, 0.37, 0.36, 0.36]
    def to_px(step, loss, W=440, H=160, pad=40):
        x = pad + (step / 5000) * (W - pad)
        y = pad + (1 - (loss - 0.3) / 1.6) * (H - pad)
        return x, y
    def polyline(vals, W=440, H=160, pad=40):
        pts = " ".join(f"{to_px(s, v)[0]:.1f},{to_px(s, v)[1]:.1f}" for s, v in zip(steps, vals))
        return pts
    svg2 = f"""
    <svg width="460" height="200" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">
      <text x="230" y="22" text-anchor="middle" fill="#C74634" font-size="14" font-weight="bold">LoRA vs Full Fine-Tune Convergence</text>
      <polyline points="{polyline(lora_loss)}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
      <polyline points="{polyline(full_loss)}" fill="none" stroke="#34d399" stroke-width="2.5" stroke-dasharray="6,3"/>
      <rect x="260" y="30" width="12" height="3" fill="#38bdf8"/>
      <text x="276" y="34" fill="#94a3b8" font-size="11">LoRA (rank-16)</text>
      <rect x="260" y="44" width="12" height="3" fill="#34d399"/>
      <text x="276" y="48" fill="#94a3b8" font-size="11">Full fine-tune</text>
      <text x="14" y="170" fill="#64748b" font-size="10">Loss</text>
      <text x="230" y="195" text-anchor="middle" fill="#64748b" font-size="10">Steps</text>
      <line x1="40" y1="40" x2="40" y2="170" stroke="#334155" stroke-width="1"/>
      <line x1="40" y1="170" x2="450" y2="170" stroke="#334155" stroke-width="1"/>
    </svg>
    """

    # --- SVG 3: Rank sweep Pareto scatter ---
    ranks = [1,  4,    8,    16,   32,   64  ]
    sr    = [71, 87.3, 94.1, 98.7, 99.2, 99.5]
    vram  = [4.1, 7.2, 11.8, 18.4, 28.9, 47.3]
    def scatter_pt(v, s, W=400, H=160, pad=40):
        x = pad + (v - 0) / 50 * (W - pad)
        y = pad + (1 - (s - 65) / 40) * (H - pad)
        return x, y
    dots = ""
    for i, (r, s, v) in enumerate(zip(ranks, sr, vram)):
        cx, cy = scatter_pt(v, s)
        color = "#C74634" if r == 16 else "#38bdf8"
        dots += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{color}" opacity="0.9"/>'
        dots += f'<text x="{cx + 9:.1f}" y="{cy + 4:.1f}" fill="#94a3b8" font-size="10">r={r}</text>'
    # circle Pareto frontier rank-16
    px16, py16 = scatter_pt(18.4, 98.7)
    dots += f'<circle cx="{px16:.1f}" cy="{py16:.1f}" r="11" fill="none" stroke="#C74634" stroke-width="2" stroke-dasharray="4,2"/>'
    svg3 = f"""
    <svg width="440" height="200" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">
      <text x="220" y="22" text-anchor="middle" fill="#C74634" font-size="14" font-weight="bold">Rank Sweep Pareto (SR vs VRAM)</text>
      {dots}
      <line x1="40" y1="40" x2="40" y2="170" stroke="#334155" stroke-width="1"/>
      <line x1="40" y1="170" x2="430" y2="170" stroke="#334155" stroke-width="1"/>
      <text x="220" y="195" text-anchor="middle" fill="#64748b" font-size="10">VRAM (GB)</text>
      <text x="10" y="110" fill="#64748b" font-size="10" transform="rotate(-90,10,110)">SR (%)</text>
      <text x="{px16 + 14:.1f}" y="{py16 - 14:.1f}" fill="#C74634" font-size="10" font-weight="bold">Pareto</text>
    </svg>
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>LoRA Adapter Analyzer | OCI Robot Cloud</title>
  <style>
    body {{ background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',Arial,sans-serif; margin:0; padding:24px; }}
    h1 {{ color:#C74634; font-size:1.7rem; margin-bottom:4px; }}
    h2 {{ color:#C74634; font-size:1.1rem; margin:18px 0 8px; }}
    .subtitle {{ color:#94a3b8; font-size:.95rem; margin-bottom:24px; }}
    .grid {{ display:flex; flex-wrap:wrap; gap:24px; margin-bottom:28px; }}
    .card {{ background:#1e293b; border-radius:10px; padding:20px; flex:1; min-width:280px; }}
    .metric-row {{ display:flex; gap:18px; flex-wrap:wrap; margin-bottom:24px; }}
    .metric {{ background:#1e293b; border-radius:8px; padding:14px 20px; min-width:180px; }}
    .metric .val {{ font-size:1.5rem; font-weight:700; color:#38bdf8; }}
    .metric .lbl {{ font-size:.82rem; color:#94a3b8; margin-top:2px; }}
    footer {{ color:#475569; font-size:.8rem; margin-top:32px; }}
  </style>
</head>
<body>
  <h1>LoRA Adapter Analyzer</h1>
  <div class="subtitle">OCI Robot Cloud &mdash; GR00T N1.6 | Port {PORT}</div>

  <div class="metric-row">
    <div class="metric"><div class="val">98.7%</div><div class="lbl">Rank-16 SR vs full fine-tune</div></div>
    <div class="metric"><div class="val">23%</div><div class="lbl">VRAM vs full fine-tune</div></div>
    <div class="metric"><div class="val">8.4 M</div><div class="lbl">Adapter params (0.28% of 3B)</div></div>
    <div class="metric"><div class="val">Rank-32+</div><div class="lbl">Diminishing returns above</div></div>
  </div>

  <h2>Weight Delta per Layer</h2>
  <div class="card">{svg1}</div>

  <div class="grid">
    <div>
      <h2>Convergence Curves</h2>
      <div class="card">{svg2}</div>
    </div>
    <div>
      <h2>Rank Sweep Pareto</h2>
      <div class="card">{svg3}</div>
    </div>
  </div>

  <footer>OCI Robot Cloud &bull; cycle-140B &bull; LoRA Adapter Analyzer &bull; port {PORT}</footer>
</body>
</html>"""
    return html


if USE_FASTAPI:
    app = FastAPI(title="LoRA Adapter Analyzer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "lora_adapter_analyzer", "port": PORT}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"lora_adapter_analyzer"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        print(f"[lora_adapter_analyzer] Serving on http://0.0.0.0:{PORT}")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

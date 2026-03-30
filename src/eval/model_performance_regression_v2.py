"""Model Performance Regression V2 — FastAPI port 8714"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8714

def build_html():
    random.seed(42)
    # Generate regression metric timeseries (30 checkpoints)
    checkpoints = list(range(0, 30))
    mae_values = [0.28 - 0.007 * i + 0.015 * math.sin(i * 0.8) + random.gauss(0, 0.005) for i in checkpoints]
    mae_values = [max(0.05, v) for v in mae_values]
    mse_values = [v ** 2 * 12 + random.gauss(0, 0.003) for v in mae_values]
    r2_values  = [min(0.999, 1.0 - v * 2.5 + random.gauss(0, 0.008)) for v in mae_values]

    # SVG line chart for MAE
    W, H = 560, 180
    pad = 40
    n = len(checkpoints)
    max_mae = max(mae_values) + 0.02
    min_mae = max(0, min(mae_values) - 0.01)

    def sx(i): return pad + (i / (n - 1)) * (W - 2 * pad)
    def sy(v): return H - pad - ((v - min_mae) / (max_mae - min_mae + 1e-9)) * (H - 2 * pad)

    polyline_pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(mae_values))
    baseline_y = sy(mae_values[0])

    # Threshold line at MAE=0.10
    thresh_y = sy(0.10)
    thresh_line = f'<line x1="{pad}" y1="{thresh_y:.1f}" x2="{W-pad}" y2="{thresh_y:.1f}" stroke="#f59e0b" stroke-dasharray="6,3" stroke-width="1.5"/>'
    thresh_label = f'<text x="{W-pad+4}" y="{thresh_y+4:.1f}" fill="#f59e0b" font-size="10">0.10</text>'

    # Dot for best checkpoint
    best_idx = mae_values.index(min(mae_values))
    best_dot = f'<circle cx="{sx(best_idx):.1f}" cy="{sy(mae_values[best_idx]):.1f}" r="5" fill="#22c55e" stroke="#0f172a" stroke-width="1.5"/>'

    # R2 bar chart
    bar_W, bar_H = 560, 140
    bar_pad = 40
    bar_w = (bar_W - 2 * bar_pad) / n - 2
    bars_svg = ""
    for i, v in enumerate(r2_values):
        bx = bar_pad + i * ((bar_W - 2 * bar_pad) / n)
        bh = max(2, v * (bar_H - 2 * bar_pad))
        by = bar_H - bar_pad - bh
        color = "#38bdf8" if i != best_idx else "#22c55e"
        bars_svg += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" rx="2"/>'

    # Summary stats
    latest_mae = mae_values[-1]
    best_mae   = mae_values[best_idx]
    avg_r2     = sum(r2_values) / len(r2_values)
    improvement_pct = (mae_values[0] - best_mae) / mae_values[0] * 100

    # Regression table rows
    table_rows = ""
    for i in range(0, n, 5):
        row_class = "best" if i == best_idx else ""
        table_rows += f"<tr class='{row_class}'><td>ckpt-{i:02d}</td><td>{mae_values[i]:.4f}</td><td>{mse_values[i]:.5f}</td><td>{r2_values[i]:.4f}</td></tr>\n"

    return f"""<!DOCTYPE html><html><head><title>Model Performance Regression V2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 4px;margin:0;font-size:1.6rem}}
.subtitle{{color:#94a3b8;padding:0 20px 16px;font-size:0.85rem}}
h2{{color:#38bdf8;margin:0 0 10px;font-size:1rem}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:0 20px 12px}}
.card{{background:#1e293b;padding:16px 20px;border-radius:8px}}
.stat{{font-size:1.8rem;font-weight:700;color:#f1f5f9}}
.stat-label{{font-size:0.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-top:2px}}
.good{{color:#22c55e}}.warn{{color:#f59e0b}}.neutral{{color:#38bdf8}}
.chart-card{{background:#1e293b;padding:16px 20px;margin:0 20px 12px;border-radius:8px}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{color:#64748b;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
td{{padding:5px 8px;border-bottom:1px solid #1e293b}}
tr.best td{{color:#22c55e;font-weight:600}}
.badge{{display:inline-block;padding:2px 8px;border-radius:9999px;font-size:0.7rem;font-weight:600;background:#14532d;color:#4ade80}}
</style></head>
<body>
<h1>Model Performance Regression V2</h1>
<div class="subtitle">Regression metrics across training checkpoints — port {PORT}</div>

<div class="grid">
  <div class="card"><div class="stat good">{best_mae:.4f}</div><div class="stat-label">Best MAE</div></div>
  <div class="card"><div class="stat {'warn' if latest_mae > 0.12 else 'good'}">{latest_mae:.4f}</div><div class="stat-label">Latest MAE</div></div>
  <div class="card"><div class="stat neutral">{avg_r2:.4f}</div><div class="stat-label">Avg R²</div></div>
  <div class="card"><div class="stat good">↓{improvement_pct:.1f}%</div><div class="stat-label">MAE Improvement</div></div>
</div>

<div class="chart-card">
  <h2>MAE over Checkpoints <span class="badge">Best: ckpt-{best_idx:02d}</span></h2>
  <svg width="100%" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
    <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{H-pad}" stroke="#334155" stroke-width="1"/>
    <line x1="{pad}" y1="{H-pad}" x2="{W-pad}" y2="{H-pad}" stroke="#334155" stroke-width="1"/>
    {thresh_line}
    {thresh_label}
    <polyline points="{polyline_pts}" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linejoin="round"/>
    {best_dot}
    <text x="4" y="{baseline_y:.1f}" fill="#64748b" font-size="9">{mae_values[0]:.3f}</text>
    <text x="{pad-4}" y="{H-pad+14}" fill="#64748b" font-size="9">0</text>
    <text x="{W-pad-8}" y="{H-pad+14}" fill="#64748b" font-size="9">{n-1}</text>
  </svg>
</div>

<div class="chart-card">
  <h2>R² Score per Checkpoint</h2>
  <svg width="100%" viewBox="0 0 {bar_W} {bar_H}" xmlns="http://www.w3.org/2000/svg">
    <line x1="{bar_pad}" y1="{bar_pad}" x2="{bar_pad}" y2="{bar_H-bar_pad}" stroke="#334155" stroke-width="1"/>
    <line x1="{bar_pad}" y1="{bar_H-bar_pad}" x2="{bar_W-bar_pad}" y2="{bar_H-bar_pad}" stroke="#334155" stroke-width="1"/>
    {bars_svg}
    <text x="4" y="{bar_pad+4}" fill="#64748b" font-size="9">1.0</text>
    <text x="4" y="{bar_H-bar_pad+4}" fill="#64748b" font-size="9">0.0</text>
  </svg>
</div>

<div class="chart-card">
  <h2>Checkpoint Regression Table</h2>
  <table>
    <thead><tr><th>Checkpoint</th><th>MAE</th><th>MSE</th><th>R²</th></tr></thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Model Performance Regression V2")
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

# Video Fine-Tuning Pipeline — port 8940
import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

if USE_FASTAPI:
    app = FastAPI(title="Video Fine-Tuning Pipeline")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(content=build_html())

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            html = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html)
        def log_message(self, *a):
            pass


# ── Data constants ──────────────────────────────────────────────────────────
DEMOS          = 847
STEPS          = 300
FPS            = 30
TOTAL_FRAMES   = DEMOS * STEPS * FPS          # 7 623 000
BYTES_PER_FRAME = 3 * 640 * 480               # ~921 600 B  (640×480 RGB)
TOTAL_TB       = TOTAL_FRAMES * BYTES_PER_FRAME / 1e12  # ≈ 2.5 TB

# Success-rate deltas (video vs image baseline)
TASKS = [
    {"name": "pour",       "image_sr": 61, "video_sr": 73},
    {"name": "fold",       "image_sr": 54, "video_sr": 63},
    {"name": "pick_place", "image_sr": 68, "video_sr": 75},
]

# Pipeline throughput (demos/min at each stage)
STAGES = [
    {"stage": "Ingest",    "dpm": 420},
    {"stage": "Encode",    "dpm": 310},
    {"stage": "Tokenize",  "dpm": 580},
    {"stage": "Fine-tune", "dpm": 94},
    {"stage": "Eval",      "dpm": 210},
]


def _sr_bar_chart() -> str:
    """SVG bar chart: image vs video success rate per task."""
    W, H = 520, 260
    bar_w = 44
    gap   = 12
    group_gap = 36
    x0, y0 = 60, 20
    max_sr = 100
    chart_h = H - 60

    def bar_height(sr):
        return round(chart_h * sr / max_sr, 1)

    rects = []
    labels = []
    x = x0
    for t in TASKS:
        bh_img = bar_height(t["image_sr"])
        bh_vid = bar_height(t["video_sr"])
        # image bar
        ry = y0 + chart_h - bh_img
        rects.append(f'<rect x="{x}" y="{ry:.1f}" width="{bar_w}" height="{bh_img:.1f}" fill="#38bdf8" rx="3"/>')
        rects.append(f'<text x="{x + bar_w//2}" y="{ry - 4:.1f}" text-anchor="middle" fill="#94a3b8" font-size="11">{t["image_sr"]}%</text>')
        # video bar
        x2 = x + bar_w + gap
        ry2 = y0 + chart_h - bh_vid
        rects.append(f'<rect x="{x2}" y="{ry2:.1f}" width="{bar_w}" height="{bh_vid:.1f}" fill="#C74634" rx="3"/>')
        rects.append(f'<text x="{x2 + bar_w//2}" y="{ry2 - 4:.1f}" text-anchor="middle" fill="#e2e8f0" font-size="11">{t["video_sr"]}%</text>')
        # task label
        cx = x + bar_w + gap // 2
        ly = y0 + chart_h + 16
        labels.append(f'<text x="{cx}" y="{ly}" text-anchor="middle" fill="#94a3b8" font-size="12">{t["name"]}</text>')
        x += 2 * bar_w + gap + group_gap

    # y-axis gridlines
    grids = []
    for pct in [0, 25, 50, 75, 100]:
        gy = y0 + chart_h - bar_height(pct)
        grids.append(f'<line x1="{x0 - 8}" y1="{gy:.1f}" x2="{x - group_gap + gap}" y2="{gy:.1f}" stroke="#334155" stroke-width="1"/>')
        grids.append(f'<text x="{x0 - 12}" y="{gy + 4:.1f}" text-anchor="end" fill="#64748b" font-size="10">{pct}</text>')

    # legend
    lx = x0
    ly = y0 + chart_h + 36
    legend = (
        f'<rect x="{lx}" y="{ly}" width="14" height="14" fill="#38bdf8" rx="2"/>'
        f'<text x="{lx+18}" y="{ly+11}" fill="#94a3b8" font-size="11">Image SR</text>'
        f'<rect x="{lx+100}" y="{ly}" width="14" height="14" fill="#C74634" rx="2"/>'
        f'<text x="{lx+118}" y="{ly+11}" fill="#94a3b8" font-size="11">Video SR</text>'
    )

    body = "\n".join(grids + rects + labels) + "\n" + legend
    return f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">{body}</svg>'


def _throughput_chart() -> str:
    """SVG horizontal bar chart: pipeline stage throughput (demos/min)."""
    W, H = 520, 220
    max_dpm = 600
    bar_h = 28
    gap   = 12
    x0, y0 = 100, 16
    chart_w = W - x0 - 20

    rects = []
    for i, s in enumerate(STAGES):
        bw = round(chart_w * s["dpm"] / max_dpm, 1)
        y  = y0 + i * (bar_h + gap)
        hue = int(200 + i * 18)  # blue-ish gradient via hsl
        rects.append(f'<rect x="{x0}" y="{y}" width="{bw}" height="{bar_h}" fill="hsl({hue},70%,55%)" rx="3"/>')
        rects.append(f'<text x="{x0 - 6}" y="{y + bar_h//2 + 4}" text-anchor="end" fill="#94a3b8" font-size="12">{s["stage"]}</text>')
        rects.append(f'<text x="{x0 + bw + 6}" y="{y + bar_h//2 + 4}" fill="#e2e8f0" font-size="11">{s["dpm"]} d/m</text>')

    return f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">{"\n".join(rects)}</svg>'


def build_html() -> str:
    sr_svg  = _sr_bar_chart()
    thr_svg = _throughput_chart()

    delta_rows = "".join(
        f'<tr><td style="padding:6px 12px;color:#e2e8f0">{t["name"]}</td>'
        f'<td style="padding:6px 12px;color:#38bdf8;text-align:center">{t["image_sr"]}%</td>'
        f'<td style="padding:6px 12px;color:#C74634;text-align:center">{t["video_sr"]}%</td>'
        f'<td style="padding:6px 12px;color:#4ade80;text-align:center">+{t["video_sr"]-t["image_sr"]}pp</td></tr>'
        for t in TASKS
    )

    total_frames_fmt = f"{TOTAL_FRAMES:,}"
    total_tb_fmt     = f"{TOTAL_TB:.1f} TB"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Video Fine-Tuning Pipeline</title>
<style>
  body{{margin:0;background:#0f172a;font-family:'Segoe UI',sans-serif;color:#e2e8f0}}
  h1{{color:#C74634;margin:0 0 4px}}
  h2{{color:#38bdf8;font-size:1rem;margin:24px 0 8px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:20px}}
  .stat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:20px}}
  .stat{{background:#1e293b;border-radius:8px;padding:14px;text-align:center}}
  .stat .val{{font-size:1.6rem;font-weight:700;color:#C74634}}
  .stat .lbl{{font-size:.75rem;color:#64748b;margin-top:2px}}
  table{{border-collapse:collapse;width:100%}}
  th{{color:#64748b;font-size:.75rem;text-align:left;padding:6px 12px;border-bottom:1px solid #334155}}
  tr:hover td{{background:#273548}}
  .wrap{{max-width:820px;margin:0 auto;padding:28px 20px}}
  .badge{{display:inline-block;background:#0f172a;border:1px solid #334155;border-radius:4px;padding:2px 8px;font-size:.7rem;color:#94a3b8;margin-left:8px}}
</style>
</head>
<body>
<div class="wrap">
  <h1>Video Fine-Tuning Pipeline <span class="badge">port 8940</span></h1>
  <p style="color:#64748b;margin-top:0">GR00T N2 · 4-frame temporal attention · {DEMOS} demos × {STEPS} steps × {FPS} fps</p>

  <div class="stat-grid">
    <div class="stat"><div class="val">{DEMOS}</div><div class="lbl">Demo Episodes</div></div>
    <div class="stat"><div class="val">{total_frames_fmt}</div><div class="lbl">Total Frames</div></div>
    <div class="stat"><div class="val">{total_tb_fmt}</div><div class="lbl">Dataset Size</div></div>
    <div class="stat"><div class="val">4</div><div class="lbl">Temporal Attention Frames</div></div>
  </div>

  <div class="card">
    <h2>Success Rate: Video vs Image (per task)</h2>
    {sr_svg}
    <table style="margin-top:16px">
      <thead><tr>
        <th>Task</th><th>Image SR</th><th>Video SR</th><th>Delta</th>
      </tr></thead>
      <tbody>{delta_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>Data Pipeline Throughput (demos / min)</h2>
    {thr_svg}
    <p style="color:#64748b;font-size:.8rem;margin-top:8px">
      Fine-tune stage is GPU-bound (94 d/m on A100); ingest &amp; tokenize are I/O-bound and can scale horizontally.
    </p>
  </div>

  <div class="card" style="font-size:.8rem;color:#64748b">
    <b style="color:#94a3b8">Model:</b> GR00T N2 &nbsp;·&nbsp;
    <b style="color:#94a3b8">Attention:</b> 4-frame causal temporal &nbsp;·&nbsp;
    <b style="color:#94a3b8">Avg SR gain:</b>
    +{round(sum(t['video_sr']-t['image_sr'] for t in TASKS)/len(TASKS),1)}pp over image baseline
  </div>
</div>
</body>
</html>"""


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8940)
    else:
        print("FastAPI not found — starting fallback HTTPServer on :8940")
        HTTPServer(("0.0.0.0", 8940), Handler).serve_forever()

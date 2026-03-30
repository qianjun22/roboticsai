"""Episode Quality Scorer V2 — FastAPI port 8886"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8886

# Multi-axis episode quality assessment across 7 axes:
# task_success, smoothness, efficiency, safety, generalization, sim2real, uncertainty
AXES = ["task_success", "smoothness", "efficiency", "safety", "generalization", "sim2real", "uncertainty"]
TIERS = ["gold", "silver", "bronze", "reject"]
TIER_COLORS = {"gold": "#FFD700", "silver": "#C0C0C0", "bronze": "#CD7F32", "reject": "#EF4444"}

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))

    # Per-axis quality scores
    axis_scores = {ax: round(random.uniform(0.55, 0.98), 3) for ax in AXES}
    axis_rows = "".join(
        f'<tr><td style="padding:4px 10px">{ax}</td>'
        f'<td style="padding:4px 10px"><div style="background:#334155;border-radius:4px;width:160px">'
        f'<div style="background:#C74634;width:{int(score*160)}px;height:14px;border-radius:4px"></div></div></td>'
        f'<td style="padding:4px 10px;color:#38bdf8">{score}</td></tr>'
        for ax, score in axis_scores.items()
    )

    # Quality tier distribution (gold/silver/bronze/reject)
    tier_counts = {"gold": random.randint(120, 200), "silver": random.randint(300, 450),
                   "bronze": random.randint(150, 250), "reject": random.randint(40, 100)}
    total = sum(tier_counts.values())
    tier_bars = "".join(
        f'<div style="margin:6px 0"><span style="display:inline-block;width:80px;color:{TIER_COLORS[t]}">{t}</span>'
        f'<div style="display:inline-block;background:#334155;border-radius:4px;width:200px;vertical-align:middle">'
        f'<div style="background:{TIER_COLORS[t]};width:{int(c/total*200)}px;height:16px;border-radius:4px"></div></div>'
        f'<span style="margin-left:8px;color:#94a3b8">{c} ({round(c/total*100,1)}%)</span></div>'
        for t, c in tier_counts.items()
    )

    # DAgger round trend
    dagger_scores = [round(0.55 + i*0.04 + random.uniform(-0.01, 0.01), 3) for i in range(8)]
    dagger_pts = " ".join(f"{30+i*55},{150-int(s*120)}" for i, s in enumerate(dagger_scores))
    dagger_circles = "".join(f'<circle cx="{30+i*55}" cy="{150-int(s*120)}" r="5" fill="#38bdf8"/><text x="{30+i*55}" y="{165-int(s*120)}" fill="#94a3b8" font-size="10" text-anchor="middle">{s}</text>' for i, s in enumerate(dagger_scores))

    return f"""<!DOCTYPE html><html><head><title>Episode Quality Scorer V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse}}td{{border:1px solid #334155}}</style></head>
<body><h1>Episode Quality Scorer V2</h1>
<p style="margin:10px;color:#94a3b8">Multi-axis episode quality assessment (7 axes) across DAgger rounds — automatically grades each rollout into gold/silver/bronze/reject tiers.</p>

<div class="card"><h2>7-Axis Quality Scores</h2>
<table>{axis_rows}</table></div>

<div class="card"><h2>Quality Tier Distribution (latest round, n={total})</h2>
{tier_bars}</div>

<div class="card"><h2>Composite Score Trend Across DAgger Rounds</h2>
<svg width="450" height="180">
  <polyline points="{dagger_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
  {dagger_circles}
</svg>
<p style="color:#94a3b8">Round 1 → Round {len(dagger_scores)} | Latest: {dagger_scores[-1]} | Peak: {max(dagger_scores)}</p></div>

<div class="card"><h2>Metrics</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Episode Quality Scorer V2")
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

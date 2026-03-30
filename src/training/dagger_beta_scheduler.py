"""DAgger Beta Scheduler API — port 8345
Optimizes the DAgger β parameter schedule for faster convergence and higher final SR.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

random.seed(42)

N_EPS = 1000

def _linear_decay(ep):
    return max(0.0, 1.0 - ep / N_EPS)

def _exp_decay(ep):
    return math.exp(-3.0 * ep / N_EPS)

def _step_func(ep):
    if ep < 200:   return 1.0
    elif ep < 400: return 0.7
    elif ep < 600: return 0.4
    elif ep < 800: return 0.2
    else:          return 0.05

def _adaptive_sr(ep):
    # drops faster once SR > 0.4 (simulated)
    if ep < 150:  return 1.0 - 0.002 * ep
    elif ep < 380: return 0.70 - 0.001 * (ep - 150)
    else:          return max(0.05, 0.47 - 0.0008 * (ep - 380))

def _run10_actual(ep):
    # run10 follows adaptive_sr with small noise
    base = _adaptive_sr(ep)
    return min(1.0, max(0.0, base + random.gauss(0, 0.02)))

SCHEDULES = {
    "linear_decay":    _linear_decay,
    "exponential_decay": _exp_decay,
    "step_function":   _step_func,
    "adaptive_sr":     _adaptive_sr,
    "run10_actual":    _run10_actual,
}

# Pre-compute sample points (every 20 episodes)
SCHEDULE_POINTS = {
    name: [(ep, round(fn(ep), 4)) for ep in range(0, N_EPS + 1, 20)]
    for name, fn in SCHEDULES.items()
}

# SR curves (simulated policy success rate per episode)
def _sr_curve(schedule_name, ep):
    """Simulate SR at episode ep for a given beta schedule."""
    noise = random.gauss(0, 0.03)
    if schedule_name == "adaptive_sr":
        sr = min(0.72, 0.65 * (1 - math.exp(-ep / 280))) + noise
    elif schedule_name == "linear_decay":
        sr = min(0.66, 0.60 * (1 - math.exp(-ep / 350))) + noise
    elif schedule_name == "exponential_decay":
        sr = min(0.64, 0.58 * (1 - math.exp(-ep / 320))) + noise
    elif schedule_name == "step_function":
        # drops at step boundaries
        drop = 0.08 if ep in range(195, 210) or ep in range(395, 410) else 0
        sr = min(0.63, 0.57 * (1 - math.exp(-ep / 400))) - drop + noise
    else:  # run10_actual
        sr = min(0.69, 0.63 * (1 - math.exp(-ep / 290))) + noise
    return round(min(1.0, max(0.0, sr)), 4)

SR_CURVES = {
    name: [(ep, _sr_curve(name, ep)) for ep in range(0, N_EPS + 1, 20)]
    for name in SCHEDULES
}

# run10 scatter: 200 individual episodes
RUN10_SCATTER = [
    {"ep": ep, "sr": round(_sr_curve("run10_actual", ep) + random.gauss(0, 0.04), 3),
     "beta": round(_run10_actual(ep), 3)}
    for ep in random.choices(range(0, N_EPS), k=200)
]

METRICS = {
    "current_beta": 0.71,
    "current_episode": 412,
    "best_schedule": "adaptive_sr",
    "adaptive_sr_target_ep": 380,
    "linear_target_ep": 450,
    "current_sr": 0.65,
    "step_worst": True,
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

SCHEDULE_COLORS = {
    "linear_decay":      "#38bdf8",
    "exponential_decay": "#a78bfa",
    "step_function":     "#C74634",
    "adaptive_sr":       "#4ade80",
    "run10_actual":      "#fbbf24",
}

def _beta_schedule_svg() -> str:
    """Line chart comparing 5 beta schedules over 1000 episodes."""
    W, H = 680, 280
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 50
    cw = W - pad_l - pad_r
    ch = H - pad_t - pad_b

    def tx(ep):  return pad_l + int(ep / N_EPS * cw)
    def ty(b):   return pad_t + ch - int(b * ch)

    lines = []
    # grid
    for pct in [0, 25, 50, 75, 100]:
        y = ty(pct / 100)
        lines.append(f'<line x1="{pad_l}" y1="{y}" x2="{W - pad_r}" y2="{y}" stroke="#1e3a5f" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l - 6}" y="{y + 4}" text-anchor="end" font-size="10" fill="#475569">{pct}%</text>')
    for ep in range(0, N_EPS + 1, 200):
        x = tx(ep)
        lines.append(f'<line x1="{x}" y1="{pad_t}" x2="{x}" y2="{pad_t + ch}" stroke="#1e3a5f" stroke-width="1"/>')
        lines.append(f'<text x="{x}" y="{pad_t + ch + 14}" text-anchor="middle" font-size="10" fill="#475569">{ep}</text>')

    for name, pts in SCHEDULE_POINTS.items():
        color = SCHEDULE_COLORS[name]
        d = " ".join(
            f"{tx(ep)},{ty(b)}" for ep, b in pts
        )
        lines.append(f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="{2 if name != "run10_actual" else 1.5}" stroke-dasharray="{"" if name not in ("run10_actual",) else "4,2"}"/>')

    # annotation: adaptive_sr hits target fastest
    ax, ay = tx(380), ty(0.47)
    lines.append(f'<line x1="{ax}" y1="{pad_t}" x2="{ax}" y2="{pad_t + ch}" stroke="#4ade80" stroke-width="1" stroke-dasharray="4,3"/>')
    lines.append(f'<text x="{ax + 4}" y="{pad_t + 14}" font-size="10" fill="#4ade80">adaptive fastest (ep 380)</text>')

    # legend
    lx, ly = pad_l, H - 14
    for i, (name, color) in enumerate(SCHEDULE_COLORS.items()):
        x = lx + i * 128
        lines.append(f'<rect x="{x}" y="{ly - 8}" width="18" height="8" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{x + 22}" y="{ly}" font-size="9" fill="#94a3b8">{name}</text>')

    inner = "\n".join(lines)
    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;width:100%;max-width:{W}px">\n'
        + inner
        + "\n</svg>"
    )


def _scatter_svg() -> str:
    """Scatter plot: SR vs beta for 200 run10 episodes with quadrant analysis."""
    W, H = 680, 300
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 50
    cw = W - pad_l - pad_r
    ch = H - pad_t - pad_b

    def px(beta): return pad_l + int(beta * cw)
    def py(sr):   return pad_t + ch - int(sr * ch)

    lines = []
    # grid
    for pct in [0, 25, 50, 75, 100]:
        y = py(pct / 100)
        lines.append(f'<line x1="{pad_l}" y1="{y}" x2="{W - pad_r}" y2="{y}" stroke="#1e3a5f" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l - 6}" y="{y + 4}" text-anchor="end" font-size="10" fill="#475569">{pct}%</text>')
    for b_pct in [0, 25, 50, 75, 100]:
        x = px(b_pct / 100)
        lines.append(f'<line x1="{x}" y1="{pad_t}" x2="{x}" y2="{pad_t + ch}" stroke="#1e3a5f" stroke-width="1"/>')
        lines.append(f'<text x="{x}" y="{pad_t + ch + 14}" text-anchor="middle" font-size="10" fill="#475569">{b_pct}%</text>')

    # quadrant dividers
    mid_x = px(0.5)
    mid_y = py(0.5)
    lines.append(f'<line x1="{mid_x}" y1="{pad_t}" x2="{mid_x}" y2="{pad_t + ch}" stroke="#334155" stroke-width="1.5" stroke-dasharray="6,3"/>')
    lines.append(f'<line x1="{pad_l}" y1="{mid_y}" x2="{W - pad_r}" y2="{mid_y}" stroke="#334155" stroke-width="1.5" stroke-dasharray="6,3"/>')

    # quadrant labels
    lines.append(f'<text x="{mid_x + 8}" y="{pad_t + 14}" font-size="9" fill="#4ade80">high-β / high-SR</text>')
    lines.append(f'<text x="{pad_l + 6}" y="{pad_t + 14}" font-size="9" fill="#38bdf8">low-β / high-SR</text>')
    lines.append(f'<text x="{mid_x + 8}" y="{mid_y + 24}" font-size="9" fill="#C74634">high-β / low-SR</text>')
    lines.append(f'<text x="{pad_l + 6}" y="{mid_y + 24}" font-size="9" fill="#94a3b8">low-β / low-SR</text>')

    # scatter points
    for pt in RUN10_SCATTER:
        x = px(pt["beta"])
        y = py(max(0, pt["sr"]))
        color = "#4ade80" if pt["beta"] >= 0.5 and pt["sr"] >= 0.5 else (
                "#38bdf8" if pt["beta"] < 0.5 and pt["sr"] >= 0.5 else
                "#C74634" if pt["beta"] >= 0.5 else "#475569")
        lines.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{color}" opacity="0.7"/>')

    # axis labels
    lines.append(f'<text x="{pad_l + cw//2}" y="{H - 2}" text-anchor="middle" font-size="11" fill="#94a3b8">β (beta)</text>')
    lines.append(f'<text x="12" y="{pad_t + ch//2}" text-anchor="middle" font-size="11" fill="#94a3b8" transform="rotate(-90,12,{pad_t + ch//2})">SR</text>')

    inner = "\n".join(lines)
    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;width:100%;max-width:{W}px">\n'
        + inner
        + "\n</svg>"
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    beta_svg = _beta_schedule_svg()
    scatter_svg = _scatter_svg()
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>DAgger Beta Scheduler — Port 8345</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:24px}}
    h1{{color:#38bdf8;font-size:1.6rem;margin-bottom:4px}}
    .subtitle{{color:#94a3b8;font-size:.9rem;margin-bottom:24px}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:28px}}
    .card{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px}}
    .card-label{{font-size:.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em}}
    .card-value{{font-size:1.5rem;font-weight:700;margin-top:4px}}
    .red{{color:#C74634}} .blue{{color:#38bdf8}} .green{{color:#4ade80}} .yellow{{color:#fbbf24}}
    .section{{margin-bottom:32px}}
    .section h2{{color:#38bdf8;font-size:1rem;margin-bottom:12px;border-bottom:1px solid #334155;padding-bottom:6px}}
    .note{{font-size:.82rem;color:#64748b;margin-top:8px}}
    footer{{color:#475569;font-size:.75rem;margin-top:32px}}
  </style>
</head>
<body>
  <h1>DAgger Beta Scheduler</h1>
  <p class="subtitle">Optimizing β schedule for faster convergence &amp; higher final SR &nbsp;|&nbsp; Port 8345 &nbsp;|&nbsp; {ts}</p>

  <div class="grid">
    <div class="card"><div class="card-label">Current β</div><div class="card-value yellow">{METRICS['current_beta']}</div></div>
    <div class="card"><div class="card-label">Current Episode</div><div class="card-value blue">{METRICS['current_episode']}</div></div>
    <div class="card"><div class="card-label">Best Schedule</div><div class="card-value green">{METRICS['best_schedule']}</div></div>
    <div class="card"><div class="card-label">Adaptive SR Target</div><div class="card-value green">ep {METRICS['adaptive_sr_target_ep']}</div></div>
    <div class="card"><div class="card-label">Linear Target</div><div class="card-value red">ep {METRICS['linear_target_ep']}</div></div>
    <div class="card"><div class="card-label">Current SR</div><div class="card-value blue">{METRICS['current_sr']:.0%}</div></div>
  </div>

  <div class="section">
    <h2>Beta Schedule Comparison (5 strategies, 0–1000 episodes)</h2>
    {beta_svg}
    <p class="note">adaptive_sr reaches SR=0.65 target at ep 380 vs linear at ep 450 (+18% faster). step_function worst — discontinuous SR drops at β step boundaries.</p>
  </div>

  <div class="section">
    <h2>SR vs Beta — run10 scatter (200 episodes, quadrant analysis)</h2>
    {scatter_svg}
    <p class="note">Top-right (high-β / high-SR): good early exploitation. Top-left (low-β / high-SR): policy independence achieved. run10 currently at β=0.71, ep 412.</p>
  </div>

  <footer>OCI Robot Cloud &mdash; DAgger Beta Scheduler &mdash; cycle-71A</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="DAgger Beta Scheduler API", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(_build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "dagger_beta_scheduler", "port": 8345}

    @app.get("/metrics")
    async def metrics():
        return {"metrics": METRICS, "schedules": list(SCHEDULES.keys())}

    @app.get("/schedule/{name}")
    async def get_schedule(name: str):
        if name not in SCHEDULE_POINTS:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Schedule '{name}' not found")
        return {"name": name, "points": SCHEDULE_POINTS[name]}

    @app.get("/beta")
    async def current_beta():
        return {
            "episode": METRICS["current_episode"],
            "beta": METRICS["current_beta"],
            "schedule": METRICS["best_schedule"],
        }

    @app.post("/beta/step")
    async def step_beta(body: dict):
        ep = body.get("episode", 0)
        schedule = body.get("schedule", "adaptive_sr")
        fn = SCHEDULES.get(schedule, _adaptive_sr)
        return {"episode": ep, "beta": round(fn(ep), 4), "schedule": schedule}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json as _json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path in ("/", ""):
                body = _build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/health":
                body = _json.dumps({"status": "ok", "port": 8345}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/metrics":
                body = _json.dumps({"metrics": METRICS}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

    def _run_stdlib():
        server = HTTPServer(("0.0.0.0", 8345), Handler)
        print("DAgger Beta Scheduler (stdlib fallback) running on http://0.0.0.0:8345")
        server.serve_forever()


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run("dagger_beta_scheduler:app", host="0.0.0.0", port=8345, reload=False)
    else:
        _run_stdlib()

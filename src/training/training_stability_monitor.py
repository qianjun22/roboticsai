"""Training Stability Monitor — port 8974
Real-time gradient norm / loss variance / LR / weight stats with EWC.
"""
import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _ewc_penalty(lam: float, steps: int) -> float:
    return lam * math.exp(-steps / 500.0)

def _stability_score(grad_norm: float, loss_var: float) -> float:
    raw = 1.0 - min(1.0, 0.3 * grad_norm + 0.7 * loss_var)
    return round(max(0.0, raw), 3)

# Deterministic seed so the demo looks the same on every reload
random.seed(42)

STEPS = list(range(0, 2200, 100))

GRAD_NORMS = []
LOSS_VAR = []
LR_TRACE = []
WEIGHT_NORMS = []

base_grad = 1.8
base_loss_var = 0.45
base_lr = 3e-4
base_w = 12.4

for i, s in enumerate(STEPS):
    noise_g = random.gauss(0, 0.12)
    noise_l = random.gauss(0, 0.03)
    # simulate stabilisation after step 1000
    decay = math.exp(-s / 1800.0)
    gn = round(max(0.1, base_grad * decay + noise_g), 4)
    lv = round(max(0.01, base_loss_var * decay + noise_l), 4)
    lr = round(base_lr * (0.97 ** (s // 100)), 7)
    wn = round(base_w + 0.002 * s + random.gauss(0, 0.08), 4)
    GRAD_NORMS.append(gn)
    LOSS_VAR.append(lv)
    LR_TRACE.append(lr)
    WEIGHT_NORMS.append(wn)

# Instability events — steps where grad_norm > mean + 3*std
mean_gn = sum(GRAD_NORMS) / len(GRAD_NORMS)
std_gn = math.sqrt(sum((x - mean_gn) ** 2 for x in GRAD_NORMS) / len(GRAD_NORMS))
THRESHOLD_GN = mean_gn + 3 * std_gn

EVENTS = []
for i, (s, gn) in enumerate(zip(STEPS, GRAD_NORMS)):
    if gn > THRESHOLD_GN:
        action = "Reduce LR by 10%"
        new_lr = round(LR_TRACE[i] * 0.9, 7)
        EVENTS.append({"step": s, "grad_norm": gn, "action": action, "lr_after": new_lr})

# Current run metrics
RUN10_SCORE = 0.89
RUN11_TARGET = 0.92
CURRENT_SCORE = _stability_score(GRAD_NORMS[-1], LOSS_VAR[-1])
EWC_LAMBDA = 0.004
EWC_PEN = round(_ewc_penalty(EWC_LAMBDA, STEPS[-1]), 6)

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_line_chart(
    series: list,
    color: str,
    label: str,
    width: int = 700,
    height: int = 180,
    x_labels: list = None,
) -> str:
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 40
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b

    mn = min(series)
    mx = max(series)
    rng = mx - mn or 1e-9

    def px(i):
        return pad_l + i * inner_w / (len(series) - 1)

    def py(v):
        return pad_t + inner_h * (1 - (v - mn) / rng)

    pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(series))

    # y-axis ticks
    ticks_svg = ""
    for k in range(5):
        yv = mn + rng * k / 4
        yt = pad_t + inner_h * (1 - k / 4)
        ticks_svg += (
            f'<line x1="{pad_l}" y1="{yt:.1f}" x2="{pad_l + inner_w}" y2="{yt:.1f}" '
            f'stroke="#334155" stroke-width="0.5"/>'
            f'<text x="{pad_l - 5}" y="{yt + 4:.1f}" text-anchor="end" '
            f'font-size="9" fill="#94a3b8">{yv:.4g}</text>'
        )

    # x-axis labels (every 4th)
    x_svg = ""
    if x_labels:
        step_count = len(x_labels)
        for k in range(0, step_count, max(1, step_count // 6)):
            xp = px(k)
            x_svg += (
                f'<text x="{xp:.1f}" y="{pad_t + inner_h + 14}" text-anchor="middle" '
                f'font-size="9" fill="#94a3b8">{x_labels[k]}</text>'
            )

    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        f'{ticks_svg}{x_svg}'
        f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>'
        f'<text x="{pad_l}" y="{pad_t - 6}" font-size="10" fill="#94a3b8">{label}</text>'
        f'</svg>'
    )


def _make_html() -> str:
    chart_grad = _svg_line_chart(GRAD_NORMS, "#38bdf8", "Gradient Norm", x_labels=[str(s) for s in STEPS])
    chart_loss = _svg_line_chart(LOSS_VAR, "#fb923c", "Loss Variance", x_labels=[str(s) for s in STEPS])
    chart_lr = _svg_line_chart(LR_TRACE, "#a78bfa", "Learning Rate", x_labels=[str(s) for s in STEPS])
    chart_wn = _svg_line_chart(WEIGHT_NORMS, "#4ade80", "Weight Norm", x_labels=[str(s) for s in STEPS])

    score_color = "#4ade80" if CURRENT_SCORE >= RUN11_TARGET else "#f87171"
    progress_pct = min(100, int(CURRENT_SCORE / RUN11_TARGET * 100))

    events_rows = ""
    for ev in EVENTS[:10]:
        events_rows += (
            f'<tr><td>{ev["step"]}</td><td>{ev["grad_norm"]:.4f}</td>'
            f'<td>{ev["action"]}</td><td>{ev["lr_after"]:.2e}</td></tr>'
        )
    if not EVENTS:
        events_rows = '<tr><td colspan="4" style="text-align:center;color:#64748b">No instability events detected</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Training Stability Monitor</title>
<style>
  body{{margin:0;padding:24px;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
  h1{{color:#C74634;margin-bottom:4px}}
  h2{{color:#38bdf8;font-size:1rem;margin:20px 0 8px}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin-bottom:24px}}
  .card{{background:#1e293b;border-radius:10px;padding:16px}}
  .card .val{{font-size:1.8rem;font-weight:700;margin-top:6px}}
  .card .sub{{font-size:.75rem;color:#64748b;margin-top:4px}}
  table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
  th{{background:#0f172a;padding:10px 14px;text-align:left;font-size:.75rem;color:#64748b;text-transform:uppercase}}
  td{{padding:9px 14px;border-bottom:1px solid #0f172a;font-size:.85rem}}
  tr:last-child td{{border-bottom:none}}
  .bar-bg{{background:#0f172a;border-radius:999px;height:10px;margin-top:8px}}
  .bar-fill{{background:#38bdf8;border-radius:999px;height:10px;transition:width .4s}}
  .tag{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.7rem;background:#1e293b;color:#38bdf8;border:1px solid #38bdf8}}
</style>
</head>
<body>
<h1>Training Stability Monitor</h1>
<p style="color:#64748b;font-size:.85rem">Port 8974 &mdash; Real-time gradient / loss / LR / weight statistics with EWC regularisation</p>

<div class="grid">
  <div class="card">
    <div style="color:#94a3b8;font-size:.8rem">Stability Score (current)</div>
    <div class="val" style="color:{score_color}">{CURRENT_SCORE:.3f}</div>
    <div class="sub">Run-10 baseline: {RUN10_SCORE} &nbsp;|&nbsp; Run-11 target: {RUN11_TARGET}</div>
    <div class="bar-bg"><div class="bar-fill" style="width:{progress_pct}%"></div></div>
  </div>
  <div class="card">
    <div style="color:#94a3b8;font-size:.8rem">EWC Penalty (λ={EWC_LAMBDA})</div>
    <div class="val" style="color:#a78bfa">{EWC_PEN:.2e}</div>
    <div class="sub">Catastrophic forgetting guard</div>
  </div>
  <div class="card">
    <div style="color:#94a3b8;font-size:.8rem">Instability Events</div>
    <div class="val" style="color:#fb923c">{len(EVENTS)}</div>
    <div class="sub">Grad &gt; mean + 3σ ({THRESHOLD_GN:.3f})</div>
  </div>
  <div class="card">
    <div style="color:#94a3b8;font-size:.8rem">Final Grad Norm</div>
    <div class="val" style="color:#38bdf8">{GRAD_NORMS[-1]:.4f}</div>
    <div class="sub">Step {STEPS[-1]}</div>
  </div>
  <div class="card">
    <div style="color:#94a3b8;font-size:.8rem">Final Loss Variance</div>
    <div class="val" style="color:#4ade80">{LOSS_VAR[-1]:.4f}</div>
    <div class="sub">Step {STEPS[-1]}</div>
  </div>
  <div class="card">
    <div style="color:#94a3b8;font-size:.8rem">Current LR</div>
    <div class="val" style="color:#f472b6">{LR_TRACE[-1]:.2e}</div>
    <div class="sub">Cosine decay schedule</div>
  </div>
</div>

<h2>Stability Metrics Timeline</h2>
{chart_grad}
<div style="height:12px"></div>
{chart_loss}
<div style="height:12px"></div>
{chart_lr}
<div style="height:12px"></div>
{chart_wn}

<h2>Instability Event Log <span class="tag">auto LR reduction triggered</span></h2>
<table>
  <thead><tr><th>Step</th><th>Grad Norm</th><th>Action</th><th>LR After</th></tr></thead>
  <tbody>{events_rows}</tbody>
</table>

<p style="color:#334155;font-size:.75rem;margin-top:24px">OCI Robot Cloud &mdash; Training Stability Monitor v1.0</p>
</body></html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Training Stability Monitor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTMLResponse(_make_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8974, "service": "training_stability_monitor"}

    @app.get("/metrics")
    async def metrics():
        return {
            "stability_score": CURRENT_SCORE,
            "run10_baseline": RUN10_SCORE,
            "run11_target": RUN11_TARGET,
            "ewc_penalty": EWC_PEN,
            "instability_events": len(EVENTS),
            "final_grad_norm": GRAD_NORMS[-1],
            "final_loss_variance": LOSS_VAR[-1],
            "current_lr": LR_TRACE[-1],
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8974)

else:
    # Fallback stdlib HTTP server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _make_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", 8974), Handler)
        print("Training Stability Monitor running on http://0.0.0.0:8974")
        server.serve_forever()

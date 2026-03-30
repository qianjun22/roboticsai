"""policy_gradient_tracker.py — FastAPI service on port 8209.

Dashboard for DAgger/RL policy gradient monitoring: multi-line loss
curves and per-layer-group gradient norm bar chart.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random

# ── Mock data ────────────────────────────────────────────────────────────────
random.seed(7)

RUN_NAME = "dagger_run10"
TOTAL_STEPS = 5000
STEP_INTERVAL = 100          # one data point every 100 steps
STEPS = list(range(0, TOTAL_STEPS + 1, STEP_INTERVAL))  # 0, 100, ..., 5000
N_STEPS = len(STEPS)         # 51 points
CONVERGENCE_STEP = 3200      # approx convergence
CONVERGENCE_IDX  = CONVERGENCE_STEP // STEP_INTERVAL

LAYER_GROUPS = ["encoder", "decoder", "action_head"]
N_CHECKPOINTS_BAR = 10


def _smooth(vals, alpha=0.15):
    out = [vals[0]]
    for v in vals[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out


def _make_loss_curves():
    policy_loss, value_loss, entropy = [], [], []
    for i, step in enumerate(STEPS):
        t = step / TOTAL_STEPS
        # policy loss: high early, drops to ~0.15 by step 3200, then plateau
        if step <= CONVERGENCE_STEP:
            pl = 1.8 * math.exp(-4.5 * t) + 0.15 + random.gauss(0, 0.04)
        else:
            pl = 0.15 + random.gauss(0, 0.015)
        # value loss: similar but lower magnitude
        if step <= CONVERGENCE_STEP:
            vl = 0.9 * math.exp(-3.8 * t) + 0.08 + random.gauss(0, 0.025)
        else:
            vl = 0.08 + random.gauss(0, 0.01)
        # entropy: starts ~1.6 (high exploration), drops to ~0.45 near collapse warning
        ent = max(0.3, 1.6 - 1.15 * t + random.gauss(0, 0.05))
        policy_loss.append(max(0.0, pl))
        value_loss.append(max(0.0, vl))
        entropy.append(ent)
    return _smooth(policy_loss, 0.2), _smooth(value_loss, 0.2), _smooth(entropy, 0.2)


POLICY_LOSS, VALUE_LOSS, ENTROPY = _make_loss_curves()


def _make_grad_norms():
    """Gradient norms per layer group for the last 10 checkpoints."""
    norms = {}
    for lg in LAYER_GROUPS:
        base = {"encoder": 0.45, "decoder": 0.62, "action_head": 0.38}[lg]
        # norms trend downward as training converges
        row = []
        for ck in range(N_CHECKPOINTS_BAR):
            decay = math.exp(-ck * 0.12)
            row.append(max(0.05, base * decay + random.gauss(0, 0.03)))
        norms[lg] = [round(v, 4) for v in row]
    return norms


GRAD_NORMS = _make_grad_norms()


def _key_metrics():
    entropy_collapse_threshold = 0.5
    collapse_warnings = sum(1 for e in ENTROPY if e < entropy_collapse_threshold)
    # gradient clipping events: steps where any group norm > 1.0
    clip_events = 0
    for ck in range(N_CHECKPOINTS_BAR):
        for lg in LAYER_GROUPS:
            if GRAD_NORMS[lg][ck] > 0.55:
                clip_events += 1
    # KL divergence from BC baseline (mock — increases slightly then stabilizes)
    kl_final = round(0.18 + random.gauss(0, 0.01), 3)
    # convergence loss
    conv_policy = round(sum(POLICY_LOSS[CONVERGENCE_IDX:]) / max(1, len(POLICY_LOSS[CONVERGENCE_IDX:])), 4)
    return {
        "run": RUN_NAME,
        "convergence_step": CONVERGENCE_STEP,
        "gradient_clip_events": clip_events,
        "entropy_collapse_warnings": collapse_warnings,
        "kl_from_bc": kl_final,
        "post_convergence_policy_loss": conv_policy,
        "total_steps": TOTAL_STEPS,
    }


METRICS = _key_metrics()


# ── SVG helpers ──────────────────────────────────────────────────────────────

def _svg_loss_curves() -> str:
    """Multi-line chart: policy loss, value loss, entropy over training steps."""
    W, H = 720, 340
    PAD = {"top": 44, "right": 40, "bottom": 50, "left": 60}
    plot_w = W - PAD["left"] - PAD["right"]
    plot_h = H - PAD["top"]  - PAD["bottom"]

    all_vals = POLICY_LOSS + VALUE_LOSS + ENTROPY
    max_val = max(all_vals) * 1.05

    def sx(i): return PAD["left"] + i * plot_w / (N_STEPS - 1)
    def sy(v): return PAD["top"]  + plot_h * (1 - v / max_val)

    def polyline(series, color, label, dash=""):
        pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(series))
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        return (f'<polyline points="{pts}" fill="none" stroke="{color}" '
                f'stroke-width="2"{dash_attr} opacity="0.9"/>')

    lines = [
        polyline(POLICY_LOSS, "#C74634", "policy_loss"),
        polyline(VALUE_LOSS,  "#38bdf8", "value_loss"),
        polyline(ENTROPY,     "#34d399", "entropy"),
    ]

    # vertical convergence marker
    cx = sx(CONVERGENCE_IDX)
    conv_marker = (
        f'<line x1="{cx:.1f}" y1="{PAD["top"]}" x2="{cx:.1f}" '
        f'y2="{PAD["top"]+plot_h}" stroke="#fbbf24" stroke-width="1" stroke-dasharray="5,3"/>'
        f'<text x="{cx+4:.1f}" y="{PAD["top"]+14}" font-size="10" fill="#fbbf24">converge @ {CONVERGENCE_STEP}</text>'
    )

    # axes
    axes = [
        f'<line x1="{PAD["left"]}" y1="{PAD["top"]}" x2="{PAD["left"]}" y2="{PAD["top"]+plot_h}" stroke="#334155" stroke-width="1"/>',
        f'<line x1="{PAD["left"]}" y1="{PAD["top"]+plot_h}" x2="{PAD["left"]+plot_w}" y2="{PAD["top"]+plot_h}" stroke="#334155" stroke-width="1"/>',
    ]

    # x-axis tick labels every 500 steps
    xlabels = []
    for step in range(0, TOTAL_STEPS + 1, 500):
        i = step // STEP_INTERVAL
        x = sx(i)
        xlabels.append(f'<text x="{x:.1f}" y="{PAD["top"]+plot_h+16}" text-anchor="middle" font-size="10" fill="#94a3b8">{step}</text>')
        xlabels.append(f'<line x1="{x:.1f}" y1="{PAD["top"]+plot_h}" x2="{x:.1f}" y2="{PAD["top"]+plot_h+4}" stroke="#475569" stroke-width="1"/>')

    # y-axis
    ylabels = []
    for i in range(5):
        v = max_val * i / 4
        y = sy(v)
        ylabels.append(f'<text x="{PAD["left"]-8}" y="{y:.1f}" text-anchor="end" font-size="10" fill="#94a3b8" dominant-baseline="middle">{v:.2f}</text>')
        ylabels.append(f'<line x1="{PAD["left"]}" y1="{y:.1f}" x2="{PAD["left"]+plot_w}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1" stroke-dasharray="3,3"/>')

    # legend
    legend_items = [
        ("#C74634", "Policy Loss"),
        ("#38bdf8", "Value Loss"),
        ("#34d399", "Entropy"),
    ]
    legend = []
    for idx, (color, label) in enumerate(legend_items):
        lx = PAD["left"] + idx * 160
        ly = H - 6
        legend.append(f'<rect x="{lx}" y="{ly-7}" width="18" height="4" fill="{color}"/>')
        legend.append(f'<text x="{lx+22}" y="{ly}" font-size="10" fill="#cbd5e1">{label}</text>')

    title  = f'<text x="{W//2}" y="22" text-anchor="middle" font-size="14" font-weight="bold" fill="#f1f5f9">Policy / Value Loss &amp; Entropy — {RUN_NAME} (0&#x2013;{TOTAL_STEPS} steps)</text>'
    xlabel = f'<text x="{PAD["left"]+plot_w//2}" y="{H-4}" text-anchor="middle" font-size="11" fill="#64748b">Training Step</text>'
    ylabel = f'<text x="16" y="{H//2}" text-anchor="middle" font-size="11" fill="#94a3b8" transform="rotate(-90 16 {H//2})">Loss / Entropy</text>'

    inner = "\n".join(axes + ylabels + xlabels + [conv_marker] + lines + legend + [title, xlabel, ylabel])
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">\n{inner}\n</svg>'


def _svg_grad_norm_bars() -> str:
    """Grouped bar chart: gradient norms per layer group across last 10 checkpoints."""
    BAR_W  = 14
    GROUP_GAP = 24
    N_GROUPS = N_CHECKPOINTS_BAR
    N_BARS   = len(LAYER_GROUPS)
    COLORS   = {"encoder": "#38bdf8", "decoder": "#C74634", "action_head": "#34d399"}

    PAD_LEFT, PAD_TOP, PAD_BOT, PAD_RIGHT = 60, 44, 60, 30
    GROUP_W = N_BARS * BAR_W + GROUP_GAP
    W = PAD_LEFT + N_GROUPS * GROUP_W + PAD_RIGHT
    H = 300
    plot_h = H - PAD_TOP - PAD_BOT

    max_norm = max(v for lg in LAYER_GROUPS for v in GRAD_NORMS[lg]) * 1.1

    def bar_y(v):  return PAD_TOP + plot_h * (1 - v / max_norm)
    def bar_h(v):  return plot_h * (v / max_norm)

    bars = []
    xlabels = []
    for ck in range(N_GROUPS):
        gx = PAD_LEFT + ck * GROUP_W
        for bi, lg in enumerate(LAYER_GROUPS):
            bx = gx + bi * BAR_W
            v  = GRAD_NORMS[lg][ck]
            by = bar_y(v)
            bh = bar_h(v)
            bars.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{BAR_W-2}" height="{bh:.1f}" fill="{COLORS[lg]}" rx="2" opacity="0.85"/>')
        # x label
        lx = gx + (N_BARS * BAR_W) / 2
        xlabels.append(f'<text x="{lx:.1f}" y="{PAD_TOP+plot_h+16}" text-anchor="middle" font-size="10" fill="#94a3b8">ck-{ck}</text>')

    # y-axis labels
    ylabels = []
    for i in range(5):
        v = max_norm * i / 4
        y = bar_y(v)
        ylabels.append(f'<text x="{PAD_LEFT-8}" y="{y:.1f}" text-anchor="end" font-size="10" fill="#94a3b8" dominant-baseline="middle">{v:.2f}</text>')
        ylabels.append(f'<line x1="{PAD_LEFT}" y1="{y:.1f}" x2="{W-PAD_RIGHT}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1" stroke-dasharray="3,3"/>')

    # axes
    axes = [
        f'<line x1="{PAD_LEFT}" y1="{PAD_TOP}" x2="{PAD_LEFT}" y2="{PAD_TOP+plot_h}" stroke="#334155" stroke-width="1"/>',
        f'<line x1="{PAD_LEFT}" y1="{PAD_TOP+plot_h}" x2="{W-PAD_RIGHT}" y2="{PAD_TOP+plot_h}" stroke="#334155" stroke-width="1"/>',
    ]

    # legend
    legend = []
    for idx, lg in enumerate(LAYER_GROUPS):
        lx = PAD_LEFT + idx * 170
        ly = H - 8
        legend.append(f'<rect x="{lx}" y="{ly-8}" width="12" height="12" fill="{COLORS[lg]}" rx="2"/>')
        legend.append(f'<text x="{lx+16}" y="{ly}" font-size="10" fill="#cbd5e1">{lg}</text>')

    # clip threshold line
    clip_v = 0.55
    clip_y = bar_y(clip_v)
    clip_line = (f'<line x1="{PAD_LEFT}" y1="{clip_y:.1f}" x2="{W-PAD_RIGHT}" y2="{clip_y:.1f}" '
                 f'stroke="#fbbf24" stroke-width="1" stroke-dasharray="5,3"/>'
                 f'<text x="{W-PAD_RIGHT+2}" y="{clip_y:.1f}" font-size="9" fill="#fbbf24" dominant-baseline="middle">clip</text>')

    title  = f'<text x="{W//2}" y="22" text-anchor="middle" font-size="14" font-weight="bold" fill="#f1f5f9">Gradient Norms per Layer Group — Last {N_CHECKPOINTS_BAR} Checkpoints</text>'
    ylabel = f'<text x="16" y="{H//2}" text-anchor="middle" font-size="11" fill="#94a3b8" transform="rotate(-90 16 {H//2})">Grad Norm</text>'

    inner = "\n".join(axes + ylabels + [clip_line] + bars + xlabels + legend + [title, ylabel])
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">\n{inner}\n</svg>'


# ── HTML page ────────────────────────────────────────────────────────────────

def _build_html() -> str:
    loss_svg = _svg_loss_curves()
    bar_svg  = _svg_grad_norm_bars()
    m = METRICS
    warn_color = "#C74634" if m["entropy_collapse_warnings"] > 5 else "#34d399"
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Policy Gradient Tracker | Port 8209</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
    h1{{color:#C74634;font-size:1.6rem;margin-bottom:4px}}
    .subtitle{{color:#64748b;font-size:.85rem;margin-bottom:24px}}
    .metrics{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}}
    .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px 22px;min-width:160px}}
    .card .label{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.08em}}
    .card .value{{font-size:1.5rem;font-weight:700;color:#38bdf8;margin-top:4px}}
    .card .value.red{{color:#C74634}}
    .card .value.green{{color:#34d399}}
    .card .value.warn{{color:#fbbf24}}
    .section{{margin-bottom:32px}}
    .section h2{{font-size:1rem;color:#94a3b8;margin-bottom:12px;border-bottom:1px solid #1e293b;padding-bottom:6px}}
    .chart-wrap{{overflow-x:auto}}
    footer{{margin-top:32px;font-size:.75rem;color:#334155;text-align:center}}
  </style>
</head>
<body>
  <h1>Policy Gradient Tracker</h1>
  <div class="subtitle">Port 8209 &nbsp;|&nbsp; Run: {m['run']} &nbsp;|&nbsp; Steps 0&#x2013;{m['total_steps']} &nbsp;|&nbsp; OCI Robot Cloud</div>

  <div class="metrics">
    <div class="card">
      <div class="label">Convergence Step</div>
      <div class="value">{m['convergence_step']:,}</div>
    </div>
    <div class="card">
      <div class="label">Post-Conv Policy Loss</div>
      <div class="value green">{m['post_convergence_policy_loss']}</div>
    </div>
    <div class="card">
      <div class="label">Grad Clip Events</div>
      <div class="value warn">{m['gradient_clip_events']}</div>
    </div>
    <div class="card">
      <div class="label">Entropy Collapse Warnings</div>
      <div class="value" style="color:{warn_color}">{m['entropy_collapse_warnings']}</div>
    </div>
    <div class="card">
      <div class="label">KL from BC</div>
      <div class="value">{m['kl_from_bc']}</div>
    </div>
  </div>

  <div class="section">
    <h2>Policy Loss, Value Loss &amp; Entropy Curves</h2>
    <div class="chart-wrap">{loss_svg}</div>
  </div>

  <div class="section">
    <h2>Gradient Norms per Layer Group</h2>
    <div class="chart-wrap">{bar_svg}</div>
  </div>

  <footer>OCI Robot Cloud &mdash; Policy Gradient Tracker &mdash; Port 8209</footer>
</body>
</html>
"""


# ── FastAPI app ──────────────────────────────────────────────────────────────
if USE_FASTAPI:
    app = FastAPI(title="Policy Gradient Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_html()

    @app.get("/api/losses")
    async def api_losses():
        return {
            "steps": STEPS,
            "policy_loss": POLICY_LOSS,
            "value_loss":  VALUE_LOSS,
            "entropy":     ENTROPY,
        }

    @app.get("/api/grad_norms")
    async def api_grad_norms():
        return {"layer_groups": LAYER_GROUPS, "norms": GRAD_NORMS}

    @app.get("/api/metrics")
    async def api_metrics():
        return METRICS

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "policy_gradient_tracker", "port": 8209}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8209)
    else:
        print("FastAPI not found — falling back to stdlib http.server on port 8209")
        server = HTTPServer(("0.0.0.0", 8209), _Handler)
        print("Serving on http://0.0.0.0:8209")
        server.serve_forever()

"""training_loss_debugger.py — Diagnoses training loss anomalies, spikes, and plateaus in GR00T fine-tuning. Port 8267."""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math
from datetime import datetime

# ── Mock Data ────────────────────────────────────────────────────────────────

random.seed(7)

TOTAL_STEPS = 1000

def gen_loss_curve():
    """Generate 1000-step training loss with:
    - gradient_spike at step 147 (0.89 → 2.31, recovered in 8 steps)
    - plateau step 680–750 (delta < 0.001)
    - overfitting onset at step 820
    - final loss 0.099
    """
    steps = list(range(TOTAL_STEPS))
    train_loss = []
    val_loss = []

    base = 1.8
    for s in steps:
        # Normal decay
        t = s / TOTAL_STEPS
        smooth = base * math.exp(-3.5 * t) + 0.095 + 0.04 * math.exp(-8 * t)
        noise = random.gauss(0, 0.008)

        # Gradient spike: step 147
        if s == 147:
            val = 2.31
        elif 147 < s <= 155:
            # Recovery over 8 steps back to smooth trajectory
            recovery_t = (s - 147) / 8
            val = 2.31 * (1 - recovery_t) + smooth * recovery_t + noise
        # Plateau: steps 680–750
        elif 680 <= s <= 750:
            val = 0.235 + random.gauss(0, 0.0004)
        else:
            val = smooth + noise

        train_loss.append(round(max(0.09, val), 4))

        # Validation loss diverges from step 820 (overfitting onset)
        if s < 820:
            val_noise = random.gauss(0, 0.012)
            val_loss.append(round(max(0.10, smooth * 1.04 + val_noise), 4))
        else:
            overfit_gap = (s - 820) / TOTAL_STEPS * 0.18
            val_noise = random.gauss(0, 0.014)
            val_loss.append(round(max(0.10, smooth * 1.04 + overfit_gap + val_noise), 4))

    # Pin final train loss
    train_loss[-1] = 0.099
    return steps, train_loss, val_loss


ANOMALIES = [
    {"step": 147, "type": "gradient_spike",  "severity": "high",   "detail": "Loss 0.89→2.31 (outlier batch trajectory)", "color": "#ef4444"},
    {"step": 715, "type": "plateau",          "severity": "medium", "detail": "Steps 680-750: Δloss<0.001 (LR warmup restart)", "color": "#f59e0b"},
    {"step": 820, "type": "overfitting_onset","severity": "medium", "detail": "Val loss diverges from train loss", "color": "#a78bfa"},
]


def gen_loss_components():
    """Generate stacked area data: action_bc_loss / kl_divergence / auxiliary_loss.
    action_bc dominates ~78% throughout; kl_div increases relative share after step 500.
    """
    steps = list(range(0, TOTAL_STEPS, 5))  # sample every 5 steps for area chart
    action_bc, kl_div, aux = [], [], []
    for s in steps:
        t = s / TOTAL_STEPS
        total_approx = 1.8 * math.exp(-3.5 * t) + 0.095
        # Spike region
        if 145 <= s <= 155:
            total_approx = total_approx * 2.3
        # Plateau
        if 680 <= s <= 750:
            total_approx = 0.235

        # kl weight increases after step 500
        kl_share = 0.08 + 0.10 * max(0, (s - 500) / 500)
        aux_share = 0.06
        bc_share = 1.0 - kl_share - aux_share

        action_bc.append(round(total_approx * bc_share, 5))
        kl_div.append(round(total_approx * kl_share, 5))
        aux.append(round(total_approx * aux_share, 5))
    return steps, action_bc, kl_div, aux


def gen_diagnostics():
    return {
        "spike_frequency": "1 spike / 1000 steps",
        "plateau_duration": "70 steps (680-750)",
        "component_balance_ratio": "BC:KL:Aux = 78:14:8 (final)",
        "debugging_recommendation": "Clip grad norm ≤1.0; LR warmup 500 steps; filter outlier trajectories",
        "final_train_loss": "0.099",
        "overfitting_onset_step": "820",
        "spike_recovery_steps": "8",
        "action_bc_dominance": "78% throughout",
    }


# ── SVG Builders ─────────────────────────────────────────────────────────────

def build_loss_curve_svg(steps, train_loss, val_loss):
    W, H = 820, 340
    pad_l, pad_r, pad_t, pad_b = 60, 20, 40, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    sample = 5  # plot every 5th point for performance
    s_steps = steps[::sample]
    s_train = train_loss[::sample]
    s_val = val_loss[::sample]

    max_loss = 2.5
    min_loss = 0.0

    def px(s):
        return pad_l + (s / TOTAL_STEPS) * chart_w

    def py(v):
        return pad_t + chart_h - ((v - min_loss) / (max_loss - min_loss)) * chart_h

    def polyline_pts(xs, ys):
        return " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in zip(xs, ys))

    train_line = f'<polyline points="{polyline_pts(s_steps, s_train)}" fill="none" stroke="#38bdf8" stroke-width="1.8" stroke-linejoin="round"/>'
    val_line   = f'<polyline points="{polyline_pts(s_steps, s_val)}" fill="none" stroke="#a78bfa" stroke-width="1.4" stroke-dasharray="5,3" stroke-linejoin="round"/>'

    # Grid
    grid = []
    for v in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]:
        y = py(v)
        grid.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+chart_w}" y2="{y:.1f}" stroke="#1e293b" stroke-width="0.7"/>')
        grid.append(f'<text x="{pad_l-4}" y="{y+3:.1f}" fill="#64748b" font-size="9" text-anchor="end">{v:.1f}</text>')

    for s in range(0, TOTAL_STEPS+1, 100):
        x = px(s)
        grid.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t+chart_h}" stroke="#1e293b" stroke-width="0.5"/>')
        grid.append(f'<text x="{x:.1f}" y="{pad_t+chart_h+14}" fill="#64748b" font-size="9" text-anchor="middle">{s}</text>')

    # Anomaly markers
    markers = []
    for an in ANOMALIES:
        x = px(an["step"])
        y_top = py(max_loss * 0.96)
        y_bot = pad_t + chart_h
        markers.append(f'<line x1="{x:.1f}" y1="{y_top:.1f}" x2="{x:.1f}" y2="{y_bot:.1f}" stroke="{an["color"]}" stroke-width="1" stroke-dasharray="4,3" opacity="0.8"/>')
        markers.append(f'<circle cx="{x:.1f}" cy="{py(train_loss[an["step"]]):.1f}" r="5" fill="{an["color"]}" opacity="0.9"/>')
        label_x = x + 4
        markers.append(f'<text x="{label_x:.1f}" y="{y_top-2:.1f}" fill="{an["color"]}" font-size="8" font-weight="bold">{an["type"]}</text>')

    # Plateau shading
    x_680 = px(680)
    x_750 = px(750)
    plateau_rect = f'<rect x="{x_680:.1f}" y="{pad_t}" width="{x_750-x_680:.1f}" height="{chart_h}" fill="#f59e0b" opacity="0.07"/>'

    # Legend
    legend = [
        f'<rect x="{pad_l}" y="{H-14}" width="18" height="3" fill="#38bdf8"/>',
        f'<text x="{pad_l+22}" y="{H-8}" fill="#94a3b8" font-size="9">Train Loss</text>',
        f'<rect x="{pad_l+90}" y="{H-14}" width="18" height="3" fill="#a78bfa" stroke-dasharray="5,3"/>',
        f'<text x="{pad_l+112}" y="{H-8}" fill="#94a3b8" font-size="9">Val Loss (dashed)</text>',
    ]

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px;">',
        f'<text x="{W//2}" y="18" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="middle">GR00T Fine-Tuning Loss Curve (1000 Steps) — Annotated Anomalies</text>',
    ] + grid + [plateau_rect, train_line, val_line] + markers + legend
    svg_parts.append(f'<text x="{pad_l+chart_w//2}" y="{H-3}" fill="#475569" font-size="8" text-anchor="middle">Training Step</text>')
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


def build_loss_component_svg(comp_steps, action_bc, kl_div, aux):
    W, H = 820, 280
    pad_l, pad_r, pad_t, pad_b = 60, 20, 35, 45
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    n = len(comp_steps)
    total = [action_bc[i] + kl_div[i] + aux[i] for i in range(n)]
    max_total = max(total) * 1.05

    def px(idx):
        return pad_l + (idx / (n - 1)) * chart_w

    def py(v):
        return pad_t + chart_h - (v / max_total) * chart_h

    # Build stacked area paths
    def area_path(bottom_vals, top_vals, color):
        fwd = " ".join(f"{px(i):.1f},{py(top_vals[i]):.1f}" for i in range(n))
        bwd = " ".join(f"{px(i):.1f},{py(bottom_vals[i]):.1f}" for i in range(n - 1, -1, -1))
        return f'<polygon points="{fwd} {bwd}" fill="{color}" opacity="0.75"/>'

    # Stack: aux (bottom) → kl → action_bc (top)
    zero = [0.0] * n
    aux_top   = aux
    kl_top    = [aux[i] + kl_div[i] for i in range(n)]
    bc_top    = total

    path_aux = area_path(zero, aux_top, "#fb923c")
    path_kl  = area_path(aux_top, kl_top, "#f59e0b")
    path_bc  = area_path(kl_top, bc_top, "#38bdf8")

    # kl_div increase marker at step 500
    step500_idx = next((i for i, s in enumerate(comp_steps) if s >= 500), n // 2)
    x500 = px(step500_idx)
    kl_marker = [
        f'<line x1="{x500:.1f}" y1="{pad_t}" x2="{x500:.1f}" y2="{pad_t+chart_h}" stroke="#f59e0b" stroke-dasharray="4,2" stroke-width="1" opacity="0.7"/>',
        f'<text x="{x500+3:.1f}" y="{pad_t+12}" fill="#f59e0b" font-size="8">KL weight ↑ (step 500)</text>',
    ]

    # Grid
    grid = []
    for v in [0.0, 0.5, 1.0, 1.5, 2.0]:
        if v > max_total:
            continue
        y = py(v)
        grid.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+chart_w}" y2="{y:.1f}" stroke="#1e293b" stroke-width="0.6"/>')
        grid.append(f'<text x="{pad_l-4}" y="{y+3:.1f}" fill="#64748b" font-size="9" text-anchor="end">{v:.1f}</text>')

    for s in [0, 250, 500, 750, 1000]:
        idx = min(range(n), key=lambda i: abs(comp_steps[i] - s))
        x = px(idx)
        grid.append(f'<text x="{x:.1f}" y="{pad_t+chart_h+14}" fill="#64748b" font-size="9" text-anchor="middle">{s}</text>')

    # Legend
    legend_items = [
        ("action_bc_loss (78%)",  "#38bdf8"),
        ("kl_divergence",         "#f59e0b"),
        ("auxiliary_loss",        "#fb923c"),
    ]
    legend = []
    lx = pad_l
    for lbl, clr in legend_items:
        legend.append(f'<rect x="{lx}" y="{H-14}" width="12" height="10" fill="{clr}" opacity="0.85" rx="2"/>')
        legend.append(f'<text x="{lx+15}" y="{H-5}" fill="#94a3b8" font-size="9">{lbl}</text>')
        lx += 160

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px;">',
        f'<text x="{W//2}" y="18" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="middle">Loss Component Breakdown — action_bc / kl_divergence / auxiliary (Stacked Area)</text>',
    ] + grid + [path_aux, path_kl, path_bc] + kl_marker + legend
    svg_parts.append(f'<text x="{pad_l+chart_w//2}" y="{H-3}" fill="#475569" font-size="8" text-anchor="middle">Training Step</text>')
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


# ── HTML Dashboard ────────────────────────────────────────────────────────────

def build_html():
    steps, train_loss, val_loss = gen_loss_curve()
    comp_steps, action_bc, kl_div, aux = gen_loss_components()
    diag = gen_diagnostics()

    svg1 = build_loss_curve_svg(steps, train_loss, val_loss)
    svg2 = build_loss_component_svg(comp_steps, action_bc, kl_div, aux)

    sev_badge = {"high": ("#7f1d1d", "#f87171"), "medium": ("#451a03", "#fb923c"), "low": ("#14532d", "#4ade80")}
    anomaly_rows = "".join(
        f'<tr>'
        f'<td style="padding:7px 12px;color:#e2e8f0;font-weight:600;">{a["step"]}</td>'
        f'<td style="padding:7px 12px;"><span style="background:{sev_badge[a["severity"]][0]};color:{sev_badge[a["severity"]][1]};padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">{a["type"]}</span></td>'
        f'<td style="padding:7px 12px;color:#94a3b8;font-size:12px;">{a["detail"]}</td>'
        f'</tr>'
        for a in ANOMALIES
    )

    metric_cards = "".join(
        f'<div style="background:#1e293b;border-radius:8px;padding:14px 18px;margin:6px;min-width:200px;">'  
        f'<div style="color:#64748b;font-size:11px;margin-bottom:4px;">{k.replace("_"," ").upper()}</div>'  
        f'<div style="color:#38bdf8;font-size:16px;font-weight:700;">{v}</div>'  
        f'</div>'
        for k, v in diag.items()
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Training Loss Debugger — Port 8267</title>
<style>
  body {{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;}}
  h1 {{color:#C74634;}} h2 {{color:#38bdf8;font-size:14px;margin-top:28px;}}
  table {{border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden;width:100%;}}
  th {{background:#0f172a;color:#64748b;font-size:11px;padding:8px 12px;text-align:left;}}
  tr:hover td {{background:#1a2a3a;}}
</style>
</head>
<body style="padding:24px 32px;">
<h1 style="font-size:22px;margin-bottom:4px;">Training Loss Debugger</h1>
<p style="color:#64748b;margin-top:0;">GR00T fine-tuning anomaly diagnosis · Spike · Plateau · Overfitting detection · Port 8267</p>

<h2>Detected Anomalies</h2>
<table><thead><tr><th>Step</th><th>Type</th><th>Detail</th></tr></thead><tbody>{anomaly_rows}</tbody></table>

<h2 style="margin-top:28px;">Diagnostics</h2>
<div style="display:flex;flex-wrap:wrap;margin:0 -6px;">{metric_cards}</div>

<h2 style="margin-top:28px;">Annotated Loss Curve</h2>
{svg1}
<p style="color:#64748b;font-size:11px;">Gradient spike at step 147 (outlier batch): 0.89→2.31, recovery in 8 steps. Plateau steps 680-750 broken by LR warmup restart. Overfitting onset at step 820. Final train loss: 0.099.</p>

<h2 style="margin-top:28px;">Loss Component Breakdown (Stacked Area)</h2>
{svg2}
<p style="color:#64748b;font-size:11px;">action_bc_loss dominates at 78% throughout training. kl_divergence weight increases after step 500 (scheduler-driven). auxiliary_loss remains stable at ~6-8%.</p>

<p style="color:#334155;font-size:10px;margin-top:40px;">OCI Robot Cloud · training_loss_debugger.py · {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}</p>
</body></html>"""
    return html


# ── App ───────────────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="Training Loss Debugger", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/diagnostics")
    async def diagnostics():
        return gen_diagnostics()

    @app.get("/anomalies")
    async def anomalies():
        return ANOMALIES

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "training_loss_debugger", "port": 8267}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            content = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, fmt, *args):
            pass

    def run_stdlib():
        server = HTTPServer(("", 8267), Handler)
        print("[training_loss_debugger] stdlib fallback on http://0.0.0.0:8267")
        server.serve_forever()


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8267)
    else:
        run_stdlib()

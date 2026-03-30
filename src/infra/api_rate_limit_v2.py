"""api_rate_limit_v2.py — Enhanced rate limiting with per-endpoint quotas, burst handling, and partner tier enforcement. Port 8266."""

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

# ── Mock Data ────────────────────────────────────────────────────────────────

random.seed(42)

TIERS = {
    "enterprise": {"quota_hr": 10000, "color": "#C74634"},
    "growth":     {"quota_hr": 2000,  "color": "#38bdf8"},
    "starter":    {"quota_hr": 500,   "color": "#818cf8"},
    "burst_zone": {"quota_hr": 1200,  "color": "#fb923c"},
}

ENDPOINTS = ["/predict", "/finetune", "/embed", "/health", "/status", "/eval", "/train", "/infer"]

PARTNERS = ["Acme Robotics", "TechCorp AI", "FutureBot", "NovaMech", "OmniArm"]

def gen_hourly_requests():
    """Generate 24h stacked request data per tier with throttle events."""
    hours = list(range(24))
    data = {tier: [] for tier in TIERS}
    throttle_events = []

    for h in hours:
        base_enterprise = int(7000 + 2000 * math.sin(math.pi * h / 12) + random.gauss(0, 200))
        base_enterprise = max(0, base_enterprise)
        # PI exhausts /predict quota at hour 14 — burst credit used
        if h == 14:
            base_enterprise = 10200  # over limit — throttle
            throttle_events.append({"hour": h, "tier": "enterprise", "note": "Burst credit used"})
        if h == 20:
            throttle_events.append({"hour": h, "tier": "growth", "note": "Quota exhausted"})

        data["enterprise"].append(min(base_enterprise, 10000))
        data["growth"].append(int(1200 + 600 * math.sin(math.pi * h / 10) + random.gauss(0, 80)))
        data["starter"].append(int(200 + 200 * (h / 24) + random.gauss(0, 20)))
        data["burst_zone"].append(max(0, int(300 * math.sin(math.pi * h / 8) + random.gauss(0, 50))))

    return hours, data, throttle_events

def gen_partner_endpoint_matrix():
    """5×8 matrix: utilization % of hourly quota for each partner×endpoint."""
    matrix = []
    for p in PARTNERS:
        row = []
        for ep in ENDPOINTS:
            if ep == "/finetune":
                util = random.uniform(75, 99)  # most quota-constrained
            elif ep == "/predict" and p == "Acme Robotics":
                util = 102.0  # burst used
            else:
                util = random.uniform(10, 70)
            row.append(round(util, 1))
        matrix.append(row)
    return matrix

def gen_key_metrics():
    return {
        "quota_utilization": {
            "enterprise": "87.3%",
            "growth": "61.2%",
            "starter": "44.8%",
            "burst_zone": "38.1%",
        },
        "throttle_frequency": "2 events / 24h",
        "burst_credit_usage_rate": "14.7% of enterprise calls",
        "fairness_score": "0.94 (Jain's index)",
        "requests_within_quota": "99.4%",
        "total_requests_24h": "214,388",
    }

# ── SVG Builders ─────────────────────────────────────────────────────────────

def build_stacked_bar_svg(hours, data, throttle_events):
    W, H = 820, 320
    pad_l, pad_r, pad_t, pad_b = 60, 20, 30, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    max_val = 11000
    bar_w = chart_w / 24 * 0.7
    bar_gap = chart_w / 24

    tier_order = ["starter", "growth", "burst_zone", "enterprise"]
    tier_colors = {"enterprise": "#C74634", "growth": "#38bdf8", "starter": "#818cf8", "burst_zone": "#fb923c"}
    tier_quotas = {"enterprise": 10000, "growth": 2000, "starter": 500, "burst_zone": 1200}

    def y_of(val):
        return pad_t + chart_h - (val / max_val) * chart_h

    def x_of(h):
        return pad_l + h * bar_gap + bar_gap * 0.15

    bars = []
    for h in hours:
        stack_bottom = pad_t + chart_h
        for tier in tier_order:
            v = data[tier][h]
            bar_h = (v / max_val) * chart_h
            x = x_of(h)
            y = stack_bottom - bar_h
            bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{tier_colors[tier]}" opacity="0.85"/>')
            stack_bottom = y

    # Ceiling lines per tier (enterprise only for legibility)
    ceiling_y = y_of(10000)
    ceiling = f'<line x1="{pad_l}" y1="{ceiling_y:.1f}" x2="{pad_l+chart_w}" y2="{ceiling_y:.1f}" stroke="#f87171" stroke-dasharray="6,3" stroke-width="1.5"/>'
    ceiling_label = f'<text x="{pad_l+chart_w-2}" y="{ceiling_y-4:.1f}" fill="#f87171" font-size="9" text-anchor="end">Enterprise 10k/hr ceiling</text>'

    # Throttle event annotations
    annotations = []
    for ev in throttle_events:
        x = x_of(ev["hour"]) + bar_w / 2
        y_top = y_of(max_val * 0.95)
        annotations.append(f'<line x1="{x:.1f}" y1="{y_top:.1f}" x2="{x:.1f}" y2="{y_of(0)-4:.1f}" stroke="#fde047" stroke-width="1" stroke-dasharray="3,2"/>')
        annotations.append(f'<text x="{x:.1f}" y="{y_top-4:.1f}" fill="#fde047" font-size="8" text-anchor="middle">⚡{ev["hour"]}h</text>')
        annotations.append(f'<text x="{x:.1f}" y="{y_top+8:.1f}" fill="#fde047" font-size="7" text-anchor="middle">{ev["note"]}</text>')

    # Axes
    x_labels = [f'<text x="{x_of(h)+bar_w/2:.1f}" y="{pad_t+chart_h+14}" fill="#94a3b8" font-size="8" text-anchor="middle">{h:02d}</text>' for h in range(0, 24, 4)]
    y_labels = []
    for v in [0, 2500, 5000, 7500, 10000]:
        y = y_of(v)
        y_labels.append(f'<text x="{pad_l-4}" y="{y+3:.1f}" fill="#94a3b8" font-size="8" text-anchor="end">{v//1000}k</text>')
        y_labels.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+chart_w}" y2="{y:.1f}" stroke="#1e293b" stroke-width="0.5"/>')

    # Legend
    legend = []
    lx = pad_l
    for tier in reversed(tier_order):
        legend.append(f'<rect x="{lx}" y="{H-12}" width="10" height="8" fill="{tier_colors[tier]}"/>')
        legend.append(f'<text x="{lx+13}" y="{H-5}" fill="#94a3b8" font-size="8">{tier}</text>')
        lx += 90

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px;">',
        f'<text x="{W//2}" y="18" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="middle">API Requests per Hour (24h) — Stacked by Tier</text>',
    ] + y_labels + bars + [ceiling, ceiling_label] + annotations + x_labels + legend
    svg_parts.append(f'<text x="{pad_l+chart_w//2}" y="{H-2}" fill="#64748b" font-size="8" text-anchor="middle">Hour of Day (UTC)</text>')
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


def build_heatmap_svg(matrix):
    W, H = 820, 280
    pad_l, pad_r, pad_t, pad_b = 110, 20, 40, 30
    n_rows = len(PARTNERS)
    n_cols = len(ENDPOINTS)
    cell_w = (W - pad_l - pad_r) / n_cols
    cell_h = (H - pad_t - pad_b) / n_rows

    def util_color(u):
        # green → yellow → orange → red
        if u > 100:
            return "#dc2626"
        ratio = u / 100.0
        if ratio < 0.5:
            r = int(56 + (251 - 56) * ratio * 2)
            g = int(189 - (189 - 191) * ratio * 2)
            b = int(248 * (1 - ratio * 2))
        else:
            ratio2 = (ratio - 0.5) * 2
            r = int(251 + (199 - 251) * (1 - ratio2))
            g = int(191 * (1 - ratio2) + 29 * ratio2)
            b = int(ratio2 * 0)
        return f"rgb({max(0,min(255,r))},{max(0,min(255,g))},{max(0,min(255,b))})"

    cells = []
    for ri, partner in enumerate(PARTNERS):
        for ci, ep in enumerate(ENDPOINTS):
            u = matrix[ri][ci]
            x = pad_l + ci * cell_w
            y = pad_t + ri * cell_h
            color = util_color(u)
            cells.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w-2:.1f}" height="{cell_h-2:.1f}" fill="{color}" rx="2"/>')
            cells.append(f'<text x="{x+cell_w/2:.1f}" y="{y+cell_h/2+4:.1f}" fill="#0f172a" font-size="8" font-weight="bold" text-anchor="middle">{u:.0f}%</text>')

    row_labels = [f'<text x="{pad_l-4}" y="{pad_t + ri*cell_h + cell_h/2+4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">{p}</text>' for ri, p in enumerate(PARTNERS)]
    col_labels = [f'<text x="{pad_l + ci*cell_w + cell_w/2:.1f}" y="{pad_t-6}" fill="#94a3b8" font-size="8" text-anchor="middle" transform="rotate(-25 {pad_l+ci*cell_w+cell_w/2:.1f},{pad_t-6})">{ep}</text>' for ci, ep in enumerate(ENDPOINTS)]

    # Color scale legend
    legend_x = pad_l
    legend_y = H - 12
    scale_labels = ["0%", "25%", "50%", "75%", "100%+"]
    scale_colors = [util_color(v) for v in [0, 25, 50, 75, 101]]
    scale_els = []
    for i, (lbl, clr) in enumerate(zip(scale_labels, scale_colors)):
        sx = legend_x + i * 80
        scale_els.append(f'<rect x="{sx}" y="{legend_y}" width="14" height="10" fill="{clr}" rx="2"/>')
        scale_els.append(f'<text x="{sx+16}" y="{legend_y+8}" fill="#94a3b8" font-size="8">{lbl}</text>')

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px;">',
        f'<text x="{W//2}" y="16" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="middle">Partner × Endpoint Quota Utilization Heatmap</text>',
    ] + row_labels + col_labels + cells + scale_els
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


# ── HTML Dashboard ────────────────────────────────────────────────────────────

def build_html():
    hours, req_data, throttle_events = gen_hourly_requests()
    matrix = gen_partner_endpoint_matrix()
    metrics = gen_key_metrics()

    svg1 = build_stacked_bar_svg(hours, req_data, throttle_events)
    svg2 = build_heatmap_svg(matrix)

    metric_cards = "".join(
        f'<div style="background:#1e293b;border-radius:8px;padding:14px 18px;margin:6px;min-width:180px;">'  
        f'<div style="color:#64748b;font-size:11px;margin-bottom:4px;">{k.replace("_"," ").upper()}</div>'  
        f'<div style="color:#38bdf8;font-size:18px;font-weight:700;">{v}</div>'  
        f'</div>'
        for k, v in metrics.items() if not isinstance(v, dict)
    )

    tier_rows = "".join(
        f'<tr><td style="padding:6px 12px;color:#e2e8f0;">{tier}</td>'
        f'<td style="padding:6px 12px;color:#38bdf8;">{info["quota_hr"]:,}/hr</td>'
        f'<td style="padding:6px 12px;"><span style="display:inline-block;width:12px;height:12px;background:{info["color"]};border-radius:2px;"></span></td></tr>'
        for tier, info in TIERS.items()
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>API Rate Limit v2 — Port 8266</title>
<style>
  body {{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;}}
  h1 {{color:#C74634;}} h2 {{color:#38bdf8;font-size:14px;margin-top:28px;}}
  table {{border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden;}}
  th {{background:#0f172a;color:#64748b;font-size:11px;padding:8px 12px;text-align:left;}}
  tr:hover td {{background:#1a2a3a;}}
  .badge {{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;}}
  .ok {{background:#14532d;color:#4ade80;}} .warn {{background:#451a03;color:#fb923c;}}
</style>
</head>
<body style="padding:24px 32px;">
<h1 style="font-size:22px;margin-bottom:4px;">API Rate Limit v2</h1>
<p style="color:#64748b;margin-top:0;">Enhanced per-endpoint quotas · Burst handling · Partner tier enforcement · Port 8266</p>
<div style="display:flex;flex-wrap:wrap;margin:16px -6px;">{metric_cards}</div>

<h2>Tier Quota Configuration</h2>
<table><thead><tr><th>Tier</th><th>Quota/hr</th><th>Color</th></tr></thead><tbody>{tier_rows}</tbody></table>

<h2 style="margin-top:28px;">Hourly Request Volume by Tier (24h)</h2>
{svg1}
<p style="color:#64748b;font-size:11px;">⚡ Throttle events annotated. Enterprise ceiling = 10k/hr. Burst credit consumed by Acme Robotics at 14h.</p>

<h2 style="margin-top:28px;">Partner × Endpoint Quota Utilization Heatmap</h2>
{svg2}
<p style="color:#64748b;font-size:11px;">/finetune is most quota-constrained across all partners. Acme Robotics /predict exceeded quota (burst activated). 99.4% of all requests within quota.</p>

<p style="color:#334155;font-size:10px;margin-top:40px;">OCI Robot Cloud · api_rate_limit_v2.py · {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}</p>
</body></html>"""
    return html


# ── App ───────────────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="API Rate Limit v2", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/metrics")
    async def metrics():
        return gen_key_metrics()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "api_rate_limit_v2", "port": 8266}

else:
    # Fallback: stdlib http.server
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
        server = HTTPServer(("", 8266), Handler)
        print("[api_rate_limit_v2] stdlib fallback on http://0.0.0.0:8266")
        server.serve_forever()


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8266)
    else:
        run_stdlib()

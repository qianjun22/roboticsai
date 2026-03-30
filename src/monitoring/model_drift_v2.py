"""model_drift_v2.py — Advanced model drift detection v2: multivariate drift, concept drift, auto-remediation.
FastAPI service on port 8268.
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
import json
from datetime import datetime, timedelta

# ── Mock data ────────────────────────────────────────────────────────────────

random.seed(42)

DRIFT_TYPES = ["covariate_shift", "label_drift", "concept_drift", "prediction_confidence"]
ENVIRONMENTS = ["PI_SF", "Apt_Austin", "1X_Boston", "OCI_ashburn", "OCI_frankfurt"]
FEATURES = ["camera_noise", "joint_angle", "obj_texture", "lighting", "depth_err", "latency", "cmd_vel", "grip_force"]

# Drift events
DRIFT_EVENTS = [
    {"day": 18, "type": "covariate_shift", "env": "PI_SF",      "cause": "PI lighting change (winter sun angle)",    "severity": 0.71, "remediated": True},
    {"day": 34, "type": "concept_drift",   "env": "Apt_Austin", "cause": "Apt new table height (+12cm)",             "severity": 0.58, "remediated": True},
    {"day": 52, "type": "prediction_confidence", "env": "1X_Boston", "cause": "New object textures (metallic cans)", "severity": 0.63, "remediated": True},
]

def generate_signal(days: int, drift_day: int, base: float, spike: float, noise: float) -> list:
    vals = []
    for d in range(days):
        v = base + noise * (random.random() - 0.5)
        if d >= drift_day:
            decay = 1.0 - math.exp(-(d - drift_day) / 8.0)
            v += spike * decay
        vals.append(round(max(0.0, min(1.0, v)), 3))
    return vals

DAYS = 60
SIGNALS = {
    "covariate_shift":        generate_signal(DAYS, 18, 0.12, 0.55, 0.04),
    "label_drift":            generate_signal(DAYS, 34, 0.08, 0.30, 0.03),
    "concept_drift":          generate_signal(DAYS, 34, 0.10, 0.45, 0.05),
    "prediction_confidence":  generate_signal(DAYS, 52, 0.05, 0.58, 0.04),
}

# Drift severity heatmap: environments x features
HEATMAP = {
    "PI_SF":         {"camera_noise": 0.71, "joint_angle": 0.22, "obj_texture": 0.31, "lighting": 0.68, "depth_err": 0.19, "latency": 0.08, "cmd_vel": 0.14, "grip_force": 0.11},
    "Apt_Austin":    {"camera_noise": 0.18, "joint_angle": 0.58, "obj_texture": 0.27, "lighting": 0.22, "depth_err": 0.33, "latency": 0.12, "cmd_vel": 0.41, "grip_force": 0.35},
    "1X_Boston":     {"camera_noise": 0.24, "joint_angle": 0.19, "obj_texture": 0.63, "lighting": 0.15, "depth_err": 0.28, "latency": 0.09, "cmd_vel": 0.22, "grip_force": 0.17},
    "OCI_ashburn":   {"camera_noise": 0.07, "joint_angle": 0.11, "obj_texture": 0.09, "lighting": 0.05, "depth_err": 0.13, "latency": 0.21, "cmd_vel": 0.08, "grip_force": 0.06},
    "OCI_frankfurt": {"camera_noise": 0.09, "joint_angle": 0.08, "obj_texture": 0.12, "lighting": 0.06, "depth_err": 0.10, "latency": 0.18, "cmd_vel": 0.07, "grip_force": 0.05},
}

KEY_METRICS = {
    "drift_detection_latency_ms": 340,
    "false_positive_rate_pct": 2.1,
    "auto_remediation_success_pct": 94.7,
    "drift_root_cause_categories": 4,
    "total_drift_events_30d": 7,
    "envs_monitored": len(ENVIRONMENTS),
    "features_tracked": len(FEATURES),
}

# ── SVG builders ─────────────────────────────────────────────────────────────

def build_multisignal_svg() -> str:
    W, H = 900, 420
    pad_l, pad_r, pad_t, pad_b = 130, 40, 30, 40
    lane_h = (H - pad_t - pad_b) // len(DRIFT_TYPES)
    chart_w = W - pad_l - pad_r

    COLORS = {
        "covariate_shift":       ("#38bdf8", "Covariate Shift"),
        "label_drift":           ("#a78bfa", "Label Drift"),
        "concept_drift":         ("#fb923c", "Concept Drift"),
        "prediction_confidence": ("#f43f5e", "Pred. Confidence Drop"),
    }

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:12px">',
        f'<text x="{W//2}" y="20" text-anchor="middle" fill="#e2e8f0" font-size="14" font-family="monospace" font-weight="bold">Multi-Signal Drift Dashboard — 60-Day Window</text>',
    ]

    for i, dtype in enumerate(DRIFT_TYPES):
        color, label = COLORS[dtype]
        vals = SIGNALS[dtype]
        y_base = pad_t + i * lane_h
        y_mid = y_base + lane_h // 2
        y_lo = y_base + 8
        y_hi = y_base + lane_h - 8
        span = y_hi - y_lo

        # Lane background
        bg = "#1e293b" if i % 2 == 0 else "#172033"
        lines.append(f'<rect x="{pad_l}" y="{y_base}" width="{chart_w}" height="{lane_h}" fill="{bg}"/>')

        # Label
        lines.append(f'<text x="{pad_l - 8}" y="{y_mid + 5}" text-anchor="end" fill="{color}" font-size="11" font-family="monospace">{label}</text>')

        # Threshold line at 0.45
        thresh_y = int(y_hi - 0.45 * span)
        lines.append(f'<line x1="{pad_l}" y1="{thresh_y}" x2="{pad_l + chart_w}" y2="{thresh_y}" stroke="#ef4444" stroke-width="1" stroke-dasharray="4,4" opacity="0.5"/>')

        # Build polyline
        pts = []
        for d, v in enumerate(vals):
            x = pad_l + int(d / (DAYS - 1) * chart_w)
            y = int(y_hi - v * span)
            pts.append(f"{x},{y}")
        lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2" opacity="0.9"/>')

        # Fill under curve
        fill_pts = f"{pad_l},{y_hi} " + " ".join(pts) + f" {pad_l + chart_w},{y_hi}"
        lines.append(f'<polygon points="{fill_pts}" fill="{color}" opacity="0.08"/>')

        # Annotate drift events for this type
        for ev in DRIFT_EVENTS:
            if ev["type"] == dtype:
                ex = pad_l + int(ev["day"] / (DAYS - 1) * chart_w)
                ey = int(y_hi - ev["severity"] * span)
                sev_color = "#ef4444" if ev["severity"] > 0.6 else "#f59e0b"
                lines.append(f'<circle cx="{ex}" cy="{ey}" r="6" fill="{sev_color}" stroke="#fff" stroke-width="1.5"/>')
                lines.append(f'<line x1="{ex}" y1="{ey - 6}" x2="{ex}" y2="{y_base + 2}" stroke="{sev_color}" stroke-width="1" stroke-dasharray="2,2"/>')
                short = ev["cause"][:28] + ("…" if len(ev["cause"]) > 28 else "")
                lines.append(f'<text x="{ex + 8}" y="{y_base + 16}" fill="{sev_color}" font-size="9" font-family="monospace">Day {ev["day"]}: {short}</text>')

    # X-axis labels
    for tick in [0, 10, 20, 30, 40, 50, 60]:
        x = pad_l + int(tick / (DAYS) * chart_w)
        lines.append(f'<text x="{x}" y="{H - pad_b + 14}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">d{tick}</text>')
        lines.append(f'<line x1="{x}" y1="{H - pad_b}" x2="{x}" y2="{H - pad_b + 4}" stroke="#475569" stroke-width="1"/>')

    lines.append('</svg>')
    return "\n".join(lines)


def build_heatmap_svg() -> str:
    W, H = 820, 300
    pad_l, pad_r, pad_t, pad_b = 110, 20, 50, 30
    n_rows = len(ENVIRONMENTS)
    n_cols = len(FEATURES)
    cell_w = (W - pad_l - pad_r) // n_cols
    cell_h = (H - pad_t - pad_b) // n_rows

    def score_color(v: float) -> str:
        if v < 0.25:
            return f"rgba(56,189,248,{0.3 + v})"
        elif v < 0.50:
            return f"rgba(251,146,60,{0.4 + v * 0.5})"
        else:
            return f"rgba(239,68,68,{0.5 + v * 0.4})"

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:12px">',
        f'<text x="{W//2}" y="20" text-anchor="middle" fill="#e2e8f0" font-size="14" font-family="monospace" font-weight="bold">Drift Severity Heatmap — Environments × Features</text>',
    ]

    # Column headers
    for j, feat in enumerate(FEATURES):
        x = pad_l + j * cell_w + cell_w // 2
        lines.append(f'<text x="{x}" y="{pad_t - 8}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace" transform="rotate(-25,{x},{pad_t - 8})">{feat}</text>')

    # Row headers + cells
    for i, env in enumerate(ENVIRONMENTS):
        y = pad_t + i * cell_h
        lines.append(f'<text x="{pad_l - 8}" y="{y + cell_h // 2 + 4}" text-anchor="end" fill="#cbd5e1" font-size="11" font-family="monospace">{env}</text>')
        for j, feat in enumerate(FEATURES):
            score = HEATMAP[env][feat]
            x = pad_l + j * cell_w
            c = score_color(score)
            lines.append(f'<rect x="{x + 2}" y="{y + 2}" width="{cell_w - 4}" height="{cell_h - 4}" rx="4" fill="{c}"/>')
            txt_color = "#fff" if score > 0.4 else "#94a3b8"
            lines.append(f'<text x="{x + cell_w // 2}" y="{y + cell_h // 2 + 4}" text-anchor="middle" fill="{txt_color}" font-size="10" font-family="monospace" font-weight="bold">{score:.2f}</text>')

    # Legend
    legend_x = pad_l
    legend_y = H - 14
    for label, color in [("low (<0.25)", "rgba(56,189,248,0.6)"), ("medium (0.25-0.5)", "rgba(251,146,60,0.7)"), ("high (>0.5)", "rgba(239,68,68,0.8)")]:
        lines.append(f'<rect x="{legend_x}" y="{legend_y - 10}" width="12" height="12" rx="2" fill="{color}"/>')
        lines.append(f'<text x="{legend_x + 16}" y="{legend_y}" fill="#94a3b8" font-size="10" font-family="monospace">{label}</text>')
        legend_x += 160

    lines.append('</svg>')
    return "\n".join(lines)


# ── HTML dashboard ────────────────────────────────────────────────────────────

def build_html() -> str:
    svg1 = build_multisignal_svg()
    svg2 = build_heatmap_svg()
    m = KEY_METRICS
    events_html = "".join(
        f'<div style="background:#1e293b;border-left:3px solid {"#ef4444" if e["severity"]>0.6 else "#f59e0b"};padding:10px 14px;border-radius:6px;margin-bottom:8px">'
        f'<span style="color:#38bdf8;font-size:11px">Day {e["day"]} · {e["env"]}</span>'
        f'<div style="color:#e2e8f0;font-size:13px;margin-top:4px">{e["cause"]}</div>'
        f'<div style="color:#94a3b8;font-size:11px;margin-top:2px">Severity: {e["severity"]} · Auto-remediated: {"Yes" if e["remediated"] else "No"}</div>'
        f'</div>'
        for e in DRIFT_EVENTS
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Model Drift v2 — Port 8268</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace;padding:24px}}
  h1{{color:#C74634;margin:0 0 4px}}
  .sub{{color:#94a3b8;font-size:13px;margin-bottom:24px}}
  .metrics{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:28px}}
  .card{{background:#1e293b;border-radius:10px;padding:16px 20px;min-width:160px}}
  .card-val{{font-size:26px;font-weight:bold;color:#38bdf8}}
  .card-lbl{{font-size:11px;color:#64748b;margin-top:4px}}
  .section{{margin-bottom:32px}}
  .section-title{{font-size:15px;font-weight:bold;color:#C74634;margin-bottom:12px;border-bottom:1px solid #334155;padding-bottom:6px}}
  svg{{max-width:100%;height:auto}}
</style>
</head>
<body>
<h1>Model Drift v2</h1>
<div class="sub">Advanced multivariate drift detection · concept drift · auto-remediation · Port 8268</div>

<div class="metrics">
  <div class="card"><div class="card-val">{m["drift_detection_latency_ms"]}ms</div><div class="card-lbl">Detection Latency</div></div>
  <div class="card"><div class="card-val">{m["false_positive_rate_pct"]}%</div><div class="card-lbl">False Positive Rate</div></div>
  <div class="card"><div class="card-val">{m["auto_remediation_success_pct"]}%</div><div class="card-lbl">Auto-Remediation Success</div></div>
  <div class="card"><div class="card-val">{m["drift_root_cause_categories"]}</div><div class="card-lbl">Root Cause Categories</div></div>
  <div class="card"><div class="card-val">{m["total_drift_events_30d"]}</div><div class="card-lbl">Drift Events (30d)</div></div>
  <div class="card"><div class="card-val">{m["envs_monitored"]}</div><div class="card-lbl">Envs Monitored</div></div>
  <div class="card"><div class="card-val">{m["features_tracked"]}</div><div class="card-lbl">Features Tracked</div></div>
</div>

<div class="section">
  <div class="section-title">Multi-Signal Drift Dashboard (60 Days)</div>
  {svg1}
</div>

<div class="section">
  <div class="section-title">Drift Severity Heatmap</div>
  {svg2}
</div>

<div class="section">
  <div class="section-title">Annotated Drift Events</div>
  {events_html}
</div>
</body></html>"""


# ── App / fallback ────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="Model Drift v2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "model_drift_v2", "port": 8268}

    @app.get("/metrics")
    async def metrics():
        return KEY_METRICS

    @app.get("/events")
    async def events():
        return DRIFT_EVENTS

    @app.get("/signals")
    async def signals():
        return SIGNALS

    @app.get("/heatmap")
    async def heatmap():
        return HEATMAP

else:
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            content = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8268)
    else:
        print("[model_drift_v2] fastapi not found — using stdlib http.server on port 8268")
        with socketserver.TCPServer(("", 8268), Handler) as httpd:
            httpd.serve_forever()

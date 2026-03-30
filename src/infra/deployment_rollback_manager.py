"""Deployment Rollback Manager — FastAPI service on port 8304.

Manages automatic and manual rollback procedures for model deployments.
Tracks rollback history, decision thresholds, and MTTR metrics.
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

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

ROLLBACK_HISTORY = [
    {
        "id": "rb-001",
        "date": "Jan 18",
        "day_offset": 71,
        "trigger": "SR_drop",
        "from_version": "GR00T_v1",
        "to_version": "dagger_r9",
        "mttr_min": 4.0,
        "auto": True,
        "delta": -6.2,
        "status": "success",
    },
    {
        "id": "rb-002",
        "date": "Feb 3",
        "day_offset": 55,
        "trigger": "latency_spike",
        "from_version": "GR00T_v2_rc1",
        "to_version": "GR00T_v1",
        "mttr_min": 2.1,
        "auto": True,
        "delta": 0,
        "status": "success",
    },
    {
        "id": "rb-003",
        "date": "Mar 12",
        "day_offset": 18,
        "trigger": "manual",
        "from_version": "GR00T_v2_chunk64",
        "to_version": "GR00T_v2",
        "mttr_min": 1.3,
        "auto": False,
        "delta": 0,
        "status": "success",
        "note": "chunk_size config error",
    },
]

DEPLOYMENT_EVENTS = [
    {"date": "Jan 5", "day_offset": 84, "version": "GR00T_v1", "type": "deploy"},
    {"date": "Jan 18", "day_offset": 71, "version": "GR00T_v1", "type": "rollback"},
    {"date": "Jan 22", "day_offset": 67, "version": "GR00T_v2_rc1", "type": "deploy"},
    {"date": "Feb 3", "day_offset": 55, "version": "GR00T_v2_rc1", "type": "rollback"},
    {"date": "Feb 14", "day_offset": 44, "version": "GR00T_v2", "type": "deploy"},
    {"date": "Mar 1", "day_offset": 29, "version": "GR00T_v2_chunk64", "type": "deploy"},
    {"date": "Mar 12", "day_offset": 18, "version": "GR00T_v2_chunk64", "type": "rollback"},
    {"date": "Mar 14", "day_offset": 16, "version": "GR00T_v2", "type": "deploy"},
]

THRESHOLDS = {
    "latency_ms": {"limit": 300, "current": 227, "status": "NOMINAL"},
    "error_rate_pct": {"limit": 1.0, "current": 0.12, "status": "NOMINAL"},
    "sr_drop_pp": {"limit": 5.0, "current": 1.3, "status": "NOMINAL"},
    "anomaly_score": {"limit": 0.80, "current": 0.23, "status": "NOMINAL"},
}

KEY_METRICS = {
    "avg_mttr_min": 2.47,
    "false_positive_rate_pct": 4.2,
    "rollbacks_90d": 3,
    "golden_target": "dagger_r9",
    "trigger_accuracy_pct": 95.8,
    "trend": "stable",
}

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_timeline() -> str:
    """90-day rollback history timeline."""
    W, H = 820, 220
    pad_l, pad_r, pad_t, pad_b = 60, 30, 40, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    days = 90

    def x(day_offset):
        return pad_l + (days - day_offset) / days * chart_w

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # Grid lines
    for d in [0, 15, 30, 45, 60, 75, 90]:
        xp = pad_l + d / days * chart_w
        lines.append(f'<line x1="{xp:.1f}" y1="{pad_t}" x2="{xp:.1f}" y2="{H-pad_b}" stroke="#334155" stroke-width="1"/>')
        label = f"-{90-d}d" if d < 90 else "now"
        lines.append(f'<text x="{xp:.1f}" y="{H-pad_b+14}" text-anchor="middle" fill="#94a3b8" font-size="10">{label}</text>')

    # Baseline
    mid_y = pad_t + chart_h / 2
    lines.append(f'<line x1="{pad_l}" y1="{mid_y:.1f}" x2="{W-pad_r}" y2="{mid_y:.1f}" stroke="#475569" stroke-width="1.5" stroke-dasharray="4,3"/>')
    lines.append(f'<text x="{pad_l-8}" y="{mid_y+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10">timeline</text>')

    # Deployment events
    for ev in DEPLOYMENT_EVENTS:
        xp = x(ev["day_offset"])
        if ev["type"] == "deploy":
            # Green up-arrow
            ay = mid_y - 28
            lines.append(f'<line x1="{xp:.1f}" y1="{mid_y:.1f}" x2="{xp:.1f}" y2="{ay+6:.1f}" stroke="#22c55e" stroke-width="2"/>')
            lines.append(f'<polygon points="{xp:.1f},{ay:.1f} {xp-6:.1f},{ay+10:.1f} {xp+6:.1f},{ay+10:.1f}" fill="#22c55e"/>')
            lines.append(f'<text x="{xp:.1f}" y="{ay-5:.1f}" text-anchor="middle" fill="#86efac" font-size="9">{ev["version"]}</text>')
        else:
            # Red down-arrow with trigger label
            rb = next((r for r in ROLLBACK_HISTORY if r["day_offset"] == ev["day_offset"]), None)
            trigger = rb["trigger"] if rb else "rollback"
            ay = mid_y + 28
            lines.append(f'<line x1="{xp:.1f}" y1="{mid_y:.1f}" x2="{xp:.1f}" y2="{ay-6:.1f}" stroke="#C74634" stroke-width="2"/>')
            lines.append(f'<polygon points="{xp:.1f},{ay:.1f} {xp-6:.1f},{ay-10:.1f} {xp+6:.1f},{ay-10:.1f}" fill="#C74634"/>')
            lines.append(f'<text x="{xp:.1f}" y="{ay+14:.1f}" text-anchor="middle" fill="#fca5a5" font-size="9">{trigger}</text>')

    # Title
    lines.append(f'<text x="{W//2}" y="16" text-anchor="middle" fill="#e2e8f0" font-size="12" font-weight="bold">90-Day Deployment &amp; Rollback Timeline</text>')

    # Legend
    lx = W - pad_r - 180
    lines.append(f'<polygon points="{lx},{H-pad_b-4} {lx-5},{H-pad_b+6} {lx+5},{H-pad_b+6}" fill="#22c55e"/>')
    lines.append(f'<text x="{lx+9}" y="{H-pad_b+5}" fill="#86efac" font-size="10">Deploy</text>')
    lx2 = lx + 70
    lines.append(f'<polygon points="{lx2},{H-pad_b+6} {lx2-5},{H-pad_b-4} {lx2+5},{H-pad_b-4}" fill="#C74634"/>')
    lines.append(f'<text x="{lx2+9}" y="{H-pad_b+5}" fill="#fca5a5" font-size="10">Rollback</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def svg_decision_tree() -> str:
    """Rollback decision tree flowchart."""
    W, H = 820, 300
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    def box(x, y, w, h, color, label, sublabel="", highlight=False):
        stroke = "#38bdf8" if highlight else color
        sw = 2.5 if highlight else 1.5
        lines.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#0f172a" stroke="{stroke}" stroke-width="{sw}"/>')
        cy = y + h // 2 - (6 if sublabel else 0)
        lines.append(f'<text x="{x+w//2}" y="{cy}" text-anchor="middle" fill="{color}" font-size="11" font-weight="bold">{label}</text>')
        if sublabel:
            lines.append(f'<text x="{x+w//2}" y="{cy+14}" text-anchor="middle" fill="#94a3b8" font-size="10">{sublabel}</text>')

    def arrow(x1, y1, x2, y2, color="#475569", label=""):
        lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5" marker-end="url(#arrowhead)"/>')
        if label:
            mx, my = (x1+x2)//2, (y1+y2)//2
            lines.append(f'<text x="{mx+4}" y="{my-4}" fill="#94a3b8" font-size="9">{label}</text>')

    # Arrowhead marker
    lines.append('<defs><marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#475569"/></marker></defs>')

    # Nodes
    # Row 0: Monitor
    box(340, 10, 140, 36, "#38bdf8", "Live Monitor", "every 30s")

    # Row 1: checks (4 boxes)
    checks = [
        ("latency", "Latency", ">300ms", "#fbbf24", 20),
        ("error_rate", "Error Rate", ">1%", "#fbbf24", 200),
        ("sr_drop", "SR Drop", ">5pp", "#fbbf24", 380),
        ("anomaly", "Anomaly", ">0.8", "#fbbf24", 560),
    ]
    for _, label, threshold, color, cx in checks:
        box(cx, 80, 120, 44, color, label, threshold)
        arrow(410, 46, cx + 60, 80, "#475569")

    # Row 2: Trigger Rollback
    box(300, 170, 220, 40, "#C74634", "Trigger Rollback", "auto or manual")
    for _, label, threshold, color, cx in checks:
        arrow(cx + 60, 124, 410, 170, "#C74634", "BREACH")

    # Row 3: outcomes
    box(80, 240, 160, 40, "#22c55e", "Fetch Golden Target", "dagger_r9")
    box(300, 240, 160, 40, "#38bdf8", "Hot-swap Model", "zero-downtime")
    box(520, 240, 160, 40, "#a78bfa", "Log + Alert", "PagerDuty + Slack")

    arrow(410, 210, 160, 240, "#22c55e")
    arrow(410, 210, 380, 240, "#38bdf8")
    arrow(410, 210, 600, 240, "#a78bfa")

    # Current thresholds sidebar
    lines.append(f'<text x="700" y="90" fill="#94a3b8" font-size="10" font-weight="bold">Current Readings</text>')
    readings = [
        ("Latency", "227ms", "#22c55e"),
        ("Err Rate", "0.12%", "#22c55e"),
        ("SR Drop", "1.3pp", "#22c55e"),
        ("Anomaly", "0.23", "#22c55e"),
    ]
    for i, (name, val, color) in enumerate(readings):
        lines.append(f'<text x="700" y="{108+i*18}" fill="#94a3b8" font-size="10">{name}: <tspan fill="{color}">{val}</tspan></text>')

    lines.append(f'<text x="{W//2}" y="296" text-anchor="middle" fill="#64748b" font-size="10">Last triggered path: SR_drop (Jan 18) → auto rollback GR00T_v1 → dagger_r9</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    tl = svg_timeline()
    dt = svg_decision_tree()
    rb_rows = ""
    for rb in ROLLBACK_HISTORY:
        auto_badge = '<span style="background:#1e40af;color:#93c5fd;padding:1px 7px;border-radius:9px;font-size:11px">auto</span>' if rb["auto"] else '<span style="background:#4c1d95;color:#c4b5fd;padding:1px 7px;border-radius:9px;font-size:11px">manual</span>'
        rb_rows += f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td style="padding:8px 12px;color:#94a3b8">{rb['date']}</td>
          <td style="padding:8px 12px">{auto_badge}</td>
          <td style="padding:8px 12px;color:#fbbf24">{rb['trigger']}</td>
          <td style="padding:8px 12px;color:#e2e8f0">{rb['from_version']} → {rb['to_version']}</td>
          <td style="padding:8px 12px;color:#38bdf8">{rb['mttr_min']} min</td>
          <td style="padding:8px 12px;color:#22c55e">{rb['status']}</td>
        </tr>"""

    thresh_cards = ""
    labels = {"latency_ms": "Latency", "error_rate_pct": "Error Rate", "sr_drop_pp": "SR Drop", "anomaly_score": "Anomaly Score"}
    units = {"latency_ms": "ms", "error_rate_pct": "%", "sr_drop_pp": "pp", "anomaly_score": ""}
    for k, v in THRESHOLDS.items():
        pct = min(100, v["current"] / v["limit"] * 100)
        bar_color = "#22c55e" if pct < 70 else "#fbbf24" if pct < 90 else "#C74634"
        thresh_cards += f"""
        <div style="background:#1e293b;border-radius:8px;padding:14px 18px;min-width:160px">
          <div style="color:#94a3b8;font-size:11px;margin-bottom:4px">{labels[k]}</div>
          <div style="color:#e2e8f0;font-size:20px;font-weight:bold">{v['current']}{units[k]}</div>
          <div style="color:#64748b;font-size:11px">limit: {v['limit']}{units[k]}</div>
          <div style="background:#0f172a;border-radius:4px;height:6px;margin-top:8px">
            <div style="background:{bar_color};width:{pct:.0f}%;height:6px;border-radius:4px"></div>
          </div>
          <div style="color:#22c55e;font-size:11px;margin-top:4px">{v['status']}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Deployment Rollback Manager — Port 8304</title>
<style>
  body{{margin:0;font-family:'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#e2e8f0}}
  h1{{margin:0;font-size:22px;font-weight:700}}
  h2{{font-size:15px;color:#94a3b8;margin:24px 0 10px;text-transform:uppercase;letter-spacing:.06em}}
  .header{{background:#1e293b;border-bottom:2px solid #C74634;padding:16px 28px;display:flex;align-items:center;gap:16px}}
  .badge{{background:#C74634;color:#fff;border-radius:6px;padding:2px 10px;font-size:12px}}
  .metrics{{display:flex;flex-wrap:wrap;gap:14px;padding:20px 28px}}
  .metric{{background:#1e293b;border-radius:8px;padding:14px 20px;min-width:140px}}
  .metric .val{{font-size:24px;font-weight:700;color:#38bdf8}}
  .metric .lbl{{font-size:11px;color:#64748b;margin-top:2px}}
  .content{{padding:0 28px 28px}}
  table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
  th{{background:#0f172a;padding:9px 12px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase}}
  svg{{display:block;max-width:100%}}
</style>
</head>
<body>
<div class="header">
  <div>
    <div style="display:flex;align-items:center;gap:10px">
      <h1>Deployment Rollback Manager</h1>
      <span class="badge">PORT 8304</span>
    </div>
    <div style="color:#64748b;font-size:13px;margin-top:4px">Automated &amp; manual rollback orchestration for OCI Robot Cloud model deployments</div>
  </div>
</div>

<div class="metrics">
  <div class="metric"><div class="val">{KEY_METRICS['avg_mttr_min']}m</div><div class="lbl">Avg MTTR</div></div>
  <div class="metric"><div class="val">{KEY_METRICS['rollbacks_90d']}</div><div class="lbl">Rollbacks (90d)</div></div>
  <div class="metric"><div class="val">{KEY_METRICS['trigger_accuracy_pct']}%</div><div class="lbl">Trigger Accuracy</div></div>
  <div class="metric"><div class="val" style="color:#fbbf24">{KEY_METRICS['false_positive_rate_pct']}%</div><div class="lbl">False Positive Rate</div></div>
  <div class="metric"><div class="val" style="color:#22c55e">{KEY_METRICS['golden_target']}</div><div class="lbl">Golden Rollback Target</div></div>
  <div class="metric"><div class="val" style="color:#a78bfa">{KEY_METRICS['trend'].upper()}</div><div class="lbl">Frequency Trend</div></div>
</div>

<div class="content">
  <h2>Live Threshold Monitors</h2>
  <div style="display:flex;flex-wrap:wrap;gap:14px;margin-bottom:22px">{thresh_cards}</div>

  <h2>90-Day Rollback Timeline</h2>
  <div style="border-radius:8px;overflow:hidden;margin-bottom:22px">{tl}</div>

  <h2>Rollback Decision Tree</h2>
  <div style="border-radius:8px;overflow:hidden;margin-bottom:22px">{dt}</div>

  <h2>Rollback Log</h2>
  <table>
    <thead><tr>
      <th>Date</th><th>Mode</th><th>Trigger</th><th>Transition</th><th>MTTR</th><th>Status</th>
    </tr></thead>
    <tbody>{rb_rows}</tbody>
  </table>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Deployment Rollback Manager", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/rollbacks")
    async def api_rollbacks():
        return {"rollbacks": ROLLBACK_HISTORY, "total": len(ROLLBACK_HISTORY)}

    @app.get("/api/thresholds")
    async def api_thresholds():
        return {"thresholds": THRESHOLDS, "all_nominal": all(v["status"] == "NOMINAL" for v in THRESHOLDS.values())}

    @app.get("/api/metrics")
    async def api_metrics():
        return KEY_METRICS

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "deployment_rollback_manager", "port": 8304}

else:
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            html = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8304)
    else:
        server = http.server.HTTPServer(("0.0.0.0", 8304), Handler)
        print("Serving on http://0.0.0.0:8304 (stdlib fallback)")
        server.serve_forever()

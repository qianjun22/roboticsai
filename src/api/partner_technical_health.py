"""Partner Technical Health — port 8917"""
import math
import random
import json
import time
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

SERVICE_TITLE = "Partner Technical Health"
PORT = 8917

PARTNERS = ["AgilityRobotics", "BostonDynamics", "Figure", "1X", "Apptronik"]
SIGNALS = ["api_error_rate", "latency_p95", "eval_pass_rate", "sdk_version", "integration_test_pass"]
SIGNAL_LABELS = ["API Error Rate", "Latency p95", "Eval Pass Rate", "SDK Version", "Int. Test Pass"]

# Signal scoring: 0-100 where 100 = best health
def signal_score(signal, raw):
    if signal == "api_error_rate":   return max(0, 100 - raw * 20)   # lower is better
    if signal == "latency_p95":      return max(0, 100 - (raw - 100) / 5)  # lower is better
    if signal == "eval_pass_rate":   return raw   # higher is better
    if signal == "sdk_version":      return raw   # higher = more current
    if signal == "integration_test_pass": return raw
    return 50


def generate_partner_data():
    random.seed(int(time.time()) // 60)
    data = []
    for i, p in enumerate(PARTNERS):
        # 1X has elevated API error rate (alert)
        api_err = 2.3 if p == "1X" else round(random.uniform(0.1, 0.9), 2)
        lat_p95 = round(random.uniform(120, 310), 1)
        eval_pass = round(random.uniform(72, 98), 1)
        sdk_ver = round(random.uniform(55, 99), 1)  # percentage up-to-date
        int_test = round(random.uniform(80, 99), 1)
        raws = [api_err, lat_p95, eval_pass, sdk_ver, int_test]
        scores = [signal_score(s, v) for s, v in zip(SIGNALS, raws)]
        overall = round(sum(scores) / len(scores), 1)
        data.append({
            "partner": p,
            "api_error_rate": api_err,
            "latency_p95": lat_p95,
            "eval_pass_rate": eval_pass,
            "sdk_version": sdk_ver,
            "integration_test_pass": int_test,
            "scores": scores,
            "overall": overall,
            "alert": p == "1X",
        })
    return data


def build_radar_svg(partner_data, idx):
    """SVG radar chart for one partner (5 axes)."""
    CX, CY, R = 120, 110, 80
    N = 5
    angles = [math.pi / 2 + 2 * math.pi * k / N for k in range(N)]

    def pt(r_frac, angle):
        x = CX + r_frac * R * math.cos(angle)
        y = CY - r_frac * R * math.sin(angle)
        return x, y

    # Grid rings
    rings = ""
    for level in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{pt(level, a)[0]:.1f},{pt(level, a)[1]:.1f}" for a in angles)
        rings += f'<polygon points="{pts}" fill="none" stroke="#1e293b" stroke-width="1"/>'

    # Axes
    axes = "".join(
        f'<line x1="{CX:.1f}" y1="{CY:.1f}" x2="{pt(1, a)[0]:.1f}" y2="{pt(1, a)[1]:.1f}" stroke="#334155" stroke-width="1"/>'
        for a in angles
    )

    # Data polygon
    scores = partner_data["scores"]
    d_pts = " ".join(f"{pt(s / 100, a)[0]:.1f},{pt(s / 100, a)[1]:.1f}" for s, a in zip(scores, angles))
    fill_color = "#C74634" if partner_data["alert"] else "#38bdf8"
    data_poly = f'<polygon points="{d_pts}" fill="{fill_color}" fill-opacity="0.25" stroke="{fill_color}" stroke-width="2"/>'

    # Dots
    dots = "".join(
        f'<circle cx="{pt(s / 100, a)[0]:.1f}" cy="{pt(s / 100, a)[1]:.1f}" r="4" fill="{fill_color}"/>'
        for s, a in zip(scores, angles)
    )

    # Labels
    labels = ""
    label_shorts = ["Err%", "Lat", "Eval", "SDK", "IntTest"]
    for k, (a, lbl, score) in enumerate(zip(angles, label_shorts, scores)):
        lx, ly = pt(1.22, a)
        labels += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle" dominant-baseline="middle">{lbl}</text>'

    # Overall score
    ov_color = "#4ade80" if partner_data["overall"] >= 80 else ("#fbbf24" if partner_data["overall"] >= 60 else "#C74634")
    overall_txt = f'<text x="{CX}" y="{CY + R + 20}" fill="{ov_color}" font-size="12" text-anchor="middle" font-weight="bold">{partner_data["overall"]:.0f}/100</text>'

    return f'''
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 200" style="width:220px;height:190px;background:#1e293b;border-radius:8px">
  {rings}{axes}{data_poly}{dots}{labels}
  <text x="{CX}" y="14" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="600">{partner_data['partner']}</text>
  {overall_txt}
</svg>'''


def build_debt_tracker_svg(data):
    """Horizontal bar for technical debt (100 - overall score)."""
    W, H = 860, 240
    pad_l, pad_r, pad_t, pad_b = 140, 60, 20, 20
    bar_h = 26
    gap = 12
    max_w = W - pad_l - pad_r
    bars = ""
    for i, d in enumerate(sorted(data, key=lambda x: x["overall"])):
        y = pad_t + i * (bar_h + gap)
        debt = 100 - d["overall"]
        w = max_w * debt / 100
        color = "#C74634" if debt > 40 else ("#fbbf24" if debt > 20 else "#38bdf8")
        bars += f'<text x="{pad_l - 8}" y="{y + bar_h / 2:.1f}" fill="#e2e8f0" font-size="11" text-anchor="end" dominant-baseline="middle">{d["partner"]}</text>'
        bars += f'<rect x="{pad_l}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="4" fill="{color}" fill-opacity="0.85"/>'
        bars += f'<text x="{pad_l + w + 6:.1f}" y="{y + bar_h / 2:.1f}" fill="{color}" font-size="11" dominant-baseline="middle">{debt:.1f} pts debt</text>'
        if d["alert"]:
            bars += f'<text x="{W - pad_r}" y="{y + bar_h / 2:.1f}" fill="#C74634" font-size="11" text-anchor="end" dominant-baseline="middle">ALERT</text>'
    real_h = pad_t + len(data) * (bar_h + gap) + pad_b
    return f'''
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {real_h}" style="width:100%;background:#0f172a;border-radius:8px">
  {bars}
</svg>'''


def render_html():
    data = generate_partner_data()
    radar_svgs = "".join(
        f'<div style="display:inline-block;margin:8px">{build_radar_svg(d, i)}</div>'
        for i, d in enumerate(data)
    )
    debt_svg = build_debt_tracker_svg(data)

    # Summary table
    def status_badge(val, signal):
        if signal == "api_error_rate":
            color = "#C74634" if val > 2.0 else ("#fbbf24" if val > 1.0 else "#4ade80")
            return f'<span style="color:{color};font-weight:700">{val}%</span>'
        if signal == "latency_p95":
            color = "#C74634" if val > 280 else ("#fbbf24" if val > 200 else "#4ade80")
            return f'<span style="color:{color}">{val}ms</span>'
        if signal in ("eval_pass_rate", "sdk_version", "integration_test_pass"):
            color = "#4ade80" if val >= 90 else ("#fbbf24" if val >= 75 else "#C74634")
            return f'<span style="color:{color}">{val}%</span>'
        return str(val)

    table_rows = "".join(
        f'<tr{" style=\"background:#1a0a0a\"" if d["alert"] else ""}><td>{d["partner"]}{" <span style=\"color:#C74634;font-size:0.8em\">⚠ ALERT</span>" if d["alert"] else ""}</td>'
        f'<td>{status_badge(d["api_error_rate"], "api_error_rate")}</td>'
        f'<td>{status_badge(d["latency_p95"], "latency_p95")}</td>'
        f'<td>{status_badge(d["eval_pass_rate"], "eval_pass_rate")}</td>'
        f'<td>{status_badge(d["sdk_version"], "sdk_version")}</td>'
        f'<td>{status_badge(d["integration_test_pass"], "integration_test_pass")}</td>'
        f'<td style="color:{"#4ade80" if d["overall"] >= 80 else ("#fbbf24" if d["overall"] >= 60 else "#C74634")};font-weight:700">{d["overall"]}</td></tr>'
        for d in data
    )
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{SERVICE_TITLE}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
h1{{color:#C74634;font-size:1.7rem;margin-bottom:4px}}
h2{{color:#38bdf8;font-size:1.1rem;margin:24px 0 10px}}
.meta{{color:#64748b;font-size:0.8rem;margin-bottom:20px}}
.cards{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:24px}}
.card{{background:#1e293b;border-radius:8px;padding:14px}}
.card .label{{font-size:0.72rem;color:#64748b;margin-bottom:4px}}
.card .val{{font-size:1.4rem;font-weight:700}}
.card .sub{{font-size:0.72rem;color:#64748b;margin-top:2px}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem;margin-top:8px}}
th{{background:#1e293b;color:#94a3b8;padding:8px 10px;text-align:left;font-weight:600}}
td{{padding:7px 10px;border-bottom:1px solid #1e293b}}
tr:hover td{{background:#1e293b}}
.chart-box{{background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:12px;margin-bottom:20px}}
.alert{{background:#1e1010;border-left:3px solid #C74634;padding:10px 14px;border-radius:4px;font-size:0.82rem;margin-bottom:18px}}
.radars{{background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:16px;margin-bottom:20px;display:flex;flex-wrap:wrap;gap:4px}}
</style>
</head>
<body>
<h1>{SERVICE_TITLE}</h1>
<div class="meta">Port {PORT} · 5-signal technical health per partner · Refreshed {ts}</div>

<div class="alert">ALERT — 1X API error rate: <strong>2.3%</strong> (threshold: 2.0%). Elevated errors detected in inference endpoint. Recommended action: review SDK integration and error handling.</div>

<div class="cards">
  <div class="card"><div class="label">Signals Tracked</div><div class="val" style="color:#38bdf8">5</div><div class="sub">per partner</div></div>
  <div class="card"><div class="label">Partners Monitored</div><div class="val" style="color:#38bdf8">5</div><div class="sub">active integrations</div></div>
  <div class="card"><div class="label">Active Alerts</div><div class="val" style="color:#C74634">1</div><div class="sub">1X API errors</div></div>
  <div class="card"><div class="label">Avg Overall Health</div><div class="val" style="color:#4ade80">{round(sum(d['overall'] for d in data)/len(data),1)}</div><div class="sub">/100</div></div>
  <div class="card"><div class="label">SDK Compliance</div><div class="val" style="color:#fbbf24">{round(sum(d['sdk_version'] for d in data)/len(data),1)}%</div><div class="sub">up-to-date</div></div>
</div>

<h2>Radar Charts — 5-Signal Health per Partner</h2>
<div class="radars">{radar_svgs}</div>

<h2>Technical Debt Tracker (100 - Overall Health Score)</h2>
<div class="chart-box">{debt_svg}</div>

<h2>Signal Summary Table</h2>
<table>
<tr><th>Partner</th><th>API Error Rate</th><th>Latency p95</th><th>Eval Pass Rate</th><th>SDK Version</th><th>Int. Test Pass</th><th>Overall</th></tr>
{table_rows}
</table>
</body>
</html>'''


if USE_FASTAPI:
    app = FastAPI(title=SERVICE_TITLE)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return render_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE_TITLE, "port": PORT}

    @app.get("/metrics")
    def metrics():
        data = generate_partner_data()
        return {
            "partners": data,
            "alerts": [d for d in data if d["alert"]],
            "avg_overall_health": round(sum(d["overall"] for d in data) / len(data), 1),
            "timestamp": datetime.utcnow().isoformat(),
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)
else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            body = render_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        print(f"Serving {SERVICE_TITLE} on port {PORT} (stdlib fallback)")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

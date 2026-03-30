"""Action Head Calibrator — FastAPI port 8778"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8778

def build_html():
    random.seed(42)
    # Generate calibration residuals across 12 joints
    joints = ["shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3",
              "finger_l1", "finger_l2", "finger_r1", "finger_r2", "thumb_l", "thumb_r"]
    residuals = [round(random.gauss(0, 0.012), 4) for _ in joints]
    biases    = [round(random.gauss(0, 0.008), 4) for _ in joints]
    gains     = [round(1.0 + random.gauss(0, 0.03), 4) for _ in joints]

    # Calibration convergence curve (50 steps)
    conv_vals = [round(0.25 * math.exp(-0.08 * i) + 0.002 * math.sin(i * 0.7) + random.uniform(-0.001, 0.001), 5)
                 for i in range(50)]
    max_conv  = max(conv_vals) or 1
    chart_w, chart_h = 560, 120
    points = " ".join(
        f"{int(i / 49 * chart_w)},{int(chart_h - conv_vals[i] / max_conv * (chart_h - 10) - 4)}"
        for i in range(50)
    )

    # Joint residual bar chart (normalised)
    max_res = max(abs(r) for r in residuals) or 0.01
    bars_html = ""
    for idx, (j, r) in enumerate(zip(joints, residuals)):
        bar_len = int(abs(r) / max_res * 120)
        color   = "#ef4444" if abs(r) > 0.015 else "#22c55e"
        x_off   = idx * 46 + 10
        bars_html += (
            f'<rect x="{x_off}" y="{60 - bar_len // 2}" width="36" height="{bar_len}" fill="{color}" rx="3"/>'
            f'<text x="{x_off + 18}" y="{68 + bar_len // 2 + 12}" fill="#94a3b8" font-size="8" text-anchor="middle">{j[:6]}</text>'
        )

    # Table rows
    rows = ""
    for j, r, b, g in zip(joints, residuals, biases, gains):
        ok    = abs(r) <= 0.015
        badge = '<span style="background:#15803d;padding:2px 6px;border-radius:4px;font-size:11px">PASS</span>' if ok else '<span style="background:#b91c1c;padding:2px 6px;border-radius:4px;font-size:11px">WARN</span>'
        rows += f"<tr><td>{j}</td><td>{r:+.4f} rad</td><td>{b:+.4f}</td><td>{g:.4f}</td><td>{badge}</td></tr>"

    passed  = sum(1 for r in residuals if abs(r) <= 0.015)
    overall = "CALIBRATED" if passed == len(joints) else f"{passed}/{len(joints)} JOINTS OK"

    return f"""<!DOCTYPE html><html><head><title>Action Head Calibrator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 24px 4px;margin:0;font-size:1.6rem}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
.card{{background:#1e293b;padding:20px;margin:12px;border-radius:8px;box-shadow:0 2px 8px #0004}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#0f172a;padding:8px 12px;text-align:left;color:#94a3b8;font-weight:600}}
td{{padding:7px 12px;border-bottom:1px solid #334155}}
.badge-ok{{background:#14532d;color:#86efac;padding:2px 8px;border-radius:4px;font-size:11px}}
.metric{{display:inline-block;background:#0f172a;border-radius:6px;padding:10px 22px;margin:6px;text-align:center}}
.metric .val{{font-size:1.5rem;font-weight:700;color:#38bdf8}}
.metric .lbl{{font-size:11px;color:#64748b;margin-top:2px}}
</style></head>
<body>
<h1>Action Head Calibrator</h1>
<p style="color:#64748b;margin:0 24px 16px">Port {PORT} &nbsp;|&nbsp; GR00T N1.6 joint-space residual calibration</p>

<div style="display:flex;flex-wrap:wrap;margin:0 12px">
  <div class="metric"><div class="val">{passed}/{len(joints)}</div><div class="lbl">Joints Passing</div></div>
  <div class="metric"><div class="val">{max(abs(r) for r in residuals)*1000:.1f} mrad</div><div class="lbl">Max Residual</div></div>
  <div class="metric"><div class="val">{sum(abs(r) for r in residuals)/len(residuals)*1000:.2f} mrad</div><div class="lbl">Mean Abs Error</div></div>
  <div class="metric"><div class="val" style="color:#{'22c55e' if passed==len(joints) else 'f59e0b'}">{overall}</div><div class="lbl">Overall Status</div></div>
</div>

<div class="card">
  <h2>Calibration Convergence (50 iterations)</h2>
  <svg width="{chart_w}" height="{chart_h + 20}" style="display:block">
    <polyline points="{points}" fill="none" stroke="#38bdf8" stroke-width="2"/>
    <line x1="0" y1="{chart_h - 4}" x2="{chart_w}" y2="{chart_h - 4}" stroke="#334155" stroke-width="1"/>
    <text x="4" y="14" fill="#94a3b8" font-size="10">Loss</text>
    <text x="{chart_w - 4}" y="{chart_h + 14}" fill="#94a3b8" font-size="10" text-anchor="end">iter 50</text>
  </svg>
</div>

<div class="card">
  <h2>Per-Joint Residual Distribution</h2>
  <svg width="{len(joints)*46 + 20}" height="160" style="display:block">
    <line x1="0" y1="60" x2="{len(joints)*46 + 20}" y2="60" stroke="#334155" stroke-dasharray="4 3" stroke-width="1"/>
    {bars_html}
  </svg>
</div>

<div class="card">
  <h2>Joint Calibration Details</h2>
  <table>
    <tr><th>Joint</th><th>Residual</th><th>Bias Offset</th><th>Gain Factor</th><th>Status</th></tr>
    {rows}
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Action Head Calibrator")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/calibration")
    def calibration_status():
        random.seed(42)
        joints = ["shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3",
                  "finger_l1", "finger_l2", "finger_r1", "finger_r2", "thumb_l", "thumb_r"]
        residuals = [round(random.gauss(0, 0.012), 4) for _ in joints]
        return {"joints": dict(zip(joints, residuals)),
                "passing": sum(1 for r in residuals if abs(r) <= 0.015),
                "total": len(joints)}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a):
        pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

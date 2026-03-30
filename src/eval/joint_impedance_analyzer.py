"""Joint Impedance Analyzer — FastAPI service on port 8309.

Analyzes Franka arm joint impedance settings for optimal compliant
manipulation, particularly cube-lift tasks.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

import random
import math
from datetime import datetime

random.seed(42)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

# 7 Franka joints — stiffness K (N/m or Nm/rad) and damping D
JOINTS = [
    {"id": "J1", "K": 420,  "D": 35, "optimal_min": 200, "optimal_max": 500, "note": None},
    {"id": "J2", "K": 380,  "D": 30, "optimal_min": 200, "optimal_max": 500, "note": None},
    {"id": "J3", "K": 310,  "D": 28, "optimal_min": 150, "optimal_max": 450, "note": None},
    {"id": "J4", "K": 290,  "D": 25, "optimal_min": 150, "optimal_max": 450, "note": None},
    {"id": "J5", "K": 680,  "D": 55, "optimal_min": 200, "optimal_max": 400, "note": "TOO STIFF — reduces grasp compliance"},
    {"id": "J6", "K": 620,  "D": 50, "optimal_min": 200, "optimal_max": 400, "note": "TOO STIFF — reduces grasp compliance"},
    {"id": "J7", "K": 180,  "D": 15, "optimal_min": 100, "optimal_max": 300, "note": None},
]

OPTIMAL_K_MIN = 200   # N/m for cube_lift
OPTIMAL_K_MAX = 400   # N/m for cube_lift

# 50 episodes: (avg_stiffness, success)
EPISODES = []
for i in range(50):
    # cluster ~65% in 180-450, rest outside
    if i < 33:
        k = random.uniform(180, 450)
    elif i < 42:
        k = random.uniform(450, 750)
    else:
        k = random.uniform(80, 180)
    in_band = OPTIMAL_K_MIN <= k <= OPTIMAL_K_MAX
    # success more likely in-band
    success = random.random() < (0.78 if in_band else 0.28)
    EPISODES.append({"ep": i + 1, "avg_K": round(k, 1), "success": success})


# ---------------------------------------------------------------------------
# Derived metrics
# ---------------------------------------------------------------------------

def _metrics():
    in_band = [e for e in EPISODES if OPTIMAL_K_MIN <= e["avg_K"] <= OPTIMAL_K_MAX]
    out_band = [e for e in EPISODES if not (OPTIMAL_K_MIN <= e["avg_K"] <= OPTIMAL_K_MAX)]
    success_in = sum(1 for e in in_band if e["success"]) / max(len(in_band), 1)
    success_out = sum(1 for e in out_band if e["success"]) / max(len(out_band), 1)
    pct_in = round(100 * len(in_band) / len(EPISODES), 1)
    stiff_joints = [j for j in JOINTS if j["K"] > j["optimal_max"]]
    compliance_score = round(100 * sum(
        1 - max(0, (j["K"] - j["optimal_max"]) / j["optimal_max"])
        for j in JOINTS
    ) / len(JOINTS), 1)
    return {
        "pct_episodes_in_optimal_band": pct_in,
        "success_rate_in_band_pct": round(100 * success_in, 1),
        "success_rate_out_band_pct": round(100 * success_out, 1),
        "suboptimal_joints": [j["id"] for j in stiff_joints],
        "impedance_compliance_score": compliance_score,
        "recommended_K_range": f"{OPTIMAL_K_MIN}-{OPTIMAL_K_MAX} N/m",
        "total_episodes": len(EPISODES),
    }


# ---------------------------------------------------------------------------
# SVG 1 — Joint stiffness profile
# ---------------------------------------------------------------------------

def _stiffness_svg() -> str:
    W, H = 560, 300
    row_h = 32
    label_w = 50
    bar_area = W - label_w - 80
    max_K = 800

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>',
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="#f1f5f9" font-size="13" font-family="monospace" font-weight="bold">Joint Stiffness Profile (K &amp; D)</text>',
    ]

    # optimal band shading
    bx_min = label_w + bar_area * OPTIMAL_K_MIN / max_K
    bx_max = label_w + bar_area * OPTIMAL_K_MAX / max_K
    band_h = H - 50
    lines.append(f'<rect x="{bx_min:.1f}" y="30" width="{bx_max - bx_min:.1f}" height="{band_h}" fill="#22c55e" fill-opacity="0.08"/>')
    lines.append(f'<text x="{(bx_min+bx_max)/2:.1f}" y="44" text-anchor="middle" fill="#22c55e" font-size="9" font-family="monospace">OPTIMAL BAND</text>')

    for i, j in enumerate(JOINTS):
        y_top = 40 + i * row_h
        cy = y_top + row_h // 2
        # label
        lines.append(f'<text x="{label_w - 4}" y="{cy + 4}" text-anchor="end" fill="#cbd5e1" font-size="11" font-family="monospace" font-weight="bold">{j["id"]}</text>')
        # K bar
        kw = bar_area * j["K"] / max_K
        color = "#ef4444" if j["K"] > j["optimal_max"] else "#38bdf8"
        lines.append(f'<rect x="{label_w}" y="{y_top + 4}" width="{kw:.1f}" height="{row_h - 12}" fill="{color}" rx="3" opacity="0.85"/>')
        lines.append(f'<text x="{label_w + kw + 4:.1f}" y="{cy + 3}" fill="{color}" font-size="9" font-family="monospace">K={j["K"]}  D={j["D"]}</text>')
        if j["note"]:
            lines.append(f'<text x="{W - 4}" y="{cy + 3}" text-anchor="end" fill="#ef4444" font-size="8" font-family="monospace">⚠ {j["note"][:28]}</text>')

    # x-axis ticks
    for tick in range(0, max_K + 1, 200):
        tx = label_w + bar_area * tick / max_K
        lines.append(f'<line x1="{tx:.1f}" y1="{H-16}" x2="{tx:.1f}" y2="{H-10}" stroke="#475569" stroke-width="1"/>')
        lines.append(f'<text x="{tx:.1f}" y="{H-4}" text-anchor="middle" fill="#475569" font-size="8" font-family="monospace">{tick}</text>')
    lines.append(f'<text x="{label_w + bar_area//2}" y="{H}" text-anchor="middle" fill="#475569" font-size="9" font-family="monospace">Stiffness K (N/m)</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SVG 2 — Impedance vs task success scatter
# ---------------------------------------------------------------------------

def _scatter_svg() -> str:
    W, H = 520, 320
    pad_l, pad_r, pad_t, pad_b = 60, 30, 40, 50
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b
    K_MAX_PLOT = 800

    def sx(k): return pad_l + plot_w * k / K_MAX_PLOT
    def sy(s): return pad_t + plot_h * (1 - s)  # s=1 at top

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>',
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="#f1f5f9" font-size="13" font-family="monospace" font-weight="bold">Impedance vs Task Success (50 episodes)</text>',
    ]

    # optimal band shading
    bx1 = sx(OPTIMAL_K_MIN); bx2 = sx(OPTIMAL_K_MAX)
    lines.append(f'<rect x="{bx1:.1f}" y="{pad_t}" width="{bx2-bx1:.1f}" height="{plot_h}" fill="#22c55e" fill-opacity="0.07"/>')
    lines.append(f'<line x1="{bx1:.1f}" y1="{pad_t}" x2="{bx1:.1f}" y2="{pad_t+plot_h}" stroke="#22c55e" stroke-width="1" stroke-dasharray="4,3"/>')
    lines.append(f'<line x1="{bx2:.1f}" y1="{pad_t}" x2="{bx2:.1f}" y2="{pad_t+plot_h}" stroke="#22c55e" stroke-width="1" stroke-dasharray="4,3"/>')
    lines.append(f'<text x="{(bx1+bx2)/2:.1f}" y="{pad_t+12}" text-anchor="middle" fill="#22c55e" font-size="8" font-family="monospace">OPTIMAL K=200-400</text>')

    # axes
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" stroke="#475569" stroke-width="1"/>')

    # jitter y slightly so overlapping dots are visible
    r2 = random.Random(99)
    for ep in EPISODES:
        jitter = r2.uniform(-0.03, 0.03)
        x = sx(ep["avg_K"])
        y = sy(int(ep["success"]) + jitter)
        in_band = OPTIMAL_K_MIN <= ep["avg_K"] <= OPTIMAL_K_MAX
        color = ("#38bdf8" if in_band else "#ef4444") if ep["success"] else ("#64748b" if in_band else "#7f1d1d")
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" opacity="0.75"/>')

    # y-axis labels
    for label, yv in [("FAIL", 0.0), ("SUCCESS", 1.0)]:
        lines.append(f'<text x="{pad_l - 6}" y="{sy(yv)+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="9" font-family="monospace">{label}</text>')
    # x-axis ticks
    for tick in range(0, K_MAX_PLOT + 1, 200):
        tx = sx(tick)
        lines.append(f'<line x1="{tx:.1f}" y1="{pad_t+plot_h}" x2="{tx:.1f}" y2="{pad_t+plot_h+4}" stroke="#475569" stroke-width="1"/>')
        lines.append(f'<text x="{tx:.1f}" y="{pad_t+plot_h+14}" text-anchor="middle" fill="#475569" font-size="8" font-family="monospace">{tick}</text>')
    lines.append(f'<text x="{pad_l + plot_w//2}" y="{H-2}" text-anchor="middle" fill="#475569" font-size="9" font-family="monospace">Avg Stiffness K (N/m)</text>')

    # legend
    lx = pad_l + 10
    for c, lbl in [("#38bdf8", "In-band success"), ("#ef4444", "Out-band success"), ("#64748b", "In-band fail"), ("#7f1d1d", "Out-band fail")]:
        lines.append(f'<circle cx="{lx+4}" cy="{H-8}" r="4" fill="{c}"/>')
        lines.append(f'<text x="{lx+12}" y="{H-4}" fill="#94a3b8" font-size="8" font-family="monospace">{lbl}</text>')
        lx += 110

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html() -> str:
    m = _metrics()
    stiff_svg = _stiffness_svg()
    scatter = _scatter_svg()
    recs_html = "".join(
        f'<li style="color:#fbbf24;margin:4px 0"><b>{j["id"]}:</b> reduce K from {j["K"]} → {j["optimal_max"]} N/m (currently {j["K"] - j["optimal_max"]}N/m over target max)</li>'
        for j in JOINTS if j["K"] > j["optimal_max"]
    )
    joint_rows = "".join(
        f'<tr><td>{j["id"]}</td><td>{j["K"]}</td><td>{j["D"]}</td>'
        f'<td>{j["optimal_min"]}-{j["optimal_max"]}</td>'
        f'<td style="color:{"#ef4444" if j["K"] > j["optimal_max"] else "#22c55e"}">{"SUBOPTIMAL" if j["K"] > j["optimal_max"] else "OK"}</td>'
        f'<td style="color:#94a3b8;font-size:10px">{j["note"] or "—"}</td></tr>'
        for j in JOINTS
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Joint Impedance Analyzer — Port 8309</title>
<style>
  body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
  h1{{color:#C74634;margin:0 0 4px 0}}  .sub{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
  .kpi-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}}
  .kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 20px;min-width:150px}}
  .kpi .val{{font-size:26px;font-weight:bold;color:#38bdf8}}
  .kpi .lbl{{font-size:11px;color:#94a3b8;margin-top:2px}}
  .kpi.warn .val{{color:#fbbf24}}
  .kpi.red .val{{color:#ef4444}}
  .section{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;margin-bottom:18px}}
  h2{{color:#38bdf8;font-size:14px;margin:0 0 12px 0}}
  .charts{{display:flex;gap:16px;flex-wrap:wrap}}
  table{{width:100%;border-collapse:collapse;font-size:12px}}
  th{{color:#94a3b8;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
  td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
  ul{{margin:4px 0;padding-left:18px;font-size:12px}}
</style></head><body>
<h1>Joint Impedance Analyzer</h1>
<div class="sub">Franka Arm · Cube-Lift Task · Port 8309 · {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</div>
<div class="kpi-row">
  <div class="kpi"><div class="val">{m['impedance_compliance_score']}%</div><div class="lbl">Compliance Score</div></div>
  <div class="kpi"><div class="val">{m['pct_episodes_in_optimal_band']}%</div><div class="lbl">Episodes in Optimal Band</div></div>
  <div class="kpi"><div class="val">{m['success_rate_in_band_pct']}%</div><div class="lbl">Success Rate (In-Band)</div></div>
  <div class="kpi red"><div class="val">{m['success_rate_out_band_pct']}%</div><div class="lbl">Success Rate (Out-Band)</div></div>
  <div class="kpi warn"><div class="val">{len(m['suboptimal_joints'])}</div><div class="lbl">Suboptimal Joints</div></div>
  <div class="kpi"><div class="val">{m['recommended_K_range']}</div><div class="lbl">Recommended K</div></div>
</div>
<div class="section">
  <h2>Stiffness Profiles &amp; Episode Scatter</h2>
  <div class="charts">
    <div>{stiff_svg}</div>
    <div>{scatter}</div>
  </div>
</div>
<div class="section">
  <h2>Joint-by-Joint Impedance Table</h2>
  <table><tr><th>Joint</th><th>K (N/m)</th><th>D</th><th>Optimal K Range</th><th>Status</th><th>Note</th></tr>
  {joint_rows}
  </table>
</div>
<div class="section">
  <h2>Tuning Recommendations</h2>
  <ul>{recs_html}</ul>
  <p style="color:#64748b;font-size:11px;margin-top:8px">Optimal impedance band for cube_lift: K=200-400 N/m. Joints J5/J6 are significantly above target — reducing their stiffness is expected to improve grasp compliance and success rate from ~28% (out-band) to ~78% (in-band).</p>
</div>
</body></html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _HAS_FASTAPI:
    app = FastAPI(title="Joint Impedance Analyzer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=_html())

    @app.get("/api/metrics")
    def metrics():
        return _metrics()

    @app.get("/api/joints")
    def joints():
        return {"joints": JOINTS}

    @app.get("/api/episodes")
    def episodes():
        return {"episodes": EPISODES, "optimal_K_min": OPTIMAL_K_MIN, "optimal_K_max": OPTIMAL_K_MAX}

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "joint_impedance_analyzer", "port": 8309}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8309)
    else:
        print("fastapi not found — starting stdlib http.server on port 8309")
        HTTPServer(("0.0.0.0", 8309), _Handler).serve_forever()

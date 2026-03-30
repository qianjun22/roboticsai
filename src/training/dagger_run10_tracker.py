#!/usr/bin/env python3
"""
DAgger Run10 Tracker — FastAPI service on port 8302
Tracks progress of DAgger run10 targeting >65% CL success rate.
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

# ── Mock data ──────────────────────────────────────────────────────────────────
RUN10_DATA = {
    "run_id": "dagger_run10",
    "total_steps": 5000,
    "current_step": 1420,
    "current_sr": 0.64,
    "beta": 0.71,
    "episodes_collected": 847,
    "start_date": "2026-03-28",
    "eta": "April 14, 2026",
    "projected_sr_low": 0.74,
    "projected_sr_high": 0.78,
    "target_sr": 0.65,
}

RUN9_TRAJECTORY = [
    {"step": 0,    "sr": 0.10},
    {"step": 500,  "sr": 0.23},
    {"step": 1000, "sr": 0.38},
    {"step": 1420, "sr": 0.51},
    {"step": 2000, "sr": 0.58},
    {"step": 3000, "sr": 0.63},
    {"step": 4000, "sr": 0.67},
    {"step": 5000, "sr": 0.71},
]

RUN10_TRAJECTORY = [
    {"step": 0,    "sr": 0.10},
    {"step": 500,  "sr": 0.29},
    {"step": 1000, "sr": 0.51},
    {"step": 1420, "sr": 0.64},
    # projected
    {"step": 2000, "sr": 0.69, "projected": True},
    {"step": 3000, "sr": 0.73, "projected": True},
    {"step": 4000, "sr": 0.76, "projected": True},
    {"step": 5000, "sr": 0.77, "projected": True},
]

BETA_SCHEDULE = [
    {"step": 0,    "beta": 0.90},
    {"step": 500,  "beta": 0.85},
    {"step": 1000, "beta": 0.78},
    {"step": 1420, "beta": 0.71},
    {"step": 2000, "beta": 0.60},
    {"step": 3000, "beta": 0.40},
    {"step": 4000, "beta": 0.22},
    {"step": 5000, "beta": 0.10},
]

EPISODE_TIMELINE = [
    {"day": "Mar 28", "eps": 110},
    {"day": "Mar 29", "eps": 145},
    {"day": "Mar 30", "eps": 132},
    {"day": "Mar 31", "eps": 158},
    {"day": "Apr 1",  "eps": 167},
    {"day": "Apr 2",  "eps": 135},
]


def build_svg_progress_dashboard() -> str:
    """SVG 1: Run10 progress dashboard."""
    w, h = 820, 460
    pct = RUN10_DATA["current_step"] / RUN10_DATA["total_steps"]
    sr = RUN10_DATA["current_sr"]
    beta = RUN10_DATA["beta"]
    eps = RUN10_DATA["episodes_collected"]

    # Chart area for beta + episode timeline
    cx, cy = 60, 60
    cw, ch = 340, 180

    # Beta schedule path
    def sx(step): return cx + (step / 5000) * cw
    def sy_beta(b): return cy + ch - (b - 0.0) / 1.0 * ch

    beta_path = " ".join(f"{sx(p['step']):.1f},{sy_beta(p['beta']):.1f}" for p in BETA_SCHEDULE)

    # Episode bars
    bar_w = 36
    max_eps = max(e["eps"] for e in EPISODE_TIMELINE)
    bar_area_x, bar_area_y = 460, 60
    bar_area_h = 180

    bars_svg = ""
    for i, ep in enumerate(EPISODE_TIMELINE):
        bh = (ep["eps"] / max_eps) * bar_area_h
        bx = bar_area_x + i * (bar_w + 8)
        by = bar_area_y + bar_area_h - bh
        bars_svg += f'<rect x="{bx}" y="{by:.1f}" width="{bar_w}" height="{bh:.1f}" fill="#38bdf8" opacity="0.85" rx="3"/>'
        bars_svg += f'<text x="{bx + bar_w/2:.1f}" y="{bar_area_y + bar_area_h + 16}" fill="#94a3b8" font-size="10" text-anchor="middle">{ep["day"]}</text>'
        bars_svg += f'<text x="{bx + bar_w/2:.1f}" y="{by - 4:.1f}" fill="#e2e8f0" font-size="10" text-anchor="middle">{ep["eps"]}</text>'

    # Progress arc
    arc_cx, arc_cy, arc_r = 230, 330, 80
    arc_angle = pct * 2 * math.pi
    arc_x = arc_cx + arc_r * math.sin(arc_angle)
    arc_y = arc_cy - arc_r * math.cos(arc_angle)
    large_arc = 1 if pct > 0.5 else 0

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#0f172a;border-radius:12px;font-family:monospace">
  <!-- Title -->
  <text x="{w//2}" y="32" fill="#f1f5f9" font-size="18" font-weight="bold" text-anchor="middle">DAgger Run10 Progress Dashboard</text>
  <text x="{w//2}" y="50" fill="#94a3b8" font-size="12" text-anchor="middle">Target: >65% CL Success Rate · Port 8302</text>

  <!-- Beta decay chart -->
  <rect x="{cx-10}" y="{cy-10}" width="{cw+20}" height="{ch+30}" fill="#1e293b" rx="8" opacity="0.6"/>
  <text x="{cx + cw//2}" y="{cy-14}" fill="#94a3b8" font-size="11" text-anchor="middle">β Decay Schedule (0.90 → 0.10)</text>
  <line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy+ch}" stroke="#334155" stroke-width="1"/>
  <line x1="{cx}" y1="{cy+ch}" x2="{cx+cw}" y2="{cy+ch}" stroke="#334155" stroke-width="1"/>
  <polyline points="{beta_path}" fill="none" stroke="#C74634" stroke-width="2.5"/>
  <!-- Current beta marker -->
  <circle cx="{sx(1420):.1f}" cy="{sy_beta(beta):.1f}" r="5" fill="#38bdf8"/>
  <text x="{sx(1420)+8:.1f}" y="{sy_beta(beta)-6:.1f}" fill="#38bdf8" font-size="11">β={beta}</text>
  <!-- axis labels -->
  <text x="{cx}" y="{cy+ch+20}" fill="#64748b" font-size="10">0</text>
  <text x="{cx+cw}" y="{cy+ch+20}" fill="#64748b" font-size="10">5000</text>
  <text x="{cx-12}" y="{cy+4}" fill="#64748b" font-size="10" text-anchor="end">1.0</text>
  <text x="{cx-12}" y="{cy+ch}" fill="#64748b" font-size="10" text-anchor="end">0.0</text>

  <!-- Episode timeline bars -->
  <rect x="{bar_area_x-10}" y="{bar_area_y-10}" width="{len(EPISODE_TIMELINE)*(bar_w+8)+20}" height="{bar_area_h+36}" fill="#1e293b" rx="8" opacity="0.6"/>
  <text x="{bar_area_x + len(EPISODE_TIMELINE)*(bar_w+8)//2}" y="{bar_area_y-14}" fill="#94a3b8" font-size="11" text-anchor="middle">Daily Episode Collection</text>
  {bars_svg}

  <!-- Progress arc -->
  <circle cx="{arc_cx}" cy="{arc_cy}" r="{arc_r+10}" fill="#1e293b" opacity="0.6"/>
  <circle cx="{arc_cx}" cy="{arc_cy}" r="{arc_r}" fill="none" stroke="#1e293b" stroke-width="16"/>
  <path d="M {arc_cx} {arc_cy - arc_r} A {arc_r} {arc_r} 0 {large_arc} 1 {arc_x:.2f} {arc_y:.2f}"
        fill="none" stroke="#C74634" stroke-width="16" stroke-linecap="round"/>
  <text x="{arc_cx}" y="{arc_cy - 10}" fill="#f1f5f9" font-size="22" font-weight="bold" text-anchor="middle">{RUN10_DATA['current_step']}</text>
  <text x="{arc_cx}" y="{arc_cy + 12}" fill="#94a3b8" font-size="12" text-anchor="middle">/ 5000 steps</text>
  <text x="{arc_cx}" y="{arc_cy + 30}" fill="#38bdf8" font-size="13" text-anchor="middle">{pct*100:.1f}% complete</text>

  <!-- Key metrics row -->
  <rect x="460" y="290" width="120" height="70" fill="#1e293b" rx="8" opacity="0.8"/>
  <text x="520" y="315" fill="#94a3b8" font-size="11" text-anchor="middle">Current SR</text>
  <text x="520" y="342" fill="#38bdf8" font-size="26" font-weight="bold" text-anchor="middle">{int(sr*100)}%</text>
  <text x="520" y="358" fill="#94a3b8" font-size="10" text-anchor="middle">target ≥65%</text>

  <rect x="600" y="290" width="120" height="70" fill="#1e293b" rx="8" opacity="0.8"/>
  <text x="660" y="315" fill="#94a3b8" font-size="11" text-anchor="middle">Episodes</text>
  <text x="660" y="342" fill="#C74634" font-size="26" font-weight="bold" text-anchor="middle">{eps}</text>
  <text x="660" y="358" fill="#94a3b8" font-size="10" text-anchor="middle">collected</text>

  <!-- ETA -->
  <rect x="460" y="375" width="260" height="50" fill="#1e293b" rx="8" opacity="0.8"/>
  <text x="590" y="397" fill="#94a3b8" font-size="11" text-anchor="middle">Projected SR at completion</text>
  <text x="590" y="418" fill="#a3e635" font-size="16" font-weight="bold" text-anchor="middle">{RUN10_DATA['projected_sr_low']*100:.0f}%–{RUN10_DATA['projected_sr_high']*100:.0f}% · ETA {RUN10_DATA['eta']}</text>

  <!-- Steps remaining -->
  <rect x="60" y="375" width="200" height="50" fill="#1e293b" rx="8" opacity="0.8"/>
  <text x="160" y="397" fill="#94a3b8" font-size="11" text-anchor="middle">Steps remaining</text>
  <text x="160" y="418" fill="#f1f5f9" font-size="20" font-weight="bold" text-anchor="middle">{RUN10_DATA['total_steps'] - RUN10_DATA['current_step']}</text>

  <!-- Target SR line indicator -->
  <rect x="280" y="375" width="160" height="50" fill="#064e3b" rx="8" opacity="0.8"/>
  <text x="360" y="397" fill="#6ee7b7" font-size="11" text-anchor="middle">Target SR</text>
  <text x="360" y="418" fill="#6ee7b7" font-size="20" font-weight="bold" text-anchor="middle">≥ 65% ✓ ({int(sr*100)}% now)</text>
</svg>'''
    return svg


def build_svg_comparison() -> str:
    """SVG 2: Run10 vs Run9 comparison."""
    w, h = 820, 400
    cx, cy = 60, 40
    cw, ch = 700, 280

    def sx(step): return cx + (step / 5000) * cw
    def sy(sr): return cy + ch - sr * ch

    # Run9 path (completed)
    r9_pts = " ".join(f"{sx(p['step']):.1f},{sy(p['sr']):.1f}" for p in RUN9_TRAJECTORY)
    # Run10 actual
    r10_actual = [p for p in RUN10_TRAJECTORY if not p.get("projected")]
    r10_proj   = [p for p in RUN10_TRAJECTORY if p.get("projected")]
    r10_pts_actual = " ".join(f"{sx(p['step']):.1f},{sy(p['sr']):.1f}" for p in r10_actual)
    # Connect projected from last actual
    r10_pts_proj = " ".join(f"{sx(p['step']):.1f},{sy(p['sr']):.1f}" for p in [r10_actual[-1]] + r10_proj)

    # Shaded advantage region between run10 and run9 from step 0 to 1420
    shared_steps = [0, 500, 1000, 1420]
    shade_top = " ".join(
        f"{sx(s):.1f},{sy(next(p['sr'] for p in RUN10_TRAJECTORY if p['step']==s)):.1f}"
        for s in shared_steps
    )
    shade_bot = " ".join(
        f"{sx(s):.1f},{sy(next(p['sr'] for p in RUN9_TRAJECTORY if p['step']==s)):.1f}"
        for s in reversed(shared_steps)
    )
    shade_pts = shade_top + " " + shade_bot

    # Grid lines
    grid = ""
    for sr_tick in [0.2, 0.4, 0.6, 0.8, 1.0]:
        gy = sy(sr_tick)
        grid += f'<line x1="{cx}" y1="{gy:.1f}" x2="{cx+cw}" y2="{gy:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{cx-8}" y="{gy+4:.1f}" fill="#475569" font-size="10" text-anchor="end">{int(sr_tick*100)}%</text>'
    for step_tick in [0, 1000, 2000, 3000, 4000, 5000]:
        gx = sx(step_tick)
        grid += f'<line x1="{gx:.1f}" y1="{cy}" x2="{gx:.1f}" y2="{cy+ch}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{gx:.1f}" y="{cy+ch+16}" fill="#475569" font-size="10" text-anchor="middle">{step_tick}</text>'

    # Target line 65%
    tgt_y = sy(0.65)

    # Current step marker
    cur_x = sx(1420)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#0f172a;border-radius:12px;font-family:monospace">
  <text x="{w//2}" y="24" fill="#f1f5f9" font-size="16" font-weight="bold" text-anchor="middle">Run10 vs Run9 Trajectory Comparison</text>

  <!-- Grid -->
  {grid}

  <!-- Axes -->
  <line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy+ch}" stroke="#475569" stroke-width="1.5"/>
  <line x1="{cx}" y1="{cy+ch}" x2="{cx+cw}" y2="{cy+ch}" stroke="#475569" stroke-width="1.5"/>
  <text x="{cx+cw//2}" y="{cy+ch+30}" fill="#64748b" font-size="11" text-anchor="middle">Training Steps</text>
  <text x="{cx-38}" y="{cy+ch//2}" fill="#64748b" font-size="11" text-anchor="middle" transform="rotate(-90,{cx-38},{cy+ch//2})">Success Rate</text>

  <!-- Advantage shading -->
  <polygon points="{shade_pts}" fill="#38bdf8" opacity="0.12"/>

  <!-- Target 65% line -->
  <line x1="{cx}" y1="{tgt_y:.1f}" x2="{cx+cw}" y2="{tgt_y:.1f}" stroke="#a3e635" stroke-width="1.5" stroke-dasharray="6,4"/>
  <text x="{cx+cw+4}" y="{tgt_y+4:.1f}" fill="#a3e635" font-size="10">65% target</text>

  <!-- Current step vertical -->
  <line x1="{cur_x:.1f}" y1="{cy}" x2="{cur_x:.1f}" y2="{cy+ch}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,3"/>
  <text x="{cur_x+4:.1f}" y="{cy+12}" fill="#f59e0b" font-size="10">step 1420 (now)</text>

  <!-- Run9 line -->
  <polyline points="{r9_pts}" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="6,3"/>
  <text x="{sx(5000)+4}" y="{sy(0.71)+4:.1f}" fill="#64748b" font-size="11">Run9 (done)</text>

  <!-- Run10 actual -->
  <polyline points="{r10_pts_actual}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
  <!-- Run10 projected -->
  <polyline points="{r10_pts_proj}" fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="5,4"/>
  <text x="{sx(5000)+4}" y="{sy(0.77)+4:.1f}" fill="#38bdf8" font-size="11">Run10 (proj)</text>

  <!-- Delta annotation at step 1420 -->
  <line x1="{cur_x+20:.1f}" y1="{sy(0.51):.1f}" x2="{cur_x+20:.1f}" y2="{sy(0.64):.1f}" stroke="#f59e0b" stroke-width="1.5" marker-end="url(#arr)"/>
  <text x="{cur_x+26:.1f}" y="{(sy(0.51)+sy(0.64))/2:.1f}" fill="#f59e0b" font-size="11">+13pp</text>

  <!-- Markers -->
  <circle cx="{sx(1420):.1f}" cy="{sy(0.64):.1f}" r="5" fill="#38bdf8"/>
  <circle cx="{sx(1420):.1f}" cy="{sy(0.51):.1f}" r="5" fill="#64748b"/>

  <!-- Legend -->
  <rect x="{cx}" y="{cy+ch+36}" width="14" height="3" fill="#64748b"/>
  <text x="{cx+18}" y="{cy+ch+41}" fill="#94a3b8" font-size="11">Run9 completed (SR=0.71 final)</text>
  <rect x="{cx+230}" y="{cy+ch+36}" width="14" height="3" fill="#38bdf8"/>
  <text x="{cx+248}" y="{cy+ch+41}" fill="#94a3b8" font-size="11">Run10 in-progress (proj 0.74-0.78)</text>
  <text x="{cx+480}" y="{cy+ch+41}" fill="#f59e0b" font-size="11">ETA: April 14, 2026</text>
</svg>'''
    return svg


def build_html() -> str:
    svg1 = build_svg_progress_dashboard()
    svg2 = build_svg_comparison()
    d = RUN10_DATA
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>DAgger Run10 Tracker — Port 8302</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Courier New', monospace; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 16px; border-left: 3px solid #C74634; }}
    .card.blue {{ border-left-color: #38bdf8; }}
    .card.green {{ border-left-color: #6ee7b7; }}
    .card.amber {{ border-left-color: #f59e0b; }}
    .card-label {{ color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .card-value {{ color: #f1f5f9; font-size: 1.5rem; font-weight: bold; margin-top: 6px; }}
    .card-sub {{ color: #94a3b8; font-size: 0.75rem; margin-top: 4px; }}
    .svg-wrap {{ background: #0f172a; border-radius: 12px; margin-bottom: 24px; overflow-x: auto; }}
    .section-title {{ color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 10px; }}
    .status-badge {{ display: inline-block; background: #064e3b; color: #6ee7b7; border-radius: 6px; padding: 3px 10px; font-size: 0.8rem; margin-left: 10px; }}
  </style>
</head>
<body>
  <h1>DAgger Run10 Tracker <span class="status-badge">IN PROGRESS</span></h1>
  <div class="subtitle">Port 8302 · Target: >65% CL Success Rate · ETA {d['eta']}</div>

  <div class="grid">
    <div class="card">
      <div class="card-label">Current Step</div>
      <div class="card-value">{d['current_step']:,}</div>
      <div class="card-sub">of {d['total_steps']:,} total ({d['current_step']/d['total_steps']*100:.1f}%)</div>
    </div>
    <div class="card blue">
      <div class="card-label">Success Rate</div>
      <div class="card-value">{d['current_sr']*100:.0f}%</div>
      <div class="card-sub">target ≥65% · +13pp vs run9</div>
    </div>
    <div class="card">
      <div class="card-label">Beta (β)</div>
      <div class="card-value">{d['beta']}</div>
      <div class="card-sub">decay 0.90 → 0.10</div>
    </div>
    <div class="card green">
      <div class="card-label">Episodes</div>
      <div class="card-value">{d['episodes_collected']}</div>
      <div class="card-sub">collected this run</div>
    </div>
    <div class="card amber">
      <div class="card-label">Steps Remaining</div>
      <div class="card-value">{d['total_steps']-d['current_step']:,}</div>
      <div class="card-sub">ETA {d['eta']}</div>
    </div>
    <div class="card green">
      <div class="card-label">Projected SR</div>
      <div class="card-value">{d['projected_sr_low']*100:.0f}–{d['projected_sr_high']*100:.0f}%</div>
      <div class="card-sub">at step 5000 completion</div>
    </div>
  </div>

  <div class="section-title">Progress Dashboard</div>
  <div class="svg-wrap">{svg1}</div>

  <div class="section-title">Run10 vs Run9 Trajectory</div>
  <div class="svg-wrap">{svg2}</div>

  <div style="color:#475569;font-size:0.75rem;margin-top:16px;">Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · OCI Robot Cloud · DAgger Run10</div>
</body>
</html>"""


if USE_FASTAPI:
    app = FastAPI(title="DAgger Run10 Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/status")
    async def status():
        d = RUN10_DATA
        return {
            "run_id": d["run_id"],
            "current_step": d["current_step"],
            "total_steps": d["total_steps"],
            "pct_complete": round(d["current_step"] / d["total_steps"] * 100, 1),
            "current_sr": d["current_sr"],
            "beta": d["beta"],
            "episodes_collected": d["episodes_collected"],
            "projected_sr_range": [d["projected_sr_low"], d["projected_sr_high"]],
            "eta": d["eta"],
            "target_sr": d["target_sr"],
            "above_target": d["current_sr"] >= d["target_sr"],
        }

    @app.get("/api/trajectory")
    async def trajectory():
        return {"run9": RUN9_TRAJECTORY, "run10": RUN10_TRAJECTORY, "beta_schedule": BETA_SCHEDULE}

else:
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(build_html().encode())

        def log_message(self, format, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8302)
    else:
        print("FastAPI not found — using stdlib HTTP server on port 8302")
        with socketserver.TCPServer(("", 8302), Handler) as httpd:
            httpd.serve_forever()

"""
Deal Flow Tracker — port 8651
OCI Robot Cloud | cycle-148A
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import json
from datetime import datetime

# ── Data ───────────────────────────────────────────────────────────────────────

DEALS = [
    # (name, stage, arr_k, source, days_in_stage)
    ("RoboMfg Inc",      "prospect",    18,  "cold",   5),
    ("AutoTech EU",      "qualified",   35,  "warm",  12),
    ("Nvidia Ref-A",     "demo",        62,  "nvidia", 8),
    ("LogiBot Co",       "demo",        29,  "warm",  15),
    ("Nvidia Ref-B",     "pilot",       84,  "nvidia", 6),
    ("FactoryOS",        "negotiation", 48,  "warm",  22),
    ("ArmaTech",         "negotiation", 32,  "cold",  31),
]

STAGES = ["prospect", "qualified", "demo", "pilot", "negotiation", "closed"]
FUNNEL_COUNTS = [24, 14, 9, 5, 3, 1]   # top-of-funnel → closed (illustrative)

SOURCE_COLOR = {"nvidia": "#38bdf8", "warm": "#22c55e", "cold": "#64748b"}

# ── SVG helpers ────────────────────────────────────────────────────────────────

def svg_pipeline() -> str:
    """Deal pipeline board — columns per stage, deal cards."""
    col_w   = 108
    col_gap = 8
    card_h  = 44
    card_gap = 6
    hdr_h   = 32
    W       = len(STAGES) * (col_w + col_gap) + 10
    # group deals by stage
    by_stage = {s: [] for s in STAGES}
    for d in DEALS:
        by_stage[d[1]].append(d)

    max_cards = max(len(v) for v in by_stage.values()) or 1
    H = hdr_h + max_cards * (card_h + card_gap) + 30

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{W//2}" y="18" fill="#f8fafc" font-size="14" font-weight="bold" '
        f'text-anchor="middle">Deal Pipeline — $284k ARR Total</text>',
    ]

    for ci, stage in enumerate(STAGES):
        cx = 5 + ci * (col_w + col_gap)
        # column header
        lines.append(f'<rect x="{cx}" y="24" width="{col_w}" height="{hdr_h-4}" rx="4" fill="#1e293b"/>')
        lines.append(f'<text x="{cx + col_w//2}" y="43" fill="#94a3b8" font-size="11" '
                      f'font-weight="bold" text-anchor="middle">{stage.upper()}</text>')

        for ri, deal in enumerate(by_stage[stage]):
            name, _, arr, source, days = deal
            card_y = 24 + hdr_h + ri * (card_h + card_gap)
            sc = SOURCE_COLOR.get(source, "#64748b")
            lines.append(f'<rect x="{cx}" y="{card_y}" width="{col_w}" height="{card_h}" '
                          f'rx="5" fill="{sc}" opacity="0.15"/>')
            lines.append(f'<rect x="{cx}" y="{card_y}" width="{col_w}" height="{card_h}" '
                          f'rx="5" fill="none" stroke="{sc}" stroke-width="1.5"/>')
            # source dot
            lines.append(f'<circle cx="{cx+10}" cy="{card_y+12}" r="4" fill="{sc}"/>')
            lines.append(f'<text x="{cx+18}" y="{card_y+16}" fill="#f8fafc" font-size="10">'
                          f'{name[:13]}</text>')
            lines.append(f'<text x="{cx+6}" y="{card_y+34}" fill="{sc}" font-size="11" '
                          f'font-weight="bold">${arr}k ARR</text>')

    # legend
    ly = H - 14
    lx = 6
    for src, sc in SOURCE_COLOR.items():
        lines.append(f'<circle cx="{lx+5}" cy="{ly}" r="4" fill="{sc}"/>')
        lines.append(f'<text x="{lx+13}" y="{ly+4}" fill="{sc}" font-size="10">{src.upper()}</text>')
        lx += 100

    lines.append('</svg>')
    return "\n".join(lines)


def svg_velocity_scatter() -> str:
    """Deal velocity scatter — days_in_stage vs deal_size, source-colored."""
    W, H = 560, 320
    ml, mr, mt, mb = 55, 20, 35, 45

    iw = W - ml - mr
    ih = H - mt - mb

    days_max = 40
    arr_max  = 100

    def px(d): return ml + d / days_max * iw
    def py(a): return mt + ih - a / arr_max * ih

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{W//2}" y="22" fill="#f8fafc" font-size="14" font-weight="bold" '
        f'text-anchor="middle">Deal Velocity (days in stage vs ARR)</text>',
    ]

    # grid
    for d_tick in [0, 10, 20, 30, 40]:
        x = px(d_tick)
        lines.append(f'<line x1="{x:.1f}" y1="{mt}" x2="{x:.1f}" y2="{mt+ih}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{mt+ih+14}" fill="#64748b" font-size="10" text-anchor="middle">{d_tick}d</text>')
    for a_tick in [0, 25, 50, 75, 100]:
        y = py(a_tick)
        lines.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{ml+iw}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{ml-5}" y="{y+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">${a_tick}k</text>')

    # axis labels
    lines.append(f'<text x="{ml+iw//2}" y="{H-5}" fill="#94a3b8" font-size="10" text-anchor="middle">Days in Stage</text>')
    lines.append(f'<text x="12" y="{mt+ih//2}" fill="#94a3b8" font-size="10" text-anchor="middle" '
                 f'transform="rotate(-90,12,{mt+ih//2})">ARR ($k)</text>')

    # trend line (simple: nvidia cluster top-left)
    x1, y1 = px(5), py(80)
    x2, y2 = px(35), py(28)
    lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                 f'stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.7"/>')
    lines.append(f'<text x="{x2+4:.1f}" y="{y2:.1f}" fill="#f59e0b" font-size="9">trend</text>')

    # points
    for name, stage, arr, source, days in DEALS:
        sc = SOURCE_COLOR.get(source, "#64748b")
        x = px(days)
        y = py(arr)
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{sc}" opacity="0.85"/>')
        lines.append(f'<text x="{x+9:.1f}" y="{y+4:.1f}" fill="{sc}" font-size="9">{name[:8]}</text>')

    # NVIDIA cluster annotation
    lines.append(f'<rect x="{px(4):.1f}" y="{py(92):.1f}" width="130" height="20" rx="4" '
                 f'fill="#38bdf8" opacity="0.1"/>')
    lines.append(f'<text x="{px(4)+4:.1f}" y="{py(92)+14:.1f}" fill="#38bdf8" font-size="9">'
                 f'NVIDIA-referred: 2.3× faster close</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def svg_conversion_funnel() -> str:
    """Conversion funnel — trapezoid SVG, 6 stages."""
    W, H = 400, 340
    stage_labels = STAGES
    counts       = FUNNEL_COUNTS
    colors = ["#38bdf8","#60a5fa","#818cf8","#a78bfa","#C74634","#22c55e"]

    top_w   = 340
    step_h  = 42
    shrink  = 22
    cx      = W // 2
    margin  = 30

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{cx}" y="20" fill="#f8fafc" font-size="14" font-weight="bold" '
        f'text-anchor="middle">Conversion Funnel</text>',
    ]

    for i, (stage, count, color) in enumerate(zip(stage_labels, counts, colors)):
        tw = top_w - i * shrink * 2
        bw = top_w - (i+1) * shrink * 2
        ty = margin + i * step_h
        by = ty + step_h - 2

        x_tl = cx - tw // 2
        x_tr = cx + tw // 2
        x_bl = cx - bw // 2
        x_br = cx + bw // 2

        conv = f"{counts[i]/counts[0]*100:.0f}%" if i == 0 else f"{counts[i]/counts[i-1]*100:.0f}%"

        lines.append(f'<polygon points="{x_tl},{ty} {x_tr},{ty} {x_br},{by} {x_bl},{by}" '
                     f'fill="{color}" opacity="0.25"/>')
        lines.append(f'<polygon points="{x_tl},{ty} {x_tr},{ty} {x_br},{by} {x_bl},{by}" '
                     f'fill="none" stroke="{color}" stroke-width="1.5"/>')
        lines.append(f'<text x="{cx}" y="{ty + step_h//2 + 4}" fill="{color}" font-size="12" '
                     f'font-weight="bold" text-anchor="middle">{stage.upper()} — {count}</text>')
        if i > 0:
            lines.append(f'<text x="{x_tr + 8}" y="{ty+10}" fill="#f59e0b" font-size="10">'
                         f'↓{conv}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ── HTML page ──────────────────────────────────────────────────────────────────

def build_html() -> str:
    pipe  = svg_pipeline()
    vel   = svg_velocity_scatter()
    funl  = svg_conversion_funnel()

    pipeline_arr = sum(d[2] for d in DEALS)
    neg_arr      = sum(d[2] for d in DEALS if d[1] == "negotiation")

    metrics = [
        ("Active Deals",         "7",        "in pipeline"),
        ("Total Pipeline ARR",   f"${pipeline_arr}k", "combined"),
        ("In Negotiation",       f"${neg_arr}k ARR", "2 deals"),
        ("NVIDIA Ref Speed",     "2.3×",     "faster close"),
        ("Avg Deal Size",        f"${pipeline_arr//len(DEALS)}k", "per deal"),
        ("Top Deal",             "$84k",     "Nvidia Ref-B (pilot)"),
    ]

    cards = "".join(
        f'<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;min-width:150px">'
        f'<div style="color:#94a3b8;font-size:11px;margin-bottom:4px">{m[0]}</div>'
        f'<div style="color:#38bdf8;font-size:24px;font-weight:bold">{m[1]}</div>'
        f'<div style="color:#64748b;font-size:10px;margin-top:2px">{m[2]}</div>'
        f'</div>'
        for m in metrics
    )

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Deal Flow Tracker | OCI Robot Cloud</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#f8fafc;font-family:'JetBrains Mono',monospace,sans-serif;padding:24px}}
    h1{{font-size:22px;color:#38bdf8;margin-bottom:4px}}
    .sub{{color:#64748b;font-size:13px;margin-bottom:24px}}
    .metrics{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:28px}}
    .section{{margin-bottom:32px}}
    .section h2{{font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px;
                 border-bottom:1px solid #1e293b;padding-bottom:6px}}
    .row{{display:flex;flex-wrap:wrap;gap:24px;align-items:flex-start}}
    svg{{border-radius:8px;display:block}}
  </style>
</head>
<body>
  <h1>Deal Flow Tracker</h1>
  <div class="sub">OCI Robot Cloud &mdash; port 8651 &mdash; {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</div>

  <div class="metrics">{cards}</div>

  <div class="section">
    <h2>Deal Pipeline Board</h2>
    {pipe}
  </div>

  <div class="section row">
    <div>
      <h2>Deal Velocity</h2>
      {vel}
    </div>
    <div>
      <h2>Conversion Funnel</h2>
      {funl}
    </div>
  </div>
</body>
</html>"""


# ── App ────────────────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="Deal Flow Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "deal_flow_tracker", "port": 8651})

    @app.get("/deals")
    async def deals():
        return JSONResponse([
            {"name": d[0], "stage": d[1], "arr_k": d[2], "source": d[3], "days_in_stage": d[4]}
            for d in DEALS
        ])

    @app.get("/metrics")
    async def metrics():
        pipeline_arr = sum(d[2] for d in DEALS)
        return JSONResponse({
            "active_deals": len(DEALS),
            "total_pipeline_arr_k": pipeline_arr,
            "negotiation_arr_k": sum(d[2] for d in DEALS if d[1] == "negotiation"),
            "nvidia_ref_speed_multiplier": 2.3,
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8651)

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "deal_flow_tracker", "port": 8651}).encode()
                ct = "application/json"
            else:
                body = build_html().encode()
                ct = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        print("FastAPI unavailable — running stdlib HTTPServer on :8651")
        HTTPServer(("0.0.0.0", 8651), Handler).serve_forever()

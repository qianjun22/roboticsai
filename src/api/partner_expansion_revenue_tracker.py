"""
Partner Expansion Revenue Tracker — port 8661
OCI Robot Cloud | cycle-150B
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False


# ── SVG helpers ────────────────────────────────────────────────────────────────

def svg_partner_mrr_stacked() -> str:
    """5 partners × 3 months stacked bar (base_MRR / upsell / cross_sell)."""
    partners = ["PrecisionInno", "Apptronik", "1X Tech", "Machina Labs", "Wandelbots"]
    short    = ["PI", "Apt", "1X", "ML", "WB"]
    # [base_mrr, upsell, cross_sell] for months M1, M2, M3
    data = {
        "PI":  [(520, 80, 30), (560, 160, 50), (600, 280, 80)],
        "Apt": [(380, 60, 20), (400, 100, 35), (420, 180, 60)],
        "1X":  [(290, 40, 15), (270, 30, 10), (250, 20,  8)],
        "ML":  [(240, 30, 10), (260, 50, 18), (280, 70, 25)],
        "WB":  [(180, 20,  8), (195, 35, 12), (210, 55, 20)],
    }
    months = ["Jan", "Feb", "Mar"]
    colors = {"base": "#38bdf8", "upsell": "#C74634", "cross": "#22c55e"}

    W, H = 720, 400
    pad_l, pad_r, pad_t, pad_b = 110, 20, 50, 60
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b
    max_val = 1000  # max stacked

    n_partners = len(short)
    n_months   = 3
    group_gap  = 12
    bar_gap    = 4
    group_w    = (plot_w - (n_partners - 1) * group_gap) / n_partners
    bar_w      = (group_w - (n_months - 1) * bar_gap) / n_months

    def bh(v): return v / max_val * plot_h
    def gx(pi): return pad_l + pi * (group_w + group_gap)
    def bx(pi, mi): return gx(pi) + mi * (bar_w + bar_gap)

    rects = []
    for pi, s in enumerate(short):
        for mi, (base, up, cross) in enumerate(data[s]):
            x = bx(pi, mi)
            y_base  = pad_t + plot_h - bh(base)
            y_up    = y_base - bh(up)
            y_cross = y_up   - bh(cross)
            rects.append(f'<rect x="{x:.1f}" y="{y_base:.1f}" width="{bar_w:.1f}" height="{bh(base):.1f}" fill="{colors["base"]}" rx="2"/>')
            rects.append(f'<rect x="{x:.1f}" y="{y_up:.1f}"   width="{bar_w:.1f}" height="{bh(up):.1f}"   fill="{colors["upsell"]}" rx="2"/>')
            rects.append(f'<rect x="{x:.1f}" y="{y_cross:.1f}" width="{bar_w:.1f}" height="{bh(cross):.1f}" fill="{colors["cross"]}" rx="2"/>')
        # partner label
        lx = gx(pi) + group_w / 2
        rects.append(f'<text x="{lx:.1f}" y="{pad_t+plot_h+16}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">{s}</text>')
        rects.append(f'<text x="{pad_l-6}" y="{pad_t+plot_h//2}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace" transform="rotate(-90,{pad_l-6},{pad_t+plot_h//2})">MRR ($)</text>')

    # month sub-labels under first group
    for mi, m in enumerate(months):
        x = bx(0, mi) + bar_w / 2
        rects.append(f'<text x="{x:.1f}" y="{pad_t+plot_h+30}" text-anchor="middle" fill="#475569" font-size="9" font-family="monospace">{m}</text>')

    # y grid
    grid = "".join(f'<line x1="{pad_l}" y1="{pad_t + plot_h - bh(v):.1f}" x2="{W-pad_r}" y2="{pad_t + plot_h - bh(v):.1f}" stroke="#334155" stroke-width="0.7"/>' for v in [200, 400, 600, 800, 1000])
    yticks = "".join(f'<text x="{pad_l-6}" y="{pad_t + plot_h - bh(v) + 4:.1f}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{v}</text>' for v in [200, 400, 600, 800, 1000])

    rects_svg = "\n  ".join(rects)

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px;background:#1e293b;border-radius:10px;">
  <text x="{W//2}" y="28" text-anchor="middle" fill="#e2e8f0" font-size="15" font-weight="bold" font-family="monospace">Partner MRR Breakdown — 3-Month Stacked</text>
  <rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" fill="#0f172a" rx="4"/>
  {grid}
  {yticks}
  {rects_svg}
  <!-- legend -->
  <rect x="{pad_l}" y="36" width="12" height="10" fill="{colors['base']}" rx="2"/>
  <text x="{pad_l+16}" y="45" fill="#94a3b8" font-size="11" font-family="monospace">Base MRR</text>
  <rect x="{pad_l+100}" y="36" width="12" height="10" fill="{colors['upsell']}" rx="2"/>
  <text x="{pad_l+116}" y="45" fill="#94a3b8" font-size="11" font-family="monospace">Upsell</text>
  <rect x="{pad_l+175}" y="36" width="12" height="10" fill="{colors['cross']}" rx="2"/>
  <text x="{pad_l+191}" y="45" fill="#94a3b8" font-size="11" font-family="monospace">Cross-sell</text>
  <!-- PI fastest note -->
  <text x="{W-pad_r}" y="{pad_t+14}" text-anchor="end" fill="#C74634" font-size="11" font-family="monospace">PI growing fastest ↑</text>
</svg>"""


def svg_nrr_waterfall() -> str:
    """NRR waterfall: start → new → expansion → churn → contraction → end."""
    W, H = 720, 380
    pad_l, pad_r, pad_t, pad_b = 60, 30, 50, 60
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    steps = [
        ("Start\n$2,927",   2927, "base"),
        ("+New\n+$840",     840, "pos"),
        ("+Expansion\n+$412", 412, "pos"),
        ("−Churn\n−$240",  -240, "neg"),
        ("−Contraction\n−$120", -120, "neg"),
        ("End\n$3,819",    3819, "base"),
    ]

    max_val = 4200
    bar_w = (plot_w - 5 * 18) / 6  # 6 bars, 5 gaps of 18

    def bh(v): return abs(v) / max_val * plot_h
    def bx(i): return pad_l + i * (bar_w + 18)

    # running total for stacking pos/neg
    running = 2927
    rects = []
    labels = []
    connectors = []

    prev_top = pad_t + plot_h - bh(running)

    for i, (label, val, kind) in enumerate(steps):
        x = bx(i)
        if kind == "base":
            y     = pad_t + plot_h - bh(val)
            h     = bh(val)
            color = "#38bdf8"
            top   = y
        elif kind == "pos":
            y     = pad_t + plot_h - bh(running + val)
            h     = bh(val)
            color = "#22c55e"
            top   = y
            running += val
        else:
            y     = pad_t + plot_h - bh(running)
            h     = bh(abs(val))
            color = "#ef4444"
            top   = y
            running += val  # val is negative

        rects.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}" rx="3" fill-opacity="0.9"/>')

        # value label on bar
        mid_y = y + h / 2 + 4
        lbl_val = f"+{abs(val)}" if kind == "pos" else (f"−{abs(val)}" if kind == "neg" else f"${val:,}")
        rects.append(f'<text x="{x + bar_w/2:.1f}" y="{mid_y:.1f}" text-anchor="middle" fill="#fff" font-size="11" font-weight="bold" font-family="monospace">{lbl_val}</text>')

        # x-axis label (multiline via tspan)
        parts = label.split("\n")
        y_lbl = pad_t + plot_h + 16
        for pi, part in enumerate(parts):
            rects.append(f'<text x="{x + bar_w/2:.1f}" y="{y_lbl + pi*13}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">{part}</text>')

        # connector line to next bar
        if i < len(steps) - 1:
            if kind == "base":
                conn_y = pad_t + plot_h - bh(val)
            else:
                conn_y = top if kind == "pos" else y
            nx = bx(i + 1)
            connectors.append(f'<line x1="{x + bar_w:.1f}" y1="{conn_y:.1f}" x2="{nx:.1f}" y2="{conn_y:.1f}" stroke="#475569" stroke-width="1" stroke-dasharray="3,2"/>')

    # y grid
    grid = "".join(f'<line x1="{pad_l}" y1="{pad_t + plot_h - bh(v):.1f}" x2="{W-pad_r}" y2="{pad_t + plot_h - bh(v):.1f}" stroke="#334155" stroke-width="0.7"/>' for v in [1000, 2000, 3000, 4000])
    yticks = "".join(f'<text x="{pad_l-5}" y="{pad_t + plot_h - bh(v) + 4:.1f}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">${v:,}</text>' for v in [1000, 2000, 3000, 4000])

    rects_svg   = "\n  ".join(rects)
    conn_svg    = "\n  ".join(connectors)

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px;background:#1e293b;border-radius:10px;">
  <text x="{W//2}" y="28" text-anchor="middle" fill="#e2e8f0" font-size="15" font-weight="bold" font-family="monospace">NRR Waterfall — NRR 127%</text>
  <rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" fill="#0f172a" rx="4"/>
  {grid}
  {yticks}
  {conn_svg}
  {rects_svg}
  <text x="{pad_l + plot_w//2}" y="{H - 8}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">MRR ($)</text>
</svg>"""


def svg_upsell_pipeline() -> str:
    """5 upsell opportunities as horizontal bars with probability and expected ARR."""
    W, H = 720, 340
    pad_l, pad_r, pad_t, pad_b = 170, 120, 50, 40
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    opps = [
        ("PI — bimanual arm",     0.78, 420 * 12),
        ("Apt — GPU tier up",     0.65, 280 * 12),
        ("1X — recovery pkg",     0.40, 140 * 12),
        ("Machina — pilot ext.",  0.55, 200 * 12),
        ("Wandelbots — pro plan", 0.50, 180 * 12),
    ]
    max_arr = 6000

    bar_h  = 32
    gap    = (plot_h - len(opps) * bar_h) / (len(opps) + 1)

    def bw(v): return v / max_arr * plot_w

    rects = []
    for i, (name, prob, arr) in enumerate(opps):
        y = pad_t + gap + i * (bar_h + gap)
        # probability-shaded bar
        color = "#22c55e" if prob >= 0.65 else ("#facc15" if prob >= 0.50 else "#ef4444")
        rects.append(f'<rect x="{pad_l}" y="{y:.1f}" width="{bw(arr):.1f}" height="{bar_h}" fill="{color}" rx="4" fill-opacity="{0.5 + prob * 0.4:.2f}"/>')
        # probability badge
        prob_x = pad_l + bw(arr) + 8
        rects.append(f'<rect x="{prob_x:.1f}" y="{y+4:.1f}" width="46" height="20" fill="#1e293b" rx="3" stroke="{color}" stroke-width="1"/>')
        rects.append(f'<text x="{prob_x+23:.1f}" y="{y+17:.1f}" text-anchor="middle" fill="{color}" font-size="10" font-weight="bold" font-family="monospace">{int(prob*100)}%</text>')
        # ARR label
        rects.append(f'<text x="{prob_x+55:.1f}" y="{y+17:.1f}" fill="#94a3b8" font-size="10" font-family="monospace">${arr//1000}k ARR</text>')
        # opportunity name
        rects.append(f'<text x="{pad_l-8}" y="{y+bar_h//2+4:.1f}" text-anchor="end" fill="#e2e8f0" font-size="11" font-family="monospace">{name}</text>')

    # x grid
    grid = "".join(f'<line x1="{pad_l + bw(v):.1f}" y1="{pad_t}" x2="{pad_l + bw(v):.1f}" y2="{pad_t+plot_h}" stroke="#334155" stroke-width="0.7"/>' for v in [1000, 2000, 3000, 4000, 5000, 6000])
    xticks = "".join(f'<text x="{pad_l + bw(v):.1f}" y="{pad_t+plot_h+14}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">${v//1000}k</text>' for v in [1000, 2000, 3000, 4000, 5000, 6000])

    rects_svg = "\n  ".join(rects)

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px;background:#1e293b;border-radius:10px;">
  <text x="{W//2}" y="28" text-anchor="middle" fill="#e2e8f0" font-size="15" font-weight="bold" font-family="monospace">Upsell Pipeline — $84k ARR Total</text>
  <rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" fill="#0f172a" rx="4"/>
  {grid}
  {xticks}
  {rects_svg}
  <text x="{pad_l + plot_w//2}" y="{H-6}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">Expected ARR ($)</text>
</svg>"""


# ── HTML page ──────────────────────────────────────────────────────────────────

def build_html() -> str:
    mrr_chart      = svg_partner_mrr_stacked()
    nrr_chart      = svg_nrr_waterfall()
    pipeline_chart = svg_upsell_pipeline()

    metrics = [
        ("Net Revenue Retention", "127%",    "healthy expansion",  "#22c55e"),
        ("PI Upsell",             "+$420/mo", "fastest growing",    "#38bdf8"),
        ("Apt Upsell",            "+$280/mo", "GPU tier upgrade",   "#38bdf8"),
        ("1X Tech",               "−$140/mo", "at-risk · monitor",  "#ef4444"),
        ("Expansion Pipeline",    "$84k ARR", "5 opportunities",    "#C74634"),
    ]

    metric_cards = "".join(f"""
      <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 18px;min-width:140px;flex:1;">
        <div style="color:#64748b;font-size:11px;margin-bottom:4px;">{m[0]}</div>
        <div style="color:#e2e8f0;font-size:20px;font-weight:bold;">{m[1]}</div>
        <div style="color:{m[3]};font-size:12px;margin-top:2px;">{m[2]}</div>
      </div>""" for m in metrics)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Partner Expansion Revenue Tracker — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px;}}
  h1{{font-size:22px;color:#38bdf8;margin-bottom:4px;}}
  .subtitle{{color:#64748b;font-size:13px;margin-bottom:24px;}}
  .metrics{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:28px;}}
  .chart-block{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px;margin-bottom:20px;}}
  .chart-title{{color:#94a3b8;font-size:13px;margin-bottom:12px;letter-spacing:.05em;text-transform:uppercase;}}
  .badge{{display:inline-block;background:#C74634;color:#fff;font-size:11px;padding:2px 8px;border-radius:4px;margin-left:8px;vertical-align:middle;}}
</style>
</head>
<body>
<h1>Partner Expansion Revenue Tracker <span class="badge">port 8661</span></h1>
<div class="subtitle">OCI Robot Cloud · cycle-150B · NRR tracking + upsell pipeline</div>

<div class="metrics">
  {metric_cards}
</div>

<div class="chart-block">
  <div class="chart-title">Partner MRR Breakdown — 3-Month Stacked</div>
  {mrr_chart}
</div>

<div class="chart-block">
  <div class="chart-title">NRR Waterfall — Start to End MRR</div>
  {nrr_chart}
</div>

<div class="chart-block">
  <div class="chart-title">Upsell Pipeline — Probability &amp; Expected ARR</div>
  {pipeline_chart}
</div>

<div style="color:#334155;font-size:11px;margin-top:16px;text-align:center;">
  OCI Robot Cloud · Partner Expansion Revenue Tracker · port 8661 · stdlib-only fallback supported
</div>
</body>
</html>"""


# ── App ────────────────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="Partner Expansion Revenue Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "partner_expansion_revenue_tracker", "port": 8661}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8661)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"partner_expansion_revenue_tracker","port":8661}'
                ct = b"application/json"
            else:
                body = build_html().encode()
                ct = b"text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct.decode())
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        srv = HTTPServer(("0.0.0.0", 8661), Handler)
        print("Partner Expansion Revenue Tracker running on port 8661 (stdlib)")
        srv.serve_forever()

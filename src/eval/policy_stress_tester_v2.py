"""
policy_stress_tester_v2.py — OCI Robot Cloud
Port 8682 | Stress-test BC vs DAgger under 6 environmental conditions × 3 severity levels.
Dark theme FastAPI (#0f172a, #C74634, #38bdf8). stdlib only.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_heatmap() -> str:
    """Stress-test matrix heatmap: 6 conditions × 3 severity levels.
    Color = success rate under stress (green=high, red=low).
    DAgger consistently greener than BC.
    """
    conditions = ["sensor_noise", "lighting_change", "latency_spike",
                  "object_shift", "occlusion", "temperature"]
    severities = ["Severity-1", "Severity-2", "Severity-3"]

    # BC success rates [condition][severity]
    bc = [
        [0.82, 0.71, 0.58],  # sensor_noise
        [0.78, 0.63, 0.51],  # lighting_change  (worst)
        [0.80, 0.68, 0.54],  # latency_spike
        [0.85, 0.74, 0.60],  # object_shift
        [0.76, 0.62, 0.49],  # occlusion
        [0.83, 0.72, 0.59],  # temperature
    ]
    # DAgger success rates — consistently greener
    dagger = [
        [0.91, 0.85, 0.76],
        [0.89, 0.80, 0.70],
        [0.92, 0.86, 0.78],
        [0.93, 0.88, 0.80],
        [0.88, 0.82, 0.73],
        [0.91, 0.85, 0.77],
    ]

    def sr_to_color(sr: float) -> str:
        # green (#22c55e) → yellow (#facc15) → red (#ef4444)
        if sr >= 0.75:
            t = (sr - 0.75) / 0.25
            r = int(34 + t * (34 - 34))
            g = int(197 + t * (197 - 197))
            b = int(94 + t * (94 - 94))
            r = int((1 - t) * 250 + t * 34)
            g = int((1 - t) * 204 + t * 197)
            b = int((1 - t) * 21 + t * 94)
        else:
            t = sr / 0.75
            r = int((1 - t) * 239 + t * 250)
            g = int((1 - t) * 68 + t * 204)
            b = int((1 - t) * 68 + t * 21)
        return f"rgb({r},{g},{b})"

    cell_w, cell_h = 80, 40
    label_w = 130
    top_pad = 80
    section_gap = 20
    cols = len(severities)
    rows = len(conditions)
    total_w = label_w + cols * cell_w * 2 + section_gap + 40
    total_h = top_pad + rows * cell_h + 30

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" '
        f'style="background:#0f172a;font-family:monospace">',
        # Title
        f'<text x="{total_w//2}" y="22" fill="#38bdf8" font-size="14" font-weight="bold" '
        f'text-anchor="middle">Stress Test Matrix Heatmap — BC vs DAgger</text>',
        # Section labels
        f'<text x="{label_w + cols*cell_w//2}" y="44" fill="#94a3b8" font-size="11" text-anchor="middle">BC</text>',
        f'<text x="{label_w + cols*cell_w + section_gap + cols*cell_w//2}" y="44" fill="#38bdf8" '
        f'font-size="11" text-anchor="middle">DAgger</text>',
    ]

    # Severity column headers
    for si, sev in enumerate(severities):
        bx = label_w + si * cell_w + cell_w // 2
        dx = label_w + cols * cell_w + section_gap + si * cell_w + cell_w // 2
        lines.append(f'<text x="{bx}" y="60" fill="#64748b" font-size="9" text-anchor="middle">{sev}</text>')
        lines.append(f'<text x="{dx}" y="60" fill="#64748b" font-size="9" text-anchor="middle">{sev}</text>')

    for ri, cond in enumerate(conditions):
        y = top_pad + ri * cell_h
        # Row label
        lines.append(f'<text x="{label_w - 6}" y="{y + cell_h//2 + 4}" fill="#cbd5e1" '
                     f'font-size="9" text-anchor="end">{cond}</text>')
        for si in range(cols):
            # BC cell
            bx = label_w + si * cell_w
            bc_sr = bc[ri][si]
            lines.append(f'<rect x="{bx}" y="{y}" width="{cell_w - 2}" height="{cell_h - 2}" '
                         f'fill="{sr_to_color(bc_sr)}" rx="3"/>')
            lines.append(f'<text x="{bx + cell_w//2}" y="{y + cell_h//2 + 4}" fill="#0f172a" '
                         f'font-size="9" text-anchor="middle" font-weight="bold">{bc_sr:.2f}</text>')
            # DAgger cell
            dx = label_w + cols * cell_w + section_gap + si * cell_w
            dg_sr = dagger[ri][si]
            lines.append(f'<rect x="{dx}" y="{y}" width="{cell_w - 2}" height="{cell_h - 2}" '
                         f'fill="{sr_to_color(dg_sr)}" rx="3"/>')
            lines.append(f'<text x="{dx + cell_w//2}" y="{y + cell_h//2 + 4}" fill="#0f172a" '
                         f'font-size="9" text-anchor="middle" font-weight="bold">{dg_sr:.2f}</text>')

    # Legend
    legend_y = total_h - 18
    for i, (label, color) in enumerate([("Low SR", "rgb(239,68,68)"), ("Mid SR", "rgb(250,204,21)"), ("High SR", "rgb(34,197,94)")]):
        lx = total_w // 2 - 120 + i * 80
        lines.append(f'<rect x="{lx}" y="{legend_y}" width="14" height="10" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx + 18}" y="{legend_y + 9}" fill="#94a3b8" font-size="8">{label}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def svg_failure_bars() -> str:
    """Grouped bar chart: failure rate by condition, BC vs DAgger."""
    conditions = ["sensor_noise", "lighting_change", "latency_spike",
                  "object_shift", "occlusion", "temperature"]
    bc_fail   = [0.42, 0.49, 0.46, 0.40, 0.51, 0.41]
    dagger_fail = [0.24, 0.30, 0.22, 0.20, 0.27, 0.23]

    w, h = 620, 300
    pad_l, pad_r, pad_t, pad_b = 50, 20, 40, 70
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    n = len(conditions)
    group_w = chart_w / n
    bar_w = group_w * 0.35

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{w//2}" y="22" fill="#38bdf8" font-size="13" font-weight="bold" '
        f'text-anchor="middle">Failure Rate by Stress Condition</text>',
        # Axes
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#334155" stroke-width="1"/>',
        f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#334155" stroke-width="1"/>',
    ]

    # Y gridlines
    for tick in [0.1, 0.2, 0.3, 0.4, 0.5]:
        yy = pad_t + chart_h - tick * chart_h / 0.6
        lines.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{pad_l+chart_w}" y2="{yy:.1f}" '
                     f'stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{pad_l-4}" y="{yy+4:.1f}" fill="#64748b" font-size="8" text-anchor="end">{tick:.1f}</text>')

    for i, cond in enumerate(conditions):
        gx = pad_l + i * group_w + group_w * 0.1
        # BC bar (red)
        bh = bc_fail[i] / 0.6 * chart_h
        by = pad_t + chart_h - bh
        lines.append(f'<rect x="{gx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                     f'fill="#C74634" rx="2" opacity="0.85"/>')
        lines.append(f'<text x="{gx + bar_w/2:.1f}" y="{by-3:.1f}" fill="#fca5a5" font-size="7.5" '
                     f'text-anchor="middle">{bc_fail[i]:.2f}</text>')
        # DAgger bar (blue)
        dh = dagger_fail[i] / 0.6 * chart_h
        dy = pad_t + chart_h - dh
        dx = gx + bar_w + 3
        lines.append(f'<rect x="{dx:.1f}" y="{dy:.1f}" width="{bar_w:.1f}" height="{dh:.1f}" '
                     f'fill="#38bdf8" rx="2" opacity="0.85"/>')
        lines.append(f'<text x="{dx + bar_w/2:.1f}" y="{dy-3:.1f}" fill="#7dd3fc" font-size="7.5" '
                     f'text-anchor="middle">{dagger_fail[i]:.2f}</text>')
        # X label
        lx = gx + bar_w
        lines.append(f'<text x="{lx:.1f}" y="{pad_t+chart_h+14}" fill="#94a3b8" font-size="7.5" '
                     f'text-anchor="middle" transform="rotate(-25,{lx:.1f},{pad_t+chart_h+14})">'
                     f'{cond}</text>')

    # Legend
    lines += [
        f'<rect x="{pad_l}" y="{h-14}" width="10" height="8" fill="#C74634" rx="1"/>',
        f'<text x="{pad_l+13}" y="{h-7}" fill="#94a3b8" font-size="8">BC</text>',
        f'<rect x="{pad_l+40}" y="{h-14}" width="10" height="8" fill="#38bdf8" rx="1"/>',
        f'<text x="{pad_l+53}" y="{h-7}" fill="#94a3b8" font-size="8">DAgger (shorter = more resilient)</text>',
    ]
    lines.append('</svg>')
    return "\n".join(lines)


def svg_radar() -> str:
    """Resilience radar: 6 stress categories, 3 polygons (GR00T_v2, dagger_r9, BC)."""
    import math
    categories = ["sensor_noise", "lighting", "latency", "obj_shift", "occlusion", "temperature"]
    scores = {
        "BC":        [0.65, 0.57, 0.61, 0.67, 0.55, 0.64],
        "dagger_r9": [0.82, 0.75, 0.80, 0.84, 0.77, 0.81],
        "GR00T_v2":  [0.91, 0.85, 0.89, 0.92, 0.87, 0.90],
    }
    colors = {"BC": "#C74634", "dagger_r9": "#38bdf8", "GR00T_v2": "#22c55e"}
    cx, cy, r_max = 280, 200, 130
    n = len(categories)
    w, h = 560, 420

    def point(score, i):
        angle = math.pi / 2 - 2 * math.pi * i / n
        rr = score * r_max
        return cx + rr * math.cos(angle), cy - rr * math.sin(angle)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{w//2}" y="22" fill="#38bdf8" font-size="13" font-weight="bold" '
        f'text-anchor="middle">Resilience Radar — Stress Categories</text>',
    ]

    # Grid rings
    for level in [0.25, 0.5, 0.75, 1.0]:
        pts = []
        for i in range(n):
            x, y = point(level, i)
            pts.append(f"{x:.1f},{y:.1f}")
        lines.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{cx+3}" y="{cy - level*r_max - 3:.1f}" fill="#475569" font-size="7">{level:.2f}</text>')

    # Spoke lines
    for i in range(n):
        x, y = point(1.0, i)
        lines.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>')

    # Category labels
    for i, cat in enumerate(categories):
        x, y = point(1.15, i)
        lines.append(f'<text x="{x:.1f}" y="{y:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{cat}</text>')

    # Polygons (back to front: BC, dagger_r9, GR00T_v2)
    for name in ["BC", "dagger_r9", "GR00T_v2"]:
        pts = []
        for i, sc in enumerate(scores[name]):
            x, y = point(sc, i)
            pts.append(f"{x:.1f},{y:.1f}")
        c = colors[name]
        lines.append(f'<polygon points="{" ".join(pts)}" fill="{c}" fill-opacity="0.15" '
                     f'stroke="{c}" stroke-width="2"/>')
        # Score dots + labels
        for i, sc in enumerate(scores[name]):
            x, y = point(sc, i)
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{c}"/>')

    # Legend
    legend_x, legend_y = w - 140, h - 70
    for idx, (name, c) in enumerate(colors.items()):
        ly = legend_y + idx * 18
        lines.append(f'<line x1="{legend_x}" y1="{ly+4}" x2="{legend_x+18}" y2="{ly+4}" stroke="{c}" stroke-width="2"/>')
        lines.append(f'<circle cx="{legend_x+9}" cy="{ly+4}" r="3" fill="{c}"/>')
        lines.append(f'<text x="{legend_x+24}" y="{ly+8}" fill="#cbd5e1" font-size="9">{name}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Policy Stress Tester v2 — Port 8682</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px}}
    h1{{color:#C74634;font-size:1.5rem;margin-bottom:4px}}
    .sub{{color:#38bdf8;font-size:.85rem;margin-bottom:24px}}
    .grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px}}
    .card{{background:#0f1f35;border:1px solid #1e3a5f;border-radius:10px;padding:20px}}
    .card h2{{color:#38bdf8;font-size:.95rem;margin-bottom:14px}}
    .card-wide{{background:#0f1f35;border:1px solid #1e3a5f;border-radius:10px;padding:20px;margin-bottom:24px}}
    .card-wide h2{{color:#38bdf8;font-size:.95rem;margin-bottom:14px}}
    .metrics{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:24px}}
    .metric{{background:#0f1f35;border:1px solid #1e3a5f;border-radius:8px;padding:14px 20px;min-width:160px}}
    .metric .val{{font-size:1.8rem;font-weight:bold;color:#C74634}}
    .metric .lbl{{font-size:.75rem;color:#64748b;margin-top:2px}}
    .metric .sub2{{font-size:.7rem;color:#38bdf8}}
    svg{{max-width:100%;height:auto;display:block}}
    .badge{{display:inline-block;background:#C74634;color:#fff;border-radius:4px;
             padding:2px 8px;font-size:.7rem;margin-left:8px;vertical-align:middle}}
    footer{{color:#334155;font-size:.7rem;margin-top:30px;text-align:center}}
  </style>
</head>
<body>
  <h1>Policy Stress Tester v2 <span class="badge">PORT 8682</span></h1>
  <div class="sub">OCI Robot Cloud — BC vs DAgger resilience under environmental perturbations</div>

  <div class="metrics">
    <div class="metric">
      <div class="val">2.4×</div>
      <div class="lbl">DAgger resilience gain over BC</div>
      <div class="sub2">average across all conditions</div>
    </div>
    <div class="metric">
      <div class="val" style="color:#38bdf8">3 steps</div>
      <div class="lbl">DAgger recovery time</div>
      <div class="sub2">BC requires 8+ steps</div>
    </div>
    <div class="metric">
      <div class="val" style="color:#facc15">0.51</div>
      <div class="lbl">Worst SR: lighting sev-3</div>
      <div class="sub2">BC: 0.78 → 0.51 at severity-3</div>
    </div>
    <div class="metric">
      <div class="val" style="color:#22c55e">6</div>
      <div class="lbl">Stress conditions tested</div>
      <div class="sub2">× 3 severity levels each</div>
    </div>
  </div>

  <div class="card-wide">
    <h2>Stress Test Matrix Heatmap (6 conditions × 3 severity levels)</h2>
    {svg_heatmap()}
  </div>

  <div class="grid">
    <div class="card">
      <h2>Failure Rate by Condition (BC vs DAgger)</h2>
      {svg_failure_bars()}
    </div>
    <div class="card">
      <h2>Resilience Radar (GR00T_v2 / dagger_r9 / BC)</h2>
      {svg_radar()}
    </div>
  </div>

  <footer>OCI Robot Cloud · policy_stress_tester_v2.py · port 8682 · stdlib only</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app / fallback HTTP server
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Policy Stress Tester v2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "policy_stress_tester_v2", "port": 8682}

    @app.get("/metrics")
    async def metrics():
        return {
            "dagger_resilience_multiplier": 2.4,
            "dagger_recovery_steps": 3,
            "bc_recovery_steps_min": 8,
            "worst_condition": "lighting_change",
            "worst_bc_sr_severity3": 0.51,
            "worst_bc_sr_severity1": 0.78,
            "conditions_tested": 6,
            "severity_levels": 3,
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8682)

else:
    # stdlib fallback
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"policy_stress_tester_v2","port":8682}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        print("FastAPI not found — using stdlib HTTPServer on port 8682")
        HTTPServer(("0.0.0.0", 8682), Handler).serve_forever()

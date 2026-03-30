"""Experiment Notebook Viewer — OCI Robot Cloud  (port 8203)

Lab-notebook style viewer for robot learning experiments.
Tracks training runs, success rates, and deployment status.
"""

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e}  —  pip install fastapi uvicorn") from e

import math

app = FastAPI(
    title="Experiment Notebook",
    description="Robot learning experiment tracker — OCI Robot Cloud",
    version="1.0.0",
)

# ── Experiment data ────────────────────────────────────────────────────────────
STATUS_PRODUCTION   = "PRODUCTION"
STATUS_STAGING      = "STAGING"
STATUS_ARCHIVED     = "ARCHIVED"
STATUS_IN_PROGRESS  = "IN_PROGRESS"

EXPERIMENTS = [
    {
        "id": "exp_001",
        "date": "2026-01-10",
        "title": "Baseline BC Training",
        "tags": ["baseline", "bc"],
        "summary": "First behavioral cloning run. 500 demos, 3000 steps. SR=5% (expected — no online learning).",
        "result_model": "bc_baseline",
        "result_version": "v0.1.0",
        "result_sr": 0.05,
        "status": STATUS_ARCHIVED,
    },
    {
        "id": "exp_002",
        "date": "2026-01-28",
        "title": "DAgger Run 5 — First Online Loop",
        "tags": ["dagger", "online"],
        "summary": "Implemented DAgger with chunk_step reset fix. 500 expert demos + online collection. SR=42%.",
        "result_model": "dagger_run5",
        "result_version": "v0.2.0",
        "result_sr": 0.42,
        "status": STATUS_ARCHIVED,
    },
    {
        "id": "exp_003",
        "date": "2026-02-14",
        "title": "DAgger Run 9 v2.2 — Production",
        "tags": ["dagger", "production"],
        "summary": "1000 demos, 5000 steps, chunk_size=16 fix. SR=71%. First production deployment.",
        "result_model": "dagger_run9_v2",
        "result_version": "v0.3.0",
        "result_sr": 0.71,
        "status": STATUS_PRODUCTION,
    },
    {
        "id": "exp_004",
        "date": "2026-03-01",
        "title": "GR00T Fine-tune v2 — STAGING",
        "tags": ["groot", "finetune", "staging"],
        "summary": "GR00T N1.6 backbone, LoRA rank=16, 1600 curated demos. SR=78% (+7pp over DAgger). STAGING now.",
        "result_model": "groot_finetune_v2",
        "result_version": "v1.0.0",
        "result_sr": 0.78,
        "status": STATUS_STAGING,
    },
    {
        "id": "exp_005",
        "date": "2026-03-30",
        "title": "GR00T Fine-tune v3 — In Training",
        "tags": ["groot", "finetune", "inprogress"],
        "summary": "Extended training 8000 steps. adapter_r16_v2 config. Target SR=81%+. 40% complete.",
        "result_model": "groot_finetune_v3",
        "result_version": "v1.1.0-rc1",
        "result_sr": None,
        "status": STATUS_IN_PROGRESS,
    },
]

STATUS_COLOR = {
    STATUS_PRODUCTION:  "#C74634",
    STATUS_STAGING:     "#f59e0b",
    STATUS_ARCHIVED:    "#64748b",
    STATUS_IN_PROGRESS: "#38bdf8",
}

# ── Chart helpers ──────────────────────────────────────────────────────────────

def _timeline_svg() -> str:
    """Experiment timeline — 680×160 px."""
    W, H    = 680, 160
    pad_l   = 50
    pad_r   = 30
    pad_t   = 40
    pad_b   = 32
    chart_w = W - pad_l - pad_r
    # x spans 2026-01-01 to 2026-04-30
    t_start = 0       # days from Jan 1 2026
    t_end   = 119     # Apr 30 = day 119

    def day_of(date_str: str) -> int:
        months = [0, 31, 59, 90, 120, 151]
        y, m, d = (int(x) for x in date_str.split("-"))
        return months[m - 1] + d - 1

    def tx(date_str: str) -> float:
        return pad_l + chart_w * day_of(date_str) / t_end

    cy = (pad_t + H - pad_b) / 2

    # Baseline axis
    axis = f'<line x1="{pad_l}" y1="{cy:.1f}" x2="{W - pad_r}" y2="{cy:.1f}" stroke="#334155" stroke-width="2"/>'

    # Month labels
    months_lbl = ""
    month_days = [("Jan", 0), ("Feb", 31), ("Mar", 59), ("Apr", 90)]
    for lbl, d in month_days:
        mx = pad_l + chart_w * d / t_end
        months_lbl += (
            f'<line x1="{mx:.1f}" y1="{cy - 6}" x2="{mx:.1f}" y2="{cy + 6}" stroke="#475569" stroke-width="1"/>'
            f'<text x="{mx:.1f}" y="{H - pad_b + 14:.1f}" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace">{lbl}</text>'
        )

    circles = ""
    for exp in EXPERIMENTS:
        ex     = tx(exp["date"])
        sr     = exp["result_sr"] or 0.40   # size for in-progress
        radius = 8 + sr * 22                # 8–30 px
        color  = STATUS_COLOR.get(exp["status"], "#64748b")
        short  = exp["id"].replace("exp_", "#")
        # Alternate labels above/below to avoid overlap
        idx    = EXPERIMENTS.index(exp)
        lbl_dy = -radius - 6 if idx % 2 == 0 else radius + 14
        anchor = "middle"

        circles += (
            f'<circle cx="{ex:.1f}" cy="{cy:.1f}" r="{radius:.1f}" fill="{color}" opacity="0.85"/>'
            f'<text x="{ex:.1f}" y="{cy + lbl_dy:.1f}" text-anchor="{anchor}" fill="{color}" font-size="10" font-family="monospace">{short}</text>'
        )
        # SR label inside circle if big enough
        if exp["result_sr"]:
            circles += f'<text x="{ex:.1f}" y="{cy + 4:.1f}" text-anchor="middle" fill="#fff" font-size="9" font-family="monospace" font-weight="bold">{int(exp["result_sr"]*100)}%</text>'
        else:
            circles += f'<text x="{ex:.1f}" y="{cy + 4:.1f}" text-anchor="middle" fill="#fff" font-size="8" font-family="monospace">TBD</text>'

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">'
        f'<text x="{W//2}" y="16" text-anchor="middle" fill="#e2e8f0" font-size="12" font-family="monospace" font-weight="bold">'
        f'Experiment Timeline — Jan–Apr 2026 (circle size = success rate)</text>'
        + axis + months_lbl + circles +
        f'</svg>'
    )
    return svg


def _funnel_svg() -> str:
    """Status funnel — 420×240 px."""
    W, H = 420, 240
    stages = [
        ("Started",     5, "#38bdf8"),
        ("Archived",    2, "#64748b"),
        ("In Progress", 1, "#38bdf8"),
        ("Staging",     1, "#f59e0b"),
        ("Production",  1, "#C74634"),
    ]
    max_count = 5
    bar_h     = 28
    gap       = 10
    pad_l     = 110
    pad_r     = 60
    chart_w   = W - pad_l - pad_r
    start_y   = 20

    bars = ""
    for i, (label, count, color) in enumerate(stages):
        bw = chart_w * count / max_count
        by = start_y + i * (bar_h + gap)
        cx = pad_l + bw / 2
        bars += (
            f'<rect x="{pad_l}" y="{by}" width="{bw:.1f}" height="{bar_h}" fill="{color}" opacity="0.8" rx="4"/>'
            f'<text x="{pad_l - 8}" y="{by + bar_h/2 + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="11" font-family="monospace">{label}</text>'
            f'<text x="{pad_l + bw + 8:.1f}" y="{by + bar_h/2 + 4:.1f}" fill="{color}" font-size="13" font-family="monospace" font-weight="bold">{count}</text>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">'
        f'<text x="{W//2}" y="16" text-anchor="middle" fill="#e2e8f0" font-size="12" font-family="monospace" font-weight="bold">'
        f'Experiment Lifecycle Funnel</text>'
        + bars +
        f'</svg>'
    )
    return svg


def _tag_cloud_svg() -> str:
    """Tag cloud — 680×80 px."""
    W, H = 680, 80
    tag_counts: dict = {}
    for exp in EXPERIMENTS:
        for t in exp["tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1

    sorted_tags = sorted(tag_counts.items(), key=lambda x: -x[1])
    colors = ["#C74634", "#38bdf8", "#f59e0b", "#34d399", "#818cf8", "#fb923c"]
    cx, cy = W // 2, H // 2 + 4
    tags_svg = ""
    # Lay out horizontally, sized by count
    x = 30
    for i, (tag, cnt) in enumerate(sorted_tags):
        size = 12 + cnt * 5
        color = colors[i % len(colors)]
        tags_svg += f'<text x="{x}" y="{cy + (size - 20)//2:.0f}" fill="{color}" font-size="{size}" font-family="monospace" opacity="0.9">{tag}</text>'
        x += len(tag) * size * 0.62 + 14
        if x > W - 80:
            break

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">' +
        tags_svg +
        f'<text x="{W - 8}" y="{H - 8}" text-anchor="end" fill="#334155" font-size="9" font-family="monospace">tag frequency</text>'
        f'</svg>'
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/experiments")
def list_experiments(tag: str = Query(default=None, description="Filter by tag")):
    """List all experiments, optionally filtered by tag."""
    exps = EXPERIMENTS
    if tag:
        exps = [e for e in exps if tag in e["tags"]]
    return JSONResponse({"count": len(exps), "experiments": exps})


@app.get("/experiments/{exp_id}")
def get_experiment(exp_id: str):
    """Get a single experiment by ID."""
    for exp in EXPERIMENTS:
        if exp["id"] == exp_id:
            return JSONResponse(exp)
    return JSONResponse({"error": f"Experiment '{exp_id}' not found"}, status_code=404)


@app.get("/active")
def get_active():
    """Return all non-archived experiments."""
    active = [e for e in EXPERIMENTS if e["status"] != STATUS_ARCHIVED]
    return JSONResponse({"count": len(active), "experiments": active})


@app.get("/", response_class=HTMLResponse)
def dashboard():
    timeline_svg  = _timeline_svg()
    funnel_svg    = _funnel_svg()
    tag_cloud_svg = _tag_cloud_svg()

    STATUS_BADGE = {
        STATUS_PRODUCTION:  ("#C74634", "PRODUCTION"),
        STATUS_STAGING:     ("#f59e0b", "STAGING"),
        STATUS_ARCHIVED:    ("#64748b", "ARCHIVED"),
        STATUS_IN_PROGRESS: ("#38bdf8", "IN PROGRESS"),
    }

    exp_cards = ""
    for exp in reversed(EXPERIMENTS):   # newest first
        color, badge = STATUS_BADGE.get(exp["status"], ("#64748b", exp["status"]))
        sr_text = f"{int(exp['result_sr']*100)}%" if exp["result_sr"] is not None else "TBD"
        tags_html = " ".join(
            f'<span style="background:#334155;color:#94a3b8;padding:2px 7px;border-radius:3px;font-size:10px;font-family:monospace">{t}</span>'
            for t in exp["tags"]
        )
        exp_cards += f"""
        <div style="background:#1e293b;border:1px solid #334155;border-left:4px solid {color};border-radius:8px;padding:16px 20px;margin-bottom:14px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
              <span style="color:#475569;font-size:11px;font-family:monospace">{exp['id']} &nbsp;·&nbsp; {exp['date']}</span>
              <h3 style="color:#e2e8f0;font-size:15px;margin:4px 0 6px">{exp['title']}</h3>
              <div style="margin-bottom:8px">{tags_html}</div>
              <p style="color:#94a3b8;font-size:13px;line-height:1.5">{exp['summary']}</p>
            </div>
            <div style="text-align:right;min-width:110px;padding-left:16px">
              <div style="background:{color}22;color:{color};border:1px solid {color};padding:3px 10px;border-radius:4px;font-size:11px;font-family:monospace;white-space:nowrap">{badge}</div>
              <div style="color:{color};font-size:26px;font-weight:800;margin-top:8px">{sr_text}</div>
              <div style="color:#475569;font-size:10px">success rate</div>
              <div style="color:#64748b;font-size:10px;margin-top:4px;font-family:monospace">{exp['result_model']} {exp['result_version']}</div>
            </div>
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Experiment Notebook — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: system-ui, sans-serif; }}
    .header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 16px 32px; display: flex; align-items: center; gap: 16px; }}
    .logo {{ color: #C74634; font-size: 22px; font-weight: 800; letter-spacing: -0.5px; }}
    .subtitle {{ color: #64748b; font-size: 13px; }}
    .container {{ max-width: 900px; margin: 0 auto; padding: 28px 24px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 24px; border: 1px solid #334155; }}
    .card-title {{ color: #38bdf8; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 14px; }}
    .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }}
    .stat-val {{ font-size: 32px; font-weight: 800; color: #C74634; }}
    .stat-lbl {{ color: #64748b; font-size: 12px; margin-top: 2px; }}
    .port {{ color: #64748b; font-size: 12px; font-family: monospace; }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <div class="logo">OCI Robot Cloud</div>
      <div class="subtitle">Experiment Notebook &nbsp;&#183;&nbsp; Robot Learning Lab &nbsp;&#183;&nbsp; <span class="port">:8203</span></div>
    </div>
    <div style="margin-left:auto;display:flex;gap:16px">
      <div style="text-align:center"><div class="stat-val">78%</div><div class="stat-lbl">best SR (staging)</div></div>
      <div style="text-align:center"><div class="stat-val" style="color:#38bdf8">5</div><div class="stat-lbl">experiments</div></div>
    </div>
  </div>
  <div class="container">

    <div class="card">
      <div class="card-title">Timeline</div>
      {timeline_svg}
    </div>

    <div style="display:grid;grid-template-columns:1fr auto;gap:20px;margin-bottom:24px;align-items:start">
      <div class="card" style="margin-bottom:0">
        <div class="card-title">Tag Cloud</div>
        {tag_cloud_svg}
      </div>
      <div class="card" style="margin-bottom:0">
        <div class="card-title">Lifecycle Funnel</div>
        {funnel_svg}
      </div>
    </div>

    <div>
      <div style="color:#38bdf8;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:14px">All Experiments (newest first)</div>
      {exp_cards}
    </div>

    <div style="color:#475569;font-size:11px;text-align:center;margin-top:8px">
      API: <code>/experiments</code> &nbsp;<code>/experiments/{{id}}</code> &nbsp;<code>/experiments?tag=dagger</code> &nbsp;<code>/active</code>
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(html)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8203)

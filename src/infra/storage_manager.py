"""OCI Object Storage Manager for robot training data — port 8138."""

import math
from datetime import datetime, timedelta

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None
    HTMLResponse = None
    JSONResponse = None
    uvicorn = None

app = FastAPI(title="OCI Storage Manager", version="1.0.0") if FastAPI else None

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

BUCKETS = [
    {
        "name": "robotics-training-data",
        "size_gb": 247.3,
        "objects": 14821,
        "last_modified": "2026-03-29",
        "region": "us-ashburn-1",
        "tier": "standard",
        "cost_per_month": 12.37,
    },
    {
        "name": "robotics-checkpoints",
        "size_gb": 84.6,
        "objects": 342,
        "last_modified": "2026-03-30",
        "region": "us-ashburn-1",
        "tier": "standard",
        "cost_per_month": 4.23,
    },
    {
        "name": "robotics-eval-results",
        "size_gb": 12.1,
        "objects": 2847,
        "last_modified": "2026-03-30",
        "region": "us-ashburn-1",
        "tier": "standard",
        "cost_per_month": 0.61,
    },
]

UPLOADS = [
    {"timestamp": "2026-03-30 14:22", "bucket": "robotics-training-data",  "file": "genesis_sdg_v3_batch_041.hdf5",      "size_mb": 847, "duration_s": 12.4, "throughput_mbps": 68.3},
    {"timestamp": "2026-03-30 11:05", "bucket": "robotics-checkpoints",     "file": "gr00t_finetune_step_5000.pt",         "size_mb": 312, "duration_s":  3.8, "throughput_mbps": 82.1},
    {"timestamp": "2026-03-29 22:47", "bucket": "robotics-training-data",  "file": "genesis_sdg_v3_batch_040.hdf5",      "size_mb": 823, "duration_s": 13.1, "throughput_mbps": 62.8},
    {"timestamp": "2026-03-29 18:33", "bucket": "robotics-eval-results",   "file": "eval_dagger_run6_results.json",       "size_mb":  4.2, "duration_s":  0.2, "throughput_mbps": 21.0},
    {"timestamp": "2026-03-29 15:10", "bucket": "robotics-checkpoints",    "file": "gr00t_finetune_step_4500.pt",         "size_mb": 312, "duration_s":  3.6, "throughput_mbps": 86.7},
    {"timestamp": "2026-03-28 09:54", "bucket": "robotics-training-data",  "file": "genesis_sdg_v3_batch_039.hdf5",      "size_mb": 791, "duration_s": 13.8, "throughput_mbps": 57.3},
    {"timestamp": "2026-03-27 21:16", "bucket": "robotics-training-data",  "file": "real_robot_demos_batch_012.hdf5",    "size_mb": 1240, "duration_s": 14.6, "throughput_mbps": 84.9},
    {"timestamp": "2026-03-26 16:42", "bucket": "robotics-checkpoints",    "file": "gr00t_finetune_step_4000.pt",         "size_mb": 312, "duration_s":  4.1, "throughput_mbps": 76.1},
]

LIFECYCLE_POLICIES = [
    {
        "id": "lp-001",
        "name": "Archive old checkpoints",
        "bucket": "robotics-checkpoints",
        "condition": "age > 90 days",
        "action": "Transition to Infrequent Access tier",
        "estimated_savings": "$1.20/mo",
    },
    {
        "id": "lp-002",
        "name": "Delete stale eval results",
        "bucket": "robotics-eval-results",
        "condition": "age > 180 days",
        "action": "Delete object",
        "estimated_savings": "$0.15/mo",
    },
    {
        "id": "lp-003",
        "name": "Compress SDG raw data",
        "bucket": "robotics-training-data",
        "condition": "prefix=genesis_sdg_raw/ AND age > 30 days",
        "action": "Compress and re-upload (Lambda trigger)",
        "estimated_savings": "$2.80/mo",
    },
]

# ---------------------------------------------------------------------------
# SVG chart generators
# ---------------------------------------------------------------------------

def _storage_growth_svg() -> str:
    """Stacked area chart: storage growth over 30 days, 680x200."""
    W, H = 680, 200
    PAD_L, PAD_R, PAD_T, PAD_B = 52, 20, 18, 34
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    n = 30
    # Simulate exponential-ish growth: total goes from ~180 to ~344 GB
    # Buckets: training-data, checkpoints, eval-results
    days = list(range(n))

    def grow(start, end, n, exp=1.6):
        return [start + (end - start) * ((i / (n - 1)) ** exp) for i in range(n)]

    td = grow(132, 247.3, n)
    ck = grow(44, 84.6, n)
    er = grow(4, 12.1, n)

    totals = [td[i] + ck[i] + er[i] for i in range(n)]
    max_val = max(totals) * 1.05

    def fy(v):
        return PAD_T + chart_h - (v / max_val) * chart_h

    def fx(i):
        return PAD_L + (i / (n - 1)) * chart_w

    # Build stacked polygons
    def poly_points(bot_series, top_series):
        fwd = " ".join(f"{fx(i):.1f},{fy(top_series[i]):.1f}" for i in range(n))
        bwd = " ".join(f"{fx(i):.1f},{fy(bot_series[i]):.1f}" for i in range(n - 1, -1, -1))
        return fwd + " " + bwd

    zeros = [0] * n
    er_top = er
    ck_top = [er[i] + ck[i] for i in range(n)]
    td_top = totals

    pts_er = poly_points(zeros, er_top)
    pts_ck = poly_points(er_top, ck_top)
    pts_td = poly_points(ck_top, td_top)

    # Y-axis labels
    y_labels = ""
    for v in [0, 100, 200, 300, 344]:
        y = fy(v)
        y_labels += f'<text x="{PAD_L-6}" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v}</text>'
        y_labels += f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L+chart_w}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'

    # X-axis labels (every 5 days)
    x_labels = ""
    base_date = datetime(2026, 3, 1)
    for i in range(0, n, 5):
        x = fx(i)
        label = (base_date + timedelta(days=i)).strftime("%m/%d")
        x_labels += f'<text x="{x:.1f}" y="{H-8}" fill="#94a3b8" font-size="10" text-anchor="middle">{label}</text>'

    svg = f"""<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:8px">
  <polygon points="{pts_td}" fill="#C74634" opacity="0.75"/>
  <polygon points="{pts_ck}" fill="#f59e0b" opacity="0.80"/>
  <polygon points="{pts_er}" fill="#38bdf8" opacity="0.85"/>
  {y_labels}
  {x_labels}
  <text x="{PAD_L+chart_w//2}" y="12" fill="#e2e8f0" font-size="11" text-anchor="middle" font-family="monospace">Storage Growth — Last 30 Days (GB)</text>
  <!-- Legend -->
  <rect x="460" y="22" width="10" height="10" fill="#C74634"/><text x="474" y="31" fill="#94a3b8" font-size="10">training-data</text>
  <rect x="460" y="36" width="10" height="10" fill="#f59e0b"/><text x="474" y="45" fill="#94a3b8" font-size="10">checkpoints</text>
  <rect x="460" y="50" width="10" height="10" fill="#38bdf8"/><text x="474" y="59" fill="#94a3b8" font-size="10">eval-results</text>
</svg>"""
    return svg


def _upload_throughput_svg() -> str:
    """Bar chart of upload throughput per recent upload, 680x180."""
    W, H = 680, 180
    PAD_L, PAD_R, PAD_T, PAD_B = 52, 20, 18, 50
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    n = len(UPLOADS)
    max_tp = 100.0
    bar_w = chart_w / n * 0.6
    gap = chart_w / n

    def color(tp):
        if tp >= 80:
            return "#22c55e"
        elif tp >= 50:
            return "#f59e0b"
        return "#ef4444"

    bars = ""
    x_labels = ""
    for i, u in enumerate(UPLOADS):
        tp = u["throughput_mbps"]
        bh = (tp / max_tp) * chart_h
        bx = PAD_L + i * gap + (gap - bar_w) / 2
        by = PAD_T + chart_h - bh
        bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color(tp)}" rx="2"/>'
        bars += f'<text x="{bx+bar_w/2:.1f}" y="{by-4:.1f}" fill="#e2e8f0" font-size="9" text-anchor="middle">{tp}</text>'
        short = u["file"].split(".")[0][-12:]
        x_labels += f'<text x="{bx+bar_w/2:.1f}" y="{H-34}" fill="#94a3b8" font-size="8" text-anchor="end" transform="rotate(-35,{bx+bar_w/2:.1f},{H-34})">{short}</text>'

    # Y gridlines
    grid = ""
    for v in [0, 25, 50, 75, 100]:
        y = PAD_T + chart_h - (v / max_tp) * chart_h
        grid += f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L+chart_w}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{PAD_L-6}" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v}</text>'

    svg = f"""<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:8px">
  {grid}
  {bars}
  {x_labels}
  <text x="{PAD_L+chart_w//2}" y="12" fill="#e2e8f0" font-size="11" text-anchor="middle" font-family="monospace">Upload Throughput (MBps) — Recent Uploads</text>
  <!-- legend -->
  <rect x="460" y="4" width="8" height="8" fill="#22c55e"/><text x="471" y="12" fill="#94a3b8" font-size="9">&gt;=80</text>
  <rect x="497" y="4" width="8" height="8" fill="#f59e0b"/><text x="508" y="12" fill="#94a3b8" font-size="9">50-79</text>
  <rect x="538" y="4" width="8" height="8" fill="#ef4444"/><text x="549" y="12" fill="#94a3b8" font-size="9">&lt;50</text>
</svg>"""
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    growth_svg = _storage_growth_svg()
    tp_svg = _upload_throughput_svg()

    bucket_rows = ""
    for b in BUCKETS:
        bucket_rows += f"""
        <tr>
          <td style="color:#38bdf8">{b['name']}</td>
          <td>{b['size_gb']:.1f} GB</td>
          <td>{b['objects']:,}</td>
          <td>{b['last_modified']}</td>
          <td>{b['region']}</td>
          <td style="color:#f59e0b">${b['cost_per_month']:.2f}</td>
        </tr>"""

    upload_rows = ""
    for u in UPLOADS:
        tp = u["throughput_mbps"]
        color = "#22c55e" if tp >= 80 else ("#f59e0b" if tp >= 50 else "#ef4444")
        upload_rows += f"""
        <tr>
          <td style="color:#94a3b8">{u['timestamp']}</td>
          <td style="color:#38bdf8">{u['bucket'].replace('robotics-','')}</td>
          <td style="font-size:11px">{u['file']}</td>
          <td>{u['size_mb']} MB</td>
          <td>{u['duration_s']}s</td>
          <td style="color:{color}">{tp} MBps</td>
        </tr>"""

    policy_cards = ""
    for p in LIFECYCLE_POLICIES:
        policy_cards += f"""
        <div style="background:#1e293b;border-radius:8px;padding:14px;border-left:3px solid #C74634">
          <div style="color:#38bdf8;font-weight:bold;margin-bottom:6px">{p['name']}</div>
          <div style="color:#94a3b8;font-size:12px">Bucket: {p['bucket']}</div>
          <div style="color:#cbd5e1;font-size:12px;margin-top:4px">Condition: {p['condition']}</div>
          <div style="color:#cbd5e1;font-size:12px">Action: {p['action']}</div>
          <div style="color:#22c55e;font-size:12px;margin-top:4px">Savings: {p['estimated_savings']}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>OCI Storage Manager — Port 8138</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .sub {{ color: #94a3b8; font-size: 13px; margin-bottom: 24px; }}
    .cards {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 14px; margin-bottom: 24px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 16px; border-top: 3px solid #C74634; }}
    .card .label {{ color: #94a3b8; font-size: 12px; margin-bottom: 6px; }}
    .card .value {{ color: #38bdf8; font-size: 26px; font-weight: bold; }}
    .card .unit {{ color: #64748b; font-size: 12px; }}
    .section {{ margin-bottom: 28px; }}
    h2 {{ color: #cbd5e1; font-size: 15px; margin-bottom: 12px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ color: #94a3b8; text-align: left; padding: 8px; border-bottom: 1px solid #1e293b; font-weight: 500; }}
    td {{ padding: 8px; border-bottom: 1px solid #0f172a; }}
    tr:hover td {{ background: #1e293b; }}
    .policy-grid {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 14px; }}
    .badge {{ display:inline-block;padding:2px 8px;border-radius:9999px;font-size:11px; }}
  </style>
</head>
<body>
  <h1>OCI Object Storage Manager</h1>
  <div class="sub">OCI Robot Cloud — us-ashburn-1 | Port 8138 | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>

  <div class="cards">
    <div class="card">
      <div class="label">Total Storage</div>
      <div class="value">344.0<span class="unit"> GB</span></div>
    </div>
    <div class="card">
      <div class="label">Monthly Cost</div>
      <div class="value">$17.21<span class="unit">/mo</span></div>
    </div>
    <div class="card">
      <div class="label">Total Objects</div>
      <div class="value">18,010</div>
    </div>
    <div class="card">
      <div class="label">Avg Upload Speed</div>
      <div class="value">71.4<span class="unit"> MBps</span></div>
    </div>
  </div>

  <div class="section">
    <h2>Storage Growth (Last 30 Days)</h2>
    {growth_svg}
  </div>

  <div class="section">
    <h2>Upload Throughput</h2>
    {tp_svg}
  </div>

  <div class="section">
    <h2>Buckets</h2>
    <table>
      <thead><tr><th>Name</th><th>Size</th><th>Objects</th><th>Last Modified</th><th>Region</th><th>Cost/mo</th></tr></thead>
      <tbody>{bucket_rows}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>Recent Uploads (Last 7 Days)</h2>
    <table>
      <thead><tr><th>Timestamp</th><th>Bucket</th><th>File</th><th>Size</th><th>Duration</th><th>Throughput</th></tr></thead>
      <tbody>{upload_rows}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>Lifecycle Policies</h2>
    <div class="policy-grid">{policy_cards}</div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

if app:
    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _dashboard_html()

    @app.get("/buckets")
    async def get_buckets():
        total_gb = sum(b["size_gb"] for b in BUCKETS)
        total_cost = sum(b["cost_per_month"] for b in BUCKETS)
        return {"buckets": BUCKETS, "total_size_gb": round(total_gb, 1), "total_cost_per_month": round(total_cost, 2)}

    @app.get("/uploads")
    async def get_uploads():
        return {"uploads": UPLOADS, "count": len(UPLOADS)}

    @app.get("/summary")
    async def get_summary():
        total_gb = sum(b["size_gb"] for b in BUCKETS)
        total_cost = sum(b["cost_per_month"] for b in BUCKETS)
        total_objects = sum(b["objects"] for b in BUCKETS)
        avg_tp = sum(u["throughput_mbps"] for u in UPLOADS) / len(UPLOADS)
        return {
            "total_storage_gb": round(total_gb, 1),
            "total_cost_per_month": round(total_cost, 2),
            "total_objects": total_objects,
            "avg_upload_throughput_mbps": round(avg_tp, 1),
            "buckets": len(BUCKETS),
            "lifecycle_policies": len(LIFECYCLE_POLICIES),
            "region": "us-ashburn-1",
            "service": "oci-storage-manager",
            "port": 8138,
        }


if __name__ == "__main__":
    if uvicorn:
        uvicorn.run(app, host="0.0.0.0", port=8138)
    else:
        print("uvicorn not installed — run: pip install fastapi uvicorn")

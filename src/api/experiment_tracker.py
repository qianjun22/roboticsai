try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    raise ImportError("fastapi and uvicorn are required: pip install fastapi uvicorn")

import math
from datetime import datetime

app = FastAPI(title="OCI Robot Cloud — Experiment Tracker", version="1.0.0")

EXPERIMENTS = [
    {"id": "exp_001", "lr": 1e-4, "batch": 32, "epochs": 50, "success_rate": 62, "loss": 0.142, "status": "COMPLETED", "gpu_hrs": 2.1, "is_best": False},
    {"id": "exp_002", "lr": 5e-5, "batch": 64, "epochs": 100, "success_rate": 71, "loss": 0.103, "status": "COMPLETED", "gpu_hrs": 4.3, "is_best": False},
    {"id": "exp_003", "lr": 1e-4, "batch": 64, "epochs": 100, "success_rate": 78, "loss": 0.089, "status": "COMPLETED", "gpu_hrs": 4.8, "is_best": True},
    {"id": "exp_004", "lr": 2e-4, "batch": 32, "epochs": 50, "success_rate": 58, "loss": 0.167, "status": "COMPLETED", "gpu_hrs": 2.0, "is_best": False},
    {"id": "exp_005", "lr": 5e-5, "batch": 128, "epochs": 150, "success_rate": 75, "loss": 0.098, "status": "RUNNING", "progress_pct": 67, "gpu_hrs": None, "is_best": False},
    {"id": "exp_006", "lr": 1e-5, "batch": 64, "epochs": 200, "success_rate": None, "loss": None, "status": "QUEUED", "gpu_hrs": None, "is_best": False},
]


def _lr_display(lr: float) -> str:
    if lr == 1e-4: return "1e-4"
    if lr == 5e-5: return "5e-5"
    if lr == 2e-4: return "2e-4"
    if lr == 1e-5: return "1e-5"
    return f"{lr:.0e}"


def _build_scatter_svg() -> str:
    W, H = 700, 200
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 20, 20, 40
    lr_log_min, lr_log_max = -5.2, -3.5
    sr_min, sr_max = 50, 85
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B

    def x_pos(lr):
        return PAD_L + (math.log10(lr) - lr_log_min) / (lr_log_max - lr_log_min) * inner_w

    def y_pos(sr):
        return PAD_T + inner_h - (sr - sr_min) / (sr_max - sr_min) * inner_h

    batch_color = {32: "#f59e0b", 64: "#C74634", 128: "#a855f7"}
    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">',
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{PAD_L}" y1="{PAD_T+inner_h}" x2="{PAD_L+inner_w}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
        f'<text x="{PAD_L-8}" y="{y_pos(50)+4}" fill="#94a3b8" font-size="11" text-anchor="end">50%</text>',
        f'<text x="{PAD_L-8}" y="{y_pos(60)+4}" fill="#94a3b8" font-size="11" text-anchor="end">60%</text>',
        f'<text x="{PAD_L-8}" y="{y_pos(70)+4}" fill="#94a3b8" font-size="11" text-anchor="end">70%</text>',
        f'<text x="{PAD_L-8}" y="{y_pos(80)+4}" fill="#94a3b8" font-size="11" text-anchor="end">80%</text>',
        *[f'<line x1="{PAD_L}" y1="{y_pos(v)}" x2="{PAD_L+inner_w}" y2="{y_pos(v)}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>' for v in (60, 70, 80)],
        f'<text x="{x_pos(1e-5)}" y="{PAD_T+inner_h+18}" fill="#94a3b8" font-size="10" text-anchor="middle">1e-5</text>',
        f'<text x="{x_pos(5e-5)}" y="{PAD_T+inner_h+18}" fill="#94a3b8" font-size="10" text-anchor="middle">5e-5</text>',
        f'<text x="{x_pos(1e-4)}" y="{PAD_T+inner_h+18}" fill="#94a3b8" font-size="10" text-anchor="middle">1e-4</text>',
        f'<text x="{x_pos(2e-4)}" y="{PAD_T+inner_h+18}" fill="#94a3b8" font-size="10" text-anchor="middle">2e-4</text>',
        f'<text x="{PAD_L+inner_w//2}" y="{H-2}" fill="#64748b" font-size="10" text-anchor="middle">Learning Rate</text>',
    ]
    lx = W - 150
    ly = PAD_T + 5
    lines.append(f'<text x="{lx}" y="{ly+10}" fill="#94a3b8" font-size="10">Batch size:</text>')
    for i, (bs, col) in enumerate(batch_color.items()):
        lines.append(f'<rect x="{lx}" y="{ly+18+i*16}" width="10" height="10" fill="{col}" rx="2"/>')
        lines.append(f'<text x="{lx+14}" y="{ly+27+i*16}" fill="#94a3b8" font-size="10">{bs}</text>')
    for exp in EXPERIMENTS:
        if exp["success_rate"] is None:
            continue
        cx = x_pos(exp["lr"])
        cy = y_pos(exp["success_rate"])
        color = batch_color.get(exp["batch"], "#94a3b8")
        r = 8 if exp["is_best"] else 6
        stroke = "#ffffff" if exp["is_best"] else "none"
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{color}" stroke="{stroke}" stroke-width="1.5" opacity="0.9"/>')
        label_dy = -12 if cy > PAD_T + 20 else 18
        lines.append(f'<text x="{cx:.1f}" y="{cy+label_dy:.1f}" fill="#e2e8f0" font-size="9" text-anchor="middle">{exp["id"]}</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def _build_loss_bar_svg() -> str:
    W, H = 700, 160
    PAD_L, PAD_R, PAD_T, PAD_B = 90, 20, 15, 30
    completed = sorted([e for e in EXPERIMENTS if e["status"] == "COMPLETED"], key=lambda e: e["success_rate"], reverse=True)
    n = len(completed)
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B
    bar_h = max(12, inner_h // n - 8)
    gap = (inner_h - bar_h * n) // (n + 1)
    loss_max = 0.20

    def bar_w(loss):
        return loss / loss_max * inner_w

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">',
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{PAD_L}" y1="{PAD_T+inner_h}" x2="{PAD_L+inner_w}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
    ]
    for v in (0.05, 0.10, 0.15, 0.20):
        gx = PAD_L + bar_w(v)
        lines.append(f'<line x1="{gx:.1f}" y1="{PAD_T}" x2="{gx:.1f}" y2="{PAD_T+inner_h}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{gx:.1f}" y="{PAD_T+inner_h+14}" fill="#94a3b8" font-size="10" text-anchor="middle">{v:.2f}</text>')
    lines.append(f'<text x="{PAD_L+inner_w//2}" y="{H-2}" fill="#64748b" font-size="10" text-anchor="middle">Loss</text>')
    for i, exp in enumerate(completed):
        y = PAD_T + gap + i * (bar_h + gap)
        bw = bar_w(exp["loss"])
        color = "#22c55e" if exp["is_best"] else "#38bdf8"
        lines.append(f'<rect x="{PAD_L}" y="{y}" width="{bw:.1f}" height="{bar_h}" fill="{color}" rx="3" opacity="0.85"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{y+bar_h//2+4}" fill="#e2e8f0" font-size="10" text-anchor="end">{exp["id"]} (SR {exp["success_rate"]}%)</text>')
        lines.append(f'<text x="{PAD_L+bw+4:.1f}" y="{y+bar_h//2+4}" fill="#94a3b8" font-size="10">{exp["loss"]:.3f}</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def _status_badge(exp: dict) -> str:
    s = exp["status"]
    if s == "COMPLETED" and exp["is_best"]:
        return '<span style="background:#166534;color:#86efac;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">BEST</span>'
    if s == "COMPLETED":
        return '<span style="background:#1e3a5f;color:#38bdf8;padding:2px 8px;border-radius:4px;font-size:11px;">COMPLETED</span>'
    if s == "RUNNING":
        pct = exp.get("progress_pct", 0)
        return f'<span style="background:#431407;color:#fb923c;padding:2px 8px;border-radius:4px;font-size:11px;">RUNNING {pct}%</span>'
    return '<span style="background:#1e293b;color:#64748b;padding:2px 8px;border-radius:4px;font-size:11px;border:1px solid #334155;">QUEUED</span>'


def _render_html() -> str:
    scatter_svg = _build_scatter_svg()
    loss_svg = _build_loss_bar_svg()
    total = len(EXPERIMENTS)
    running = sum(1 for e in EXPERIMENTS if e["status"] == "RUNNING")
    completed = sum(1 for e in EXPERIMENTS if e["status"] == "COMPLETED")
    best_sr = max((e["success_rate"] for e in EXPERIMENTS if e["success_rate"] is not None), default=0)
    rows = []
    for exp in EXPERIMENTS:
        sr_display = f'{exp["success_rate"]}%' if exp["success_rate"] is not None else "—"
        loss_display = f'{exp["loss"]:.3f}' if exp["loss"] is not None else "—"
        gpu_display = f'{exp["gpu_hrs"]}h' if exp["gpu_hrs"] is not None else "TBD"
        badge = _status_badge(exp)
        rows.append(f"""
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:10px 12px;font-family:monospace;color:#38bdf8;">{exp['id']}</td>
          <td style="padding:10px 12px;color:#e2e8f0;">{_lr_display(exp['lr'])}</td>
          <td style="padding:10px 12px;color:#e2e8f0;">{exp['batch']}</td>
          <td style="padding:10px 12px;color:#e2e8f0;">{exp['epochs']}</td>
          <td style="padding:10px 12px;color:#e2e8f0;font-weight:600;">{sr_display}</td>
          <td style="padding:10px 12px;color:#e2e8f0;">{loss_display}</td>
          <td style="padding:10px 12px;">{badge}</td>
          <td style="padding:10px 12px;color:#94a3b8;">{gpu_display}</td>
        </tr>""")
    rows_html = "".join(rows)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>OCI Robot Cloud — Experiment Tracker</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }}
    .header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }}
    .header h1 {{ font-size: 20px; font-weight: 700; color: #f1f5f9; }}
    .sub {{ font-size: 13px; color: #64748b; margin-top: 2px; }}
    .content {{ padding: 28px 32px; max-width: 1100px; margin: 0 auto; }}
    .banner {{ background: linear-gradient(135deg, #14532d 0%, #166534 100%); border: 1px solid #22c55e; border-radius: 10px; padding: 18px 24px; margin-bottom: 28px; display: flex; align-items: center; gap: 20px; }}
    .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .stat-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px 20px; }}
    .stat-label {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }}
    .stat-value {{ font-size: 28px; font-weight: 700; color: #f1f5f9; }}
    .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px 24px; margin-bottom: 24px; }}
    .section-title {{ font-size: 14px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    thead tr {{ background: #0f172a; }}
    thead th {{ padding: 10px 12px; text-align: left; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; border-bottom: 1px solid #334155; }}
    tbody tr:hover {{ background: #0f172a; }}
    .footer {{ text-align: center; padding: 20px; font-size: 11px; color: #334155; border-top: 1px solid #1e293b; margin-top: 16px; }}
  </style>
</head>
<body>
  <div class="header"><div style="width:10px;height:10px;border-radius:50%;background:#C74634;"></div><div><h1>Experiment Tracker</h1><div class="sub">GR00T N1.6-3B Hyperparameter Search — OCI A100 Fleet</div></div></div>
  <div class="content">
    <div class="banner"><div style="font-size:28px;">&#127942;</div><div><div style="font-size:15px;font-weight:700;color:#86efac;">Best Experiment: exp_003</div><div style="font-size:13px;color:#4ade80;margin-top:3px;">lr=1e-4 &nbsp;|&nbsp; batch=64 &nbsp;|&nbsp; epochs=100 &nbsp;|&nbsp; SR=78% &nbsp;|&nbsp; loss=0.089 &nbsp;|&nbsp; 4.8 GPU-hrs</div></div></div>
    <div class="stats">
      <div class="stat-card"><div class="stat-label">Total Experiments</div><div class="stat-value">{total}</div></div>
      <div class="stat-card"><div class="stat-label">Completed</div><div class="stat-value" style="color:#38bdf8;">{completed}</div></div>
      <div class="stat-card"><div class="stat-label">Running</div><div class="stat-value" style="color:#fb923c;">{running}</div></div>
      <div class="stat-card"><div class="stat-label">Best SR</div><div class="stat-value" style="color:#C74634;">{best_sr}%</div></div>
    </div>
    <div class="section"><div class="section-title">Success Rate vs Learning Rate</div><div style="overflow-x:auto;">{scatter_svg}</div></div>
    <div class="section"><div class="section-title">Loss by Experiment (Completed, sorted by SR)</div><div style="overflow-x:auto;">{loss_svg}</div></div>
    <div class="section"><div class="section-title">All Experiments</div>
      <table><thead><tr><th>ID</th><th>LR</th><th>Batch</th><th>Epochs</th><th>Success Rate</th><th>Loss</th><th>Status</th><th>GPU-hrs</th></tr></thead>
      <tbody>{rows_html}</tbody></table></div>
  </div>
  <div class="footer">Oracle Confidential | OCI Robot Cloud Experiment Tracker | Port 8124</div>
</body></html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return _render_html()


@app.get("/experiments")
def list_experiments():
    return JSONResponse(content=EXPERIMENTS)


@app.get("/experiments/{exp_id}")
def get_experiment(exp_id: str):
    for exp in EXPERIMENTS:
        if exp["id"] == exp_id:
            return JSONResponse(content=exp)
    raise HTTPException(status_code=404, detail=f"Experiment '{exp_id}' not found")


@app.get("/best")
def best_experiment():
    for exp in EXPERIMENTS:
        if exp.get("is_best"):
            return JSONResponse(content=exp)
    raise HTTPException(status_code=404, detail="No best experiment found")


@app.get("/health")
def health():
    return JSONResponse(content={"status": "ok", "service": "experiment_tracker", "port": 8124, "timestamp": datetime.utcnow().isoformat() + "Z", "total_experiments": len(EXPERIMENTS)})


def main():
    uvicorn.run("experiment_tracker:app", host="0.0.0.0", port=8124, reload=False)


if __name__ == "__main__":
    main()

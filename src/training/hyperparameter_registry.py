"""hyperparameter_registry.py
OCI Robot Cloud — Hyperparameter registry and HPO search results dashboard.

Tracks Optuna TPE sampler trials, stores winning configurations, and serves
a dark-theme HTML dashboard with scatter and parallel-coordinates SVG charts.

Usage:
    pip install fastapi uvicorn
    python src/training/hyperparameter_registry.py

Port: 8129
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    raise ImportError("fastapi and uvicorn are required: pip install fastapi uvicorn")

PORT = 8129
SERVICE_NAME = "Hyperparameter Registry"

TRIALS: list[dict[str, Any]] = [
    {"id": "trial_001", "lr": 1.2e-5,  "batch": 16,  "warmup": 50,  "wd": 0.08,  "chunk": 8,  "sr": 58, "loss": 0.198},
    {"id": "trial_002", "lr": 8.5e-5,  "batch": 32,  "warmup": 150, "wd": 0.05,  "chunk": 16, "sr": 67, "loss": 0.162},
    {"id": "trial_003", "lr": 9.3e-5,  "batch": 64,  "warmup": 180, "wd": 0.012, "chunk": 16, "sr": 75, "loss": 0.101},
    {"id": "trial_004", "lr": 2.1e-5,  "batch": 128, "warmup": 100, "wd": 0.07,  "chunk": 8,  "sr": 62, "loss": 0.183},
    {"id": "trial_005", "lr": 1.5e-4,  "batch": 32,  "warmup": 250, "wd": 0.02,  "chunk": 16, "sr": 70, "loss": 0.142},
    {"id": "trial_006", "lr": 5.4e-5,  "batch": 64,  "warmup": 120, "wd": 0.04,  "chunk": 8,  "sr": 68, "loss": 0.155},
    {"id": "trial_007", "lr": 1.0e-4,  "batch": 64,  "warmup": 200, "wd": 0.01,  "chunk": 16, "sr": 78, "loss": 0.089},
    {"id": "trial_008", "lr": 7.2e-5,  "batch": 32,  "warmup": 160, "wd": 0.03,  "chunk": 16, "sr": 71, "loss": 0.138},
    {"id": "trial_009", "lr": 1.1e-4,  "batch": 64,  "warmup": 220, "wd": 0.011, "chunk": 16, "sr": 73, "loss": 0.115},
    {"id": "trial_010", "lr": 3.8e-5,  "batch": 16,  "warmup": 80,  "wd": 0.06,  "chunk": 8,  "sr": 63, "loss": 0.175},
    {"id": "trial_011", "lr": 1.7e-4,  "batch": 128, "warmup": 300, "wd": 0.005, "chunk": 32, "sr": 69, "loss": 0.148},
    {"id": "trial_012", "lr": 9.8e-5,  "batch": 64,  "warmup": 190, "wd": 0.013, "chunk": 16, "sr": 76, "loss": 0.095},
    {"id": "trial_013", "lr": 6.6e-5,  "batch": 32,  "warmup": 140, "wd": 0.025, "chunk": 16, "sr": 66, "loss": 0.163},
    {"id": "trial_014", "lr": 2.0e-4,  "batch": 128, "warmup": 400, "wd": 0.003, "chunk": 32, "sr": 64, "loss": 0.172},
    {"id": "trial_015", "lr": 1.4e-5,  "batch": 16,  "warmup": 60,  "wd": 0.09,  "chunk": 8,  "sr": 61, "loss": 0.191},
    {"id": "trial_016", "lr": 8.0e-5,  "batch": 64,  "warmup": 170, "wd": 0.018, "chunk": 16, "sr": 72, "loss": 0.125},
    {"id": "trial_017", "lr": 1.05e-4, "batch": 64,  "warmup": 210, "wd": 0.010, "chunk": 16, "sr": 74, "loss": 0.108},
    {"id": "trial_018", "lr": 5.0e-5,  "batch": 32,  "warmup": 130, "wd": 0.04,  "chunk": 8,  "sr": 65, "loss": 0.169},
    {"id": "trial_019", "lr": 1.3e-4,  "batch": 64,  "warmup": 230, "wd": 0.009, "chunk": 16, "sr": 72, "loss": 0.119},
    {"id": "trial_020", "lr": 4.5e-5,  "batch": 32,  "warmup": 110, "wd": 0.05,  "chunk": 8,  "sr": 64, "loss": 0.177},
]

BEST_TRIAL = next(t for t in TRIALS if t["id"] == "trial_007")

REGISTRY_META: dict[str, Any] = {
    "sampler": "Optuna TPE", "trials_run": len(TRIALS), "best_sr_pct": 78, "best_loss": 0.089,
    "search_time_minutes": 127, "param_space_size": "~12,288 combinations",
    "base_model": "GR00T N1.6-3B", "dataset": "LIBERO-SDG-1000",
    "eval_metric": "closed-loop success rate (SR%)",
}

_TOP5_IDS = {"trial_007", "trial_012", "trial_003", "trial_017", "trial_009"}
_BOT3_IDS = {"trial_001", "trial_015", "trial_004"}


def _svg_scatter() -> str:
    W, H = 700, 200
    PAD_L, PAD_R, PAD_T, PAD_B = 56, 24, 20, 40
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    X_MIN, X_MAX = -5.0, -3.7
    Y_MIN, Y_MAX = 55.0, 82.0
    BATCH_COLORS = {16: "#94a3b8", 32: "#f59e0b", 64: "#C74634", 128: "#a78bfa"}

    def px(lr_val): return PAD_L + (math.log10(lr_val) - X_MIN) / (X_MAX - X_MIN) * chart_w
    def py(sr): return PAD_T + chart_h - (sr - Y_MIN) / (Y_MAX - Y_MIN) * chart_h

    grid = "".join(f'<line x1="{PAD_L}" y1="{py(sr):.1f}" x2="{PAD_L+chart_w}" y2="{py(sr):.1f}" stroke="#1e293b" stroke-width="1"/><text x="{PAD_L-6}" y="{py(sr)+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{sr}%</text>' for sr in [60, 65, 70, 75, 80])
    x_labels = "".join(f'<text x="{PAD_L+(log_v-X_MIN)/(X_MAX-X_MIN)*chart_w:.1f}" y="{PAD_T+chart_h+16}" fill="#94a3b8" font-size="10" text-anchor="middle">{label}</text>' for log_v, label in [(-5.0, "1e-5"), (-4.5, "3e-5"), (-4.0, "1e-4"), (-3.7, "2e-4")])
    opt_x = px(1e-4)
    opt_line = f'<line x1="{opt_x:.1f}" y1="{PAD_T}" x2="{opt_x:.1f}" y2="{PAD_T+chart_h}" stroke="#C74634" stroke-width="1" stroke-dasharray="4,3" opacity="0.7"/><text x="{opt_x+4:.1f}" y="{PAD_T+10}" fill="#C74634" font-size="10">optimal lr</text>'
    dots = ""
    for t in TRIALS:
        x, y = px(t["lr"]), py(t["sr"])
        color = BATCH_COLORS.get(t["batch"], "#94a3b8")
        if t["id"] == "trial_007":
            dots += f'<text x="{x:.1f}" y="{y+5:.1f}" fill="#fbbf24" font-size="14" text-anchor="middle">★</text><text x="{x+10:.1f}" y="{y-4:.1f}" fill="#fbbf24" font-size="9">trial_007</text>'
        else:
            dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" opacity="0.85"/>'
    legend = ""
    lx = PAD_L + chart_w - 170
    for idx, (bs, color) in enumerate(sorted(BATCH_COLORS.items())):
        ly = PAD_T + 4 + idx * 18
        legend += f'<circle cx="{lx+6}" cy="{ly+6}" r="5" fill="{color}"/><text x="{lx+16}" y="{ly+10}" fill="#94a3b8" font-size="10">batch={bs}</text>'
    return f"""<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#0f172a" rx="6"/>
  {grid}{opt_line}{dots}{x_labels}{legend}
  <text x="{PAD_L}" y="14" fill="#94a3b8" font-size="10">SR %</text>
  <text x="{W//2}" y="{H-4}" fill="#94a3b8" font-size="10" text-anchor="middle">log₁₀(learning rate)</text>
</svg>"""


def _svg_parallel() -> str:
    W, H = 700, 160
    PAD_L, PAD_R, PAD_T, PAD_B = 50, 50, 30, 36
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    axes_cfg = [
        ("lr (log)", math.log10(1.2e-5), math.log10(2.0e-4), lambda t: math.log10(t["lr"]), "2e-4", "1e-5"),
        ("batch",    16,                 128,                 lambda t: float(t["batch"]),    "128",  "16"),
        ("warmup",   50,                 400,                 lambda t: float(t["warmup"]),   "400",  "50"),
        ("SR %",     58,                 78,                  lambda t: float(t["sr"]),       "78%",  "58%"),
    ]
    n_axes = len(axes_cfg)
    axis_xs = [PAD_L + i * chart_w / (n_axes - 1) for i in range(n_axes)]

    def norm_y(val, vmin, vmax):
        frac = (val - vmin) / (vmax - vmin) if vmax != vmin else 0.5
        return PAD_T + chart_h - frac * chart_h

    def trial_pts(t):
        return [(axis_xs[i], norm_y(getter(t), vmin, vmax)) for i, (_, vmin, vmax, getter, _, _) in enumerate(axes_cfg)]

    def polyline(pts, color, opacity):
        coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        return f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="1.5" opacity="{opacity}" stroke-linejoin="round"/>'

    lines = ""
    for t in TRIALS:
        if t["id"] not in _TOP5_IDS and t["id"] not in _BOT3_IDS:
            lines += polyline(trial_pts(t), "#475569", "0.4")
    for t in TRIALS:
        if t["id"] in _BOT3_IDS:
            lines += polyline(trial_pts(t), "#f87171", "0.85")
    for t in TRIALS:
        if t["id"] in _TOP5_IDS:
            color = "#fbbf24" if t["id"] == "trial_007" else "#4ade80"
            lines += polyline(trial_pts(t), color, "0.95")

    axes_svg = ""
    for i, (label, vmin, vmax, _, top_label, bot_label) in enumerate(axes_cfg):
        ax = axis_xs[i]
        axes_svg += (f'<line x1="{ax:.1f}" y1="{PAD_T}" x2="{ax:.1f}" y2="{PAD_T+chart_h}" stroke="#334155" stroke-width="1.5"/>'
                     f'<text x="{ax:.1f}" y="{PAD_T-6}" fill="#94a3b8" font-size="10" text-anchor="middle">{label}</text>'
                     f'<text x="{ax:.1f}" y="{PAD_T+10}" fill="#475569" font-size="9" text-anchor="middle">{top_label}</text>'
                     f'<text x="{ax:.1f}" y="{PAD_T+chart_h+12}" fill="#475569" font-size="9" text-anchor="middle">{bot_label}</text>')

    legend = (f'<circle cx="{W-PAD_R-110}" cy="{H-10}" r="4" fill="#4ade80"/><text x="{W-PAD_R-102}" y="{H-6}" fill="#94a3b8" font-size="10">top-5</text>'
              f'<circle cx="{W-PAD_R-60}" cy="{H-10}" r="4" fill="#f87171"/><text x="{W-PAD_R-52}" y="{H-6}" fill="#94a3b8" font-size="10">bottom-3</text>'
              f'<text x="{W-PAD_R-5}" y="{H-6}" fill="#fbbf24" font-size="12" text-anchor="end">★ best</text>')
    return f"""<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#0f172a" rx="6"/>
  {lines}{axes_svg}{legend}
</svg>"""


def _status_badge_trial(trial_id: str) -> str:
    if trial_id == "trial_007":
        return '<span style="background:#172554;color:#fbbf24;border:1px solid #fbbf24;padding:2px 10px;border-radius:99px;font-size:11px;font-weight:700">★ BEST</span>'
    if trial_id in _TOP5_IDS:
        return '<span style="background:#052e16;color:#4ade80;border:1px solid #4ade80;padding:2px 10px;border-radius:99px;font-size:11px;font-weight:600">TOP-5</span>'
    return ""


def _build_html() -> str:
    best = BEST_TRIAL
    stat_cards = [("Trials Run", str(REGISTRY_META["trials_run"]), "#38bdf8"), ("Best SR", f"{REGISTRY_META['best_sr_pct']}%", "#22c55e"), ("Best Loss", str(REGISTRY_META["best_loss"]), "#C74634"), ("Search Time", f"{REGISTRY_META['search_time_minutes']} min", "#f59e0b")]
    cards_html = "".join(f'<div style="background:#1e293b;border-radius:10px;padding:20px 24px;border-left:4px solid {accent};flex:1;min-width:155px"><div style="color:#94a3b8;font-size:13px;margin-bottom:6px">{title}</div><div style="color:{accent};font-size:28px;font-weight:700">{value}</div></div>' for title, value, accent in stat_cards)
    best_callout = f"""
    <div style="background:#1e293b;border:2px solid #fbbf24;border-radius:12px;padding:24px;margin-bottom:24px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
        <span style="font-size:22px">★</span>
        <div style="font-size:16px;font-weight:700;color:#fbbf24">Champion Configuration — trial_007</div>
        <div style="margin-left:auto;background:#172554;color:#fbbf24;border:1px solid #fbbf24;padding:4px 14px;border-radius:99px;font-size:13px;font-weight:700">SR = {best['sr']}%</div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:12px">
        {''.join(f'<div style="background:#0f172a;border-radius:8px;padding:10px 18px;text-align:center;min-width:110px"><div style="color:#64748b;font-size:11px;margin-bottom:4px">{label}</div><div style="color:#f1f5f9;font-size:16px;font-weight:600">{val}</div></div>' for label, val in [("Learning Rate", f"{best['lr']:.0e}"), ("Batch Size", str(best['batch'])), ("Warmup Steps", str(best['warmup'])), ("Weight Decay", str(best['wd'])), ("Chunk Size", str(best['chunk'])), ("Val Loss", str(best['loss']))])}
      </div>
    </div>"""
    top10 = sorted(TRIALS, key=lambda t: -t["sr"])[:10]
    rows_html = "".join(f'<tr style="border-bottom:1px solid #334155"><td style="padding:10px 14px;color:#38bdf8;font-family:monospace">{t["id"]}</td><td style="padding:10px 14px;color:#e2e8f0;font-family:monospace">{t["lr"]:.1e}</td><td style="padding:10px 14px;color:#e2e8f0;text-align:center">{t["batch"]}</td><td style="padding:10px 14px;color:#e2e8f0;text-align:center">{t["warmup"]}</td><td style="padding:10px 14px;color:#e2e8f0;text-align:center">{t["wd"]}</td><td style="padding:10px 14px;color:#e2e8f0;text-align:center">{t["chunk"]}</td><td style="padding:10px 14px;color:#22c55e;font-weight:600;text-align:right">{t["sr"]}%</td><td style="padding:10px 14px;color:#94a3b8;text-align:right">{t["loss"]}</td><td style="padding:10px 14px;text-align:center">{_status_badge_trial(t["id"])}</td></tr>' for t in top10)
    scatter_svg = _svg_scatter()
    parallel_svg = _svg_parallel()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>OCI Robot Cloud — {SERVICE_NAME}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}}
    table{{border-collapse:collapse;width:100%}}
    th{{background:#0f172a;color:#64748b;font-size:12px;letter-spacing:.8px;text-transform:uppercase;padding:9px 14px;text-align:left}}
    tr:hover td{{background:#263348}}
    .section{{background:#1e293b;border-radius:12px;padding:24px;margin-bottom:24px}}
    .section-title{{color:#f1f5f9;font-size:16px;font-weight:600;margin-bottom:16px;display:flex;align-items:center;gap:8px}}
    .dot{{width:8px;height:8px;border-radius:50%;background:#C74634;display:inline-block}}
  </style>
</head>
<body>
<div style="max-width:980px;margin:0 auto;padding:32px 20px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:28px">
    <div style="display:flex;align-items:center;gap:12px">
      <div style="width:36px;height:36px;background:#C74634;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px">H</div>
      <div>
        <div style="font-size:22px;font-weight:700;color:#f1f5f9">OCI Robot Cloud <span style="color:#C74634">{SERVICE_NAME}</span></div>
        <div style="color:#64748b;font-size:13px;margin-top:2px">Optuna TPE · GR00T N1.6-3B · LIBERO-SDG-1000 · Port {PORT}</div>
      </div>
    </div>
    <div style="text-align:right"><div style="color:#22c55e;font-size:13px;font-weight:600">● LIVE</div><div style="color:#64748b;font-size:12px;margin-top:2px">{now_utc}</div></div>
  </div>
  <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px">{cards_html}</div>
  {best_callout}
  <div class="section"><div class="section-title"><span class="dot"></span>SR% vs Learning Rate</div><div style="overflow-x:auto">{scatter_svg}</div><div style="color:#64748b;font-size:12px;margin-top:8px">Color = batch size · ★ = best trial (trial_007, lr=1e-4) · dashed line = optimal lr</div></div>
  <div class="section"><div class="section-title"><span class="dot"></span>Parallel Coordinates — Top-5 vs Bottom-3</div><div style="overflow-x:auto">{parallel_svg}</div><div style="color:#64748b;font-size:12px;margin-top:8px">Green = top-5 trials · Red = bottom-3 trials · Gold star = champion (trial_007)</div></div>
  <div class="section"><div class="section-title"><span class="dot"></span>Top 10 Trials by SR%</div><div style="overflow-x:auto"><table><thead><tr><th>Trial</th><th>Learning Rate</th><th style="text-align:center">Batch</th><th style="text-align:center">Warmup</th><th style="text-align:center">Wt Decay</th><th style="text-align:center">Chunk</th><th style="text-align:right">SR%</th><th style="text-align:right">Loss</th><th style="text-align:center">Rank</th></tr></thead><tbody>{rows_html}</tbody></table></div></div>
  <div class="section"><div class="section-title"><span class="dot"></span>Search Metadata</div><div style="display:flex;flex-wrap:wrap;gap:16px">{''.join(f'<div style="flex:1;min-width:200px"><div style="color:#64748b;font-size:12px">{k.replace("_"," ").title()}</div><div style="color:#e2e8f0;font-size:14px;margin-top:2px">{v}</div></div>' for k, v in REGISTRY_META.items())}</div></div>
  <div style="text-align:center;color:#334155;font-size:12px;margin-top:32px;padding-top:16px;border-top:1px solid #1e293b">Oracle Confidential | OCI Robot Cloud {SERVICE_NAME} | Port {PORT}</div>
</div>
</body>
</html>"""


app = FastAPI(title=f"OCI Robot Cloud — {SERVICE_NAME}", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse(content=_build_html())


@app.get("/trials")
def get_trials() -> JSONResponse:
    return JSONResponse(content={"trials": sorted(TRIALS, key=lambda t: -t["sr"]), "total": len(TRIALS), "sampler": REGISTRY_META["sampler"]})


@app.get("/best")
def get_best() -> JSONResponse:
    return JSONResponse(content={"trial": BEST_TRIAL, "rank": 1, "notes": "Champion config — Optuna TPE converged to lr=1e-4, batch=64"})


@app.get("/trials/{trial_id}")
def get_trial(trial_id: str) -> JSONResponse:
    match = next((t for t in TRIALS if t["id"] == trial_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Trial '{trial_id}' not found")
    rank = sorted(TRIALS, key=lambda t: -t["sr"]).index(match) + 1
    return JSONResponse(content={"trial": match, "rank": rank})


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse(content={"status": "ok", "service": SERVICE_NAME, "port": PORT, "trials_indexed": len(TRIALS), "best_trial": BEST_TRIAL["id"], "timestamp": datetime.now(timezone.utc).isoformat()})


def main() -> None:
    uvicorn.run("hyperparameter_registry:app", host="0.0.0.0", port=PORT, reload=False, log_level="info")


if __name__ == "__main__":
    main()

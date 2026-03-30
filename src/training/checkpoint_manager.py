"""checkpoint_manager.py
OCI Robot Cloud — Checkpoint registry and promotion dashboard.
Tracks training checkpoints across runs, shows SR progression, and manages
PRODUCTION / STAGING slots.
Port: 8126
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

PORT = 8126
SERVICE_NAME = "Checkpoint Manager"

# ---------------------------------------------------------------------------
# Static checkpoint data
# ---------------------------------------------------------------------------

CHECKPOINTS: list[dict[str, Any]] = [
    # dagger_run9 — 3 checkpoints
    {"run": "dagger_run9", "step": 1000, "sr_pct": 42, "loss": 0.188, "size_gb": 6.2, "slot": None, "ts": "2026-03-01T08:00:00Z"},
    {"run": "dagger_run9", "step": 3000, "sr_pct": 61, "loss": 0.134, "size_gb": 6.2, "slot": None, "ts": "2026-03-01T14:00:00Z"},
    {"run": "dagger_run9", "step": 5000, "sr_pct": 71, "loss": 0.103, "size_gb": 6.2, "slot": "PRODUCTION", "ts": "2026-03-01T20:00:00Z"},
    # groot_finetune_v2 — 3 checkpoints
    {"run": "groot_finetune_v2", "step": 1000, "sr_pct": 55, "loss": 0.162, "size_gb": 6.7, "slot": None, "ts": "2026-03-10T09:00:00Z"},
    {"run": "groot_finetune_v2", "step": 3000, "sr_pct": 68, "loss": 0.121, "size_gb": 6.7, "slot": None, "ts": "2026-03-10T15:00:00Z"},
    {"run": "groot_finetune_v2", "step": 5000, "sr_pct": 78, "loss": 0.089, "size_gb": 6.7, "slot": "STAGING", "ts": "2026-03-10T21:00:00Z"},
    # dagger_run10 — 2 partial checkpoints (in progress)
    {"run": "dagger_run10", "step": 1000, "sr_pct": 61, "loss": 0.155, "size_gb": 6.7, "slot": None, "ts": "2026-03-20T10:00:00Z"},
    {"run": "dagger_run10", "step": 2500, "sr_pct": 70, "loss": 0.118, "size_gb": 6.7, "slot": None, "ts": "2026-03-20T16:00:00Z"},
]

RUNS = list(dict.fromkeys(c["run"] for c in CHECKPOINTS))  # preserve order
RUN_COLORS = {"dagger_run9": "#38bdf8", "groot_finetune_v2": "#C74634", "dagger_run10": "#f59e0b"}
RUN_STATUS = {"dagger_run9": "COMPLETE", "groot_finetune_v2": "COMPLETE", "dagger_run10": "IN_PROGRESS"}

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _svg_sr_line() -> str:
    """SR vs step line chart 700x220. One line per run. ★ at PRODUCTION/STAGING."""
    W, H = 700, 220
    PAD_L, PAD_R, PAD_T, PAD_B = 52, 24, 20, 40
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B

    max_step = max(c["step"] for c in CHECKPOINTS)
    Y_MIN, Y_MAX = 35, 85

    def cx(step: int) -> float:
        return PAD_L + step / max_step * chart_w

    def cy(sr: float) -> float:
        return PAD_T + chart_h - (sr - Y_MIN) / (Y_MAX - Y_MIN) * chart_h

    grid = ""
    for sr in [40, 50, 60, 70, 80]:
        y = cy(sr)
        grid += (f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L+chart_w}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
                 f'<text x="{PAD_L-6}" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{sr}%</text>')

    x_labels = ""
    for step in [0, 1000, 2000, 3000, 4000, 5000]:
        x = cx(step)
        x_labels += f'<text x="{x:.1f}" y="{PAD_T+chart_h+16}" fill="#94a3b8" font-size="10" text-anchor="middle">{step}</text>'

    paths = ""
    for run in RUNS:
        run_ckpts = sorted([c for c in CHECKPOINTS if c["run"] == run], key=lambda c: c["step"])
        color = RUN_COLORS[run]
        pts = [(cx(c["step"]), cy(c["sr_pct"])) for c in run_ckpts]
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
        paths += f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" opacity="0.9"/>'
        for i, (ckpt, (x, y)) in enumerate(zip(run_ckpts, pts)):
            if ckpt["slot"] in ("PRODUCTION", "STAGING"):
                star_color = "#22c55e" if ckpt["slot"] == "PRODUCTION" else "#fbbf24"
                paths += (f'<text x="{x:.1f}" y="{y+5:.1f}" fill="{star_color}" font-size="14" text-anchor="middle">\u2605</text>'
                          f'<text x="{x+12:.1f}" y="{y-6:.1f}" fill="{star_color}" font-size="9">{ckpt["slot"]}</text>')
            else:
                paths += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" opacity="0.8"/>'

    legend = ""
    lx = PAD_L
    for run in RUNS:
        color = RUN_COLORS[run]
        legend += (f'<rect x="{lx}" y="7" width="16" height="4" fill="{color}" rx="2"/>'
                   f'<text x="{lx+20}" y="14" fill="#94a3b8" font-size="10">{run}</text>')
        lx += len(run) * 6.5 + 28

    return f"""<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#0f172a" rx="6"/>
  {grid}
  {paths}
  {x_labels}
  {legend}
  <text x="{PAD_L}" y="18" fill="#94a3b8" font-size="10">SR %</text>
  <text x="{W//2}" y="{H-2}" fill="#94a3b8" font-size="10" text-anchor="middle">Training Step</text>
</svg>"""


def _svg_storage_bar() -> str:
    """Stacked horizontal bar for checkpoint storage by run."""
    W, H = 700, 100
    PAD_L, PAD_R, PAD_T, PAD_B = 140, 20, 15, 20
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B

    run_totals = {}
    for run in RUNS:
        run_ckpts = [c for c in CHECKPOINTS if c["run"] == run]
        run_totals[run] = round(sum(c["size_gb"] for c in run_ckpts), 1)

    total_gb = sum(run_totals.values())
    bar_h = max(14, inner_h // len(RUNS) - 8)
    gap = (inner_h - bar_h * len(RUNS)) // (len(RUNS) + 1)

    lines = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:6px;">']
    for i, run in enumerate(RUNS):
        y = PAD_T + gap + i * (bar_h + gap)
        bw = run_totals[run] / (total_gb / inner_w) if total_gb > 0 else 0
        bw = min(bw, inner_w)
        color = RUN_COLORS[run]
        lines.append(f'<rect x="{PAD_L}" y="{y}" width="{bw:.1f}" height="{bar_h}" fill="{color}" rx="3" opacity="0.8"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{y+bar_h//2+4}" fill="#e2e8f0" font-size="10" text-anchor="end">{run}</text>')
        lines.append(f'<text x="{PAD_L+bw+5:.1f}" y="{y+bar_h//2+4}" fill="#94a3b8" font-size="10">{run_totals[run]} GB</text>')
    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _slot_badge(slot: str | None) -> str:
    if slot == "PRODUCTION":
        return '<span style="background:#166534;color:#86efac;border:1px solid #22c55e;padding:2px 10px;border-radius:99px;font-size:11px;font-weight:700">PRODUCTION</span>'
    if slot == "STAGING":
        return '<span style="background:#172554;color:#fbbf24;border:1px solid #fbbf24;padding:2px 10px;border-radius:99px;font-size:11px;font-weight:700">STAGING</span>'
    return ""


def _build_html() -> str:
    prod_ckpt = next((c for c in CHECKPOINTS if c["slot"] == "PRODUCTION"), None)
    stag_ckpt = next((c for c in CHECKPOINTS if c["slot"] == "STAGING"), None)

    sr_svg = _svg_sr_line()
    storage_svg = _svg_storage_bar()

    total_ckpts = len(CHECKPOINTS)
    total_gb = round(sum(c["size_gb"] for c in CHECKPOINTS), 1)
    sr_delta = (stag_ckpt["sr_pct"] - prod_ckpt["sr_pct"]) if prod_ckpt and stag_ckpt else 0

    stat_cards = [
        ("Total Checkpoints", str(total_ckpts), "#38bdf8"),
        ("PRODUCTION SR", f"{prod_ckpt['sr_pct']}%" if prod_ckpt else "—", "#22c55e"),
        ("STAGING SR", f"{stag_ckpt['sr_pct']}%" if stag_ckpt else "—", "#fbbf24"),
        ("Staging Lead", f"+{sr_delta}pp", "#C74634"),
    ]
    cards_html = ""
    for title, value, accent in stat_cards:
        cards_html += f"""
        <div style="background:#1e293b;border-radius:10px;padding:20px 24px;border-left:4px solid {accent};flex:1;min-width:155px">
          <div style="color:#94a3b8;font-size:13px;margin-bottom:6px">{title}</div>
          <div style="color:{accent};font-size:28px;font-weight:700">{value}</div>
        </div>"""

    rows_html = ""
    for c in CHECKPOINTS:
        badge = _slot_badge(c["slot"])
        run_color = RUN_COLORS.get(c["run"], "#94a3b8")
        rows_html += f"""
        <tr style="border-bottom:1px solid #334155">
          <td style="padding:10px 14px;color:{run_color};font-family:monospace">{c['run']}</td>
          <td style="padding:10px 14px;color:#e2e8f0;text-align:center">{c['step']:,}</td>
          <td style="padding:10px 14px;color:#22c55e;font-weight:600;text-align:right">{c['sr_pct']}%</td>
          <td style="padding:10px 14px;color:#94a3b8;text-align:right">{c['loss']}</td>
          <td style="padding:10px 14px;color:#64748b;text-align:center">{c['size_gb']} GB</td>
          <td style="padding:10px 14px;text-align:center">{badge}</td>
        </tr>"""

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
    th{{background:#0f172a;color:#64748b;font-size:12px;letter-spacing:.8px;text-transform:uppercase;padding:10px 14px;text-align:left}}
    tr:hover td{{background:#263348}}
    .section{{background:#1e293b;border-radius:12px;padding:24px;margin-bottom:24px}}
    .section-title{{color:#f1f5f9;font-size:16px;font-weight:600;margin-bottom:16px}}
    .dot{{width:8px;height:8px;border-radius:50%;background:#C74634;display:inline-block;margin-right:8px}}
  </style>
</head>
<body>
<div style="max-width:980px;margin:0 auto;padding:32px 20px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:28px">
    <div style="display:flex;align-items:center;gap:12px">
      <div style="width:36px;height:36px;background:#C74634;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px">C</div>
      <div>
        <div style="font-size:22px;font-weight:700;color:#f1f5f9">OCI Robot Cloud <span style="color:#C74634">{SERVICE_NAME}</span></div>
        <div style="color:#64748b;font-size:13px;margin-top:2px">GR00T N1.6-3B · dagger_run9 / groot_finetune_v2 / dagger_run10 · Port {PORT}</div>
      </div>
    </div>
    <div style="text-align:right"><div style="color:#22c55e;font-size:13px;font-weight:600">● LIVE</div><div style="color:#64748b;font-size:12px;margin-top:2px">{now_utc}</div></div>
  </div>

  <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px">{cards_html}</div>

  <div class="section">
    <div class="section-title"><span class="dot"></span>SR% Progression by Step</div>
    <div style="overflow-x:auto">{sr_svg}</div>
    <div style="color:#64748b;font-size:12px;margin-top:8px">&#9733; green = PRODUCTION &nbsp;|&nbsp; &#9733; gold = STAGING</div>
  </div>

  <div class="section">
    <div class="section-title"><span class="dot"></span>Checkpoint Storage by Run</div>
    <div style="overflow-x:auto">{storage_svg}</div>
  </div>

  <div class="section">
    <div class="section-title"><span class="dot"></span>All Checkpoints</div>
    <div style="overflow-x:auto">
      <table>
        <thead><tr><th>Run</th><th style="text-align:center">Step</th><th style="text-align:right">SR%</th><th style="text-align:right">Loss</th><th style="text-align:center">Size</th><th style="text-align:center">Slot</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
  </div>

  <div style="text-align:center;color:#334155;font-size:12px;margin-top:32px;padding-top:16px;border-top:1px solid #1e293b">
    Oracle Confidential | OCI Robot Cloud {SERVICE_NAME} | Port {PORT}
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title=f"OCI Robot Cloud — {SERVICE_NAME}", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse(content=_build_html())


@app.get("/checkpoints")
def list_checkpoints() -> JSONResponse:
    return JSONResponse(content={"checkpoints": CHECKPOINTS, "total": len(CHECKPOINTS)})


@app.get("/checkpoints/{run}")
def get_run_checkpoints(run: str) -> JSONResponse:
    ckpts = [c for c in CHECKPOINTS if c["run"] == run]
    if not ckpts:
        raise HTTPException(status_code=404, detail=f"Run '{run}' not found")
    return JSONResponse(content={"run": run, "checkpoints": ckpts})


@app.get("/slots")
def get_slots() -> JSONResponse:
    prod = next((c for c in CHECKPOINTS if c["slot"] == "PRODUCTION"), None)
    stag = next((c for c in CHECKPOINTS if c["slot"] == "STAGING"), None)
    return JSONResponse(content={"PRODUCTION": prod, "STAGING": stag})


@app.get("/health")
def health() -> JSONResponse:
    prod = next((c for c in CHECKPOINTS if c["slot"] == "PRODUCTION"), None)
    return JSONResponse(content={"status": "ok", "service": SERVICE_NAME, "port": PORT, "total_checkpoints": len(CHECKPOINTS), "production_sr_pct": prod["sr_pct"] if prod else None, "timestamp": datetime.now(timezone.utc).isoformat()})


def main() -> None:
    uvicorn.run("checkpoint_manager:app", host="0.0.0.0", port=PORT, reload=False)


if __name__ == "__main__":
    main()

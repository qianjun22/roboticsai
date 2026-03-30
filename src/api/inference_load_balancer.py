"""inference_load_balancer.py
OCI Robot Cloud — Inference load balancer dashboard.
Routes GR00T N1.6-3B inference requests across backends with weighted traffic
splitting (prod 90%, canary 10%) and serves a dark-theme HTML dashboard.
Port: 8127
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

PORT = 8127
SERVICE_NAME = "Inference Load Balancer"

# ---------------------------------------------------------------------------
# Static backend data
# ---------------------------------------------------------------------------

BACKENDS: list[dict[str, Any]] = [
    {
        "id": "groot-prod",
        "model": "dagger_run9_v2.2",
        "weight_pct": 90,
        "status": "ACTIVE",
        "region": "us-ashburn-1",
        "avg_latency_ms": 226,
        "p99_latency_ms": 341,
        "req_8h": 2_847,
        "error_rate_pct": 0.4,
        "gpu_util_pct": 87,
    },
    {
        "id": "groot-canary",
        "model": "groot_finetune_v2",
        "weight_pct": 10,
        "status": "ACTIVE",
        "region": "us-ashburn-1",
        "avg_latency_ms": 223,
        "p99_latency_ms": 335,
        "req_8h": 316,
        "error_rate_pct": 0.3,
        "gpu_util_pct": 45,
    },
    {
        "id": "groot-staging",
        "model": "groot_finetune_v2",
        "weight_pct": 0,
        "status": "STANDBY",
        "region": "eu-frankfurt-1",
        "avg_latency_ms": 231,
        "p99_latency_ms": 358,
        "req_8h": 0,
        "error_rate_pct": 0.0,
        "gpu_util_pct": 71,
    },
    {
        "id": "groot-shadow",
        "model": "dagger_run9_v2.2",
        "weight_pct": 0,
        "status": "CRITICAL",
        "region": "us-ashburn-1",
        "avg_latency_ms": None,
        "p99_latency_ms": None,
        "req_8h": 0,
        "error_rate_pct": None,
        "gpu_util_pct": 11,
        "alert": "Config drift — chunk_size=8 (expected 16)",
    },
]

# 8h traffic history (requests per hour, last 8 hours)
TRAFFIC_8H: list[int] = [287, 312, 298, 324, 341, 318, 305, 329]
HOURS_LABELS = ["8h ago", "7h ago", "6h ago", "5h ago", "4h ago", "3h ago", "2h ago", "1h ago"]

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _arc_path(cx: float, cy: float, r_out: float, r_in: float, start_deg: float, end_deg: float) -> str:
    """Donut arc segment from start_deg to end_deg."""
    def pt(deg: float, r: float):
        rad = math.radians(deg - 90)
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    x1o, y1o = pt(start_deg, r_out)
    x2o, y2o = pt(end_deg, r_out)
    x1i, y1i = pt(end_deg, r_in)
    x2i, y2i = pt(start_deg, r_in)
    large = 1 if (end_deg - start_deg) > 180 else 0
    return (f"M {x1o:.2f} {y1o:.2f} A {r_out} {r_out} 0 {large} 1 {x2o:.2f} {y2o:.2f} "
            f"L {x1i:.2f} {y1i:.2f} A {r_in} {r_in} 0 {large} 0 {x2i:.2f} {y2i:.2f} Z")


def _svg_donut() -> str:
    """Traffic split donut 700x220."""
    W, H = 700, 220
    cx, cy = W // 2, H // 2
    R_OUT, R_IN = 85, 52

    slices = [
        ("groot-prod (90%)",   90, "#38bdf8"),
        ("groot-canary (10%)", 10, "#C74634"),
    ]
    paths = ""
    angle = 0.0
    for label, pct, color in slices:
        sweep = pct * 360 / 100
        paths += f'<path d="{_arc_path(cx, cy, R_OUT, R_IN, angle, angle + sweep)}" fill="{color}"/>'
        angle += sweep

    total_req = sum(TRAFFIC_8H)
    center = (f'<text x="{cx}" y="{cy-8}" fill="#f1f5f9" font-size="14" text-anchor="middle" font-weight="600">{total_req:,}</text>'
              f'<text x="{cx}" y="{cy+10}" fill="#94a3b8" font-size="11" text-anchor="middle">req / 8h</text>')

    legend = ""
    lx = cx + R_OUT + 30
    for idx, (label, pct, color) in enumerate(slices):
        ly = cy - 12 + idx * 26
        legend += (f'<rect x="{lx}" y="{ly}" width="14" height="14" fill="{color}" rx="3"/>'
                   f'<text x="{lx+20}" y="{ly+11}" fill="#cbd5e1" font-size="13">{label}</text>')

    return f"""<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="#0f172a" rx="6"/>
  {paths}
  {center}
  {legend}
</svg>"""


def _svg_latency_bar() -> str:
    """Avg (solid) + p99 (faded) latency horizontal bars for active backends."""
    W, H = 700, 120
    PAD_L, PAD_R, PAD_T, PAD_B = 130, 80, 15, 20
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B

    active = [b for b in BACKENDS if b["avg_latency_ms"] is not None]
    n = len(active)
    bar_h = max(12, inner_h // n - 8)
    gap = (inner_h - bar_h * n) // (n + 1)
    max_lat = 400

    lines = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:6px;">']
    for v in [100, 200, 300, 400]:
        gx = PAD_L + v / max_lat * inner_w
        lines.append(f'<line x1="{gx:.1f}" y1="{PAD_T}" x2="{gx:.1f}" y2="{PAD_T+inner_h}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{gx:.1f}" y="{PAD_T+inner_h+14}" fill="#64748b" font-size="9" text-anchor="middle">{v}ms</text>')

    for i, b in enumerate(active):
        y = PAD_T + gap + i * (bar_h + gap)
        # p99 bar (faded)
        p99_w = b["p99_latency_ms"] / max_lat * inner_w
        lines.append(f'<rect x="{PAD_L}" y="{y}" width="{p99_w:.1f}" height="{bar_h}" fill="#38bdf8" rx="3" opacity="0.25"/>')
        # avg bar (solid)
        avg_w = b["avg_latency_ms"] / max_lat * inner_w
        color = "#C74634" if b["id"] == "groot-canary" else "#38bdf8"
        lines.append(f'<rect x="{PAD_L}" y="{y+2}" width="{avg_w:.1f}" height="{bar_h-4}" fill="{color}" rx="3" opacity="0.85"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{y+bar_h//2+4}" fill="#e2e8f0" font-size="10" text-anchor="end">{b["id"]}</text>')
        lines.append(f'<text x="{PAD_L+avg_w+5:.1f}" y="{y+bar_h//2+4}" fill="#94a3b8" font-size="9">{b["avg_latency_ms"]}ms avg / {b["p99_latency_ms"]}ms p99</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def _svg_traffic_line() -> str:
    """8h traffic history line chart."""
    W, H = 700, 160
    PAD_L, PAD_R, PAD_T, PAD_B = 50, 20, 15, 35
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B
    n = len(TRAFFIC_8H)
    max_val = max(TRAFFIC_8H)

    def cx(i): return PAD_L + i / (n - 1) * inner_w
    def cy(v): return PAD_T + inner_h - v / max_val * inner_h

    pts = " ".join(f"{cx(i):.1f},{cy(v):.1f}" for i, v in enumerate(TRAFFIC_8H))
    fill_pts = pts + f" {cx(n-1):.1f},{PAD_T+inner_h:.1f} {cx(0):.1f},{PAD_T+inner_h:.1f}"

    labels = "".join(
        f'<text x="{cx(i):.1f}" y="{PAD_T+inner_h+14}" fill="#64748b" font-size="9" text-anchor="middle">{HOURS_LABELS[i]}</text>'
        for i in range(n)
    )
    y_labels = "".join(
        f'<text x="{PAD_L-6}" y="{cy(v)+4:.1f}" fill="#64748b" font-size="9" text-anchor="end">{v}</text>'
        for v in [200, 300, 400] if v <= max_val
    )
    peak_i = TRAFFIC_8H.index(max_val)
    peak = (f'<circle cx="{cx(peak_i):.1f}" cy="{cy(max_val):.1f}" r="5" fill="#C74634"/>'
            f'<text x="{cx(peak_i):.1f}" y="{cy(max_val)-8:.1f}" fill="#C74634" font-size="9" text-anchor="middle">{max_val}</text>')

    return f"""<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">
  <defs><linearGradient id="tg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#38bdf8" stop-opacity="0.3"/><stop offset="100%" stop-color="#38bdf8" stop-opacity="0.02"/></linearGradient></defs>
  <rect width="{W}" height="{H}" fill="#0f172a" rx="6"/>
  {y_labels}
  <polygon points="{fill_pts}" fill="url(#tg)"/>
  <polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
  {labels}
  {peak}
  <text x="{PAD_L}" y="14" fill="#94a3b8" font-size="10">req/hr</text>
</svg>"""


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _status_badge(status: str) -> str:
    colors = {"ACTIVE": ("#22c55e", "#052e16"), "STANDBY": ("#f59e0b", "#1c1407"), "CRITICAL": ("#ef4444", "#2d0a0a")}
    fg, bg = colors.get(status, ("#94a3b8", "#1e293b"))
    return f'<span style="background:{bg};color:{fg};border:1px solid {fg};padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600">{status}</span>'


def _build_html() -> str:
    donut_svg = _svg_donut()
    latency_svg = _svg_latency_bar()
    traffic_svg = _svg_traffic_line()

    total_req = sum(b["req_8h"] for b in BACKENDS)
    active = sum(1 for b in BACKENDS if b["status"] == "ACTIVE")
    avg_lat = round(sum(b["avg_latency_ms"] for b in BACKENDS if b["avg_latency_ms"]) / max(1, sum(1 for b in BACKENDS if b["avg_latency_ms"])), 0)
    critical = [b for b in BACKENDS if b["status"] == "CRITICAL"]

    stat_cards = [
        ("8h Requests",    f"{total_req:,}",        "#38bdf8"),
        ("Active Backends", str(active),              "#22c55e"),
        ("Avg Latency",    f"{int(avg_lat)} ms",     "#f59e0b"),
        ("Critical",       str(len(critical)),        "#ef4444"),
    ]
    cards_html = ""
    for title, value, accent in stat_cards:
        cards_html += f"""
        <div style="background:#1e293b;border-radius:10px;padding:20px 24px;border-left:4px solid {accent};flex:1;min-width:155px">
          <div style="color:#94a3b8;font-size:13px;margin-bottom:6px">{title}</div>
          <div style="color:{accent};font-size:28px;font-weight:700">{value}</div>
        </div>"""

    alert_html = ""
    for b in critical:
        alert_html += f"""
    <div style="background:#2d0a0a;border:1px solid #ef4444;border-radius:8px;padding:12px 18px;margin-bottom:16px;display:flex;align-items:center;gap:12px">
      <span style="color:#ef4444;font-weight:700">&#9888; CRITICAL:</span>
      <span style="color:#fca5a5">{b['id']} — {b.get('alert','unknown error')}</span>
    </div>"""

    rows_html = ""
    for b in BACKENDS:
        lat_display = f"{b['avg_latency_ms']} ms" if b["avg_latency_ms"] else "—"
        err_display = f"{b['error_rate_pct']}%" if b["error_rate_pct"] is not None else "—"
        rows_html += f"""
        <tr style="border-bottom:1px solid #334155">
          <td style="padding:11px 14px;color:#38bdf8;font-family:monospace">{b['id']}</td>
          <td style="padding:11px 14px;color:#e2e8f0;font-family:monospace;font-size:12px">{b['model']}</td>
          <td style="padding:11px 14px;color:#94a3b8;text-align:center">{b['weight_pct']}%</td>
          <td style="padding:11px 14px;text-align:center">{_status_badge(b['status'])}</td>
          <td style="padding:11px 14px;color:#38bdf8;text-align:center">{lat_display}</td>
          <td style="padding:11px 14px;color:#f87171;text-align:center">{err_display}</td>
          <td style="padding:11px 14px;color:#94a3b8;text-align:right">{b['req_8h']:,}</td>
          <td style="padding:11px 14px;color:#64748b;font-size:12px">{b['region']}</td>
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
    .section-title{{color:#f1f5f9;font-size:16px;font-weight:600;margin-bottom:16px;display:flex;align-items:center;gap:8px}}
    .dot{{width:8px;height:8px;border-radius:50%;background:#C74634;display:inline-block}}
  </style>
</head>
<body>
<div style="max-width:980px;margin:0 auto;padding:32px 20px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:28px">
    <div style="display:flex;align-items:center;gap:12px">
      <div style="width:36px;height:36px;background:#C74634;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px">LB</div>
      <div>
        <div style="font-size:22px;font-weight:700;color:#f1f5f9">OCI Robot Cloud <span style="color:#C74634">{SERVICE_NAME}</span></div>
        <div style="color:#64748b;font-size:13px;margin-top:2px">GR00T N1.6-3B · 90/10 prod/canary split · Port {PORT}</div>
      </div>
    </div>
    <div style="text-align:right"><div style="color:#22c55e;font-size:13px;font-weight:600">● LIVE</div><div style="color:#64748b;font-size:12px;margin-top:2px">{now_utc}</div></div>
  </div>

  {alert_html}

  <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px">{cards_html}</div>

  <div class="section">
    <div class="section-title"><span class="dot"></span>Backend Configuration</div>
    <div style="overflow-x:auto"><table>
      <thead><tr><th>Backend</th><th>Model</th><th style="text-align:center">Weight</th><th style="text-align:center">Status</th><th style="text-align:center">Avg Latency</th><th style="text-align:center">Error Rate</th><th style="text-align:right">8h Req</th><th>Region</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table></div>
  </div>

  <div class="section">
    <div class="section-title"><span class="dot"></span>Traffic Split (8h)</div>
    <div style="overflow-x:auto">{donut_svg}</div>
  </div>

  <div class="section">
    <div class="section-title"><span class="dot"></span>Latency Comparison — avg vs p99</div>
    <div style="overflow-x:auto">{latency_svg}</div>
    <div style="color:#64748b;font-size:12px;margin-top:8px">Solid = avg latency &nbsp;|&nbsp; Faded = p99 latency</div>
  </div>

  <div class="section">
    <div class="section-title"><span class="dot"></span>8-Hour Traffic History</div>
    <div style="overflow-x:auto">{traffic_svg}</div>
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


@app.get("/backends")
def get_backends() -> JSONResponse:
    return JSONResponse(content={"backends": BACKENDS, "total": len(BACKENDS)})


@app.get("/backends/{backend_id}")
def get_backend(backend_id: str) -> JSONResponse:
    b = next((b for b in BACKENDS if b["id"] == backend_id), None)
    if b is None:
        raise HTTPException(status_code=404, detail=f"Backend '{backend_id}' not found")
    return JSONResponse(content=b)


@app.get("/traffic")
def get_traffic() -> JSONResponse:
    return JSONResponse(content={"traffic_8h": [{"label": HOURS_LABELS[i], "req": v} for i, v in enumerate(TRAFFIC_8H)], "total_8h": sum(TRAFFIC_8H), "peak_req_hr": max(TRAFFIC_8H)})


@app.get("/health")
def health() -> JSONResponse:
    critical = [b["id"] for b in BACKENDS if b["status"] == "CRITICAL"]
    return JSONResponse(content={"status": "critical" if critical else "ok", "service": SERVICE_NAME, "port": PORT, "critical_backends": critical, "timestamp": datetime.now(timezone.utc).isoformat()})


def main() -> None:
    uvicorn.run("inference_load_balancer:app", host="0.0.0.0", port=PORT, reload=False)


if __name__ == "__main__":
    main()

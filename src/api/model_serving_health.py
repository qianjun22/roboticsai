"""Model serving layer health monitor — port 8175."""

import math

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e}. Install with: pip install fastapi uvicorn") from e

app = FastAPI(title="Model Serving Health Monitor", version="1.0.0")

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

ENDPOINTS = [
    {
        "endpoint": "/predict",
        "port": 8001,
        "requests_24h": 12847,
        "success_rate": 0.998,
        "avg_latency_ms": 226,
        "p99_latency_ms": 287,
        "errors_24h": 26,
        "status": "HEALTHY",
        "sla_p99_ms": 400,
    },
    {
        "endpoint": "/predict_batch",
        "port": 8001,
        "requests_24h": 341,
        "success_rate": 0.991,
        "avg_latency_ms": 1840,
        "p99_latency_ms": 2340,
        "errors_24h": 3,
        "status": "HEALTHY",
        "sla_p99_ms": 5000,
    },
    {
        "endpoint": "/embed",
        "port": 8001,
        "requests_24h": 2341,
        "success_rate": 0.999,
        "avg_latency_ms": 48,
        "p99_latency_ms": 72,
        "errors_24h": 2,
        "status": "HEALTHY",
        "sla_p99_ms": 200,
    },
    {
        "endpoint": "/finetune",
        "port": 8002,
        "requests_24h": 12,
        "success_rate": 1.0,
        "avg_latency_ms": 14200000,
        "p99_latency_ms": 21000000,
        "errors_24h": 0,
        "status": "HEALTHY",
        "sla_p99_ms": 28800000,  # 8 hours
    },
    {
        "endpoint": "/dagger_step",
        "port": 8003,
        "requests_24h": 8420,
        "success_rate": 0.994,
        "avg_latency_ms": 312,
        "p99_latency_ms": 401,
        "errors_24h": 50,
        "status": "WARNING",
        "sla_p99_ms": 400,
    },
]

# Summary stats
TOTAL_REQUESTS = sum(e["requests_24h"] for e in ENDPOINTS)
TOTAL_ERRORS = sum(e["errors_24h"] for e in ENDPOINTS)
OVERALL_SUCCESS_RATE = round((TOTAL_REQUESTS - TOTAL_ERRORS) / TOTAL_REQUESTS, 4)
P99_WORST = max(e["p99_latency_ms"] for e in ENDPOINTS if e["endpoint"] != "/finetune")

# Colours per endpoint
EP_COLORS = ["#38bdf8", "#f59e0b", "#4ade80", "#a78bfa", "#C74634"]


# ---------------------------------------------------------------------------
# Deterministic synthetic hourly traffic (24 buckets)
# ---------------------------------------------------------------------------

def _hourly_volumes():
    """Return list of 24 dicts {hour: int, volumes: [v_per_endpoint]}"""
    # Weight curve: peaks at hours 10, 14, 17; low at 2-6
    weights = [
        0.15, 0.10, 0.06, 0.04, 0.04, 0.06, 0.20, 0.50,
        0.75, 0.90, 1.00, 0.95, 0.80, 0.85, 0.95, 0.90,
        0.80, 0.70, 0.55, 0.45, 0.35, 0.28, 0.22, 0.18,
    ]
    daily_totals = [e["requests_24h"] for e in ENDPOINTS]
    rows = []
    for h, w in enumerate(weights):
        vols = [int(d * w / sum(weights)) for d in daily_totals]
        rows.append({"hour": h, "volumes": vols})
    return rows


HOURLY = _hourly_volumes()


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _area_chart() -> str:
    """Stacked area chart — hourly request volume per endpoint, 24 h."""
    W, H = 680, 200
    pad_l, pad_r, pad_t, pad_b = 40, 10, 10, 30
    cw = W - pad_l - pad_r
    ch = H - pad_t - pad_b

    # compute stacked maxima
    stacked_max = max(sum(row["volumes"]) for row in HOURLY)

    def px(h):
        return pad_l + h / 23 * cw

    def py(v, base=0):
        return pad_t + ch - (v + base) / stacked_max * ch

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">']

    # grid
    for tick in [0, 6, 12, 18, 23]:
        x = px(tick)
        lines.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t+ch}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{H-6}" fill="#64748b" font-size="9" text-anchor="middle">{tick:02d}:00</text>')

    # draw stacked areas bottom→top (each EP layer)
    n_ep = len(ENDPOINTS)
    for ep_idx in range(n_ep - 1, -1, -1):
        # upper boundary = sum of layers 0..ep_idx
        upper_pts = []
        lower_pts = []
        for row in HOURLY:
            x = px(row["hour"])
            upper = sum(row["volumes"][: ep_idx + 1])
            lower = sum(row["volumes"][: ep_idx])
            upper_pts.append((x, py(upper)))
            lower_pts.append((x, py(lower)))
        path_d = (
            f"M {upper_pts[0][0]:.1f} {upper_pts[0][1]:.1f} "
            + " ".join(f"L {x:.1f} {y:.1f}" for x, y in upper_pts[1:])
            + " "
            + " ".join(f"L {x:.1f} {y:.1f}" for x, y in reversed(lower_pts))
            + " Z"
        )
        color = EP_COLORS[ep_idx]
        lines.append(f'<path d="{path_d}" fill="{color}" opacity="0.55"/>')
        # top stroke
        stroke_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in upper_pts)
        lines.append(f'<polyline points="{stroke_pts}" fill="none" stroke="{color}" stroke-width="1.5"/>')

    # legend
    lx = pad_l + 4
    for i, ep in enumerate(ENDPOINTS):
        lines.append(f'<rect x="{lx + i*120}" y="{pad_t+4}" width="10" height="10" fill="{EP_COLORS[i]}" rx="2" opacity="0.8"/>')
        lines.append(f'<text x="{lx + i*120 + 13}" y="{pad_t+13}" fill="#94a3b8" font-size="9">{ep["endpoint"]}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def _error_rate_bars() -> str:
    """Bar chart: error rate per endpoint; SLA line at 1%."""
    W, H = 680, 160
    pad_l, pad_r, pad_t, pad_b = 110, 20, 10, 30
    cw = W - pad_l - pad_r
    ch = H - pad_t - pad_b

    error_rates = [
        round(e["errors_24h"] / e["requests_24h"] * 100, 3)
        for e in ENDPOINTS
    ]
    max_rate = max(max(error_rates) * 1.3, 1.5)
    bar_w = cw / len(ENDPOINTS) * 0.6
    gap = cw / len(ENDPOINTS)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">']

    # y-axis ticks
    for tick in [0.0, 0.5, 1.0, 1.5]:
        if tick > max_rate:
            break
        y = pad_t + ch - (tick / max_rate) * ch
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{W-pad_r}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{y+4:.1f}" fill="#64748b" font-size="9" text-anchor="end">{tick}%</text>')

    # SLA line at 1%
    sla_y = pad_t + ch - (1.0 / max_rate) * ch
    lines.append(f'<line x1="{pad_l}" y1="{sla_y:.1f}" x2="{W-pad_r}" y2="{sla_y:.1f}" stroke="#C74634" stroke-width="1.5" stroke-dasharray="5 3"/>')
    lines.append(f'<text x="{W-pad_r-2}" y="{sla_y-4:.1f}" fill="#C74634" font-size="9" text-anchor="end">SLA 1%</text>')

    for i, (ep, rate) in enumerate(zip(ENDPOINTS, error_rates)):
        x = pad_l + (i + 0.2) * gap
        bh = (rate / max_rate) * ch
        y = pad_t + ch - bh
        color = "#f59e0b" if ep["status"] == "WARNING" else EP_COLORS[i]
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" rx="2" opacity="0.85"/>')
        # label
        cx_bar = x + bar_w / 2
        lines.append(f'<text x="{cx_bar:.1f}" y="{pad_t+ch+14}" fill="#64748b" font-size="9" text-anchor="middle">{ep["endpoint"]}</text>')
        lines.append(f'<text x="{cx_bar:.1f}" y="{y-4:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{rate}%</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    area_svg = _area_chart()
    err_svg = _error_rate_bars()

    def status_badge(s):
        color = "#4ade80" if s == "HEALTHY" else "#f59e0b"
        return f'<span style="background:{color}22;color:{color};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">{s}</span>'

    def fmt_latency(ms):
        if ms >= 3600000:
            return f"{ms/3600000:.1f}h"
        if ms >= 60000:
            return f"{ms/60000:.1f}m"
        return f"{ms}ms"

    ep_rows = "".join(
        f"""<tr style="border-bottom:1px solid #1e293b">
          <td style="padding:8px 12px;color:#38bdf8;font-family:monospace">{e['endpoint']}</td>
          <td style="padding:8px 12px;color:#64748b">{e['port']}</td>
          <td style="padding:8px 12px;color:#e2e8f0">{e['requests_24h']:,}</td>
          <td style="padding:8px 12px;color:#4ade80">{e['success_rate']*100:.1f}%</td>
          <td style="padding:8px 12px;color:#94a3b8">{fmt_latency(e['avg_latency_ms'])}</td>
          <td style="padding:8px 12px;color:#{'f59e0b' if e['p99_latency_ms'] > e['sla_p99_ms'] else 'e2e8f0'}">{fmt_latency(e['p99_latency_ms'])}</td>
          <td style="padding:8px 12px;color:#f87171">{e['errors_24h']}</td>
          <td style="padding:8px 12px">{status_badge(e['status'])}</td>
        </tr>"""
        for e in ENDPOINTS
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Model Serving Health — Port 8175</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
    h1{{color:#C74634;font-size:22px;margin-bottom:4px}}
    .sub{{color:#64748b;font-size:13px;margin-bottom:24px}}
    .stat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}}
    .card{{background:#1e293b;border-radius:8px;padding:16px;border-left:3px solid #C74634}}
    .card-val{{font-size:24px;font-weight:700;color:#38bdf8}}
    .card-lbl{{font-size:12px;color:#64748b;margin-top:4px}}
    .section{{margin-bottom:24px}}
    .section-title{{color:#94a3b8;font-size:13px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px}}
    table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
    th{{padding:10px 12px;color:#64748b;font-size:12px;text-align:left;background:#0f172a;text-transform:uppercase}}
    .warn-box{{background:#f59e0b11;border:1px solid #f59e0b44;border-radius:8px;padding:12px 16px;color:#f59e0b;font-size:13px}}
  </style>
</head>
<body>
  <h1>Model Serving Health Monitor</h1>
  <div class="sub">OCI Robot Cloud · Port 8175 · All inference endpoints · 24h rolling window</div>

  <div class="stat-grid">
    <div class="card"><div class="card-val">{TOTAL_REQUESTS:,}</div><div class="card-lbl">Total requests (24h)</div></div>
    <div class="card"><div class="card-val" style="color:#4ade80">{OVERALL_SUCCESS_RATE*100:.2f}%</div><div class="card-lbl">Overall success rate</div></div>
    <div class="card"><div class="card-val" style="color:#f87171">{TOTAL_ERRORS}</div><div class="card-lbl">Total errors (24h)</div></div>
    <div class="card"><div class="card-val" style="color:#f59e0b">{P99_WORST}ms</div><div class="card-lbl">P99 worst (excl. finetune)</div></div>
  </div>

  <div class="section">
    <div class="section-title">Hourly Request Volume — Stacked by Endpoint</div>
    {area_svg}
  </div>

  <div class="section">
    <div class="section-title">Error Rate by Endpoint (SLA: 1%)</div>
    {err_svg}
  </div>

  <div class="section">
    <div class="section-title">Endpoint Status Table</div>
    <table>
      <thead><tr>
        <th>Endpoint</th><th>Port</th><th>Requests 24h</th><th>Success</th>
        <th>Avg Latency</th><th>P99 Latency</th><th>Errors</th><th>Status</th>
      </tr></thead>
      <tbody>{ep_rows}</tbody>
    </table>
  </div>

  {'<div class="section"><div class="warn-box">⚠ WARNING: /dagger_step p99 latency 401ms exceeds SLA of 400ms. Investigate OCI A100 scheduling delays or chunked action buffer overflow.</div></div>' if any(e['status']=='WARNING' for e in ENDPOINTS) else ''}
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/endpoints")
def get_endpoints():
    return JSONResponse(content=ENDPOINTS)


@app.get("/summary")
def get_summary():
    return JSONResponse(content={
        "total_requests_24h": TOTAL_REQUESTS,
        "total_errors_24h": TOTAL_ERRORS,
        "overall_success_rate": OVERALL_SUCCESS_RATE,
        "p99_worst_ms": P99_WORST,
        "endpoints_healthy": sum(1 for e in ENDPOINTS if e["status"] == "HEALTHY"),
        "endpoints_warning": sum(1 for e in ENDPOINTS if e["status"] == "WARNING"),
        "endpoints_total": len(ENDPOINTS),
    })


@app.get("/alerts")
def get_alerts():
    alerts = []
    for ep in ENDPOINTS:
        if ep["p99_latency_ms"] > ep["sla_p99_ms"]:
            alerts.append({
                "endpoint": ep["endpoint"],
                "issue": "p99_latency_exceeds_sla",
                "p99_latency_ms": ep["p99_latency_ms"],
                "sla_p99_ms": ep["sla_p99_ms"],
                "overage_ms": ep["p99_latency_ms"] - ep["sla_p99_ms"],
            })
        if ep["success_rate"] < 0.99:
            alerts.append({
                "endpoint": ep["endpoint"],
                "issue": "success_rate_below_99pct",
                "success_rate": ep["success_rate"],
            })
    return JSONResponse(content={"alerts": alerts, "count": len(alerts)})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8175)

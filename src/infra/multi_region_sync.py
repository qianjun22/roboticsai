"""Multi-region model and data synchronization monitor — port 8170."""

import math
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

REGIONS = ["ashburn", "phoenix", "frankfurt"]

SYNC_STATUS = [
    {
        "pair": "ashburn→phoenix",
        "src": "ashburn",
        "dst": "phoenix",
        "model_sync": "CURRENT",
        "model_lag_min": 0,
        "data_sync": "CURRENT",
        "data_lag_min": 2,
        "last_sync": "2026-03-30T15:42Z",
        "bytes_transferred_24h_gb": 2.4,
        "throughput_mbps": 28.4,
        "backbone": "100G",
        "backbone_utilized_pct": 0.2,
    },
    {
        "pair": "ashburn→frankfurt",
        "src": "ashburn",
        "dst": "frankfurt",
        "model_sync": "CURRENT",
        "model_lag_min": 0,
        "data_sync": "LAG",
        "data_lag_min": 8.2,
        "sla_min": 5,
        "last_sync": "2026-03-30T15:34Z",
        "bytes_transferred_24h_gb": 1.8,
        "throughput_mbps": 21.7,
        "backbone": "100G",
        "backbone_utilized_pct": 0.17,
    },
    {
        "pair": "phoenix→ashburn",
        "src": "phoenix",
        "dst": "ashburn",
        "model_sync": "N/A",
        "model_lag_min": None,
        "data_sync": "CURRENT",
        "data_lag_min": 1,
        "last_sync": "2026-03-30T15:41Z",
        "bytes_transferred_24h_gb": 0.4,
        "throughput_mbps": None,
        "backbone": "100G",
        "backbone_utilized_pct": 0.03,
        "note": "eval results back-sync",
    },
]

# 7-day p99 lag history (minutes) for each region pair
# index 0 = 7 days ago, index 6 = today
LAG_HISTORY = {
    "ashburn→phoenix": [1.8, 2.1, 1.9, 2.4, 2.0, 1.7, 2.0],
    "ashburn→frankfurt": [2.2, 3.1, 2.8, 12.0, 3.4, 4.1, 8.2],
}

# Daily bytes transferred (GB) per pair over 7 days
TRANSFERS_HISTORY = {
    "ashburn→phoenix": [2.1, 2.3, 2.0, 2.5, 2.2, 2.4, 2.4],
    "ashburn→frankfurt": [1.6, 1.7, 1.5, 1.9, 1.7, 1.8, 1.8],
    "phoenix→ashburn": [0.3, 0.4, 0.3, 0.5, 0.4, 0.4, 0.4],
}

SLA_LAG_MIN = 5  # minutes


# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _lag_area_chart() -> str:
    """680×200 SVG area chart: 7-day p99 lag for phx and fra."""
    W, H = 680, 200
    pad_l, pad_r, pad_t, pad_b = 48, 16, 20, 36
    cw = W - pad_l - pad_r
    ch = H - pad_t - pad_b
    days = 7
    max_lag = 14.0  # y-axis ceiling

    phx = LAG_HISTORY["ashburn→phoenix"]
    fra = LAG_HISTORY["ashburn→frankfurt"]

    def x(i):
        return pad_l + i * cw / (days - 1)

    def y(v):
        return pad_t + ch - (v / max_lag) * ch

    def poly(series, close=True):
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(series))
        if close:
            pts += f" {x(days-1):.1f},{y(0):.1f} {x(0):.1f},{y(0):.1f}"
        return pts

    # SLA line y-coord
    sla_y = y(SLA_LAG_MIN)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">')

    # Y-axis grid + labels
    for tick in [0, 2, 4, 6, 8, 10, 12, 14]:
        ty = y(tick)
        lines.append(f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{W-pad_r}" y2="{ty:.1f}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{ty+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="9" font-family="monospace">{tick}</text>')

    # X-axis labels
    day_labels = ["D-6", "D-5", "D-4", "D-3", "D-2", "D-1", "Today"]
    for i, lbl in enumerate(day_labels):
        lx = x(i)
        lines.append(f'<text x="{lx:.1f}" y="{H-6}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{lbl}</text>')

    # PHX area (sky blue, semi-transparent)
    lines.append(f'<polygon points="{poly(phx)}" fill="#38bdf8" fill-opacity="0.18" stroke="none"/>')
    pts_phx = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(phx))
    lines.append(f'<polyline points="{pts_phx}" fill="none" stroke="#38bdf8" stroke-width="2"/>')

    # FRA area (amber, semi-transparent)
    lines.append(f'<polygon points="{poly(fra)}" fill="#f59e0b" fill-opacity="0.18" stroke="none"/>')
    pts_fra = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(fra))
    lines.append(f'<polyline points="{pts_fra}" fill="none" stroke="#f59e0b" stroke-width="2"/>')

    # Highlight day 4 spike (index 3) for fra
    spike_x = x(3)
    spike_y = y(fra[3])
    lines.append(f'<circle cx="{spike_x:.1f}" cy="{spike_y:.1f}" r="5" fill="#ef4444" stroke="#0f172a" stroke-width="1.5"/>')
    lines.append(f'<text x="{spike_x+6:.1f}" y="{spike_y-4:.1f}" fill="#ef4444" font-size="9" font-family="monospace">12.0m spike</text>')

    # SLA dashed line
    lines.append(f'<line x1="{pad_l}" y1="{sla_y:.1f}" x2="{W-pad_r}" y2="{sla_y:.1f}" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="6,3"/>')
    lines.append(f'<text x="{W-pad_r-2}" y="{sla_y-4:.1f}" text-anchor="end" fill="#ef4444" font-size="9" font-family="monospace">SLA 5min</text>')

    # Legend
    lines.append(f'<rect x="{pad_l}" y="{pad_t}" width="10" height="8" fill="#38bdf8" fill-opacity="0.7"/>')
    lines.append(f'<text x="{pad_l+14}" y="{pad_t+8}" fill="#38bdf8" font-size="9" font-family="monospace">ashburn→phoenix</text>')
    lines.append(f'<rect x="{pad_l+110}" y="{pad_t}" width="10" height="8" fill="#f59e0b" fill-opacity="0.7"/>')
    lines.append(f'<text x="{pad_l+124}" y="{pad_t+8}" fill="#f59e0b" font-size="9" font-family="monospace">ashburn→frankfurt</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def _transfer_bar_chart() -> str:
    """680×160 SVG grouped bar chart: daily data transferred per pair."""
    W, H = 680, 160
    pad_l, pad_r, pad_t, pad_b = 48, 16, 20, 36
    cw = W - pad_l - pad_r
    ch = H - pad_t - pad_b
    days = 7
    max_gb = 3.0

    pairs = ["ashburn→phoenix", "ashburn→frankfurt", "phoenix→ashburn"]
    colors = ["#38bdf8", "#f59e0b", "#a78bfa"]
    data = [TRANSFERS_HISTORY[p] for p in pairs]

    group_w = cw / days
    bar_w = group_w / (len(pairs) + 1)

    def bx(day, pair_idx):
        return pad_l + day * group_w + (pair_idx + 0.5) * bar_w

    def by(v):
        return pad_t + ch - (v / max_gb) * ch

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">')

    # Grid
    for tick in [0, 1, 2, 3]:
        ty = by(tick)
        lines.append(f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{W-pad_r}" y2="{ty:.1f}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{ty+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="9" font-family="monospace">{tick}GB</text>')

    # X labels
    day_labels = ["D-6", "D-5", "D-4", "D-3", "D-2", "D-1", "Today"]
    for i, lbl in enumerate(day_labels):
        lx = pad_l + i * group_w + group_w / 2
        lines.append(f'<text x="{lx:.1f}" y="{H-6}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{lbl}</text>')

    # Bars
    for pi, (pair, color, series) in enumerate(zip(pairs, colors, data)):
        total = sum(series)
        for di, val in enumerate(series):
            bx_v = bx(di, pi)
            by_top = by(val)
            bh = (val / max_gb) * ch
            lines.append(f'<rect x="{bx_v-bar_w/2:.1f}" y="{by_top:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" fill-opacity="0.8" rx="2"/>')
        # Total label on last bar
        last_bx = bx(days - 1, pi)
        lines.append(f'<text x="{last_bx:.1f}" y="{pad_t+10+(pi*11)}" text-anchor="middle" fill="{color}" font-size="8" font-family="monospace">{total:.1f}GB</text>')

    # Legend
    lx = pad_l
    for color, pair in zip(colors, pairs):
        label = pair.split('→')[1]
        lines.append(f'<rect x="{lx}" y="{pad_t}" width="8" height="8" fill="{color}" fill-opacity="0.8"/>')
        lines.append(f'<text x="{lx+11}" y="{pad_t+8}" fill="{color}" font-size="9" font-family="monospace">{label}</text>')
        lx += 90

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    lag_svg = _lag_area_chart()
    bar_svg = _transfer_bar_chart()

    breach = any(s.get("data_sync") == "LAG" for s in SYNC_STATUS)
    breach_html = ""
    if breach:
        breach_html = '''
        <div style="background:#7f1d1d;border:1px solid #ef4444;border-radius:8px;padding:12px 16px;margin-bottom:24px;display:flex;align-items:center;gap:12px">
          <span style="font-size:20px">&#x26A0;&#xFE0F;</span>
          <span style="color:#fca5a5;font-size:14px;font-weight:600">BREACH: ashburn&#x2192;frankfurt data_sync LAG 8.2min exceeds SLA 5min</span>
        </div>'''

    status_rows = ""
    for s in SYNC_STATUS:
        msync_color = "#38bdf8" if s["model_sync"] == "CURRENT" else ("#94a3b8" if s["model_sync"] == "N/A" else "#ef4444")
        dsync_color = "#38bdf8" if s["data_sync"] == "CURRENT" else "#ef4444"
        lag_str = f"{s['data_lag_min']}min" if s['data_lag_min'] is not None else "-"
        sla_str = f" (SLA {s['sla_min']}min)" if 'sla_min' in s else ""
        note_str = f" <span style='color:#64748b;font-size:11px'>({s.get('note','')})</span>" if 'note' in s else ""
        tp = f"{s['throughput_mbps']} MBps" if s['throughput_mbps'] else "-"
        status_rows += f'''
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 12px;color:#e2e8f0;font-size:13px">{s['pair']}{note_str}</td>
            <td style="padding:10px 12px;text-align:center"><span style="color:{msync_color};font-size:12px;font-weight:600">{s['model_sync']}</span></td>
            <td style="padding:10px 12px;text-align:center"><span style="color:{dsync_color};font-size:12px;font-weight:600">{s['data_sync']}</span></td>
            <td style="padding:10px 12px;text-align:center;color:#cbd5e1;font-size:12px">{lag_str}{sla_str}</td>
            <td style="padding:10px 12px;text-align:center;color:#94a3b8;font-size:12px">{s['bytes_transferred_24h_gb']} GB</td>
            <td style="padding:10px 12px;text-align:center;color:#94a3b8;font-size:12px">{tp}</td>
            <td style="padding:10px 12px;text-align:center;color:#64748b;font-size:11px">{s['last_sync']}</td>
          </tr>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Multi-Region Sync Monitor — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 32px; }}
    h1 {{ font-size: 22px; font-weight: 700; color: #f1f5f9; }}
    h2 {{ font-size: 15px; font-weight: 600; color: #94a3b8; margin: 24px 0 12px; text-transform: uppercase; letter-spacing: .06em; }}
    .badge {{ display:inline-block; background:#C74634; color:#fff; font-size:11px; font-weight:700; padding:2px 8px; border-radius:4px; margin-left:8px; vertical-align:middle; }}
    table {{ width:100%; border-collapse:collapse; background:#0f1e33; border-radius:8px; overflow:hidden; }}
    th {{ padding:10px 12px; text-align:left; color:#64748b; font-size:11px; text-transform:uppercase; letter-spacing:.06em; background:#0a1628; }}
    tr:hover td {{ background:#132035; }}
    .card {{ background:#0f1e33; border-radius:8px; padding:20px; margin-bottom:24px; }}
    .stat-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-bottom:24px; }}
    .stat {{ background:#0f1e33; border-radius:8px; padding:16px; text-align:center; }}
    .stat-val {{ font-size:26px; font-weight:700; color:#38bdf8; }}
    .stat-label {{ font-size:11px; color:#64748b; margin-top:4px; text-transform:uppercase; letter-spacing:.05em; }}
  </style>
</head>
<body>
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px">
    <div>
      <span style="color:#C74634;font-weight:700;font-size:13px;letter-spacing:.08em">OCI ROBOT CLOUD</span>
      <h1>Multi-Region Sync Monitor <span class="badge">PORT 8170</span></h1>
    </div>
    <div style="color:#64748b;font-size:12px">{datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ")}</div>
  </div>

  {breach_html}

  <div class="stat-grid">
    <div class="stat"><div class="stat-val">3</div><div class="stat-label">Regions</div></div>
    <div class="stat"><div class="stat-val" style="color:#ef4444">1</div><div class="stat-label">SLA Breaches</div></div>
    <div class="stat"><div class="stat-val">4.6 GB</div><div class="stat-label">Total Transferred 24h</div></div>
  </div>

  <h2>Sync Status</h2>
  <table>
    <thead><tr>
      <th>Pair</th><th>Model Sync</th><th>Data Sync</th><th>Lag</th><th>24h Bytes</th><th>Throughput</th><th>Last Sync</th>
    </tr></thead>
    <tbody>{status_rows}</tbody>
  </table>

  <h2>7-Day Sync Lag (p99, minutes)</h2>
  <div class="card" style="padding:16px">{lag_svg}</div>

  <h2>Daily Data Transferred (GB)</h2>
  <div class="card" style="padding:16px">{bar_svg}</div>

  <h2>Backbone Utilization</h2>
  <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:16px">
    <div class="stat"><div class="stat-val">28.4 MBps</div><div class="stat-label">ashburn&#x2192;phoenix avg</div></div>
    <div class="stat"><div class="stat-val">21.7 MBps</div><div class="stat-label">ashburn&#x2192;frankfurt avg</div></div>
  </div>
  <p style="color:#64748b;font-size:11px;margin-top:12px">100G backbone — peak utilization &lt;0.2%</p>
</body>
</html>'''


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Multi-Region Sync Monitor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _dashboard_html()

    @app.get("/status")
    def status():
        return JSONResponse({"regions": REGIONS, "sync": SYNC_STATUS})

    @app.get("/history")
    def history():
        return JSONResponse({"lag_p99_7day": LAG_HISTORY, "sla_min": SLA_LAG_MIN})

    @app.get("/transfers")
    def transfers():
        return JSONResponse({"daily_gb_7day": TRANSFERS_HISTORY})

if __name__ == "__main__":
    if FastAPI is None:
        raise RuntimeError("fastapi not installed — run: pip install fastapi uvicorn")
    uvicorn.run("multi_region_sync:app", host="0.0.0.0", port=8170, reload=False)

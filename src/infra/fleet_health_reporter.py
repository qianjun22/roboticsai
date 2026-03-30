"""\nFleet Health Reporter — OCI Robot Cloud multi-region deployment\nPort: 8122\n"""

import json
from datetime import datetime

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    raise ImportError("fastapi and uvicorn are required: pip install fastapi uvicorn")

app = FastAPI(title="Fleet Health Reporter", version="1.0.0")

# ---------------------------------------------------------------------------
# Static fleet data
# ---------------------------------------------------------------------------
NODES = [
    {
        "name": "ashburn-prod-1",
        "status": "HEALTHY",
        "gpu": "A100_80GB",
        "latency_ms": 226,
        "success_rate": 71,
        "uptime_pct": 99.94,
        "incidents": 0,
        "incident_reason": None,
    },
    {
        "name": "ashburn-canary-1",
        "status": "HEALTHY",
        "gpu": "A100_80GB",
        "latency_ms": 228,
        "success_rate": 78,
        "uptime_pct": 99.91,
        "incidents": 0,
        "incident_reason": None,
    },
    {
        "name": "phoenix-eval-1",
        "status": "DEGRADED",
        "gpu": "A100_40GB",
        "latency_ms": 241,
        "success_rate": 65,
        "uptime_pct": 98.7,
        "incidents": 2,
        "incident_reason": "Elevated latency; eval workload contention",
    },
    {
        "name": "frankfurt-staging-1",
        "status": "HEALTHY",
        "gpu": "A100_40GB",
        "latency_ms": 258,
        "success_rate": 71,
        "uptime_pct": 99.82,
        "incidents": 1,
        "incident_reason": "Brief network partition 2026-03-28 02:14 UTC",
    },
    {
        "name": "ashburn-shadow-1",
        "status": "CRITICAL",
        "gpu": "A100_80GB",
        "latency_ms": 312,
        "success_rate": 45,
        "uptime_pct": 95.2,
        "incidents": 5,
        "incident_reason": "Config drift: chunk_size=8 vs golden 16",
    },
]

FLEET_SCORE = 98.7  # weighted avg uptime
FLEET_STATUS = "DEGRADED"  # due to shadow node

STATUS_COLOR = {
    "HEALTHY": "#22c55e",
    "DEGRADED": "#f59e0b",
    "CRITICAL": "#ef4444",
}

STATUS_BG = {
    "HEALTHY": "#14532d",
    "DEGRADED": "#451a03",
    "CRITICAL": "#450a0a",
}


# ---------------------------------------------------------------------------
# SVG fleet map
# ---------------------------------------------------------------------------
def build_fleet_svg() -> str:
    """5 node boxes in a 3-2 grid (700x200), colored by status."""
    W, H = 700, 200
    box_w, box_h = 180, 72
    gap_x, gap_y = 20, 20

    # Row 0: nodes 0,1,2 — Row 1: nodes 3,4 (centered)
    positions = []
    # Row 0 — x offsets for 3 boxes with gap
    row0_total = 3 * box_w + 2 * gap_x
    row0_start = (W - row0_total) // 2
    for i in range(3):
        x = row0_start + i * (box_w + gap_x)
        y = 10
        positions.append((x, y))
    # Row 1 — x offsets for 2 boxes centered
    row1_total = 2 * box_w + gap_x
    row1_start = (W - row1_total) // 2
    for i in range(2):
        x = row1_start + i * (box_w + gap_x)
        y = 10 + box_h + gap_y
        positions.append((x, y))

    rects = []
    for idx, node in enumerate(NODES):
        x, y = positions[idx]
        color = STATUS_COLOR[node["status"]]
        bg = STATUS_BG[node["status"]]
        rects.append(f"""
  <rect x="{x}" y="{y}" width="{box_w}" height="{box_h}"
        rx="6" ry="6" fill="{bg}" stroke="{color}" stroke-width="2"/>
  <text x="{x + box_w//2}" y="{y + 16}" text-anchor="middle"
        font-size="10" font-weight="bold" fill="{color}" font-family="monospace">{node['name']}</text>
  <text x="{x + box_w//2}" y="{y + 30}" text-anchor="middle"
        font-size="9" fill="#94a3b8" font-family="monospace">{node['gpu']}</text>
  <text x="{x + box_w//2}" y="{y + 44}" text-anchor="middle"
        font-size="9" fill="#e2e8f0" font-family="monospace">{node['latency_ms']}ms | SR {node['success_rate']}%</text>
  <text x="{x + box_w//2}" y="{y + 57}" text-anchor="middle"
        font-size="9" fill="#94a3b8" font-family="monospace">uptime {node['uptime_pct']}% | inc {node['incidents']}</text>
  <text x="{x + box_w//2}" y="{y + 69}" text-anchor="middle"
        font-size="9" font-weight="bold" fill="{color}" font-family="monospace">{node['status']}</text>""")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">
{''.join(rects)}
</svg>"""


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
def build_dashboard() -> str:
    fleet_color = STATUS_COLOR[FLEET_STATUS]
    fleet_bg = STATUS_BG[FLEET_STATUS]

    node_cards = []
    for node in NODES:
        color = STATUS_COLOR[node["status"]]
        bg = STATUS_BG[node["status"]]
        incident_html = (
            f'<div style="margin-top:6px;font-size:11px;color:#fca5a5">'
            f'Incident: {node["incident_reason"]}</div>'
            if node["incident_reason"]
            else ""
        )
        node_cards.append(f"""
      <div style="background:{bg};border:1px solid {color};border-radius:8px;padding:16px;min-width:220px">
        <div style="font-size:13px;font-weight:700;color:{color};font-family:monospace">{node['name']}</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:2px">{node['gpu']}</div>
        <div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:6px">
          <div style="background:#0f172a;border-radius:4px;padding:6px;text-align:center">
            <div style="font-size:18px;font-weight:700;color:#38bdf8">{node['latency_ms']}ms</div>
            <div style="font-size:10px;color:#64748b">latency</div>
          </div>
          <div style="background:#0f172a;border-radius:4px;padding:6px;text-align:center">
            <div style="font-size:18px;font-weight:700;color:#a78bfa">{node['success_rate']}%</div>
            <div style="font-size:10px;color:#64748b">success rate</div>
          </div>
          <div style="background:#0f172a;border-radius:4px;padding:6px;text-align:center">
            <div style="font-size:18px;font-weight:700;color:#34d399">{node['uptime_pct']}%</div>
            <div style="font-size:10px;color:#64748b">uptime</div>
          </div>
          <div style="background:#0f172a;border-radius:4px;padding:6px;text-align:center">
            <div style="font-size:18px;font-weight:700;color:{'#ef4444' if node['incidents'] > 0 else '#22c55e'}">{node['incidents']}</div>
            <div style="font-size:10px;color:#64748b">incidents</div>
          </div>
        </div>
        {incident_html}
      </div>""")

    incident_rows = []
    for node in NODES:
        if node["incidents"] > 0:
            color = STATUS_COLOR[node["status"]]
            incident_rows.append(f"""
        <tr>
          <td style="padding:8px 12px;font-family:monospace;font-size:12px;color:{color}">{node['name']}</td>
          <td style="padding:8px 12px;font-size:12px;color:{color}">{node['status']}</td>
          <td style="padding:8px 12px;font-size:12px;color:#94a3b8">{node['incidents']}</td>
          <td style="padding:8px 12px;font-size:12px;color:#e2e8f0">{node['incident_reason']}</td>
        </tr>""")

    svg = build_fleet_svg()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Fleet Health Reporter | OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }}
    .header {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-bottom: 1px solid #1e3a5f; padding: 20px 32px; display: flex; align-items: center; justify-content: space-between; }}
    .header-title {{ font-size: 20px; font-weight: 700; color: #38bdf8; letter-spacing: 0.5px; }}
    .header-sub {{ font-size: 12px; color: #64748b; margin-top: 2px; }}
    .oracle-badge {{ background: #C74634; color: #fff; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 4px; letter-spacing: 0.5px; }}
    .main {{ padding: 24px 32px; max-width: 1200px; margin: 0 auto; }}
    .section-title {{ font-size: 13px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; margin-top: 28px; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }}
    thead tr {{ background: #0f172a; }}
    th {{ padding: 10px 12px; text-align: left; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }}
    tbody tr:hover {{ background: #263548; }}
    .footer {{ text-align: center; font-size: 11px; color: #475569; padding: 28px 0 16px; border-top: 1px solid #1e293b; margin-top: 40px; }}
    .ts {{ font-size: 11px; color: #475569; }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <div class="header-title">Fleet Health Reporter</div>
      <div class="header-sub">OCI Robot Cloud — Multi-Region Deployment | Port 8122</div>
    </div>
    <div style="display:flex;align-items:center;gap:12px">
      <span class="ts">Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</span>
      <span class="oracle-badge">ORACLE CONFIDENTIAL</span>
    </div>
  </div>

  <div class="main">

    <!-- Fleet Score Banner -->
    <div class="section-title">Fleet Score</div>
    <div style="background:{fleet_bg};border:2px solid {fleet_color};border-radius:10px;padding:20px 28px;display:flex;align-items:center;gap:32px">
      <div style="text-align:center">
        <div style="font-size:48px;font-weight:800;color:{fleet_color}">{FLEET_SCORE}%</div>
        <div style="font-size:12px;color:#94a3b8;margin-top:2px">Weighted Avg Uptime</div>
      </div>
      <div style="flex:1">
        <div style="font-size:18px;font-weight:700;color:{fleet_color}">{FLEET_STATUS}</div>
        <div style="font-size:13px;color:#94a3b8;margin-top:4px">5 nodes reporting &nbsp;|&nbsp; 1 critical, 1 degraded, 3 healthy</div>
        <div style="font-size:12px;color:#fca5a5;margin-top:6px">Root cause: ashburn-shadow-1 config drift (chunk_size=8 vs golden 16)</div>
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">
        {''.join(f'<div style="display:flex;align-items:center;gap:6px"><span style="width:10px;height:10px;border-radius:50%;background:{STATUS_COLOR[s]};display:inline-block"></span><span style="font-size:12px;color:#94a3b8">{s}: {sum(1 for n in NODES if n["status"]==s)}</span></div>' for s in ["HEALTHY","DEGRADED","CRITICAL"])}
      </div>
    </div>

    <!-- Node Cards -->
    <div class="section-title">Node Status</div>
    <div style="display:flex;flex-wrap:wrap;gap:14px">
      {''.join(node_cards)}
    </div>

    <!-- Fleet Map SVG -->
    <div class="section-title">Fleet Map</div>
    <div style="overflow-x:auto">
      {svg}
    </div>

    <!-- Incident Log -->
    <div class="section-title">Incident Log</div>
    <table>
      <thead>
        <tr>
          <th>Node</th><th>Status</th><th>Incidents</th><th>Reason</th>
        </tr>
      </thead>
      <tbody>
        {''.join(incident_rows) if incident_rows else '<tr><td colspan="4" style="padding:16px 12px;text-align:center;color:#64748b">No incidents recorded</td></tr>'}
      </tbody>
    </table>

    <!-- All Nodes Table -->
    <div class="section-title">All Nodes</div>
    <table>
      <thead>
        <tr>
          <th>Name</th><th>Status</th><th>GPU</th><th>Latency</th><th>Success Rate</th><th>Uptime</th><th>Incidents</th>
        </tr>
      </thead>
      <tbody>
        {''.join(f"""<tr>
          <td style="padding:8px 12px;font-family:monospace;font-size:12px;color:#38bdf8">{n['name']}</td>
          <td style="padding:8px 12px"><span style="background:{STATUS_BG[n['status']]};color:{STATUS_COLOR[n['status']]};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">{n['status']}</span></td>
          <td style="padding:8px 12px;font-size:12px;color:#94a3b8">{n['gpu']}</td>
          <td style="padding:8px 12px;font-size:12px;color:#38bdf8">{n['latency_ms']}ms</td>
          <td style="padding:8px 12px;font-size:12px;color:#a78bfa">{n['success_rate']}%</td>
          <td style="padding:8px 12px;font-size:12px;color:#34d399">{n['uptime_pct']}%</td>
          <td style="padding:8px 12px;font-size:12px;color:{'#ef4444' if n['incidents']>0 else '#22c55e'}">{n['incidents']}</td>
        </tr>""" for n in NODES)}
      </tbody>
    </table>

  </div>

  <div class="footer">
    Oracle Confidential | OCI Robot Cloud Fleet Health Reporter | Port 8122
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=build_dashboard())


@app.get("/nodes")
async def get_nodes():
    return JSONResponse(content={"nodes": NODES, "count": len(NODES)})


@app.get("/nodes/{name}")
async def get_node(name: str):
    for node in NODES:
        if node["name"] == name:
            return JSONResponse(content=node)
    raise HTTPException(status_code=404, detail=f"Node '{name}' not found")


@app.get("/fleet-score")
async def fleet_score():
    return JSONResponse(content={
        "fleet_score_pct": FLEET_SCORE,
        "fleet_status": FLEET_STATUS,
        "node_count": len(NODES),
        "healthy": sum(1 for n in NODES if n["status"] == "HEALTHY"),
        "degraded": sum(1 for n in NODES if n["status"] == "DEGRADED"),
        "critical": sum(1 for n in NODES if n["status"] == "CRITICAL"),
        "total_incidents": sum(n["incidents"] for n in NODES),
    })


@app.get("/health")
async def health():
    return JSONResponse(content={
        "status": "ok",
        "service": "fleet_health_reporter",
        "port": 8122,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    try:
        uvicorn.run(app, host="0.0.0.0", port=8122, log_level="info")
    except Exception as exc:
        print(f"[fleet_health_reporter] Failed to start: {exc}")
        raise


if __name__ == "__main__":
    main()

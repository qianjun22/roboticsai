"""Fleet Commander — OCI Robot Cloud master command & control dashboard (port 8155)."""

import math
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e}. Run: pip install fastapi uvicorn pydantic") from e

app = FastAPI(title="Fleet Commander", version="1.0.0")

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

FLEET_SUMMARY = {
    "total_nodes": 4,
    "node_breakdown": {"A100_80GB": 2, "A100_40GB": 2},
    "total_gpu_memory_gb": 240,
    "active_jobs": 3,
    "active_job_names": ["fine_tune", "hpo", "eval"],
    "queued_jobs": 4,
    "services_healthy": 13,
    "services_total": 15,
    "degraded_services": ["fleet_health_reporter", "network_topology"],
    "monthly_cost_usd": 3182.84,
    "uptime_30d_pct": 99.94,
}

COMMAND_HISTORY = [
    {"ts": "2026-03-30T14:00Z", "cmd": "launch_eval",      "target": "eval_server:8121",             "status": "SUCCESS", "user": "jun.q"},
    {"ts": "2026-03-30T10:22Z", "cmd": "restart_service",  "target": "inference_server:8001",        "status": "SUCCESS", "user": "jun.q"},
    {"ts": "2026-03-29T09:11Z", "cmd": "scale_up",         "target": "ashburn-prod-1",               "status": "SUCCESS", "user": "autoscaler"},
    {"ts": "2026-03-28T16:44Z", "cmd": "rollback",          "target": "model_serving:groot_finetune_v2", "status": "SUCCESS", "user": "jun.q"},
    {"ts": "2026-03-27T11:30Z", "cmd": "clear_cache",       "target": "inference_cache:8104",         "status": "FAILED",  "user": "jun.q",   "error": "timeout 30s"},
]

HEALTH_SCORES = [
    {"category": "compute",  "score": 94},
    {"category": "training", "score": 87},
    {"category": "eval",     "score": 91},
    {"category": "infra",    "score": 82},
    {"category": "data",     "score": 96},
]

# 15 known service ports with health
SERVICES_MAP = [
    {"name": "inference_server",      "port": 8001, "health": "OK"},
    {"name": "data_collection_api",   "port": 8003, "health": "OK"},
    {"name": "pipeline_orchestrator", "port": 8080, "health": "OK"},
    {"name": "groot_inference",       "port": 8001, "health": "OK"},
    {"name": "hpo_search",            "port": 8021, "health": "OK"},
    {"name": "training_monitor",      "port": 8022, "health": "OK"},
    {"name": "model_registry",        "port": 8076, "health": "OK"},
    {"name": "inference_scheduler",   "port": 8077, "health": "OK"},
    {"name": "multi_region_failover", "port": 8078, "health": "OK"},
    {"name": "drift_detector",        "port": 8087, "health": "OK"},
    {"name": "online_eval",           "port": 8089, "health": "OK"},
    {"name": "eval_server",           "port": 8121, "health": "OK"},
    {"name": "cost_optimizer",        "port": 8090, "health": "OK"},
    {"name": "fleet_health_reporter", "port": 8154, "health": "DEGRADED"},
    {"name": "network_topology",      "port": 8155, "health": "DEGRADED"},
]

# In-memory command log (extended by POST /command)
_command_log = list(COMMAND_HISTORY)

# ---------------------------------------------------------------------------
# SVG: health scorecard 680x160
# ---------------------------------------------------------------------------

def _health_scorecard_svg() -> str:
    w, h = 680, 160
    items = HEALTH_SCORES
    n = len(items)
    cell_w = w / n

    def gauge_color(score):
        if score >= 90:
            return "#22c55e"
        if score >= 70:
            return "#f59e0b"
        return "#ef4444"

    gauges = ""
    for i, item in enumerate(items):
        cx = cell_w * i + cell_w / 2
        cy = 80
        r = 46
        score = item["score"]
        color = gauge_color(score)

        # Arc: 180-degree semicircle (left-to-right, bottom flat)
        # We'll draw a full circle progress ring (270 degrees)
        circumference = 2 * math.pi * r
        # Use 75% of circle (270 deg) as the gauge arc
        arc_len = circumference * 0.75
        progress = arc_len * (score / 100)
        # Rotate start: -225 deg so arc starts bottom-left
        rotation = -225

        gauges += (
            f'<circle cx="{cx:.1f}" cy="{cy}" r="{r}" fill="none" stroke="#1e293b" stroke-width="10"/>'
            f'<circle cx="{cx:.1f}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="10"'
            f' stroke-dasharray="{progress:.2f} {circumference:.2f}"'
            f' stroke-dashoffset="0"'
            f' transform="rotate({rotation} {cx:.1f} {cy})"/>'
            f'<text x="{cx:.1f}" y="{cy+5}" fill="{color}" font-size="18" font-weight="800" text-anchor="middle">{score}</text>'
            f'<text x="{cx:.1f}" y="{cy+22}" fill="#64748b" font-size="10" text-anchor="middle">{item["category"].upper()}</text>'
        )

    return f'''<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{w}" height="{h}" fill="#0f172a" rx="8"/>
  {gauges}
  <text x="{w//2}" y="{h-8}" fill="#334155" font-size="9" text-anchor="middle">green ≥90 · amber 70-89 · red &lt;70</text>
</svg>'''


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    scorecard_svg = _health_scorecard_svg()

    # Fleet summary cards
    healthy_pct = round(FLEET_SUMMARY["services_healthy"] / FLEET_SUMMARY["services_total"] * 100, 1)

    # Command history table rows
    cmd_rows = ""
    for cmd in reversed(_command_log):
        s_color = "#22c55e" if cmd["status"] == "SUCCESS" else "#ef4444"
        error_cell = f"<span style='color:#f87171;font-size:11px'>{cmd.get('error','')}</span>" if cmd.get("error") else ""
        cmd_rows += f"""
        <tr>
          <td style='padding:9px 12px;color:#64748b;font-size:12px'>{cmd['ts']}</td>
          <td style='padding:9px 12px;color:#38bdf8;font-weight:600'>{cmd['cmd']}</td>
          <td style='padding:9px 12px;color:#94a3b8'>{cmd['target']}</td>
          <td style='padding:9px 12px;color:#94a3b8'>{cmd['user']}</td>
          <td style='padding:9px 12px'>
            <span style='background:{s_color}22;color:{s_color};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700'>{cmd['status']}</span>
            {error_cell}
          </td>
        </tr>"""

    # Services map
    svc_cells = ""
    for svc in SERVICES_MAP:
        dot_color = "#22c55e" if svc["health"] == "OK" else "#f59e0b"
        svc_cells += f"""
          <div style='background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;
                      display:flex;align-items:center;gap:8px;min-width:200px'>
            <div style='width:8px;height:8px;background:{dot_color};border-radius:50%;flex-shrink:0'></div>
            <div>
              <div style='color:#e2e8f0;font-size:12px;font-weight:600'>{svc['name']}</div>
              <div style='color:#475569;font-size:11px'>:{svc['port']} · {svc['health']}</div>
            </div>
          </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Fleet Commander — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }}
    .header {{ background: linear-gradient(135deg,#1e293b,#0f172a); border-bottom: 1px solid #1e293b;
               padding: 18px 32px; display: flex; align-items: center; gap: 16px; }}
    .header .logo {{ width: 28px; height: 28px; background: #C74634; border-radius: 6px;
                    display: flex; align-items: center; justify-content: center; font-weight: 900;
                    color: #fff; font-size: 14px; }}
    .header h1 {{ font-size: 20px; font-weight: 700; }}
    .header .sub {{ color: #64748b; font-size: 13px; margin-top: 2px; }}
    .badge-ok {{ background: #22c55e22; color: #22c55e; padding: 2px 10px; border-radius: 12px;
                 font-size: 11px; font-weight: 700; margin-left: 12px; }}
    .content {{ padding: 28px 32px; }}
    .kpi-row {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }}
    .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
            padding: 18px 24px; flex: 1; min-width: 160px; }}
    .kpi .val {{ font-size: 26px; font-weight: 800; color: #38bdf8; }}
    .kpi .lbl {{ color: #64748b; font-size: 12px; margin-top: 4px; }}
    .section-title {{ font-size: 15px; font-weight: 700; color: #94a3b8; margin-bottom: 14px;
                      text-transform: uppercase; letter-spacing: .06em; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
             padding: 20px; margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    tr:nth-child(even) {{ background: #ffffff06; }}
    th {{ padding: 9px 12px; text-align: left; color: #64748b; font-size: 11px;
          text-transform: uppercase; letter-spacing: .06em; border-bottom: 1px solid #334155; }}
    .svc-grid {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .quick-actions {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }}
    .qa-btn {{ background: #C7463422; border: 1px solid #C74634; color: #C74634;
               padding: 8px 18px; border-radius: 8px; font-size: 13px; font-weight: 600;
               cursor: pointer; font-family: inherit; }}
    .qa-btn:hover {{ background: #C7463444; }}
  </style>
</head>
<body>
<div class="header">
  <div class="logo">FC</div>
  <div>
    <h1>Fleet Commander <span class="badge-ok">OPERATIONAL</span></h1>
    <div class="sub">OCI Robot Cloud · Master Command &amp; Control · Port 8155</div>
  </div>
</div>
<div class="content">
  <div class="kpi-row">
    <div class="kpi"><div class="val">4</div><div class="lbl">Total Nodes (2×80GB + 2×40GB)</div></div>
    <div class="kpi"><div class="val">240 GB</div><div class="lbl">Total GPU Memory</div></div>
    <div class="kpi"><div class="val" style="color:#22c55e">3</div><div class="lbl">Active Jobs</div></div>
    <div class="kpi"><div class="val" style="color:#f59e0b">4</div><div class="lbl">Queued Jobs</div></div>
    <div class="kpi"><div class="val">{FLEET_SUMMARY['services_healthy']}/{FLEET_SUMMARY['services_total']}</div><div class="lbl">Services Healthy ({healthy_pct}%)</div></div>
    <div class="kpi"><div class="val" style="color:#22c55e">{FLEET_SUMMARY['uptime_30d_pct']}%</div><div class="lbl">30-Day Uptime</div></div>
    <div class="kpi"><div class="val" style="color:#f59e0b">${FLEET_SUMMARY['monthly_cost_usd']:,.2f}</div><div class="lbl">Monthly Cost</div></div>
  </div>

  <div class="card">
    <div class="section-title">Fleet Health Scorecard</div>
    {scorecard_svg}
  </div>

  <div class="section-title">Quick Actions</div>
  <div class="quick-actions">
    <button class="qa-btn" onclick="postCmd('launch_eval','eval_server:8121')">&#9654; Launch Eval</button>
    <button class="qa-btn" onclick="postCmd('scale_up','ashburn-prod-1')">&#9650; Scale Up</button>
    <button class="qa-btn" onclick="postCmd('clear_cache','inference_cache:8104')">&#10005; Clear Cache</button>
    <button class="qa-btn" onclick="postCmd('restart_service','inference_server:8001')">&#8635; Restart Service</button>
  </div>

  <div class="card">
    <div class="section-title">Command History</div>
    <table>
      <thead><tr><th>Timestamp</th><th>Command</th><th>Target</th><th>User</th><th>Status</th></tr></thead>
      <tbody id="cmd-body">{cmd_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <div class="section-title">Services Map — {len(SERVICES_MAP)} Services</div>
    <div class="svc-grid">{svc_cells}</div>
  </div>
</div>
<script>
async function postCmd(cmd, target) {{
  const res = await fetch('/command', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{cmd, target, user: 'jun.q'}})
  }});
  const data = await res.json();
  alert(data.message || JSON.stringify(data));
  location.reload();
}}
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/summary")
async def get_summary():
    return JSONResponse(content=FLEET_SUMMARY)


@app.get("/commands")
async def get_commands():
    return JSONResponse(content={"commands": list(reversed(_command_log)), "total": len(_command_log)})


@app.get("/health-matrix")
async def get_health_matrix():
    return JSONResponse(content={
        "scores": HEALTH_SCORES,
        "services": SERVICES_MAP,
        "overall_pct": round(sum(s["score"] for s in HEALTH_SCORES) / len(HEALTH_SCORES), 1),
    })


class CommandRequest(BaseModel):
    cmd: str
    target: str
    user: str = "api"


VALID_COMMANDS = {"launch_eval", "scale_up", "clear_cache", "restart_service"}


@app.post("/command")
async def issue_command(req: CommandRequest):
    if req.cmd not in VALID_COMMANDS:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unknown command '{req.cmd}'. Valid: {sorted(VALID_COMMANDS)}"},
        )
    entry = {
        "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"),
        "cmd": req.cmd,
        "target": req.target,
        "status": "SUCCESS",
        "user": req.user,
    }
    _command_log.append(entry)
    return JSONResponse(content={"message": f"Command '{req.cmd}' dispatched to {req.target}", "entry": entry})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8155)

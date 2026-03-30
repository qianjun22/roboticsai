"""GPU Autoscaler Service — OCI Robot Cloud, port 8135.

Monitors GPU node fleet, evaluates scaling rules, and recommends actions.
"""

import math
from typing import Dict, Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:  # pragma: no cover
    FastAPI = None
    HTMLResponse = JSONResponse = None
    uvicorn = None

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

FLEET: Dict[str, Dict[str, Any]] = {
    "ashburn-prod-1": {
        "util_pct": 87, "mem_used_gb": 68.2, "mem_total_gb": 80,
        "jobs": 3, "status": "HEALTHY", "region": "ashburn",
    },
    "ashburn-canary-1": {
        "util_pct": 72, "mem_used_gb": 51.4, "mem_total_gb": 80,
        "jobs": 2, "status": "HEALTHY", "region": "ashburn",
    },
    "phoenix-eval-1": {
        "util_pct": 45, "mem_used_gb": 18.6, "mem_total_gb": 40,
        "jobs": 1, "status": "DEGRADED", "region": "phoenix",
    },
    "frankfurt-staging-1": {
        "util_pct": 31, "mem_used_gb": 12.4, "mem_total_gb": 40,
        "jobs": 1, "status": "HEALTHY", "region": "frankfurt",
    },
}

RULES = [
    {
        "id": "scale_up_high_util",
        "description": "Trigger if any node util > 85% for 10 min → provision new A100_80GB",
        "trigger": "any_node_util > 85% for 10min",
        "action": "provision A100_80GB",
        "est_duration_min": 8,
        "cost_delta_hr": 3.06,
        "enabled": True,
    },
    {
        "id": "scale_up_queue_depth",
        "description": "Trigger if training queue depth > 5 → provision A100_80GB",
        "trigger": "queue_depth > 5",
        "action": "provision A100_80GB",
        "est_duration_min": 8,
        "cost_delta_hr": 3.06,
        "enabled": True,
    },
    {
        "id": "scale_down_idle",
        "description": "Trigger if node util < 20% for 60 min → deprovision node (save $3.06/hr)",
        "trigger": "any_node_util < 20% for 60min",
        "action": "deprovision node",
        "est_duration_min": 3,
        "cost_delta_hr": -3.06,
        "enabled": True,
    },
    {
        "id": "rebalance",
        "description": "Trigger if util variance > 0.3 → migrate jobs to balance",
        "trigger": "util_variance > 0.3",
        "action": "migrate jobs",
        "est_duration_min": 2,
        "cost_delta_hr": 0.0,
        "enabled": True,
    },
]

EVENTS = [
    {"timestamp": "2026-02-03T08:14:00Z", "rule": "scale_up_high_util",
     "action": "provisioned", "node": "ashburn-prod-1", "cost_delta": +3.06, "duration_min": 9},
    {"timestamp": "2026-02-11T14:30:00Z", "rule": "scale_down_idle",
     "action": "deprovisioned", "node": "frankfurt-staging-1", "cost_delta": -3.06, "duration_min": 3},
    {"timestamp": "2026-02-18T11:05:00Z", "rule": "rebalance",
     "action": "migrated jobs", "node": "ashburn-canary-1", "cost_delta": 0.0, "duration_min": 2},
    {"timestamp": "2026-02-24T17:52:00Z", "rule": "scale_up_queue_depth",
     "action": "provisioned", "node": "phoenix-eval-1", "cost_delta": +3.06, "duration_min": 8},
    {"timestamp": "2026-03-02T06:00:00Z", "rule": "scale_down_idle",
     "action": "deprovisioned", "node": "phoenix-eval-1", "cost_delta": -3.06, "duration_min": 4},
    {"timestamp": "2026-03-10T09:22:00Z", "rule": "scale_up_high_util",
     "action": "provisioned", "node": "ashburn-prod-1", "cost_delta": +3.06, "duration_min": 8},
    {"timestamp": "2026-03-19T15:44:00Z", "rule": "rebalance",
     "action": "migrated jobs", "node": "ashburn-canary-1", "cost_delta": 0.0, "duration_min": 2},
    {"timestamp": "2026-03-27T20:01:00Z", "rule": "scale_down_idle",
     "action": "deprovisioned", "node": "frankfurt-staging-1", "cost_delta": -3.06, "duration_min": 3},
]

# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def _fleet_avg_util() -> float:
    utils = [n["util_pct"] for n in FLEET.values()]
    return sum(utils) / len(utils)

def _util_variance() -> float:
    utils = [n["util_pct"] / 100.0 for n in FLEET.values()]
    mean = sum(utils) / len(utils)
    return sum((u - mean) ** 2 for u in utils) / len(utils)

def _monthly_cost() -> float:
    # Rough: 4 nodes, mixed A100 40GB ($2.06/hr) and 80GB ($3.06/hr), 730hr/mo
    cost = 0.0
    for node in FLEET.values():
        rate = 3.06 if node["mem_total_gb"] == 80 else 2.06
        cost += rate * 730
    return round(cost, 2)

def _estimated_savings_monthly() -> float:
    # Based on scale_down events: avg 3 per month * 3.06/hr * 24hr * ~4.7 days avg
    return round(3 * 3.06 * 24 * 1.92, 2)  # ~420

# ---------------------------------------------------------------------------
# Rule evaluator
# ---------------------------------------------------------------------------

def _evaluate_rules() -> list:
    recommendations = []
    utils = {name: data["util_pct"] for name, data in FLEET.items()}
    variance = _util_variance()

    # scale_up_high_util
    high_nodes = [n for n, u in utils.items() if u > 85]
    if high_nodes:
        recommendations.append({
            "rule": "scale_up_high_util",
            "triggered": True,
            "reason": f"Nodes above 85%: {', '.join(high_nodes)}",
            "recommended_action": "provision new A100_80GB node in ashburn",
            "estimated_cost_delta_hr": +3.06,
            "priority": "HIGH",
        })

    # rebalance
    if variance > 0.08:  # 0.3 in fractional terms ~= 0.09 variance
        recommendations.append({
            "rule": "rebalance",
            "triggered": True,
            "reason": f"Util variance {variance:.3f} exceeds threshold",
            "recommended_action": "migrate 1 job from ashburn-prod-1 to frankfurt-staging-1",
            "estimated_cost_delta_hr": 0.0,
            "priority": "MEDIUM",
        })

    # scale_down_idle
    idle_nodes = [n for n, u in utils.items() if u < 20]
    for node in idle_nodes:
        recommendations.append({
            "rule": "scale_down_idle",
            "triggered": True,
            "reason": f"{node} util {utils[node]}% < 20% threshold",
            "recommended_action": f"deprovision {node}",
            "estimated_cost_delta_hr": -3.06,
            "priority": "LOW",
        })

    if not recommendations:
        recommendations.append({
            "rule": "none",
            "triggered": False,
            "reason": "All fleet metrics within normal bounds",
            "recommended_action": "no action required",
            "priority": "NONE",
        })

    return recommendations


# ---------------------------------------------------------------------------
# SVG charts
# ---------------------------------------------------------------------------

def _heatmap_svg() -> str:
    """680x140 fleet utilization heatmap."""
    W, H = 680, 140
    nodes = list(FLEET.items())
    n = len(nodes)
    cell_w = (W - 40) / n
    cell_h = 80
    pad_x, pad_y = 20, 30

    lines = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    lines.append(f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>')
    lines.append(f'<text x="{W//2}" y="18" fill="#94a3b8" font-size="11" text-anchor="middle" font-family="sans-serif">Fleet GPU Utilization Heatmap</text>')

    for i, (name, data) in enumerate(nodes):
        u = data["util_pct"]
        x = pad_x + i * cell_w
        y = pad_y
        if u >= 80:
            color = "#C74634"
        elif u >= 50:
            color = "#d97706"
        else:
            color = "#16a34a"

        # status dim for DEGRADED
        opacity = "0.65" if data["status"] == "DEGRADED" else "1"
        lines.append(f'<rect x="{x:.1f}" y="{y}" width="{cell_w-4:.1f}" height="{cell_h}" fill="{color}" fill-opacity="{opacity}" rx="6"/>')
        # util label
        cx = x + cell_w / 2 - 2
        lines.append(f'<text x="{cx:.1f}" y="{y+38}" fill="white" font-size="20" font-weight="bold" text-anchor="middle" font-family="monospace">{u}%</text>')
        # node name
        short = name.split("-")[0] + "\u200b-" + name.split("-")[1] + "\u200b-" + name.split("-")[2] if name.count("-") >= 2 else name
        lines.append(f'<text x="{cx:.1f}" y="{y+54}" fill="#f1f5f9" font-size="8" text-anchor="middle" font-family="monospace">{name}</text>')
        # status badge
        badge_color = "#ef4444" if data["status"] == "DEGRADED" else "#22c55e"
        lines.append(f'<text x="{cx:.1f}" y="{y+68}" fill="{badge_color}" font-size="8" text-anchor="middle" font-family="monospace">{data["status"]}</text>')

    # legend
    lx = 30
    for label, col in [("<50% OK", "#16a34a"), ("50-80% WARN", "#d97706"), (">80% CRIT", "#C74634")]:
        lines.append(f'<rect x="{lx}" y="{H-14}" width="10" height="10" fill="{col}" rx="2"/>')
        lines.append(f'<text x="{lx+14}" y="{H-5}" fill="#94a3b8" font-size="9" font-family="sans-serif">{label}</text>')
        lx += 110
    lines.append("</svg>")
    return "\n".join(lines)


def _timeline_svg() -> str:
    """680x160 scaling events timeline."""
    W, H = 680, 160
    node_list = list(FLEET.keys())
    n_nodes = len(node_list)
    row_h = (H - 30) / n_nodes
    pad_x = 20
    chart_w = W - 2 * pad_x

    # Time range: Feb 1 – Mar 31 2026 (59 days)
    t_start = 1738368000  # 2026-02-01 UTC approx
    t_end = 1743379200    # 2026-03-31 UTC approx
    t_span = t_end - t_start

    def ts_to_x(ts_str: str) -> float:
        # Parse YYYY-MM-DDTHH:MM:SSZ manually
        parts = ts_str.rstrip("Z").split("T")
        d = parts[0].split("-")
        t = parts[1].split(":")
        days = (int(d[0]) - 2026) * 365 + (int(d[1]) - 1) * 30 + (int(d[2]) - 1)
        secs = int(t[0]) * 3600 + int(t[1]) * 60
        epoch_approx = 1738368000 + days * 86400 + secs
        frac = max(0.0, min(1.0, (epoch_approx - t_start) / t_span))
        return pad_x + frac * chart_w

    lines = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    lines.append(f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>')
    lines.append(f'<text x="{W//2}" y="14" fill="#94a3b8" font-size="11" text-anchor="middle" font-family="sans-serif">Scaling Events Timeline (Feb–Mar 2026)</text>')

    for i, node in enumerate(node_list):
        row_y = 22 + i * row_h
        cy = row_y + row_h / 2
        # Lane
        lines.append(f'<line x1="{pad_x}" y1="{cy:.1f}" x2="{W-pad_x}" y2="{cy:.1f}" stroke="#1e3a5f" stroke-width="1.5"/>')
        lines.append(f'<text x="{pad_x+2}" y="{cy-5:.1f}" fill="#475569" font-size="8" font-family="monospace">{node}</text>')

    # Event markers
    for ev in EVENTS:
        node = ev["node"]
        if node not in node_list:
            continue
        i = node_list.index(node)
        row_y = 22 + i * row_h
        cy = row_y + row_h / 2
        ex = ts_to_x(ev["timestamp"])
        rule = ev["rule"]

        if "scale_up" in rule:
            # Triangle up
            color = "#38bdf8"
            pts = f"{ex:.1f},{cy-9:.1f} {ex-6:.1f},{cy+5:.1f} {ex+6:.1f},{cy+5:.1f}"
            lines.append(f'<polygon points="{pts}" fill="{color}"/>')
        elif "scale_down" in rule:
            # Triangle down
            color = "#C74634"
            pts = f"{ex:.1f},{cy+9:.1f} {ex-6:.1f},{cy-5:.1f} {ex+6:.1f},{cy-5:.1f}"
            lines.append(f'<polygon points="{pts}" fill="{color}"/>')
        elif rule == "rebalance":
            # Circle
            color = "#a78bfa"
            lines.append(f'<circle cx="{ex:.1f}" cy="{cy:.1f}" r="6" fill="{color}"/>')

    # Legend
    lx = W // 2 - 120
    ly = H - 8
    for (label, shape, color) in [
        ("scale_up", "up", "#38bdf8"),
        ("scale_down", "down", "#C74634"),
        ("rebalance", "circle", "#a78bfa"),
    ]:
        if shape == "up":
            pts = f"{lx+5},{ly-9} {lx-1},{ly+1} {lx+11},{ly+1}"
            lines.append(f'<polygon points="{pts}" fill="{color}"/>')
        elif shape == "down":
            pts = f"{lx+5},{ly+1} {lx-1},{ly-9} {lx+11},{ly-9}"
            lines.append(f'<polygon points="{pts}" fill="{color}"/>')
        else:
            lines.append(f'<circle cx="{lx+5}" cy="{ly-4}" r="5" fill="{color}"/>')
        lines.append(f'<text x="{lx+16}" y="{ly}" fill="#94a3b8" font-size="9" font-family="sans-serif">{label}</text>')
        lx += 90

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html_dashboard() -> str:
    heatmap = _heatmap_svg()
    timeline = _timeline_svg()
    avg_util = _fleet_avg_util()
    monthly_cost = _monthly_cost()
    savings = _estimated_savings_monthly()
    n_rules = len(RULES)

    stat_cards = ""
    for label, value, color in [
        ("Fleet Avg Util", f"{avg_util:.1f}%", "#38bdf8"),
        ("Monthly Projected Cost", f"${monthly_cost:,.0f}", "#C74634"),
        ("Est. Scale-Down Savings", f"${savings:,.0f}/mo", "#22c55e"),
        ("Active Rules", str(n_rules), "#a78bfa"),
    ]:
        stat_cards += f"""
        <div class="stat-card">
          <div class="stat-val" style="color:{color}">{value}</div>
          <div class="stat-label">{label}</div>
        </div>"""

    node_rows = ""
    for name, d in FLEET.items():
        status_color = "#ef4444" if d["status"] == "DEGRADED" else "#22c55e"
        mem_pct = round(d["mem_used_gb"] / d["mem_total_gb"] * 100)
        node_rows += f"""
        <tr>
          <td style="font-family:monospace">{name}</td>
          <td style="color:#38bdf8">{d['region']}</td>
          <td>{d['util_pct']}%</td>
          <td>{d['mem_used_gb']}/{d['mem_total_gb']} GB ({mem_pct}%)</td>
          <td>{d['jobs']}</td>
          <td style="color:{status_color}">{d['status']}</td>
        </tr>"""

    rule_rows = ""
    for r in RULES:
        rule_rows += f"""
        <tr>
          <td style="color:#38bdf8;font-family:monospace">{r['id']}</td>
          <td style="font-size:11px">{r['trigger']}</td>
          <td>{r['action']}</td>
          <td>~{r['est_duration_min']} min</td>
          <td style="color:{'#22c55e' if r['cost_delta_hr'] <= 0 else '#ef4444'}">${r['cost_delta_hr']:+.2f}/hr</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>OCI Robot Cloud — GPU Autoscaler</title>
  <style>
    body {{ margin:0; padding:0; background:#0f172a; color:#e2e8f0; font-family:sans-serif; }}
    h1 {{ color:#C74634; text-align:center; padding:24px 0 4px; font-size:22px; letter-spacing:1px; }}
    .subtitle {{ text-align:center; color:#64748b; font-size:12px; margin-bottom:16px; }}
    .stats {{ display:flex; justify-content:center; gap:16px; padding:0 20px 16px; flex-wrap:wrap; }}
    .stat-card {{ background:#0f2340; border:1px solid #1e3a5f; border-radius:8px;
                  padding:14px 24px; text-align:center; min-width:140px; }}
    .stat-val {{ font-size:26px; font-weight:700; font-family:monospace; }}
    .stat-label {{ font-size:11px; color:#64748b; margin-top:4px; }}
    .charts {{ display:flex; flex-wrap:wrap; justify-content:center; gap:16px; padding:0 20px 16px; }}
    .card {{ background:#0f2340; border:1px solid #1e3a5f; border-radius:8px; padding:12px; }}
    h2 {{ color:#38bdf8; font-size:14px; text-transform:uppercase; letter-spacing:1px; padding:12px 20px 4px; }}
    table {{ width:100%; border-collapse:collapse; max-width:800px; margin:0 auto; }}
    th {{ background:#0f2340; color:#38bdf8; font-size:11px; text-transform:uppercase;
          padding:8px 10px; text-align:left; border-bottom:1px solid #1e3a5f; }}
    td {{ padding:7px 10px; font-size:12px; border-bottom:1px solid #1e293b; }}
    tr:hover td {{ background:#1e293b; }}
    .section {{ padding:0 20px 16px; }}
    .footer {{ text-align:center; color:#334155; font-size:10px; padding:12px; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — GPU Autoscaler</h1>
  <p class="subtitle">Port 8135 &bull; 4 nodes &bull; 4 scaling rules &bull; 2026-03-30</p>

  <div class="stats">{stat_cards}</div>

  <div class="charts">
    <div class="card">{heatmap}</div>
    <div class="card">{timeline}</div>
  </div>

  <h2>Fleet Nodes</h2>
  <div class="section">
    <table>
      <thead><tr><th>Node</th><th>Region</th><th>GPU Util</th><th>Memory</th><th>Jobs</th><th>Status</th></tr></thead>
      <tbody>{node_rows}</tbody>
    </table>
  </div>

  <h2>Scaling Rules</h2>
  <div class="section">
    <table>
      <thead><tr><th>Rule ID</th><th>Trigger</th><th>Action</th><th>Est. Time</th><th>Cost Delta</th></tr></thead>
      <tbody>{rule_rows}</tbody>
    </table>
  </div>

  <p class="footer">OCI Robot Cloud &bull; GPU Autoscaler &bull;
    <a href="/fleet" style="color:#38bdf8">/fleet</a> &bull;
    <a href="/rules" style="color:#38bdf8">/rules</a> &bull;
    <a href="/evaluate" style="color:#C74634">/evaluate (POST)</a>
  </p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="GPU Autoscaler", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _html_dashboard()

    @app.get("/fleet")
    def fleet():
        return JSONResponse(content={
            "nodes": FLEET,
            "summary": {
                "avg_util_pct": round(_fleet_avg_util(), 1),
                "util_variance": round(_util_variance(), 4),
                "monthly_cost_usd": _monthly_cost(),
                "estimated_savings_monthly_usd": _estimated_savings_monthly(),
            },
        })

    @app.get("/rules")
    def rules():
        return JSONResponse(content={"rules": RULES, "active_count": len(RULES)})

    @app.post("/evaluate")
    def evaluate():
        recs = _evaluate_rules()
        return JSONResponse(content={
            "evaluated_at": "2026-03-30T00:00:00Z",
            "fleet_snapshot": {
                name: {"util_pct": d["util_pct"], "status": d["status"]}
                for name, d in FLEET.items()
            },
            "recommendations": recs,
            "triggered_count": sum(1 for r in recs if r.get("triggered")),
        })


if __name__ == "__main__":
    if uvicorn is None:
        raise SystemExit("uvicorn not installed — run: pip install fastapi uvicorn")
    uvicorn.run("autoscaler:app", host="0.0.0.0", port=8135, reload=True)

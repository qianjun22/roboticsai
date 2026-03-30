try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    raise ImportError("fastapi and uvicorn are required: pip install fastapi uvicorn")

from datetime import datetime

app = FastAPI(title="OCI Robot Cloud — GPU Utilization Tracker", version="1.0.0")

GPU_NODES = [
    {"name": "ashburn-prod-1", "gpu_type": "A100_80GB", "region": "ashburn", "role": "prod", "status": "HEALTHY", "util_history": [87, 91, 89, 94, 88, 92, 90, 87], "mem_history": [72, 78, 75, 82, 71, 79, 76, 73], "temp_history": [67, 69, 68, 71, 66, 70, 68, 67]},
    {"name": "ashburn-canary-1", "gpu_type": "A100_80GB", "region": "ashburn", "role": "canary", "status": "HEALTHY", "util_history": [45, 52, 48, 61, 43, 55, 49, 46], "mem_history": [38, 44, 41, 52, 37, 46, 42, 39], "temp_history": [58, 61, 59, 63, 57, 62, 60, 58]},
    {"name": "phoenix-eval-1", "gpu_type": "A100_40GB", "region": "phoenix", "role": "eval", "status": "HEALTHY", "util_history": [23, 31, 27, 35, 22, 29, 25, 24], "mem_history": [55, 58, 56, 61, 54, 59, 57, 55], "temp_history": [54, 56, 55, 58, 53, 57, 55, 54]},
    {"name": "frankfurt-staging-1", "gpu_type": "A100_40GB", "region": "frankfurt", "role": "staging", "status": "HEALTHY", "util_history": [71, 75, 73, 79, 70, 76, 72, 71], "mem_history": [61, 65, 63, 68, 60, 66, 62, 61], "temp_history": [63, 65, 64, 67, 62, 66, 64, 63]},
    {"name": "ashburn-shadow-1", "gpu_type": "A100_80GB", "region": "ashburn", "role": "shadow", "status": "DEGRADED", "status_reason": "low util due to config drift", "util_history": [12, 8, 15, 11, 9, 13, 10, 11], "mem_history": [22, 20, 25, 21, 19, 23, 20, 21], "temp_history": [47, 45, 48, 46, 44, 47, 45, 46]},
]

NODE_COLORS = ["#38bdf8", "#C74634", "#22c55e", "#a855f7", "#f59e0b"]
HOURS_LABELS = ["8h ago", "7h ago", "6h ago", "5h ago", "4h ago", "3h ago", "2h ago", "1h ago"]


def _avg(lst):
    return round(sum(lst) / len(lst), 1)


def _util_color(pct: int) -> str:
    if pct > 80: return "#f97316"
    if pct >= 40: return "#22c55e"
    return "#64748b"


def _build_line_chart_svg() -> str:
    W, H = 700, 200
    PAD_L, PAD_R, PAD_T, PAD_B = 45, 160, 15, 35
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B
    n_points = 8

    def x_pos(i):
        return PAD_L + i / (n_points - 1) * inner_w

    def y_pos(val):
        return PAD_T + inner_h - val / 100 * inner_h

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">',
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{PAD_L}" y1="{PAD_T+inner_h}" x2="{PAD_L+inner_w}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
    ]
    for v in (20, 40, 60, 80, 100):
        gy = y_pos(v)
        lines.append(f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{PAD_L+inner_w}" y2="{gy:.1f}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{gy+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{v}%</text>')
    for i, label in enumerate(HOURS_LABELS):
        lx = x_pos(i)
        lines.append(f'<text x="{lx:.1f}" y="{PAD_T+inner_h+14}" fill="#64748b" font-size="9" text-anchor="middle">{label}</text>')
    for ni, node in enumerate(GPU_NODES):
        color = NODE_COLORS[ni]
        pts = node["util_history"]
        coords = [(x_pos(i), y_pos(pts[i])) for i in range(n_points)]
        d = " ".join(f"{'M' if i == 0 else 'L'}{cx:.1f},{cy:.1f}" for i, (cx, cy) in enumerate(coords))
        lines.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" opacity="0.9"/>')
        for cx, cy in coords:
            lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="{color}"/>')
    lx = PAD_L + inner_w + 12
    lines.append(f'<text x="{lx}" y="{PAD_T+10}" fill="#64748b" font-size="10" font-weight="600">Nodes</text>')
    for ni, node in enumerate(GPU_NODES):
        color = NODE_COLORS[ni]
        ly = PAD_T + 24 + ni * 20
        short_name = node["name"].replace("ashburn-", "ash-").replace("frankfurt-", "fra-").replace("phoenix-", "phx-")
        lines.append(f'<rect x="{lx}" y="{ly-8}" width="16" height="3" fill="{color}" rx="1"/>')
        lines.append(f'<text x="{lx+20}" y="{ly}" fill="#94a3b8" font-size="10">{short_name}</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def _build_bar_chart_svg() -> str:
    W, H = 700, 160
    PAD_L, PAD_R, PAD_T, PAD_B = 165, 20, 15, 30
    inner_w = W - PAD_L - PAD_R
    inner_h = H - PAD_T - PAD_B
    n = len(GPU_NODES)
    bar_h = max(14, inner_h // n - 8)
    gap = (inner_h - bar_h * n) // (n + 1)
    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">',
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{PAD_L}" y1="{PAD_T+inner_h}" x2="{PAD_L+inner_w}" y2="{PAD_T+inner_h}" stroke="#475569" stroke-width="1"/>',
    ]
    for v in (20, 40, 60, 80, 100):
        gx = PAD_L + v / 100 * inner_w
        lines.append(f'<line x1="{gx:.1f}" y1="{PAD_T}" x2="{gx:.1f}" y2="{PAD_T+inner_h}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{gx:.1f}" y="{PAD_T+inner_h+14}" fill="#64748b" font-size="10" text-anchor="middle">{v}%</text>')
    for i, node in enumerate(GPU_NODES):
        current_util = node["util_history"][-1]
        y = PAD_T + gap + i * (bar_h + gap)
        bw = current_util / 100 * inner_w
        color = _util_color(current_util)
        lines.append(f'<rect x="{PAD_L}" y="{y}" width="{bw:.1f}" height="{bar_h}" fill="{color}" rx="3" opacity="0.85"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{y+bar_h//2+4}" fill="#e2e8f0" font-size="10" text-anchor="end">{node["name"]}</text>')
        lines.append(f'<text x="{PAD_L+bw+5:.1f}" y="{y+bar_h//2+4}" fill="#94a3b8" font-size="10">{current_util}%</text>')
        if node["status"] == "DEGRADED":
            lines.append(f'<text x="{PAD_L+bw+38:.1f}" y="{y+bar_h//2+4}" fill="#f97316" font-size="9">&#x26A0; DEGRADED</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def _node_card(node: dict, color: str) -> str:
    current_util = node["util_history"][-1]
    current_mem = node["mem_history"][-1]
    current_temp = node["temp_history"][-1]
    avg_util = _avg(node["util_history"])
    uc = _util_color(current_util)
    status_color = "#22c55e" if node["status"] == "HEALTHY" else "#f97316"
    reason = node.get("status_reason", "")
    reason_html = f'<div style="font-size:11px;color:#f97316;margin-top:4px;">&#x26A0; {reason}</div>' if reason else ""
    return f"""
    <div style="background:#0f172a;border:1px solid #334155;border-radius:10px;padding:16px 20px;border-top:3px solid {color};">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;">
        <div><div style="font-size:14px;font-weight:700;color:#f1f5f9;">{node['name']}</div><div style="font-size:11px;color:#64748b;margin-top:2px;">{node['gpu_type']} &nbsp;|&nbsp; {node['region'].upper()}</div>{reason_html}</div>
        <span style="background:{'#14532d' if node['status']=='HEALTHY' else '#431407'};color:{status_color};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">{node['status']}</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">
        <div><div style="font-size:10px;color:#64748b;margin-bottom:3px;">UTIL NOW</div><div style="font-size:22px;font-weight:700;color:{uc};">{current_util}%</div></div>
        <div><div style="font-size:10px;color:#64748b;margin-bottom:3px;">MEM USED</div><div style="font-size:22px;font-weight:700;color:#38bdf8;">{current_mem}%</div></div>
        <div><div style="font-size:10px;color:#64748b;margin-bottom:3px;">TEMP</div><div style="font-size:22px;font-weight:700;color:#e2e8f0;">{current_temp}&#x2103;</div></div>
        <div><div style="font-size:10px;color:#64748b;margin-bottom:3px;">8H AVG</div><div style="font-size:22px;font-weight:700;color:#94a3b8;">{avg_util}%</div></div>
      </div>
    </div>"""


def _render_html() -> str:
    line_svg = _build_line_chart_svg()
    bar_svg = _build_bar_chart_svg()
    all_util_now = [n["util_history"][-1] for n in GPU_NODES]
    avg_util = round(sum(all_util_now) / len(all_util_now), 1)
    peak_node = max(GPU_NODES, key=lambda n: n["util_history"][-1])
    nodes_over_80 = sum(1 for u in all_util_now if u > 80)
    total_gpu_hrs = round(sum(_avg(n["util_history"]) * 24 / 100 for n in GPU_NODES), 1)
    node_cards_html = "\n".join(_node_card(node, NODE_COLORS[i]) for i, node in enumerate(GPU_NODES))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>OCI Robot Cloud — GPU Utilization Tracker</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }}
    .header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }}
    .header h1 {{ font-size: 20px; font-weight: 700; color: #f1f5f9; }}
    .sub {{ font-size: 13px; color: #64748b; margin-top: 2px; }}
    .content {{ padding: 28px 32px; max-width: 1100px; margin: 0 auto; }}
    .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .stat-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px 20px; }}
    .stat-label {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }}
    .stat-value {{ font-size: 28px; font-weight: 700; color: #f1f5f9; }}
    .stat-sub {{ font-size: 11px; color: #64748b; margin-top: 4px; }}
    .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px 24px; margin-bottom: 24px; }}
    .section-title {{ font-size: 14px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 16px; }}
    .node-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .footer {{ text-align: center; padding: 20px; font-size: 11px; color: #334155; border-top: 1px solid #1e293b; margin-top: 16px; }}
  </style>
</head>
<body>
  <div class="header"><div style="width:10px;height:10px;border-radius:50%;background:#22c55e;"></div><div><h1>GPU Utilization Tracker</h1><div class="sub">OCI A100 Fleet — 5 Nodes Across 3 Regions — Last 8 Hours</div></div></div>
  <div class="content">
    <div class="stats">
      <div class="stat-card"><div class="stat-label">Fleet Avg Utilization</div><div class="stat-value" style="color:#38bdf8;">{avg_util}%</div><div class="stat-sub">current snapshot</div></div>
      <div class="stat-card"><div class="stat-label">Peak Util Node</div><div class="stat-value" style="color:#C74634;">{peak_node['util_history'][-1]}%</div><div class="stat-sub">{peak_node['name']}</div></div>
      <div class="stat-card"><div class="stat-label">GPU-hrs Today (est.)</div><div class="stat-value">{total_gpu_hrs}h</div><div class="stat-sub">across all nodes</div></div>
      <div class="stat-card"><div class="stat-label">Nodes &gt;80% Util</div><div class="stat-value" style="color:{'#f97316' if nodes_over_80 > 0 else '#22c55e'};">{nodes_over_80}</div></div>
    </div>
    <div class="section"><div class="section-title">Utilization Over Time (8h)</div><div style="overflow-x:auto;">{line_svg}</div></div>
    <div class="section"><div class="section-title">Current Utilization by Node</div><div style="overflow-x:auto;">{bar_svg}</div></div>
    <div class="section"><div class="section-title">Per-Node Detail</div><div class="node-grid">{node_cards_html}</div></div>
  </div>
  <div class="footer">Oracle Confidential | OCI Robot Cloud GPU Utilization Tracker | Port 8125</div>
</body></html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return _render_html()


@app.get("/nodes")
def list_nodes():
    result = []
    for node in GPU_NODES:
        result.append({"name": node["name"], "gpu_type": node["gpu_type"], "region": node["region"], "role": node["role"], "status": node["status"], "status_reason": node.get("status_reason"), "current_util_pct": node["util_history"][-1], "current_mem_pct": node["mem_history"][-1], "current_temp_c": node["temp_history"][-1], "avg_util_8h": _avg(node["util_history"])})
    return JSONResponse(content=result)


@app.get("/nodes/{node_name}")
def get_node(node_name: str):
    for node in GPU_NODES:
        if node["name"] == node_name:
            return JSONResponse(content={**node, "current_util_pct": node["util_history"][-1], "current_mem_pct": node["mem_history"][-1], "current_temp_c": node["temp_history"][-1], "avg_util_8h": _avg(node["util_history"]), "hours_labels": HOURS_LABELS})
    raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found")


@app.get("/summary")
def fleet_summary():
    all_util_now = [n["util_history"][-1] for n in GPU_NODES]
    avg_util = round(sum(all_util_now) / len(all_util_now), 1)
    peak_node = max(GPU_NODES, key=lambda n: n["util_history"][-1])
    nodes_over_80 = sum(1 for u in all_util_now if u > 80)
    total_gpu_hrs = round(sum(_avg(n["util_history"]) * 24 / 100 for n in GPU_NODES), 1)
    degraded = [n["name"] for n in GPU_NODES if n["status"] == "DEGRADED"]
    return JSONResponse(content={"fleet_avg_util_pct": avg_util, "peak_util_node": peak_node["name"], "peak_util_pct": peak_node["util_history"][-1], "nodes_over_80_pct": nodes_over_80, "total_gpu_hrs_today_est": total_gpu_hrs, "total_nodes": len(GPU_NODES), "degraded_nodes": degraded, "timestamp": datetime.utcnow().isoformat() + "Z"})


@app.get("/health")
def health():
    degraded = [n["name"] for n in GPU_NODES if n["status"] == "DEGRADED"]
    return JSONResponse(content={"status": "degraded" if degraded else "ok", "service": "gpu_utilization_tracker", "port": 8125, "timestamp": datetime.utcnow().isoformat() + "Z", "total_nodes": len(GPU_NODES), "degraded_nodes": degraded})


def main():
    uvicorn.run("gpu_utilization_tracker:app", host="0.0.0.0", port=8125, reload=False)


if __name__ == "__main__":
    main()

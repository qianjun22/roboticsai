"""OCI Robot Cloud — Network Topology Visualizer
Displays live OCI deployment topology across regions with latency and bandwidth data.
Port: 8131
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    raise ImportError("fastapi and uvicorn are required: pip install fastapi uvicorn")

import math
from typing import Any

app = FastAPI(title="OCI Robot Cloud Network Topology", description="Network topology visualizer for OCI Robot Cloud multi-region deployment", version="1.0.0")

REGIONS: dict[str, dict[str, Any]] = {
    "ashburn":  {"name": "Ashburn",  "role": "primary", "color": "#38bdf8", "nodes": ["ashburn-lb", "ashburn-prod-1", "ashburn-canary-1", "ashburn-shadow-1"], "total_bandwidth_gbps": 21.5, "cross_region_latency_ms": {"phoenix": 68, "frankfurt": 98}},
    "phoenix":  {"name": "Phoenix",  "role": "eval",    "color": "#f59e0b", "nodes": ["phoenix-lb", "phoenix-eval-1"], "total_bandwidth_gbps": 10.5, "cross_region_latency_ms": {"ashburn": 68}},
    "frankfurt":{"name": "Frankfurt","role": "staging",  "color": "#34d399", "nodes": ["frankfurt-lb", "frankfurt-staging-1"], "total_bandwidth_gbps": 10.5, "cross_region_latency_ms": {"ashburn": 98}},
}

NODES: dict[str, dict[str, Any]] = {
    "client":               {"label": "Client",             "type": "external",      "region": None,        "health": "HEALTHY"},
    "ashburn-lb":           {"label": "Ashburn LB",         "type": "load_balancer", "region": "ashburn",   "health": "HEALTHY"},
    "ashburn-prod-1":       {"label": "ashburn-prod-1",     "type": "compute",       "region": "ashburn",   "health": "HEALTHY"},
    "ashburn-canary-1":     {"label": "ashburn-canary-1",   "type": "compute",       "region": "ashburn",   "health": "HEALTHY"},
    "ashburn-shadow-1":     {"label": "ashburn-shadow-1",   "type": "compute",       "region": "ashburn",   "health": "CRITICAL"},
    "phoenix-lb":           {"label": "Phoenix LB",         "type": "load_balancer", "region": "phoenix",   "health": "HEALTHY"},
    "phoenix-eval-1":       {"label": "phoenix-eval-1",     "type": "compute",       "region": "phoenix",   "health": "HEALTHY"},
    "frankfurt-lb":         {"label": "Frankfurt LB",       "type": "load_balancer", "region": "frankfurt", "health": "HEALTHY"},
    "frankfurt-staging-1":  {"label": "frankfurt-staging-1","type": "compute",       "region": "frankfurt", "health": "HEALTHY"},
}

CONNECTIONS: list[dict[str, Any]] = [
    {"src": "client",       "dst": "ashburn-lb",         "latency_ms": 228, "bandwidth_gbps": 1.0,  "type": "external",     "status": "ACTIVE"},
    {"src": "ashburn-lb",   "dst": "ashburn-prod-1",     "latency_ms": 2,   "bandwidth_gbps": 10.0, "type": "internal",     "status": "ACTIVE"},
    {"src": "ashburn-lb",   "dst": "ashburn-canary-1",   "latency_ms": 2,   "bandwidth_gbps": 10.0, "type": "internal",     "status": "ACTIVE"},
    {"src": "ashburn-lb",   "dst": "ashburn-shadow-1",   "latency_ms": 2,   "bandwidth_gbps": 10.0, "type": "internal",     "status": "DEGRADED"},
    {"src": "ashburn-lb",   "dst": "phoenix-lb",         "latency_ms": 68,  "bandwidth_gbps": 0.5,  "type": "cross_region", "status": "ACTIVE"},
    {"src": "ashburn-lb",   "dst": "frankfurt-lb",       "latency_ms": 98,  "bandwidth_gbps": 0.5,  "type": "cross_region", "status": "ACTIVE"},
    {"src": "phoenix-lb",   "dst": "phoenix-eval-1",     "latency_ms": 3,   "bandwidth_gbps": 10.0, "type": "internal",     "status": "ACTIVE"},
    {"src": "frankfurt-lb", "dst": "frankfurt-staging-1","latency_ms": 3,   "bandwidth_gbps": 10.0, "type": "internal",     "status": "ACTIVE"},
]

NODE_POSITIONS: dict[str, tuple[float, float]] = {
    "client": (50, 150), "ashburn-lb": (210, 150), "ashburn-prod-1": (360, 80),
    "ashburn-canary-1": (360, 150), "ashburn-shadow-1": (360, 220),
    "phoenix-lb": (520, 80), "phoenix-eval-1": (640, 80),
    "frankfurt-lb": (520, 220), "frankfurt-staging-1": (640, 220),
}

REGION_BOXES: dict[str, tuple[float, float, float, float]] = {
    "ashburn": (180, 50, 400, 260), "phoenix": (490, 48, 680, 118), "frankfurt": (490, 185, 680, 255),
}

REGION_COLORS = {"ashburn": "#38bdf8", "phoenix": "#f59e0b", "frankfurt": "#34d399"}


def _arrowhead(x2, y2, dx, dy, color):
    length = math.hypot(dx, dy)
    if length == 0: return ""
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    size = 6
    ax = x2 - ux * size + px * (size / 2)
    ay = y2 - uy * size + py * (size / 2)
    bx = x2 - ux * size - px * (size / 2)
    by = y2 - uy * size - py * (size / 2)
    return f'<polygon points="{x2:.1f},{y2:.1f} {ax:.1f},{ay:.1f} {bx:.1f},{by:.1f}" fill="{color}"/>'


def _topology_svg():
    W, H = 700, 300
    lines: list[str] = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:10px;">']
    for region_key, (rx1, ry1, rx2, ry2) in REGION_BOXES.items():
        color = REGION_COLORS[region_key]
        lines.append(f'<rect x="{rx1}" y="{ry1}" width="{rx2-rx1}" height="{ry2-ry1}" rx="10" fill="{color}" fill-opacity="0.06" stroke="{color}" stroke-opacity="0.35" stroke-width="1.5"/>')
        lines.append(f'<text x="{rx1+8}" y="{ry1+14}" fill="{color}" font-size="9" font-weight="700" opacity="0.8">{REGIONS[region_key]["name"]} ({REGIONS[region_key]["role"].upper()})</text>')
    for conn in CONNECTIONS:
        x1, y1 = NODE_POSITIONS[conn["src"]]
        x2, y2 = NODE_POSITIONS[conn["dst"]]
        is_critical = NODES[conn["src"]]["health"] == "CRITICAL" or NODES[conn["dst"]]["health"] == "CRITICAL"
        if is_critical or conn["status"] == "DEGRADED":
            stroke, dash = "#ef4444", "stroke-dasharray:5,4;"
        elif conn["type"] == "cross_region":
            stroke, dash = "#7c3aed", "stroke-dasharray:6,3;"
        elif conn["type"] == "external":
            stroke, dash = "#38bdf8", ""
        else:
            stroke, dash = "#475569", ""
        lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="1.8" {dash}/>')
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length > 0:
            t = (length - 13) / length
            lines.append(_arrowhead(x1 + dx * t, y1 + dy * t, dx, dy, stroke))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        lines.append(f'<rect x="{mx-14:.1f}" y="{my-8:.1f}" width="28" height="14" rx="3" fill="#0f172a" fill-opacity="0.85"/>')
        lines.append(f'<text x="{mx:.1f}" y="{my+4:.1f}" fill="{stroke}" font-size="8" text-anchor="middle">{conn["latency_ms"]}ms</text>')
    for node_key, (nx, ny) in NODE_POSITIONS.items():
        node = NODES[node_key]
        is_critical = node["health"] == "CRITICAL"
        region = node["region"]
        if node_key == "client":
            fill, stroke, r = "#1e293b", "#38bdf8", 22
        elif node["type"] == "load_balancer":
            fill, stroke, r = "#1e293b", REGION_COLORS.get(region, "#94a3b8") if region else "#94a3b8", 18
        else:
            fill = "#1e293b"
            stroke = "#ef4444" if is_critical else (REGION_COLORS.get(region, "#94a3b8") if region else "#94a3b8")
            r = 14
        stroke_w = "2.5" if is_critical else "1.8"
        lines.append(f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_w}"/>')
        dot_color = "#ef4444" if is_critical else "#22c55e"
        lines.append(f'<circle cx="{nx+r-3:.1f}" cy="{ny-r+3:.1f}" r="4" fill="{dot_color}" stroke="#0f172a" stroke-width="1.2"/>')
        icon = "C" if node_key == "client" else ("LB" if node["type"] == "load_balancer" else "A")
        lines.append(f'<text x="{nx:.1f}" y="{ny+4:.1f}" fill="#e2e8f0" font-size="9" font-weight="700" text-anchor="middle">{icon}</text>')
        label_y = ny + r + 13
        lines.append(f'<text x="{nx:.1f}" y="{label_y:.1f}" fill="#94a3b8" font-size="8.5" text-anchor="middle">{node["label"]}</text>')
        if is_critical:
            lines.append(f'<text x="{nx:.1f}" y="{label_y+11:.1f}" fill="#ef4444" font-size="8" text-anchor="middle" font-weight="700">CRITICAL</text>')
    legend = [("#38bdf8", "External"), ("#475569", "Internal"), ("#7c3aed", "Cross-region"), ("#ef4444", "Degraded/Critical"), ("#22c55e", "Healthy")]
    lx = 10
    for lcolor, ltxt in legend:
        lines.append(f'<rect x="{lx}" y="{H-18}" width="16" height="8" rx="2" fill="{lcolor}"/>')
        lines.append(f'<text x="{lx+20}" y="{H-11}" fill="#64748b" font-size="8">{ltxt}</text>')
        lx += len(ltxt) * 5.2 + 30
    lines.append("</svg>")
    return "\n".join(lines)


def _build_html():
    topo_svg = _topology_svg()
    region_cards = ""
    for rk, region in REGIONS.items():
        color = REGION_COLORS[rk]
        cross_lat = region.get("cross_region_latency_ms", {})
        lat_str = " / ".join(f"{v}ms to {k.capitalize()}" for k, v in cross_lat.items()) or "N/A"
        role_badge_bg = {"primary": "#1a3352", "eval": "#4a2500", "staging": "#0c3020"}.get(region["role"], "#1e293b")
        role_badge_fg = {"primary": "#38bdf8", "eval": "#f59e0b", "staging": "#34d399"}.get(region["role"], "#94a3b8")
        region_cards += f'<div style="background:#1e293b;border:1px solid {color};border-top:3px solid {color};border-radius:10px;padding:18px 22px;flex:1;min-width:180px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;"><span style="color:{color};font-weight:700;font-size:15px;">{region["name"]}</span><span style="background:{role_badge_bg};color:{role_badge_fg};padding:2px 8px;border-radius:9999px;font-size:10px;font-weight:600;">{region["role"].upper()}</span></div><div style="color:#e2e8f0;font-size:1.8rem;font-weight:800;">{len(region["nodes"])}</div><div style="color:#64748b;font-size:11px;">nodes</div><div style="color:#94a3b8;font-size:11px;margin-top:8px;">{region["total_bandwidth_gbps"]} Gbps total BW</div><div style="color:#64748b;font-size:10px;margin-top:4px;">{lat_str}</div></div>'
    conn_rows = ""
    for conn in CONNECTIONS:
        is_degraded = conn["status"] == "DEGRADED" or NODES[conn["src"]]["health"] == "CRITICAL" or NODES[conn["dst"]]["health"] == "CRITICAL"
        status_color = "#ef4444" if is_degraded else "#22c55e"
        status_label = "DEGRADED" if is_degraded else "ACTIVE"
        type_color = {"external": "#38bdf8", "internal": "#64748b", "cross_region": "#a78bfa"}.get(conn["type"], "#64748b")
        bw = f"{conn['bandwidth_gbps']} Gbps" if conn["bandwidth_gbps"] >= 1 else f"{int(conn['bandwidth_gbps']*1000)} Mbps"
        conn_rows += f'<tr style="border-bottom:1px solid #1e293b;"><td style="padding:9px 14px;color:#e2e8f0;">{conn["src"]}</td><td style="color:#475569;padding:9px 4px;">&rarr;</td><td style="padding:9px 14px;color:#e2e8f0;">{conn["dst"]}</td><td style="padding:9px 14px;color:#38bdf8;text-align:center;">{conn["latency_ms"]} ms</td><td style="padding:9px 14px;color:#94a3b8;text-align:center;">{bw}</td><td style="padding:9px 14px;text-align:center;"><span style="color:{type_color};font-size:10px;">{conn["type"].replace("_"," ").upper()}</span></td><td style="padding:9px 14px;text-align:center;"><span style="color:{status_color};font-weight:600;font-size:11px;">{status_label}</span></td></tr>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>OCI Robot Cloud — Network Topology</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }}
    .header {{ background: #1e293b; border-bottom: 2px solid #38bdf8; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }}
    .content {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px; }}
    .alert {{ background: #2d1010; border: 1px solid #ef4444; border-radius: 8px; padding: 12px 18px; margin-bottom: 24px; display: flex; align-items: center; gap: 12px; }}
    .section-title {{ font-size: 1rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 14px; }}
    .cards {{ display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 30px; }}
    .chart-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 28px; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 10px; overflow: hidden; border: 1px solid #334155; }}
    th {{ background: #0f172a; color: #64748b; font-size: 11px; text-transform: uppercase; padding: 10px 14px; text-align: left; }}
    td {{ padding: 9px 14px; color: #94a3b8; font-size: 12px; }}
    tr:hover {{ background: #243046; }}
    .footer {{ text-align: center; color: #334155; font-size: 11px; margin-top: 40px; padding: 16px; border-top: 1px solid #1e293b; }}
  </style>
</head>
<body>
  <div class="header">
    <div style="width:36px;height:36px;background:linear-gradient(135deg,#38bdf8,#0284c7);border-radius:8px;display:flex;align-items:center;justify-content:center;"><svg width="20" height="20" viewBox="0 0 20 20"><circle cx="10" cy="10" r="3" fill="white"/><line x1="10" y1="10" x2="3" y2="4" stroke="white" stroke-width="1.5"/><line x1="10" y1="10" x2="17" y2="4" stroke="white" stroke-width="1.5"/><line x1="10" y1="10" x2="3" y2="16" stroke="white" stroke-width="1.5"/><line x1="10" y1="10" x2="17" y2="16" stroke="white" stroke-width="1.5"/><circle cx="3" cy="4" r="2" fill="none" stroke="white" stroke-width="1.2"/><circle cx="17" cy="4" r="2" fill="none" stroke="white" stroke-width="1.2"/><circle cx="3" cy="16" r="2" fill="none" stroke="white" stroke-width="1.2"/><circle cx="17" cy="16" r="2" fill="none" stroke="white" stroke-width="1.2"/></svg></div>
    <div><div style="font-size:1.3rem;font-weight:700;color:#f1f5f9;">Network Topology</div><div style="font-size:0.8rem;color:#64748b;margin-top:2px;">OCI Robot Cloud &mdash; Multi-region deployment visualizer</div></div>
    <div style="margin-left:auto;color:#334155;font-size:12px;">Port 8131</div>
  </div>
  <div class="content">
    <div class="alert"><svg width="18" height="18" viewBox="0 0 18 18"><path d="M9 1L1 16h16L9 1z" fill="none" stroke="#ef4444" stroke-width="1.5"/><line x1="9" y1="7" x2="9" y2="11" stroke="#ef4444" stroke-width="1.5"/><circle cx="9" cy="13.5" r="0.8" fill="#ef4444"/></svg><span style="color:#ef4444;font-weight:700;font-size:13px;">CRITICAL:</span><span style="color:#fca5a5;font-size:13px;">ashburn-shadow-1 is in CRITICAL state &mdash; connection from Ashburn LB degraded</span></div>
    <div class="section-title">Regions</div>
    <div class="cards">{region_cards}</div>
    <div class="section-title">Topology Diagram</div>
    <div class="chart-card"><div style="color:#64748b;font-size:11px;margin-bottom:12px;text-transform:uppercase;">Live deployment graph &mdash; arrow direction = traffic flow &nbsp;|&nbsp; dashed = cross-region or degraded</div>{topo_svg}</div>
    <div class="section-title">Connections</div>
    <table><thead><tr><th>Source</th><th></th><th>Destination</th><th style="text-align:center;">Latency</th><th style="text-align:center;">Bandwidth</th><th style="text-align:center;">Type</th><th style="text-align:center;">Status</th></tr></thead><tbody>{conn_rows}</tbody></table>
  </div>
  <div class="footer">Oracle Confidential | OCI Robot Cloud Network Topology | Port 8131</div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=_build_html())


@app.get("/topology")
async def get_topology():
    return JSONResponse(content={"nodes": NODES, "edges": CONNECTIONS})


@app.get("/regions")
async def get_regions():
    return JSONResponse(content=REGIONS)


@app.get("/paths")
async def get_paths():
    paths: list[dict[str, Any]] = []
    def _neighbors(node_key):
        return [(c["dst"], c) for c in CONNECTIONS if c["src"] == node_key]
    def _dfs(current, visited, path, total_lat):
        for dst, conn in _neighbors(current):
            if dst in visited: continue
            new_path = path + [{"hop": dst, "edge": conn}]
            new_lat = total_lat + conn["latency_ms"]
            paths.append({"src": path[0]["hop"] if path else current, "dst": dst, "hops": len(new_path), "total_latency_ms": round(new_lat, 1), "path": new_path})
            _dfs(dst, visited | {dst}, new_path, new_lat)
    for start in NODES:
        _dfs(start, {start}, [], 0.0)
    paths.sort(key=lambda p: p["total_latency_ms"])
    return JSONResponse(content={"total_paths": len(paths), "paths": paths})


@app.get("/health")
async def health():
    critical_nodes = [k for k, v in NODES.items() if v["health"] == "CRITICAL"]
    degraded_conns = [c for c in CONNECTIONS if c["status"] == "DEGRADED"]
    return JSONResponse(content={"status": "degraded" if critical_nodes else "healthy", "service": "network_topology", "port": 8131, "regions": len(REGIONS), "total_nodes": len(NODES), "total_connections": len(CONNECTIONS), "critical_nodes": critical_nodes, "degraded_connections": len(degraded_conns)})


def main():
    uvicorn.run(app, host="0.0.0.0", port=8131, log_level="info")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
network_topology_monitor.py — FastAPI port 8096
OCI Robot Cloud multi-region network topology and connectivity monitor.
Oracle Confidential
"""

import json
import math
import random
import datetime
from typing import Dict, List, Optional

REGIONS = {
    "us-ashburn-1": {
        "label": "Ashburn (Primary)", "role": "primary", "hardware": "2×A100_80GB",
        "baseline_latency_ms": 226, "x": 150, "y": 200,
    },
    "us-phoenix-1": {
        "label": "Phoenix (Eval)", "role": "eval", "hardware": "A100_40GB",
        "baseline_latency_ms": 241, "x": 500, "y": 200,
    },
    "eu-frankfurt-1": {
        "label": "Frankfurt (Staging)", "role": "staging", "hardware": "A100_40GB",
        "baseline_latency_ms": 258, "x": 850, "y": 200,
    },
}

SERVICES = ["groot_inference", "fine_tune_api", "data_pipeline", "eval_pipeline", "gateway"]
SLA = {"latency_ms": 300.0, "packet_loss_pct": 0.5, "bandwidth_mbps": 100.0}
CROSS_REGION_BASELINES = {
    ("us-ashburn-1", "us-phoenix-1"): 62.4,
    ("us-ashburn-1", "eu-frankfurt-1"): 98.7,
    ("us-phoenix-1", "eu-frankfurt-1"): 141.2,
}


def _seed_for(region: str, day: int) -> int:
    return hash(region + str(day)) & 0xFFFFFFFF


def simulate_day_metrics(region_id: str, day: int) -> Dict:
    rng = random.Random(_seed_for(region_id, day))
    base = REGIONS[region_id]["baseline_latency_ms"]
    latency = base + rng.gauss(0, 4.0)
    packet_loss = max(0.0, rng.gauss(0.05, 0.03))
    bandwidth = rng.gauss(450.0, 20.0)
    jitter = max(0.0, rng.gauss(3.5, 1.0))
    if region_id == "us-phoenix-1" and day in (13, 14):
        packet_loss = rng.gauss(1.8, 0.3)
        latency += rng.gauss(35, 5)
    if region_id == "eu-frankfurt-1" and day in (21, 22):
        latency += rng.gauss(120, 15)
        jitter += rng.gauss(25, 4)
    return {
        "day": day + 1,
        "latency_ms": round(latency, 2),
        "packet_loss_pct": round(packet_loss, 4),
        "bandwidth_mbps": round(bandwidth, 2),
        "jitter_ms": round(jitter, 3),
    }


def get_current_metrics(region_id: str) -> Dict:
    return simulate_day_metrics(region_id, 29)


def service_status(region_id: str, service: str) -> Dict:
    rng = random.Random(hash(region_id + service) & 0xFFFFFFFF)
    healthy = rng.random() > 0.04
    latency = get_current_metrics(region_id)["latency_ms"] + rng.gauss(0, 8)
    return {
        "service": service, "status": "healthy" if healthy else "degraded",
        "latency_ms": round(latency, 2),
        "uptime_pct": round(99.5 + rng.gauss(0, 0.3), 3),
    }


def cross_region_matrix() -> Dict:
    region_ids = list(REGIONS.keys())
    matrix = {}
    for r1 in region_ids:
        row = {}
        for r2 in region_ids:
            if r1 == r2:
                row[r2] = 0.0
            else:
                key = tuple(sorted([r1, r2]))
                base = CROSS_REGION_BASELINES.get(key, 100.0)
                rng = random.Random(hash(r1 + r2 + "29") & 0xFFFFFFFF)
                row[r2] = round(base + rng.gauss(0, 2.5), 2)
        matrix[r1] = row
    return matrix


def get_alerts() -> List[Dict]:
    alerts = []
    for rid in REGIONS:
        m = get_current_metrics(rid)
        if m["latency_ms"] > SLA["latency_ms"]:
            alerts.append({"region": rid, "metric": "latency_ms", "value": m["latency_ms"],
                           "threshold": SLA["latency_ms"], "severity": "critical"})
        if m["packet_loss_pct"] > SLA["packet_loss_pct"]:
            alerts.append({"region": rid, "metric": "packet_loss_pct", "value": m["packet_loss_pct"],
                           "threshold": SLA["packet_loss_pct"], "severity": "warning"})
        if m["bandwidth_mbps"] < SLA["bandwidth_mbps"]:
            alerts.append({"region": rid, "metric": "bandwidth_mbps", "value": m["bandwidth_mbps"],
                           "threshold": SLA["bandwidth_mbps"], "severity": "critical"})
    return alerts


def sla_badge(value: float, threshold: float, invert: bool = False) -> str:
    ok = value <= threshold if not invert else value >= threshold
    color = "#22c55e" if ok else "#ef4444"
    return f'<span style="color:{color};font-weight:700">{value}</span>'


def render_topology_svg(matrix: Dict) -> str:
    nodes = {rid: REGIONS[rid] for rid in REGIONS}
    pairs = [("us-ashburn-1","us-phoenix-1"),("us-ashburn-1","eu-frankfurt-1"),("us-phoenix-1","eu-frankfurt-1")]
    lines = ""
    for r1, r2 in pairs:
        x1,y1 = nodes[r1]["x"]+60, nodes[r1]["y"]+30
        x2,y2 = nodes[r2]["x"]+60, nodes[r2]["y"]+30
        mx,my = (x1+x2)//2, (y1+y2)//2
        lat = matrix[r1][r2]
        color = "#22c55e" if lat < 150 else "#f59e0b"
        lines += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2"/>'
        lines += f'<text x="{mx}" y="{my-6}" fill="#94a3b8" font-size="11" text-anchor="middle">{lat}ms</text>'
    boxes = ""
    role_colors = {"primary": "#C74634", "eval": "#3b82f6", "staging": "#8b5cf6"}
    for rid, info in nodes.items():
        cx,cy = info["x"], info["y"]
        rc = role_colors.get(info["role"], "#64748b")
        boxes += (f'<rect x="{cx}" y="{cy}" width="120" height="60" rx="8" fill="#1e293b" stroke="{rc}" stroke-width="2"/>'
                  f'<text x="{cx+60}" y="{cy+22}" fill="{rc}" font-size="11" font-weight="bold" text-anchor="middle">{info["role"].upper()}</text>'
                  f'<text x="{cx+60}" y="{cy+38}" fill="#e2e8f0" font-size="9" text-anchor="middle">{rid}</text>'
                  f'<text x="{cx+60}" y="{cy+52}" fill="#94a3b8" font-size="8" text-anchor="middle">{info["hardware"]}</text>')
    return ('<svg viewBox="0 0 1060 320" xmlns="http://www.w3.org/2000/svg" '
            'style="width:100%;max-width:1040px;background:#0f172a;border-radius:10px">'
            + lines + boxes + '</svg>')


def render_latency_sparkline(region_id: str) -> str:
    days = [simulate_day_metrics(region_id, d)["latency_ms"] for d in range(30)]
    w, h = 300, 60
    mn, mx = min(days), max(days)
    rng = mx - mn if mx != mn else 1
    pts = []
    for i, v in enumerate(days):
        x = int(i * w / 29)
        y = int(h - (v - mn) / rng * (h - 4) - 2)
        pts.append(f"{x},{y}")
    polyline = " ".join(pts)
    sla_y = int(h - (SLA["latency_ms"] - mn) / rng * (h - 4) - 2) if mn < SLA["latency_ms"] < mx else -1
    sla_line = (f'<line x1="0" y1="{sla_y}" x2="{w}" y2="{sla_y}" stroke="#ef4444" stroke-width="1" stroke-dasharray="4,2"/>') if sla_y >= 0 else ""
    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{w}px">'
            f'{sla_line}<polyline points="{polyline}" fill="none" stroke="#38bdf8" stroke-width="1.5"/>'
            f'<text x="0" y="{h-1}" fill="#94a3b8" font-size="8">Day 1</text>'
            f'<text x="{w}" y="{h-1}" fill="#94a3b8" font-size="8" text-anchor="end">Day 30</text></svg>')


def build_dashboard() -> str:
    matrix = cross_region_matrix()
    alerts = get_alerts()
    alert_html = ""
    for a in alerts:
        color = "#ef4444" if a["severity"] == "critical" else "#f59e0b"
        alert_html += (f'<div style="background:#1e293b;border-left:4px solid {color};'
                       f'padding:8px 14px;margin:6px 0;border-radius:4px;font-size:13px;">'
                       f'<b style="color:{color}">[{a["severity"].upper()}]</b> '
                       f'{a["region"]} — {a["metric"]}: {a["value"]} (threshold {a["threshold"]})</div>')
    if not alerts:
        alert_html = '<div style="color:#22c55e;font-size:13px">All regions within SLA thresholds.</div>'
    region_cards = ""
    for rid, info in REGIONS.items():
        m = get_current_metrics(rid)
        svcs = [service_status(rid, s) for s in SERVICES]
        svc_rows = "".join(
            f'<tr><td style="padding:4px 8px;color:#94a3b8">{s["service"]}</td>'
            f'<td style="padding:4px 8px;color:{"#22c55e" if s["status"]=="healthy" else "#ef4444"}">'
            f'{s["status"]}</td><td style="padding:4px 8px;color:#e2e8f0">{s["latency_ms"]}ms</td></tr>'
            for s in svcs)
        spark = render_latency_sparkline(rid)
        region_cards += f'''
        <div style="background:#1e293b;border-radius:10px;padding:20px;margin-bottom:20px">
          <h3 style="color:#C74634;margin:0 0 4px">{info["label"]}</h3>
          <p style="color:#64748b;font-size:12px;margin:0 0 12px">{rid} | {info["hardware"]}</p>
          <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:14px">
            <div><span style="color:#94a3b8;font-size:12px">Latency</span><br>{sla_badge(m["latency_ms"], SLA["latency_ms"])} ms</div>
            <div><span style="color:#94a3b8;font-size:12px">Packet Loss</span><br>{sla_badge(m["packet_loss_pct"], SLA["packet_loss_pct"])} %</div>
            <div><span style="color:#94a3b8;font-size:12px">Bandwidth</span><br>{sla_badge(m["bandwidth_mbps"], SLA["bandwidth_mbps"], invert=True)} Mbps</div>
            <div><span style="color:#94a3b8;font-size:12px">Jitter</span><br><span style="color:#e2e8f0">{m["jitter_ms"]} ms</span></div>
          </div>
          <p style="color:#64748b;font-size:11px;margin:0 0 4px">30-day latency trend (red dashed = SLA limit)</p>
          {spark}
          <table style="width:100%;border-collapse:collapse;margin-top:14px;font-size:13px">
            <tr><th style="text-align:left;color:#64748b;padding:4px 8px">Service</th>
                <th style="text-align:left;color:#64748b;padding:4px 8px">Status</th>
                <th style="text-align:left;color:#64748b;padding:4px 8px">Latency</th></tr>
            {svc_rows}
          </table>
        </div>'''
    region_ids = list(REGIONS.keys())
    header_cells = "".join(f'<th style="padding:8px;color:#64748b;font-size:12px">{r.split("-")[1][:3].upper()}</th>' for r in region_ids)
    matrix_rows = ""
    for r1 in region_ids:
        cells = "".join(f'<td style="padding:8px;text-align:center;color:{"#22c55e" if matrix[r1][r2]==0 else ("#f59e0b" if matrix[r1][r2]>100 else "#e2e8f0")}">{matrix[r1][r2] if matrix[r1][r2] else "\u2014"}</td>' for r2 in region_ids)
        matrix_rows += f'<tr><td style="padding:8px;color:#94a3b8;font-size:12px">{r1}</td>{cells}</tr>'
    topo_svg = render_topology_svg(matrix)
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OCI Robot Cloud — Network Topology Monitor</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}} h2{{color:#38bdf8;font-size:16px;margin:20px 0 10px}}
.footer{{color:#475569;font-size:11px;text-align:center;margin-top:40px;border-top:1px solid #1e293b;padding-top:12px}}</style></head>
<body><h1>OCI Robot Cloud — Network Topology Monitor</h1>
<p style="color:#64748b;font-size:13px;margin:0 0 20px">Port 8096 | Updated: {ts} UTC | 3 Regions | 5 Services each</p>
<h2>Active Alerts</h2>{alert_html}
<h2>Topology Diagram</h2>{topo_svg}
<h2>Cross-Region Latency Matrix (ms)</h2>
<div style="background:#1e293b;border-radius:8px;padding:16px;display:inline-block;margin-bottom:20px">
<table style="border-collapse:collapse;font-size:13px"><tr><th></th>{header_cells}</tr>{matrix_rows}</table></div>
<h2>Region Status</h2>{region_cards}
<div class="footer">Oracle Confidential — OCI Robot Cloud Infrastructure | network_topology_monitor.py | Port 8096</div>
</body></html>'''


def topology_json() -> Dict:
    matrix = cross_region_matrix()
    regions_out = {}
    for rid, info in REGIONS.items():
        m = get_current_metrics(rid)
        m["sla_ok"] = (m["latency_ms"] < SLA["latency_ms"] and
                       m["packet_loss_pct"] < SLA["packet_loss_pct"] and
                       m["bandwidth_mbps"] > SLA["bandwidth_mbps"])
        regions_out[rid] = {**info, "current_metrics": m,
                            "services": [service_status(rid, s) for s in SERVICES]}
    return {"regions": regions_out, "cross_region_matrix": matrix,
            "alerts": get_alerts(), "sla_thresholds": SLA,
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z"}


def region_detail(region_id: str) -> Optional[Dict]:
    if region_id not in REGIONS:
        return None
    info = REGIONS[region_id]
    history = [simulate_day_metrics(region_id, d) for d in range(30)]
    m = get_current_metrics(region_id)
    return {"region_id": region_id, **info, "current_metrics": m,
            "services": [service_status(region_id, s) for s in SERVICES],
            "30day_history": history}


try:
    from fastapi import FastAPI, HTTPException, Response
    import uvicorn
    app = FastAPI(title="OCI Network Topology Monitor", version="1.0.0")

    @app.get("/", response_class=Response)
    def dashboard(): return Response(content=build_dashboard(), media_type="text/html")

    @app.get("/topology")
    def topology(): return topology_json()

    @app.get("/regions/{region_id}")
    def region(region_id: str):
        d = region_detail(region_id)
        if d is None: raise HTTPException(status_code=404, detail=f"Region '{region_id}' not found")
        return d

    @app.get("/health")
    def health():
        alerts = get_alerts()
        return {"status": "ok" if not alerts else "degraded", "alert_count": len(alerts),
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}

    @app.get("/alerts")
    def alerts(): return {"alerts": get_alerts(), "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    app = None


if __name__ == "__main__":
    if FASTAPI_AVAILABLE:
        import uvicorn
        print("Starting OCI Network Topology Monitor on http://0.0.0.0:8096")
        uvicorn.run(app, host="0.0.0.0", port=8096, log_level="info")
    else:
        print("FastAPI not available — running CLI report\n")
        data = topology_json()
        print(json.dumps(data, indent=2))
        out = "/tmp/network_topology_report.html"
        with open(out, "w") as f: f.write(build_dashboard())
        print(f"\nHTML dashboard saved to {out}")

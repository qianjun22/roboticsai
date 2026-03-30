"""
OCI Robot Cloud — Fleet-Wide Health Dashboard
Port 8112 | Aggregates health from all 15 microservices
"""

import math, hashlib, random, datetime, json, collections

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

SERVICES = [
    {"name": "groot_inference",          "port": 8001, "uptime": 99.94, "last_check_ms": 226},
    {"name": "fine_tune_api",            "port": 8002, "uptime": 99.81, "last_check_ms": 180},
    {"name": "data_pipeline",            "port": 8003, "uptime": 99.95, "last_check_ms": 45},
    {"name": "eval_pipeline",            "port": 8004, "uptime": 99.72, "last_check_ms": 310},
    {"name": "gateway",                  "port": 8080, "uptime": 99.99, "last_check_ms": 12},
    {"name": "ab_testing",               "port": 8098, "uptime": 99.88, "last_check_ms": 88},
    {"name": "model_serving_router",     "port": 8099, "uptime": 98.21, "last_check_ms": 445},
    {"name": "perf_regression_detector", "port": 8100, "uptime": 99.90, "last_check_ms": 95},
    {"name": "deployment_scheduler",     "port": 8101, "uptime": 99.95, "last_check_ms": 67},
    {"name": "feature_flag_manager",     "port": 8102, "uptime": 99.99, "last_check_ms": 8},
    {"name": "rollback_controller",      "port": 8103, "uptime": 99.97, "last_check_ms": 22},
    {"name": "inference_cache_warmer",   "port": 8104, "uptime": 99.85, "last_check_ms": 134},
    {"name": "model_quality_gate",       "port": 8105, "uptime": 99.91, "last_check_ms": 78},
    {"name": "config_drift_detector",    "port": 8106, "uptime": 97.44, "last_check_ms": 502},
    {"name": "latency_profiler",         "port": 8107, "uptime": 99.88, "last_check_ms": 98},
]

STATUS_COLORS = {"HEALTHY": "#22c55e", "DEGRADED": "#f59e0b", "DOWN": "#ef4444"}


def compute_status(svc):
    if svc["uptime"] > 99.0 and svc["last_check_ms"] < 400: return "HEALTHY"
    if svc["uptime"] > 95.0: return "DEGRADED"
    return "DOWN"


def annotated_services():
    return [{**s, "status": compute_status(s)} for s in SERVICES]


def fleet_summary():
    svcs = annotated_services()
    counts = collections.Counter(s["status"] for s in svcs)
    return {"total": len(svcs), "healthy": counts.get("HEALTHY", 0), "degraded": counts.get("DEGRADED", 0),
            "down": counts.get("DOWN", 0), "fleet_score": round(sum(s["uptime"] for s in svcs) / len(svcs), 4),
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}


def build_svg_grid():
    svcs = annotated_services()
    w, h, cols = 700, 180, 5
    cell_w, cell_h = w // cols, h // 3
    parts = []
    for idx, svc in enumerate(svcs):
        cx = (idx % cols) * cell_w + cell_w // 2
        cy = (idx // cols) * cell_h + 26
        color = STATUS_COLORS[svc["status"]]
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="10" fill="{color}" opacity="0.9"/>')
        parts.append(f'<text x="{cx}" y="{cy+20}" text-anchor="middle" font-size="9" fill="#94a3b8" font-family="monospace">{svc["name"].replace("_"," ")}</text>')
        parts.append(f'<text x="{cx}" y="{cy+31}" text-anchor="middle" font-size="8" fill="#64748b" font-family="monospace">:{svc["port"]}</text>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#1e293b;border-radius:8px;">\n{chr(10).join(parts)}\n</svg>'


def _uptime_bar(u, w=120, h=14):
    fw = int(w * u / 100)
    c = "#22c55e" if u > 99 else ("#f59e0b" if u > 95 else "#ef4444")
    return f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg"><rect width="{w}" height="{h}" rx="3" fill="#0f172a"/><rect width="{fw}" height="{h}" rx="3" fill="{c}" opacity="0.85"/><text x="{w//2}" y="{h-3}" text-anchor="middle" font-size="9" fill="#f1f5f9" font-family="monospace">{u:.2f}%</text></svg>'


def build_html():
    svcs = annotated_services()
    summary = fleet_summary()
    grid_svg = build_svg_grid()
    sc = "#22c55e" if summary["fleet_score"] >= 99.5 else ("#f59e0b" if summary["fleet_score"] >= 97 else "#ef4444")

    banner = f'<div style="background:#1e293b;border-radius:10px;padding:20px 28px;margin-bottom:22px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;"><div><div style="color:#C74634;font-size:13px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;">Fleet Health Score</div><div style="color:{sc};font-size:48px;font-weight:800;line-height:1;">{summary["fleet_score"]:.2f}<span style="font-size:22px;color:#64748b;">%</span></div><div style="color:#94a3b8;font-size:12px;margin-top:6px;">{summary["timestamp"]}</div></div><div style="display:flex;gap:24px;"><div style="text-align:center;"><div style="color:#22c55e;font-size:36px;font-weight:700;">{summary["healthy"]}</div><div style="color:#94a3b8;font-size:11px;text-transform:uppercase;">Healthy</div></div><div style="text-align:center;"><div style="color:#f59e0b;font-size:36px;font-weight:700;">{summary["degraded"]}</div><div style="color:#94a3b8;font-size:11px;text-transform:uppercase;">Degraded</div></div><div style="text-align:center;"><div style="color:#ef4444;font-size:36px;font-weight:700;">{summary["down"]}</div><div style="color:#94a3b8;font-size:11px;text-transform:uppercase;">Down</div></div></div></div>'

    rows = "".join(
        f'<tr style="border-bottom:1px solid #0f172a;"><td style="padding:10px 12px;color:#38bdf8;font-family:monospace;font-size:13px;">{s["name"]}</td>'
        f'<td style="padding:10px 12px;color:#64748b;font-family:monospace;font-size:12px;">:{s["port"]}</td>'
        f'<td style="padding:10px 12px;"><span style="background:{STATUS_COLORS[s["status"]]}22;color:{STATUS_COLORS[s["status"]]};border:1px solid {STATUS_COLORS[s["status"]]}55;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:700;">{s["status"]}</span></td>'
        f'<td style="padding:10px 12px;">{_uptime_bar(s["uptime"])}</td>'
        f'<td style="padding:10px 12px;color:{"#22c55e" if s["last_check_ms"]<200 else ("#f59e0b" if s["last_check_ms"]<400 else "#ef4444")};font-family:monospace;font-size:13px;">{s["last_check_ms"]} ms</td></tr>'
        for s in svcs
    )
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>OCI Robot Cloud — Health Dashboard</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#f1f5f9;font-family:system-ui,sans-serif;}}h1{{color:#C74634;font-size:22px;font-weight:800;}}</style></head><body>
<div style="max-width:900px;margin:0 auto;padding:28px 20px;">
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;"><div><h1>OCI Robot Cloud</h1><div style="color:#94a3b8;font-size:13px;margin-top:4px;">Fleet-Wide Health Dashboard &mdash; 15 Microservices</div></div><div style="background:#1e293b;border-radius:8px;padding:8px 16px;color:#38bdf8;font-size:12px;font-family:monospace;">PORT 8112</div></div>
{banner}
<div style="background:#1e293b;border-radius:10px;padding:18px 20px;margin-bottom:22px;"><div style="color:#C74634;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px;">Service Status Grid</div>{grid_svg}<div style="display:flex;gap:18px;margin-top:10px;"><span style="color:#22c55e;font-size:11px;">&#9679; HEALTHY</span><span style="color:#f59e0b;font-size:11px;">&#9679; DEGRADED</span><span style="color:#ef4444;font-size:11px;">&#9679; DOWN</span></div></div>
<div style="background:#1e293b;border-radius:10px;overflow:hidden;"><div style="color:#C74634;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;padding:16px 20px;border-bottom:1px solid #0f172a;">Service Details</div>
<table style="width:100%;border-collapse:collapse;"><thead><tr style="background:#0f172a;"><th style="padding:10px 12px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;">Service</th><th style="padding:10px 12px;text-align:left;color:#64748b;font-size:11px;">Port</th><th style="padding:10px 12px;text-align:left;color:#64748b;font-size:11px;">Status</th><th style="padding:10px 12px;text-align:left;color:#64748b;font-size:11px;">Uptime</th><th style="padding:10px 12px;text-align:left;color:#64748b;font-size:11px;">Latency</th></tr></thead><tbody>{rows}</tbody></table></div>
<div style="text-align:center;color:#334155;font-size:11px;margin-top:28px;padding-top:16px;border-top:1px solid #1e293b;">Oracle Confidential | OCI Robot Cloud Health Dashboard | Port 8112</div></div></body></html>"""


if HAS_FASTAPI:
    app = FastAPI(title="OCI Robot Cloud — Health Dashboard", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def root(): return HTMLResponse(content=build_html())

    @app.get("/health")
    def health(): return JSONResponse({"status": "ok", "service": "health_dashboard", "port": 8112})

    @app.get("/services")
    def services(): return JSONResponse(annotated_services())

    @app.get("/services/{name}")
    def service_by_name(name: str):
        match = [s for s in annotated_services() if s["name"] == name]
        return JSONResponse(match[0] if match else {"error": f"Not found"}, status_code=200 if match else 404)

    @app.get("/summary")
    def summary(): return JSONResponse(fleet_summary())


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run("health_dashboard:app", host="0.0.0.0", port=8112, reload=False)
    else:
        out = "/tmp/health_dashboard.html"
        with open(out, "w") as f: f.write(build_html())
        print(f"Saved to {out}")
        print(json.dumps(fleet_summary(), indent=2))

"""
Multi-Model Serving Router with load balancing across GR00T variants.
Oracle Confidential — OCI Robot Cloud, Infrastructure Team.

FastAPI service on port 8099. Weighted round-robin routing across regional
GR00T N1.6 policy backends with health checks and a live dashboard.
"""

import math
import random
import hashlib
import datetime
from typing import Dict, Any, List

BACKENDS: Dict[str, Dict[str, Any]] = {
    "ashburn_prod": {"host": "138.1.153.110", "port": 8001, "model": "dagger_run9_v2.2", "region": "us-ashburn-1", "weight": 5, "healthy": True, "rps": 42.3, "latency_ms": 226, "error_rate": 0.003},
    "ashburn_canary": {"host": "138.1.153.110", "port": 8002, "model": "groot_finetune_v2", "region": "us-ashburn-1", "weight": 1, "healthy": True, "rps": 8.1, "latency_ms": 231, "error_rate": 0.002},
    "phoenix_eval": {"host": "10.0.1.42", "port": 8001, "model": "dagger_run9_v2.2", "region": "us-phoenix-1", "weight": 2, "healthy": True, "rps": 15.7, "latency_ms": 241, "error_rate": 0.005},
    "frankfurt_staging": {"host": "10.0.2.88", "port": 8001, "model": "dagger_run5", "region": "eu-frankfurt-1", "weight": 1, "healthy": False, "rps": 0.0, "latency_ms": 258, "error_rate": 0.041},
    "ashburn_shadow": {"host": "138.1.153.110", "port": 8003, "model": "bc_baseline", "region": "us-ashburn-1", "weight": 0, "healthy": True, "rps": 0.0, "latency_ms": 224, "error_rate": 0.012},
}


def weighted_round_robin(request_id: int) -> str:
    eligible = {name: cfg for name, cfg in BACKENDS.items() if cfg["healthy"] and cfg["weight"] > 0}
    if not eligible: raise RuntimeError("No healthy backends with weight > 0 available")
    total_weight = sum(cfg["weight"] for cfg in eligible.values())
    bucket = int(hashlib.md5(str(request_id).encode()).hexdigest(), 16) % total_weight
    cumulative = 0
    for name, cfg in eligible.items():
        cumulative += cfg["weight"]
        if bucket < cumulative: return name
    return list(eligible.keys())[-1]


def route_request(request_id: int, strategy: str = "wRR") -> Dict[str, Any]:
    if strategy != "wRR": raise ValueError(f"Unsupported strategy: {strategy}")
    backend_name = weighted_round_robin(request_id)
    cfg = BACKENDS[backend_name]
    jitter = random.Random(request_id ^ 0xDEAD).gauss(0, 5)
    est_latency = max(1, cfg["latency_ms"] + jitter)
    return {"request_id": request_id, "strategy": strategy, "backend": backend_name,
            "host": cfg["host"], "port": cfg["port"], "model": cfg["model"],
            "region": cfg["region"], "estimated_latency_ms": round(est_latency, 1)}


def traffic_summary() -> Dict[str, Any]:
    total_rps = sum(cfg["rps"] for cfg in BACKENDS.values())
    if total_rps > 0:
        weighted_lat = sum(cfg["latency_ms"] * cfg["rps"] for cfg in BACKENDS.values()) / total_rps
        weighted_err = sum(cfg["error_rate"] * cfg["rps"] for cfg in BACKENDS.values()) / total_rps
    else:
        hb = [cfg for cfg in BACKENDS.values() if cfg["healthy"]]
        weighted_lat = sum(c["latency_ms"] for c in hb) / len(hb) if hb else 0.0
        weighted_err = sum(c["error_rate"] for c in hb) / len(hb) if hb else 0.0
    n_healthy = sum(1 for cfg in BACKENDS.values() if cfg["healthy"])
    return {"total_rps": round(total_rps, 1), "avg_latency_ms": round(weighted_lat, 1),
            "total_error_rate": round(weighted_err, 4), "healthy_backends": n_healthy,
            "total_backends": len(BACKENDS), "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}


def health_check_all() -> Dict[str, Any]:
    per_backend = {name: {"healthy": cfg["healthy"], "model": cfg["model"], "region": cfg["region"],
                          "rps": cfg["rps"], "latency_ms": cfg["latency_ms"],
                          "error_rate": cfg["error_rate"], "weight": cfg["weight"]}
                   for name, cfg in BACKENDS.items()}
    n_healthy = sum(1 for cfg in BACKENDS.values() if cfg["healthy"])
    status = "OK" if n_healthy >= 2 else ("DEGRADED" if n_healthy == 1 else "DOWN")
    return {"aggregate_status": status, "healthy_count": n_healthy, "total_count": len(BACKENDS),
            "backends": per_backend, "checked_at": datetime.datetime.utcnow().isoformat() + "Z"}


def latency_histogram_svg(n_bins: int = 20) -> str:
    summary = traffic_summary()
    avg_lat = summary["avg_latency_ms"] if summary["avg_latency_ms"] > 0 else 230.0
    rng = random.Random(7)
    samples = [max(100, rng.gauss(avg_lat, 18.0)) for _ in range(500)]
    lo, hi = min(samples), max(samples); span = hi - lo or 1.0
    bin_w = span / n_bins; bins = [0] * n_bins
    for s in samples:
        bins[min(int((s - lo) / bin_w), n_bins - 1)] += 1
    W, H = 600, 280; pad_l, pad_b, pad_t, pad_r = 45, 50, 20, 20
    chart_w = W - pad_l - pad_r; chart_h = H - pad_b - pad_t
    bar_w = chart_w / n_bins - 1; max_count = max(bins) or 1
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;font-family:monospace">',
             f'<text x="{W//2}" y="14" text-anchor="middle" font-size="11" fill="#94a3b8">Request Latency Distribution (n=500)</text>']
    for yi in range(5):
        y_val = yi / 4; y_px = pad_t + chart_h * (1 - y_val)
        lines.append(f'<line x1="{pad_l}" y1="{y_px:.1f}" x2="{W-pad_r}" y2="{y_px:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{y_px+4:.1f}" text-anchor="end" font-size="9" fill="#94a3b8">{int(max_count*y_val)}</text>')
    for i, count in enumerate(bins):
        bar_h = chart_h * count / max_count
        bx = pad_l + i * (bar_w + 1); by = pad_t + chart_h - bar_h
        lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="#C74634" rx="1"/>')
    for xi in range(5):
        x_px = pad_l + chart_w * xi / 4; x_val = lo + span * xi / 4
        lines.append(f'<text x="{x_px:.1f}" y="{H-pad_b+14}" text-anchor="middle" font-size="9" fill="#94a3b8">{x_val:.0f}ms</text>')
    lines.append(f'<text x="{W//2}" y="{H-4}" text-anchor="middle" font-size="10" fill="#64748b">Latency (ms)</text></svg>')
    return "\n".join(lines)


def build_dashboard() -> str:
    summary = traffic_summary(); health = health_check_all(); svg = latency_histogram_svg()
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    status_color = {"OK": "#4ade80", "DEGRADED": "#facc15", "DOWN": "#f87171"}
    agg_color = status_color.get(health["aggregate_status"], "#94a3b8")
    table_rows = []
    for name, cfg in BACKENDS.items():
        badge_bg = "#166534" if cfg["healthy"] else "#7f1d1d"
        badge_text = "#4ade80" if cfg["healthy"] else "#f87171"
        badge_label = "HEALTHY" if cfg["healthy"] else "UNHEALTHY"
        row_style = 'style="background:#1e2d40"' if name == "ashburn_prod" else ""
        table_rows.append(f'<tr {row_style}><td style="padding:8px 12px;color:#38bdf8;font-weight:600">{name}</td><td style="padding:8px 12px;color:#94a3b8;font-size:11px">{cfg["host"]}:{cfg["port"]}</td><td style="padding:8px 12px;color:#e2e8f0">{cfg["model"]}</td><td style="padding:8px 12px;color:#94a3b8">{cfg["region"]}</td><td style="padding:8px 12px;color:#e2e8f0;text-align:right">{cfg["weight"]}</td><td style="padding:8px 12px;color:#e2e8f0;text-align:right">{cfg["rps"]:.1f}</td><td style="padding:8px 12px;color:#e2e8f0;text-align:right">{cfg["latency_ms"]}ms</td><td style="padding:8px 12px;color:#e2e8f0;text-align:right">{cfg["error_rate"]*100:.1f}%</td><td style="padding:8px 12px"><span style="background:{badge_bg};color:{badge_text};font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px">{badge_label}</span></td></tr>')
    err_color = "#f87171" if summary["total_error_rate"] > 0.01 else "#4ade80"
    healthy_color = "#4ade80" if health["healthy_count"] >= 3 else "#facc15"
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Model Serving Router \u2014 OCI Robot Cloud</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:24px}}
h1{{font-size:22px;font-weight:700;color:#f1f5f9}}h2{{font-size:14px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px}}
.chip{{display:inline-block;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:10px 18px;margin:4px}}
.chip-label{{font-size:11px;color:#94a3b8}}.chip-value{{font-size:20px;font-weight:700;color:#38bdf8}}
.section{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:20px;margin-bottom:20px;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;min-width:700px}}th{{background:#0f172a;color:#94a3b8;font-size:11px;text-transform:uppercase;padding:8px 12px;text-align:left;border-bottom:1px solid #334155}}
tr:hover td{{background:#1a2840!important}}.footer{{color:#475569;font-size:11px;text-align:center;margin-top:24px}}</style></head><body>
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
<div><h1>Model Serving Router</h1><div style="color:#64748b;font-size:12px;margin-top:4px">GR00T N1.6 Weighted Round-Robin \u00b7 {now}</div></div>
<div style="background:{agg_color};color:#0f172a;font-size:11px;font-weight:700;padding:6px 14px;border-radius:20px">{health["aggregate_status"]}</div></div>
<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px">
<div class="chip"><div class="chip-label">Total RPS</div><div class="chip-value">{summary["total_rps"]:.1f}</div></div>
<div class="chip"><div class="chip-label">Avg Latency</div><div class="chip-value">{summary["avg_latency_ms"]:.0f}ms</div></div>
<div class="chip"><div class="chip-label">Healthy Backends</div><div class="chip-value" style="color:{healthy_color}">{health["healthy_count"]}/{health["total_count"]}</div></div>
<div class="chip"><div class="chip-label">Error Rate</div><div class="chip-value" style="color:{err_color}">{summary["total_error_rate"]*100:.2f}%</div></div></div>
<div class="section"><h2>Latency Distribution</h2>{svg}</div>
<div class="section"><h2>Backend Routing Table</h2>
<table><thead><tr><th>Name</th><th>Host:Port</th><th>Model</th><th>Region</th><th>Weight</th><th>RPS</th><th>Latency</th><th>Error %</th><th>Status</th></tr></thead>
<tbody>{" ".join(table_rows)}</tbody></table></div>
<div class="footer">Oracle Confidential \u00b7 OCI Robot Cloud \u00b7 Model Serving Router \u00b7 Port 8099</div>
</body></html>"""


try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    app = FastAPI(title="OCI Robot Cloud \u2014 Model Serving Router", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(): return build_dashboard()

    @app.get("/route/{request_id}")
    async def route(request_id: int, strategy: str = Query(default="wRR")):
        try: return JSONResponse(route_request(request_id, strategy))
        except (RuntimeError, ValueError) as exc: return JSONResponse({"error": str(exc)}, status_code=503)

    @app.get("/backends")
    async def backends(): return JSONResponse(BACKENDS)

    @app.get("/health")
    async def health(): return JSONResponse(health_check_all())

    @app.get("/traffic")
    async def traffic(): return JSONResponse(traffic_summary())

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False; app = None


if __name__ == "__main__":
    if FASTAPI_AVAILABLE:
        import uvicorn; uvicorn.run(app, host="0.0.0.0", port=8099)
    else:
        h = health_check_all(); s = traffic_summary()
        print(f"Status: {h['aggregate_status']}  Healthy: {h['healthy_count']}/{h['total_count']}  RPS: {s['total_rps']}  Lat: {s['avg_latency_ms']}ms")
        for name, cfg in BACKENDS.items():
            print(f"  {name:<22} {cfg['model']:<22} w={cfg['weight']} {'OK' if cfg['healthy'] else 'DOWN'}")
        with open("/tmp/model_serving_router.html", "w") as f: f.write(build_dashboard())
        print("Dashboard saved to /tmp/model_serving_router.html")

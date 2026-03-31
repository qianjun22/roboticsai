"""
Real-time OCI spend tracking — GPU + storage + network + inference cost breakdown.
FastAPI service — OCI Robot Cloud
Port: 10081
"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime, timedelta
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10081

# ---------------------------------------------------------------------------
# Cost model constants (USD)
# ---------------------------------------------------------------------------

# OCI A100 GPU instance: ~$3.40/h per GPU (BM.GPU.A100-v2.8 = $27.20/h / 8 GPUs)
GPU_COST_PER_GPU_HOUR = 3.40
# Block storage: $0.0255/GB-month → per hour
STORAGE_COST_PER_GB_HOUR = 0.0255 / (30 * 24)
# Outbound network: $0.0085/GB
NETWORK_COST_PER_GB = 0.0085
# Inference API call: cost per 1k calls
INFERENCE_COST_PER_1K_CALLS = 0.04

# Target gross margin
TARGET_MARGIN = 0.65

# Simulated per-service resource footprint
SERVICES = [
    {"name": "gr00t_inference",         "gpus": 2, "storage_gb": 120, "net_gb_day": 8.5,  "api_calls_day": 14200},
    {"name": "fine_tune_pipeline",       "gpus": 4, "storage_gb": 350, "net_gb_day": 2.1,  "api_calls_day": 320},
    {"name": "dagger_training",          "gpus": 1, "storage_gb": 80,  "net_gb_day": 0.9,  "api_calls_day": 150},
    {"name": "data_collection_api",      "gpus": 0, "storage_gb": 600, "net_gb_day": 15.0, "api_calls_day": 32000},
    {"name": "closed_loop_eval",         "gpus": 1, "storage_gb": 40,  "net_gb_day": 1.2,  "api_calls_day": 2800},
    {"name": "task_sequencing_optimizer","gpus": 0, "storage_gb": 10,  "net_gb_day": 0.3,  "api_calls_day": 5400},
    {"name": "model_registry",           "gpus": 0, "storage_gb": 900, "net_gb_day": 4.0,  "api_calls_day": 1100},
    {"name": "sim_to_real_validator",    "gpus": 1, "storage_gb": 55,  "net_gb_day": 0.7,  "api_calls_day": 480},
]


def _period_hours(period: str) -> int:
    """Convert period string to hours."""
    mapping = {
        "1h": 1, "6h": 6, "12h": 12,
        "1d": 24, "7d": 168, "30d": 720, "90d": 2160
    }
    p = period.lower().strip()
    if p not in mapping:
        raise ValueError(f"Unknown period '{period}'. Valid: {list(mapping)}")
    return mapping[p]


def _service_cost(svc: dict, hours: int) -> dict:
    """Compute cost breakdown for a single service over `hours`."""
    gpu_cost    = svc["gpus"] * GPU_COST_PER_GPU_HOUR * hours
    storage_cost = svc["storage_gb"] * STORAGE_COST_PER_GB_HOUR * hours
    days         = hours / 24
    net_cost     = svc["net_gb_day"] * days * NETWORK_COST_PER_GB
    inf_cost     = svc["api_calls_day"] * days * INFERENCE_COST_PER_1K_CALLS / 1000
    total        = gpu_cost + storage_cost + net_cost + inf_cost

    # Add ±3% noise to simulate real billing granularity
    noise = random.uniform(0.97, 1.03)
    total = round(total * noise, 4)
    return {
        "service": svc["name"],
        "gpu_cost_usd": round(gpu_cost, 4),
        "storage_cost_usd": round(storage_cost, 4),
        "network_cost_usd": round(net_cost, 4),
        "inference_cost_usd": round(inf_cost, 4),
        "total_cost_usd": total
    }


def _aggregate_breakdown(per_service: list[dict]) -> dict:
    """Aggregate per-service costs into a category breakdown."""
    return {
        "gpu_cost_usd":       round(sum(s["gpu_cost_usd"]       for s in per_service), 4),
        "storage_cost_usd":   round(sum(s["storage_cost_usd"]   for s in per_service), 4),
        "network_cost_usd":   round(sum(s["network_cost_usd"]   for s in per_service), 4),
        "inference_cost_usd": round(sum(s["inference_cost_usd"] for s in per_service), 4),
    }


def _margin_health(total_cost: float, period: str) -> dict:
    """Estimate margin health based on simulated revenue."""
    # Simulated revenue: based on API calls across all services
    hours = _period_hours(period)
    days = hours / 24
    total_api_calls = sum(s["api_calls_day"] for s in SERVICES) * days
    # $0.12 per 1k calls blended revenue
    revenue = total_api_calls * 0.12 / 1000
    gross_profit = revenue - total_cost
    margin = gross_profit / revenue if revenue > 0 else 0.0
    return {
        "revenue_usd": round(revenue, 2),
        "gross_profit_usd": round(gross_profit, 2),
        "gross_margin_pct": round(margin * 100, 1),
        "target_margin_pct": round(TARGET_MARGIN * 100, 1),
        "margin_status": "healthy" if margin >= TARGET_MARGIN else ("warning" if margin >= 0.50 else "critical")
    }


def _optimization_opportunities(per_service: list[dict], hours: int) -> list[dict]:
    """Identify cost optimization opportunities."""
    opportunities = []
    for s in per_service:
        if s["storage_cost_usd"] > s["gpu_cost_usd"] * 2 and s["storage_cost_usd"] > 0.5:
            savings = round(s["storage_cost_usd"] * 0.30, 4)
            opportunities.append({
                "service": s["service"],
                "type": "storage_tiering",
                "description": f"Move cold data to OCI Archive Storage (30% savings estimate)",
                "estimated_savings_usd": savings
            })
        if s["gpu_cost_usd"] > 5.0:
            savings = round(s["gpu_cost_usd"] * 0.20, 4)
            opportunities.append({
                "service": s["service"],
                "type": "gpu_spot_instances",
                "description": "Use OCI preemptible GPU instances for non-latency-critical workloads (20% savings)",
                "estimated_savings_usd": savings
            })
        if s["inference_cost_usd"] > 2.0:
            savings = round(s["inference_cost_usd"] * 0.15, 4)
            opportunities.append({
                "service": s["service"],
                "type": "inference_batching",
                "description": "Increase inference batch size to reduce per-call overhead (15% savings)",
                "estimated_savings_usd": savings
            })
    # Deduplicate by type+service
    seen = set()
    unique = []
    for o in opportunities:
        key = (o["service"], o["type"])
        if key not in seen:
            seen.add(key)
            unique.append(o)
    return sorted(unique, key=lambda x: -x["estimated_savings_usd"])[:8]


def _forecast(horizon_months: int) -> dict:
    """Project costs and margin over a future horizon."""
    # Monthly baseline from 30-day cost
    hours_30d = 720
    per_service_30d = [_service_cost(s, hours_30d) for s in SERVICES]
    monthly_cost = sum(s["total_cost_usd"] for s in per_service_30d)

    # Assume 8% MoM growth in usage, 2% MoM cost efficiency improvement
    USAGE_GROWTH = 0.08
    EFFICIENCY_IMPROVEMENT = 0.02

    projections = []
    base_date = datetime.utcnow().replace(day=1)
    for m in range(1, horizon_months + 1):
        cost = monthly_cost * ((1 + USAGE_GROWTH - EFFICIENCY_IMPROVEMENT) ** m)
        revenue = cost / (1 - TARGET_MARGIN) * ((1 + USAGE_GROWTH) ** m)
        margin = (revenue - cost) / revenue if revenue > 0 else 0.0
        proj_month = (base_date + timedelta(days=30 * m)).strftime("%Y-%m")
        projections.append({
            "month": proj_month,
            "projected_cost_usd": round(cost, 2),
            "projected_revenue_usd": round(revenue, 2),
            "projected_margin_pct": round(margin * 100, 1)
        })

    total_projected = sum(p["projected_cost_usd"] for p in projections)
    avg_margin = round(sum(p["projected_margin_pct"] for p in projections) / len(projections), 1)
    return {
        "horizon_months": horizon_months,
        "monthly_projections": projections,
        "total_projected_cost_usd": round(total_projected, 2),
        "average_projected_margin_pct": avg_margin,
        "assumptions": {
            "usage_growth_mom_pct": USAGE_GROWTH * 100,
            "efficiency_improvement_mom_pct": EFFICIENCY_IMPROVEMENT * 100,
            "target_margin_pct": TARGET_MARGIN * 100
        }
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="OCI Cost Dashboard", version="1.0.0")

    @app.get("/oci/cost_dashboard")
    def cost_dashboard(period: str = Query(default="1d", description="Time window: 1h,6h,12h,1d,7d,30d,90d")):
        try:
            hours = _period_hours(period)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        per_service = [_service_cost(s, hours) for s in SERVICES]
        breakdown = _aggregate_breakdown(per_service)
        total_cost = round(sum(s["total_cost_usd"] for s in per_service), 4)
        margin = _margin_health(total_cost, period)
        opps = _optimization_opportunities(per_service, hours)
        total_savings = round(sum(o["estimated_savings_usd"] for o in opps), 4)

        return JSONResponse({
            "period": period,
            "total_cost_usd": total_cost,
            "breakdown": {
                **breakdown,
                "breakdown_pct": {
                    k.replace("_usd", "_pct"): round(v / total_cost * 100, 1) if total_cost > 0 else 0
                    for k, v in breakdown.items()
                }
            },
            "per_service": sorted(per_service, key=lambda x: -x["total_cost_usd"]),
            "margin": margin,
            "optimization_opportunities": opps,
            "potential_savings_usd": total_savings,
            "ts": datetime.utcnow().isoformat()
        })

    @app.get("/oci/cost_forecast")
    def cost_forecast(
        horizon_months: int = Query(default=3, ge=1, le=24, description="Forecast horizon in months")
    ):
        result = _forecast(horizon_months)
        result["ts"] = datetime.utcnow().isoformat()
        return JSONResponse(result)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "oci_cost_dashboard", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>OCI Cost Dashboard</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}
svg{display:block;margin:1rem 0}</style></head><body>
<h1>OCI Cost Dashboard</h1><p>OCI Robot Cloud · Port 10081</p>
<div class="stat"><b>Tracked Services</b><br>8</div>
<div class="stat"><b>Cost Categories</b><br>GPU · Storage · Network · Inference</div>
<div class="stat"><b>Status</b><br>Online</div>
<svg width="300" height="80" viewBox="0 0 300 80">
  <rect width="300" height="80" fill="#1e293b" rx="8"/>
  <rect x="10" y="50" width="40" height="20" fill="#C74634" rx="3"/>
  <rect x="60" y="35" width="40" height="35" fill="#C74634" rx="3"/>
  <rect x="110" y="20" width="40" height="50" fill="#C74634" rx="3"/>
  <rect x="160" y="10" width="40" height="60" fill="#38bdf8" rx="3"/>
  <rect x="210" y="25" width="40" height="45" fill="#38bdf8" rx="3"/>
  <text x="150" y="76" fill="#94a3b8" font-size="9" text-anchor="middle">spend by service</text>
</svg>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/oci/cost_dashboard">Dashboard (1d)</a></p>
</body></html>""")

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)
else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())
        def log_message(self, *a): pass
    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

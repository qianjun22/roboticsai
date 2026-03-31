"""
Sales pipeline velocity tracker — velocity = (deals × win_rate × ACV) / cycle_time.
FastAPI service — OCI Robot Cloud
Port: 10077
"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10077

# ---------------------------------------------------------------------------
# Domain logic — sales pipeline velocity
# Velocity = (Number of Deals × Win Rate × Average Contract Value) / Sales Cycle Length
# ---------------------------------------------------------------------------

# Simulated pipeline stage data (seeded for reproducibility in demos)
PIPELINE_STAGES = [
    "prospecting",
    "qualification",
    "solution_design",
    "proposal",
    "negotiation",
    "closed_won",
    "closed_lost",
]

# Historical baseline metrics per period type
BASELINE_METRICS: Dict[str, Dict[str, float]] = {
    "weekly": {
        "avg_deals_entered": 18.0,
        "win_rate": 0.24,
        "avg_acv_usd": 142_000.0,
        "avg_cycle_days": 87.0,
    },
    "monthly": {
        "avg_deals_entered": 74.0,
        "win_rate": 0.24,
        "avg_acv_usd": 142_000.0,
        "avg_cycle_days": 87.0,
    },
    "quarterly": {
        "avg_deals_entered": 220.0,
        "win_rate": 0.24,
        "avg_acv_usd": 142_000.0,
        "avg_cycle_days": 87.0,
    },
}

# Stage-level conversion rates and average dwell time (days)
STAGE_STATS: Dict[str, Dict[str, float]] = {
    "prospecting":    {"conversion_rate": 0.52, "avg_dwell_days": 8.0,  "deal_count_pct": 0.28},
    "qualification":  {"conversion_rate": 0.61, "avg_dwell_days": 12.0, "deal_count_pct": 0.22},
    "solution_design":{"conversion_rate": 0.70, "avg_dwell_days": 18.0, "deal_count_pct": 0.18},
    "proposal":       {"conversion_rate": 0.58, "avg_dwell_days": 14.0, "deal_count_pct": 0.15},
    "negotiation":    {"conversion_rate": 0.72, "avg_dwell_days": 16.0, "deal_count_pct": 0.10},
    "closed_won":     {"conversion_rate": 1.00, "avg_dwell_days": 2.0,  "deal_count_pct": 0.04},
    "closed_lost":    {"conversion_rate": 0.00, "avg_dwell_days": 1.0,  "deal_count_pct": 0.03},
}

VELOCITY_LEVERS = [
    "deal_volume",
    "win_rate",
    "acv",
    "cycle_time",
]


def _add_noise(value: float, pct: float = 0.05) -> float:
    """Add small random noise to simulate real-world variance."""
    return value * (1.0 + random.gauss(0, pct))


def compute_velocity(
    deals: float,
    win_rate: float,
    acv_usd: float,
    cycle_days: float,
) -> float:
    """Core pipeline velocity formula: (deals × win_rate × ACV) / cycle_days."""
    if cycle_days <= 0:
        return 0.0
    return (deals * win_rate * acv_usd) / cycle_days


def _identify_bottleneck() -> Dict[str, Any]:
    """Find the pipeline stage with the worst efficiency score."""
    scores = {}
    for stage, stats in STAGE_STATS.items():
        if stage in ("closed_won", "closed_lost"):
            continue
        # Efficiency = conversion_rate / avg_dwell_days (higher is better)
        efficiency = stats["conversion_rate"] / stats["avg_dwell_days"]
        scores[stage] = {
            "efficiency": round(efficiency, 4),
            "conversion_rate": stats["conversion_rate"],
            "avg_dwell_days": stats["avg_dwell_days"],
            "deal_count_pct": stats["deal_count_pct"],
        }

    worst_stage = min(scores, key=lambda s: scores[s]["efficiency"])
    return {
        "worst_stage": worst_stage,
        "stage_scores": scores,
        "recommendation": (
            f"Focus on '{worst_stage}': "
            f"conversion rate {scores[worst_stage]['conversion_rate']:.0%}, "
            f"avg dwell {scores[worst_stage]['avg_dwell_days']:.0f} days. "
            "Consider targeted coaching and deal inspection cadence."
        ),
    }


def _build_trend(period: str, base_velocity: float) -> List[Dict[str, Any]]:
    """Generate a synthetic trend of velocity over past 6 periods."""
    trend = []
    v = base_velocity * random.uniform(0.78, 0.88)  # start lower
    for i in range(6):
        # Gradual upward trend with noise
        v = v * random.uniform(1.02, 1.07)
        trend.append({
            "period_offset": -(5 - i),
            "velocity_per_day": round(v, 2),
            "label": f"{period} -{5 - i}" if i < 5 else f"{period} (current)",
        })
    return trend


def get_pipeline_velocity(period: str) -> Dict[str, Any]:
    """Compute pipeline velocity and analysis for the given period."""
    period = period.lower()
    if period not in BASELINE_METRICS:
        period = "monthly"  # default fallback

    bm = BASELINE_METRICS[period]
    deals = _add_noise(bm["avg_deals_entered"], 0.08)
    win_rate = max(0.05, min(0.95, _add_noise(bm["win_rate"], 0.06)))
    acv = _add_noise(bm["avg_acv_usd"], 0.07)
    cycle_days = max(30.0, _add_noise(bm["avg_cycle_days"], 0.05))

    velocity = compute_velocity(deals, win_rate, acv, cycle_days)
    bottleneck = _identify_bottleneck()
    trend = _build_trend(period, velocity)

    # Quarter-over-quarter velocity change
    qoq_change_pct = round(
        (velocity - trend[-2]["velocity_per_day"]) / trend[-2]["velocity_per_day"] * 100, 1
    ) if len(trend) >= 2 else 0.0

    return {
        "period": period,
        "velocity_per_day": round(velocity, 2),
        "components": {
            "deals": round(deals, 1),
            "win_rate": round(win_rate, 4),
            "acv_usd": round(acv, 2),
            "cycle_days": round(cycle_days, 1),
        },
        "trend": trend,
        "qoq_change_pct": qoq_change_pct,
        "bottleneck": bottleneck,
        "stage_breakdown": {
            stage: {
                "estimated_deals": round(deals * stats["deal_count_pct"], 1),
                "conversion_rate": stats["conversion_rate"],
                "avg_dwell_days": stats["avg_dwell_days"],
            }
            for stage, stats in STAGE_STATS.items()
        },
        "ts": datetime.utcnow().isoformat(),
    }


def simulate_velocity_lever(
    lever: str,
    change_pct: float,
    period: str = "monthly",
) -> Dict[str, Any]:
    """
    Simulate the impact of changing one velocity lever by change_pct%.
    Returns projected velocity impact and sensitivity analysis.
    """
    period = period.lower()
    if period not in BASELINE_METRICS:
        period = "monthly"

    bm = BASELINE_METRICS[period]
    deals = bm["avg_deals_entered"]
    win_rate = bm["win_rate"]
    acv = bm["avg_acv_usd"]
    cycle_days = bm["avg_cycle_days"]
    base_velocity = compute_velocity(deals, win_rate, acv, cycle_days)

    lever = lever.lower()
    multiplier = 1.0 + change_pct / 100.0

    if lever == "deal_volume":
        new_velocity = compute_velocity(deals * multiplier, win_rate, acv, cycle_days)
        lever_description = f"Increase deal volume by {change_pct:+.1f}%"
    elif lever == "win_rate":
        new_win_rate = max(0.01, min(0.99, win_rate * multiplier))
        new_velocity = compute_velocity(deals, new_win_rate, acv, cycle_days)
        lever_description = f"Improve win rate by {change_pct:+.1f}% (abs: {new_win_rate:.1%})"
    elif lever == "acv":
        new_velocity = compute_velocity(deals, win_rate, acv * multiplier, cycle_days)
        lever_description = f"Increase ACV by {change_pct:+.1f}%"
    elif lever == "cycle_time":
        # Reducing cycle time (negative change_pct) improves velocity
        new_cycle_days = max(10.0, cycle_days * multiplier)
        new_velocity = compute_velocity(deals, win_rate, acv, new_cycle_days)
        lever_description = f"Change cycle time by {change_pct:+.1f}%"
    else:
        return {
            "error": f"Unknown lever '{lever}'. Valid options: {VELOCITY_LEVERS}",
            "valid_levers": VELOCITY_LEVERS,
        }

    velocity_delta = new_velocity - base_velocity
    velocity_impact_pct = round((velocity_delta / base_velocity) * 100, 2) if base_velocity else 0.0
    annual_revenue_impact = round(velocity_delta * 365, 2)

    # Sensitivity: how much does a 1% change in each lever move velocity?
    sensitivities = {}
    for lv in VELOCITY_LEVERS:
        m = 1.01  # +1% test
        if lv == "deal_volume":
            v_test = compute_velocity(deals * m, win_rate, acv, cycle_days)
        elif lv == "win_rate":
            v_test = compute_velocity(deals, min(0.99, win_rate * m), acv, cycle_days)
        elif lv == "acv":
            v_test = compute_velocity(deals, win_rate, acv * m, cycle_days)
        elif lv == "cycle_time":
            v_test = compute_velocity(deals, win_rate, acv, max(10, cycle_days * m))
        else:
            v_test = base_velocity
        sensitivities[lv] = round((v_test - base_velocity) / base_velocity * 100, 3)

    return {
        "lever": lever,
        "change_pct": change_pct,
        "lever_description": lever_description,
        "period": period,
        "baseline_velocity_per_day": round(base_velocity, 2),
        "projected_velocity_per_day": round(new_velocity, 2),
        "velocity_delta": round(velocity_delta, 2),
        "projected_velocity_impact_pct": velocity_impact_pct,
        "projected_annual_revenue_impact_usd": annual_revenue_impact,
        "sensitivity_per_1pct_change": sensitivities,
        "recommendation": (
            f"{lever_description} → velocity {'+' if velocity_delta >= 0 else ''}{velocity_delta:.2f}/day "
            f"({velocity_impact_pct:+.1f}%), "
            f"annual impact: ${annual_revenue_impact:,.0f}"
        ),
        "ts": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Pipeline Velocity Tracker",
        version="1.0.0",
        description="Sales pipeline velocity analytics: velocity = (deals × win_rate × ACV) / cycle_time.",
    )

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "pipeline_velocity_tracker",
            "port": PORT,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>Pipeline Velocity Tracker</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}
svg{display:block;margin:1rem 0}</style></head><body>
<h1>Pipeline Velocity Tracker</h1><p>OCI Robot Cloud · Port 10077</p>
<div class="stat"><b>Status</b><br>Online</div>
<div class="stat"><b>Formula</b><br>(Deals × Win Rate × ACV) / Cycle</div>
<div class="stat"><b>Periods</b><br>weekly / monthly / quarterly</div>
<svg width="300" height="80" viewBox="0 0 300 80">
  <rect width="300" height="80" fill="#1e293b" rx="8"/>
  <rect x="10" y="50" width="40" height="20" fill="#C74634" rx="3"/>
  <rect x="60" y="35" width="40" height="35" fill="#C74634" rx="3"/>
  <rect x="110" y="20" width="40" height="50" fill="#C74634" rx="3"/>
  <rect x="160" y="10" width="40" height="60" fill="#38bdf8" rx="3"/>
  <rect x="210" y="25" width="40" height="45" fill="#38bdf8" rx="3"/>
  <text x="150" y="76" fill="#94a3b8" font-size="9" text-anchor="middle">pipeline velocity trend</text>
</svg>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a></p>
</body></html>""")

    @app.get("/sales/velocity")
    def sales_velocity(
        period: str = Query(default="monthly", description="Period: weekly | monthly | quarterly"),
    ):
        """
        Compute sales pipeline velocity for the given period.

        Returns velocity per day, component breakdown (deals, win rate, ACV, cycle time),
        6-period trend, period-over-period change, and stage bottleneck analysis.
        """
        if period.lower() not in BASELINE_METRICS:
            return JSONResponse(
                status_code=422,
                content={"error": f"Invalid period '{period}'. Choose from: {list(BASELINE_METRICS.keys())}"},
            )
        return JSONResponse(get_pipeline_velocity(period))

    @app.get("/sales/velocity_levers")
    def velocity_levers(
        lever: str = Query(..., description="Lever to change: deal_volume | win_rate | acv | cycle_time"),
        change_pct: float = Query(..., description="Percentage change to simulate (e.g., 10 for +10%, -15 for -15%)"),
        period: str = Query(default="monthly", description="Baseline period: weekly | monthly | quarterly"),
    ):
        """
        Simulate the projected velocity impact of changing a single sales lever.

        Supports deal_volume, win_rate, acv, and cycle_time. Returns projected velocity,
        delta, annual revenue impact, and sensitivity analysis for all levers.
        """
        if abs(change_pct) > 200:
            return JSONResponse(
                status_code=422,
                content={"error": "change_pct magnitude must be <= 200%"},
            )
        result = simulate_velocity_lever(lever, change_pct, period)
        if "error" in result:
            return JSONResponse(status_code=422, content=result)
        return JSONResponse(result)

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

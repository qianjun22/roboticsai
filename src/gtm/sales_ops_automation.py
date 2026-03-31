"""
Sales ops automation — CRM hygiene, pipeline reporting, forecast roll-up, commission calculation
FastAPI service — OCI Robot Cloud
Port: 10093
"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10093

# --------------------------------------------------------------------------- #
# Simulated CRM data
# --------------------------------------------------------------------------- #

PIPELINE_STAGES = ["Prospecting", "Qualification", "Solution", "Proposal", "Negotiation", "Closed Won", "Closed Lost"]

STAGE_CLOSE_PROB = {
    "Prospecting": 0.05, "Qualification": 0.10, "Solution": 0.25,
    "Proposal": 0.45, "Negotiation": 0.75, "Closed Won": 1.0, "Closed Lost": 0.0,
}

REPS = {
    "R001": {"name": "Alice Chen",    "quota": 1_500_000, "region": "West"},
    "R002": {"name": "Bob Martinez",  "quota": 1_200_000, "region": "East"},
    "R003": {"name": "Carol Okonkwo", "quota": 1_800_000, "region": "EMEA"},
    "R004": {"name": "David Park",    "quota": 1_000_000, "region": "APAC"},
    "R005": {"name": "Eva Rossi",     "quota": 1_350_000, "region": "Central"},
}

ACCELERATOR_TIERS = [
    (0.00, 0.75,  0.80),   # < 75% quota → 80% rate
    (0.75, 1.00,  1.00),   # 75-100%     → 100% rate
    (1.00, 1.25,  1.20),   # 100-125%    → 120% accelerator
    (1.25, 1.50,  1.35),   # 125-150%    → 135% accelerator
    (1.50, math.inf, 1.50),# > 150%      → 150% accelerator
]


def _seed_for_period(period: str) -> int:
    return hash(period) & 0xFFFFFF


def _generate_opportunities(rep_id: str, period: str, count: int = 18) -> List[Dict]:
    """Deterministically generate a set of CRM opportunities for a rep + period."""
    rng = random.Random(_seed_for_period(period + rep_id))
    ops = []
    for i in range(count):
        stage = rng.choice(PIPELINE_STAGES)
        age_days = rng.randint(1, 180)
        amount = rng.randint(20, 500) * 1000
        expected = amount * STAGE_CLOSE_PROB[stage]
        ops.append({
            "opp_id": f"OPP-{rep_id}-{i:03d}",
            "stage": stage,
            "amount": amount,
            "expected_revenue": round(expected),
            "age_days": age_days,
            "close_date": (datetime.utcnow() + timedelta(days=rng.randint(-30, 90))).strftime("%Y-%m-%d"),
            "crm_hygiene_ok": rng.random() > 0.18,  # 82% hygiene rate
        })
    return ops


def _compute_pipeline_report(period: str) -> Dict:
    """Aggregate pipeline metrics across all reps for the given period."""
    rng = random.Random(_seed_for_period(period))
    stage_dist: Dict[str, Dict] = {s: {"count": 0, "total_amount": 0, "expected": 0} for s in PIPELINE_STAGES}
    at_risk: List[Dict] = []
    all_opps: List[Dict] = []

    for rep_id in REPS:
        ops = _generate_opportunities(rep_id, period)
        for o in ops:
            s = o["stage"]
            stage_dist[s]["count"] += 1
            stage_dist[s]["total_amount"] += o["amount"]
            stage_dist[s]["expected"] += o["expected_revenue"]
            if o["age_days"] > 90 and s not in ("Closed Won", "Closed Lost"):
                at_risk.append({"opp_id": o["opp_id"], "rep_id": rep_id, "stage": s,
                                "age_days": o["age_days"], "amount": o["amount"]})
            if not o["crm_hygiene_ok"]:
                o["hygiene_issue"] = rng.choice(["missing close date", "no next step",
                                                  "stale last activity", "no contact linked"])
            all_opps.append(o)

    total_pipeline = sum(v["total_amount"] for v in stage_dist.values())
    total_expected = sum(v["expected"] for v in stage_dist.values())
    avg_velocity = round(rng.uniform(28, 55), 1)  # days average sales cycle

    # Forecast roll-up: weighted expected + management override
    mgmt_override = round(total_expected * rng.uniform(0.95, 1.08))
    return {
        "period": period,
        "generated_at": datetime.utcnow().isoformat(),
        "stage_distribution": {
            s: {
                "count": v["count"],
                "total_amount": v["total_amount"],
                "expected_revenue": v["expected"],
                "close_probability": STAGE_CLOSE_PROB[s],
            }
            for s, v in stage_dist.items()
        },
        "velocity": {
            "avg_sales_cycle_days": avg_velocity,
            "deals_closing_30d": rng.randint(8, 20),
            "avg_deal_size": round(total_pipeline / max(len(all_opps), 1)),
        },
        "at_risk": at_risk[:10],  # top 10 at-risk deals
        "forecast": {
            "bottoms_up": total_expected,
            "management_override": mgmt_override,
            "commit": round(mgmt_override * 0.85),
            "upside": round(total_expected * 1.15),
        },
        "crm_hygiene": {
            "total_opps": len(all_opps),
            "hygiene_issues": sum(1 for o in all_opps if not o["crm_hygiene_ok"]),
            "hygiene_rate": round(sum(1 for o in all_opps if o["crm_hygiene_ok"]) / max(len(all_opps), 1) * 100, 1),
        },
    }


def _compute_commission(rep_id: str, period: str) -> Dict:
    """Calculate commission, accelerators, and breakdown for a sales rep."""
    if rep_id not in REPS:
        return None
    rep = REPS[rep_id]
    ops = _generate_opportunities(rep_id, period)
    won = [o for o in ops if o["stage"] == "Closed Won"]
    total_bookings = sum(o["amount"] for o in won)
    quota = rep["quota"]
    attainment = total_bookings / quota if quota else 0

    # Base commission rate: 10% of bookings
    BASE_RATE = 0.10

    # Find applicable accelerator tier
    accel_rate = 1.0
    for low, high, rate in ACCELERATOR_TIERS:
        if low <= attainment < high:
            accel_rate = rate
            break

    commission_base = total_bookings * BASE_RATE
    commission_total = commission_base * accel_rate

    # SPIFs / bonuses
    spif_bonus = sum(5000 for o in won if o["amount"] >= 200_000)  # $5k SPIF per large deal
    total_payout = commission_total + spif_bonus

    breakdown = [
        {"item": "Closed Won Bookings", "amount": total_bookings},
        {"item": f"Base Commission ({BASE_RATE*100:.0f}%)", "amount": round(commission_base)},
        {"item": f"Accelerator ({accel_rate:.2f}x)", "amount": round(commission_total - commission_base)},
        {"item": "SPIF Bonuses", "amount": spif_bonus},
        {"item": "Total Payout", "amount": round(total_payout)},
    ]

    return {
        "rep_id": rep_id,
        "rep_name": rep["name"],
        "region": rep["region"],
        "period": period,
        "quota": quota,
        "total_bookings": total_bookings,
        "attainment_pct": round(attainment * 100, 1),
        "commission_amount": round(total_payout),
        "breakdown": breakdown,
        "accelerators": {
            "tier_applied": f"{accel_rate:.2f}x",
            "attainment_band": f"{int(attainment*100)}% of quota",
            "spif_deals": len([o for o in won if o["amount"] >= 200_000]),
            "spif_bonus": spif_bonus,
        },
        "won_deals": len(won),
        "generated_at": datetime.utcnow().isoformat(),
    }


if USE_FASTAPI:
    app = FastAPI(title="Sales Ops Automation", version="1.0.0")

    class CommissionRequest(BaseModel):
        rep_id: str
        period: str  # e.g. "2026-Q1"

    @app.get("/salesops/pipeline_report")
    def pipeline_report(period: str = "2026-Q1"):
        """
        Generate weekly pipeline report for the given period.
        Returns stage_distribution, velocity, at_risk, and forecast roll-up.
        """
        report = _compute_pipeline_report(period)
        return report

    @app.post("/salesops/commission")
    def commission(req: CommissionRequest):
        """
        Calculate commission for a sales rep for the given period.
        Returns commission_amount, breakdown, and accelerator details.
        """
        result = _compute_commission(req.rep_id, req.period)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Rep '{req.rep_id}' not found. Valid IDs: {list(REPS.keys())}")
        return result

    @app.get("/salesops/reps")
    def list_reps():
        """List all sales reps with quota and region."""
        return {"reps": [
            {"rep_id": rid, **info} for rid, info in REPS.items()
        ]}

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "sales_ops_automation", "port": PORT,
                "ts": datetime.utcnow().isoformat(), "reps_tracked": len(REPS)}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>Sales Ops Automation</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}
svg{display:block;margin:1rem 0}</style></head><body>
<h1>Sales Ops Automation</h1><p>OCI Robot Cloud · Port 10093</p>
<div class="stat"><b>Pipeline Report</b><br>Stage dist + velocity + at-risk</div>
<div class="stat"><b>Commission Calc</b><br>Base + accelerators + SPIFs</div>
<div class="stat"><b>CRM Hygiene</b><br>Auto-flagging + 82% hygiene rate</div>
<svg width="300" height="80" viewBox="0 0 300 80">
  <rect width="300" height="80" fill="#1e293b" rx="8"/>
  <rect x="10" y="50" width="40" height="20" fill="#C74634" rx="3"/>
  <rect x="60" y="35" width="40" height="35" fill="#C74634" rx="3"/>
  <rect x="110" y="20" width="40" height="50" fill="#C74634" rx="3"/>
  <rect x="160" y="10" width="40" height="60" fill="#38bdf8" rx="3"/>
  <rect x="210" y="25" width="40" height="45" fill="#38bdf8" rx="3"/>
  <text x="150" y="72" fill="#94a3b8" font-size="9" text-anchor="middle">pipeline forecast metrics</text>
</svg>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/salesops/pipeline_report?period=2026-Q1">Pipeline Report</a> | <a href="/salesops/reps">Reps</a></p>
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

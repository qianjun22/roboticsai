"""
Net Revenue Retention expansion engine — NRR 118%→130% target.
FastAPI service — OCI Robot Cloud
Port: 10099
"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime, timedelta
from typing import Optional

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10099

# ── NRR domain constants ──────────────────────────────────────────────────────
CURRENT_NRR   = 1.18   # 118%
TARGET_NRR    = 1.30   # 130%
CHURN_RATE    = 0.04   # 4% gross churn
CONTRACTION   = 0.02   # 2% contraction (downgrades)

# Expansion playbook definitions
PLAYBOOKS = {
    "robot_expansion": {
        "name":        "Robot Fleet Expansion",
        "description": "Customer adds robot units to existing deployment",
        "avg_expansion_pct": 0.22,   # 22% ACV uplift per trigger
        "trigger":     "utilization > 80% for 14 consecutive days",
        "conversion_rate": 0.61,
        "median_days_to_close": 18,
        "nrr_contribution_pts": 4.2,  # percentage points to NRR
    },
    "new_use_case": {
        "name":        "New Use Case Adoption",
        "description": "Customer enables a second task type (e.g. pick→pack+sort)",
        "avg_expansion_pct": 0.35,
        "trigger":     "task_success_rate > 92% for 30 days",
        "conversion_rate": 0.48,
        "median_days_to_close": 32,
        "nrr_contribution_pts": 5.8,
    },
    "volume_growth": {
        "name":        "Volume / Data Tier Upgrade",
        "description": "Customer exceeds included demo quota; upsell data tier",
        "avg_expansion_pct": 0.15,
        "trigger":     "monthly_demos > 0.85 * included_quota",
        "conversion_rate": 0.74,
        "median_days_to_close": 9,
        "nrr_contribution_pts": 2.1,
    },
    "premium_upgrade": {
        "name":        "Premium Support & SLA Upgrade",
        "description": "Upsell to 99.9% SLA + dedicated CSE + priority fine-tune",
        "avg_expansion_pct": 0.28,
        "trigger":     "support_tickets > 5/month OR revenue_at_risk flag",
        "conversion_rate": 0.39,
        "median_days_to_close": 25,
        "nrr_contribution_pts": 3.9,
    },
}


def _compute_nrr(period_months: int = 12) -> dict:
    """Compute blended NRR and expansion breakdown for a rolling period."""
    # Simulate per-playbook expansion amounts across a synthetic customer base
    base_arr = 4_200_000  # $4.2M ARR (start of period)
    expansion_breakdown = {}
    total_expansion = 0.0

    for key, pb in PLAYBOOKS.items():
        # Expected expansions = base_arr * contribution over period
        raw_expansion = base_arr * (pb["nrr_contribution_pts"] / 100)
        # Add mild stochastic noise
        noise = random.uniform(-0.03, 0.03)
        expansion = round(raw_expansion * (1 + noise), 2)
        total_expansion += expansion
        expansion_breakdown[key] = {
            "playbook":          pb["name"],
            "expansion_arr":     expansion,
            "contribution_pts":  round(pb["nrr_contribution_pts"] * (1 + noise), 2),
            "conversion_rate":   pb["conversion_rate"],
            "median_days_close": pb["median_days_to_close"],
        }

    churn_arr       = round(base_arr * CHURN_RATE, 2)
    contraction_arr = round(base_arr * CONTRACTION, 2)
    net_expansion   = round(total_expansion - churn_arr - contraction_arr, 2)
    nrr_pct         = round((base_arr + net_expansion) / base_arr * 100, 2)

    return {
        "period_months":      period_months,
        "beginning_arr":      base_arr,
        "expansion_arr":      round(total_expansion, 2),
        "churn_arr":          churn_arr,
        "contraction_arr":    contraction_arr,
        "net_expansion_arr":  net_expansion,
        "ending_arr":         round(base_arr + net_expansion, 2),
        "nrr_pct":            nrr_pct,
        "current_nrr_pct":    CURRENT_NRR * 100,
        "target_nrr_pct":     TARGET_NRR * 100,
        "gap_to_target_pts":  round(TARGET_NRR * 100 - nrr_pct, 2),
        "expansion_breakdown": expansion_breakdown,
        "ts":                 datetime.utcnow().isoformat(),
    }


def _nrr_forecast(target_nrr: float) -> dict:
    """Given a target NRR%, compute required additional expansions and timeline."""
    base_arr          = 4_200_000
    current_expansion = base_arr * (CURRENT_NRR - 1 + CHURN_RATE + CONTRACTION)
    required_ending   = base_arr * target_nrr
    required_expansion = required_ending - base_arr + base_arr * (CHURN_RATE + CONTRACTION)
    additional_needed  = max(0, required_expansion - current_expansion)

    # Allocate additional expansion across playbooks weighted by NRR contribution
    total_pts = sum(pb["nrr_contribution_pts"] for pb in PLAYBOOKS.values())
    playbook_targets = {}
    total_days = 0
    for key, pb in PLAYBOOKS.items():
        weight   = pb["nrr_contribution_pts"] / total_pts
        add_arr  = round(additional_needed * weight, 2)
        # Additional customers to convert
        avg_deal = base_arr * pb["avg_expansion_pct"] * 0.12  # ~12% of base
        add_deals = math.ceil(add_arr / max(avg_deal, 1))
        days_needed = math.ceil(add_deals / pb["conversion_rate"]) * pb["median_days_to_close"]
        playbook_targets[key] = {
            "playbook":            pb["name"],
            "additional_arr":      add_arr,
            "additional_deals":    add_deals,
            "estimated_days":      days_needed,
        }
        total_days = max(total_days, days_needed)

    target_date = (datetime.utcnow() + timedelta(days=total_days)).strftime("%Y-%m-%d")
    return {
        "target_nrr_pct":        round(target_nrr * 100, 1),
        "current_nrr_pct":       CURRENT_NRR * 100,
        "additional_expansion":  round(additional_needed, 2),
        "required_expansions":   playbook_targets,
        "estimated_days_to_target": total_days,
        "estimated_target_date": target_date,
        "ts":                    datetime.utcnow().isoformat(),
    }


if USE_FASTAPI:
    app = FastAPI(title="NRR Expansion Engine", version="1.0.0")

    @app.get("/finance/nrr")
    def get_nrr(period: int = Query(default=12, ge=1, le=36, description="Rolling period in months")):
        """Return NRR%, expansion breakdown by playbook, churn, contraction, and net expansion."""
        return _compute_nrr(period_months=period)

    @app.get("/finance/nrr_forecast")
    def get_nrr_forecast(
        target_nrr: float = Query(default=1.30, ge=1.0, le=2.0, description="Target NRR as a decimal, e.g. 1.30 for 130%")
    ):
        """Given a target NRR, return required expansions per playbook and estimated timeline."""
        return _nrr_forecast(target_nrr=target_nrr)

    @app.get("/finance/playbooks")
    def list_playbooks():
        """Return all expansion playbooks with trigger logic and conversion metrics."""
        return {
            "playbooks":    PLAYBOOKS,
            "current_nrr":  CURRENT_NRR,
            "target_nrr":   TARGET_NRR,
            "ts":           datetime.utcnow().isoformat(),
        }

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "nrr_expansion_engine", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>NRR Expansion Engine</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}</style></head><body>
<h1>NRR Expansion Engine</h1><p>OCI Robot Cloud · Port 10099</p>
<p>Net Revenue Retention: <strong>118% → 130% target</strong>.</p>
<p>Playbooks: Robot Expansion · New Use Case · Volume Growth · Premium Upgrade</p>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/finance/nrr">NRR Dashboard</a> | <a href="/finance/playbooks">Playbooks</a></p>
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

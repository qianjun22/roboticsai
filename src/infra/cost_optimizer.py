"""OCI Compute Cost Optimizer — Robot Cloud Training & Inference
Port 8090 | OCI Robot Cloud | March 2026: $224 actual vs $341 unoptimized (34% savings)
"""
from __future__ import annotations
import json, time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import numpy as np

PORT = 8090
BILLING_MONTH = "2026-03"
ACTUAL_SPEND = 224.18
UNOPTIMIZED_SPEND = 341.22
SAVINGS_BREAKDOWN = {"spot_instances": 82.15, "schedule_shifting": 23.40, "right_sizing": 11.49}
SPOT_AVAILABILITY_PCT = 0.92
SPOT_SAVINGS_PCT_RANGE = (0.40, 0.60)
GPU_SPECS = {
    "A100_80GB": {"hourly_usd": 3.40, "vram_gb": 80, "best_for": ["fine_tune_large", "multi_gpu_ddp"]},
    "A100_40GB": {"hourly_usd": 2.10, "vram_gb": 40, "best_for": ["fine_tune_small", "inference_batch"]},
    "V100": {"hourly_usd": 1.25, "vram_gb": 16, "best_for": ["eval", "data_prep"]},
}
DESIGN_PARTNERS = {
    "partner_alpha": {"label": "Alpha Robotics", "inference_hours": 42.0, "fine_tune_jobs": 3, "gpu_type": "A100_40GB", "data_gb": 18.5},
    "partner_beta": {"label": "Beta Automation", "inference_hours": 28.0, "fine_tune_jobs": 1, "gpu_type": "V100", "data_gb": 6.2},
    "partner_gamma": {"label": "Gamma Systems", "inference_hours": 61.0, "fine_tune_jobs": 5, "gpu_type": "A100_80GB", "data_gb": 34.0},
}
STORAGE_RATE_USD_PER_GB = 0.025
TRANSFER_RATE_USD_PER_GB = 0.0085

@dataclass
class Recommendation:
    category: str; priority: str; title: str; description: str; estimated_savings_usd: float; effort: str; action: str

@dataclass
class PartnerBill:
    partner_id: str; label: str; inference_cost: float; fine_tune_cost: float; storage_cost: float; transfer_cost: float
    @property
    def total(self) -> float: return self.inference_cost + self.fine_tune_cost + self.storage_cost + self.transfer_cost
    def to_dict(self): return {"partner_id": self.partner_id, "label": self.label, "inference_cost": round(self.inference_cost, 2), "fine_tune_cost": round(self.fine_tune_cost, 2), "storage_cost": round(self.storage_cost, 2), "total": round(self.total, 2)}

@dataclass
class CostSnapshot:
    month: str; actual_usd: float; unoptimized_usd: float; savings_realized_usd: float; savings_breakdown: dict
    recommendations: list = field(default_factory=list); partner_bills: list = field(default_factory=list)
    @property
    def savings_pct(self) -> float: return (self.unoptimized_usd - self.actual_usd) / self.unoptimized_usd if self.unoptimized_usd else 0.0
    @property
    def potential_additional_savings(self) -> float: return sum(r.estimated_savings_usd for r in self.recommendations if r.priority == "high")
    def to_dict(self): return {"month": self.month, "actual_usd": round(self.actual_usd, 2), "unoptimized_usd": round(self.unoptimized_usd, 2), "savings_realized_usd": round(self.savings_realized_usd, 2), "savings_pct": round(self.savings_pct * 100, 1)}

def simulate_spot_availability(n_checks: int = 100, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed); available = rng.random(n_checks) < SPOT_AVAILABILITY_PCT
    savings_pcts = rng.uniform(*SPOT_SAVINGS_PCT_RANGE, n_checks)
    return {"availability_pct": float(np.mean(available) * 100), "avg_savings_when_available_pct": round(float(np.mean(savings_pcts[available])) * 100, 1), "preemption_count_per_100h": int(np.sum(~available))}

def compute_partner_bills() -> list:
    bills = []
    for pid, info in DESIGN_PARTNERS.items():
        gpu = GPU_SPECS[info["gpu_type"]]
        bills.append(PartnerBill(partner_id=pid, label=info["label"], inference_cost=round(info["inference_hours"] * gpu["hourly_usd"], 2),
            fine_tune_cost=round(info["fine_tune_jobs"] * 8.0 * gpu["hourly_usd"], 2), storage_cost=round(info["data_gb"] * STORAGE_RATE_USD_PER_GB, 2),
            transfer_cost=round(info["data_gb"] * 0.3 * TRANSFER_RATE_USD_PER_GB, 2)))
    return bills

def generate_recommendations() -> list:
    return [
        Recommendation("spot_instances", "high", "Migrate fine-tune jobs to OCI Preemptible VMs",
            "Fine-tuning workloads are checkpoint-friendly and can tolerate preemption. 40-60% savings, 92% availability.",
            82.15, "medium", "Set instance_type=preemptible in training_config.yaml"),
        Recommendation("schedule_shifting", "high", "Shift non-urgent fine-tune jobs to off-peak (11PM-6AM)",
            "Off-peak scheduling reduces OCI resource contention. Estimated 23% cost reduction for shiftable workloads.",
            23.40, "low", "Add --schedule=offpeak flag to training pipeline"),
        Recommendation("right_sizing", "medium", "Downsize eval and data-prep jobs from A100 80GB to V100",
            "Eval runs and preprocessing do not need 80GB VRAM. V100 = $1.25/hr vs $3.40/hr (63% savings).",
            11.49, "low", "Pass --gpu=V100 to eval scripts"),
        Recommendation("right_sizing", "medium", "Use A100 40GB for single-task inference (6.7GB VRAM only)",
            "GR00T N1.6 uses ~6.7GB VRAM at inference time. A100 40GB handles 5 concurrent sessions.",
            6.80, "low", "Update inference_server.py default shape to BM.GPU.A10.2"),
        Recommendation("other", "low", "Enable Object Storage lifecycle policy for model checkpoints",
            "Checkpoints older than 30 days to Infrequent Access tier ($0.01/GB). ~480GB stored.",
            3.36, "low", "Apply lifecycle_policy.json to oci://robot-cloud-checkpoints"),
    ]

def build_snapshot() -> CostSnapshot:
    return CostSnapshot(month=BILLING_MONTH, actual_usd=ACTUAL_SPEND, unoptimized_usd=UNOPTIMIZED_SPEND,
        savings_realized_usd=UNOPTIMIZED_SPEND - ACTUAL_SPEND, savings_breakdown=SAVINGS_BREAKDOWN,
        recommendations=generate_recommendations(), partner_bills=compute_partner_bills())

def build_html_dashboard(snapshot: CostSnapshot) -> str:
    spot = simulate_spot_availability()
    priority_colors = {"high": "#ef4444", "medium": "#fbbf24", "low": "#94a3b8"}
    rec_rows = "".join(f'<tr><td>{r.title}</td><td><span style="color:{priority_colors.get(r.priority,"#94a3b8")};font-weight:600">{r.priority.upper()}</span></td><td>{r.category.replace("_"," ")}</td><td style="color:#34d399;font-weight:600">${r.estimated_savings_usd:.2f}</td><td>{r.effort}</td></tr>' for r in snapshot.recommendations)
    partner_rows = "".join(f'<tr><td>{b.label}</td><td>${b.inference_cost:.2f}</td><td>${b.fine_tune_cost:.2f}</td><td>${b.storage_cost:.2f}</td><td style="font-weight:700">${b.total:.2f}</td></tr>' for b in snapshot.partner_bills)
    return f"""<!DOCTYPE html><html><head><meta charset='UTF-8'/><title>Cost Optimizer</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:24px}}h1{{color:#C74634}}h2{{color:#C74634;font-size:1.05rem;margin:28px 0 12px}}.cards{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px}}.card{{background:#1e293b;border-radius:8px;padding:16px 20px;min-width:150px;flex:1}}.card .lbl{{color:#64748b;font-size:.72rem;text-transform:uppercase}}.card .val{{font-size:1.55rem;font-weight:700;margin-top:4px}}.card .sub{{color:#94a3b8;font-size:.78rem;margin-top:2px}}table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;margin-bottom:24px}}th{{background:#0f172a;color:#94a3b8;font-size:.75rem;text-transform:uppercase;padding:10px 14px;text-align:left}}td{{padding:9px 14px;font-size:.88rem;border-top:1px solid #0f172a;color:#cbd5e1}}</style></head><body>
<h1>OCI Robot Cloud — Cost Optimizer</h1><p style="color:#64748b">Compute cost analysis · March 2026 · Port {PORT}</p>
<div class="cards"><div class="card"><div class="lbl">Actual Spend</div><div class="val">${snapshot.actual_usd:.2f}</div><div class="sub">March 2026</div></div><div class="card"><div class="lbl">Savings Realized</div><div class="val" style="color:#34d399">${snapshot.savings_realized_usd:.2f}</div><div class="sub">{snapshot.savings_pct*100:.0f}% vs unoptimized</div></div><div class="card"><div class="lbl">Unoptimized Baseline</div><div class="val" style="color:#94a3b8">${snapshot.unoptimized_usd:.2f}</div></div><div class="card"><div class="lbl">Additional Potential</div><div class="val" style="color:#fbbf24">${snapshot.potential_additional_savings:.2f}</div><div class="sub">high-priority recs</div></div></div>
<h2>Spot Instance Analysis</h2><div style="background:#1e293b;border-radius:8px;padding:16px 20px;margin-bottom:24px"><span style="color:#34d399;font-weight:700">{spot['availability_pct']:.0f}%</span> availability &nbsp;|&nbsp; <span style="color:#34d399;font-weight:700">{spot['avg_savings_when_available_pct']:.0f}%</span> avg savings &nbsp;|&nbsp; <span style="color:#fbbf24;font-weight:700">{spot['preemption_count_per_100h']}</span> preemptions/100h &nbsp;|&nbsp; Off-peak: 11PM–6AM</div>
<h2>Recommendations</h2><table><tr><th>Recommendation</th><th>Priority</th><th>Category</th><th>Est. Savings/Mo</th><th>Effort</th></tr>{rec_rows}</table>
<h2>Design Partner Billing — {snapshot.month}</h2><table><tr><th>Partner</th><th>Inference</th><th>Fine-Tune</th><th>Storage</th><th>Total</th></tr>{partner_rows}</table>
<div style="margin-top:32px;color:#475569;font-size:.75rem">Oracle Confidential | OCI Robot Cloud | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div></body></html>"""

def build_fastapi_app(snapshot: CostSnapshot):
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
        import uvicorn
    except ImportError: return None
    app = FastAPI(title="Cost Optimizer", version="1.0.0")
    @app.get("/", response_class=HTMLResponse)
    async def dashboard(): return build_html_dashboard(snapshot)
    @app.get("/recommendations")
    async def recommendations(): return JSONResponse(snapshot.to_dict())
    @app.get("/billing/{partner_id}")
    async def billing(partner_id: str):
        bill = next((b for b in snapshot.partner_bills if b.partner_id == partner_id), None)
        if not bill: return JSONResponse({"error": f"'{partner_id}' not found", "available": [b.partner_id for b in snapshot.partner_bills]}, status_code=404)
        return JSONResponse(bill.to_dict())
    return app, uvicorn

def main() -> None:
    print("=" * 60); print("OCI Robot Cloud — Cost Optimizer"); print(f"Month: {BILLING_MONTH}"); print("=" * 60)
    snapshot = build_snapshot()
    print(f"Actual spend: ${snapshot.actual_usd:.2f} | Unoptimized: ${snapshot.unoptimized_usd:.2f} | Savings: ${snapshot.savings_realized_usd:.2f} ({snapshot.savings_pct*100:.0f}%)")
    for cat, val in snapshot.savings_breakdown.items(): print(f"  {cat:<22} ${val:.2f}")
    print("\nTop recommendations:")
    for r in sorted(snapshot.recommendations, key=lambda x: -x.estimated_savings_usd): print(f"  [{r.priority.upper():<6}] {r.title[:50]:<50} ${r.estimated_savings_usd:.2f}/mo")
    html = build_html_dashboard(snapshot)
    out_path = Path("/tmp/cost_optimizer.html"); out_path.write_text(html, encoding="utf-8"); print(f"\nHTML: {out_path}")
    result = build_fastapi_app(snapshot)
    if result: app, uvicorn = result; print(f"Starting server port {PORT}"); uvicorn.run(app, host="0.0.0.0", port=PORT)
    else: print("(FastAPI not installed) | Oracle Confidential | OCI Robot Cloud")

if __name__ == "__main__":
    main()

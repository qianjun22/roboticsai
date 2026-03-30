"""inference_cost_tracker.py
Tracks per-request inference costs for OCI Robot Cloud design partners.
Usage: python inference_cost_tracker.py
       uvicorn inference_cost_tracker:app --port 8086
Endpoints: GET / (dashboard), /usage, /usage/{id}, /usage/{id}/requests, /trends, /invoice/{id}
"""
from __future__ import annotations
import json, math, uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np

COST_PER_REQUEST_USD: float = 0.00114
BILLING_PERIOD_DAYS: int = 30
PORT: int = 8086
PARTNERS: List[str] = ["covariant", "apptronik", "1x_technologies", "skild_ai", "physical_intelligence"]
PARTNER_SHARE: Dict[str, float] = {"covariant": 0.40, "apptronik": 0.20, "1x_technologies": 0.167, "skild_ai": 0.133, "physical_intelligence": 0.10}
PARTNER_COLORS: Dict[str, str] = {"covariant": "#C0392B", "apptronik": "#E67E22", "1x_technologies": "#27AE60", "skild_ai": "#2980B9", "physical_intelligence": "#8E44AD"}
BILLING_START = datetime(2026, 3, 1); BILLING_END = datetime(2026, 3, 30, 23, 59, 59)
_INFERENCE_LOG: List = []

@dataclass
class InferenceRequest:
    request_id: str; partner_id: str; timestamp: datetime; latency_ms: float
    model_version: str; action_chunk_size: int; billed_usd: float; status: str

@dataclass
class PartnerUsageSummary:
    partner_id: str; period_start: datetime; period_end: datetime
    total_requests: int; total_cost_usd: float; avg_latency_ms: float; success_rate: float

def generate_inference_log(seed: int = 42) -> List[InferenceRequest]:
    rng = np.random.default_rng(seed); requests: List[InferenceRequest] = []
    total_seconds = int((BILLING_END - BILLING_START).total_seconds())
    for partner in PARTNERS:
        n_requests = int(3000 * PARTNER_SHARE[partner] * rng.uniform(0.97, 1.03))
        for _ in range(n_requests):
            ts = BILLING_START + timedelta(seconds=int(rng.integers(0, total_seconds)))
            latency = float(rng.lognormal(mean=math.log(226), sigma=0.18))
            latency = max(80.0, min(latency, 1200.0))
            status = "success" if rng.random() < 0.985 else "error"
            billed = COST_PER_REQUEST_USD if status == "success" else 0.0
            chunk_size = int(rng.choice([16, 32], p=[0.35, 0.65]))
            requests.append(InferenceRequest(
                request_id=f"req_{uuid.UUID(int=int(rng.integers(0, 2**64))).hex[:12]}",
                partner_id=partner, timestamp=ts, latency_ms=round(latency, 1),
                model_version="gr00t-n1.6", action_chunk_size=chunk_size,
                billed_usd=billed, status=status))
    requests.sort(key=lambda r: r.timestamp)
    return requests

def _seed_data() -> None:
    global _INFERENCE_LOG
    if not _INFERENCE_LOG: _INFERENCE_LOG = generate_inference_log(seed=42)

_seed_data()

def compute_partner_summaries(requests=None) -> List[PartnerUsageSummary]:
    if requests is None: requests = _INFERENCE_LOG
    summaries = []
    for partner in PARTNERS:
        pr = [r for r in requests if r.partner_id == partner]
        if not pr: continue
        total = len(pr); success_count = sum(1 for r in pr if r.status == "success")
        summaries.append(PartnerUsageSummary(
            partner_id=partner, period_start=BILLING_START, period_end=BILLING_END,
            total_requests=total, total_cost_usd=round(sum(r.billed_usd for r in pr), 4),
            avg_latency_ms=round(float(np.mean([r.latency_ms for r in pr])), 1),
            success_rate=round(success_count / total, 4)))
    return summaries

def compute_cost_trends(requests=None) -> Dict:
    if requests is None: requests = _INFERENCE_LOG
    daily: Dict[str, Dict] = {}
    for d in range(BILLING_PERIOD_DAYS):
        day = (BILLING_START + timedelta(days=d)).strftime("%Y-%m-%d")
        daily[day] = {"date": day, "cost_usd": 0.0, "request_count": 0}
    for r in requests:
        day_str = r.timestamp.strftime("%Y-%m-%d")
        if day_str in daily: daily[day_str]["cost_usd"] += r.billed_usd; daily[day_str]["request_count"] += 1
    daily_list = [{"date": v["date"], "cost_usd": round(v["cost_usd"], 4), "request_count": v["request_count"]} for v in sorted(daily.values(), key=lambda x: x["date"])]
    total_cost = sum(v["cost_usd"] for v in daily_list)
    peak_day = max(daily_list, key=lambda x: x["cost_usd"])["date"]
    return {"daily": daily_list, "total_cost_usd": round(total_cost, 4), "peak_day": peak_day, "peak_hour": 14}

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    app = FastAPI(title="OCI Robot Cloud — Inference Cost Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        summaries = compute_partner_summaries(); trends = compute_cost_trends()
        total_req = sum(s.total_requests for s in summaries); total_cost = sum(s.total_cost_usd for s in summaries)
        rows = "".join(f"<tr><td style='color:{PARTNER_COLORS.get(s.partner_id,'#888')}'>{s.partner_id}</td><td>{s.total_requests:,}</td><td>${s.total_cost_usd:.4f}</td><td>{s.avg_latency_ms:.1f}ms</td><td>{s.success_rate*100:.1f}%</td></tr>" for s in summaries)
        return f"""<!DOCTYPE html><html><head><meta charset='UTF-8'/><title>Inference Cost Tracker</title><style>body{{background:#0d0d1a;color:#e0e0e0;font-family:monospace;padding:20px}}h1{{color:#C0392B}}table{{border-collapse:collapse;width:100%}}th{{background:#1a1a2e;color:#C0392B;padding:8px}}td{{padding:6px 8px;border-bottom:1px solid #1e2a3a}}</style></head><body><h1>OCI Robot Cloud — Inference Cost Tracker</h1><p>Total: {total_req:,} requests | ${total_cost:.4f} | {len(PARTNERS)} partners | Peak day: {trends['peak_day']}</p><table><tr><th>Partner</th><th>Requests</th><th>Cost</th><th>Avg Latency</th><th>Success</th></tr>{rows}</table><footer style='color:#555;margin-top:20px'>OCI Robot Cloud | Port {PORT}</footer></body></html>"""

    @app.get("/usage")
    def usage_all(): return JSONResponse([{"partner_id": s.partner_id, "total_requests": s.total_requests, "total_cost_usd": s.total_cost_usd, "avg_latency_ms": s.avg_latency_ms, "success_rate": s.success_rate} for s in compute_partner_summaries()])

    @app.get("/usage/{partner_id}")
    def usage_partner(partner_id: str):
        summaries = {s.partner_id: s for s in compute_partner_summaries()}
        if partner_id not in summaries: raise HTTPException(status_code=404, detail=f"Partner '{partner_id}' not found")
        s = summaries[partner_id]; return JSONResponse({"partner_id": s.partner_id, "total_requests": s.total_requests, "total_cost_usd": s.total_cost_usd, "avg_latency_ms": s.avg_latency_ms, "success_rate": s.success_rate})

    @app.get("/usage/{partner_id}/requests")
    def usage_partner_requests(partner_id: str, limit: int = 100):
        if partner_id not in PARTNERS: raise HTTPException(status_code=404, detail=f"Partner '{partner_id}' not found")
        pr = sorted([r for r in _INFERENCE_LOG if r.partner_id == partner_id], key=lambda r: r.timestamp, reverse=True)[:limit]
        return JSONResponse([{"request_id": r.request_id, "timestamp": r.timestamp.isoformat(), "latency_ms": r.latency_ms, "billed_usd": r.billed_usd, "status": r.status} for r in pr])

    @app.get("/trends")
    def trends(): return JSONResponse(compute_cost_trends())

    @app.get("/invoice/{partner_id}", response_class=HTMLResponse)
    def invoice(partner_id: str):
        summaries = {s.partner_id: s for s in compute_partner_summaries()}
        if partner_id not in summaries: raise HTTPException(status_code=404, detail=f"Partner '{partner_id}' not found")
        s = summaries[partner_id]; color = PARTNER_COLORS.get(partner_id, "#C0392B")
        return f"""<!DOCTYPE html><html><head><meta charset='UTF-8'/><title>Invoice - {partner_id}</title><style>body{{font-family:Arial;max-width:680px;margin:40px auto;padding:0 20px}}h1{{color:{color}}}table{{border-collapse:collapse;width:100%}}th{{background:#f5f5f5;padding:8px;text-align:left}}td{{padding:7px 8px;border-bottom:1px solid #eee}}</style></head><body><h1>OCI Robot Cloud — Invoice: {partner_id}</h1><p>Period: 2026-03-01 – 2026-03-30 | Due: 2026-04-15</p><table><tr><th>Description</th><th>Qty</th><th>Unit Price</th><th>Amount</th></tr><tr><td>GR00T N1.6 Inference (gr00t-n1.6, {s.avg_latency_ms:.1f}ms avg)</td><td>{s.total_requests:,}</td><td>${COST_PER_REQUEST_USD:.5f}</td><td>${s.total_cost_usd:.4f}</td></tr><tr style='font-weight:bold'><td colspan='3'>TOTAL DUE</td><td style='color:{color}'>${s.total_cost_usd:.4f} USD</td></tr></table><p style='margin-top:20px'>Success rate: {s.success_rate*100:.1f}%</p><div style='color:#999;font-size:11px;margin-top:30px'>Oracle Cloud Infrastructure | robotics-billing@oracle.com</div></body></html>"""
except ImportError:
    app = None

def main() -> None:
    print("=" * 72); print("OCI Robot Cloud — Inference Cost Tracker")
    print(f"Billing period: {BILLING_START.date()} to {BILLING_END.date()}")
    print("=" * 72)
    summaries = compute_partner_summaries(); trends = compute_cost_trends()
    print(f"\n{'Partner':<26} {'Requests':>10} {'Cost (USD)':>12} {'Avg Lat':>10} {'Success':>9}")
    print("-" * 72)
    for s in summaries: print(f"{s.partner_id:<26} {s.total_requests:>10,} ${s.total_cost_usd:>11.4f} {s.avg_latency_ms:>9.1f}ms {s.success_rate*100:>8.1f}%")
    print("-" * 72); print(f"{'TOTAL':<26} {sum(s.total_requests for s in summaries):>10,} ${sum(s.total_cost_usd for s in summaries):>11.4f}")
    print(f"\nPeak day: {trends['peak_day']} | Total cost: ${trends['total_cost_usd']:.4f} USD")

if __name__ == "__main__":
    main()

"""
ASC 606 revenue recognition compliance — performance obligation identification, ratable vs usage-based rev rec, automated journal entries, deferred revenue tracking.
FastAPI service — OCI Robot Cloud
Port: 10087
"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10087

# ---------------------------------------------------------------------------
# Domain constants & helpers
# ---------------------------------------------------------------------------

class RevRecMethod(str, Enum):
    RATABLE = "ratable"          # Recognized evenly over service period
    USAGE_BASED = "usage_based"  # Recognized as units consumed
    MILESTONE = "milestone"      # Recognized at delivery milestones


class ObligationStatus(str, Enum):
    IDENTIFIED = "identified"
    PARTIALLY_SATISFIED = "partially_satisfied"
    FULLY_SATISFIED = "fully_satisfied"


# Simulated customer contract database
_CONTRACTS: Dict[str, Dict] = {
    "CUST-001": {
        "name": "Acme Robotics",
        "contract_value": 480000.0,
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "method": RevRecMethod.RATABLE,
        "performance_obligations": [
            {"id": "PO-001-A", "desc": "GR00T inference API (12-month subscription)", "ssp": 360000.0, "method": RevRecMethod.RATABLE},
            {"id": "PO-001-B", "desc": "Fine-tuning pipeline credits", "ssp": 80000.0, "method": RevRecMethod.USAGE_BASED},
            {"id": "PO-001-C", "desc": "Onboarding & integration milestone", "ssp": 40000.0, "method": RevRecMethod.MILESTONE},
        ],
        "milestone_delivered": True,
        "usage_consumed_pct": 0.62,
        "invoiced": 480000.0,
        "collected": 240000.0,
    },
    "CUST-002": {
        "name": "Horizon Automation",
        "contract_value": 120000.0,
        "start_date": "2026-02-01",
        "end_date": "2026-07-31",
        "method": RevRecMethod.RATABLE,
        "performance_obligations": [
            {"id": "PO-002-A", "desc": "Robot Cloud Platform (6-month)", "ssp": 90000.0, "method": RevRecMethod.RATABLE},
            {"id": "PO-002-B", "desc": "DAgger data collection API usage", "ssp": 30000.0, "method": RevRecMethod.USAGE_BASED},
        ],
        "milestone_delivered": False,
        "usage_consumed_pct": 0.45,
        "invoiced": 120000.0,
        "collected": 120000.0,
    },
    "CUST-003": {
        "name": "Vertex Industrial",
        "contract_value": 240000.0,
        "start_date": "2025-07-01",
        "end_date": "2026-06-30",
        "method": RevRecMethod.USAGE_BASED,
        "performance_obligations": [
            {"id": "PO-003-A", "desc": "Inference compute (pay-per-call)", "ssp": 200000.0, "method": RevRecMethod.USAGE_BASED},
            {"id": "PO-003-B", "desc": "Annual support & SLA", "ssp": 40000.0, "method": RevRecMethod.RATABLE},
        ],
        "milestone_delivered": False,
        "usage_consumed_pct": 0.78,
        "invoiced": 200000.0,
        "collected": 180000.0,
    },
}

# ---------------------------------------------------------------------------
# ASC 606 calculation engine
# ---------------------------------------------------------------------------

def _parse_date(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _period_elapsed_fraction(start: str, end: str, period_end: str) -> float:
    """Fraction of service period elapsed as of period_end date."""
    s = _parse_date(start)
    e = _parse_date(end)
    p = _parse_date(period_end)
    total_days = (e - s).days
    if total_days <= 0:
        return 1.0
    elapsed = min((p - s).days, total_days)
    return max(0.0, elapsed / total_days)


def _recognize_obligation(
    po: Dict,
    elapsed_fraction: float,
    usage_consumed_pct: float,
    milestone_delivered: bool,
) -> Dict:
    """Compute recognized and deferred revenue for a single performance obligation."""
    ssp = po["ssp"]
    method = po["method"]

    if method == RevRecMethod.RATABLE:
        recognized = ssp * elapsed_fraction
    elif method == RevRecMethod.USAGE_BASED:
        recognized = ssp * usage_consumed_pct
    elif method == RevRecMethod.MILESTONE:
        recognized = ssp if milestone_delivered else 0.0
    else:
        recognized = 0.0

    recognized = round(min(recognized, ssp), 2)
    deferred = round(ssp - recognized, 2)

    if recognized >= ssp:
        status = ObligationStatus.FULLY_SATISFIED
    elif recognized > 0:
        status = ObligationStatus.PARTIALLY_SATISFIED
    else:
        status = ObligationStatus.IDENTIFIED

    return {
        "obligation_id": po["id"],
        "description": po["desc"],
        "method": method,
        "standalone_selling_price": ssp,
        "recognized_revenue": recognized,
        "deferred_revenue": deferred,
        "status": status,
    }


def _generate_journal_entries(
    customer_id: str,
    customer_name: str,
    po_results: List[Dict],
    invoiced: float,
    collected: float,
    period: str,
) -> List[Dict]:
    """Generate ASC 606 compliant journal entries for the period."""
    total_recognized = sum(p["recognized_revenue"] for p in po_results)
    total_deferred = sum(p["deferred_revenue"] for p in po_results)
    entries = []
    je_seq = 1

    def je(debit_acct, credit_acct, amount, memo):
        return {
            "je_id": f"JE-{customer_id}-{period.replace('-', '')}-{je_seq:03d}",
            "period": period,
            "customer_id": customer_id,
            "customer_name": customer_name,
            "debit_account": debit_acct,
            "credit_account": credit_acct,
            "amount": round(amount, 2),
            "memo": memo,
            "asc606_ref": "ASC 606-10-25",
        }

    # 1. Cash / AR recognition
    if collected > 0:
        entries.append(je("1010 Cash", "1200 Accounts Receivable", collected,
                          f"Cash collected from {customer_name}"))

    ar_unbilled = max(0.0, invoiced - collected)
    if ar_unbilled > 0:
        entries.append(je("1200 Accounts Receivable", "2300 Contract Liability (Deferred Revenue)",
                          ar_unbilled, f"Invoice issued; revenue not yet recognized"))

    # 2. Revenue recognition entries per obligation
    for po in po_results:
        if po["recognized_revenue"] > 0:
            entries.append(je(
                "2300 Contract Liability (Deferred Revenue)",
                "4000 Revenue — Robot Cloud Services",
                po["recognized_revenue"],
                f"Rev rec: {po['description']} ({po['method']})",
            ))

    # 3. Remaining deferred revenue
    if total_deferred > 0:
        entries.append(je(
            "4000 Revenue — Robot Cloud Services",
            "2300 Contract Liability (Deferred Revenue)",
            total_deferred,
            f"Deferred revenue — unearned as of {period}",
        ))

    # Fix sequential IDs
    for i, e in enumerate(entries, 1):
        e["je_id"] = f"JE-{customer_id}-{period.replace('-', '')}-{i:03d}"

    return entries


# ---------------------------------------------------------------------------
# FastAPI / fallback server
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Revenue Recognition Compliance (ASC 606)", version="1.0.0")

    @app.get("/finance/rev_rec")
    def rev_rec(
        customer_id: str = Query(..., description="Customer contract ID (e.g. CUST-001)"),
        period: str = Query(..., description="Reporting period end date YYYY-MM-DD"),
    ):
        """
        Compute ASC 606 recognized and deferred revenue for a single customer as of the reporting period.
        Returns performance obligation breakdown, journal entries, and compliance flags.
        """
        if customer_id not in _CONTRACTS:
            return JSONResponse(
                status_code=404,
                content={"error": f"Customer '{customer_id}' not found. Available: {list(_CONTRACTS.keys())}"}
            )

        contract = _CONTRACTS[customer_id]
        elapsed = _period_elapsed_fraction(contract["start_date"], contract["end_date"], period)

        po_results = [
            _recognize_obligation(
                po,
                elapsed_fraction=elapsed,
                usage_consumed_pct=contract["usage_consumed_pct"],
                milestone_delivered=contract["milestone_delivered"],
            )
            for po in contract["performance_obligations"]
        ]

        total_recognized = round(sum(p["recognized_revenue"] for p in po_results), 2)
        total_deferred = round(sum(p["deferred_revenue"] for p in po_results), 2)

        journal_entries = _generate_journal_entries(
            customer_id=customer_id,
            customer_name=contract["name"],
            po_results=po_results,
            invoiced=contract["invoiced"],
            collected=contract["collected"],
            period=period,
        )

        # Compliance checks
        contract_value = contract["contract_value"]
        ssp_total = sum(po["ssp"] for po in contract["performance_obligations"])
        compliance_flags = []
        if abs(ssp_total - contract_value) > 0.01:
            compliance_flags.append({
                "code": "SSP_MISMATCH",
                "severity": "WARNING",
                "detail": f"Sum of SSPs ({ssp_total}) differs from contract value ({contract_value}) — review variable consideration.",
            })
        if total_recognized > contract_value:
            compliance_flags.append({
                "code": "OVER_RECOGNITION",
                "severity": "ERROR",
                "detail": "Recognized revenue exceeds total contract value — constraint violation under ASC 606-10-32.",
            })
        if not compliance_flags:
            compliance_flags.append({"code": "COMPLIANT", "severity": "OK", "detail": "No ASC 606 violations detected."})

        return {
            "customer_id": customer_id,
            "customer_name": contract["name"],
            "period": period,
            "contract_value": contract_value,
            "elapsed_fraction": round(elapsed, 4),
            "recognized_revenue": total_recognized,
            "deferred_revenue": total_deferred,
            "performance_obligations": po_results,
            "journal_entries": journal_entries,
            "compliance_flags": compliance_flags,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/finance/rev_rec_summary")
    def rev_rec_summary(
        period: str = Query(..., description="Reporting period end date YYYY-MM-DD"),
    ):
        """
        Aggregate recognized and deferred revenue across all customers for the period.
        Includes growth rate vs prior period (30-day look-back).
        """
        # Compute prior period (30 days back)
        period_dt = _parse_date(period)
        prior_dt = period_dt - timedelta(days=30)
        prior_period = prior_dt.strftime("%Y-%m-%d")

        rows = []
        total_recognized = 0.0
        total_deferred = 0.0
        prior_recognized = 0.0

        for cid, contract in _CONTRACTS.items():
            elapsed = _period_elapsed_fraction(contract["start_date"], contract["end_date"], period)
            elapsed_prior = _period_elapsed_fraction(contract["start_date"], contract["end_date"], prior_period)

            po_results = [
                _recognize_obligation(po, elapsed, contract["usage_consumed_pct"], contract["milestone_delivered"])
                for po in contract["performance_obligations"]
            ]
            po_prior = [
                _recognize_obligation(po, elapsed_prior, contract["usage_consumed_pct"] * 0.85, contract["milestone_delivered"])
                for po in contract["performance_obligations"]
            ]

            rec = round(sum(p["recognized_revenue"] for p in po_results), 2)
            def_ = round(sum(p["deferred_revenue"] for p in po_results), 2)
            rec_prior = round(sum(p["recognized_revenue"] for p in po_prior), 2)

            total_recognized += rec
            total_deferred += def_
            prior_recognized += rec_prior

            rows.append({
                "customer_id": cid,
                "customer_name": contract["name"],
                "recognized_revenue": rec,
                "deferred_revenue": def_,
            })

        total_recognized = round(total_recognized, 2)
        total_deferred = round(total_deferred, 2)
        prior_recognized = round(prior_recognized, 2)

        growth_rate = 0.0
        if prior_recognized > 0:
            growth_rate = round((total_recognized - prior_recognized) / prior_recognized * 100, 2)

        return {
            "period": period,
            "prior_period": prior_period,
            "total_recognized": total_recognized,
            "total_deferred": total_deferred,
            "prior_period_recognized": prior_recognized,
            "growth_rate_pct": growth_rate,
            "customer_breakdown": rows,
            "customer_count": len(rows),
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "revenue_recognition_compliance",
            "port": PORT,
            "active_contracts": len(_CONTRACTS),
            "ts": datetime.utcnow().isoformat(),
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>Revenue Recognition Compliance</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}</style></head><body>
<h1>Revenue Recognition Compliance (ASC 606)</h1><p>OCI Robot Cloud · Port 10087</p>
<p>Performance obligation identification, ratable &amp; usage-based rev rec, automated journal entries, deferred revenue tracking.</p>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/finance/rev_rec_summary?period=2026-03-31">Summary (Q1 2026)</a></p>
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

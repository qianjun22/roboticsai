"""
partner_qbr_generator_v2.py — OCI Robot Cloud Partner QBR Generator
Port: 8083

Auto-generates Quarterly Business Review reports for OCI Robot Cloud
design partners covering Q1 2026 results, KPIs, SLA compliance, and
recommendations.
"""

import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

PORT = 8083
QUARTER = "Q1 2026"
ORACLE_RED = "#C74634"
_TIER_COLORS = {1: "#C74634", 2: "#2563eb", 3: "#7c3aed"}
TOTAL_REVENUE: float = 0.0


@dataclass
class PartnerQBR:
    partner_id: str
    partner_name: str
    tier: int
    quarter: str
    total_jobs: int
    successful_jobs: int
    failed_jobs: int
    total_gpu_hours: float
    total_spend_usd: float
    avg_latency_ms: float
    p99_latency_ms: float
    sla_compliance_pct: float
    data_uploaded_gb: float
    models_fine_tuned: int
    best_sr: float
    budget_used_pct: float
    recommendations: List[str] = field(default_factory=list)


_QBR_STORE: Dict[str, PartnerQBR] = {
    "covariant": PartnerQBR(
        partner_id="covariant", partner_name="Covariant", tier=1, quarter=QUARTER,
        total_jobs=847, successful_jobs=821, failed_jobs=26, total_gpu_hours=412.0, total_spend_usd=1689.0,
        avg_latency_ms=224.0, p99_latency_ms=267.0, sla_compliance_pct=99.7, data_uploaded_gb=2457.6,
        models_fine_tuned=3, best_sr=0.71, budget_used_pct=82.0,
        recommendations=["Increase GPU allocation for Q2", "Enable multi-task training", "Schedule GTC 2027 co-presentation"]),
    "apptronik": PartnerQBR(
        partner_id="apptronik", partner_name="Apptronik", tier=2, quarter=QUARTER,
        total_jobs=234, successful_jobs=218, failed_jobs=16, total_gpu_hours=134.0, total_spend_usd=549.0,
        avg_latency_ms=231.0, p99_latency_ms=289.0, sla_compliance_pct=98.9, data_uploaded_gb=890.0,
        models_fine_tuned=2, best_sr=0.58, budget_used_pct=67.0,
        recommendations=["Adopt DAgger to push SR above 70%", "Schedule DAgger onboarding workshop for Q2", "Expand demo corpus to 600+ episodes"]),
    "1x_technologies": PartnerQBR(
        partner_id="1x_technologies", partner_name="1X Technologies", tier=2, quarter=QUARTER,
        total_jobs=189, successful_jobs=176, failed_jobs=13, total_gpu_hours=98.0, total_spend_usd=402.0,
        avg_latency_ms=238.0, p99_latency_ms=291.0, sla_compliance_pct=99.1, data_uploaded_gb=670.0,
        models_fine_tuned=1, best_sr=0.52, budget_used_pct=49.0,
        recommendations=["Diversify demo collection to 500+ episodes", "Enable DAgger training in Q2", "Resolve P2 NaN-loss ticket before next training run"]),
    "skild_ai": PartnerQBR(
        partner_id="skild_ai", partner_name="Skild AI", tier=3, quarter=QUARTER,
        total_jobs=67, successful_jobs=61, failed_jobs=6, total_gpu_hours=41.0, total_spend_usd=168.0,
        avg_latency_ms=243.0, p99_latency_ms=298.0, sla_compliance_pct=97.8, data_uploaded_gb=310.0,
        models_fine_tuned=1, best_sr=0.41, budget_used_pct=21.0,
        recommendations=["Collect additional 150 high-quality demos to break SR plateau", "Increase GPU budget utilization — currently at 21%", "Schedule quarterly executive review"]),
    "physical_intelligence": PartnerQBR(
        partner_id="physical_intelligence", partner_name="Physical Intelligence", tier=3, quarter=QUARTER,
        total_jobs=43, successful_jobs=38, failed_jobs=5, total_gpu_hours=29.0, total_spend_usd=119.0,
        avg_latency_ms=249.0, p99_latency_ms=302.0, sla_compliance_pct=97.2, data_uploaded_gb=220.0,
        models_fine_tuned=1, best_sr=0.38, budget_used_pct=15.0,
        recommendations=["Complete onboarding: run first BC fine-tune", "Assign dedicated CSE for co-development", "Waive Q2 onboarding fee to accelerate adoption"]),
}

_PARTNER_ORDER = ["covariant", "apptronik", "1x_technologies", "skild_ai", "physical_intelligence"]
TOTAL_REVENUE = sum(q.total_spend_usd for q in _QBR_STORE.values())


def _sla_color(pct):
    return "#16a34a" if pct >= 99.5 else "#d97706" if pct >= 98.0 else "#dc2626"

def _sr_color(sr):
    return "#16a34a" if sr >= 0.65 else "#d97706" if sr >= 0.45 else "#dc2626"

def _kpi_card(label, value, color=ORACLE_RED):
    return f"<div class='kpi'><div class='kpi-label'>{label}</div><div class='kpi-value' style='color:{color}'>{value}</div></div>"


def _inline_css():
    return f"""<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fff;color:#1e293b;font-size:14px}}
header{{background:{ORACLE_RED};color:white;padding:0}}
.header-inner{{display:flex;justify-content:space-between;align-items:center;padding:20px 32px}}
header h1{{font-size:1.4rem;font-weight:700}}.subtitle{{font-size:.85rem;opacity:.88;margin-top:3px}}
.partner-badge{{border:2px solid white;border-radius:8px;padding:10px 18px;text-align:right}}
.partner-name{{font-size:1.1rem;font-weight:700}}
.tier-label{{font-size:.8rem;margin-top:3px;background:white;border-radius:4px;padding:2px 8px;display:inline-block}}
main{{padding:28px 32px}}section{{margin-bottom:28px}}
.section-title{{font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.7px;color:{ORACLE_RED};border-bottom:2px solid {ORACLE_RED};padding-bottom:6px;margin-bottom:14px}}
.kpi-row{{display:flex;flex-wrap:wrap;gap:12px}}
.kpi{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;min-width:110px}}
.kpi-label{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px}}
.kpi-value{{font-size:1.4rem;font-weight:700;color:{ORACLE_RED}}}
.metrics-table{{width:100%;border-collapse:collapse}}
.metrics-table th{{background:{ORACLE_RED};color:white;padding:9px 14px;text-align:left;font-size:.78rem}}
.metrics-table td{{padding:9px 14px;border-bottom:1px solid #e2e8f0;font-size:.875rem}}
.metrics-table tr:hover td{{background:#fef2f0}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.72rem;font-weight:700;text-transform:uppercase}}
.badge-ok{{background:#dcfce7;color:#16a34a}}.badge-warn{{background:#fef9c3;color:#a16207}}.badge-fail{{background:#fee2e2;color:#dc2626}}
footer{{background:#f1f5f9;padding:12px 32px;display:flex;justify-content:space-between;font-size:.75rem;color:#64748b}}
</style>"""


def _render_partner_html(qbr: PartnerQBR, standalone=False):
    tc = _TIER_COLORS.get(qbr.tier, "#6b7280")
    sla_c = _sla_color(qbr.sla_compliance_pct)
    sr_c = _sr_color(qbr.best_sr)
    success_pct = qbr.successful_jobs / qbr.total_jobs * 100 if qbr.total_jobs else 0
    kpi_row = "".join([
        _kpi_card("Total Jobs", f"{qbr.total_jobs:,}"),
        _kpi_card("Job Success", f"{success_pct:.1f}%", "#16a34a"),
        _kpi_card("Failed", str(qbr.failed_jobs), "#dc2626"),
        _kpi_card("GPU Hours", f"{qbr.total_gpu_hours:.0f}"),
        _kpi_card("Spend", f"${qbr.total_spend_usd:,.0f}"),
        _kpi_card("Best SR", f"{qbr.best_sr:.0%}", sr_c),
        _kpi_card("SLA", f"{qbr.sla_compliance_pct:.1f}%", sla_c),
        _kpi_card("Budget Used", f"{qbr.budget_used_pct:.0f}%"),
    ])
    rec_rows = "".join(f"<tr><td>&#8226;</td><td>{r}</td></tr>" for r in qbr.recommendations)
    content = f"""
<section><div class="section-title">KPI Summary — {qbr.quarter}</div>
<div class="kpi-row">{kpi_row}</div></section>
<section><div class="section-title">Metrics Detail</div>
<table class="metrics-table"><thead><tr><th>Metric</th><th>Value</th><th>Status</th></tr></thead><tbody>
<tr><td>Total Jobs</td><td>{qbr.total_jobs:,}</td><td><span class="badge badge-ok">OK</span></td></tr>
<tr><td>Successful Jobs</td><td>{qbr.successful_jobs:,}</td><td><span class="badge badge-ok">OK</span></td></tr>
<tr><td>Failed Jobs</td><td>{qbr.failed_jobs}</td><td><span class="badge {'badge-warn' if qbr.failed_jobs > 20 else 'badge-ok'}">{"REVIEW" if qbr.failed_jobs > 20 else "OK"}</span></td></tr>
<tr><td>Avg Latency</td><td>{qbr.avg_latency_ms:.0f} ms</td><td><span class="badge {'badge-warn' if qbr.avg_latency_ms > 240 else 'badge-ok'}">{"WATCH" if qbr.avg_latency_ms > 240 else "OK"}</span></td></tr>
<tr><td>P99 Latency</td><td>{qbr.p99_latency_ms:.0f} ms</td><td><span class="badge {'badge-warn' if qbr.p99_latency_ms > 280 else 'badge-ok'}">{"WATCH" if qbr.p99_latency_ms > 280 else "OK"}</span></td></tr>
<tr><td>SLA Compliance</td><td style="color:{sla_c};font-weight:600">{qbr.sla_compliance_pct:.1f}%</td><td><span class="badge {'badge-ok' if qbr.sla_compliance_pct >= 99.0 else 'badge-warn'}">{"MET" if qbr.sla_compliance_pct >= 99.0 else "AT RISK"}</span></td></tr>
<tr><td>Data Uploaded</td><td>{qbr.data_uploaded_gb / 1024:.2f} TB</td><td><span class="badge badge-ok">OK</span></td></tr>
<tr><td>Models Fine-tuned</td><td>{qbr.models_fine_tuned}</td><td><span class="badge badge-ok">OK</span></td></tr>
<tr><td>Best SR</td><td style="color:{sr_c};font-weight:600">{qbr.best_sr:.0%}</td><td><span class="badge {'badge-ok' if qbr.best_sr >= 0.60 else 'badge-warn'}">{"STRONG" if qbr.best_sr >= 0.60 else "IMPROVING"}</span></td></tr>
<tr><td>Budget Used</td><td>{qbr.budget_used_pct:.0f}%</td><td><span class="badge {'badge-warn' if qbr.budget_used_pct < 30 else 'badge-ok'}">{"LOW" if qbr.budget_used_pct < 30 else "OK"}</span></td></tr>
</tbody></table></section>
<section><div class="section-title">Recommendations</div>
<table class="metrics-table"><tbody>{rec_rows}</tbody></table></section>"""
    if not standalone: return content
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/>
<title>QBR — {qbr.partner_name} — {qbr.quarter}</title>{_inline_css()}</head>
<body><header><div class="header-inner"><div><h1>OCI Robot Cloud</h1>
<div class="subtitle">Quarterly Business Review — {qbr.quarter}</div></div>
<div class="partner-badge" style="border-color:{tc}">
<div class="partner-name">{qbr.partner_name}</div>
<div class="tier-label" style="color:{tc}">Tier {qbr.tier} Partner</div></div></div></header>
<main>{content}</main>
<footer><span>OCI Robot Cloud — Partner QBR Generator v2 — Port {PORT}</span><span>Oracle Confidential</span></footer>
</body></html>"""


def _build_dashboard():
    all_qbrs = [_QBR_STORE[pid] for pid in _PARTNER_ORDER]
    total_rev = sum(q.total_spend_usd for q in all_qbrs)
    total_gpu = sum(q.total_gpu_hours for q in all_qbrs)
    avg_sla = sum(q.sla_compliance_pct for q in all_qbrs) / len(all_qbrs)
    total_jobs = sum(q.total_jobs for q in all_qbrs)
    total_success = sum(q.successful_jobs for q in all_qbrs)
    kpi_row = "".join([
        _kpi_card("Total Revenue", f"${total_rev:,.0f}"),
        _kpi_card("Total GPU Hours", f"{total_gpu:.0f}"),
        _kpi_card("Avg SLA", f"{avg_sla:.1f}%", _sla_color(avg_sla)),
        _kpi_card("Total Jobs", f"{total_jobs:,}"),
        _kpi_card("Overall Success", f"{total_success/total_jobs*100:.1f}%", "#16a34a"),
        _kpi_card("Partners", str(len(all_qbrs))),
    ])
    partner_rows = ""
    for qbr in all_qbrs:
        tc = _TIER_COLORS.get(qbr.tier, "#6b7280")
        sla_c = _sla_color(qbr.sla_compliance_pct)
        sr_c = _sr_color(qbr.best_sr)
        sp = qbr.successful_jobs / qbr.total_jobs * 100 if qbr.total_jobs else 0
        partner_rows += (f"<tr><td><strong>{qbr.partner_name}</strong></td>"
                         f"<td><span style='color:{tc};font-weight:600'>Tier {qbr.tier}</span></td>"
                         f"<td>{qbr.total_jobs:,}</td><td>{sp:.1f}%</td>"
                         f"<td>{qbr.total_gpu_hours:.0f}</td><td>${qbr.total_spend_usd:,.0f}</td>"
                         f"<td>{qbr.avg_latency_ms:.0f} ms</td><td>{qbr.p99_latency_ms:.0f} ms</td>"
                         f"<td style='color:{sla_c};font-weight:600'>{qbr.sla_compliance_pct:.1f}%</td>"
                         f"<td style='color:{sr_c};font-weight:600'>{qbr.best_sr:.0%}</td>"
                         f"<td>{qbr.budget_used_pct:.0f}%</td>"
                         f"<td><a href='/qbr/{qbr.partner_id}/html' style='color:{ORACLE_RED}'>View QBR</a></td></tr>\n")
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/>
<title>Partner QBR Dashboard — OCI Robot Cloud</title>{_inline_css()}</head>
<body><header><div class="header-inner"><div>
<h1>OCI Robot Cloud — Partner QBR Dashboard</h1>
<div class="subtitle">{QUARTER} | Design Partner Overview</div>
</div></div></header><main>
<section><div class="section-title">Portfolio Summary</div><div class="kpi-row">{kpi_row}</div></section>
<section><div class="section-title">All Partners</div>
<table class="metrics-table"><thead><tr>
<th>Partner</th><th>Tier</th><th>Total Jobs</th><th>Job Success</th>
<th>GPU Hours</th><th>Spend</th><th>Avg Lat</th><th>P99 Lat</th>
<th>SLA</th><th>Best SR</th><th>Budget</th><th>Report</th>
</tr></thead><tbody>{partner_rows}</tbody></table></section></main>
<footer><span>OCI Robot Cloud Partner QBR Generator v2 — Port {PORT}</span><span>Oracle Confidential</span></footer>
</body></html>"""


try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="OCI Robot Cloud — Partner QBR Generator v2", version="2.0.0")

    @app.get("/qbr")
    def list_qbrs():
        return [{"partner_id": q.partner_id, "partner_name": q.partner_name, "tier": q.tier,
                 "quarter": q.quarter, "total_jobs": q.total_jobs, "total_spend_usd": q.total_spend_usd,
                 "sla_compliance_pct": q.sla_compliance_pct, "best_sr": q.best_sr, "budget_used_pct": q.budget_used_pct}
                for pid in _PARTNER_ORDER for q in [_QBR_STORE[pid]]]

    @app.get("/qbr/aggregate")
    def aggregate_qbr():
        all_q = list(_QBR_STORE.values())
        total_j = sum(q.total_jobs for q in all_q)
        return {"quarter": QUARTER, "partner_count": len(all_q),
                "total_revenue_usd": round(sum(q.total_spend_usd for q in all_q), 2),
                "total_gpu_hours": round(sum(q.total_gpu_hours for q in all_q), 1),
                "avg_sla_compliance_pct": round(sum(q.sla_compliance_pct for q in all_q) / len(all_q), 2),
                "total_jobs": total_j, "total_successful_jobs": sum(q.successful_jobs for q in all_q),
                "overall_job_success_pct": round(sum(q.successful_jobs for q in all_q) / total_j * 100, 2) if total_j else 0,
                "total_data_uploaded_tb": round(sum(q.data_uploaded_gb for q in all_q) / 1024, 2)}

    @app.get("/qbr/{partner_id}")
    def get_qbr(partner_id: str):
        if partner_id not in _QBR_STORE: raise HTTPException(status_code=404, detail=f"Partner '{partner_id}' not found")
        return asdict(_QBR_STORE[partner_id])

    @app.get("/qbr/{partner_id}/html", response_class=HTMLResponse)
    def get_qbr_html(partner_id: str):
        if partner_id not in _QBR_STORE: raise HTTPException(status_code=404, detail=f"Partner '{partner_id}' not found")
        return _render_partner_html(_QBR_STORE[partner_id], standalone=True)

    @app.post("/qbr/{partner_id}/regenerate")
    def regenerate_qbr(partner_id: str):
        if partner_id not in _QBR_STORE: raise HTTPException(status_code=404, detail=f"Partner '{partner_id}' not found")
        return {"status": "queued", "partner_id": partner_id,
                "message": f"QBR regeneration queued for {_QBR_STORE[partner_id].partner_name}",
                "job_id": str(uuid.uuid4()), "estimated_completion_seconds": 30}

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(): return _build_dashboard()


def _print_startup_summary():
    print("=" * 68)
    print(f"  OCI Robot Cloud — Partner QBR Generator v2  (port {PORT})")
    print(f"  Quarter: {QUARTER}   Total Revenue: ${TOTAL_REVENUE:,.2f}")
    print("=" * 68)
    print(f"  {'Partner':<24} {'Tier':>4} {'Jobs':>6} {'Success':>8} {'Spend':>8} {'SLA':>7} {'Best SR':>8} {'Budget':>7}")
    print("  " + "-" * 64)
    for pid in _PARTNER_ORDER:
        q = _QBR_STORE[pid]
        sp = q.successful_jobs / q.total_jobs * 100 if q.total_jobs else 0
        print(f"  {q.partner_name:<24} {q.tier:>4} {q.total_jobs:>6} {sp:>7.1f}% ${q.total_spend_usd:>6.0f} {q.sla_compliance_pct:>6.1f}% {q.best_sr:>7.0%} {q.budget_used_pct:>6.0f}%")
    print("=" * 68)


def main():
    _print_startup_summary()
    if not _FASTAPI_AVAILABLE:
        print("[WARN] fastapi/uvicorn not installed. Install with: pip install fastapi uvicorn")
        return
    uvicorn.run("partner_qbr_generator_v2:app", host="0.0.0.0", port=PORT, reload=False)


if __name__ == "__main__":
    main()

"""
sla_reporting_service.py — OCI Robot Cloud SLA Reporting Service
FastAPI port 8091 | Design Partner SLA tracking: uptime, latency, throughput, error rate
Oracle Confidential
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    print("[sla_reporting_service] FastAPI not available — running in CLI mode")

SLA_TARGETS: Dict[str, Dict] = {
    "uptime_pct":       {"target": 99.5,  "unit": "%",   "direction": "gte"},
    "p50_latency_ms":   {"target": 250.0, "unit": "ms",  "direction": "lte"},
    "p99_latency_ms":   {"target": 500.0, "unit": "ms",  "direction": "lte"},
    "throughput_rph":   {"target": 100.0, "unit": "r/h", "direction": "gte"},
    "error_rate_pct":   {"target": 2.0,   "unit": "%",   "direction": "lte"},
}

PARTNERS = ["covariant","apptronik","1x_technologies","skild_ai","physical_intelligence"]

PARTNER_PROFILES: Dict[str, Dict] = {
    "covariant":             {"uptime": 99.7, "p50": 218.0, "p99": 441.0, "tput": 142.0, "err": 0.8},
    "apptronik":             {"uptime": 99.2, "p50": 231.0, "p99": 462.0, "tput": 118.0, "err": 1.4},
    "1x_technologies":       {"uptime": 99.6, "p50": 226.0, "p99": 455.0, "tput": 127.0, "err": 1.1},
    "skild_ai":              {"uptime": 99.8, "p50": 211.0, "p99": 430.0, "tput": 156.0, "err": 0.5},
    "physical_intelligence": {"uptime": 99.5, "p50": 238.0, "p99": 489.0, "tput": 103.0, "err": 1.9},
}

def _gauss(rng: random.Random, base: float, spread: float) -> float:
    import math
    u1 = max(1e-10, rng.random())
    u2 = rng.random()
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return base + z * spread

def generate_daily_metrics(partner_id: str, days: int = 30) -> List[Dict]:
    profile = PARTNER_PROFILES[partner_id]
    rng = random.Random(hash(partner_id) % 999_983)
    now = datetime.utcnow()
    records = []
    for d in range(days):
        day = now - timedelta(days=(days - 1 - d))
        uptime_base = profile["uptime"]
        if partner_id == "apptronik" and d in (7, 21):
            uptime_base = 98.6
        uptime = min(100.0, _gauss(rng, uptime_base, 0.08))
        p50    = max(50.0,  _gauss(rng, profile["p50"],  6.0))
        p99    = max(80.0,  _gauss(rng, profile["p99"], 14.0))
        tput   = max(10.0,  _gauss(rng, profile["tput"],  4.0))
        err    = max(0.0,   _gauss(rng, profile["err"],   0.15))
        records.append({
            "date":           day.strftime("%Y-%m-%d"),
            "uptime_pct":     round(uptime, 3),
            "p50_latency_ms": round(p50, 1),
            "p99_latency_ms": round(p99, 1),
            "throughput_rph": round(tput, 1),
            "error_rate_pct": round(err, 3),
        })
    return records

def compute_aggregates(daily: List[Dict]) -> Dict:
    def avg(key: str) -> float:
        vals = [r[key] for r in daily]
        return round(sum(vals) / len(vals), 3) if vals else 0.0
    return {
        "uptime_pct":     round(min(r["uptime_pct"] for r in daily), 3),
        "p50_latency_ms": avg("p50_latency_ms"),
        "p99_latency_ms": avg("p99_latency_ms"),
        "throughput_rph": avg("throughput_rph"),
        "error_rate_pct": avg("error_rate_pct"),
    }

def sla_status(metric: str, value: float) -> str:
    spec   = SLA_TARGETS[metric]
    target = spec["target"]
    gte    = spec["direction"] == "gte"
    if gte:
        if value >= target:          return "GREEN"
        if value >= target * 0.995: return "YELLOW"
        return "RED"
    else:
        if value <= target:         return "GREEN"
        if value <= target * 1.05: return "YELLOW"
        return "RED"

def detect_breaches(partner_id: str, daily: List[Dict]) -> List[Dict]:
    breaches = []
    rng_dur = random.Random(hash(partner_id + "dur") % 88_003)
    for rec in daily:
        for metric, spec in SLA_TARGETS.items():
            val      = rec[metric]
            target   = spec["target"]
            gte      = spec["direction"] == "gte"
            breached = (gte and val < target) or (not gte and val > target)
            if breached:
                delta    = abs(val - target)
                severity = delta / target
                credit   = min(500.0, round(50.0 * (1.0 + severity * 10.0), 2))
                breaches.append({
                    "partner_id":         partner_id,
                    "date":               rec["date"],
                    "metric":             metric,
                    "observed":           val,
                    "target":             target,
                    "unit":               spec["unit"],
                    "delta":              round(delta, 4),
                    "severity":           "HIGH" if severity > 0.01 else "LOW",
                    "penalty_credit_usd": credit,
                    "resolved":           True,
                    "duration_min":       rng_dur.randint(4, 47),
                })
    return breaches

ALL_DAILY: Dict[str, List[Dict]]  = {p: generate_daily_metrics(p, 30) for p in PARTNERS}
ALL_AGGS:  Dict[str, Dict]        = {p: compute_aggregates(ALL_DAILY[p]) for p in PARTNERS}
ALL_SCORECARDS: Dict[str, Dict]   = {}
ALL_BREACHES:   List[Dict]        = []

for _p in PARTNERS:
    _agg   = ALL_AGGS[_p]
    _sc: Dict[str, Dict] = {}
    _green = 0
    for _metric in SLA_TARGETS:
        _st = sla_status(_metric, _agg[_metric])
        _sc[_metric] = {"value": _agg[_metric], "status": _st, "target": SLA_TARGETS[_metric]["target"], "unit": SLA_TARGETS[_metric]["unit"]}
        if _st == "GREEN": _green += 1
    _compliance = round(100.0 * _green / len(SLA_TARGETS), 1)
    ALL_SCORECARDS[_p] = {"partner_id": _p, "metrics": _sc, "compliance_pct": _compliance}
    ALL_BREACHES.extend(detect_breaches(_p, ALL_DAILY[_p]))
ALL_BREACHES.sort(key=lambda x: x["date"], reverse=True)

_STATUS_COLOR = {"GREEN": "#22c55e", "YELLOW": "#f59e0b", "RED": "#ef4444"}
_STATUS_BG    = {"GREEN": "rgba(34,197,94,0.15)", "YELLOW": "rgba(245,158,11,0.15)", "RED": "rgba(239,68,68,0.15)"}

def _badge(status: str) -> str:
    fg = _STATUS_COLOR.get(status, "#64748b")
    bg = _STATUS_BG.get(status, "rgba(100,116,139,0.15)")
    return f'<span style="background:{bg};color:{fg};padding:2px 9px;border-radius:4px;font-size:0.76em;font-weight:700;">{status}</span>'

def build_dashboard() -> str:
    total_breaches = len(ALL_BREACHES)
    total_credits  = round(sum(b["penalty_credit_usd"] for b in ALL_BREACHES), 2)
    partners_green = sum(1 for p in PARTNERS if ALL_SCORECARDS[p]["compliance_pct"] == 100.0)
    rows: List[str] = []
    for pid in PARTNERS:
        sc = ALL_SCORECARDS[pid]; comp = sc["compliance_pct"]; m = sc["metrics"]
        comp_color = "#22c55e" if comp == 100.0 else ("#f59e0b" if comp >= 80 else "#ef4444")
        rows.append(f"<tr><td style='font-weight:600;color:#e2e8f0'>{pid.replace('_',' ').title()}</td>"
            f"<td>{m['uptime_pct']['value']}% {_badge(m['uptime_pct']['status'])}</td>"
            f"<td>{m['p50_latency_ms']['value']} ms {_badge(m['p50_latency_ms']['status'])}</td>"
            f"<td>{m['p99_latency_ms']['value']} ms {_badge(m['p99_latency_ms']['status'])}</td>"
            f"<td>{m['throughput_rph']['value']} r/h {_badge(m['throughput_rph']['status'])}</td>"
            f"<td>{m['error_rate_pct']['value']}% {_badge(m['error_rate_pct']['status'])}</td>"
            f"<td style='color:{comp_color};font-weight:700'>{comp}%</td></tr>")
    breach_rows: List[str] = []
    for b in ALL_BREACHES[:20]:
        sev_color = "#ef4444" if b["severity"] == "HIGH" else "#f59e0b"
        breach_rows.append(f"<tr><td style='color:#94a3b8'>{b['date']}</td>"
            f"<td style='color:#e2e8f0'>{b['partner_id'].replace('_',' ').title()}</td>"
            f"<td style='color:#c084fc'>{b['metric']}</td><td>{b['observed']} {b['unit']}</td>"
            f"<td>{b['target']} {b['unit']}</td><td style='color:{sev_color};font-weight:700'>{b['severity']}</td>"
            f"<td>{b['duration_min']} min</td><td style='color:#fb923c'>${b['penalty_credit_usd']:.2f}</td></tr>")
    if not breach_rows:
        breach_rows.append("<tr><td colspan='8' style='color:#22c55e;text-align:center;padding:16px'>No SLA breaches recorded</td></tr>")
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>OCI Robot Cloud — SLA Reporting</title>
<style>body{{background:#0f172a;color:#cbd5e1;font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:0}}
.hdr{{background:#1e293b;border-bottom:2px solid #C74634;padding:18px 32px}}
h1{{color:#C74634;margin:0 0 4px;font-size:1.4em}}h2{{color:#C74634;border-bottom:1px solid #334155;padding-bottom:6px;margin:32px 0 12px;font-size:1.05em}}
.wrap{{max-width:1280px;margin:0 auto;padding:24px 32px}}.stats{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px}}
.stat{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 22px;min-width:130px}}
.sv{{font-size:1.7em;font-weight:700;color:#e2e8f0}}.sl{{font-size:0.75em;color:#64748b;margin-top:3px}}
table{{border-collapse:collapse;width:100%;margin-top:8px}}th{{background:#1e293b;color:#94a3b8;font-size:0.76em;text-transform:uppercase;padding:9px 11px;text-align:left;border-bottom:1px solid #334155}}
td{{padding:8px 11px;border-bottom:1px solid #1e293b;font-size:0.87em}}tr:hover td{{background:#1e293b55}}
.footer{{margin-top:40px;text-align:center;color:#475569;font-size:0.74em;border-top:1px solid #1e293b;padding:12px 0 24px}}</style></head>
<body><div class="hdr"><h1>OCI Robot Cloud — SLA Reporting Dashboard</h1>
<span style="color:#64748b;font-size:0.85em">30-day rolling window &nbsp;|&nbsp; Generated {generated} UTC &nbsp;|&nbsp; Port 8091</span></div>
<div class="wrap"><div class="stats">
<div class="stat"><div class="sv">{len(PARTNERS)}</div><div class="sl">Design Partners</div></div>
<div class="stat"><div class="sv" style="color:#22c55e">{partners_green}</div><div class="sl">100% Compliant</div></div>
<div class="stat"><div class="sv" style="color:#ef4444">{total_breaches}</div><div class="sl">Total Breaches</div></div>
<div class="stat"><div class="sv" style="color:#fb923c">${total_credits:,.2f}</div><div class="sl">Penalty Credits</div></div></div>
<h2>SLA Scorecard — 30-Day Aggregates</h2><table><thead><tr>
<th>Partner</th><th>Uptime (&ge;99.5%)</th><th>P50 Latency (&le;250 ms)</th><th>P99 Latency (&le;500 ms)</th>
<th>Throughput (&ge;100 r/h)</th><th>Error Rate (&lt;2%)</th><th>Compliance</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<h2>SLA Breach Log — Latest 20 Events</h2><table><thead><tr>
<th>Date</th><th>Partner</th><th>Metric</th><th>Observed</th><th>Target</th><th>Severity</th><th>Duration</th><th>Penalty Credit</th>
</tr></thead><tbody>{''.join(breach_rows)}</tbody></table>
<div class="footer">Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; SLA Reporting Service v1.0 &nbsp;|&nbsp; GR00T N1.6 Platform</div>
</div></body></html>"""

if _FASTAPI:
    app = FastAPI(title="OCI Robot Cloud — SLA Reporting", version="1.0.0",
        description="Design partner SLA tracking: uptime, latency, throughput, error rate.")

    @app.get("/", response_class=HTMLResponse)
    def dashboard(): return HTMLResponse(content=build_dashboard())

    @app.get("/health")
    def health(): return {"status": "ok", "service": "sla_reporting", "port": 8091}

    @app.get("/sla")
    def all_sla(): return JSONResponse(content={"partners": ALL_SCORECARDS, "sla_targets": SLA_TARGETS, "generated_utc": datetime.utcnow().isoformat()})

    @app.get("/sla/{partner_id}")
    def partner_sla(partner_id: str):
        if partner_id not in PARTNERS: raise HTTPException(status_code=404, detail=f"Partner '{partner_id}' not found")
        return JSONResponse(content={"scorecard": ALL_SCORECARDS[partner_id], "aggregates": ALL_AGGS[partner_id], "daily": ALL_DAILY[partner_id]})

    @app.get("/breaches")
    def breach_log(partner_id: Optional[str] = None, severity: Optional[str] = None):
        result = list(ALL_BREACHES)
        if partner_id: result = [b for b in result if b["partner_id"] == partner_id]
        if severity:   result = [b for b in result if b["severity"] == severity.upper()]
        return JSONResponse(content={"count": len(result), "total_penalty_credits_usd": round(sum(b["penalty_credit_usd"] for b in result), 2), "breaches": result})

def _cli_report() -> None:
    print("\n=== OCI Robot Cloud — SLA Report (30-day rolling) ===\n")
    for pid in PARTNERS:
        agg = ALL_AGGS[pid]; comp = ALL_SCORECARDS[pid]["compliance_pct"]
        print(f"{pid:<27} uptime={agg['uptime_pct']:.3f}% p50={agg['p50_latency_ms']:.1f}ms p99={agg['p99_latency_ms']:.1f}ms tput={agg['throughput_rph']:.1f} err={agg['error_rate_pct']:.3f}% compliance={comp:.1f}%")
    print(f"\nBreaches: {len(ALL_BREACHES)} | Credits: ${sum(b['penalty_credit_usd'] for b in ALL_BREACHES):,.2f}")

if __name__ == "__main__":
    if _FASTAPI: uvicorn.run(app, host="0.0.0.0", port=8091, log_level="info")
    else: _cli_report()

"""
deployment_scheduler.py — FastAPI port 8101
Deployment scheduler for GR00T policy rollouts across OCI regions.

Oracle Confidential
"""

import math
import datetime
from typing import List, Dict, Any, Optional

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ---------------------------------------------------------------------------
# Deployment queue
# ---------------------------------------------------------------------------
DEPLOYMENT_QUEUE: List[Dict[str, Any]] = [
    {"id": "deploy_001", "model": "dagger_run9_v2.2", "target": "ashburn prod", "region": "us-ashburn-1",
     "scheduled": "2026-03-28T02:00:00Z", "status": "COMPLETED", "duration_min": 4.2,
     "started": "2026-03-28T02:00:00Z", "finished": "2026-03-28T02:04:12Z"},
    {"id": "deploy_002", "model": "groot_finetune_v2", "target": "ashburn canary", "region": "us-ashburn-1",
     "scheduled": "2026-03-29T03:00:00Z", "status": "COMPLETED", "duration_min": 3.8,
     "started": "2026-03-29T03:00:00Z", "finished": "2026-03-29T03:03:48Z"},
    {"id": "deploy_003", "model": "groot_finetune_v2", "target": "phoenix eval", "region": "us-phoenix-1",
     "scheduled": "2026-03-30T02:00:00Z", "status": "RUNNING", "duration_min": None,
     "started": "2026-03-30T02:00:00Z", "finished": None},
    {"id": "deploy_004", "model": "groot_finetune_v2", "target": "frankfurt staging", "region": "eu-frankfurt-1",
     "scheduled": "2026-03-30T04:00:00Z", "status": "PENDING", "duration_min": None,
     "started": None, "finished": None},
    {"id": "deploy_005", "model": "dagger_run9_v2.2", "target": "all regions health check", "region": "all",
     "scheduled": "2026-03-31T00:00:00Z", "status": "PENDING", "duration_min": None,
     "started": None, "finished": None},
    {"id": "deploy_006", "model": "groot_finetune_v2", "target": "ashburn prod (promotion)", "region": "us-ashburn-1",
     "scheduled": "2026-04-01T02:00:00Z", "status": "PENDING", "duration_min": None,
     "started": None, "finished": None},
    {"id": "deploy_007", "model": "model_v3_candidate", "target": "ashburn canary", "region": "us-ashburn-1",
     "scheduled": "2026-04-07T03:00:00Z", "status": "PENDING", "duration_min": None,
     "started": None, "finished": None},
    {"id": "deploy_008", "model": "model_v3_candidate", "target": "all regions", "region": "all",
     "scheduled": "2026-04-14T02:00:00Z", "status": "PENDING", "duration_min": None,
     "started": None, "finished": None},
]

MAINTENANCE_WINDOWS: Dict[str, str] = {
    "us-ashburn-1":   "02:00-04:00 UTC Mon",
    "us-phoenix-1":   "02:00-04:00 UTC Tue",
    "eu-frankfurt-1": "02:00-04:00 UTC Wed",
}

_NOW = datetime.datetime(2026, 3, 30, 8, 0, 0, tzinfo=datetime.timezone.utc)
_MW_WEEKDAY = {"us-ashburn-1": 0, "us-phoenix-1": 1, "eu-frankfurt-1": 2}
_MW_START_H = 2
_MW_END_H   = 4


def _parse_dt(ts: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _in_maintenance_window(region: str, scheduled_ts: str) -> bool:
    if region == "all":
        return True
    weekday = _MW_WEEKDAY.get(region)
    if weekday is None:
        return False
    dt = _parse_dt(scheduled_ts)
    return dt.weekday() == weekday and _MW_START_H <= dt.hour < _MW_END_H


def schedule_health_check() -> Dict[str, Any]:
    pending = [d for d in DEPLOYMENT_QUEUE if d["status"] == "PENDING"]
    bucket_map: Dict[str, List[str]] = {}
    for d in pending:
        if d["region"] == "all":
            continue
        dt = _parse_dt(d["scheduled"])
        key = f"{d['region']}|{dt.strftime('%Y-%m-%dT%H')}"
        bucket_map.setdefault(key, []).append(d["id"])

    results = []
    for d in pending:
        issues = []
        if not _in_maintenance_window(d["region"], d["scheduled"]):
            issues.append(f"Scheduled outside maintenance window for {d['region']} ({MAINTENANCE_WINDOWS.get(d['region'], 'N/A')})")
        if d["region"] != "all":
            dt = _parse_dt(d["scheduled"])
            key = f"{d['region']}|{dt.strftime('%Y-%m-%dT%H')}"
            conflicting = [x for x in bucket_map.get(key, []) if x != d["id"]]
            if conflicting:
                issues.append(f"Time conflict with: {', '.join(conflicting)}")
        results.append({"id": d["id"], "model": d["model"], "target": d["target"],
                        "scheduled": d["scheduled"], "pass": len(issues) == 0, "issues": issues})

    passing = sum(1 for r in results if r["pass"])
    return {"checked": len(results), "passing": passing, "failing": len(results) - passing, "results": results}


def upcoming_deployments(days: int = 7) -> List[Dict[str, Any]]:
    cutoff = _NOW + datetime.timedelta(days=days)
    return sorted(
        [d for d in DEPLOYMENT_QUEUE if d["status"] == "PENDING" and _NOW <= _parse_dt(d["scheduled"]) <= cutoff],
        key=lambda x: x["scheduled"]
    )


def deployment_gantt_svg() -> str:
    W, H = 700, 180
    PL, PR, PT, PB = 130, 15, 30, 30
    inner_w = W - PL - PR
    inner_h = H - PT - PB
    start_date = datetime.date(2026, 3, 28)
    end_date   = datetime.date(2026, 4, 14)
    total_days = (end_date - start_date).days + 1
    REGIONS_ORDER = ["us-ashburn-1", "us-phoenix-1", "eu-frankfurt-1", "all"]
    region_labels = {"us-ashburn-1": "Ashburn", "us-phoenix-1": "Phoenix", "eu-frankfurt-1": "Frankfurt", "all": "All Regions"}
    n_rows = len(REGIONS_ORDER)
    row_h  = inner_h / n_rows
    STATUS_COLOR = {"COMPLETED": "#22c55e", "RUNNING": "#38bdf8", "PENDING": "#f59e0b", "FAILED": "#ef4444"}

    def date_x(dt_str):
        dt = _parse_dt(dt_str)
        return PL + ((dt.date() - start_date).days + dt.hour / 24.0) / total_days * inner_w

    def row_y(region):
        idx = REGIONS_ORDER.index(region) if region in REGIONS_ORDER else n_rows - 1
        return PT + idx * row_h + row_h * 0.2

    bar_h = row_h * 0.6
    grid_lines = ""
    for i in range(total_days + 1):
        d = start_date + datetime.timedelta(days=i)
        x = PL + i / total_days * inner_w
        color = "#334155" if d.weekday() not in (5, 6) else "#1e3a5f"
        grid_lines += f'<line x1="{x:.1f}" y1="{PT}" x2="{x:.1f}" y2="{PT + inner_h}" stroke="{color}" stroke-width="0.5"/>'
        if i % 3 == 0:
            grid_lines += f'<text x="{x:.1f}" y="{H - 5}" text-anchor="middle" font-size="8" fill="#64748b">{d.strftime("%b %d")}</text>'

    row_labels = ""
    for region in REGIONS_ORDER:
        y_c = PT + REGIONS_ORDER.index(region) * row_h + row_h / 2 + 4
        row_labels += f'<text x="{PL - 6}" y="{y_c:.1f}" text-anchor="end" font-size="9" fill="#94a3b8">{region_labels[region]}</text>'

    bars = ""
    for d in DEPLOYMENT_QUEUE:
        region = d["region"] if d["region"] in REGIONS_ORDER else "all"
        x1 = date_x(d["scheduled"])
        if d["status"] == "COMPLETED" and d["duration_min"]:
            bar_w = max(6.0, d["duration_min"] / 60 / total_days * inner_w)
        elif d["status"] == "RUNNING":
            elapsed_h = (_NOW - _parse_dt(d["started"])).total_seconds() / 3600 if d["started"] else 2
            bar_w = max(6.0, elapsed_h / total_days * inner_w)
        else:
            bar_w = max(6.0, 2.0 / 24 / total_days * inner_w)
        x1 = max(PL, min(x1, PL + inner_w - 4))
        bar_w = min(bar_w, PL + inner_w - x1)
        y_top = row_y(region)
        color = STATUS_COLOR.get(d["status"], "#94a3b8")
        bars += (f'<rect x="{x1:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{color}" rx="3" opacity="0.85"/>'
                 f'<title>{d["id"]}: {d["model"]} ({d["status"]})</title>')
        if bar_w > 28:
            bars += f'<text x="{x1 + bar_w/2:.1f}" y="{y_top + bar_h/2 + 4:.1f}" text-anchor="middle" font-size="7" fill="#0f172a" font-weight="700">{d["id"][-3:]}</text>'

    return (f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="{W}" height="{H}" fill="#1e293b" rx="6"/>'
            f'<text x="{W//2}" y="18" text-anchor="middle" font-size="11" fill="#e2e8f0" font-family="monospace">Deployment Schedule — Mar 28 to Apr 14, 2026</text>'
            f'{grid_lines}{row_labels}{bars}'
            f'<rect x="{PL}" y="{H - PB + 4}" width="10" height="8" fill="#22c55e" rx="2"/>'
            f'<text x="{PL + 13}" y="{H - PB + 12}" font-size="8" fill="#94a3b8">COMPLETED</text>'
            f'<rect x="{PL + 80}" y="{H - PB + 4}" width="10" height="8" fill="#38bdf8" rx="2"/>'
            f'<text x="{PL + 93}" y="{H - PB + 12}" font-size="8" fill="#94a3b8">RUNNING</text>'
            f'<rect x="{PL + 150}" y="{H - PB + 4}" width="10" height="8" fill="#f59e0b" rx="2"/>'
            f'<text x="{PL + 163}" y="{H - PB + 12}" font-size="8" fill="#94a3b8">PENDING</text>'
            f'<rect x="{PL + 215}" y="{H - PB + 4}" width="10" height="8" fill="#ef4444" rx="2"/>'
            f'<text x="{PL + 228}" y="{H - PB + 12}" font-size="8" fill="#94a3b8">FAILED</text>'
            f'</svg>')


def build_dashboard() -> str:
    gantt_svg = deployment_gantt_svg()
    upcoming  = upcoming_deployments(days=7)
    health    = schedule_health_check()
    total     = len(DEPLOYMENT_QUEUE)
    pending   = sum(1 for d in DEPLOYMENT_QUEUE if d["status"] == "PENDING")
    completed = sum(1 for d in DEPLOYMENT_QUEUE if d["status"] == "COMPLETED")
    running   = sum(1 for d in DEPLOYMENT_QUEUE if d["status"] == "RUNNING")
    failed    = sum(1 for d in DEPLOYMENT_QUEUE if d["status"] == "FAILED")

    SC = {"COMPLETED": "#22c55e", "RUNNING": "#38bdf8", "PENDING": "#f59e0b", "FAILED": "#ef4444"}
    def badge(s): c=SC.get(s,"#94a3b8"); return f'<span style="background:{c}22;color:{c};border:1px solid {c};border-radius:12px;padding:2px 9px;font-size:11px;font-weight:600">{s}</span>'

    def chip(val, label, color):
        return (f'<div style="background:#1e293b;border:1px solid {"#ef4444" if color=="red" else "#334155"};border-radius:8px;padding:12px 20px;text-align:center;min-width:90px;">'
                f'<div style="font-size:24px;font-weight:700;color:{color}">{val}</div>'
                f'<div style="font-size:11px;color:#64748b">{label}</div></div>')

    hc = '#22c55e' if health['failing']==0 else '#ef4444'
    chips = '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px;">'
    chips += chip(total, "Total", "#e2e8f0") + chip(pending, "Pending", "#f59e0b")
    chips += chip(completed, "Completed", "#22c55e") + chip(running, "Running", "#38bdf8")
    if failed: chips += chip(failed, "Failed", "#ef4444")
    chips += chip(f"{health['passing']}/{health['checked']}", "Health Pass", hc) + "</div>"

    ts  = "width:100%;border-collapse:collapse;font-size:13px;"
    ths = "background:#0f172a;color:#94a3b8;padding:8px 12px;text-align:left;border-bottom:1px solid #334155;font-size:11px;"
    tds = "padding:7px 12px;border-bottom:1px solid #1e293b;color:#cbd5e1;"

    up_rows = "".join(
        f"<tr><td>{d['id']}</td><td style='color:#e2e8f0;font-weight:600'>{d['model']}</td><td>{d['target']}</td><td>{d['scheduled']}</td><td>{badge(d['status'])}</td></tr>"
        for d in upcoming
    ) or '<tr><td colspan="5" style="color:#64748b">No upcoming deployments in next 7 days.</td></tr>'

    health_rows = "".join(
        f"<tr><td>{r['id']}</td><td style='color:#e2e8f0'>{r['model']}</td><td>{r['target']}</td><td>{r['scheduled']}</td>"
        f"<td style='color:{'#22c55e' if r['pass'] else '#ef4444'};font-weight:700'>{'PASS' if r['pass'] else 'FAIL'}</td>"
        f"<td style='font-size:11px;color:#94a3b8'>{'; '.join(r['issues']) if r['issues'] else '—'}</td></tr>"
        for r in health["results"]
    )

    hist_rows = "".join(
        f"<tr><td>{d['id']}</td><td style='color:#e2e8f0;font-weight:600'>{d['model']}</td><td>{d['target']}</td>"
        f"<td>{d['scheduled']}</td><td>{badge(d['status'])}</td><td>{f\"{d['duration_min']:.1f} min\" if d['duration_min'] else '—'}</td></tr>"
        for d in DEPLOYMENT_QUEUE
    )

    mw_rows = "".join(
        f'<tr><td style="color:#e2e8f0">{r}</td><td style="color:#f59e0b">{w}</td></tr>'
        for r, w in MAINTENANCE_WINDOWS.items()
    )

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>OCI Robot Cloud — Deployment Scheduler</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;font-size:14px;padding:24px}}
h1{{font-size:20px;font-weight:700;color:#e2e8f0;margin-bottom:4px}}h2{{font-size:14px;font-weight:600;color:#94a3b8;margin:20px 0 10px}}
.card{{background:#1e293b;border-radius:8px;padding:18px;margin-bottom:18px}}table{{{ts}}}th{{{ths}}}td{{{tds}}}tr:hover td{{background:#273549}}
.footer{{color:#475569;font-size:11px;text-align:center;margin-top:32px}}</style></head><body>
<h1>&#x1F680; OCI Robot Cloud — Deployment Scheduler</h1>
<p style="color:#64748b;font-size:12px;margin-bottom:18px;">Port 8101 &nbsp;|&nbsp; {total} deployments &nbsp;|&nbsp; Reference: {_NOW.strftime('%Y-%m-%d %H:%M UTC')}</p>
<div class="card"><h2 style="margin-top:0">Overview</h2>{chips}</div>
<div class="card"><h2 style="margin-top:0">Gantt Chart</h2>{gantt_svg}</div>
<div class="card"><h2 style="margin-top:0">Upcoming Deployments (Next 7 Days)</h2>
<table><thead><tr><th>ID</th><th>Model</th><th>Target</th><th>Scheduled (UTC)</th><th>Status</th></tr></thead><tbody>{up_rows}</tbody></table></div>
<div class="card"><h2 style="margin-top:0">Schedule Health Check — Pending Deployments</h2>
<table><thead><tr><th>ID</th><th>Model</th><th>Target</th><th>Scheduled</th><th>Result</th><th>Issues</th></tr></thead>
<tbody>{health_rows or '<tr><td colspan="6" style="color:#64748b">No pending deployments.</td></tr>'}</tbody></table></div>
<div class="card"><h2 style="margin-top:0">Full Deployment History</h2>
<table><thead><tr><th>ID</th><th>Model</th><th>Target</th><th>Scheduled (UTC)</th><th>Status</th><th>Duration</th></tr></thead><tbody>{hist_rows}</tbody></table></div>
<div class="card"><h2 style="margin-top:0">Maintenance Windows</h2>
<table><thead><tr><th>Region</th><th>Window</th></tr></thead><tbody>{mw_rows}</tbody></table></div>
<p class="footer">Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; Deployment Scheduler v1.0</p></body></html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="Deployment Scheduler",
        description="GR00T policy rollout scheduler across OCI regions. Oracle Confidential.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def root(): return build_dashboard()

    @app.get("/schedule")
    def get_schedule(): return JSONResponse(content=DEPLOYMENT_QUEUE)

    @app.get("/upcoming")
    def get_upcoming(days: int = 7): return JSONResponse(content=upcoming_deployments(days=days))

    @app.get("/health-check")
    def get_health_check(): return JSONResponse(content=schedule_health_check())


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("OCI Robot Cloud — Deployment Scheduler")
    print("Oracle Confidential")
    print("=" * 60)
    total     = len(DEPLOYMENT_QUEUE)
    pending   = sum(1 for d in DEPLOYMENT_QUEUE if d["status"] == "PENDING")
    completed = sum(1 for d in DEPLOYMENT_QUEUE if d["status"] == "COMPLETED")
    running   = sum(1 for d in DEPLOYMENT_QUEUE if d["status"] == "RUNNING")
    print(f"\nTotal: {total}  |  Pending: {pending}  |  Running: {running}  |  Completed: {completed}")
    for d in upcoming_deployments(days=7):
        print(f"  {d['id']}  {d['model']:<25} → {d['target']:<30} [{d['scheduled']}]")
    health = schedule_health_check()
    print(f"\nHealth Check: {health['passing']}/{health['checked']} PASS")
    for r in health["results"]:
        if not r["pass"]:
            print(f"  FAIL {r['id']}: {'; '.join(r['issues'])}")
    out_path = "/tmp/deployment_schedule.html"
    with open(out_path, "w") as fh:
        fh.write(build_dashboard())
    print(f"\nHTML schedule saved to {out_path}")
    if HAS_FASTAPI:
        try:
            uvicorn.run(app, host="0.0.0.0", port=8101)
        except Exception as exc:
            print(f"Could not start FastAPI server: {exc}")


if __name__ == "__main__":
    main()

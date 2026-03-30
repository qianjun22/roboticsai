"""
OCI Robot Cloud — Alert Manager
Port 8108 | Tracks and displays active alerts across the fleet.
Oracle Confidential
"""

import math
import hashlib
import random
import datetime
import json
import collections

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

ALERT_RULES = {
    "sr_critical": {"condition": "SR < 0.40", "metric": "success_rate", "threshold": 0.40, "operator": "lt", "severity": "CRITICAL", "cooldown_min": 5, "description": "Success rate critically low — robot policy failing majority of tasks"},
    "sr_warning": {"condition": "SR < 0.60", "metric": "success_rate", "threshold": 0.60, "operator": "lt", "severity": "WARNING", "cooldown_min": 15, "description": "Success rate below acceptable baseline"},
    "latency_critical": {"condition": "p99 > 300ms", "metric": "inference_latency_p99_ms", "threshold": 300, "operator": "gt", "severity": "CRITICAL", "cooldown_min": 5, "description": "Inference latency critically high"},
    "latency_warning": {"condition": "p99 > 250ms", "metric": "inference_latency_p99_ms", "threshold": 250, "operator": "gt", "severity": "WARNING", "cooldown_min": 10, "description": "Inference latency elevated above target"},
    "error_rate": {"condition": "error_rate > 2.0%", "metric": "error_rate_pct", "threshold": 2.0, "operator": "gt", "severity": "CRITICAL", "cooldown_min": 5, "description": "API error rate exceeded 2% SLO"},
    "cost_spike": {"condition": "cost_per_run > $1.00", "metric": "cost_per_run_usd", "threshold": 1.00, "operator": "gt", "severity": "WARNING", "cooldown_min": 30, "description": "Per-run cost above budget threshold"},
    "drift_critical": {"condition": "config_drift_keys > 2", "metric": "config_drift_keys", "threshold": 2, "operator": "gt", "severity": "CRITICAL", "cooldown_min": 10, "description": "Multiple configuration keys drifted"},
    "queue_depth": {"condition": "pending_deployments > 5", "metric": "pending_deployments", "threshold": 5, "operator": "gt", "severity": "WARNING", "cooldown_min": 60, "description": "Deployment queue depth exceeded"},
}

ACTIVE_ALERTS = [
    {"id": "alert_001", "rule": "sr_critical", "target": "ashburn-shadow-1", "state": "FIRING", "severity": "CRITICAL", "fired_at": "2026-03-28T14:22:00Z", "resolved_at": None, "value": 0.31, "value_display": "SR 0.31", "message": "SR 0.31 below critical threshold 0.40"},
    {"id": "alert_002", "rule": "latency_warning", "target": "phoenix-eval-1", "state": "FIRING", "severity": "WARNING", "fired_at": "2026-03-29T09:15:00Z", "resolved_at": None, "value": 267, "value_display": "267ms p99", "message": "Inference latency p99 267ms exceeds warning threshold 250ms"},
    {"id": "alert_003", "rule": "drift_critical", "target": "ashburn-shadow-1", "state": "FIRING", "severity": "CRITICAL", "fired_at": "2026-03-29T11:30:00Z", "resolved_at": None, "value": 3, "value_display": "3 drifted keys", "message": "3 config keys drifted from desired state"},
    {"id": "alert_004", "rule": "cost_spike", "target": "frankfurt-staging-1", "state": "RESOLVED", "severity": "WARNING", "fired_at": "2026-03-27T16:00:00Z", "resolved_at": "2026-03-27T18:45:00Z", "value": 1.23, "value_display": "$1.23/run", "message": "Cost per run $1.23 exceeded threshold — resolved after batch job completion"},
    {"id": "alert_005", "rule": "sr_warning", "target": "ashburn-canary-1", "state": "FIRING", "severity": "WARNING", "fired_at": "2026-03-30T08:00:00Z", "resolved_at": None, "value": 0.52, "value_display": "SR 0.52", "message": "SR 0.52 below warning threshold 0.60 on canary"},
    {"id": "alert_006", "rule": "queue_depth", "target": "ashburn-prod-1", "state": "RESOLVED", "severity": "WARNING", "fired_at": "2026-03-28T20:00:00Z", "resolved_at": "2026-03-29T06:00:00Z", "value": 6, "value_display": "6 pending", "message": "Deployment queue depth 6 exceeded threshold 5 — resolved"},
]


def alert_summary():
    firing = sum(1 for a in ACTIVE_ALERTS if a["state"] == "FIRING")
    resolved = sum(1 for a in ACTIVE_ALERTS if a["state"] == "RESOLVED")
    critical = sum(1 for a in ACTIVE_ALERTS if a["severity"] == "CRITICAL" and a["state"] == "FIRING")
    warning = sum(1 for a in ACTIVE_ALERTS if a["severity"] == "WARNING" and a["state"] == "FIRING")
    return {"total": len(ACTIVE_ALERTS), "firing": firing, "resolved": resolved,
            "critical_firing": critical, "warning_firing": warning, "rules_defined": len(ALERT_RULES)}


def get_active_alerts():
    return [a for a in ACTIVE_ALERTS if a["state"] == "FIRING"]


def _parse_dt(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)


def build_svg_timeline():
    t_start = datetime.datetime(2026, 3, 27)
    t_end = datetime.datetime(2026, 3, 31)
    total_secs = (t_end - t_start).total_seconds()
    W, H, LEFT, TOP, LANE_H, LANE_GAP = 700, 160, 10, 20, 20, 4

    def tx(dt):
        return LEFT + max(0.0, min(1.0, (dt - t_start).total_seconds() / total_secs)) * (W - LEFT - 10)

    color_map = {("CRITICAL","FIRING"): "#ef4444", ("WARNING","FIRING"): "#f59e0b",
                 ("CRITICAL","RESOLVED"): "#6b7280", ("WARNING","RESOLVED"): "#6b7280"}
    parts = []
    for d in range(5):
        dt = datetime.datetime(2026, 3, 27 + d)
        x = tx(dt)
        parts.append(f'<line x1="{x:.1f}" y1="{TOP}" x2="{x:.1f}" y2="{H-10}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>')
        parts.append(f'<text x="{x:.1f}" y="{TOP-4}" font-size="9" fill="#94a3b8" text-anchor="middle">Mar {27+d}</text>')
    for i, alert in enumerate(ACTIVE_ALERTS):
        y = TOP + i * (LANE_H + LANE_GAP)
        fired = _parse_dt(alert["fired_at"])
        ended = _parse_dt(alert["resolved_at"]) if alert["resolved_at"] else datetime.datetime(2026, 3, 30, 12)
        x1, x2 = tx(fired), tx(ended)
        w = max(x2 - x1, 4.0)
        color = color_map.get((alert["severity"], alert["state"]), "#6b7280")
        parts.append(f'<rect x="{x1:.1f}" y="{y:.1f}" width="{w:.1f}" height="{LANE_H}" rx="3" fill="{color}" opacity="0.85"><title>{alert["id"]}: {alert["message"]}</title></rect>')
        parts.append(f'<text x="{x1+4:.1f}" y="{y+LANE_H/2+4:.1f}" font-size="8" fill="#f8fafc">{alert["id"]}</text>')
    return f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:8px;">\n{chr(10).join(parts)}\n</svg>'


def build_html():
    summary = alert_summary()
    svg = build_svg_timeline()
    sev_color = {"CRITICAL": "#ef4444", "WARNING": "#f59e0b"}
    state_color = {"FIRING": "#ef4444", "RESOLVED": "#22c55e"}

    def card(t, v, s="", c="#38bdf8"):
        return f'<div style="background:#1e293b;border-radius:8px;padding:16px 20px;min-width:130px;"><div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">{t}</div><div style="font-size:28px;font-weight:700;color:{c};">{v}</div><div style="font-size:11px;color:#64748b;margin-top:2px;">{s}</div></div>'

    cards = (card("FIRING", summary["firing"], "active alerts", "#ef4444") +
             card("CRITICAL", summary["critical_firing"], "firing critical", "#ef4444") +
             card("WARNING", summary["warning_firing"], "firing warning", "#f59e0b") +
             card("RESOLVED", summary["resolved"], "last 72h", "#22c55e") +
             card("RULES", summary["rules_defined"], "defined", "#38bdf8"))

    rows = "".join(
        f'<tr><td style="color:#f8fafc;font-weight:600;">{a["id"]}</td>'
        f'<td style="color:#94a3b8;">{a["rule"]}</td>'
        f'<td style="color:#38bdf8;">{a["target"]}</td>'
        f'<td><span style="color:{sev_color.get(a["severity"],"#94a3b8")};font-weight:700;">{a["severity"]}</span></td>'
        f'<td><span style="color:{state_color.get(a["state"],"#94a3b8")};font-weight:600;">{a["state"]}</span></td>'
        f'<td style="color:#f8fafc;">{a["value_display"]}</td>'
        f'<td style="color:#94a3b8;font-size:11px;">{a["fired_at"]}</td>'
        f'<td style="color:#64748b;font-size:11px;">{a["resolved_at"] or "—"}</td>'
        f'<td style="color:#cbd5e1;font-size:11px;">{a["message"]}</td></tr>'
        for a in ACTIVE_ALERTS
    )
    rule_rows = "".join(
        f'<tr><td style="color:#38bdf8;font-weight:600;">{n}</td>'
        f'<td style="color:#f8fafc;">{r["condition"]}</td>'
        f'<td><span style="color:{sev_color.get(r["severity"],"#94a3b8")};font-weight:700;">{r["severity"]}</span></td>'
        f'<td style="color:#94a3b8;">{r["cooldown_min"]}m</td>'
        f'<td style="color:#64748b;font-size:11px;">{r["description"]}</td></tr>'
        for n, r in ALERT_RULES.items()
    )
    th = 'style="padding:8px 12px;text-align:left;font-size:11px;color:#64748b;border-bottom:1px solid #334155;font-weight:600;text-transform:uppercase;"'
    td = 'style="padding:8px 12px;border-bottom:1px solid #1e293b;vertical-align:top;"'
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>OCI Robot Cloud — Alert Manager</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#f8fafc;font-family:system-ui,sans-serif;padding:24px}}
h1{{color:#C74634;font-size:22px;font-weight:700;margin-bottom:4px}}h2{{color:#C74634;font-size:15px;font-weight:600;margin:28px 0 12px}}
.subtitle{{color:#64748b;font-size:12px;margin-bottom:24px}}.cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:28px}}
table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
th{{{th}padding:10px 12px}}td{{{td}}}tr:last-child td{{border-bottom:none}}tr:hover td{{background:#0f172a}}
.section{{margin-bottom:32px}}footer{{margin-top:40px;text-align:center;color:#334155;font-size:11px}}</style></head><body>
<h1>OCI Robot Cloud — Alert Manager</h1><div class="subtitle">Fleet-wide alert tracking | Port 8108 | 2026-03-30</div>
<div class="cards">{cards}</div>
<div class="section"><h2>Alert Timeline (Mar 27–30)</h2><div style="overflow-x:auto;padding:4px 0;">{svg}</div>
<div style="font-size:10px;color:#475569;margin-top:6px;"><span style="color:#ef4444;">&#9632;</span> CRITICAL &nbsp;<span style="color:#f59e0b;">&#9632;</span> WARNING &nbsp;<span style="color:#6b7280;">&#9632;</span> RESOLVED</div></div>
<div class="section"><h2>All Alerts</h2><table><thead><tr><th>ID</th><th>Rule</th><th>Target</th><th>Severity</th><th>State</th><th>Value</th><th>Fired</th><th>Resolved</th><th>Message</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="section"><h2>Alert Rules</h2><table><thead><tr><th>Rule</th><th>Condition</th><th>Severity</th><th>Cooldown</th><th>Description</th></tr></thead><tbody>{rule_rows}</tbody></table></div>
<footer>Oracle Confidential | OCI Robot Cloud Alert Manager | Port 8108</footer></body></html>"""


if _FASTAPI_AVAILABLE:
    app = FastAPI(title="OCI Robot Cloud — Alert Manager", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(): return HTMLResponse(content=build_html())

    @app.get("/alerts")
    async def list_alerts(): return JSONResponse({"alerts": ACTIVE_ALERTS, "total": len(ACTIVE_ALERTS)})

    @app.get("/alerts/active")
    async def active_alerts():
        firing = get_active_alerts()
        return JSONResponse({"alerts": firing, "count": len(firing)})

    @app.get("/rules")
    async def list_rules(): return JSONResponse({"rules": ALERT_RULES, "count": len(ALERT_RULES)})

    @app.get("/health")
    async def health(): return JSONResponse({"status": "ok", "service": "alert_manager", "port": 8108, **alert_summary()})


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run("alert_manager:app", host="0.0.0.0", port=8108, reload=False)
    else:
        out = "/tmp/alert_manager.html"
        with open(out, "w") as f: f.write(build_html())
        print(f"Saved to {out}")

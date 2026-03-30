"""
SLO Tracker — OCI Robot Cloud
Port: 8110
Tracks Service Level Objectives for production system.
"""

import math, hashlib, random, datetime, json, collections

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

SLOS = [
    {"name": "inference_latency_p99", "description": "P99 inference latency", "target": "<226ms", "target_value": 226.0, "target_op": "lt", "unit": "ms", "window": "30d", "current": 221.0, "status": "GOOD", "budget_remaining": 87, "notes": ""},
    {"name": "inference_availability", "description": "Inference endpoint availability", "target": ">99.9%", "target_value": 99.9, "target_op": "gt", "unit": "%", "window": "30d", "current": 99.94, "status": "GOOD", "budget_remaining": 40, "notes": "already burning budget"},
    {"name": "fine_tune_completion", "description": "Fine-tune time per 1000 steps", "target": "<45min", "target_value": 45.0, "target_op": "lt", "unit": "min", "window": "7d", "current": 38.0, "status": "GOOD", "budget_remaining": 100, "notes": ""},
    {"name": "sr_production", "description": "Success rate in production", "target": ">65%", "target_value": 65.0, "target_op": "gt", "unit": "%", "window": "7d", "current": 71.0, "status": "GOOD", "budget_remaining": 100, "notes": "dagger_run9_v2.2"},
    {"name": "api_error_rate", "description": "API error rate", "target": "<0.1%", "target_value": 0.1, "target_op": "lt", "unit": "%", "window": "24h", "current": 0.08, "status": "GOOD", "budget_remaining": 20, "notes": "nearly burned"},
    {"name": "fleet_sync_lag", "description": "Fleet config sync lag", "target": "<5min", "target_value": 5.0, "target_op": "lt", "unit": "min", "window": "1h", "current": 8.2, "status": "BREACHED", "budget_remaining": 0, "notes": "SLO breach"},
]


def _classify_budget(slo):
    if slo["status"] == "BREACHED": return "BREACHED"
    br = slo["budget_remaining"]
    if br <= 0: return "BREACHED"
    if br < 10: return "BURNED"
    if br <= 50: return "AT_RISK"
    return "GOOD"


def slo_summary():
    counts = collections.Counter()
    total_consumed = 0
    for slo in SLOS:
        counts[_classify_budget(slo)] += 1
        total_consumed += (100 - slo["budget_remaining"])
    return {"total": len(SLOS), "counts": dict(counts),
            "avg_error_budget_consumed_pct": round(total_consumed / len(SLOS) if SLOS else 0, 1),
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z"}


def _gen_availability_burn_series():
    rng = random.Random(42)
    raw = [rng.random() for _ in range(30)]
    total = sum(raw)
    return [v / total * 60.0 for v in raw]


def _build_burn_chart_svg():
    daily = _gen_availability_burn_series()
    cumulative, running = [], 0.0
    for v in daily:
        running += v
        cumulative.append(round(running, 2))
    W, H = 700, 160
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 20, 20, 35
    chart_w, chart_h = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    n = len(cumulative)

    def px(i, v):
        x = PAD_L + (i / (n - 1)) * chart_w
        y = PAD_T + chart_h - (v / 100.0) * chart_h
        return round(x, 1), round(y, 1)

    area_pts, line_pts = [], []
    for i, v in enumerate(cumulative):
        x, y = px(i, v)
        area_pts.append(f"{x},{y}")
        line_pts.append(f"{x},{y}")
    x_last, _ = px(n - 1, 0)
    x_first, _ = px(0, 0)
    y_bot = PAD_T + chart_h
    area_pts += [f"{x_last},{y_bot}", f"{x_first},{y_bot}"]
    _, y_exhaust = px(0, 100)

    y_labels = [(pct, round(PAD_T + chart_h - (pct / 100.0) * chart_h, 1)) for pct in [0, 25, 50, 75, 100]]
    x_labels = [(f"D{i+1}", round(PAD_L + (i / (n - 1)) * chart_w, 1)) for i in range(0, n, 5)]

    grid = "".join(f'<line x1="{PAD_L}" y1="{yy}" x2="{W-PAD_R}" y2="{yy}" stroke="#334155" stroke-width="1"/>' for _, yy in y_labels)
    y_axis = "".join(f'<text x="{PAD_L-6}" y="{yy+4}" font-size="10" fill="#94a3b8" text-anchor="end">{p}%</text>' for p, yy in y_labels)
    x_axis = "".join(f'<text x="{xx}" y="{PAD_T+chart_h+14}" font-size="9" fill="#64748b" text-anchor="middle">{lbl}</text>' for lbl, xx in x_labels)

    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px;"><defs><linearGradient id="aG" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#f97316" stop-opacity="0.6"/><stop offset="100%" stop-color="#f97316" stop-opacity="0.05"/></linearGradient></defs>{grid}<polygon points="{" ".join(area_pts)}" fill="url(#aG)"/><line x1="{PAD_L}" y1="{y_exhaust}" x2="{W-PAD_R}" y2="{y_exhaust}" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="6,3"/><text x="{W-PAD_R-2}" y="{y_exhaust-4}" font-size="9" fill="#ef4444" text-anchor="end">Budget Exhausted</text><polyline points="{" ".join(line_pts)}" fill="none" stroke="#f97316" stroke-width="2"/>{y_axis}{x_axis}<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+chart_h}" stroke="#475569" stroke-width="1"/><line x1="{PAD_L}" y1="{PAD_T+chart_h}" x2="{W-PAD_R}" y2="{PAD_T+chart_h}" stroke="#475569" stroke-width="1"/><text x="{W//2}" y="{PAD_T-5}" font-size="11" fill="#cbd5e1" text-anchor="middle">inference_availability — 30-day Error Budget Burn (cumulative %)</text></svg>'


_STATUS_COLORS = {"GOOD": ("#166534", "#4ade80"), "AT_RISK": ("#92400e", "#fbbf24"), "BURNED": ("#7c2d12", "#f97316"), "BREACHED": ("#7f1d1d", "#ef4444")}


def build_html():
    summary = slo_summary()
    burn_svg = _build_burn_chart_svg()
    counts = summary["counts"]

    def card(l, v, c="#38bdf8"):
        return f'<div style="background:#1e293b;border-radius:10px;padding:20px 24px;min-width:140px;flex:1;"><div style="font-size:12px;color:#64748b;margin-bottom:6px;">{l}</div><div style="font-size:28px;font-weight:700;color:{c};">{v}</div></div>'

    cards = (card("Total SLOs", summary["total"]) + card("GOOD", counts.get("GOOD", 0), "#4ade80") +
             card("AT_RISK", counts.get("AT_RISK", 0), "#fbbf24") + card("BURNED", counts.get("BURNED", 0), "#f97316") +
             card("BREACHED", counts.get("BREACHED", 0), "#ef4444") + card("Avg Budget Consumed", f'{summary["avg_error_budget_consumed_pct"]}%', "#f97316"))

    rows = "".join(
        f'<tr style="border-bottom:1px solid #334155;"><td style="padding:12px 14px;color:#e2e8f0;font-family:monospace;font-size:13px;">{s["name"]}</td>'
        f'<td style="padding:12px 14px;color:#94a3b8;font-size:13px;">{s["description"]}</td>'
        f'<td style="padding:12px 14px;color:#38bdf8;font-size:13px;">{s["target"]}</td>'
        f'<td style="padding:12px 14px;color:#e2e8f0;font-size:13px;">{s["current"]} {s["unit"]}</td>'
        f'<td style="padding:12px 14px;color:{"#4ade80" if s["budget_remaining"]>50 else ("#fbbf24" if s["budget_remaining"]>10 else "#ef4444")};font-size:13px;">{s["budget_remaining"]}%</td>'
        f'<td style="padding:12px 14px;"><span style="background:{_STATUS_COLORS.get(_classify_budget(s),("#1e293b","#e2e8f0"))[0]};color:{_STATUS_COLORS.get(_classify_budget(s),("#1e293b","#e2e8f0"))[1]};padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600;">{_classify_budget(s)}</span></td>'
        f'<td style="padding:12px 14px;color:#64748b;font-size:11px;">{s["notes"]}</td>'
        f'<td style="padding:12px 14px;color:#64748b;font-size:12px;">{s["window"]}</td></tr>'
        for s in SLOS
    )
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    th = 'style="padding:12px 14px;color:#C74634;text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:0.05em;"'
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>SLO Tracker — OCI Robot Cloud</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:32px}}
h1{{color:#C74634;font-size:24px;margin-bottom:4px}}h2{{color:#C74634;font-size:16px;margin-bottom:14px;margin-top:28px}}
.subtitle{{color:#64748b;font-size:13px;margin-bottom:28px}}.cards{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}}
footer{{margin-top:40px;color:#475569;font-size:11px;text-align:center;border-top:1px solid #1e293b;padding-top:16px}}</style></head><body>
<h1>SLO Tracker</h1><div class="subtitle">OCI Robot Cloud — Production Service Level Objectives &nbsp;|&nbsp; {now}</div>
<div class="cards">{cards}</div>
<h2>Error Budget Burn Chart</h2><div style="margin-bottom:28px;">{burn_svg}</div>
<h2>SLO Details</h2><div style="overflow-x:auto;margin-bottom:28px;">
<table style="width:100%;border-collapse:collapse;background:#1e293b;border-radius:10px;overflow:hidden;">
<thead><tr style="background:#0f172a;"><th {th}>SLO Name</th><th {th}>Description</th><th {th}>Target</th><th {th}>Current</th><th {th}>Budget Remaining</th><th {th}>Status</th><th {th}>Notes</th><th {th}>Window</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<footer>Oracle Confidential | OCI Robot Cloud SLO Tracker | Port 8110</footer></body></html>"""


if HAS_FASTAPI:
    app = FastAPI(title="SLO Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()

    @app.get("/slos")
    def list_slos(): return JSONResponse({"slos": SLOS})

    @app.get("/slos/{name}")
    def get_slo(name: str):
        for slo in SLOS:
            if slo["name"] == name: return JSONResponse({**slo, "computed_status": _classify_budget(slo)})
        raise HTTPException(status_code=404, detail=f"SLO '{name}' not found")

    @app.get("/summary")
    def get_summary(): return JSONResponse(slo_summary())

    @app.get("/burn-rate/{name}")
    def get_burn_rate(name: str):
        for slo in SLOS:
            if slo["name"] == name:
                series = _gen_availability_burn_series() if name == "inference_availability" else None
                return JSONResponse({"name": name, "budget_remaining": slo["budget_remaining"], "daily_burn_series": series})
        raise HTTPException(status_code=404, detail=f"SLO '{name}' not found")

    @app.get("/health")
    def health():
        breached = sum(1 for s in SLOS if _classify_budget(s) == "BREACHED")
        return JSONResponse({"status": "degraded" if breached > 0 else "ok", "breached_count": breached})


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run("slo_tracker:app", host="0.0.0.0", port=8110, reload=False)
    else:
        out = "/tmp/slo_report.html"
        with open(out, "w") as f: f.write(build_html())
        print(f"Saved to {out}")
        print(json.dumps(slo_summary(), indent=2))

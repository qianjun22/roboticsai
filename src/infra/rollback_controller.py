"""
rollback_controller.py — OCI Robot Cloud Automated Rollback Controller
FastAPI service on port 8103.

Tracks GR00T policy deployment rollback history, evaluates rollback rules,
and provides a dashboard for incident review.

Oracle Confidential — OCI Robot Cloud Platform
"""

import sys
from typing import Dict, List, Any

# ── Rollback history ────────────────────────────────────────────────────────────

ROLLBACK_HISTORY: List[Dict[str, Any]] = [
    {"id":"RB001","trigger":"sr_drop","from_version":"dagger_run7","to_version":"dagger_run6",
     "region":"us-ashburn-1","timestamp":"2026-02-10 03:41","reason":"SR dropped from 40% to 18% in 2h window",
     "success":True,"duration_min":4.2,"sr_before":0.40,"sr_after":0.39},
    {"id":"RB002","trigger":"latency_spike","from_version":"groot_finetune_v1","to_version":"dagger_run9",
     "region":"us-phoenix-1","timestamp":"2026-02-18 14:22","reason":"p99 latency 892ms > 500ms SLA",
     "success":True,"duration_min":2.8,"sr_before":0.68,"sr_after":0.70},
    {"id":"RB003","trigger":"error_rate","from_version":"dagger_run9_patched","to_version":"dagger_run9",
     "region":"eu-frankfurt-1","timestamp":"2026-02-25 09:15","reason":"error rate 8.2% > 2% threshold",
     "success":True,"duration_min":3.1,"sr_before":0.70,"sr_after":0.71},
    {"id":"RB004","trigger":"manual","from_version":"groot_finetune_v2_beta","to_version":"dagger_run9",
     "region":"us-ashburn-1","timestamp":"2026-03-05 16:03","reason":"Manual rollback by eng team (config error)",
     "success":True,"duration_min":1.5,"sr_before":0.73,"sr_after":0.71},
    {"id":"RB005","trigger":"sr_drop","from_version":"dagger_run9_lora","to_version":"dagger_run9",
     "region":"us-phoenix-1","timestamp":"2026-03-12 22:47","reason":"LoRA inference SR: 55% vs 71% expected",
     "success":True,"duration_min":3.7,"sr_before":0.55,"sr_after":0.71},
    {"id":"RB006","trigger":"cost_spike","from_version":"dagger_run9_debug","to_version":"dagger_run9",
     "region":"eu-frankfurt-1","timestamp":"2026-03-20 08:00","reason":"GPU cost 3.1x normal during debug mode",
     "success":True,"duration_min":0.8,"sr_before":0.71,"sr_after":0.71},
    {"id":"RB007","trigger":"latency_spike","from_version":"groot_finetune_v2","to_version":"dagger_run9",
     "region":"us-ashburn-1","timestamp":"2026-03-28 04:18","reason":"p99 latency 345ms > 300ms after deploy",
     "success":False,"duration_min":12.4,"sr_before":0.74,"sr_after":0.69},
]

ROLLBACK_RULES: Dict[str, float] = {
    "sr_drop_threshold": 0.10,
    "latency_p99_ms": 300.0,
    "error_rate_pct": 2.0,
    "cost_multiplier": 2.0,
}

# ── Core logic ───────────────────────────────────────────────────────────────────

def check_rollback_needed(current_sr, baseline_sr, p99_latency, error_rate, cost_mult) -> Dict[str, Any]:
    triggers = []
    sr_drop = baseline_sr - current_sr
    if sr_drop > ROLLBACK_RULES["sr_drop_threshold"]:
        triggers.append({"rule":"sr_drop_threshold","value":round(sr_drop,4),"threshold":ROLLBACK_RULES["sr_drop_threshold"],
                         "detail":f"SR dropped {sr_drop:.1%} (current={current_sr:.1%}, baseline={baseline_sr:.1%})"})
    if p99_latency > ROLLBACK_RULES["latency_p99_ms"]:
        triggers.append({"rule":"latency_p99_ms","value":p99_latency,"threshold":ROLLBACK_RULES["latency_p99_ms"],
                         "detail":f"p99 latency {p99_latency:.0f}ms > {ROLLBACK_RULES['latency_p99_ms']:.0f}ms SLA"})
    if error_rate > ROLLBACK_RULES["error_rate_pct"]:
        triggers.append({"rule":"error_rate_pct","value":error_rate,"threshold":ROLLBACK_RULES["error_rate_pct"],
                         "detail":f"Error rate {error_rate:.1f}% > {ROLLBACK_RULES['error_rate_pct']:.1f}% threshold"})
    if cost_mult > ROLLBACK_RULES["cost_multiplier"]:
        triggers.append({"rule":"cost_multiplier","value":cost_mult,"threshold":ROLLBACK_RULES["cost_multiplier"],
                         "detail":f"Cost {cost_mult:.1f}x baseline > {ROLLBACK_RULES['cost_multiplier']:.1f}x limit"})
    return {"rollback":len(triggers)>0,"triggers":triggers,
            "inputs":{"current_sr":current_sr,"baseline_sr":baseline_sr,"p99_latency_ms":p99_latency,
                      "error_rate_pct":error_rate,"cost_multiplier":cost_mult}}

def rollback_stats() -> Dict[str, Any]:
    total = len(ROLLBACK_HISTORY)
    successes = sum(1 for e in ROLLBACK_HISTORY if e["success"])
    avg_duration = sum(e["duration_min"] for e in ROLLBACK_HISTORY) / total if total else 0
    by_trigger: Dict[str, int] = {}
    by_region: Dict[str, int] = {}
    for e in ROLLBACK_HISTORY:
        by_trigger[e["trigger"]] = by_trigger.get(e["trigger"], 0) + 1
        by_region[e["region"]] = by_region.get(e["region"], 0) + 1
    last = ROLLBACK_HISTORY[-1] if ROLLBACK_HISTORY else None
    return {"total_rollbacks":total,"success_count":successes,"failed_count":total-successes,
            "success_rate_pct":round(100*successes/total,1) if total else 0,
            "avg_duration_min":round(avg_duration,2),"by_trigger":by_trigger,"by_region":by_region,
            "last_rollback_id":last["id"] if last else None,"last_rollback_ts":last["timestamp"] if last else None}

# ── SVG timeline ──────────────────────────────────────────────────────────────

def timeline_svg() -> str:
    width, height = 700, 150
    margin_l, margin_r = 60, 20
    axis_y = 90
    chart_w = width - margin_l - margin_r
    total_days = 59
    def day_x(ts):
        parts = ts.split(" ")[0].split("-")
        m, d = int(parts[1]), int(parts[2])
        offset = d - 1 if m == 2 else 28 + d - 1
        return margin_l + int(chart_w * offset / total_days)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#0f172a;font-family:monospace;">',
        f'<text x="{width//2}" y="14" text-anchor="middle" fill="#38bdf8" font-size="11" font-weight="bold">Rollback Timeline — Feb/Mar 2026</text>',
        f'<line x1="{margin_l}" y1="{axis_y}" x2="{width - margin_r}" y2="{axis_y}" stroke="#334155" stroke-width="1.5"/>',
        f'<text x="{margin_l + 4}" y="{axis_y - 50}" fill="#fbbf24" font-size="9">Rules: SR drop &gt;10pp | p99 &gt;300ms | err &gt;2% | cost &gt;2x</text>',
    ]
    for label, day_offset in (("Feb 2026", 0), ("Mar 2026", 28)):
        lx = margin_l + int(chart_w * day_offset / total_days)
        lines.append(f'<text x="{lx}" y="{axis_y + 18}" fill="#64748b" font-size="10">{label}</text>')
        lines.append(f'<line x1="{lx}" y1="{axis_y - 4}" x2="{lx}" y2="{axis_y + 4}" stroke="#475569" stroke-width="1"/>')
    for ev in ROLLBACK_HISTORY:
        ex = day_x(ev["timestamp"])
        color = "#22c55e" if ev["success"] else "#ef4444"
        lines.append(f'<circle cx="{ex}" cy="{axis_y}" r="7" fill="{color}" stroke="#0f172a" stroke-width="2"/>')
        lines.append(f'<text x="{ex}" y="{axis_y - 14}" text-anchor="middle" fill="{color}" font-size="9" font-weight="bold">{ev["id"]}</text>')
        lines.append(f'<line x1="{ex}" y1="{axis_y - 7}" x2="{ex}" y2="{axis_y - 11}" stroke="{color}" stroke-width="1"/>')
    lines += [f'<circle cx="{width - 120}" cy="130" r="5" fill="#22c55e"/>',
              f'<text x="{width - 112}" y="134" fill="#22c55e" font-size="9">Success</text>',
              f'<circle cx="{width - 70}" cy="130" r="5" fill="#ef4444"/>',
              f'<text x="{width - 62}" y="134" fill="#ef4444" font-size="9">Failed</text>',
              "</svg>"]
    return "\n".join(lines)

# ── HTML dashboard ─────────────────────────────────────────────────────────

def build_dashboard() -> str:
    stats = rollback_stats()
    svg = timeline_svg()
    def sr_delta(before, after):
        delta = after - before
        color = "#22c55e" if delta >= 0 else "#ef4444"
        sign = "+" if delta >= 0 else ""
        return f'<span style="color:{color}">{sign}{delta:.0%}</span>'
    history_rows = ""
    for ev in ROLLBACK_HISTORY:
        status_badge = ('<span style="background:#166534;color:#86efac;padding:2px 8px;border-radius:9px;font-size:11px;">SUCCESS</span>'
                        if ev["success"] else '<span style="background:#7f1d1d;color:#fca5a5;padding:2px 8px;border-radius:9px;font-size:11px;">FAILED</span>')
        tc = {"sr_drop":"#f97316","latency_spike":"#a78bfa","error_rate":"#ef4444",
               "cost_spike":"#fbbf24","manual":"#94a3b8"}.get(ev["trigger"],"#94a3b8")
        history_rows += (f"<tr><td style='color:#38bdf8;font-family:monospace;font-weight:bold;'>{ev['id']}</td>"
                         f"<td style='color:{tc};font-size:11px;'>{ev['trigger']}</td>"
                         f"<td style='color:#cbd5e1;font-size:11px;'>{ev['from_version']}</td>"
                         f"<td style='color:#94a3b8;font-size:11px;'>→ {ev['to_version']}</td>"
                         f"<td style='color:#64748b;font-size:11px;'>{ev['region']}</td>"
                         f"<td style='color:#94a3b8;font-size:11px;'>{ev['timestamp']}</td>"
                         f"<td>{status_badge}</td><td style='color:#fbbf24;text-align:center;'>{ev['duration_min']}m</td>"
                         f"<td style='color:#94a3b8;font-size:11px;'>{ev['sr_before']:.0%} → {ev['sr_after']:.0%} {sr_delta(ev['sr_before'],ev['sr_after'])}</td>"
                         f"<td style='color:#cbd5e1;font-size:11px;max-width:200px;'>{ev['reason']}</td></tr>")
    rules_html = "".join(
        f'<div style="background:#0f172a;border-radius:6px;padding:10px 14px;margin-bottom:8px;border-left:3px solid #C74634;">'
        f'<span style="color:#38bdf8;font-family:monospace;font-size:12px;">{rule}</span>'
        f'<span style="color:#fbbf24;font-size:14px;font-weight:bold;margin-left:12px;">{val}</span></div>'
        for rule, val in ROLLBACK_RULES.items()
    )
    by_trigger_html = "".join(f'<span style="background:#1e3a5f;color:#93c5fd;padding:4px 10px;border-radius:12px;font-size:12px;margin:2px;">{t}: {c}</span>' for t,c in stats["by_trigger"].items())
    by_region_html  = "".join(f'<span style="background:#1c1917;color:#a8a29e;padding:4px 10px;border-radius:12px;font-size:12px;margin:2px;">{r}: {c}</span>'  for r,c in stats["by_region"].items())
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Rollback Controller — Port 8103</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:-apple-system,monospace;padding:24px}}
h1{{color:#C74634;font-size:22px;margin-bottom:4px}}.sub{{color:#64748b;font-size:13px;margin-bottom:20px}}
.chips{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px}}.chip{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:8px 16px}}
.chip .val{{font-size:22px;font-weight:bold;color:#38bdf8}}.chip .lbl{{font-size:11px;color:#64748b;margin-top:2px}}
.card{{background:#1e293b;border-radius:10px;padding:16px;margin-bottom:20px;border:1px solid #334155}}
.card h2{{color:#38bdf8;font-size:14px;margin-bottom:12px}}.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#0f172a;color:#64748b;text-align:left;padding:8px 10px;border-bottom:1px solid #334155;font-size:11px;text-transform:uppercase}}
td{{padding:8px 10px;border-bottom:1px solid #1e293b;vertical-align:middle}}tr:hover td{{background:#243144}}
input{{background:#0f172a;border:1px solid #334155;color:#e2e8f0;padding:6px 10px;border-radius:6px;font-size:12px;width:90px}}
button{{background:#C74634;color:white;border:none;padding:7px 16px;border-radius:6px;cursor:pointer;font-size:13px;margin-left:8px}}
button:hover{{background:#a33828}}label{{color:#94a3b8;font-size:12px}}
pre{{background:#0f172a;padding:12px;border-radius:6px;font-size:11px;color:#a3e635;overflow-x:auto;white-space:pre-wrap;margin-top:10px}}
.footer{{color:#334155;font-size:11px;text-align:center;margin-top:30px}}</style></head><body>
<h1>Rollback Controller</h1><div class="sub">OCI Robot Cloud — Port 8103 — Automated GR00T Policy Deployment Safety</div>
<div class="chips">
<div class="chip"><div class="val">{stats['total_rollbacks']}</div><div class="lbl">Total Rollbacks</div></div>
<div class="chip"><div class="val" style="color:#22c55e;">{stats['success_rate_pct']}%</div><div class="lbl">Success Rate</div></div>
<div class="chip"><div class="val" style="color:#fbbf24;">{stats['avg_duration_min']}m</div><div class="lbl">Avg Duration</div></div>
<div class="chip"><div class="val" style="color:#a78bfa;">{stats['last_rollback_id']}</div><div class="lbl">Last Rollback ({stats['last_rollback_ts']})</div></div>
</div>
<div class="grid2">
<div class="card"><h2>Rollback Rules (Auto-Trigger Thresholds)</h2>{rules_html}</div>
<div class="card"><h2>By Trigger Type</h2><div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px;">{by_trigger_html}</div>
<h2 style="margin-top:12px;">By Region</h2><div style="display:flex;gap:6px;flex-wrap:wrap;">{by_region_html}</div></div>
</div>
<div class="card"><h2>Event Timeline</h2>{svg}</div>
<div class="card"><h2>Rollback History</h2><table>
<thead><tr><th>ID</th><th>Trigger</th><th>From Version</th><th>To Version</th><th>Region</th><th>Timestamp</th><th>Status</th><th>Duration</th><th>SR Change</th><th>Reason</th></tr></thead>
<tbody>{history_rows}</tbody></table></div>
<div class="card"><h2>Check Rollback Decision</h2>
<div style="display:flex;gap:16px;flex-wrap:wrap;align-items:flex-end;">
<div><label>Current SR (0-1)</label><br><input type="number" id="sr" value="0.60" step="0.01"></div>
<div><label>Baseline SR (0-1)</label><br><input type="number" id="bsr" value="0.71" step="0.01"></div>
<div><label>p99 Latency (ms)</label><br><input type="number" id="lat" value="320"></div>
<div><label>Error Rate (%)</label><br><input type="number" id="err" value="1.5" step="0.1"></div>
<div><label>Cost Multiplier</label><br><input type="number" id="cost" value="1.2" step="0.1"></div>
<button onclick="checkRollback()">Evaluate</button></div>
<pre id="check-result">Fill in values and click Evaluate.</pre></div>
<div class="footer">Oracle Confidential — OCI Robot Cloud Platform &copy; 2026</div>
<script>async function checkRollback(){{const body={{sr:parseFloat(document.getElementById('sr').value),
baseline_sr:parseFloat(document.getElementById('bsr').value),p99_ms:parseFloat(document.getElementById('lat').value),
error_rate:parseFloat(document.getElementById('err').value),cost_mult:parseFloat(document.getElementById('cost').value)}};
const pre=document.getElementById('check-result');pre.textContent='Evaluating...';
try{{const resp=await fetch('/check',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
const data=await resp.json();pre.textContent=JSON.stringify(data,null,2);pre.style.color=data.rollback?'#ef4444':'#a3e635';
}}catch(e){{pre.textContent='Error: '+e.message;}}}}</script></body></html>"""

# ── FastAPI ───────────────────────────────────────────────────────────────────────

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    app = FastAPI(title="Rollback Controller", version="1.0.0")

    class CheckRequest(BaseModel):
        sr: float; baseline_sr: float; p99_ms: float; error_rate: float; cost_mult: float

    @app.get("/", response_class=HTMLResponse)
    def dashboard(): return build_dashboard()

    @app.get("/history")
    def history(): return JSONResponse(content=ROLLBACK_HISTORY)

    @app.get("/rules")
    def rules(): return JSONResponse(content=ROLLBACK_RULES)

    @app.post("/check")
    def check(req: CheckRequest):
        return JSONResponse(content=check_rollback_needed(req.sr, req.baseline_sr, req.p99_ms, req.error_rate, req.cost_mult))

    @app.get("/stats")
    def stats(): return JSONResponse(content=rollback_stats())

except ImportError:
    app = None  # type: ignore

# ── CLI entrypoint ──────────────────────────────────────────────────────────

def main():
    s = rollback_stats()
    print(f"Total rollbacks : {s['total_rollbacks']}")
    print(f"Success rate    : {s['success_rate_pct']}%")
    print(f"Avg duration    : {s['avg_duration_min']} min")
    print(f"Last rollback   : {s['last_rollback_id']} @ {s['last_rollback_ts']}")
    html_path = "/tmp/rollback_controller.html"
    with open(html_path, "w") as fh: fh.write(build_dashboard())
    print(f"\nDashboard saved → {html_path}")
    if "--serve" in sys.argv:
        if app is None: print("FastAPI not installed"); sys.exit(1)
        uvicorn.run(app, host="0.0.0.0", port=8103)

if __name__ == "__main__":
    main()

"""
model_quality_gate.py — Automated quality gate for GR00T model promotions.
FastAPI port 8105.

Oracle Confidential
"""

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

QUALITY_GATES: List[Dict] = [
    {"id":"min_success_rate",       "name":"Min Success Rate",         "category":"accuracy",    "threshold":0.60, "operator":"ge","unit":"rate",   "weight":3},
    {"id":"max_mae",                "name":"Max MAE",                  "category":"accuracy",    "threshold":0.020,"operator":"le","unit":"float",  "weight":3},
    {"id":"p50_latency",            "name":"P50 Latency",              "category":"latency",     "threshold":250,  "operator":"le","unit":"ms",     "weight":2},
    {"id":"p99_latency",            "name":"P99 Latency",              "category":"latency",     "threshold":350,  "operator":"le","unit":"ms",     "weight":2},
    {"id":"max_error_rate",         "name":"Max Error Rate",           "category":"reliability", "threshold":0.02, "operator":"le","unit":"rate",   "weight":2},
    {"id":"min_uptime",             "name":"Min Uptime",               "category":"reliability", "threshold":99.0, "operator":"ge","unit":"percent","weight":2},
    {"id":"joint_violations_per_ep","name":"Joint Violations / Episode","category":"safety",     "threshold":0.5,  "operator":"le","unit":"count",  "weight":3},
    {"id":"workspace_violations",   "name":"Workspace Violations",     "category":"safety",      "threshold":0.1,  "operator":"le","unit":"rate",   "weight":3},
    {"id":"min_regression_pass_rate","name":"Min Regression Pass Rate","category":"regression",  "threshold":0.85, "operator":"ge","unit":"rate",   "weight":2},
    {"id":"max_vram_gb",            "name":"Max VRAM",                 "category":"resources",   "threshold":40.0, "operator":"le","unit":"gb",     "weight":1},
    {"id":"min_throughput_rps",     "name":"Min Throughput",           "category":"resources",   "threshold":3.0,  "operator":"ge","unit":"rps",    "weight":1},
    {"id":"model_size_gb",          "name":"Model Size",               "category":"packaging",   "threshold":15.0, "operator":"le","unit":"gb",     "weight":1},
]

_GATE_MAP: Dict[str, Dict] = {g["id"]: g for g in QUALITY_GATES}

CANDIDATE_MODELS: Dict[str, Dict] = {
    "bc_baseline": {
        "label":"BC Baseline","tag":"bc_baseline",
        "min_success_rate":0.05,"max_mae":0.103,"p50_latency":226,"p99_latency":267,
        "max_error_rate":0.001,"min_uptime":99.9,"joint_violations_per_ep":0.3,"workspace_violations":0.02,
        "min_regression_pass_rate":0.70,"max_vram_gb":6.7,"min_throughput_rps":4.4,"model_size_gb":6.7,
    },
    "dagger_run9_v2.2": {
        "label":"DAgger Run9 v2.2","tag":"CURRENT PROD",
        "min_success_rate":0.71,"max_mae":0.013,"p50_latency":226,"p99_latency":267,
        "max_error_rate":0.003,"min_uptime":99.94,"joint_violations_per_ep":0.4,"workspace_violations":0.05,
        "min_regression_pass_rate":0.91,"max_vram_gb":6.7,"min_throughput_rps":4.4,"model_size_gb":6.7,
    },
    "groot_finetune_v2": {
        "label":"GR00T Finetune v2","tag":"CANDIDATE",
        "min_success_rate":0.74,"max_mae":0.011,"p50_latency":231,"p99_latency":285,
        "max_error_rate":0.002,"min_uptime":99.91,"joint_violations_per_ep":0.2,"workspace_violations":0.03,
        "min_regression_pass_rate":0.94,"max_vram_gb":7.1,"min_throughput_rps":4.2,"model_size_gb":7.1,
    },
}

PROMOTION_HISTORY: List[Dict] = [
    {"model_id":"bc_baseline","verdict":"BLOCKED","weighted_score":0.26,"evaluated_at":"2026-01-15T09:00:00+00:00","promoted_by":"ci/quality-gate"},
    {"model_id":"dagger_run9_v2.2","verdict":"CERTIFIED","weighted_score":0.96,"evaluated_at":"2026-02-20T14:30:00+00:00","promoted_by":"junqian"},
    {"model_id":"groot_finetune_v2","verdict":"CERTIFIED","weighted_score":1.00,"evaluated_at":"2026-03-28T11:00:00+00:00","promoted_by":"ci/quality-gate"},
]

_OPS = {"ge": lambda v,t: v>=t, "le": lambda v,t: v<=t, "gt": lambda v,t: v>t, "lt": lambda v,t: v<t}

def _verdict(weighted_score: float) -> str:
    if weighted_score >= 0.85: return "CERTIFIED"
    if weighted_score >= 0.70: return "CONDITIONAL"
    return "BLOCKED"

def evaluate_model(model_id: str) -> Dict:
    model = CANDIDATE_MODELS.get(model_id)
    if model is None: return {"error": f"Unknown model_id: {model_id}"}
    checks = []; total_weight = 0; passed_weight = 0
    for gate in QUALITY_GATES:
        gid = gate["id"]; value = model.get(gid); threshold = gate["threshold"]
        passed = _OPS[gate["operator"]](value, threshold) if value is not None else False
        w = gate["weight"]; total_weight += w
        if passed: passed_weight += w
        checks.append({"gate":gid,"name":gate["name"],"category":gate["category"],"value":value,
                       "threshold":threshold,"operator":gate["operator"],"unit":gate["unit"],
                       "pass":passed,"weight":w})
    weighted_score = round(passed_weight/total_weight, 4) if total_weight else 0.0
    return {"model_id":model_id,"label":model["label"],"tag":model.get("tag",""),"verdict":_verdict(weighted_score),
            "weighted_score":weighted_score,"passed_weight":passed_weight,"total_weight":total_weight,
            "checks":checks,"evaluated_at":datetime.now(timezone.utc).isoformat()}

def _all_results() -> Dict[str, Dict]:
    return {mid: evaluate_model(mid) for mid in CANDIDATE_MODELS}

def _category_pass_rates(result: Dict) -> Dict[str, str]:
    cats: Dict[str, List[bool]] = {}
    for c in result.get("checks", []): cats.setdefault(c["category"], []).append(c["pass"])
    return {cat: f"{round(100*sum(passes)/len(passes))}%" for cat, passes in cats.items()}

def gate_matrix_html(results: Dict[str, Dict]) -> str:
    model_ids = list(results.keys())
    headers = "".join(
        f'<th style="padding:8px 14px;color:#38bdf8;text-align:center;font-weight:600">{results[mid]["label"]}<br>'
        f'<span style="font-size:10px;color:#94a3b8">{results[mid].get("tag","")}</span></th>'
        for mid in model_ids
    )
    categories: Dict[str, List[Dict]] = {}
    for gate in QUALITY_GATES: categories.setdefault(gate["category"], []).append(gate)
    cat_colors = {"accuracy":"#818cf8","latency":"#38bdf8","reliability":"#a78bfa",
                  "safety":"#f87171","regression":"#fb923c","resources":"#4ade80","packaging":"#94a3b8"}
    rows_html = ""
    for cat, gates in categories.items():
        cat_color = cat_colors.get(cat, "#94a3b8")
        rows_html += (f'<tr><td colspan="{len(model_ids)+1}" style="background:#0f172a;color:{cat_color};font-size:11px;'
                      f'font-weight:700;padding:6px 10px;text-transform:uppercase;letter-spacing:1px">{cat}</td></tr>\n')
        for gate in gates:
            row = f'<td style="padding:6px 10px;color:#cbd5e1;font-size:12px">{gate["name"]}</td>'
            for mid in model_ids:
                checks = {c["gate"]: c for c in results[mid].get("checks", [])}
                c = checks.get(gate["id"])
                if c is None:
                    cell = '<td style="text-align:center">—</td>'
                else:
                    icon = "✔" if c["pass"] else "✘"
                    color = "#22c55e" if c["pass"] else "#ef4444"
                    cell = (f'<td style="text-align:center;color:{color};font-size:14px">{icon}<br>'
                            f'<span style="font-size:10px;color:#94a3b8">{c["value"]}</span></td>')
                row += cell
            rows_html += f"<tr>{row}</tr>\n"
    return (f'<table style="width:100%;border-collapse:collapse;font-size:13px;background:#1e293b;border-radius:10px;overflow:hidden">'
            f'<thead><tr style="background:#0f172a"><th style="padding:8px 14px;color:#94a3b8;text-align:left;font-weight:600">Gate</th>{headers}</tr></thead>'
            f'<tbody>{rows_html}</tbody></table>')

def build_dashboard() -> str:
    all_results = _all_results()
    verdict_cards = ""
    for mid, res in all_results.items():
        v = res["verdict"]
        v_color = "#22c55e" if v=="CERTIFIED" else ("#f59e0b" if v=="CONDITIONAL" else "#ef4444")
        v_bg    = "#14532d33" if v=="CERTIFIED" else ("#78350f33" if v=="CONDITIONAL" else "#7f1d1d33")
        score_pct = round(res["weighted_score"]*100)
        tag_span = (f'<span style="background:#38bdf833;color:#38bdf8;padding:2px 8px;border-radius:8px;font-size:11px;margin-left:8px">{res["tag"]}</span>'
                    if res.get("tag") else "")
        cpr = _category_pass_rates(res)
        cat_chips = "".join(f'<span style="background:#1e293b;color:#94a3b8;padding:2px 7px;border-radius:6px;font-size:10px;margin:2px">{c}: {r}</span>' for c,r in cpr.items())
        verdict_cards += (f'<div style="background:{v_bg};border:1px solid {v_color}44;border-radius:12px;padding:18px 22px;flex:1;min-width:220px">'
                          f'<div style="font-size:13px;color:#94a3b8;margin-bottom:4px">{res["label"]} {tag_span}</div>'
                          f'<div style="font-size:28px;font-weight:700;color:{v_color}">{v}</div>'
                          f'<div style="font-size:14px;color:#cbd5e1;margin:6px 0">Score: {score_pct}%</div>'
                          f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:8px">{cat_chips}</div></div>')
    matrix = gate_matrix_html(all_results)
    hist_rows = ""
    for h in PROMOTION_HISTORY:
        v = h["verdict"]
        v_color = "#22c55e" if v=="CERTIFIED" else ("#f59e0b" if v=="CONDITIONAL" else "#ef4444")
        hist_rows += (f"<tr><td style='padding:6px 10px;color:#cbd5e1'>{h['model_id']}</td>"
                      f"<td style='padding:6px 10px;text-align:center'><span style='background:{v_color}33;color:{v_color};padding:2px 10px;border-radius:9px;font-size:11px'>{v}</span></td>"
                      f"<td style='padding:6px 10px;text-align:center;color:#94a3b8'>{round(h['weighted_score']*100)}%</td>"
                      f"<td style='padding:6px 10px;text-align:center;color:#64748b;font-size:11px'>{h['evaluated_at'][:10]}</td>"
                      f"<td style='padding:6px 10px;text-align:center;color:#64748b;font-size:11px'>{h['promoted_by']}</td></tr>")
    total_gates = len(QUALITY_GATES); categories_count = len({g["category"] for g in QUALITY_GATES})
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>Model Quality Gate — Port 8105</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
h1{{color:#C74634;font-size:22px}}h2{{color:#38bdf8;font-size:15px;margin:20px 0 10px}}
.card{{background:#1e293b;border-radius:12px;padding:18px;margin-bottom:20px}}
.verdict-row{{display:flex;gap:16px;flex-wrap:wrap;margin:16px 0}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#0f172a;color:#94a3b8;text-align:left;padding:8px 10px;border-bottom:1px solid #334155}}
td{{border-bottom:1px solid #1e293b}}tr:nth-child(even){{background:rgba(15,23,42,0.3)}}
.footer{{color:#475569;font-size:10px;text-align:center;margin-top:32px}}</style></head><body>
<h1>OCI Robot Cloud — Model Quality Gate</h1>
<div style="color:#94a3b8;font-size:12px;margin:4px 0 16px">FastAPI · Port 8105 · Automated GR00T Model Promotion Gate</div>
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px">
<div style="background:#1e293b;border-radius:10px;padding:14px 22px"><div style="color:#94a3b8;font-size:11px">TOTAL GATES</div><div style="color:#f8fafc;font-size:26px;font-weight:700">{total_gates}</div></div>
<div style="background:#1e293b;border-radius:10px;padding:14px 22px"><div style="color:#94a3b8;font-size:11px">CATEGORIES</div><div style="color:#38bdf8;font-size:26px;font-weight:700">{categories_count}</div></div>
<div style="background:#1e293b;border-radius:10px;padding:14px 22px"><div style="color:#94a3b8;font-size:11px">CANDIDATES</div><div style="color:#f8fafc;font-size:26px;font-weight:700">{len(CANDIDATE_MODELS)}</div></div>
<div style="background:#1e293b;border-radius:10px;padding:14px 22px"><div style="color:#94a3b8;font-size:11px">CERTIFY THRESHOLD</div><div style="color:#22c55e;font-size:26px;font-weight:700">85%</div></div>
</div>
<h2>Model Verdicts</h2><div class="verdict-row">{verdict_cards}</div>
<div class="card"><h2>Gate Matrix</h2>{matrix}</div>
<div class="card"><h2>Promotion History</h2><table>
<thead><tr><th>Model</th><th>Verdict</th><th>Score</th><th>Date</th><th>Promoted By</th></tr></thead>
<tbody>{hist_rows}</tbody></table></div>
<div class="footer">Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; model_quality_gate.py &nbsp;|&nbsp; Port 8105</div>
</body></html>"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    app = FastAPI(title="Model Quality Gate", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(): return build_dashboard()

    @app.get("/evaluate/{model_id}")
    async def evaluate_endpoint(model_id: str): return JSONResponse(evaluate_model(model_id))

    @app.get("/gates")
    async def gates_endpoint(): return JSONResponse(QUALITY_GATES)

    @app.get("/compare")
    async def compare_endpoint():
        results = _all_results()
        return JSONResponse({mid: {"verdict":r["verdict"],"weighted_score":r["weighted_score"],"tag":r.get("tag","")} for mid,r in results.items()})

except ImportError:
    app = None  # type: ignore

def main():
    print("="*60); print("OCI Robot Cloud — Model Quality Gate (Port 8105)"); print("Oracle Confidential"); print("="*60)
    for mid in CANDIDATE_MODELS:
        res = evaluate_model(mid)
        score_pct = round(res["weighted_score"]*100)
        tag = f" [{res['tag']}]" if res.get("tag") else ""
        print(f"\n{─*50}")
        print(f"Model: {res['label']}{tag}")
        print(f"Verdict: {res['verdict']}  |  Score: {score_pct}%  ({res['passed_weight']}/{res['total_weight']} weight)")
        for c in res["checks"]:
            tick = "PASS" if c["pass"] else "FAIL"
            print(f"{c['name']:<30} {tick:<6} {str(c['value']):<10} {c['operator']} {c['threshold']}")
    html_path = "/tmp/model_quality_gate.html"
    with open(html_path, "w", encoding="utf-8") as fh: fh.write(build_dashboard())
    print(f"\nDashboard saved to {html_path}")
    if app is not None: uvicorn.run(app, host="0.0.0.0", port=8105)

if __name__ == "__main__":
    main()

"""
A/B Testing Framework for GR00T N1.6 Policy Variants.
Oracle Confidential — OCI Robot Cloud, Eval Team.

FastAPI service on port 8098. Provides deterministic request routing across
policy variants, statistical significance testing, and an HTML dashboard.
"""

import math
import random
import hashlib
import datetime
import json
from typing import Dict, Any

VARIANTS: Dict[str, Dict[str, Any]] = {
    "bc_baseline": {"success_rate": 0.05, "mae": 0.103, "latency_ms": 226, "cost_per_1k": 0.43, "description": "Behavioral cloning baseline (1000 demos)"},
    "dagger_run5": {"success_rate": 0.05, "mae": 0.089, "latency_ms": 229, "cost_per_1k": 0.61, "description": "DAgger run-5 (5000 fine-tune steps)"},
    "dagger_run9": {"success_rate": 0.71, "mae": 0.013, "latency_ms": 226, "cost_per_1k": 0.43, "description": "DAgger run-9 IK-planned SDG (production)"},
    "groot_finetune_v2": {"success_rate": 0.74, "mae": 0.011, "latency_ms": 231, "cost_per_1k": 0.47, "description": "GR00T N1.6 fine-tune v2 (latest challenger)"},
}

TRAFFIC_SPLITS: Dict[str, float] = {"bc_baseline": 0.10, "dagger_run5": 0.10, "dagger_run9": 0.60, "groot_finetune_v2": 0.20}


def route_request(request_id: int) -> str:
    bucket = int(hashlib.md5(str(request_id).encode()).hexdigest(), 16) % 100
    cumulative = 0.0
    for variant, split in TRAFFIC_SPLITS.items():
        cumulative += split * 100
        if bucket < cumulative:
            return variant
    return list(TRAFFIC_SPLITS.keys())[-1]


def simulate_experiment(n_requests: int = 1000) -> Dict[str, Any]:
    counts: Dict[str, int] = {v: 0 for v in VARIANTS}
    successes: Dict[str, int] = {v: 0 for v in VARIANTS}
    rng = random.Random(42)
    for i in range(n_requests):
        variant = route_request(i)
        counts[variant] += 1
        if rng.random() < VARIANTS[variant]["success_rate"]:
            successes[variant] += 1
    results: Dict[str, Any] = {}
    for variant in VARIANTS:
        n = counts[variant]
        s = successes[variant]
        sr = s / n if n > 0 else 0.0
        results[variant] = {"requests": n, "successes": s, "observed_sr": round(sr, 4),
                             "mae": VARIANTS[variant]["mae"], "latency_ms": VARIANTS[variant]["latency_ms"],
                             "cost_per_1k": VARIANTS[variant]["cost_per_1k"]}
    results["_meta"] = {"n_requests": n_requests, "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}
    return results


def _normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def statistical_significance(variant_a: str, variant_b: str, results: Dict[str, Any]) -> Dict[str, Any]:
    a = results[variant_a]; b = results[variant_b]
    p1, n1 = a["observed_sr"], a["requests"]
    p2, n2 = b["observed_sr"], b["requests"]
    if n1 == 0 or n2 == 0:
        return {"z_score": None, "significant": False, "error": "insufficient data"}
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    if se == 0:
        return {"z_score": 0.0, "significant": False}
    z = (p1 - p2) / se
    p_approx = 2 * (1 - _normal_cdf(abs(z)))
    return {"variant_a": variant_a, "variant_b": variant_b, "z_score": round(z, 4),
            "p_value_approx": round(p_approx, 5), "significant": abs(z) > 1.96,
            "direction": "a_better" if z > 0 else "b_better"}


def winner_analysis(results: Dict[str, Any]) -> Dict[str, Any]:
    baseline = "bc_baseline"
    variants = [v for v in VARIANTS]
    ranked = sorted(variants, key=lambda v: results[v]["observed_sr"], reverse=True)
    winner = ranked[0]
    sig = statistical_significance(winner, baseline, results)
    return {"ranking": ranked, "winner": winner if sig["significant"] else None,
            "winner_sr": results[winner]["observed_sr"], "significance_vs_baseline": sig,
            "note": "Statistically significant improvement over baseline" if sig["significant"] else "No statistically significant winner yet"}


def bar_chart_svg(results: Dict[str, Any]) -> str:
    variants = list(VARIANTS.keys())
    max_mae = max(VARIANTS[v]["mae"] for v in variants)
    max_cost = max(VARIANTS[v]["cost_per_1k"] for v in variants)
    metrics = {"SR": lambda v: results[v]["observed_sr"],
               "MAE score": lambda v: 1 - VARIANTS[v]["mae"] / max_mae,
               "Cost score": lambda v: 1 - VARIANTS[v]["cost_per_1k"] / max_cost}
    metric_colors = ["#38bdf8", "#818cf8", "#34d399"]
    W, H = 700, 340; pad_l, pad_b, pad_t, pad_r = 50, 60, 30, 20
    chart_w = W - pad_l - pad_r; chart_h = H - pad_b - pad_t
    group_w = chart_w / len(variants)
    bar_w = group_w / (len(metrics) + 1)
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;font-family:monospace">']
    for yi in range(5):
        y_val = yi / 4; y_px = pad_t + chart_h * (1 - y_val)
        lines.append(f'<line x1="{pad_l}" y1="{y_px:.1f}" x2="{W-pad_r}" y2="{y_px:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{y_px+4:.1f}" text-anchor="end" font-size="10" fill="#94a3b8">{y_val:.2f}</text>')
    for vi, variant in enumerate(variants):
        is_prod = variant == "dagger_run9"; gx = pad_l + vi * group_w
        for mi, (mname, mfn) in enumerate(metrics.items()):
            val = mfn(variant); bar_h = chart_h * val
            bx = gx + (mi + 0.5) * bar_w; by = pad_t + chart_h - bar_h
            color = "#C74634" if is_prod else metric_colors[mi]
            lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w*0.85:.1f}" height="{bar_h:.1f}" fill="{color}" rx="2"/>')
        lx = gx + group_w / 2
        lines.append(f'<text x="{lx:.1f}" y="{H-pad_b+14}" text-anchor="middle" font-size="9" fill="#94a3b8">{variant.replace("_"," ")}</text>')
    for mi, (mname, _) in enumerate(metrics.items()):
        lx = pad_l + mi * 130
        lines.append(f'<rect x="{lx}" y="{H-18}" width="10" height="10" fill="{metric_colors[mi]}" rx="1"/>')
        lines.append(f'<text x="{lx+14}" y="{H-8}" font-size="10" fill="#94a3b8">{mname}</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def build_report() -> str:
    results = simulate_experiment(1000)
    winner_info = winner_analysis(results)
    svg = bar_chart_svg(results)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    total_reqs = results["_meta"]["n_requests"]
    winner_label = winner_info["winner"] or "TBD"
    sig_rows = []
    for v in VARIANTS:
        if v == "bc_baseline": continue
        sig = statistical_significance(v, "bc_baseline", results)
        sig_badge = '<span style="color:#4ade80">\u2713 Significant</span>' if sig["significant"] else '<span style="color:#f87171">\u2717 Not significant</span>'
        sig_rows.append(f'<tr><td style="padding:8px 12px;color:#e2e8f0">{v}</td><td style="padding:8px 12px;color:#94a3b8">bc_baseline</td><td style="padding:8px 12px;color:#e2e8f0">{sig["z_score"]}</td><td style="padding:8px 12px;color:#e2e8f0">{sig.get("p_value_approx","\u2014")}</td><td style="padding:8px 12px">{sig_badge}</td></tr>')
    variant_cards = []
    for v, info in results.items():
        if v == "_meta": continue
        meta = VARIANTS[v]; border = "#C74634" if v == "dagger_run9" else "#334155"
        variant_cards.append(f'<div style="background:#1e293b;border:1px solid {border};border-radius:8px;padding:16px;min-width:160px"><div style="color:#38bdf8;font-size:11px;font-weight:700;margin-bottom:6px">{v.replace("_"," ").upper()}</div><div style="color:#e2e8f0;font-size:22px;font-weight:700">{info["observed_sr"]*100:.1f}%</div><div style="color:#94a3b8;font-size:11px">Success Rate</div><div style="margin-top:8px;color:#94a3b8;font-size:11px">MAE: <span style="color:#e2e8f0">{meta["mae"]}</span> | Lat: <span style="color:#e2e8f0">{meta["latency_ms"]}ms</span> | Cost: <span style="color:#e2e8f0">${meta["cost_per_1k"]}/1k</span></div><div style="margin-top:4px;color:#94a3b8;font-size:10px">{info["requests"]} reqs</div></div>')
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>A/B Testing Framework \u2014 OCI Robot Cloud</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:24px}}
h1{{font-size:22px;font-weight:700;color:#f1f5f9}}h2{{font-size:14px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px}}
.chip{{display:inline-block;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:10px 18px;margin:4px}}
.chip-label{{font-size:11px;color:#94a3b8}}.chip-value{{font-size:20px;font-weight:700;color:#38bdf8}}
table{{width:100%;border-collapse:collapse}}th{{background:#0f172a;color:#94a3b8;font-size:11px;text-transform:uppercase;padding:8px 12px;text-align:left;border-bottom:1px solid #334155}}
tr:hover td{{background:#1e293b}}.section{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:20px;margin-bottom:20px}}
.footer{{color:#475569;font-size:11px;text-align:center;margin-top:24px}}</style></head><body>
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
<div><h1>A/B Testing Framework</h1><div style="color:#64748b;font-size:12px;margin-top:4px">GR00T N1.6 Policy Variants \u00b7 {now}</div></div>
<div style="background:#C74634;color:#fff;font-size:11px;font-weight:700;padding:6px 14px;border-radius:20px">LIVE</div></div>
<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px">
<div class="chip"><div class="chip-label">Total Requests</div><div class="chip-value">{total_reqs:,}</div></div>
<div class="chip"><div class="chip-label">Active Variants</div><div class="chip-value">{len(VARIANTS)}</div></div>
<div class="chip"><div class="chip-label">Current Winner</div><div class="chip-value" style="font-size:14px">{winner_label}</div></div>
<div class="chip"><div class="chip-label">Winner SR</div><div class="chip-value">{winner_info["winner_sr"]*100:.1f}%</div></div></div>
<div class="section"><h2>Variant Performance</h2><div style="display:flex;flex-wrap:wrap;gap:12px">{" ".join(variant_cards)}</div></div>
<div class="section"><h2>Metric Comparison (SR / MAE Score / Cost Score)</h2>{svg}</div>
<div class="section"><h2>Statistical Significance vs Baseline (bc_baseline)</h2>
<table><thead><tr><th>Variant</th><th>Baseline</th><th>Z-Score</th><th>p-value</th><th>Result</th></tr></thead>
<tbody>{" ".join(sig_rows)}</tbody></table></div>
<div class="section" style="font-size:12px;color:#94a3b8"><strong style="color:#e2e8f0">Winner Analysis:</strong> {winner_info["note"]}</div>
<div class="footer">Oracle Confidential \u00b7 OCI Robot Cloud \u00b7 A/B Testing Framework \u00b7 Port 8098</div>
</body></html>"""


try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    app = FastAPI(title="OCI Robot Cloud \u2014 A/B Testing Framework", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(): return build_report()

    @app.get("/experiment")
    async def experiment(n_requests: int = 1000):
        results = simulate_experiment(n_requests)
        return JSONResponse({"results": results, "winner_analysis": winner_analysis(results)})

    @app.get("/variants/{variant_id}")
    async def get_variant(variant_id: str):
        if variant_id not in VARIANTS: return JSONResponse({"error": f"Unknown variant: {variant_id}"}, status_code=404)
        return JSONResponse({"variant": variant_id, "config": VARIANTS[variant_id], "traffic_split": TRAFFIC_SPLITS.get(variant_id, 0)})

    @app.get("/route/{request_id}")
    async def route(request_id: int):
        variant = route_request(request_id)
        return JSONResponse({"request_id": request_id, "routed_to": variant, "variant_config": VARIANTS[variant]})

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False; app = None


if __name__ == "__main__":
    if FASTAPI_AVAILABLE:
        import uvicorn; uvicorn.run(app, host="0.0.0.0", port=8098)
    else:
        results = simulate_experiment(1000); winner = winner_analysis(results)
        print(f"Simulated {results['_meta']['n_requests']} requests")
        for v in VARIANTS:
            r = results[v]
            print(f"  {v:<22} SR={r['observed_sr']*100:.1f}% reqs={r['requests']}")
        print(f"Winner: {winner['winner']}  Note: {winner['note']}")
        with open("/tmp/ab_testing_report.html", "w") as f: f.write(build_report())
        print("Dashboard saved to /tmp/ab_testing_report.html")

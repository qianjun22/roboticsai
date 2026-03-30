"""
OCI Robot Cloud — Reward Shaping Analysis
Port 8113 | DAgger online learning reward analysis for GR00T
"""

import math, hashlib, random, datetime, json, collections

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

REWARD_COMPONENTS = [
    {"name": "task_success",          "weight": 0.40, "current": 0.71, "baseline": 0.05},
    {"name": "cube_lift_height",      "weight": 0.20, "current": 0.84, "baseline": 0.12},
    {"name": "grasp_stability",       "weight": 0.15, "current": 0.79, "baseline": 0.31},
    {"name": "approach_smoothness",   "weight": 0.10, "current": 0.88, "baseline": 0.62},
    {"name": "trajectory_efficiency", "weight": 0.08, "current": 0.76, "baseline": 0.48},
    {"name": "collision_avoidance",   "weight": 0.05, "current": 0.97, "baseline": 0.91},
    {"name": "time_penalty",          "weight": 0.02, "current": 0.63, "baseline": 0.71},
]

SHAPING_RUNS = [("v1.0",0.38,0.05),("v1.5",0.52,0.15),("v2.0",0.77,0.55),("v2.2",0.81,0.71),("v3.0_proposed",0.84,0.78)]


def compute_composite(components):
    return round(sum(c["weight"] * c["current"] for c in components), 4)


def compute_baseline_composite(components):
    return round(sum(c["weight"] * c["baseline"] for c in components), 4)


def propose_v3_weights(components):
    gap = [max(0.0, c["baseline"] + 0.3 - c["current"]) for c in components]
    total_gap = sum(gap)
    proposed = []
    for i, c in enumerate(components):
        delta = round((gap[i] / total_gap) * 0.05, 4) if total_gap > 0 else 0.0
        proposed.append({"name": c["name"], "current_weight": c["weight"], "proposed_weight": round(c["weight"] + delta, 4), "delta": round(delta, 4)})
    total = sum(p["proposed_weight"] for p in proposed)
    for p in proposed: p["proposed_weight"] = round(p["proposed_weight"] / total, 4)
    return proposed


def build_svg_contribution():
    w, h = 700, 220
    pad_l, pad_r, pad_t = 170, 20, 20
    chart_w, chart_h = w - pad_l - pad_r, h - pad_t - 30
    max_c = max(c["weight"] * c["current"] for c in REWARD_COMPONENTS)
    bar_h = chart_h // len(REWARD_COMPONENTS) - 4
    parts = [f'<text x="{w//2}" y="14" text-anchor="middle" font-size="12" fill="#C74634" font-weight="bold">Weighted Contribution per Component</text>']
    for idx, c in enumerate(REWARD_COMPONENTS):
        contrib = c["weight"] * c["current"]
        bw = int(chart_w * contrib / max_c)
        y = pad_t + idx * (chart_h // len(REWARD_COMPONENTS))
        parts.append(f'<text x="{pad_l-8}" y="{y+bar_h//2+4}" text-anchor="end" font-size="11" fill="#94a3b8" font-family="monospace">{c["name"].replace("_"," ")}</text>')
        parts.append(f'<rect x="{pad_l}" y="{y}" width="{chart_w}" height="{bar_h}" rx="3" fill="#0f172a"/>')
        parts.append(f'<rect x="{pad_l}" y="{y}" width="{bw}" height="{bar_h}" rx="3" fill="#C74634" opacity="0.85"/>')
        parts.append(f'<text x="{pad_l+bw+5}" y="{y+bar_h//2+4}" font-size="10" fill="#f59e0b" font-family="monospace">{contrib:.4f}</text>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#1e293b;border-radius:8px;">\n{chr(10).join(parts)}\n</svg>'


def build_svg_history():
    w, h = 700, 160
    pl, pr, pt, pb = 40, 20, 20, 36
    chart_w, chart_h = w - pl - pr, h - pt - pb
    n = len(SHAPING_RUNS)

    def tx(i): return pl + int(i * chart_w / (n - 1))
    def ty(v): return pt + chart_h - int((v - 0) / 1.0 * chart_h)

    comp_pts = " ".join(f"{tx(i)},{ty(r[1])}" for i, r in enumerate(SHAPING_RUNS))
    sr_pts = " ".join(f"{tx(i)},{ty(r[2])}" for i, r in enumerate(SHAPING_RUNS))
    grid = "".join(f'<line x1="{pl}" y1="{ty(v)}" x2="{w-pr}" y2="{ty(v)}" stroke="#0f172a" stroke-width="1"/><text x="{pl-4}" y="{ty(v)+4}" text-anchor="end" font-size="8" fill="#475569" font-family="monospace">{v:.1f}</text>' for v in [0.2, 0.4, 0.6, 0.8, 1.0])
    xlabels = "".join(f'<text x="{tx(i)}" y="{h-6}" text-anchor="middle" font-size="9" fill="#64748b" font-family="monospace">{r[0]}</text>' for i, r in enumerate(SHAPING_RUNS))
    comp_dots = "".join(f'<circle cx="{tx(i)}" cy="{ty(r[1])}" r="4" fill="#38bdf8"/>' for i, r in enumerate(SHAPING_RUNS))
    sr_dots = "".join(f'<circle cx="{tx(i)}" cy="{ty(r[2])}" r="4" fill="#C74634"/>' for i, r in enumerate(SHAPING_RUNS))
    legend = f'<rect x="{w-160}" y="4" width="10" height="10" rx="2" fill="#38bdf8"/><text x="{w-146}" y="13" font-size="10" fill="#94a3b8" font-family="monospace">Composite</text><rect x="{w-80}" y="4" width="10" height="10" rx="2" fill="#C74634"/><text x="{w-66}" y="13" font-size="10" fill="#94a3b8" font-family="monospace">SR</text>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#1e293b;border-radius:8px;">{grid}<polyline points="{comp_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/><polyline points="{sr_pts}" fill="none" stroke="#C74634" stroke-width="2.5" stroke-linejoin="round"/>{comp_dots}{sr_dots}{xlabels}{legend}</svg>'


def build_html():
    composite = compute_composite(REWARD_COMPONENTS)
    baseline = compute_baseline_composite(REWARD_COMPONENTS)
    improvement = round((composite - baseline) / max(baseline, 1e-9) * 100, 1)
    proposed = propose_v3_weights(REWARD_COMPONENTS)

    comp_rows = "".join(
        f'<tr style="border-bottom:1px solid #0f172a;"><td style="padding:10px 12px;color:#38bdf8;font-family:monospace;font-size:12px;">{c["name"].replace("_"," ")}</td>'
        f'<td style="padding:10px 12px;color:#94a3b8;font-family:monospace;text-align:center;">{c["weight"]:.2f}</td>'
        f'<td style="padding:10px 12px;color:#38bdf8;font-family:monospace;text-align:center;">{c["current"]:.2f}</td>'
        f'<td style="padding:10px 12px;color:#64748b;font-family:monospace;text-align:center;">{c["baseline"]:.2f}</td>'
        f'<td style="padding:10px 12px;color:{"#22c55e" if c["current"]>c["baseline"] else "#ef4444"};font-family:monospace;text-align:center;">{c["current"]-c["baseline"]:+.3f}</td>'
        f'<td style="padding:10px 12px;color:#f59e0b;font-family:monospace;text-align:center;">{c["weight"]*c["current"]:.4f}</td></tr>'
        for c in REWARD_COMPONENTS
    )
    prop_rows = "".join(
        f'<tr style="border-bottom:1px solid #0f172a;"><td style="padding:10px 12px;color:#38bdf8;font-family:monospace;font-size:12px;">{p["name"].replace("_"," ")}</td>'
        f'<td style="padding:10px 12px;color:#94a3b8;font-family:monospace;text-align:center;">{p["current_weight"]:.4f}</td>'
        f'<td style="padding:10px 12px;color:#f59e0b;font-family:monospace;text-align:center;">{p["proposed_weight"]:.4f}</td>'
        f'<td style="padding:10px 12px;color:{"#22c55e" if p["delta"]>0 else ("#ef4444" if p["delta"]<0 else "#64748b")};font-family:monospace;text-align:center;">{p["delta"]:+.4f}</td></tr>'
        for p in proposed
    )
    th = 'style="padding:10px 12px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;"'
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>OCI Robot Cloud — Reward Shaper</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#f1f5f9;font-family:system-ui,sans-serif;}}h1{{color:#C74634;font-size:22px;font-weight:800;}}</style></head><body>
<div style="max-width:900px;margin:0 auto;padding:28px 20px;">
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;"><div><h1>OCI Robot Cloud</h1><div style="color:#94a3b8;font-size:13px;margin-top:4px;">Reward Shaping Analysis &mdash; DAgger Online Learning for GR00T</div></div><div style="background:#1e293b;border-radius:8px;padding:8px 16px;color:#38bdf8;font-size:12px;font-family:monospace;">PORT 8113</div></div>
<div style="background:#1e293b;border-radius:10px;padding:20px 28px;margin-bottom:22px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;"><div><div style="color:#C74634;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;">Composite Reward Score</div><div style="color:#38bdf8;font-size:52px;font-weight:800;line-height:1;">{composite}</div><div style="color:#94a3b8;font-size:12px;margin-top:6px;">Baseline: <span style="color:#f59e0b;">{baseline}</span> &nbsp;|&nbsp; Improvement: <span style="color:#22c55e;">+{improvement}%</span></div></div><div style="display:flex;flex-direction:column;gap:10px;"><div><div style="color:#64748b;font-size:11px;text-transform:uppercase;">Version</div><div style="color:#38bdf8;font-size:20px;font-weight:700;">v2.2 (active)</div></div><div><div style="color:#64748b;font-size:11px;text-transform:uppercase;">Success Rate</div><div style="color:#22c55e;font-size:20px;font-weight:700;">71.0%</div></div></div></div>
<div style="background:#1e293b;border-radius:10px;padding:18px 20px;margin-bottom:22px;"><div style="color:#C74634;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px;">Weighted Contribution Breakdown</div>{build_svg_contribution()}</div>
<div style="background:#1e293b;border-radius:10px;padding:18px 20px;margin-bottom:22px;"><div style="color:#C74634;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px;">Shaping History</div>{build_svg_history()}</div>
<div style="background:#1e293b;border-radius:10px;overflow:hidden;margin-bottom:22px;"><div style="color:#C74634;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;padding:16px 20px;border-bottom:1px solid #0f172a;">Component Details</div><table style="width:100%;border-collapse:collapse;"><thead><tr style="background:#0f172a;"><th {th}>Component</th><th {th}>Weight</th><th {th}>Current</th><th {th}>Baseline</th><th {th}>Delta</th><th {th}>Contribution</th></tr></thead><tbody>{comp_rows}</tbody></table></div>
<div style="background:#1e293b;border-radius:10px;overflow:hidden;"><div style="color:#C74634;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;padding:16px 20px;border-bottom:1px solid #0f172a;">Proposed v3.0 Weight Adjustments</div><table style="width:100%;border-collapse:collapse;"><thead><tr style="background:#0f172a;"><th {th}>Component</th><th {th}>Current W</th><th {th}>Proposed W</th><th {th}>Delta</th></tr></thead><tbody>{prop_rows}</tbody></table></div>
<div style="text-align:center;color:#334155;font-size:11px;margin-top:28px;padding-top:16px;border-top:1px solid #1e293b;">Oracle Confidential | OCI Robot Cloud Reward Shaper | Port 8113</div></div></body></html>"""


if HAS_FASTAPI:
    app = FastAPI(title="OCI Robot Cloud — Reward Shaper", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def root(): return HTMLResponse(content=build_html())

    @app.get("/health")
    def health(): return JSONResponse({"status": "ok", "service": "reward_shaper", "port": 8113})

    @app.get("/components")
    def components():
        return JSONResponse({"components": [{**c, "contribution": round(c["weight"]*c["current"],4)} for c in REWARD_COMPONENTS], "composite": compute_composite(REWARD_COMPONENTS)})

    @app.get("/history")
    def history(): return JSONResponse([{"version": r[0], "composite": r[1], "success_rate": r[2]} for r in SHAPING_RUNS])

    @app.get("/propose")
    def propose(): return JSONResponse({"proposed_weights": propose_v3_weights(REWARD_COMPONENTS), "current_composite": compute_composite(REWARD_COMPONENTS)})


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run("reward_shaper:app", host="0.0.0.0", port=8113, reload=False)
    else:
        out = "/tmp/reward_shaper.html"
        with open(out, "w") as f: f.write(build_html())
        print(f"Saved to {out}")
        print(f"Composite: {compute_composite(REWARD_COMPONENTS)}")

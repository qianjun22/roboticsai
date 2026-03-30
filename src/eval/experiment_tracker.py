"""
Experiment Tracker — OCI Robot Cloud
Port: 8111
Tracks ML experiments for GR00T fine-tuning and DAgger runs.
"""

import math, hashlib, random, datetime, json, collections

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

EXPERIMENTS = [
    {"id": "exp_bc_500", "name": "BC Baseline 500 demos", "type": "BC", "demos": 500, "steps": 5000, "lr": 1e-4, "chunk": None, "sr": 0.05, "mae": 0.103, "cost_usd": 2.15, "status": "COMPLETED", "tags": ["baseline"], "notes": ""},
    {"id": "exp_bc_1000", "name": "BC 1000 demos", "type": "BC", "demos": 1000, "steps": 10000, "lr": 1e-4, "chunk": None, "sr": 0.05, "mae": 0.099, "cost_usd": 4.30, "status": "COMPLETED", "tags": ["baseline", "production_candidate"], "notes": ""},
    {"id": "exp_dagger_run5", "name": "DAgger Run 5", "type": "DAgger", "demos": 1000, "steps": 5000, "lr": 5e-5, "chunk": None, "sr": 0.05, "mae": 0.098, "cost_usd": 3.10, "status": "COMPLETED", "tags": ["dagger", "regression"], "notes": "flagged regression"},
    {"id": "exp_dagger_run6", "name": "DAgger Run 6", "type": "DAgger", "demos": 1500, "steps": 8000, "lr": 5e-5, "chunk": None, "sr": 0.15, "mae": 0.071, "cost_usd": 4.80, "status": "COMPLETED", "tags": ["dagger"], "notes": ""},
    {"id": "exp_dagger_run9", "name": "DAgger Run 9", "type": "DAgger", "demos": 3000, "steps": 20000, "lr": 3e-5, "chunk": None, "sr": 0.55, "mae": 0.034, "cost_usd": 8.60, "status": "COMPLETED", "tags": ["dagger", "milestone"], "notes": ""},
    {"id": "exp_dagger_run9_v2", "name": "DAgger Run 9 v2.2", "type": "DAgger", "demos": 3000, "steps": 25000, "lr": 2e-5, "chunk": 16, "sr": 0.71, "mae": 0.013, "cost_usd": 10.75, "status": "PRODUCTION", "tags": ["dagger", "production", "current"], "notes": ""},
    {"id": "exp_groot_finetune_v2", "name": "GR00T Finetune v2 (full)", "type": "GR00T", "demos": 3000, "steps": 60000, "lr": 1e-5, "chunk": None, "sr": 0.78, "mae": 0.011, "cost_usd": 25.80, "status": "STAGING", "tags": ["full_finetune", "staging"], "notes": ""},
    {"id": "exp_hpo_sweep_lr", "name": "HPO Sweep (LR)", "type": "HPO", "demos": None, "steps": None, "lr": None, "chunk": None, "sr": 0.71, "mae": None, "cost_usd": None, "status": "COMPLETED", "tags": ["hpo"], "notes": "5 runs lr 1e-5..1e-4; best_lr=2e-5"},
]


def experiment_summary():
    counts = collections.Counter(e["status"] for e in EXPERIMENTS)
    srs = [e["sr"] for e in EXPERIMENTS if e["sr"] is not None]
    maes = [e["mae"] for e in EXPERIMENTS if e["mae"] is not None]
    return {"total": len(EXPERIMENTS), "counts_by_status": dict(counts),
            "best_sr": max(srs) if srs else None, "best_mae": min(maes) if maes else None,
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z"}


def _get_by_id(exp_id):
    return next((e for e in EXPERIMENTS if e["id"] == exp_id), None)


def _build_sr_svg():
    plotable = [(i, e) for i, e in enumerate(EXPERIMENTS) if e["sr"] is not None]
    W, H = 700, 180
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 20, 25, 40
    chart_w, chart_h = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    n = len(plotable)

    def px(idx, sr):
        x = PAD_L + (idx / max(n - 1, 1)) * chart_w
        y = PAD_T + chart_h - sr * chart_h
        return round(x, 1), round(y, 1)

    line_pts = " ".join(f"{px(idx, e['sr'])[0]},{px(idx, e['sr'])[1]}" for idx, (_, e) in enumerate(plotable))

    markers = []
    for idx, (_, e) in enumerate(plotable):
        x, y = px(idx, e["sr"])
        if "regression" in e.get("tags", []):
            s = 8
            markers.append(f'<polygon points="{x},{y+s} {x-s},{y-s//2} {x+s},{y-s//2}" fill="#ef4444" opacity="0.9"/>')
        elif e["status"] == "PRODUCTION":
            markers.append(f'<text x="{x}" y="{y+5}" font-size="16" fill="#fbbf24" text-anchor="middle">★</text>')
        else:
            markers.append(f'<circle cx="{x}" cy="{y}" r="4" fill="#38bdf8" stroke="#0f172a" stroke-width="1.5"/>')

    y_grid = "".join(f'<line x1="{PAD_L}" y1="{PAD_T+chart_h-v*chart_h:.1f}" x2="{W-PAD_R}" y2="{PAD_T+chart_h-v*chart_h:.1f}" stroke="#334155" stroke-width="1"/><text x="{PAD_L-6}" y="{PAD_T+chart_h-v*chart_h+4:.1f}" font-size="10" fill="#94a3b8" text-anchor="end">{int(v*100)}%</text>' for v in [0, 0.25, 0.5, 0.75, 1.0])
    x_axis = "".join(f'<text x="{px(idx,0)[0]}" y="{PAD_T+chart_h+14}" font-size="8" fill="#64748b" text-anchor="end" transform="rotate(-35,{px(idx,0)[0]},{PAD_T+chart_h+14})">{e["id"].replace("exp_","").replace("_"," ")}</text>' for idx, (_, e) in enumerate(plotable))

    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px;">{y_grid}<polyline points="{line_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>{"".join(markers)}{x_axis}<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+chart_h}" stroke="#475569" stroke-width="1"/><line x1="{PAD_L}" y1="{PAD_T+chart_h}" x2="{W-PAD_R}" y2="{PAD_T+chart_h}" stroke="#475569" stroke-width="1"/><text x="{W//2}" y="13" font-size="11" fill="#cbd5e1" text-anchor="middle">Success Rate Progression across Experiments</text></svg>'


_SC = {"COMPLETED": ("#1e3a5f", "#38bdf8"), "PRODUCTION": ("#14532d", "#4ade80"), "STAGING": ("#3b2f14", "#fbbf24"), "FAILED": ("#7f1d1d", "#ef4444")}


def build_html():
    summary = experiment_summary()
    chart_svg = _build_sr_svg()
    counts = summary["counts_by_status"]
    sorted_exps = sorted(EXPERIMENTS, key=lambda e: (e["sr"] or -1), reverse=True)

    def card(l, v, c="#38bdf8"):
        return f'<div style="background:#1e293b;border-radius:10px;padding:20px 24px;min-width:130px;flex:1;"><div style="font-size:12px;color:#64748b;margin-bottom:6px;">{l}</div><div style="font-size:26px;font-weight:700;color:{c};">{v}</div></div>'

    cards = (card("Total", summary["total"]) + card("COMPLETED", counts.get("COMPLETED", 0)) +
             card("PRODUCTION", counts.get("PRODUCTION", 0), "#4ade80") + card("STAGING", counts.get("STAGING", 0), "#fbbf24") +
             card("Best SR", f'{summary["best_sr"]*100:.0f}%' if summary["best_sr"] else "N/A", "#4ade80") +
             card("Best MAE", f'{summary["best_mae"]:.3f}' if summary["best_mae"] else "N/A", "#a78bfa"))

    rows = "".join(
        f'<tr style="border-bottom:1px solid #334155;">'
        f'<td style="padding:11px 12px;color:#e2e8f0;font-family:monospace;font-size:12px;">{e["id"]}</td>'
        f'<td style="padding:11px 12px;color:#94a3b8;font-size:12px;">{e["name"]}</td>'
        f'<td style="padding:11px 12px;color:#38bdf8;">{e["type"]}</td>'
        f'<td style="padding:11px 12px;color:#e2e8f0;">{e["demos"] or "—"}</td>'
        f'<td style="padding:11px 12px;color:#e2e8f0;">{f"{e[\"steps\"]:,}" if e["steps"] else "—"}</td>'
        f'<td style="padding:11px 12px;color:#94a3b8;">{f"{e[\"lr\"]:.0e}" if e["lr"] else "—"}</td>'
        f'<td style="padding:11px 12px;color:{"#4ade80" if (e["sr"] or 0)>=0.7 else ("#fbbf24" if (e["sr"] or 0)>=0.3 else "#94a3b8")};font-size:13px;font-weight:600;">{f"{e[\"sr\"]*100:.0f}%" if e["sr"] is not None else "—"}</td>'
        f'<td style="padding:11px 12px;color:#a78bfa;">{f"{e[\"mae\"]:.3f}" if e["mae"] else "—"}</td>'
        f'<td style="padding:11px 12px;color:#64748b;">{f"${e[\"cost_usd\"]:.2f}" if e["cost_usd"] else "—"}</td>'
        f'<td style="padding:11px 12px;"><span style="background:{_SC.get(e["status"],("#1e293b","#e2e8f0"))[0]};color:{_SC.get(e["status"],("#1e293b","#e2e8f0"))[1]};padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600;">{e["status"]}</span></td>'
        f'<td style="padding:11px 12px;font-size:10px;color:#64748b;">{" ".join(e.get("tags", []))}</td>'
        f'<td style="padding:11px 12px;color:#64748b;font-size:11px;">{e["notes"]}</td></tr>'
        for e in sorted_exps
    )
    th = 'style="padding:11px 12px;color:#C74634;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;"'
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>Experiment Tracker — OCI Robot Cloud</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:32px}}
h1{{color:#C74634;font-size:24px;margin-bottom:4px}}h2{{color:#C74634;font-size:16px;margin-bottom:14px;margin-top:28px}}
.subtitle{{color:#64748b;font-size:13px;margin-bottom:28px}}.cards{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}}
footer{{margin-top:40px;color:#475569;font-size:11px;text-align:center;border-top:1px solid #1e293b;padding-top:16px}}</style></head><body>
<h1>Experiment Tracker</h1><div class="subtitle">OCI Robot Cloud — GR00T Fine-tuning &amp; DAgger Experiments &nbsp;|&nbsp; {now}</div>
<div class="cards">{cards}</div>
<h2>SR Progression</h2><div style="margin-bottom:28px;">{chart_svg}</div>
<h2>All Experiments (sorted by SR desc)</h2><div style="overflow-x:auto;margin-bottom:28px;">
<table style="width:100%;border-collapse:collapse;background:#1e293b;border-radius:10px;overflow:hidden;">
<thead><tr style="background:#0f172a;"><th {th}>ID</th><th {th}>Name</th><th {th}>Type</th><th {th}>Demos</th><th {th}>Steps</th><th {th}>LR</th><th {th}>SR ▼</th><th {th}>MAE</th><th {th}>Cost</th><th {th}>Status</th><th {th}>Tags</th><th {th}>Notes</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<footer>Oracle Confidential | OCI Robot Cloud Experiment Tracker | Port 8111</footer></body></html>"""


if HAS_FASTAPI:
    app = FastAPI(title="Experiment Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()

    @app.get("/experiments")
    def list_experiments(): return JSONResponse({"experiments": EXPERIMENTS})

    @app.get("/experiments/{exp_id}")
    def get_experiment(exp_id: str):
        exp = _get_by_id(exp_id)
        if exp is None: raise HTTPException(status_code=404, detail=f"Experiment '{exp_id}' not found")
        return JSONResponse(exp)

    @app.get("/summary")
    def get_summary(): return JSONResponse(experiment_summary())

    @app.get("/compare")
    def compare(ids: str = ""):
        if not ids: raise HTTPException(status_code=400, detail="Provide ?ids=exp1,exp2")
        results = [_get_by_id(i.strip()) for i in ids.split(",") if i.strip()]
        results = [r for r in results if r]
        delta = round(results[1]["sr"] - results[0]["sr"], 4) if len(results) == 2 and all(r["sr"] for r in results) else None
        return JSONResponse({"experiments": results, "sr_delta": delta})

    @app.get("/health")
    def health():
        prod = [e["id"] for e in EXPERIMENTS if e["status"] == "PRODUCTION"]
        return JSONResponse({"status": "ok", "production_experiments": prod, "total": len(EXPERIMENTS)})


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run("experiment_tracker:app", host="0.0.0.0", port=8111, reload=False)
    else:
        out = "/tmp/experiment_tracker.html"
        with open(out, "w") as f: f.write(build_html())
        print(f"Saved to {out}")
        print(json.dumps(experiment_summary(), indent=2))

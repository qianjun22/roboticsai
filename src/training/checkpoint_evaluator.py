"""
checkpoint_evaluator.py — OCI Robot Cloud
FastAPI port 8095: Automated checkpoint evaluation service.
Evaluates GR00T N1.6 checkpoints against benchmark tasks and recommends
best checkpoint for production deployment.
Oracle Confidential
"""

import json
import math
from datetime import date
from typing import Dict, List, Tuple

CHECKPOINTS: Dict[str, dict] = {
    "bc_500_ckpt5k":           {"label": "BC 500-demo ckpt5k",             "sr_pick_place":0.35,"sr_stack":0.28,"sr_pour":0.22,"sr_wipe":0.18,"sr_handover":0.15, "mae":0.187,"latency_ms":221,"vram_gb":6.2,"cost_per_run":0.39,"is_production":False},
    "bc_1000_ckpt5k":          {"label": "BC 1000-demo ckpt5k",            "sr_pick_place":0.45,"sr_stack":0.38,"sr_pour":0.31,"sr_wipe":0.27,"sr_handover":0.22, "mae":0.099,"latency_ms":224,"vram_gb":6.4,"cost_per_run":0.41,"is_production":False},
    "dagger_run5_ckpt5k":      {"label": "DAgger Run5 ckpt5k",             "sr_pick_place":0.50,"sr_stack":0.43,"sr_pour":0.36,"sr_wipe":0.30,"sr_handover":0.27, "mae":0.083,"latency_ms":226,"vram_gb":6.5,"cost_per_run":0.43,"is_production":False},
    "dagger_run9_v2.2_ckpt5k": {"label": "DAgger Run9 v2.2 ckpt5k (PROD)", "sr_pick_place":0.71,"sr_stack":0.64,"sr_pour":0.58,"sr_wipe":0.52,"sr_handover":0.49, "mae":0.013,"latency_ms":226,"vram_gb":6.7,"cost_per_run":0.43,"is_production":True},
    "curriculum_ckpt8k":       {"label": "Curriculum ckpt8k",              "sr_pick_place":0.66,"sr_stack":0.59,"sr_pour":0.53,"sr_wipe":0.47,"sr_handover":0.43, "mae":0.021,"latency_ms":231,"vram_gb":6.9,"cost_per_run":0.44,"is_production":False},
    "lora_r16_ckpt5k":         {"label": "LoRA r=16 ckpt5k",               "sr_pick_place":0.60,"sr_stack":0.54,"sr_pour":0.47,"sr_wipe":0.41,"sr_handover":0.37, "mae":0.031,"latency_ms":198,"vram_gb":4.8,"cost_per_run":0.37,"is_production":False},
    "multi_task_ckpt6k":       {"label": "Multi-task ckpt6k",              "sr_pick_place":0.68,"sr_stack":0.61,"sr_pour":0.55,"sr_wipe":0.49,"sr_handover":0.45, "mae":0.018,"latency_ms":238,"vram_gb":7.1,"cost_per_run":0.46,"is_production":False},
    "ensemble_4ckpt":          {"label": "Ensemble (4 checkpoints)",        "sr_pick_place":0.74,"sr_stack":0.67,"sr_pour":0.61,"sr_wipe":0.55,"sr_handover":0.51, "mae":0.009,"latency_ms":412,"vram_gb":14.2,"cost_per_run":0.89,"is_production":False},
}
PRODUCTION_BASELINE_ID = "dagger_run9_v2.2_ckpt5k"
SCORE_WEIGHTS = {"sr": 0.40, "mae": 0.20, "latency": 0.20, "cost": 0.20}
MAE_WORST=0.20; MAE_BEST=0.005; LATENCY_WORST=450.0; LATENCY_BEST=180.0; COST_WORST=0.90; COST_BEST=0.35

def mean_sr(c: dict) -> float:
    return sum(c[t] for t in ["sr_pick_place","sr_stack","sr_pour","sr_wipe","sr_handover"]) / 5

def score_comp(v: float, best: float, worst: float) -> float:
    if abs(worst-best) < 1e-9: return 1.0
    return max(0.0, min(1.0, (v-worst)/(best-worst)))

def composite_score(c: dict) -> float:
    return round(0.40*score_comp(mean_sr(c),1.0,0.0) + 0.20*score_comp(c["mae"],MAE_BEST,MAE_WORST)
                 + 0.20*score_comp(c["latency_ms"],LATENCY_BEST,LATENCY_WORST)
                 + 0.20*score_comp(c["cost_per_run"],COST_BEST,COST_WORST), 4)

def ranked_leaderboard() -> List[dict]:
    rows = [{"id":cid,"label":c["label"],"composite_score":composite_score(c),"mean_sr":round(mean_sr(c),4),
             "mae":c["mae"],"latency_ms":c["latency_ms"],"vram_gb":c["vram_gb"],
             "cost_per_run":c["cost_per_run"],"is_production":c["is_production"]} for cid,c in CHECKPOINTS.items()]
    rows.sort(key=lambda r: r["composite_score"], reverse=True)
    for rank,row in enumerate(rows, 1): row["rank"] = rank
    return rows

def delta_vs_production(cid: str) -> dict:
    prod = CHECKPOINTS[PRODUCTION_BASELINE_ID]; c = CHECKPOINTS[cid]
    return {"delta_mean_sr": round(mean_sr(c)-mean_sr(prod),4), "delta_mae": round(c["mae"]-prod["mae"],4),
            "delta_latency_ms": round(c["latency_ms"]-prod["latency_ms"],1),
            "delta_cost": round(c["cost_per_run"]-prod["cost_per_run"],3),
            "delta_composite": round(composite_score(c)-composite_score(prod),4)}

def _polar(cx,cy,r,angle_deg):
    a = math.radians(angle_deg-90)
    return round(cx+r*math.cos(a),2), round(cy+r*math.sin(a),2)

def radar_svg(top3_ids: List[str]) -> str:
    cx,cy,r = 180,160,110; axes=["SR","MAE inv","Lat inv","Cost inv","VRAM inv"]
    angles = [i*72 for i in range(5)]; colors=["#C74634","#38bdf8","#a78bfa"]
    lines = []
    for lvl in [0.25,0.5,0.75,1.0]:
        pts = " ".join(f"{_polar(cx,cy,r*lvl,a)[0]},{_polar(cx,cy,r*lvl,a)[1]}" for a in angles)
        lines.append(f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="0.8"/>')
    for i,(ax,ang) in enumerate(zip(axes,angles)):
        x2,y2=_polar(cx,cy,r,ang); lx,ly=_polar(cx,cy,r+18,ang)
        lines.append(f'<line x1="{cx}" y1="{cy}" x2="{x2}" y2="{y2}" stroke="#475569" stroke-width="0.8"/>'
                     f'<text x="{lx}" y="{ly}" text-anchor="middle" dominant-baseline="middle" fill="#94a3b8" font-size="10" font-family="monospace">{ax}</text>')
    for idx,cid in enumerate(top3_ids):
        c = CHECKPOINTS[cid]
        scores = [score_comp(mean_sr(c),1.0,0.0), score_comp(c["mae"],MAE_BEST,MAE_WORST),
                  score_comp(c["latency_ms"],LATENCY_BEST,LATENCY_WORST), score_comp(c["cost_per_run"],COST_BEST,COST_WORST),
                  score_comp(c["vram_gb"],4.0,16.0)]
        pts = " ".join(f"{_polar(cx,cy,r*s,angles[i])[0]},{_polar(cx,cy,r*s,angles[i])[1]}" for i,s in enumerate(scores))
        color = colors[idx%len(colors)]
        lines.append(f'<polygon points="{pts}" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="1.5"/>'
                     f'<rect x="300" y="{10+idx*18}" width="12" height="12" fill="{color}" rx="2"/>'
                     f'<text x="318" y="{20+idx*18}" fill="#94a3b8" font-size="10" font-family="monospace">{CHECKPOINTS[cid]["label"][:30]}</text>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="520" height="330" style="background:#0f172a;border-radius:8px">{chr(10).join(lines)}</svg>'

def build_html_report() -> str:
    lb = ranked_leaderboard(); top3_ids = [r["id"] for r in lb[:3]]
    prod_score = composite_score(CHECKPOINTS[PRODUCTION_BASELINE_ID])
    table_rows = []
    for row in lb:
        is_prod = row["is_production"]
        prod_marker = ' <span style="background:#C74634;color:#fff;font-size:9px;padding:1px 5px;border-radius:3px">PROD</span>' if is_prod else ""
        d = delta_vs_production(row["id"])
        ds_c = "#22c55e" if d["delta_composite"]>0 else "#ef4444" if d["delta_composite"]<0 else "#94a3b8"
        dc_c = "#22c55e" if d["delta_mean_sr"]>0 else "#ef4444" if d["delta_mean_sr"]<0 else "#94a3b8"
        row_style = "background:#1e3a2f" if is_prod else ""
        table_rows.append(f'<tr style="{row_style}"><td style="padding:8px 12px"><span style="color:#f59e0b;font-weight:700">#{row["rank"]}</span></td>'
            f'<td style="padding:8px 12px;color:#e2e8f0">{row["label"]}{prod_marker}</td>'
            f'<td style="padding:8px 12px;color:#f1f5f9;font-weight:700">{row["composite_score"]:.4f}</td>'
            f'<td style="padding:8px 12px">{row["mean_sr"]:.3f}</td><td style="padding:8px 12px">{row["mae"]}</td>'
            f'<td style="padding:8px 12px">{row["latency_ms"]}</td><td style="padding:8px 12px">{row["cost_per_run"]:.2f}</td>'
            f'<td style="padding:8px 12px">{row["vram_gb"]}</td>'
            f'<td style="padding:8px 12px"><span style="color:{ds_c}">{d["delta_composite"]:+.4f}</span></td>'
            f'<td style="padding:8px 12px"><span style="color:{dc_c}">{d["delta_mean_sr"]:+.4f}</span></td></tr>')
    radar = radar_svg(top3_ids)
    prod_c = CHECKPOINTS[PRODUCTION_BASELINE_ID]
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>OCI Robot Cloud — Checkpoint Evaluator</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
h1{{color:#C74634;font-size:22px;font-weight:700;margin-bottom:4px}}h2{{color:#C74634;font-size:14px;text-transform:uppercase;letter-spacing:1px;margin-bottom:16px}}
.subtitle{{color:#64748b;font-size:13px;margin-bottom:24px}}
.banner{{background:linear-gradient(135deg,#1e3a2f,#0f2e1f);border:1px solid #22c55e;border-radius:10px;padding:20px;margin-bottom:24px}}
.section{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px;margin-bottom:24px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{color:#64748b;text-align:left;padding:8px 12px;border-bottom:1px solid #334155;font-size:11px;text-transform:uppercase}}
td{{color:#94a3b8;border-bottom:1px solid #1e293b}}tr:hover td{{background:#253347}}
.footer{{color:#475569;font-size:11px;text-align:center;margin-top:32px;padding-top:16px;border-top:1px solid #1e293b}}</style></head>
<body><h1>OCI Robot Cloud — Checkpoint Evaluator</h1>
<div class="subtitle">GR00T N1.6 &nbsp;|&nbsp; OCI A100 GPU4 &nbsp;|&nbsp; Scoring: SR×40%+MAE×20%+Latency×20%+Cost×20% &nbsp;|&nbsp; {date.today().isoformat()}</div>
<div class="banner">
  <div style="color:#22c55e;font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;font-weight:700">Recommended for Production</div>
  <div style="color:#f1f5f9;font-size:20px;font-weight:700;margin-bottom:6px">{CHECKPOINTS[PRODUCTION_BASELINE_ID]['label']}</div>
  <div style="color:#22c55e;font-size:32px;font-weight:800">{prod_score:.2f} <span style="font-size:16px;color:#64748b">composite score</span></div>
  <div style="color:#64748b;font-size:12px;margin-top:4px">Mean SR: {mean_sr(prod_c):.1%} | MAE: {prod_c['mae']} | Latency: {prod_c['latency_ms']}ms | Cost: ${prod_c['cost_per_run']}/run | VRAM: {prod_c['vram_gb']}GB</div>
</div>
<div class="section"><h2>Checkpoint Leaderboard</h2><div style="overflow-x:auto">
<table><thead><tr><th>Rank</th><th>Checkpoint</th><th>Composite</th><th>Mean SR</th><th>MAE</th><th>Latency (ms)</th><th>Cost ($)</th><th>VRAM (GB)</th><th>&Delta; Score</th><th>&Delta; SR</th></tr></thead>
<tbody>{''.join(table_rows)}</tbody></table></div></div>
<div class="section"><h2>Radar Chart — Top 3 Checkpoints</h2>{radar}
<div style="color:#475569;font-size:11px;margin-top:8px">Axes normalised to [0,1] where 1 = best. MAE/Latency/Cost/VRAM axes are inverted.</div></div>
<div class="footer">Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; GR00T N1.6 &nbsp;|&nbsp; Generated {date.today().isoformat()}</div>
</body></html>"""

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    app = FastAPI(title="OCI Robot Cloud — Checkpoint Evaluator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard(): return HTMLResponse(content=build_html_report())

    @app.get("/checkpoints")
    def list_checkpoints(): return ranked_leaderboard()

    @app.get("/checkpoints/{checkpoint_id}")
    def get_checkpoint(checkpoint_id: str):
        if checkpoint_id not in CHECKPOINTS: raise HTTPException(status_code=404, detail=f"Not found: {checkpoint_id}")
        c = CHECKPOINTS[checkpoint_id]
        return {"id": checkpoint_id, "label": c["label"], "is_production": c["is_production"],
                "composite_score": composite_score(c), "mean_sr": round(mean_sr(c),4),
                "metrics": {k: c[k] for k in ["sr_pick_place","sr_stack","sr_pour","sr_wipe","sr_handover","mae","latency_ms","vram_gb","cost_per_run"]},
                "delta_vs_production": delta_vs_production(checkpoint_id)}

    @app.post("/evaluate/{checkpoint_id}")
    def trigger_eval(checkpoint_id: str):
        if checkpoint_id not in CHECKPOINTS: raise HTTPException(status_code=404, detail=f"Not found")
        return {"status": "submitted", "checkpoint_id": checkpoint_id, "estimated_duration_min": 12, "compute": "OCI GPU.A100.4"}

    @app.get("/recommend")
    def recommend():
        lb = ranked_leaderboard(); best = lb[0]; prod_row = next(r for r in lb if r["is_production"])
        return {"recommended_checkpoint": best["id"], "composite_score": best["composite_score"],
                "current_production": PRODUCTION_BASELINE_ID, "production_score": prod_row["composite_score"],
                "upgrade_recommended": best["composite_score"] > prod_row["composite_score"] + 0.02,
                "leaderboard_top3": lb[:3]}
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False; app = None

if __name__ == "__main__":
    html = build_html_report()
    with open("/tmp/checkpoint_evaluator.html", "w") as f: f.write(html)
    print("[checkpoint_evaluator] HTML report saved to /tmp/checkpoint_evaluator.html")
    lb = ranked_leaderboard()
    print("\n=== Checkpoint Leaderboard ===")
    for row in lb:
        prod_tag = " *PROD*" if row["is_production"] else ""
        print(f"#{row['rank']} {row['id']:<35} score={row['composite_score']:.4f} sr={row['mean_sr']:.3f} mae={row['mae']} lat={row['latency_ms']}ms{prod_tag}")
    if FASTAPI_AVAILABLE:
        import uvicorn
        uvicorn.run("checkpoint_evaluator:app", host="0.0.0.0", port=8095, reload=False)

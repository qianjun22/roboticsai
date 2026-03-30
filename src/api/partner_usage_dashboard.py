"""
partner_usage_dashboard.py — OCI Robot Cloud
FastAPI port 8094: Unified partner usage dashboard aggregating GPU hours, API calls,
fine-tune runs, and DAgger iterations across all 5 design partners.
Oracle Confidential
"""

import json
import random
import math
from datetime import date
from typing import Dict, List

PARTNERS = {
    "covariant":             {"display_name": "Covariant",              "gpu_hours": 42,  "api_calls": 1200, "finetune_runs": 3, "dagger_iters": 2, "success_rate": 0.71},
    "apptronik":             {"display_name": "Apptronik",             "gpu_hours": 28,  "api_calls": 600,  "finetune_runs": 1, "dagger_iters": 1, "success_rate": 0.58},
    "1x_technologies":       {"display_name": "1X Technologies",       "gpu_hours": 35,  "api_calls": 500,  "finetune_runs": 2, "dagger_iters": 0, "success_rate": 0.45},
    "skild_ai":              {"display_name": "Skild AI",              "gpu_hours": 18,  "api_calls": 400,  "finetune_runs": 1, "dagger_iters": 1, "success_rate": 0.52},
    "physical_intelligence": {"display_name": "Physical Intelligence",  "gpu_hours": 61,  "api_calls": 300,  "finetune_runs": 5, "dagger_iters": 3, "success_rate": 0.74},
}
REPORT_MONTH    = "March 2026"
TOTAL_GPU_HOURS = sum(p["gpu_hours"] for p in PARTNERS.values())
TOTAL_API_CALLS = sum(p["api_calls"] for p in PARTNERS.values())

def get_tier(gpu_hours: int) -> str:
    return "enterprise" if gpu_hours > 40 else "growth" if gpu_hours >= 20 else "starter"

TIER_COLORS = {"enterprise": "#f59e0b", "growth": "#38bdf8", "starter": "#94a3b8"}

def sparkline_data(pid: str, total: int, days: int = 30) -> List[int]:
    rng = random.Random(hash(pid) & 0xFFFFFFFF)
    raw = [rng.randint(1, 100) for _ in range(days)]
    s = sum(raw)
    return [max(1, round(v * total / s)) for v in raw]

def svg_stacked_bar(partners_data: Dict) -> str:
    bar_colors = ["#C74634","#e07b6f","#f59e0b","#38bdf8","#a78bfa"]
    total = TOTAL_GPU_HOURS; width = 520; bar_h = 36
    segs = []; x = 0
    for i, (pid, p) in enumerate(partners_data.items()):
        w = round(p["gpu_hours"] / total * width, 2)
        c = bar_colors[i % len(bar_colors)]
        segs.append(f'<rect x="{x}" y="0" width="{w}" height="{bar_h}" fill="{c}" rx="2"/>'
            f'<text x="{x+w/2}" y="{bar_h+16}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">{p["display_name"].split()[0]}</text>'
            f'<text x="{x+w/2}" y="{bar_h+28}" text-anchor="middle" fill="#e2e8f0" font-size="9" font-family="monospace">{p["gpu_hours"]}h</text>')
        x += w
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{bar_h+50}" style="overflow:visible"><g>{chr(10).join(segs)}</g></svg>'

def sparkline_svg(vals: List[int]) -> str:
    w, h = 80, 24; mn, mx = min(vals), max(vals); rng = mx - mn if mx != mn else 1
    pts = [f"{round(i/(len(vals)-1)*w,1)},{round(h-(v-mn)/rng*h,1)}" for i,v in enumerate(vals)]
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="vertical-align:middle"><polyline points="{" ".join(pts)}" fill="none" stroke="#38bdf8" stroke-width="1.5"/></svg>'

def sr_bar(sr: float) -> str:
    pct = round(sr * 100); c = "#22c55e" if sr >= 0.7 else "#f59e0b" if sr >= 0.5 else "#ef4444"
    return (f'<div style="background:#1e293b;border-radius:4px;height:8px;width:100%;margin-top:4px">'
            f'<div style="background:{c};width:{pct}%;height:8px;border-radius:4px"></div></div>'
            f'<div style="color:{c};font-size:11px;margin-top:2px">{pct}% success rate</div>')

def gpu_bar(h: int) -> str:
    pct = min(round(h / 80 * 100), 100)
    return (f'<div style="background:#1e293b;border-radius:4px;height:6px;width:100%;margin-top:4px">'
            f'<div style="background:#C74634;width:{pct}%;height:6px;border-radius:4px"></div></div>'
            f'<div style="color:#94a3b8;font-size:11px;margin-top:2px">{h}h / 80h quota</div>')

def build_html_dashboard() -> str:
    cards = []
    for pid, p in PARTNERS.items():
        tier = get_tier(p["gpu_hours"]); tc = TIER_COLORS[tier]
        spark = sparkline_svg(sparkline_data(pid, p["api_calls"]))
        cards.append(f"""
        <div style="background:#1e293b;border-radius:10px;padding:20px;border:1px solid #334155">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <span style="color:#e2e8f0;font-size:15px;font-weight:600">{p['display_name']}</span>
            <span style="background:{tc};color:#0f172a;font-size:10px;font-weight:700;padding:2px 8px;border-radius:12px;text-transform:uppercase">{tier}</span>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">
            <div style="background:#0f172a;border-radius:6px;padding:8px">
              <div style="color:#64748b;font-size:10px;text-transform:uppercase;margin-bottom:2px">GPU Hours</div>
              <div style="color:#f1f5f9;font-size:18px;font-weight:700">{p['gpu_hours']}</div>{gpu_bar(p['gpu_hours'])}</div>
            <div style="background:#0f172a;border-radius:6px;padding:8px">
              <div style="color:#64748b;font-size:10px;text-transform:uppercase;margin-bottom:2px">API Calls</div>
              <div style="color:#f1f5f9;font-size:18px;font-weight:700">{p['api_calls']:,}</div>
              <div style="margin-top:4px">{spark}</div></div>
            <div style="background:#0f172a;border-radius:6px;padding:8px">
              <div style="color:#64748b;font-size:10px;text-transform:uppercase;margin-bottom:2px">Fine-tune Runs</div>
              <div style="color:#f1f5f9;font-size:18px;font-weight:700">{p['finetune_runs']}</div></div>
            <div style="background:#0f172a;border-radius:6px;padding:8px">
              <div style="color:#64748b;font-size:10px;text-transform:uppercase;margin-bottom:2px">DAgger Iters</div>
              <div style="color:#f1f5f9;font-size:18px;font-weight:700">{p['dagger_iters']}</div></div>
          </div>
          <div style="background:#0f172a;border-radius:6px;padding:8px">
            <div style="color:#64748b;font-size:10px;text-transform:uppercase;margin-bottom:2px">Task Success Rate</div>{sr_bar(p['success_rate'])}</div>
        </div>""")
    stacked = svg_stacked_bar(PARTNERS)
    avg_sr = sum(p['success_rate'] for p in PARTNERS.values()) / len(PARTNERS)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>OCI Robot Cloud — Partner Usage Dashboard</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
h1{{color:#C74634;font-size:22px;font-weight:700;margin-bottom:4px}}
.subtitle{{color:#64748b;font-size:13px;margin-bottom:24px}}
.summary-bar{{display:flex;gap:16px;margin-bottom:28px;flex-wrap:wrap}}
.stat-chip{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:12px 20px}}
.stat-chip .label{{color:#64748b;font-size:11px;text-transform:uppercase;margin-bottom:4px}}
.stat-chip .value{{color:#f1f5f9;font-size:20px;font-weight:700}}
.cards-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-bottom:32px}}
.chart-section{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px;margin-bottom:24px}}
.chart-section h2{{color:#C74634;font-size:14px;text-transform:uppercase;letter-spacing:1px;margin-bottom:16px}}
.footer{{color:#475569;font-size:11px;text-align:center;margin-top:32px;padding-top:16px;border-top:1px solid #1e293b}}</style></head>
<body><h1>OCI Robot Cloud — Partner Usage Dashboard</h1>
<div class="subtitle">Report Period: {REPORT_MONTH} &nbsp;|&nbsp; GR00T N1.6 Platform &nbsp;|&nbsp; OCI A100 GPU4</div>
<div class="summary-bar">
  <div class="stat-chip"><div class="label">Total GPU Hours</div><div class="value">{TOTAL_GPU_HOURS}</div></div>
  <div class="stat-chip"><div class="label">Total API Calls</div><div class="value">{TOTAL_API_CALLS:,}</div></div>
  <div class="stat-chip"><div class="label">Active Partners</div><div class="value">{len(PARTNERS)}</div></div>
  <div class="stat-chip"><div class="label">Avg Success Rate</div><div class="value">{avg_sr:.0%}</div></div>
</div>
<div class="chart-section"><h2>GPU Hours by Partner — {REPORT_MONTH}</h2>{stacked}</div>
<div class="cards-grid">{chr(10).join(cards)}</div>
<div class="footer">Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; GR00T N1.6 &nbsp;|&nbsp; Generated {date.today().isoformat()}</div>
</body></html>"""

def partner_summary(pid: str) -> dict:
    p = PARTNERS[pid]
    return {"id": pid, "display_name": p["display_name"], "tier": get_tier(p["gpu_hours"]),
            "gpu_hours": p["gpu_hours"], "api_calls": p["api_calls"],
            "finetune_runs": p["finetune_runs"], "dagger_iters": p["dagger_iters"],
            "success_rate": p["success_rate"], "sparkline_30d": sparkline_data(pid, p["api_calls"])}

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    app = FastAPI(title="OCI Robot Cloud — Partner Usage Dashboard", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard(): return HTMLResponse(content=build_html_dashboard())

    @app.get("/partners")
    def list_partners(): return [partner_summary(pid) for pid in PARTNERS]

    @app.get("/partners/{partner_id}")
    def get_partner(partner_id: str):
        if partner_id not in PARTNERS: raise HTTPException(status_code=404, detail=f"Partner '{partner_id}' not found")
        return partner_summary(partner_id)

    @app.get("/usage/summary")
    def get_usage_summary():
        tiers = {pid: get_tier(p["gpu_hours"]) for pid, p in PARTNERS.items()}
        return {"report_month": REPORT_MONTH, "total_gpu_hours": TOTAL_GPU_HOURS,
                "total_api_calls": TOTAL_API_CALLS,
                "avg_success_rate": round(sum(p["success_rate"] for p in PARTNERS.values())/len(PARTNERS),3),
                "partner_count": len(PARTNERS),
                "tier_breakdown": {"enterprise": [p for p,t in tiers.items() if t=="enterprise"],
                                   "growth":     [p for p,t in tiers.items() if t=="growth"],
                                   "starter":    [p for p,t in tiers.items() if t=="starter"]}}
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False; app = None

if __name__ == "__main__":
    import sys
    if FASTAPI_AVAILABLE:
        import uvicorn
        uvicorn.run("partner_usage_dashboard:app", host="0.0.0.0", port=8094, reload=False)
    else:
        out = "/tmp/partner_usage_dashboard.html"
        with open(out, "w") as f: f.write(build_html_dashboard())
        print(f"HTML saved to {out}")
        print(json.dumps({"total_gpu_hours": TOTAL_GPU_HOURS, "total_api_calls": TOTAL_API_CALLS}, indent=2))

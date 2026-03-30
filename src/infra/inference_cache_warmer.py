"""
inference_cache_warmer.py — Pre-warms GR00T inference cache for low-latency responses.
FastAPI port 8104.

Oracle Confidential
"""

import hashlib
import json
import math
import random
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

CACHE_CONFIG: Dict = {
    "max_entries": 1000, "ttl_seconds": 3600,
    "target_hit_rate_pct": 60.0, "warm_interval_min": 30,
}

WARM_SCENARIOS: List[Dict] = [
    {"id":"cube_center_grasp","name":"Cube Center Grasp","description":"Grasp cube positioned at center of workspace",
     "joint_states_example":[0.0,-0.5,0.0,-2.0,0.0,1.57,0.79],"priority":1,"last_warmed":None,"hit_rate_pct":68.2},
    {"id":"cube_left_grasp","name":"Cube Left Grasp","description":"Grasp cube positioned to the left of center",
     "joint_states_example":[0.3,-0.5,0.1,-2.0,0.0,1.57,0.79],"priority":1,"last_warmed":None,"hit_rate_pct":42.7},
    {"id":"cube_right_grasp","name":"Cube Right Grasp","description":"Grasp cube positioned to the right of center",
     "joint_states_example":[-0.3,-0.5,-0.1,-2.0,0.0,1.57,0.79],"priority":1,"last_warmed":None,"hit_rate_pct":38.1},
    {"id":"pre_grasp_approach","name":"Pre-Grasp Approach","description":"Approach phase before final grasp closure",
     "joint_states_example":[0.0,-0.3,0.0,-1.8,0.0,1.5,0.8],"priority":2,"last_warmed":None,"hit_rate_pct":54.3},
    {"id":"lift_phase","name":"Lift Phase","description":"Vertical lift after successful grasp",
     "joint_states_example":[0.0,-0.4,0.0,-1.6,0.0,1.7,0.8],"priority":2,"last_warmed":None,"hit_rate_pct":47.9},
    {"id":"home_position","name":"Home Position","description":"Standard robot home / reset position",
     "joint_states_example":[0.0,0.0,0.0,-1.57,0.0,1.57,0.785],"priority":1,"last_warmed":None,"hit_rate_pct":81.4},
    {"id":"cube_edge_left","name":"Cube Edge Left","description":"Grasp cube near left workspace boundary",
     "joint_states_example":[0.5,-0.6,0.15,-2.1,0.0,1.57,0.79],"priority":3,"last_warmed":None,"hit_rate_pct":22.6},
    {"id":"cube_edge_right","name":"Cube Edge Right","description":"Grasp cube near right workspace boundary",
     "joint_states_example":[-0.5,-0.6,-0.15,-2.1,0.0,1.57,0.79],"priority":3,"last_warmed":None,"hit_rate_pct":19.8},
    {"id":"release_position","name":"Release Position","description":"Controlled object release at drop zone",
     "joint_states_example":[0.0,-0.2,0.0,-1.4,0.0,1.8,0.1],"priority":2,"last_warmed":None,"hit_rate_pct":35.7},
    {"id":"recovery_pose","name":"Recovery Pose","description":"Safe recovery posture after fault detection",
     "joint_states_example":[0.0,-0.1,0.0,-1.2,0.0,1.2,0.5],"priority":3,"last_warmed":None,"hit_rate_pct":12.4},
]

_rng = random.Random(42)
_PRIORITY_COLOR = {1:"#ef4444",2:"#f59e0b",3:"#38bdf8"}
_PRIORITY_LABEL = {1:"P1-Critical",2:"P2-Normal",3:"P3-Low"}

def _cache_key(joint_states: List[float]) -> str:
    return hashlib.sha256(json.dumps(joint_states, separators=(",",":")).encode()).hexdigest()

def _gauss_latency() -> float:
    return max(180.0, random.gauss(226, 12))

def warm_scenario(scenario_id: str) -> Dict:
    scenario = next((s for s in WARM_SCENARIOS if s["id"] == scenario_id), None)
    if scenario is None: return {"error": f"Unknown scenario_id: {scenario_id}"}
    latency_ms = round(_gauss_latency(), 2)
    ts = datetime.now(timezone.utc).isoformat()
    scenario["last_warmed"] = ts
    return {"scenario_id":scenario_id,"latency_ms":latency_ms,"cache_key":_cache_key(scenario["joint_states_example"]),
            "status":"warmed","warmed_at":ts}

def warm_all_priority(priority: int) -> List[Dict]:
    return [warm_scenario(s["id"]) for s in WARM_SCENARIOS if s["priority"] == priority]

def cache_status() -> Dict:
    total = len(WARM_SCENARIOS)
    avg_hit_rate = sum(s["hit_rate_pct"] for s in WARM_SCENARIOS) / total
    above_target = sum(1 for s in WARM_SCENARIOS if s["hit_rate_pct"] >= CACHE_CONFIG["target_hit_rate_pct"])
    seed_rng = random.Random(2024)
    cache_utilization_pct = round(seed_rng.gauss(72.0, 3.0), 1)
    return {
        "total_scenarios":total,"warmed_this_session":sum(1 for s in WARM_SCENARIOS if s["last_warmed"]),
        "avg_hit_rate_pct":round(avg_hit_rate,2),"target_hit_rate_pct":CACHE_CONFIG["target_hit_rate_pct"],
        "scenarios_above_target":above_target,"cache_utilization_pct":cache_utilization_pct,
        "max_entries":CACHE_CONFIG["max_entries"],"ttl_seconds":CACHE_CONFIG["ttl_seconds"],
        "warm_interval_min":CACHE_CONFIG["warm_interval_min"],
    }

def warming_schedule_svg() -> str:
    W, H = 600, 220
    row_h = 18; label_w = 130; bar_area_w = W - label_w - 20
    ttl = CACHE_CONFIG["ttl_seconds"]; now_epoch = int(time.time())
    rows = [f'<text x="{label_w+2}" y="12" fill="#94a3b8" font-size="9" font-family="monospace">← {ttl//60} min TTL window →</text>']
    for i, s in enumerate(WARM_SCENARIOS):
        y = 20 + i * row_h; color = _PRIORITY_COLOR[s["priority"]]
        rows.append(f'<text x="4" y="{y+12}" fill="#cbd5e1" font-size="9" font-family="monospace" clip-path="url(#lclip)">{s["name"][:18]}</text>')
        rows.append(f'<rect x="{label_w}" y="{y+2}" width="{bar_area_w}" height="{row_h-4}" fill="#1e293b" rx="2"/>')
        if s["last_warmed"]:
            try:
                dt = datetime.fromisoformat(s["last_warmed"])
                elapsed = now_epoch - int(dt.timestamp())
                remaining = max(0, ttl - elapsed)
                bar_w = max(4, int((remaining/ttl)*bar_area_w))
                bar_x = min(label_w+int((elapsed/ttl)*bar_area_w), label_w+bar_area_w-bar_w)
                rows.append(f'<rect x="{bar_x}" y="{y+3}" width="{bar_w}" height="{row_h-6}" fill="{color}" rx="2" opacity="0.85"/>')
            except Exception: pass
        else:
            rows.append(f'<rect x="{label_w}" y="{y+3}" width="6" height="{row_h-6}" fill="#475569" rx="2" opacity="0.5"/>')
    leg_y = H - 10
    for priority, color in _PRIORITY_COLOR.items():
        lx = label_w + (priority-1)*130
        rows += [f'<rect x="{lx}" y="{leg_y-8}" width="10" height="8" fill="{color}" rx="1"/>',
                 f'<text x="{lx+13}" y="{leg_y}" fill="#94a3b8" font-size="8" font-family="monospace">{_PRIORITY_LABEL[priority]}</text>']
    inner = "\n  ".join(rows)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px;">\n'
            f'  <defs><clipPath id="lclip"><rect width="{label_w-4}" height="{H}"/></clipPath></defs>\n'
            f'  <text x="4" y="12" fill="#38bdf8" font-size="10" font-weight="bold" font-family="monospace">Warming Schedule (TTL Gantt)</text>\n'
            f'  {inner}\n</svg>')

def hit_rate_bar_svg() -> str:
    W, H = 500, 260; label_w = 140; bar_area_w = W - label_w - 50; row_h = 22
    target = CACHE_CONFIG["target_hit_rate_pct"]
    target_x = label_w + int((target/100.0)*bar_area_w)
    rows = [f'<text x="4" y="14" fill="#38bdf8" font-size="10" font-weight="bold" font-family="monospace">Cache Hit Rate (%)</text>',
            f'<line x1="{target_x}" y1="18" x2="{target_x}" y2="{H-18}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3" opacity="0.7"/>',
            f'<text x="{target_x+3}" y="26" fill="#f59e0b" font-size="8" font-family="monospace">target</text>']
    for i, s in enumerate(WARM_SCENARIOS):
        y = 22 + i * row_h; rate = s["hit_rate_pct"]
        bar_w = max(2, int((rate/100.0)*bar_area_w))
        color = "#22c55e" if rate >= target else "#ef4444"
        rows += [f'<text x="4" y="{y+13}" fill="#cbd5e1" font-size="9" font-family="monospace">{s["name"][:19]}</text>',
                 f'<rect x="{label_w}" y="{y+2}" width="{bar_area_w}" height="{row_h-6}" fill="#1e293b" rx="2"/>',
                 f'<rect x="{label_w}" y="{y+2}" width="{bar_w}" height="{row_h-6}" fill="{color}" rx="2" opacity="0.85"/>',
                 f'<text x="{label_w+bar_w+4}" y="{y+13}" fill="#e2e8f0" font-size="9" font-family="monospace">{rate}%</text>']
    inner = "\n  ".join(rows)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px;">\n'
            f'  {inner}\n</svg>')

def build_dashboard() -> str:
    status = cache_status()
    warm_svg = warming_schedule_svg()
    hit_svg = hit_rate_bar_svg()
    table_rows = []
    for s in WARM_SCENARIOS:
        badge_color = _PRIORITY_COLOR[s["priority"]]
        last_w = s["last_warmed"] or "—"
        if last_w != "—":
            try: last_w = datetime.fromisoformat(last_w).strftime("%H:%M:%S UTC")
            except Exception: pass
        warmed_badge = ('<span style="background:#22c55e;color:#0f172a;padding:1px 7px;border-radius:9px;font-size:11px">WARM</span>'
                       if s["last_warmed"] else '<span style="background:#475569;color:#e2e8f0;padding:1px 7px;border-radius:9px;font-size:11px">COLD</span>')
        hr_color = "#22c55e" if s["hit_rate_pct"] >= CACHE_CONFIG["target_hit_rate_pct"] else "#ef4444"
        table_rows.append(
            f'<tr><td style="padding:6px 10px">{s["name"]}</td>'
            f'<td style="padding:6px 10px;text-align:center"><span style="background:{badge_color};color:#0f172a;padding:1px 8px;border-radius:9px;font-size:11px">P{s["priority"]}</span></td>'
            f'<td style="padding:6px 10px;text-align:center;color:{hr_color}">{s["hit_rate_pct"]}%</td>'
            f'<td style="padding:6px 10px;text-align:center;color:#94a3b8;font-size:11px">{last_w}</td>'
            f'<td style="padding:6px 10px;text-align:center">{warmed_badge}</td></tr>'
        )
    util_color = "#22c55e" if status["cache_utilization_pct"] < 85 else "#f59e0b"
    avg_color = "#22c55e" if status["avg_hit_rate_pct"] >= status["target_hit_rate_pct"] else "#ef4444"
    chips = f"""<div style="display:flex;gap:16px;flex-wrap:wrap;margin:16px 0">
<div style="background:#1e293b;border-radius:10px;padding:14px 22px;min-width:130px"><div style="color:#94a3b8;font-size:11px">SCENARIOS</div><div style="color:#f8fafc;font-size:26px;font-weight:700">{status["total_scenarios"]}</div></div>
<div style="background:#1e293b;border-radius:10px;padding:14px 22px;min-width:130px"><div style="color:#94a3b8;font-size:11px">AVG HIT RATE</div><div style="color:{avg_color};font-size:26px;font-weight:700">{status["avg_hit_rate_pct"]}%</div></div>
<div style="background:#1e293b;border-radius:10px;padding:14px 22px;min-width:130px"><div style="color:#94a3b8;font-size:11px">ABOVE TARGET</div><div style="color:#38bdf8;font-size:26px;font-weight:700">{status["scenarios_above_target"]}/{status["total_scenarios"]}</div></div>
<div style="background:#1e293b;border-radius:10px;padding:14px 22px;min-width:130px"><div style="color:#94a3b8;font-size:11px">CACHE UTIL</div><div style="color:{util_color};font-size:26px;font-weight:700">{status["cache_utilization_pct"]}%</div></div>
<div style="background:#1e293b;border-radius:10px;padding:14px 22px;min-width:130px"><div style="color:#94a3b8;font-size:11px">MAX ENTRIES</div><div style="color:#f8fafc;font-size:26px;font-weight:700">{status["max_entries"]}</div></div>
<div style="background:#1e293b;border-radius:10px;padding:14px 22px;min-width:130px"><div style="color:#94a3b8;font-size:11px">TTL</div><div style="color:#f8fafc;font-size:26px;font-weight:700">{status["ttl_seconds"]//60}m</div></div>
</div>"""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>Inference Cache Warmer — Port 8104</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
h1{{color:#C74634;font-size:22px}}h2{{color:#38bdf8;font-size:15px;margin:20px 0 10px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#0f172a;color:#94a3b8;text-align:left;padding:8px 10px;border-bottom:1px solid #334155}}
tr:nth-child(even){{background:#0f172a33}}td{{border-bottom:1px solid #1e293b}}
.card{{background:#1e293b;border-radius:12px;padding:18px;margin-bottom:20px}}
.footer{{color:#475569;font-size:10px;text-align:center;margin-top:32px}}
.charts{{display:flex;gap:20px;flex-wrap:wrap}}</style></head><body>
<h1>OCI Robot Cloud — Inference Cache Warmer</h1>
<div style="color:#94a3b8;font-size:12px;margin:4px 0 16px">FastAPI · Port 8104 · GR00T Inference Cache Pre-Warming</div>
{chips}
<div class="card"><h2>Visualizations</h2><div class="charts">{hit_svg}{warm_svg}</div></div>
<div class="card"><h2>Scenario Registry</h2><table><thead><tr><th>Name</th><th>Priority</th><th>Hit Rate</th><th>Last Warmed</th><th>Status</th></tr></thead>
<tbody>{chr(10).join(table_rows)}</tbody></table></div>
<div class="footer">Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; inference_cache_warmer.py &nbsp;|&nbsp; Port 8104</div>
</body></html>"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    app = FastAPI(title="Inference Cache Warmer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(): return build_dashboard()

    @app.get("/status")
    async def status_endpoint(): return JSONResponse(cache_status())

    @app.get("/scenarios")
    async def scenarios_endpoint(): return JSONResponse(WARM_SCENARIOS)

    @app.post("/warm/{scenario_id}")
    async def warm_one(scenario_id: str): return JSONResponse(warm_scenario(scenario_id))

    @app.post("/warm-all")
    async def warm_all_endpoint(priority: Optional[int] = None):
        results = []
        for p in ([priority] if priority else [1,2,3]):
            results.extend(warm_all_priority(p))
        return JSONResponse({"warmed": len(results), "results": results})

except ImportError:
    app = None  # type: ignore

def main():
    print("="*60); print("OCI Robot Cloud — Inference Cache Warmer (Port 8104)"); print("Oracle Confidential"); print("="*60)
    print("\nPre-warming P1 scenarios...")
    for r in warm_all_priority(1):
        print(f"  [{r.get('status','error').upper()}] {r.get('scenario_id')} — {r.get('latency_ms','?')} ms")
    html_path = "/tmp/inference_cache_warmer.html"
    with open(html_path, "w", encoding="utf-8") as fh: fh.write(build_dashboard())
    print(f"\nDashboard saved to {html_path}")
    if app is not None:
        uvicorn.run(app, host="0.0.0.0", port=8104)

if __name__ == "__main__":
    main()

"""
multi_robot_coordinator.py — OCI Robot Cloud Multi-Robot Coordination Service
FastAPI port 8092 | Fleet coordination, task dispatch, per-robot stats
Oracle Confidential
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    print("[multi_robot_coordinator] FastAPI not available — running in CLI mode")

ROBOTS: Dict[str, Dict] = {
    "robot_001": {"type": "franka_panda", "capabilities": ["pick_place","stack","handover"], "region": "us-ashburn-1"},
    "robot_002": {"type": "franka_panda", "capabilities": ["pick_place","stack","pour"],     "region": "us-ashburn-1"},
    "robot_003": {"type": "franka_panda", "capabilities": ["pick_place","wipe","handover"],  "region": "us-phoenix-1"},
    "robot_004": {"type": "ur5",          "capabilities": ["pick_place","pour","wipe"],      "region": "us-phoenix-1"},
    "robot_005": {"type": "ur5",          "capabilities": ["pick_place","stack","wipe"],     "region": "eu-frankfurt-1"},
    "robot_006": {"type": "xarm6",        "capabilities": ["pick_place","handover","pour"],  "region": "eu-frankfurt-1"},
}

TASK_TYPES  = ["pick_place","stack","pour","wipe","handover"]
COORD_MODES = ["round_robin","load_balance","capability_match"]
BASE_LATENCY_MS = 226.0

def _gauss(rng: random.Random, base: float, spread: float) -> float:
    u1 = max(1e-10, rng.random()); u2 = rng.random()
    z  = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return base + z * spread

def generate_fleet_history(days: int = 30, total_tasks: int = 500) -> Dict[str, Dict]:
    rng = random.Random(42)
    robot_ids = list(ROBOTS.keys())
    weights   = [0.20, 0.19, 0.18, 0.16, 0.14, 0.13]
    task_counts = [int(total_tasks * w) for w in weights]
    task_counts[-1] += total_tasks - sum(task_counts)
    stats: Dict[str, Dict] = {}
    for i, rid in enumerate(robot_ids):
        n = task_counts[i]
        successes = min(int(n * (0.87 + rng.uniform(-0.04, 0.04))), n)
        latencies = [max(50.0, _gauss(rng, BASE_LATENCY_MS, 18.0)) for _ in range(n)]
        avg_lat   = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
        uptime    = round(min(100.0, _gauss(rng, 99.4, 0.15)), 3)
        stats[rid] = {
            "robot_id": rid, "type": ROBOTS[rid]["type"],
            "capabilities": ROBOTS[rid]["capabilities"], "region": ROBOTS[rid]["region"],
            "tasks_completed": successes, "tasks_failed": n - successes, "tasks_total": n,
            "success_rate_pct": round(100.0 * successes / n, 2) if n else 0.0,
            "avg_latency_ms": avg_lat, "uptime_pct": uptime,
            "state": "idle", "last_task_type": rng.choice(TASK_TYPES),
        }
    return stats

def generate_hourly_utilization(days: int = 7) -> Dict[str, List[float]]:
    rng = random.Random(77)
    base_hourly = [15,10,8,7,8,12,25,45,62,71,74,70,65,72,75,73,68,60,48,38,30,24,19,16]
    result: Dict[str, List[float]] = {}
    for rid in ROBOTS:
        util = [round(max(0.0, min(100.0, _gauss(rng, base_hourly[h], 6.0))), 1) for h in range(24)]
        result[rid] = util
    return result

FLEET_STATS        = generate_fleet_history(30, 500)
HOURLY_UTILIZATION = generate_hourly_utilization(7)

_task_counter = 0
def _next_task_id() -> str:
    global _task_counter; _task_counter += 1
    return f"task_{_task_counter:05d}"

TASK_QUEUE: List[Dict] = []
_seed_rng = random.Random(99)
for _i in range(8):
    TASK_QUEUE.append({"task_id": _next_task_id(), "task_type": _seed_rng.choice(TASK_TYPES),
        "priority": _seed_rng.randint(1,5), "status": "queued", "retries": 0, "max_retries": 3,
        "created_utc": (datetime.utcnow()-timedelta(minutes=_seed_rng.randint(1,30))).isoformat(),
        "assigned_to": None, "coord_mode": _seed_rng.choice(COORD_MODES)})
TASK_QUEUE.sort(key=lambda t: -t["priority"])

def _capable_robots(task_type: str) -> List[str]:
    return [rid for rid, cfg in ROBOTS.items() if task_type in cfg["capabilities"]]

def select_robot(task_type: str, coord_mode: str) -> Optional[str]:
    candidates = _capable_robots(task_type)
    if not candidates: return None
    if coord_mode == "round_robin":
        candidates.sort(key=lambda r: FLEET_STATS[r]["tasks_total"]); return candidates[0]
    elif coord_mode == "load_balance":
        return min(candidates, key=lambda r: FLEET_STATS[r]["tasks_total"] / max(1.0, FLEET_STATS[r]["uptime_pct"]))
    else:
        return min(candidates, key=lambda r: len(ROBOTS[r]["capabilities"]))

def dispatch_task(task_type: str, priority: int = 3, coord_mode: str = "load_balance") -> Dict:
    if task_type not in TASK_TYPES:  return {"error": f"Unknown task type '{task_type}'"}
    if coord_mode not in COORD_MODES: return {"error": f"Unknown coord mode '{coord_mode}'"}
    assigned = select_robot(task_type, coord_mode)
    task_id  = _next_task_id()
    rng      = random.Random(hash(task_id) % 77_777)
    lat_ms   = round(max(50.0, _gauss(rng, BASE_LATENCY_MS, 12.0)), 1)
    record   = {"task_id": task_id, "task_type": task_type, "priority": priority,
        "status": "dispatched" if assigned else "queued_no_robot",
        "assigned_to": assigned, "coord_mode": coord_mode, "dispatch_lat_ms": lat_ms,
        "retries": 0, "max_retries": 3, "created_utc": datetime.utcnow().isoformat()}
    if assigned:
        FLEET_STATS[assigned]["tasks_total"] += 1
        FLEET_STATS[assigned]["tasks_completed"] += 1
        FLEET_STATS[assigned]["last_task_type"] = task_type
    TASK_QUEUE.append(record); TASK_QUEUE.sort(key=lambda t: -t["priority"])
    return record

def build_heatmap_svg() -> str:
    robot_ids = list(ROBOTS.keys())
    cell_w, cell_h = 28, 28; pad_left, pad_top = 88, 36
    width  = pad_left + cell_w * 24 + 20
    height = pad_top  + cell_h * len(robot_ids) + 36
    def heat_color(pct: float) -> str:
        stops = [(0,(30,58,95)),(30,(14,165,233)),(65,(245,158,11)),(100,(239,68,68))]
        pct = max(0.0, min(100.0, pct))
        for j in range(len(stops)-1):
            p0,c0 = stops[j]; p1,c1 = stops[j+1]
            if p0 <= pct <= p1:
                t = (pct-p0)/(p1-p0)
                r=int(c0[0]+t*(c1[0]-c0[0])); g=int(c0[1]+t*(c1[1]-c0[1])); b=int(c0[2]+t*(c1[2]-c0[2]))
                return f"rgb({r},{g},{b})"
        return "rgb(239,68,68)"
    cells: List[str] = []
    for ri, rid in enumerate(robot_ids):
        for h in range(24):
            pct = HOURLY_UTILIZATION[rid][h]; x = pad_left + h*cell_w; y = pad_top + ri*cell_h
            cells.append(f'<rect x="{x}" y="{y}" width="{cell_w-1}" height="{cell_h-1}" fill="{heat_color(pct)}" rx="2"><title>{rid} hour={h:02d}:00 util={pct}%</title></rect>')
            if pct >= 50: cells.append(f'<text x="{x+cell_w//2}" y="{y+cell_h//2+4}" fill="#fff" font-size="8" text-anchor="middle" font-family="monospace">{int(pct)}</text>')
    row_labels = "".join(f'<text x="{pad_left-6}" y="{pad_top+ri*cell_h+cell_h//2+4}" fill="#94a3b8" font-size="10" text-anchor="end" font-family="monospace">{rid}</text>' for ri,rid in enumerate(robot_ids))
    col_labels = "".join(f'<text x="{pad_left+h*cell_w+cell_w//2}" y="{pad_top-8}" fill="#64748b" font-size="9" text-anchor="middle" font-family="monospace">{h:02d}</text>' for h in range(0,24,2))
    title = f'<text x="{width//2}" y="16" fill="#C74634" font-size="12" font-weight="bold" text-anchor="middle" font-family="sans-serif">Fleet Utilization Heatmap — 7-Day Avg (Hour of Day)</text>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#0f172a;border-radius:8px;overflow:visible">{title}{row_labels}{col_labels}{"" .join(cells)}</svg>'

_STATE_COLOR = {"idle":"#22c55e","executing":"#3b82f6","paused":"#f59e0b","error":"#ef4444","charging":"#8b5cf6"}

def _state_badge(state: str) -> str:
    c = _STATE_COLOR.get(state, "#64748b")
    return f'<span style="background:{c}22;color:{c};padding:2px 9px;border-radius:4px;font-size:0.76em;font-weight:700;">{state.upper()}</span>'

def build_dashboard() -> str:
    total_tasks   = sum(s["tasks_total"] for s in FLEET_STATS.values())
    total_success = sum(s["tasks_completed"] for s in FLEET_STATS.values())
    fleet_success = round(100.0 * total_success / max(1, total_tasks), 1)
    avg_latency   = round(sum(s["avg_latency_ms"] for s in FLEET_STATS.values()) / len(FLEET_STATS), 1)
    avg_uptime    = round(sum(s["uptime_pct"] for s in FLEET_STATS.values()) / len(FLEET_STATS), 2)
    queued_count  = sum(1 for t in TASK_QUEUE if t["status"] in ("queued","queued_no_robot"))
    cards: List[str] = []
    for rid, s in FLEET_STATS.items():
        state = s["state"]; state_col = _STATE_COLOR.get(state, "#64748b")
        cards.append(f'<div style="background:#1e293b;border:1px solid #334155;border-left:3px solid {state_col};border-radius:8px;padding:14px 18px;">'
            f'<div style="font-weight:700;color:#e2e8f0;margin-bottom:6px">{rid}</div>'
            f'<div style="font-size:0.78em;color:#64748b;margin-bottom:8px">{s["type"]} &nbsp;|&nbsp; {s["region"]}</div>'
            f'{_state_badge(state)}<div style="margin-top:10px;font-size:0.82em;color:#94a3b8">'
            f'Tasks: <b style="color:#e2e8f0">{s["tasks_completed"]}/{s["tasks_total"]}</b> &nbsp; Success: <b style="color:#22c55e">{s["success_rate_pct"]}%</b><br>'
            f'Avg latency: <b style="color:#3b82f6">{s["avg_latency_ms"]} ms</b> &nbsp; Uptime: <b style="color:#a78bfa">{s["uptime_pct"]}%</b><br>'
            f'Last task: <span style="color:#c084fc">{s["last_task_type"]}</span></div></div>')
    queue_rows: List[str] = []
    for t in TASK_QUEUE[:15]:
        pc = "#ef4444" if t["priority"]>=4 else ("#f59e0b" if t["priority"]==3 else "#64748b")
        queue_rows.append(f"<tr><td style='color:#94a3b8;font-family:monospace'>{t['task_id']}</td>"
            f"<td style='color:#c084fc'>{t['task_type']}</td><td style='color:{pc};font-weight:700'>P{t['priority']}</td>"
            f"<td>{t['status']}</td><td style='color:#e2e8f0'>{t.get('assigned_to') or '—'}</td>"
            f"<td style='color:#64748b'>{t['coord_mode']}</td><td style='color:#94a3b8'>{t['created_utc'][:19]}</td></tr>")
    heatmap_svg = build_heatmap_svg(); generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>OCI Robot Cloud — Multi-Robot Coordinator</title>
<style>body{{background:#0f172a;color:#cbd5e1;font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:0}}
.hdr{{background:#1e293b;border-bottom:2px solid #C74634;padding:18px 32px}}
h1{{color:#C74634;margin:0 0 4px;font-size:1.4em}}h2{{color:#C74634;border-bottom:1px solid #334155;padding-bottom:6px;margin:32px 0 14px;font-size:1.05em}}
.wrap{{max-width:1300px;margin:0 auto;padding:24px 32px}}.stats{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px}}
.stat{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 22px;min-width:130px}}
.sv{{font-size:1.7em;font-weight:700;color:#e2e8f0}}.sl{{font-size:0.75em;color:#64748b;margin-top:3px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}}
table{{border-collapse:collapse;width:100%;margin-top:8px}}th{{background:#1e293b;color:#94a3b8;font-size:0.76em;text-transform:uppercase;padding:9px 11px;text-align:left;border-bottom:1px solid #334155}}
td{{padding:8px 11px;border-bottom:1px solid #1e293b;font-size:0.86em}}tr:hover td{{background:#1e293b55}}
.footer{{margin-top:40px;text-align:center;color:#475569;font-size:0.74em;border-top:1px solid #1e293b;padding:12px 0 24px}}</style></head>
<body><div class="hdr"><h1>OCI Robot Cloud — Multi-Robot Coordinator</h1>
<span style="color:#64748b;font-size:0.85em">Fleet of {len(ROBOTS)} robots &nbsp;|&nbsp; 30-day simulation &nbsp;|&nbsp; Generated {generated} UTC &nbsp;|&nbsp; Port 8092</span></div>
<div class="wrap"><div class="stats">
<div class="stat"><div class="sv">{len(ROBOTS)}</div><div class="sl">Total Robots</div></div>
<div class="stat"><div class="sv" style="color:#22c55e">{total_tasks}</div><div class="sl">Tasks Dispatched</div></div>
<div class="stat"><div class="sv" style="color:#22c55e">{fleet_success}%</div><div class="sl">Fleet Success Rate</div></div>
<div class="stat"><div class="sv" style="color:#3b82f6">{avg_latency} ms</div><div class="sl">Avg Latency</div></div>
<div class="stat"><div class="sv" style="color:#a78bfa">{avg_uptime}%</div><div class="sl">Avg Uptime</div></div>
<div class="stat"><div class="sv" style="color:#f59e0b">{queued_count}</div><div class="sl">Queued Tasks</div></div></div>
<h2>Fleet Status</h2><div class="grid">{''.join(cards)}</div>
<h2>Utilization Heatmap (7-Day Avg)</h2><div style="overflow-x:auto;padding:8px 0">{heatmap_svg}</div>
<h2>Task Queue (Latest 15)</h2><table><thead><tr>
<th>Task ID</th><th>Type</th><th>Priority</th><th>Status</th><th>Assigned To</th><th>Coord Mode</th><th>Created</th>
</tr></thead><tbody>{''.join(queue_rows)}</tbody></table>
<div class="footer">Oracle Confidential &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; Multi-Robot Coordinator v1.0 &nbsp;|&nbsp; GR00T N1.6 Platform</div>
</div></body></html>"""

if _FASTAPI:
    app = FastAPI(title="OCI Robot Cloud — Multi-Robot Coordinator", version="1.0.0",
        description="Fleet coordination for GR00T N1.6 policy inference across 6 robots.")

    @app.get("/", response_class=HTMLResponse)
    def dashboard(): return HTMLResponse(content=build_dashboard())

    @app.get("/health")
    def health(): return {"status": "ok", "service": "multi_robot_coordinator", "port": 8092}

    @app.get("/fleet")
    def fleet(): return JSONResponse(content={"robots": FLEET_STATS, "coord_modes": COORD_MODES, "generated_utc": datetime.utcnow().isoformat()})

    @app.get("/fleet/{robot_id}")
    def robot_status(robot_id: str):
        if robot_id not in FLEET_STATS: raise HTTPException(status_code=404, detail=f"Robot '{robot_id}' not found")
        return JSONResponse(content={"stats": FLEET_STATS[robot_id], "config": ROBOTS[robot_id], "utilization": HOURLY_UTILIZATION[robot_id]})

    @app.get("/tasks/queue")
    def task_queue(status: Optional[str] = None, limit: int = 50):
        result = list(TASK_QUEUE)
        if status: result = [t for t in result if t["status"] == status]
        return JSONResponse(content={"count": len(result), "tasks": result[:limit]})

    @app.post("/tasks/dispatch", status_code=201)
    def dispatch(task_type: str = "pick_place", priority: int = 3, coord_mode: str = "load_balance"):
        result = dispatch_task(task_type, priority, coord_mode)
        if "error" in result: raise HTTPException(status_code=400, detail=result["error"])
        return JSONResponse(content=result, status_code=201)

def _cli_report() -> None:
    print("\n=== OCI Robot Cloud — Multi-Robot Coordinator (30-day sim) ===\n")
    for rid, s in FLEET_STATS.items():
        print(f"{rid} {s['type']} tasks={s['tasks_total']} success={s['success_rate_pct']:.1f}% lat={s['avg_latency_ms']:.1f}ms uptime={s['uptime_pct']:.3f}%")
    total_t = sum(s["tasks_total"] for s in FLEET_STATS.values())
    total_s = sum(s["tasks_completed"] for s in FLEET_STATS.values())
    print(f"\nFleet: {total_t} tasks, {round(100.0*total_s/total_t,1)}% success | Queue depth: {len(TASK_QUEUE)}")

if __name__ == "__main__":
    if _FASTAPI: uvicorn.run(app, host="0.0.0.0", port=8092, log_level="info")
    else: _cli_report()

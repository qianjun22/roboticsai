"""
feature_flag_manager.py — OCI Robot Cloud Feature Flag Manager
FastAPI service on port 8102.

Manages gradual rollout of robot policy features across the fleet,
with deterministic per-user evaluation, dashboard, and SVG timeline.

Oracle Confidential — OCI Robot Cloud Platform
"""

import hashlib
import json
import sys
from datetime import datetime
from typing import Dict, List, Any

# ── Data ────────────────────────────────────────────────────────────────────────────

FLAGS: Dict[str, Dict[str, Any]] = {
    "new_camera_pipeline": {
        "name": "new_camera_pipeline", "enabled": True, "rollout_pct": 25,
        "variant": "v2", "description": "New stereo camera preprocessing",
        "created": "2026-01-15", "owner": "covariant",
    },
    "lora_inference_path": {
        "name": "lora_inference_path", "enabled": True, "rollout_pct": 50,
        "variant": "lora_r16", "description": "LoRA rank-16 inference branch",
        "created": "2026-01-22", "owner": "platform",
    },
    "fp8_quantization": {
        "name": "fp8_quantization", "enabled": False, "rollout_pct": 0,
        "variant": "fp8", "description": "FP8 quantized inference (TensorRT-LLM)",
        "created": "2026-02-01", "owner": "platform",
    },
    "adaptive_chunk_size": {
        "name": "adaptive_chunk_size", "enabled": True, "rollout_pct": 75,
        "variant": "adaptive", "description": "Adaptive action chunk size (K=8-24)",
        "created": "2026-02-08", "owner": "platform",
    },
    "multi_camera_fusion": {
        "name": "multi_camera_fusion", "enabled": False, "rollout_pct": 10,
        "variant": "fusion_v1", "description": "Multi-view camera fusion (beta)",
        "created": "2026-02-14", "owner": "physical_intelligence",
    },
    "dagger_auto_trigger": {
        "name": "dagger_auto_trigger", "enabled": True, "rollout_pct": 100,
        "variant": "v1", "description": "Auto-trigger DAgger when SR<50%",
        "created": "2026-02-20", "owner": "platform",
    },
    "jetson_edge_inference": {
        "name": "jetson_edge_inference", "enabled": True, "rollout_pct": 30,
        "variant": "jetson_nx", "description": "Route inference to Jetson NX edge node",
        "created": "2026-03-01", "owner": "apptronik",
    },
    "curriculum_sdg": {
        "name": "curriculum_sdg", "enabled": True, "rollout_pct": 60,
        "variant": "4stage", "description": "4-stage curriculum SDG pipeline",
        "created": "2026-03-10", "owner": "platform",
    },
}

# ── Core logic ───────────────────────────────────────────────────────────────────

def is_enabled(flag_name: str, user_id: int) -> bool:
    flag = FLAGS.get(flag_name)
    if flag is None or not flag["enabled"]:
        return False
    bucket = int(hashlib.md5(f"{flag_name}{user_id}".encode()).hexdigest(), 16) % 100
    return bucket < flag["rollout_pct"]

def evaluate_all(user_id: int) -> Dict[str, bool]:
    return {name: is_enabled(name, user_id) for name in FLAGS}

def flag_stats() -> Dict[str, Any]:
    total = len(FLAGS)
    enabled_count = sum(1 for f in FLAGS.values() if f["enabled"])
    avg_rollout = sum(f["rollout_pct"] for f in FLAGS.values()) / total if total else 0
    owner_breakdown: Dict[str, int] = {}
    for f in FLAGS.values():
        owner_breakdown[f["owner"]] = owner_breakdown.get(f["owner"], 0) + 1
    return {
        "total_flags": total, "enabled_count": enabled_count,
        "disabled_count": total - enabled_count,
        "avg_rollout_pct": round(avg_rollout, 1),
        "owner_breakdown": owner_breakdown,
    }

def rollout_impact_estimate() -> Dict[str, Any]:
    return {
        name: {"fraction_affected": flag["rollout_pct"] / 100, "rollout_pct": flag["rollout_pct"],
               "description": flag["description"], "owner": flag["owner"]}
        for name, flag in FLAGS.items() if flag["enabled"]
    }

# ── SVG timeline ──────────────────────────────────────────────────────────────

def timeline_svg() -> str:
    width, height = 600, 280
    margin_left, margin_top = 190, 20
    bar_height, bar_gap = 22, 8
    chart_width = width - margin_left - 20
    rows = list(FLAGS.values())
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#0f172a;font-family:monospace;">',
        f'<text x="{width//2}" y="14" text-anchor="middle" fill="#38bdf8" font-size="11" font-weight="bold">Feature Flag Rollout (%) — Port 8102</text>',
    ]
    for pct in (25, 50, 75, 100):
        gx = margin_left + int(chart_width * pct / 100)
        lines.append(f'<line x1="{gx}" y1="{margin_top + 4}" x2="{gx}" y2="{height - 20}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>')
        lines.append(f'<text x="{gx}" y="{height - 8}" text-anchor="middle" fill="#64748b" font-size="9">{pct}%</text>')
    for i, flag in enumerate(rows):
        y = margin_top + 10 + i * (bar_height + bar_gap)
        color = "#22c55e" if flag["enabled"] else "#ef4444"
        bar_w = max(2, int(chart_width * flag["rollout_pct"] / 100))
        short_name = flag["name"].replace("_", " ")
        lines.append(f'<text x="{margin_left - 6}" y="{y + bar_height // 2 + 4}" text-anchor="end" fill="#cbd5e1" font-size="10">{short_name}</text>')
        lines.append(f'<rect x="{margin_left}" y="{y}" width="{chart_width}" height="{bar_height}" fill="#1e293b" rx="3"/>')
        lines.append(f'<rect x="{margin_left}" y="{y}" width="{bar_w}" height="{bar_height}" fill="{color}" rx="3" opacity="0.85"/>')
        if bar_w > 24:
            lines.append(f'<text x="{margin_left + bar_w - 4}" y="{y + bar_height // 2 + 4}" text-anchor="end" fill="#0f172a" font-size="9" font-weight="bold">{flag["rollout_pct"]}%</text>')
    lines.append("</svg>")
    return "\n".join(lines)

# ── HTML dashboard ─────────────────────────────────────────────────────────

def build_dashboard() -> str:
    stats = flag_stats()
    svg = timeline_svg()
    flag_rows = ""
    for f in FLAGS.values():
        enabled_badge = ('<span style="background:#166534;color:#86efac;padding:2px 8px;border-radius:9px;font-size:11px;">ON</span>'
                        if f["enabled"] else '<span style="background:#7f1d1d;color:#fca5a5;padding:2px 8px;border-radius:9px;font-size:11px;">OFF</span>')
        flag_rows += (f"<tr><td style='color:#38bdf8;font-family:monospace;font-size:12px;'>{f['name']}</td>"
                      f"<td style='color:#94a3b8;font-size:12px;'>{f['owner']}</td><td>{enabled_badge}</td>"
                      f"<td style='color:#fbbf24;text-align:center;'>{f['rollout_pct']}%</td>"
                      f"<td style='color:#a78bfa;font-size:11px;'>{f['variant']}</td>"
                      f"<td style='color:#cbd5e1;font-size:11px;'>{f['description']}</td>"
                      f"<td style='color:#64748b;font-size:11px;'>{f['created']}</td></tr>")
    owner_chips = "".join(
        f'<span style="background:#1e3a5f;color:#93c5fd;padding:4px 10px;border-radius:12px;font-size:12px;margin:2px;">{owner}: {cnt}</span>'
        for owner, cnt in stats["owner_breakdown"].items()
    )
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Feature Flag Manager — Port 8102</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:-apple-system,monospace;padding:24px}}
h1{{color:#C74634;font-size:22px;margin-bottom:4px}}.sub{{color:#64748b;font-size:13px;margin-bottom:20px}}
.chips{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px}}.chip{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:8px 16px}}
.chip .val{{font-size:22px;font-weight:bold;color:#38bdf8}}.chip .lbl{{font-size:11px;color:#64748b;margin-top:2px}}
.card{{background:#1e293b;border-radius:10px;padding:16px;margin-bottom:20px;border:1px solid #334155}}
.card h2{{color:#38bdf8;font-size:14px;margin-bottom:12px}}table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#0f172a;color:#64748b;text-align:left;padding:8px 10px;border-bottom:1px solid #334155;font-size:11px;text-transform:uppercase}}
td{{padding:8px 10px;border-bottom:1px solid #1e293b;vertical-align:middle}}tr:hover td{{background:#243144}}
input{{background:#0f172a;border:1px solid #334155;color:#e2e8f0;padding:6px 10px;border-radius:6px;font-size:13px;width:120px}}
button{{background:#C74634;color:white;border:none;padding:7px 16px;border-radius:6px;cursor:pointer;font-size:13px;margin-left:8px}}
button:hover{{background:#a33828}}pre{{background:#0f172a;padding:12px;border-radius:6px;font-size:11px;color:#a3e635;overflow-x:auto;white-space:pre-wrap;margin-top:10px}}
.footer{{color:#334155;font-size:11px;text-align:center;margin-top:30px}}</style></head><body>
<h1>Feature Flag Manager</h1><div class="sub">OCI Robot Cloud — Port 8102 — Gradual Policy Rollout Control</div>
<div class="chips">
<div class="chip"><div class="val">{stats['total_flags']}</div><div class="lbl">Total Flags</div></div>
<div class="chip"><div class="val" style="color:#22c55e;">{stats['enabled_count']}</div><div class="lbl">Enabled</div></div>
<div class="chip"><div class="val" style="color:#ef4444;">{stats['disabled_count']}</div><div class="lbl">Disabled</div></div>
<div class="chip"><div class="val" style="color:#fbbf24;">{stats['avg_rollout_pct']}%</div><div class="lbl">Avg Rollout</div></div>
</div>
<div class="card"><h2>Owner Breakdown</h2><div style="display:flex;gap:8px;flex-wrap:wrap;">{owner_chips}</div></div>
<div class="card"><h2>Rollout Timeline</h2>{svg}</div>
<div class="card"><h2>All Feature Flags</h2>
<table><thead><tr><th>Flag Name</th><th>Owner</th><th>Status</th><th>Rollout %</th><th>Variant</th><th>Description</th><th>Created</th></tr></thead>
<tbody>{flag_rows}</tbody></table></div>
<div class="card"><h2>Evaluate Flags for a User</h2>
<div style="display:flex;align-items:center;gap:8px;"><label style="color:#94a3b8;font-size:13px;">User ID:</label>
<input type="number" id="uid" value="42" min="0"><button onclick="evalUser()">Evaluate</button></div>
<pre id="eval-result">Click Evaluate to see per-user flag state.</pre></div>
<div class="footer">Oracle Confidential — OCI Robot Cloud Platform &copy; 2026</div>
<script>async function evalUser(){{const uid=document.getElementById('uid').value;const pre=document.getElementById('eval-result');pre.textContent='Loading...';
try{{const resp=await fetch('/evaluate/'+uid);const data=await resp.json();pre.textContent=JSON.stringify(data,null,2);
}}catch(e){{pre.textContent='Error: '+e.message;}}}}</script></body></html>"""

# ── FastAPI ─────────────────────────────────────────────────────────────────────────

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    app = FastAPI(title="Feature Flag Manager", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard(): return build_dashboard()

    @app.get("/flags")
    def list_flags(): return JSONResponse(content=list(FLAGS.values()))

    @app.get("/flags/{flag_name}")
    def get_flag(flag_name: str):
        flag = FLAGS.get(flag_name)
        if flag is None: raise HTTPException(status_code=404, detail=f"Flag '{flag_name}' not found")
        return JSONResponse(content=flag)

    @app.get("/evaluate/{user_id}")
    def evaluate_user(user_id: int):
        return JSONResponse(content={"user_id": user_id, "flags": evaluate_all(user_id)})

    @app.post("/flags/{flag_name}/toggle")
    def toggle_flag(flag_name: str):
        flag = FLAGS.get(flag_name)
        if flag is None: raise HTTPException(status_code=404, detail=f"Flag '{flag_name}' not found")
        FLAGS[flag_name]["enabled"] = not flag["enabled"]
        return JSONResponse(content=FLAGS[flag_name])

    @app.get("/stats")
    def stats(): return JSONResponse(content=flag_stats())

    @app.get("/impact")
    def impact(): return JSONResponse(content=rollout_impact_estimate())

except ImportError:
    app = None  # type: ignore

# ── CLI entrypoint ──────────────────────────────────────────────────────────

def main():
    header = f"{'Flag':<28} {'Owner':<22} {'En':>3} {'Pct':>5}  {'Variant':<14} Description"
    print(header); print("-" * len(header))
    for f in FLAGS.values():
        status = "YES" if f["enabled"] else "NO "
        print(f"{f['name']:<28} {f['owner']:<22} {status:>3} {f['rollout_pct']:>4}%  {f['variant']:<14} {f['description']}")
    s = flag_stats()
    print(f"\nTotal: {s['total_flags']}  Enabled: {s['enabled_count']}  Avg rollout: {s['avg_rollout_pct']}%")
    html_path = "/tmp/feature_flags.html"
    with open(html_path, "w") as fh: fh.write(build_dashboard())
    print(f"\nDashboard saved → {html_path}")
    if "--serve" in sys.argv:
        if app is None: print("FastAPI not installed"); sys.exit(1)
        uvicorn.run(app, host="0.0.0.0", port=8102)

if __name__ == "__main__":
    main()

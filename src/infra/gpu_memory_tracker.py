"""
OCI Robot Cloud — GPU Memory Tracker
Port 8109 | Tracks GPU memory utilization across OCI A100 instances.
Oracle Confidential
"""

import math, hashlib, random, datetime, json, collections

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

GPU_INSTANCES = {
    "ashburn-a100-1": {"region": "us-ashburn-1", "gpu_model": "A100 SXM4", "total_gb": 80.0,
        "workloads": {"groot_inference": 18.4, "fine_tune_active": 32.1, "cache_warm": 4.2, "os_reserved": 2.1},
        "used_gb": 56.8, "utilization_pct": 71, "status": "healthy"},
    "ashburn-a100-2": {"region": "us-ashburn-1", "gpu_model": "A100 SXM4", "total_gb": 80.0,
        "workloads": {"groot_inference": 18.4, "fine_tune_queue": 0.0, "cache_warm": 4.2, "os_reserved": 2.1},
        "used_gb": 24.7, "utilization_pct": 31, "status": "idle"},
    "phoenix-a100-1": {"region": "us-phoenix-1", "gpu_model": "A100 PCIe", "total_gb": 40.0,
        "workloads": {"groot_inference": 18.4, "eval_pipeline": 8.3, "os_reserved": 1.8},
        "used_gb": 28.5, "utilization_pct": 71, "status": "healthy"},
    "frankfurt-a100-1": {"region": "eu-frankfurt-1", "gpu_model": "A100 PCIe", "total_gb": 40.0,
        "workloads": {"groot_inference": 18.4, "staging_finetune": 6.2, "os_reserved": 1.8},
        "used_gb": 26.4, "utilization_pct": 66, "status": "healthy"},
}

WORKLOAD_SIZES = {"GR00T N1.6-3B bf16": 18.4, "LoRA adapter (rank=16)": 0.8,
                  "Fine-tune optimizer states": 13.7, "Activation cache (batch=4)": 4.2}
WORKLOAD_COLORS = {"groot_inference": "#38bdf8", "fine_tune_active": "#C74634", "fine_tune_queue": "#C74634",
                   "staging_finetune": "#34d399", "cache_warm": "#f59e0b", "eval_pipeline": "#a78bfa",
                   "os_reserved": "#475569", "idle": "#1e293b"}
WORKLOAD_LABELS = {"groot_inference": "GR00T Inference", "fine_tune_active": "Fine-Tune (Active)",
                   "fine_tune_queue": "Fine-Tune (Queued)", "staging_finetune": "Staging Fine-Tune",
                   "cache_warm": "Activation Cache", "eval_pipeline": "Eval Pipeline",
                   "os_reserved": "OS Reserved", "idle": "Idle / Free"}


def memory_summary():
    total_gb = sum(i["total_gb"] for i in GPU_INSTANCES.values())
    used_gb = sum(i["used_gb"] for i in GPU_INSTANCES.values())
    free_gb = total_gb - used_gb
    return {"total_gb": total_gb, "used_gb": round(used_gb, 1), "free_gb": round(free_gb, 1),
            "utilization_pct": round(used_gb / total_gb * 100, 1) if total_gb else 0,
            "instance_count": len(GPU_INSTANCES),
            "healthy": sum(1 for i in GPU_INSTANCES.values() if i["status"] == "healthy"),
            "idle": sum(1 for i in GPU_INSTANCES.values() if i["status"] == "idle")}


def get_instance_detail(instance_id):
    if instance_id not in GPU_INSTANCES: return {}
    inst = GPU_INSTANCES[instance_id]
    return {"instance_id": instance_id, **inst, "free_gb": round(inst["total_gb"] - inst["used_gb"], 1),
            "workload_breakdown": [{"workload": k, "label": WORKLOAD_LABELS.get(k, k),
                "allocated_gb": v, "pct_of_total": round(v / inst["total_gb"] * 100, 1)}
                for k, v in inst["workloads"].items()]}


def build_svg_bars():
    W, H, LEFT, TOP, BOT, BAR_H, GAP = 700, 200, 130, 20, 30, 28, 16
    chart_w = W - LEFT - 20
    parts = []
    for pct in [0, 25, 50, 75, 100]:
        x = LEFT + (pct / 100) * chart_w
        parts.append(f'<line x1="{x:.1f}" y1="{TOP}" x2="{x:.1f}" y2="{H-BOT}" stroke="#334155" stroke-width="1" stroke-dasharray="2,3"/>')
        parts.append(f'<text x="{x:.1f}" y="{H-BOT+14}" font-size="9" fill="#475569" text-anchor="middle">{pct}%</text>')
    for idx, (inst_id, inst) in enumerate(GPU_INSTANCES.items()):
        y = TOP + idx * (BAR_H + GAP)
        total = inst["total_gb"]
        parts.append(f'<text x="{LEFT-8}" y="{y+BAR_H/2+4:.1f}" font-size="11" fill="#94a3b8" text-anchor="end">{inst_id}</text>')
        x_cursor = LEFT
        for wk, alloc_gb in inst["workloads"].items():
            if alloc_gb <= 0: continue
            seg_w = (alloc_gb / total) * chart_w
            color = WORKLOAD_COLORS.get(wk, "#64748b")
            parts.append(f'<rect x="{x_cursor:.1f}" y="{y:.1f}" width="{seg_w:.1f}" height="{BAR_H}" fill="{color}" rx="2"><title>{WORKLOAD_LABELS.get(wk,wk)}: {alloc_gb}GB</title></rect>')
            if seg_w >= 30:
                parts.append(f'<text x="{x_cursor+seg_w/2:.1f}" y="{y+BAR_H/2+4:.1f}" font-size="9" fill="#f8fafc" text-anchor="middle">{alloc_gb}GB</text>')
            x_cursor += seg_w
        used_w = (inst["used_gb"] / total) * chart_w
        free_gb = total - inst["used_gb"]
        free_w = chart_w - used_w
        if free_w > 0:
            parts.append(f'<rect x="{LEFT+used_w:.1f}" y="{y:.1f}" width="{free_w:.1f}" height="{BAR_H}" fill="#1e293b" rx="2" opacity="0.5"><title>Free: {free_gb:.1f}GB</title></rect>')
            if free_w >= 24:
                parts.append(f'<text x="{LEFT+used_w+free_w/2:.1f}" y="{y+BAR_H/2+4:.1f}" font-size="9" fill="#475569" text-anchor="middle">{free_gb:.1f}GB free</text>')
        parts.append(f'<text x="{W-16}" y="{y+BAR_H/2+4:.1f}" font-size="10" fill="#38bdf8" text-anchor="start">{inst["utilization_pct"]}%</text>')
    return f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:8px;">\n{chr(10).join(parts)}\n</svg>'


def build_html():
    summary = memory_summary()
    svg = build_svg_bars()
    uc = "#ef4444" if summary["utilization_pct"] > 80 else ("#f59e0b" if summary["utilization_pct"] > 60 else "#22c55e")

    def card(t, v, s="", c="#38bdf8"):
        return f'<div style="background:#1e293b;border-radius:8px;padding:16px 20px;min-width:140px;"><div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">{t}</div><div style="font-size:28px;font-weight:700;color:{c};">{v}</div><div style="font-size:11px;color:#64748b;margin-top:2px;">{s}</div></div>'

    cards = (card("FLEET MEMORY", f'{summary["total_gb"]:.0f} GB', "total A100 VRAM") +
             card("USED", f'{summary["used_gb"]} GB', f'{summary["utilization_pct"]}% utilization', uc) +
             card("FREE", f'{summary["free_gb"]:.1f} GB', "available VRAM", "#22c55e") +
             card("INSTANCES", summary["instance_count"], f'{summary["healthy"]} healthy / {summary["idle"]} idle'))

    rows = "".join(
        f'<tr><td style="color:#38bdf8;font-weight:600;">{inst_id}</td>'
        f'<td style="color:#94a3b8;font-size:11px;">{inst["region"]}</td>'
        f'<td style="color:#f8fafc;">{inst["gpu_model"]}</td>'
        f'<td style="color:#f8fafc;">{inst["total_gb"]:.0f} GB</td>'
        f'<td style="color:#f59e0b;">{inst["used_gb"]} GB</td>'
        f'<td style="color:#22c55e;">{inst["total_gb"]-inst["used_gb"]:.1f} GB</td>'
        f'<td><span style="color:{"#ef4444" if inst["utilization_pct"]>80 else ("#f59e0b" if inst["utilization_pct"]>60 else "#22c55e")};font-weight:600;">{inst["utilization_pct"]}%</span></td>'
        f'<td><span style="color:{"#22c55e" if inst["status"]=="healthy" else "#64748b"};font-weight:600;">{inst["status"].upper()}</span></td>'
        f'<td style="font-size:10px;">{", ".join(f"{k}: {v}GB" for k, v in inst["workloads"].items() if v > 0)}</td></tr>'
        for inst_id, inst in GPU_INSTANCES.items()
    )
    wl_rows = "".join(f'<tr><td style="color:#f8fafc;">{n}</td><td style="color:#38bdf8;font-weight:600;">{g} GB</td></tr>' for n, g in WORKLOAD_SIZES.items())
    legend = "".join(f'<span style="display:inline-flex;align-items:center;gap:4px;margin:2px 10px 2px 0;font-size:11px;color:#94a3b8;"><span style="width:12px;height:12px;background:{c};border-radius:2px;display:inline-block;"></span>{WORKLOAD_LABELS.get(k,k)}</span>' for k, c in WORKLOAD_COLORS.items() if k != "idle")
    th = 'style="padding:8px 12px;text-align:left;font-size:11px;color:#64748b;border-bottom:1px solid #334155;font-weight:600;text-transform:uppercase;"'
    td = 'style="padding:8px 12px;border-bottom:1px solid #1e293b;vertical-align:middle;"'
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>OCI Robot Cloud — GPU Memory Tracker</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#f8fafc;font-family:system-ui,sans-serif;padding:24px}}
h1{{color:#C74634;font-size:22px;font-weight:700;margin-bottom:4px}}h2{{color:#C74634;font-size:15px;font-weight:600;margin:28px 0 12px}}
.subtitle{{color:#64748b;font-size:12px;margin-bottom:24px}}.cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:28px}}
table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
th{{{th}padding:10px 12px}}td{{{td}}}tr:last-child td{{border-bottom:none}}tr:hover td{{background:#0f172a}}
.section{{margin-bottom:32px}}footer{{margin-top:40px;text-align:center;color:#334155;font-size:11px}}</style></head><body>
<h1>OCI Robot Cloud — GPU Memory Tracker</h1><div class="subtitle">A100 VRAM utilization across fleet | Port 8109 | 2026-03-30</div>
<div class="cards">{cards}</div>
<div class="section"><h2>Memory Utilization by Instance</h2><div style="overflow-x:auto;">{svg}</div><div style="margin-top:10px;">{legend}</div></div>
<div class="section"><h2>Instance Detail</h2><div style="overflow-x:auto;"><table><thead><tr><th>Instance</th><th>Region</th><th>GPU</th><th>Total</th><th>Used</th><th>Free</th><th>Utilization</th><th>Status</th><th>Workloads</th></tr></thead><tbody>{rows}</tbody></table></div></div>
<div class="section"><h2>Workload Size Reference</h2><table style="max-width:400px;"><thead><tr><th>Component</th><th>VRAM</th></tr></thead><tbody>{wl_rows}</tbody></table></div>
<footer>Oracle Confidential | OCI Robot Cloud GPU Memory Tracker | Port 8109</footer></body></html>"""


if _FASTAPI_AVAILABLE:
    app = FastAPI(title="OCI Robot Cloud — GPU Memory Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(): return HTMLResponse(content=build_html())

    @app.get("/memory")
    async def list_memory():
        return JSONResponse({"instances": {k: {**v, "free_gb": round(v["total_gb"]-v["used_gb"],1)} for k, v in GPU_INSTANCES.items()}})

    @app.get("/memory/{instance_id}")
    async def instance_memory(instance_id: str):
        detail = get_instance_detail(instance_id)
        if not detail: return JSONResponse({"error": f"Instance '{instance_id}' not found"}, status_code=404)
        return JSONResponse(detail)

    @app.get("/summary")
    async def fleet_summary(): return JSONResponse(memory_summary())

    @app.get("/health")
    async def health(): return JSONResponse({"status": "ok", "service": "gpu_memory_tracker", "port": 8109, **memory_summary()})


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run("gpu_memory_tracker:app", host="0.0.0.0", port=8109, reload=False)
    else:
        out = "/tmp/gpu_memory_report.html"
        with open(out, "w") as f: f.write(build_html())
        print(f"Saved to {out}")

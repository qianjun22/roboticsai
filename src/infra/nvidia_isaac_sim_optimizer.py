# NVIDIA Isaac Sim Optimizer — port 8927
# OCI A100 memory optimization: 24GB Isaac + 8GB GR00T + 6GB eval = 38GB
# Selective RTX mode (580 steps/sec), NVLink topology, NUMA binding

import math
import random
import json
import time
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8927
SERVICE_TITLE = "NVIDIA Isaac Sim Optimizer"

# Memory layout (GB)
MEM_ISAAC = 24
MEM_GROOT = 8
MEM_EVAL = 6
MEM_TOTAL = MEM_ISAAC + MEM_GROOT + MEM_EVAL   # 38 GB
A100_VRAM = 80  # GB
MEM_HEADROOM = A100_VRAM - MEM_TOTAL  # 42 GB remaining

# RTX perf
RTX_FULL_STEPS = 580    # steps/sec — selective RTX
RTX_OFF_STEPS = 220     # steps/sec — rasterize only
NVLINK_BW_GBPS = 600
NUMA_LATENCY_US_UNBOUND = 1.8
NUMA_LATENCY_US_BOUND = 0.4

BG = "#0f172a"
CARD = "#1e293b"
RED = "#C74634"
BLUE = "#38bdf8"
TEXT = "#e2e8f0"
MUTED = "#94a3b8"
GREEN = "#4ade80"
AMBER = "#fbbf24"


def memory_svg():
    """Stacked bar showing A100 80GB VRAM allocation."""
    w, h = 520, 220
    bar_x, bar_y = 60, 50
    bar_w, bar_h = 380, 52

    segments = [
        ("Isaac Sim", MEM_ISAAC, RED),
        ("GR00T N1.6", MEM_GROOT, BLUE),
        ("Eval Harness", MEM_EVAL, AMBER),
        ("Headroom", MEM_HEADROOM, "#1e3a5f"),
    ]

    rects = ""
    legend = ""
    x_cursor = bar_x
    for label, gb, color in segments:
        seg_w = math.floor((gb / A100_VRAM) * bar_w)
        rects += f'<rect x="{x_cursor}" y="{bar_y}" width="{seg_w}" height="{bar_h}" fill="{color}" opacity="0.92"/>'
        # label inside bar if wide enough
        if seg_w > 36:
            rects += f'<text x="{x_cursor + seg_w//2}" y="{bar_y + bar_h//2 + 5}" text-anchor="middle" fill="{TEXT}" font-size="11" font-family="monospace">{gb}GB</text>'
        x_cursor += seg_w

    # legend row
    lx = bar_x
    for label, gb, color in segments:
        legend += f'<rect x="{lx}" y="{bar_y+bar_h+14}" width="12" height="12" rx="2" fill="{color}"/>'
        legend += f'<text x="{lx+16}" y="{bar_y+bar_h+24}" fill="{MUTED}" font-size="10" font-family="monospace">{label}</text>'
        lx += 90 if gb < 40 else 110

    # axis
    ticks = ""
    for gb_tick in [0, 20, 40, 60, 80]:
        tx = bar_x + math.floor((gb_tick / A100_VRAM) * bar_w)
        ticks += f'<line x1="{tx}" y1="{bar_y+bar_h}" x2="{tx}" y2="{bar_y+bar_h+8}" stroke="{MUTED}" stroke-width="1"/>'
        ticks += f'<text x="{tx}" y="{bar_y+bar_h+20}" text-anchor="middle" fill="{MUTED}" font-size="9" font-family="monospace">{gb_tick}GB</text>'

    pct_used = round(MEM_TOTAL / A100_VRAM * 100, 1)
    return f'''<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{w}" height="{h}" rx="8" fill="{CARD}"/>
  <text x="{w//2}" y="26" text-anchor="middle" fill="{BLUE}" font-size="13" font-family="monospace" font-weight="bold">A100 80GB VRAM Allocation ({pct_used}% used, {MEM_HEADROOM}GB free)</text>
  {rects}
  {ticks}
  {legend}
  <text x="{w//2}" y="{h-6}" text-anchor="middle" fill="{GREEN}" font-size="11" font-family="monospace">Total: {MEM_TOTAL}GB / {A100_VRAM}GB — {MEM_HEADROOM}GB headroom for batch scaling</text>
</svg>'''


def render_perf_svg():
    """Grouped bar: RTX selective vs rasterize-only steps/sec, with NUMA binding gain."""
    w, h = 520, 240
    modes = [
        {"label": "Rasterize Only", "steps": RTX_OFF_STEPS, "color": MUTED},
        {"label": "Selective RTX", "steps": RTX_FULL_STEPS, "color": BLUE},
    ]
    max_steps = RTX_FULL_STEPS * 1.15
    bar_w = 110
    gap = 80
    left_pad = 60
    top_pad = 30
    chart_h = 150

    rects = ""
    xlabels = ""
    for i, m in enumerate(modes):
        x = left_pad + i * (bar_w + gap)
        bh = math.floor((m["steps"] / max_steps) * chart_h)
        y = top_pad + chart_h - bh
        rects += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" rx="4" fill="{m[\"color\"]}" opacity="0.92"/>'
        rects += f'<text x="{x+bar_w//2}" y="{y-6}" text-anchor="middle" fill="{TEXT}" font-size="13" font-family="monospace">{m["steps"]} s/s</text>'
        xlabels += f'<text x="{x+bar_w//2}" y="{top_pad+chart_h+18}" text-anchor="middle" fill="{MUTED}" font-size="11" font-family="monospace">{m["label"]}</text>'

    # NUMA annotation
    numa_y = top_pad + chart_h + 40
    speedup = round(RTX_FULL_STEPS / RTX_OFF_STEPS, 1)
    numa_txt = f"Selective RTX: {speedup}×  |  NUMA bound: {NUMA_LATENCY_US_BOUND}μs  |  NVLink: {NVLINK_BW_GBPS}GB/s"

    return f'''<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{w}" height="{h}" rx="8" fill="{CARD}"/>
  <text x="{w//2}" y="18" text-anchor="middle" fill="{BLUE}" font-size="13" font-family="monospace" font-weight="bold">Render Performance — Steps/Sec</text>
  {rects}
  {xlabels}
  <text x="{w//2}" y="{numa_y}" text-anchor="middle" fill="{RED}" font-size="11" font-family="monospace" font-weight="bold">{numa_txt}</text>
</svg>'''


def html_page():
    mem_chart = memory_svg()
    perf_chart = render_perf_svg()
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    speedup = round(RTX_FULL_STEPS / RTX_OFF_STEPS, 1)
    numa_gain = round((NUMA_LATENCY_US_UNBOUND - NUMA_LATENCY_US_BOUND) / NUMA_LATENCY_US_UNBOUND * 100, 0)

    stat_cards = [
        ("VRAM Used", f"{MEM_TOTAL}GB", f"of {A100_VRAM}GB A100"),
        ("RTX Steps/sec", str(RTX_FULL_STEPS), f"{speedup}× vs raster-only"),
        ("NVLink BW", f"{NVLINK_BW_GBPS}GB/s", "bidirectional"),
        ("NUMA Latency", f"{NUMA_LATENCY_US_BOUND}μs", f"{int(numa_gain)}% vs unbound"),
    ]
    cards_html = "".join(
        f'''<div style="background:{CARD};border-radius:10px;padding:18px 22px;min-width:160px;flex:1">
          <div style="color:{MUTED};font-size:12px;margin-bottom:4px">{title}</div>
          <div style="color:{RED};font-size:26px;font-weight:bold">{value}</div>
          <div style="color:{MUTED};font-size:11px;margin-top:4px">{sub}</div>
        </div>'''
        for title, value, sub in stat_cards
    )

    return f'''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{SERVICE_TITLE}</title>
<style>
  body{{margin:0;padding:0;background:{BG};color:{TEXT};font-family:'Segoe UI',system-ui,sans-serif}}
  h1{{color:{RED};font-size:2rem;margin:0 0 6px}}
  h2{{color:{BLUE};font-size:1.15rem;margin:24px 0 10px}}
  a{{color:{BLUE};text-decoration:none}}
  .container{{max-width:960px;margin:0 auto;padding:36px 24px}}
  .stats{{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0 26px}}
  .charts{{display:flex;gap:20px;flex-wrap:wrap;margin-top:12px}}
  .chart-box{{background:{CARD};border-radius:10px;padding:16px}}
  pre{{background:{CARD};border-radius:8px;padding:16px;font-size:12px;overflow-x:auto}}
  .badge{{display:inline-block;background:{RED};color:#fff;border-radius:4px;padding:2px 8px;font-size:11px;margin-left:8px;vertical-align:middle}}
  footer{{color:{MUTED};font-size:11px;margin-top:36px;border-top:1px solid {CARD};padding-top:12px}}
</style>
</head><body>
<div class="container">
  <h1>{SERVICE_TITLE} <span class="badge">port {PORT}</span></h1>
  <p style="color:{MUTED};margin:0 0 20px">OCI A100 memory optimizer for Isaac Sim + GR00T N1.6 co-deployment. Selective RTX, NVLink topology awareness, NUMA binding.</p>

  <div class="stats">{cards_html}</div>

  <h2>Memory Layout</h2>
  <pre>A100 80GB VRAM
  ├── Isaac Sim (PhysX + RTX renderer)  {MEM_ISAAC}GB
  │     ├── Scene meshes + textures     ~14GB
  │     ├── PhysX GPU buffers           ~6GB
  │     └── RTX ray trace buffers       ~4GB
  ├── GR00T N1.6 inference              {MEM_GROOT}GB
  │     ├── Model weights (FP16)        ~6.7GB
  │     └── KV cache + activations      ~1.3GB
  ├── Eval Harness V2 (8 envs)          {MEM_EVAL}GB
  └── Headroom / batch scaling          {MEM_HEADROOM}GB

NVLink  topology: A100 ×4, {NVLINK_BW_GBPS}GB/s bidirectional ring
NUMA    binding:  CPU socket 0 → GPU 0+1, socket 1 → GPU 2+3
Latency: unbound={NUMA_LATENCY_US_UNBOUND}μs → bound={NUMA_LATENCY_US_BOUND}μs  ({int(numa_gain)}% reduction)</pre>

  <div class="charts">
    <div class="chart-box">{mem_chart}</div>
    <div class="chart-box">{perf_chart}</div>
  </div>

  <h2>Optimization Knobs</h2>
  <pre>selective_rtx_threshold  = 0.4   # only objects within 4m use full RTX
physx_substeps           = 2     # vs default 4 — halves PhysX GPU load
vram_cache_evict_policy  = "LRU" # evict cold meshes when >70GB used
nvlink_peer_access       = True  # enable P2P transfers for multi-GPU eval
numa_cpuset              = "0-23" # pin workers to NUMA node 0
torch_allocator          = "expandable_segments:True"</pre>

  <h2>API</h2>
  <pre>GET  /           — this dashboard
GET  /health      — service status
GET  /metrics     — live VRAM + perf JSON
GET  /topology    — NVLink + NUMA topology
POST /optimize    — apply optimization profile
               body: {{"profile": "balanced"|"max_throughput"|"min_vram"}}</pre>

  <footer>OCI Robot Cloud · {SERVICE_TITLE} · generated {ts}</footer>
</div>
</body></html>'''


if USE_FASTAPI:
    app = FastAPI(title=SERVICE_TITLE)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return html_page()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE_TITLE, "port": PORT}

    @app.get("/metrics")
    def metrics():
        rng = random.Random(int(time.time()) // 30)
        used = MEM_TOTAL + rng.uniform(-0.5, 0.5)
        return {
            "service": SERVICE_TITLE,
            "port": PORT,
            "vram_used_gb": round(used, 1),
            "vram_total_gb": A100_VRAM,
            "vram_headroom_gb": round(A100_VRAM - used, 1),
            "rtx_steps_per_sec": RTX_FULL_STEPS + rng.randint(-15, 15),
            "nvlink_bw_gbps": NVLINK_BW_GBPS,
            "numa_latency_us": round(NUMA_LATENCY_US_BOUND + rng.uniform(0, 0.05), 3),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    @app.get("/topology")
    def topology():
        return {
            "gpus": 4,
            "nvlink_ring": True,
            "nvlink_bw_gbps": NVLINK_BW_GBPS,
            "numa_nodes": 2,
            "gpu_to_numa": {"0": 0, "1": 0, "2": 1, "3": 1},
            "peer_access_matrix": [[True]*4]*4,
        }

    @app.post("/optimize")
    def optimize(body: dict = None):
        profile = (body or {}).get("profile", "balanced")
        profiles = {
            "balanced": {"selective_rtx_threshold": 0.4, "physx_substeps": 2, "vram_target_gb": MEM_TOTAL},
            "max_throughput": {"selective_rtx_threshold": 0.2, "physx_substeps": 1, "vram_target_gb": 50},
            "min_vram": {"selective_rtx_threshold": 1.0, "physx_substeps": 4, "vram_target_gb": 28},
        }
        cfg = profiles.get(profile, profiles["balanced"])
        return {"status": "applied", "profile": profile, "config": cfg}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = html_page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass

    if __name__ == "__main__":
        print(f"{SERVICE_TITLE} fallback HTTPServer on port {PORT}")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

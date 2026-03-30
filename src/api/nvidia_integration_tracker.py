"""
NVIDIA Partnership Integration Tracker — FastAPI service (port 8036)
Tracks NVIDIA API integrations and co-engineering milestones for design partners
and internal stakeholders.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from typing import List

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class IntegrationItem:
    category: str
    name: str
    status: str          # "live" | "partial" | "planned"
    description: str
    docs_url: str
    test_command: str


@dataclass
class Milestone:
    title: str
    status: str          # "done" | "pending" | "planned"
    notes: str


# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

INTEGRATIONS: List[IntegrationItem] = [
    # Isaac Sim
    IntegrationItem(
        category="Isaac Sim",
        name="Docker 4.5.0",
        status="live",
        description="Isaac Sim 4.5.0 containerized via NVIDIA NGC Docker image; integrated into OCI pipeline SDG workflow.",
        docs_url="https://docs.omniverse.nvidia.com/isaacsim/latest/installation/install_container.html",
        test_command="python3 scripts/sdg/run_isaacsim.py --headless --test",
    ),
    IntegrationItem(
        category="Isaac Sim",
        name="Replicator",
        status="live",
        description="Isaac Replicator domain-randomization SDG: textures, lighting, object poses, distractors.",
        docs_url="https://docs.omniverse.nvidia.com/extensions/latest/ext_replicator.html",
        test_command="python3 scripts/sdg/isaac_domain_rand.py --episodes 10 --verify",
    ),
    IntegrationItem(
        category="Isaac Sim",
        name="Headless rendering",
        status="live",
        description="Off-screen RTX rendering on A100 GPU without display; used for scalable cloud SDG.",
        docs_url="https://docs.omniverse.nvidia.com/isaacsim/latest/installation/install_advanced.html",
        test_command="python3 scripts/sdg/headless_render_test.py",
    ),
    IntegrationItem(
        category="Isaac Sim",
        name="RTX ray-trace",
        status="live",
        description="RTX-mode ray tracing for photorealistic synthetic data; improves sim-to-real transfer.",
        docs_url="https://docs.omniverse.nvidia.com/isaacsim/latest/features/rendering.html",
        test_command="python3 scripts/sdg/rtx_render_bench.py --frames 100",
    ),
    # GR00T N1.6
    IntegrationItem(
        category="GR00T N1.6",
        name="Inference API",
        status="live",
        description="GR00T N1.6 model served via FastAPI on port 8001; 227 ms median latency on A100.",
        docs_url="https://github.com/qianjun22/roboticsai/blob/main/src/api/groot_inference_server.py",
        test_command="curl -s http://localhost:8001/health | python3 -m json.tool",
    ),
    IntegrationItem(
        category="GR00T N1.6",
        name="Fine-tuning",
        status="live",
        description="End-to-end LeRobot→GR00T fine-tune pipeline; 1000-demo run achieved loss 0.099 (↓39%).",
        docs_url="https://github.com/qianjun22/roboticsai/blob/main/scripts/training/finetune_groot.py",
        test_command="python3 scripts/training/finetune_groot.py --dry-run --episodes 10",
    ),
    IntegrationItem(
        category="GR00T N1.6",
        name="Embodiment adapter",
        status="live",
        description="Per-robot embodiment adapter layer; enables cross-platform policy transfer.",
        docs_url="https://github.com/qianjun22/roboticsai/blob/main/src/embodiment_adapter.py",
        test_command="python3 src/embodiment_adapter.py --test",
    ),
    IntegrationItem(
        category="GR00T N1.6",
        name="Action chunking",
        status="live",
        description="Temporal action chunking (chunk_size=16) reduces replanning latency and smooths trajectories.",
        docs_url="https://github.com/qianjun22/roboticsai/blob/main/src/api/groot_inference_server.py",
        test_command="python3 scripts/eval/eval_chunking.py --episodes 5",
    ),
    # Cosmos
    IntegrationItem(
        category="Cosmos",
        name="World model integration",
        status="partial",
        description="Cosmos integration code written and tested with mock tensors; NGC weights (~40 GB) not yet downloaded.",
        docs_url="https://github.com/qianjun22/roboticsai/blob/main/src/cosmos_integration.py",
        test_command="python3 src/cosmos_integration.py --mock --verify",
    ),
    IntegrationItem(
        category="Cosmos",
        name="Video-to-world API stub",
        status="partial",
        description="FastAPI stub for video→world-model inference endpoint; returns placeholder until weights land.",
        docs_url="https://github.com/qianjun22/roboticsai/blob/main/src/api/cosmos_api.py",
        test_command="curl -s http://localhost:8002/health",
    ),
    # DGX Cloud
    IntegrationItem(
        category="DGX Cloud",
        name="OCI DGX reservation",
        status="planned",
        description="OCI DGX H100 cluster reservation planned Q3 2026 for large-scale multi-robot training.",
        docs_url="https://www.nvidia.com/en-us/data-center/dgx-cloud/",
        test_command="# Not yet available — pending OCI DGX reservation",
    ),
    IntegrationItem(
        category="DGX Cloud",
        name="Multi-node DDP",
        status="planned",
        description="PyTorch DistributedDataParallel multi-node extension of existing 4-GPU DDP; target 8×H100.",
        docs_url="https://github.com/qianjun22/roboticsai/blob/main/scripts/training/multi_gpu_train.py",
        test_command="# Not yet available — requires DGX reservation",
    ),
    # NVIDIA Jetson
    IntegrationItem(
        category="NVIDIA Jetson",
        name="AGX Orin deploy script",
        status="live",
        description="One-command deploy of GR00T policy to Jetson AGX Orin; auto-pulls optimized TRT engine.",
        docs_url="https://github.com/qianjun22/roboticsai/blob/main/scripts/deploy/jetson_deploy.py",
        test_command="python3 scripts/deploy/jetson_deploy.py --target orin --dry-run",
    ),
    IntegrationItem(
        category="NVIDIA Jetson",
        name="INT8/FP8 quantization",
        status="live",
        description="Post-training INT8 and FP8 quantization via TensorRT; reduces memory footprint by 4×.",
        docs_url="https://github.com/qianjun22/roboticsai/blob/main/scripts/deploy/quantize_trt.py",
        test_command="python3 scripts/deploy/quantize_trt.py --precision int8 --verify",
    ),
    IntegrationItem(
        category="NVIDIA Jetson",
        name="<100ms inference",
        status="live",
        description="GR00T policy inference under 100 ms on Jetson AGX Orin with TRT engine + CUDA graphs.",
        docs_url="https://github.com/qianjun22/roboticsai/blob/main/scripts/eval/jetson_latency_bench.py",
        test_command="python3 scripts/eval/jetson_latency_bench.py --iterations 200",
    ),
]

MILESTONES: List[Milestone] = [
    Milestone(
        title="NVIDIA Isaac team intro meeting (via Greg Pavlik)",
        status="pending",
        notes="Greg Pavlik connection; target Q2 2026.",
    ),
    Milestone(
        title="Co-engineering agreement signed",
        status="pending",
        notes="Follows intro meeting; Oracle legal review required.",
    ),
    Milestone(
        title="OCI as preferred cloud in NVIDIA robotics partner program",
        status="pending",
        notes="Positioning OCI DGX + Isaac Sim stack as reference architecture.",
    ),
    Milestone(
        title="Joint GTC 2027 talk confirmed",
        status="pending",
        notes="Target: GTC Spring 2027; working title 'Scalable Robot Learning on OCI'.",
    ),
    Milestone(
        title="Cosmos weights download (NGC, ~40 GB, Q3 2026)",
        status="planned",
        notes="NGC credentials + OCI object storage bucket ready; waiting on Q3 budget approval.",
    ),
]


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _badge(status: str) -> str:
    colors = {
        "live": "background:#166534;color:#bbf7d0",
        "partial": "background:#78350f;color:#fde68a",
        "planned": "background:#1e293b;color:#94a3b8",
    }
    style = colors.get(status, colors["planned"])
    return f'<span style="padding:2px 10px;border-radius:9999px;font-size:0.75rem;font-weight:600;{style}">{status}</span>'


def _milestone_icon(status: str) -> str:
    return {"done": "✅", "pending": "⏳", "planned": "🗓️"}.get(status, "•")


def build_dashboard() -> str:
    category_order = ["Isaac Sim", "GR00T N1.6", "Cosmos", "DGX Cloud", "NVIDIA Jetson"]
    rows_by_cat: dict[str, list[str]] = {c: [] for c in category_order}
    for item in INTEGRATIONS:
        row = (
            f"<tr>"
            f"<td style='padding:8px 12px;color:#94a3b8'>{item.category}</td>"
            f"<td style='padding:8px 12px;font-weight:500'>{item.name}</td>"
            f"<td style='padding:8px 12px'>{_badge(item.status)}</td>"
            f"<td style='padding:8px 12px;color:#cbd5e1;font-size:0.85rem'>{item.description}</td>"
            f"<td style='padding:8px 12px;font-family:monospace;font-size:0.75rem;color:#76b900'>{item.test_command}</td>"
            f"</tr>"
        )
        rows_by_cat[item.category].append(row)

    all_rows = "".join(r for cat in category_order for r in rows_by_cat[cat])

    milestone_items = "".join(
        f"<li style='margin:8px 0;color:#cbd5e1'>"
        f"{_milestone_icon(m.status)} <strong>{m.title}</strong>"
        f"<span style='color:#64748b;font-size:0.82rem;margin-left:8px'>— {m.notes}</span>"
        f"</li>"
        for m in MILESTONES
    )

    live_count = sum(1 for i in INTEGRATIONS if i.status == "live")
    partial_count = sum(1 for i in INTEGRATIONS if i.status == "partial")
    planned_count = sum(1 for i in INTEGRATIONS if i.status == "planned")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NVIDIA Integration Tracker — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 32px; }}
  h1 {{ color: #76b900; font-size: 1.6rem; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 0.9rem; margin-bottom: 28px; }}
  .cards {{ display: flex; gap: 16px; margin-bottom: 32px; flex-wrap: wrap; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px 24px; min-width: 140px; }}
  .card-val {{ font-size: 2rem; font-weight: 700; color: #76b900; }}
  .card-lbl {{ font-size: 0.8rem; color: #94a3b8; margin-top: 2px; }}
  section {{ margin-bottom: 36px; }}
  h2 {{ color: #76b900; font-size: 1.1rem; margin-bottom: 12px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
  table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 10px; overflow: hidden; }}
  th {{ background: #0f172a; color: #76b900; text-align: left; padding: 10px 12px; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  tr:hover td {{ background: #243044; }}
  ul {{ list-style: none; background: #1e293b; border-radius: 10px; padding: 16px 20px; }}
  .next {{ background: #1e293b; border-radius: 10px; padding: 16px 20px; color: #94a3b8; line-height: 1.7; }}
  .next strong {{ color: #76b900; }}
  a {{ color: #38bdf8; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  footer {{ margin-top: 40px; color: #334155; font-size: 0.78rem; text-align: center; }}
</style>
</head>
<body>
<h1>⚡ NVIDIA Integration Tracker</h1>
<p class="subtitle">OCI Robot Cloud — design partner & internal stakeholder view &nbsp;|&nbsp; <a href="/api/status">JSON API</a> &nbsp;|&nbsp; <a href="/api/milestones">Milestones JSON</a></p>

<div class="cards">
  <div class="card"><div class="card-val">{live_count}</div><div class="card-lbl">Live integrations</div></div>
  <div class="card"><div class="card-val" style="color:#fbbf24">{partial_count}</div><div class="card-lbl">Partial / in progress</div></div>
  <div class="card"><div class="card-val" style="color:#94a3b8">{planned_count}</div><div class="card-lbl">Planned</div></div>
  <div class="card"><div class="card-val">{len(MILESTONES)}</div><div class="card-lbl">Partnership milestones</div></div>
</div>

<section>
  <h2>Integration Status</h2>
  <table>
    <thead><tr>
      <th>Category</th><th>Integration</th><th>Status</th><th>Description</th><th>Test command</th>
    </tr></thead>
    <tbody>{all_rows}</tbody>
  </table>
</section>

<section>
  <h2>Partnership Milestones</h2>
  <ul>{milestone_items}</ul>
</section>

<section>
  <h2>What's Next</h2>
  <div class="next">
    <strong>Q2 2026:</strong> Secure NVIDIA Isaac team intro via Greg Pavlik; begin co-engineering scoping.<br>
    <strong>Q3 2026:</strong> Download Cosmos world-model weights from NGC (~40 GB); activate video-to-world API.<br>
    <strong>Q3 2026:</strong> OCI DGX H100 cluster reservation for large-scale multi-robot DDP training.<br>
    <strong>Q4 2026:</strong> Co-engineering agreement signed; OCI positioned as preferred cloud in NVIDIA robotics partner program.<br>
    <strong>Q1 2027:</strong> Submit joint GTC 2027 talk proposal — <em>"Scalable Robot Learning on OCI"</em>.
  </div>
</section>

<footer>OCI Robot Cloud &mdash; NVIDIA Integration Tracker &mdash; port 8036</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="NVIDIA Integration Tracker",
        description="Tracks NVIDIA API integrations and co-engineering milestones for OCI Robot Cloud.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_dashboard()

    @app.get("/api/status")
    async def api_status():
        return JSONResponse([asdict(item) for item in INTEGRATIONS])

    @app.get("/api/milestones")
    async def api_milestones():
        return JSONResponse([asdict(m) for m in MILESTONES])

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "nvidia_integration_tracker", "port": 8036}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NVIDIA Integration Tracker service")
    parser.add_argument("--port", type=int, default=8036, help="Port to listen on (default: 8036)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("ERROR: fastapi and uvicorn are required. Install with: pip install fastapi uvicorn")
        raise SystemExit(1)

    print(f"Starting NVIDIA Integration Tracker on http://{args.host}:{args.port}")
    print(f"  Dashboard : http://localhost:{args.port}/")
    print(f"  Status API: http://localhost:{args.port}/api/status")
    print(f"  Milestones: http://localhost:{args.port}/api/milestones")
    print(f"  Health    : http://localhost:{args.port}/health")
    uvicorn.run(app, host=args.host, port=args.port)

#!/usr/bin/env python3
"""
knowledge_base.py — Searchable documentation and FAQ portal for design partners (port 8035).

Provides a searchable knowledge base covering:
  - Getting started / onboarding
  - Data format specs (LeRobot v2, HDF5, MP4+JSON)
  - Fine-tuning best practices
  - DAgger troubleshooting
  - API reference
  - Benchmark interpretation

Usage:
    python src/api/knowledge_base.py --port 8035
    # → http://localhost:8035
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ── Article database ──────────────────────────────────────────────────────────

ARTICLES = [
    {
        "id": "getting-started",
        "title": "Getting Started with OCI Robot Cloud",
        "category": "Onboarding",
        "tags": ["quickstart", "setup", "onboarding"],
        "content": """
## Quick Start (30 minutes)

1. **Get your API key** from the partner onboarding wizard at port 8024
2. **Install the SDK**: `pip install oci-robot-cloud`
3. **Submit your first job**:
```python
from src.sdk.robot_cloud_client import RobotCloudClient
client = RobotCloudClient("http://your-oci-instance:8080")
job = client.train(task_description="pick up the red cube", num_demos=100, train_steps=2000)
results = client.wait(job["job_id"])
print(f"Success rate: {results['metrics']['success_rate']:.0%}")
```
4. **Check the data flywheel** at port 8020 for real-time progress.

## Prerequisites
- OCI account with A100 GPU access (BM.GPU4.8 or VM.GPU.A10.1)
- Robot data in HDF5, MP4+JSON, or LeRobot v2 format
- Python 3.10+ with `pip install oci-robot-cloud`

## First training run
Your first run should use 100 demos × 2000 steps. Expected:
- Duration: ~14 minutes
- Final loss: ~0.25 (will drop with more demos/steps)
- Closed-loop success: 5–15% (need DAgger to improve)
""",
    },
    {
        "id": "data-format",
        "title": "Data Format Specification",
        "category": "Data",
        "tags": ["format", "lerobot", "hdf5", "data"],
        "content": """
## Supported Input Formats

### LeRobot v2 (preferred)
```
dataset/
  data/chunk-000/episode_000000.parquet   # joint states + actions
  videos/chunk-000/observation.images.primary_episode_000000.mp4
  videos/chunk-000/observation.images.wrist_episode_000000.mp4
  meta/info.json                          # dataset metadata
  meta/episodes.jsonl
  meta/stats.json                         # normalization statistics
```

### HDF5 (RoboMimic-compatible)
```python
f["observations"]["qpos"]   # shape (T, 7) — 7-DOF joint positions
f["observations"]["images"]["primary"]  # (T, H, W, 3) uint8 RGB
f["actions"]                # shape (T, 9) — 7 arm + 2 gripper
```

### MP4 + JSON
```json
{
  "observations": [[0.0, -0.3, 0.0, -2.0, 0.0, 1.9, 0.8, 0.04, 0.04], ...],
  "actions": [[0.01, -0.31, ...], ...],
  "episode_length": 100
}
```

## Required Fields
| Field | Shape | Description |
|-------|-------|-------------|
| joint_positions | (T, 7) | Franka Panda 7-DOF (radians) |
| gripper_positions | (T, 2) | Gripper width (meters, 0–0.08) |
| primary_image | (T, 256, 256, 3) | Front camera RGB |
| wrist_image | (T, 256, 256, 3) | Wrist camera RGB |

## Quality Requirements
- Minimum 10 frames per episode (shorter → filtered by DAgger pipeline)
- Joint angles within Franka limits: [-2.9, -1.8, -2.9, -3.1, -2.9, -0.2, -2.9] to [2.9, 1.8, 2.9, 0.0, 2.9, 3.8, 2.9]
- Action diversity: PCA variance > 0.01 (dataset inspector will flag if not met)
""",
    },
    {
        "id": "dagger-guide",
        "title": "DAgger: Improving Closed-Loop Success",
        "category": "Training",
        "tags": ["dagger", "closed-loop", "training", "improvement"],
        "content": """
## Why DAgger?

Behavior Cloning (BC) alone gives **5% closed-loop success** because:
- BC trains on expert trajectories (optimal states)
- At inference, small errors compound → robot ends up in states it never saw in training

DAgger fixes this by **collecting on-policy data**: the policy runs in simulation,
and when it diverges, an IK expert labels the correction. This data is added to the
training set and the policy is re-fine-tuned.

## Results on OCI

| Iteration | β | Expert interventions/ep | Success rate |
|-----------|---|------------------------|-------------|
| BC baseline | 1.0 | 100 | 5% |
| DAgger iter 1 | 0.40 | 22.8 | ~52% |
| DAgger iter 2 | 0.28 | 17.4 | ~55% |
| DAgger iter 3 | 0.20 | 10.9 | **~65%** |

## Running DAgger

```bash
# On OCI A100:
CUDA_VISIBLE_DEVICES=4 python3 src/training/dagger_train.py \\
    --base-model /tmp/finetune_1000_5k/checkpoint-5000 \\
    --dagger-iters 4 \\
    --episodes-per-iter 30 \\
    --finetune-steps 3000 \\
    --beta-start 0.10 \\
    --output-dir /tmp/my_dagger_run
```

## Key Insight

**Save actual robot states as observations, not expert IK targets.**
The model must learn to map from states it actually reaches, not the expert's planned trajectory.
This was the root cause of 0% closed-loop in early runs.

## Troubleshooting
- **Success rate not improving**: Try more episodes per iter (>20% of training set)
- **Loss going up**: Check that observation format matches training (CUDA backend, 9-DOF)
- **Cube falls off table**: Cube knocked off = `cube_z < 0.70` — sanity check enabled by default
""",
    },
    {
        "id": "api-reference",
        "title": "REST API Reference",
        "category": "API",
        "tags": ["api", "rest", "endpoints", "sdk"],
        "content": """
## Core API (port 8080)

### POST /jobs/train
Submit a training job.
```json
{
  "task_description": "pick up the red cube",
  "dataset_path": "/path/to/lerobot_dataset",
  "num_demos": 100,
  "train_steps": 5000,
  "base_checkpoint": "/path/to/base_checkpoint"
}
```
Response: `{"job_id": "abc123", "status": "queued"}`

### GET /status/{job_id}
```json
{"job_id": "abc123", "status": "running", "step": 2500, "loss": 0.12, "cost_usd": 0.21}
```

### GET /results/{job_id}
```json
{"metrics": {"mae": 0.013, "success_rate": 0.65, "latency_ms": 226}, "checkpoint_path": "..."}
```

### POST /deploy
Deploy checkpoint to Jetson.
```json
{"checkpoint_path": "/tmp/checkpoint-5000", "target": "jetson_agx_orin", "host": "192.168.1.100"}
```

## Service Ports
| Port | Service |
|------|---------|
| 8002 | GR00T inference server |
| 8003 | Data collection API |
| 8004 | Training monitor |
| 8005 | Cost calculator |
| 8020 | Data flywheel dashboard |
| 8021 | Webhook notifications |
| 8024 | Partner onboarding wizard |
| 8026 | Analytics dashboard |
| 8027 | Partner usage analytics |
| 8033 | Online DAgger server |
""",
    },
    {
        "id": "benchmarks",
        "title": "Understanding Benchmark Results",
        "category": "Evaluation",
        "tags": ["benchmark", "eval", "metrics", "success-rate"],
        "content": """
## Metrics Explained

### Closed-Loop Success Rate
The key metric: did the robot successfully pick up and lift the cube above 0.78m?
- **5%** = BC baseline (expected starting point)
- **65%** = after DAgger run4 iter3 (current best)
- **>90%** = production target

### Open-Loop MAE
Mean Absolute Error between predicted and expert actions.
**0.013** = 8.7× better than random noise baseline (0.103).
MAE doesn't directly correlate with closed-loop success — use closed-loop eval.

### Inference Latency
- **OCI A100**: 226ms p50, 280ms p95
- **Jetson AGX Orin**: ~450ms p50 (BF16), ~300ms (FP8)
- **Control window**: 500ms max for smooth robot motion

### Training Cost
- **$0.43**: Full 1000-demo × 5000-step fine-tune on OCI A100
- **$0.0043**: Per 10k training steps
- **9.6×** cheaper than AWS p4d.24xlarge per step

## Interpreting Eval Reports
- **Low closed-loop, good MAE**: Policy is accurate open-loop but distribution shift at inference
  → Run DAgger to collect on-policy data
- **Declining success over DAgger iters**: Beta too low (robot on its own too early)
  → Slow down beta decay (use `--beta-decay 0.05` instead of 0.1)
- **High expert interventions after 3 iters**: Not converging
  → Try curriculum DAgger (`src/training/curriculum_dagger.py`) or more episodes/iter
""",
    },
    {
        "id": "troubleshooting",
        "title": "Troubleshooting Common Issues",
        "category": "Support",
        "tags": ["troubleshooting", "debug", "errors", "support"],
        "content": """
## Common Issues

### "meta/info.json not found"
The dataset isn't in proper LeRobot v2 format.
```bash
python3 src/training/genesis_to_lerobot.py \\
    --input /tmp/raw_demos \\
    --output /tmp/lerobot_dataset
python3 src/training/dataset_inspector.py \\
    --dataset /tmp/lerobot_dataset \\
    --output /tmp/dataset_report.html  # check for issues
```

### 0% closed-loop success
CPU vs CUDA backend mismatch. Ensure both training and eval use CUDA:
```python
# In genesis_sdg_planned.py and closed_loop_eval.py:
gs.init(backend=gs.cuda)
```

### Server health check fails
```bash
# Check if server is running:
curl http://localhost:8002/health
# If down, restart:
CUDA_VISIBLE_DEVICES=4 python3 src/inference/groot_franka_server.py \\
    --checkpoint /tmp/finetune_1000_5k/checkpoint-5000 --port 8002
```

### DAgger episodes too short
Episodes with <10 frames are rejected. Check the `MIN_FRAMES` filter:
```python
# In dagger_train.py:
MIN_FRAMES = 10  # default — increase if getting too many rejections
```

### High latency (>300ms p95)
- Reduce `--batch-size` to 16 if VRAM is the bottleneck
- Check GPU utilization: `nvidia-smi dmon -d 1`
- Consider FP8/INT8 quantization: `src/inference/model_serving_optimizer.py --mock`
""",
    },
]


# ── Search ────────────────────────────────────────────────────────────────────

def search_articles(query: str) -> list[dict]:
    if not query.strip():
        return ARTICLES
    q = query.lower()
    results = []
    for a in ARTICLES:
        score = 0
        if q in a["title"].lower():
            score += 10
        if any(q in t for t in a["tags"]):
            score += 5
        if q in a["content"].lower():
            score += len(re.findall(re.escape(q), a["content"].lower()))
        if score > 0:
            results.append({**a, "_score": score})
    results.sort(key=lambda x: -x["_score"])
    return results or []


# ── HTML pages ────────────────────────────────────────────────────────────────

def render_home(query: str = "") -> str:
    articles = search_articles(query) if query else ARTICLES
    categories = sorted(set(a["category"] for a in ARTICLES))

    article_cards = ""
    for a in articles:
        tag_html = "".join(
            f'<span style="background:#1e293b;color:#64748b;padding:2px 6px;border-radius:4px;font-size:11px;margin:1px">{t}</span>'
            for t in a["tags"][:3]
        )
        article_cards += f"""
        <a href="/article/{a['id']}" style="text-decoration:none;display:block;
          background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155;
          margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;margin-bottom:6px">
            <span style="font-weight:600;color:#f8fafc;font-size:15px">{a['title']}</span>
            <span style="background:#1e293b;color:#94a3b8;padding:2px 8px;
              border-radius:10px;font-size:11px;white-space:nowrap">{a['category']}</span>
          </div>
          <div style="margin-top:4px">{tag_html}</div>
        </a>"""

    cat_filters = "".join(
        f'<a href="/?category={c}" style="background:#1e293b;color:#94a3b8;padding:4px 10px;'
        f'border-radius:6px;font-size:12px;text-decoration:none;margin:2px">{c}</a>'
        for c in categories
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>OCI Robot Cloud — Knowledge Base</title>
<style>
  body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:0;padding:24px;max-width:800px;margin:0 auto;padding:24px}}
  input{{background:#1e293b;border:1px solid #334155;color:#e2e8f0;padding:10px 14px;border-radius:8px;font-size:14px;width:100%;box-sizing:border-box}}
  input:focus{{outline:none;border-color:#3b82f6}}
</style>
</head>
<body>
<h1 style="color:#f8fafc;font-size:22px;margin-bottom:4px">Knowledge Base</h1>
<p style="color:#94a3b8;font-size:13px;margin:0 0 16px">OCI Robot Cloud design-partner documentation</p>

<form action="/" method="GET" style="margin-bottom:16px">
  <input type="text" name="q" value="{query}" placeholder="Search: DAgger, data format, API...">
</form>

<div style="margin-bottom:12px">{cat_filters}</div>
<p style="color:#64748b;font-size:12px;margin-bottom:16px">{len(articles)} articles{' matching "'+query+'"' if query else ''}</p>

{article_cards}
</body>
</html>"""


def render_article(article_id: str) -> str:
    a = next((x for x in ARTICLES if x["id"] == article_id), None)
    if not a:
        return "<h1>Article not found</h1>"

    # Simple markdown → HTML conversion
    content = a["content"]
    # Code blocks
    content = re.sub(r'```(\w*)\n(.*?)```',
                     r'<pre style="background:#0f172a;padding:12px;border-radius:6px;font-size:12px;overflow-x:auto;color:#7dd3fc"><code>\2</code></pre>',
                     content, flags=re.DOTALL)
    # Headers
    content = re.sub(r'^## (.+)$', r'<h2 style="color:#94a3b8;font-size:15px;text-transform:uppercase;letter-spacing:.05em;margin-top:20px">\1</h2>', content, flags=re.MULTILINE)
    content = re.sub(r'^### (.+)$', r'<h3 style="color:#f8fafc;font-size:14px">\1</h3>', content, flags=re.MULTILINE)
    # Bold
    content = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#f8fafc">\1</strong>', content)
    # Tables (simplified)
    content = re.sub(r'\|(.+)\|', lambda m: f'<tr>{"".join("<td style=padding:6px_10px>"+c.strip()+"</td>" for c in m.group(1).split("|") if c.strip())}</tr>', content)
    content = re.sub(r'(<tr>.*</tr>)', r'<table style="width:100%;border-collapse:collapse;margin:12px 0"><\1></table>', content, flags=re.DOTALL, count=0)
    # List items
    content = re.sub(r'^- (.+)$', r'<li style="margin:4px 0">\1</li>', content, flags=re.MULTILINE)
    # Paragraphs
    content = re.sub(r'\n\n', '</p><p style="margin:8px 0;color:#94a3b8">', content)
    content = f'<p style="margin:8px 0;color:#94a3b8">{content}</p>'

    tag_html = "".join(
        f'<span style="background:#1e293b;color:#64748b;padding:3px 8px;border-radius:4px;font-size:12px;margin:2px">{t}</span>'
        for t in a["tags"]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{a['title']} — Knowledge Base</title>
<style>
  body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:0;padding:24px;max-width:760px;margin:0 auto;padding:24px}}
  pre{{overflow-x:auto}}
  table td{{border:1px solid #334155;padding:6px 10px;font-size:13px}}
  a{{color:#3b82f6;text-decoration:none}}
</style>
</head>
<body>
<a href="/" style="color:#3b82f6;font-size:13px">← Knowledge Base</a>
<div style="margin:16px 0">
  <span style="background:#1e293b;color:#94a3b8;padding:2px 8px;border-radius:10px;font-size:11px">{a['category']}</span>
</div>
<h1 style="color:#f8fafc;font-size:22px;margin-bottom:8px">{a['title']}</h1>
<div style="margin-bottom:16px">{tag_html}</div>
<div style="line-height:1.6">{content}</div>
</body>
</html>"""


# ── FastAPI app ───────────────────────────────────────────────────────────────

def create_app() -> "FastAPI":
    app = FastAPI(title="OCI Robot Cloud Knowledge Base", version="1.0")

    @app.get("/", response_class=HTMLResponse)
    async def home(q: str = ""):
        return render_home(q)

    @app.get("/article/{article_id}", response_class=HTMLResponse)
    async def article(article_id: str):
        return render_article(article_id)

    @app.get("/api/articles")
    async def api_articles(q: str = ""):
        results = search_articles(q)
        return [{"id": a["id"], "title": a["title"],
                 "category": a["category"], "tags": a["tags"]}
                for a in results]

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "knowledge_base", "port": 8035}

    return app


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Knowledge base (port 8035)")
    parser.add_argument("--port", type=int, default=8035)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    if not HAS_FASTAPI:
        print("pip install fastapi uvicorn")
        exit(1)

    app = create_app()
    print(f"Knowledge Base → http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")

#!/usr/bin/env python3
"""
partner_support_portal.py — Design partner self-service support portal for OCI Robot Cloud.

Provides a portal at http://localhost:8039 where design partners can:
  - Search 20 FAQ entries covering common setup, training, and deployment issues
  - Submit support tickets (stored in SQLite)
  - View ticket status

Usage:
    python src/api/partner_support_portal.py
    python src/api/partner_support_portal.py --port 8039
"""

import argparse
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid

HAS_FASTAPI = False
try:
    from fastapi import FastAPI, Form, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    pass

# ── FAQ dataclass ──────────────────────────────────────────────────────────────

@dataclass
class FAQ:
    id: str
    question: str
    answer: str          # markdown
    category: str
    tags: list[str]
    views: int = 0


# ── 20 FAQ entries ─────────────────────────────────────────────────────────────

FAQS: list[FAQ] = [
    FAQ(
        id="faq-001",
        question="Why do I get 'meta/info.json not found' when loading my dataset?",
        answer=(
            "Your dataset is not in **LeRobot v2 format**. Run the conversion script:\n\n"
            "```bash\npython scripts/genesis_to_lerobot.py \\\n"
            "  --input /path/to/raw_demos \\\n"
            "  --output /tmp/lerobot_dataset\n```\n\n"
            "Then verify with `python -c \"from lerobot.common.datasets.lerobot_dataset import "
            "LeRobotDataset; ds = LeRobotDataset('/tmp/lerobot_dataset'); print(len(ds))\"`.\n\n"
            "See also: [LeRobot Dataset Format](https://github.com/huggingface/lerobot/blob/main/docs/datasets.md)."
        ),
        category="Data",
        tags=["lerobot", "dataset", "genesis", "conversion"],
    ),
    FAQ(
        id="faq-002",
        question="My closed-loop eval shows 0% success. What's wrong?",
        answer=(
            "Common causes:\n\n"
            "1. **CUDA backend not enabled** — ensure `MUJOCO_GL=egl` and that `torch.cuda.is_available()` "
            "returns `True` in the eval environment.\n"
            "2. **Wrong action dimension** — GR00T N1.6 expects **9-DOF** control "
            "(7 arm joints + 2 gripper fingers). Verify `action_space.shape == (9,)`.\n"
            "3. **Insufficient training** — BC alone often achieves only ~5% on pick-and-place. "
            "Run at least one round of **DAgger** (`python scripts/dagger_collect.py`) to improve.\n\n"
            "Run the preflight check first:\n```bash\npython scripts/eval_preflight.py\n```"
        ),
        category="Evaluation",
        tags=["closed-loop", "eval", "cuda", "dof", "dagger"],
    ),
    FAQ(
        id="faq-003",
        question="The GR00T inference server is not responding. How do I fix it?",
        answer=(
            "1. Confirm the server is running on **port 8002** (not 8001 or 8000):\n"
            "```bash\ncurl http://localhost:8002/health\n```\n"
            "2. If not running, start it:\n"
            "```bash\npython scripts/groot_franka_server.py --port 8002\n```\n"
            "3. Check GPU memory: `nvidia-smi`. GR00T N1.6 requires ~6.7 GB VRAM.\n"
            "4. Look at server logs in `/tmp/groot_server.log` for stack traces.\n\n"
            "If the server crashes on startup, verify your checkpoint path with "
            "`python scripts/eval_preflight.py --check-server`."
        ),
        category="Infrastructure",
        tags=["groot", "server", "port", "inference", "startup"],
    ),
    FAQ(
        id="faq-004",
        question="DAgger episodes are being filtered out as 'too short'. What should I check?",
        answer=(
            "Episodes shorter than **`MIN_FRAMES=10`** are automatically discarded to prevent "
            "degenerate training data.\n\n"
            "**Fix options:**\n"
            "1. Check cube spawn position — if the cube spawns outside the robot's reach, "
            "episodes end immediately. Verify `cube_x ∈ [0.45, 0.65]`, `cube_y ∈ [-0.1, 0.1]`.\n"
            "2. Increase the DAgger timeout: `--episode_timeout 30` (default 15s).\n"
            "3. Lower the filter threshold temporarily: `MIN_FRAMES=5` for debugging.\n\n"
            "Check how many episodes passed the filter:\n"
            "```bash\npython scripts/dagger_collect.py --dry_run --verbose\n```"
        ),
        category="Training",
        tags=["dagger", "episodes", "filter", "min_frames", "cube"],
    ),
    FAQ(
        id="faq-005",
        question="Inference latency is over 300ms. How do I speed it up?",
        answer=(
            "Target latency is **<227ms** on A100 (measured baseline).\n\n"
            "**Steps to reduce latency:**\n"
            "1. Check GPU load: `nvidia-smi dmon -s u`. Latency spikes when GPU utilization > 95%.\n"
            "2. Enable **FP8 quantization** on the GR00T server:\n"
            "```bash\npython scripts/groot_franka_server.py --quantize fp8\n```\n"
            "3. Ensure you are not running other heavy processes on the same GPU.\n"
            "4. Use the load tester to establish a baseline:\n"
            "```bash\npython scripts/load_test_inference.py --requests 100 --concurrency 4\n```\n\n"
            "FP8 typically reduces latency by ~30% with <1% accuracy loss."
        ),
        category="Performance",
        tags=["latency", "inference", "fp8", "quantization", "gpu"],
    ),
    FAQ(
        id="faq-006",
        question="I get CUDA out-of-memory (OOM) errors during fine-tuning. What do I do?",
        answer=(
            "**Immediate fixes:**\n"
            "1. Reduce batch size to **16** (default is 32):\n"
            "```bash\npython scripts/finetune_groot.py --batch_size 16\n```\n"
            "2. Enable **gradient checkpointing** to trade compute for memory:\n"
            "```bash\npython scripts/finetune_groot.py --gradient_checkpointing\n```\n"
            "3. Free GPU memory from other processes: `fuser -v /dev/nvidia*`\n\n"
            "**Expected VRAM usage at batch=16:** ~18 GB on A100-40GB.\n\n"
            "If OOM persists at batch=16, use `--accumulate_grad_batches 2` to simulate "
            "effective batch=32 at half the peak memory."
        ),
        category="Training",
        tags=["oom", "memory", "batch_size", "gradient_checkpointing", "finetune"],
    ),
    FAQ(
        id="faq-007",
        question="The Isaac Sim Docker container won't start. How do I debug it?",
        answer=(
            "**Common causes:**\n\n"
            "1. **Missing DISPLAY env var** — Isaac Sim requires a display (real or virtual):\n"
            "```bash\nexport DISPLAY=:0\n# or use Xvfb:\nXvfb :99 -screen 0 1280x720x24 &\nexport DISPLAY=:99\n```\n"
            "2. **Docker GPU passthrough not configured** — ensure `--gpus all` flag and that "
            "`nvidia-container-toolkit` is installed:\n"
            "```bash\ndocker run --gpus all --rm nvcr.io/nvidia/isaac-sim:latest nvidia-smi\n```\n"
            "3. **License not accepted** — set `ACCEPT_EULA=Y` in your docker run command.\n\n"
            "See `scripts/isaac_sim_preflight.sh` for a full diagnostics script."
        ),
        category="Infrastructure",
        tags=["isaac_sim", "docker", "display", "gpu", "container"],
    ),
    FAQ(
        id="faq-008",
        question="How much does it cost to fine-tune on 1000 demos?",
        answer=(
            "Use the built-in cost estimator:\n"
            "```bash\npython src/api/finetune_cost_estimator.py --demos 1000 --steps 5000\n```\n\n"
            "**Rough estimate for 5000 steps on OCI A100 ($3.06/hr, 2.35 it/s):**\n"
            "- Training time: ~35 minutes\n"
            "- Cost: **~$0.43** (at list price)\n\n"
            "Scaling table:\n"
            "| Steps | Time | Cost |\n"
            "|-------|------|------|\n"
            "| 1000  | 7 min | $0.09 |\n"
            "| 5000  | 35 min | $0.43 |\n"
            "| 20000 | 142 min | $1.71 |\n\n"
            "OCI design partners receive **free fine-tuning credits** — contact your account manager."
        ),
        category="Billing",
        tags=["cost", "pricing", "finetune", "demos", "a100"],
    ),
    FAQ(
        id="faq-009",
        question="How do I upload my own demonstration data?",
        answer=(
            "Use the **Data Collection API** on **port 8003**:\n\n"
            "**Supported formats:**\n"
            "- **HDF5** (preferred): `episode_N/observations/`, `episode_N/actions/`\n"
            "- **MP4 + JSON sidecar**: video file + `{timestamp, joints, gripper}` JSON\n\n"
            "**Upload example:**\n"
            "```bash\ncurl -X POST http://localhost:8003/upload \\\n"
            "  -F 'file=@my_demos.hdf5' \\\n"
            "  -F 'partner_id=acme-robotics' \\\n"
            "  -F 'task=pick_and_place'\n```\n\n"
            "The API validates format, counts episodes, and returns a `dataset_id` for training. "
            "See `src/api/data_collection_api.py` for full schema."
        ),
        category="Data",
        tags=["upload", "data", "hdf5", "mp4", "demos", "collection_api"],
    ),
    FAQ(
        id="faq-010",
        question="What is the difference between BC (Behavioral Cloning) and DAgger?",
        answer=(
            "| | **BC** | **DAgger** |\n"
            "|---|---|---|\n"
            "| Data source | Static offline demos | Iterative online rollouts |\n"
            "| Typical success rate | ~5% (pick-and-place) | 40–80% after 3 rounds |\n"
            "| Training time | 35 min / 5k steps | +15 min per DAgger round |\n"
            "| When to use | Quick baseline, data-rich tasks | Low success rate, distribution shift |\n\n"
            "**Rule of thumb:** Start with BC. If success < 20%, run DAgger.\n\n"
            "See the full explainer in the knowledge base: "
            "`python src/api/knowledge_base.py` → article `kb-training-bc-vs-dagger`."
        ),
        category="Training",
        tags=["bc", "dagger", "comparison", "success_rate", "knowledge_base"],
    ),
    FAQ(
        id="faq-011",
        question="How do I deploy a trained policy to a Jetson device?",
        answer=(
            "Use the Jetson deployment script:\n"
            "```bash\nbash scripts/jetson_deploy.sh \\\n"
            "  --checkpoint /tmp/groot_finetuned/checkpoint-5000 \\\n"
            "  --target jetson-orin-01.local \\\n"
            "  --quantize fp8\n```\n\n"
            "**Key requirements:**\n"
            "- Jetson AGX Orin or Orin NX (64 GB recommended)\n"
            "- JetPack 6.0+ with TensorRT 10+\n"
            "- FP8 quantization is required to hit the **<100ms latency target** on-device\n\n"
            "**Expected Jetson performance (FP8):** ~80–95ms per inference step.\n\n"
            "After deploy, run the on-device health check:\n"
            "```bash\nssh user@jetson-orin-01.local 'python3 robot_cloud_client/health_check.py'\n```"
        ),
        category="Deployment",
        tags=["jetson", "deploy", "fp8", "quantization", "edge", "latency"],
    ),
    FAQ(
        id="faq-012",
        question="How do I train a single policy for multiple robot types?",
        answer=(
            "Use the **embodiment adapter** module which adds a per-robot embedding layer:\n"
            "```bash\npython scripts/finetune_groot.py \\\n"
            "  --multi_embodiment \\\n"
            "  --embodiment_ids franka,ur5,xarm \\\n"
            "  --dataset /tmp/multi_robot_dataset\n```\n\n"
            "Each robot type gets a 64-dim learned embedding. The shared policy backbone "
            "is frozen; only adapters and the action head are trained.\n\n"
            "**Data requirement:** at least 100 demos per embodiment for good generalization.\n\n"
            "See `scripts/embodiment_adapter.py` and `scripts/multi_task_eval.py` for evaluation."
        ),
        category="Training",
        tags=["multi-robot", "embodiment", "adapter", "generalization", "ur5", "xarm"],
    ),
    FAQ(
        id="faq-013",
        question="How does curriculum learning work, and when should I use it?",
        answer=(
            "Curriculum learning progressively increases task difficulty during training. "
            "Enable it with:\n"
            "```bash\npython scripts/curriculum_sdg.py \\\n"
            "  --stages easy,medium,hard \\\n"
            "  --promotion_threshold 0.7\n```\n\n"
            "**Stage definitions (pick-and-place example):**\n"
            "- `easy`: cube at fixed position, no clutter\n"
            "- `medium`: randomized cube XY within 5cm, 1 distractor\n"
            "- `hard`: full domain randomization, 3 distractors\n\n"
            "**When to use:** curriculum training typically improves final success by "
            "10–20% compared to training on hard tasks from scratch. Recommended when "
            "your BC baseline is < 5%."
        ),
        category="Training",
        tags=["curriculum", "sdg", "domain_randomization", "stages", "difficulty"],
    ),
    FAQ(
        id="faq-014",
        question="How do I manage and restore training checkpoints?",
        answer=(
            "Checkpoints are saved every 1000 steps by default to `/tmp/groot_finetuned/`.\n\n"
            "**List checkpoints:**\n"
            "```bash\nls -lh /tmp/groot_finetuned/\n```\n\n"
            "**Resume from a checkpoint:**\n"
            "```bash\npython scripts/finetune_groot.py \\\n"
            "  --resume /tmp/groot_finetuned/checkpoint-3000\n```\n\n"
            "**Compare two checkpoints:**\n"
            "```bash\npython scripts/checkpoint_compare.py \\\n"
            "  --a checkpoint-3000 --b checkpoint-5000 \\\n"
            "  --eval_episodes 20\n```\n\n"
            "Checkpoints include: model weights, optimizer state, training step, and "
            "eval metrics. Use `scripts/model_card_generator.py` to auto-generate a "
            "model card for any checkpoint."
        ),
        category="Training",
        tags=["checkpoint", "resume", "save", "compare", "model_card"],
    ),
    FAQ(
        id="faq-015",
        question="How do I set up CI/CD for automated training and eval?",
        answer=(
            "The repo includes a GitHub Actions workflow at `.github/workflows/ci.yml`.\n\n"
            "**What the CI pipeline does:**\n"
            "1. On push to `main`: runs unit tests and a 100-step smoke fine-tune\n"
            "2. On tag `v*.*.*`: runs full 5000-step fine-tune + 20-episode eval\n"
            "3. Posts results as a PR comment with success rate and MAE\n\n"
            "**Local CI equivalent:**\n"
            "```bash\nmake ci-smoke    # fast, ~5 min\nmake ci-full     # full pipeline, ~1 hr\n```\n\n"
            "Set `OCI_ROBOT_CLOUD_API_KEY` in your repo secrets. "
            "See `Makefile` for all available targets."
        ),
        category="Infrastructure",
        tags=["ci", "cd", "github_actions", "automation", "testing", "makefile"],
    ),
    FAQ(
        id="faq-016",
        question="How do I monitor training progress in real time?",
        answer=(
            "Use the **training monitor** service:\n"
            "```bash\npython src/api/training_monitor.py --port 8010\n```\n\n"
            "Then open `http://localhost:8010` for a live dashboard showing:\n"
            "- Loss curve (updated every 10 steps via SSE)\n"
            "- GPU utilization and memory\n"
            "- Estimated time to completion\n"
            "- Step throughput (it/s)\n\n"
            "**CLI alternative:**\n"
            "```bash\npython scripts/eval_watcher.py --log /tmp/groot_finetuned/train.log\n```\n\n"
            "Training logs are also written to TensorBoard format — run "
            "`tensorboard --logdir /tmp/groot_finetuned/tensorboard`."
        ),
        category="Training",
        tags=["monitoring", "training", "dashboard", "tensorboard", "sse", "real_time"],
    ),
    FAQ(
        id="faq-017",
        question="How do I run an A/B test between two policies?",
        answer=(
            "Use the A/B testing service:\n"
            "```bash\npython src/api/ab_test.py \\\n"
            "  --policy_a checkpoint-5000 \\\n"
            "  --policy_b checkpoint-dagger-round3 \\\n"
            "  --episodes 50\n```\n\n"
            "The framework interleaves episodes between the two policies (25 each) "
            "and computes a **statistical significance test** (Mann-Whitney U).\n\n"
            "Results include: success rate, mean episode length, 95% CI, and p-value.\n\n"
            "**Rule of thumb:** n=20 per policy gives ~80% power to detect a 20pp difference; "
            "use n=50 for production decisions. "
            "See `scripts/stats_significance.py` for standalone significance tests."
        ),
        category="Evaluation",
        tags=["ab_test", "comparison", "statistics", "significance", "policy"],
    ),
    FAQ(
        id="faq-018",
        question="How do I estimate and reduce the sim-to-real gap?",
        answer=(
            "Run the sim-to-real gap analysis tool:\n"
            "```bash\npython scripts/sim_to_real_validator.py \\\n"
            "  --sim_policy checkpoint-5000 \\\n"
            "  --real_episodes /path/to/real_robot_logs\n```\n\n"
            "**Key factors that cause sim-to-real gap:**\n"
            "1. **Visual appearance** — use Isaac Sim RTX domain randomization for textures/lighting\n"
            "2. **Dynamics mismatch** — tune `joint_damping` and `friction` in the URDF\n"
            "3. **Observation noise** — add Gaussian noise to sim observations during training\n\n"
            "**Recommended pipeline:**\n"
            "Genesis SDG → Isaac Sim RTX SDG → Real robot DAgger\n\n"
            "See `scripts/domain_randomization_config.yaml` for the recommended parameter ranges."
        ),
        category="Deployment",
        tags=["sim_to_real", "domain_randomization", "gap", "real_robot", "isaac_sim"],
    ),
    FAQ(
        id="faq-019",
        question="How do I access and use the OCI Robot Cloud Python SDK?",
        answer=(
            "Install the SDK:\n"
            "```bash\npip install oci-robot-cloud\n```\n\n"
            "**Quick start:**\n"
            "```python\nfrom robot_cloud_client import RobotCloudClient\n\n"
            "client = RobotCloudClient(api_key='YOUR_KEY', endpoint='https://robot.oci.oracle.com')\n\n"
            "# Submit a training job\njob = client.submit_training(dataset_id='ds-123', steps=5000)\nprint(job.job_id)\n\n"
            "# Poll for completion\nstatus = client.get_job_status(job.job_id)\nprint(status.progress)\n```\n\n"
            "Full API reference: `python -m robot_cloud_client --help`\n\n"
            "The SDK also provides a CLI: `oci-robot-cloud train --dataset ds-123 --steps 5000`"
        ),
        category="SDK",
        tags=["sdk", "python", "cli", "api_key", "training", "client"],
    ),
    FAQ(
        id="faq-020",
        question="How do I enable the safety monitor and what does it check?",
        answer=(
            "Start the safety monitor alongside your policy server:\n"
            "```bash\npython src/api/safety_monitor.py --port 8021 --policy_port 8002\n```\n\n"
            "**Checks performed on every action (< 1ms overhead):**\n"
            "1. **Joint limits** — rejects actions outside ±2σ of training distribution\n"
            "2. **Velocity limits** — caps joint velocity at 1.5 rad/s (configurable)\n"
            "3. **Workspace bounds** — rejects end-effector positions outside defined box\n"
            "4. **Collision pre-check** — fast AABB collision check with known obstacles\n\n"
            "Violations are logged to `/tmp/safety_violations.log` and trigger an alert "
            "to the webhook configured in `src/api/webhook_notifications.py`.\n\n"
            "**Recommended for all real-robot deployments.**"
        ),
        category="Safety",
        tags=["safety", "monitor", "joint_limits", "velocity", "collision", "real_robot"],
    ),
]

# ── SQLite helpers ─────────────────────────────────────────────────────────────

DB_PATH = "/tmp/support_tickets.db"


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id          TEXT PRIMARY KEY,
                partner_email TEXT NOT NULL,
                subject     TEXT NOT NULL,
                description TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'open',
                category    TEXT NOT NULL DEFAULT 'general',
                created_at  TEXT NOT NULL,
                resolved_at TEXT,
                resolution  TEXT
            )
        """)
        conn.commit()


def submit_ticket(partner_email: str, subject: str, description: str, category: str) -> str:
    """Insert a new support ticket. Returns the new ticket ID."""
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    created_at = datetime.now(timezone.utc).isoformat()
    with _get_db() as conn:
        conn.execute(
            "INSERT INTO tickets (id, partner_email, subject, description, status, category, created_at) "
            "VALUES (?, ?, ?, ?, 'open', ?, ?)",
            (ticket_id, partner_email, subject, description, category, created_at),
        )
        conn.commit()
    return ticket_id


def resolve_ticket(ticket_id: str, resolution: str) -> bool:
    """Mark a ticket as resolved. Returns True if the ticket was found and updated."""
    resolved_at = datetime.now(timezone.utc).isoformat()
    with _get_db() as conn:
        cur = conn.execute(
            "UPDATE tickets SET status='resolved', resolved_at=?, resolution=? WHERE id=?",
            (resolved_at, resolution, ticket_id),
        )
        conn.commit()
        return cur.rowcount > 0


def _get_all_tickets() -> list[dict]:
    with _get_db() as conn:
        rows = conn.execute("SELECT * FROM tickets ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


# ── FastAPI app ────────────────────────────────────────────────────────────────

if HAS_FASTAPI:
    app = FastAPI(title="OCI Robot Cloud Partner Support Portal", version="1.0.0")
    _init_db()

    # ── HTML portal ───────────────────────────────────────────────────────────

    def _build_faq_items_html() -> str:
        items = []
        for faq in FAQS:
            tags_html = " ".join(f'<span class="tag">{t}</span>' for t in faq.tags)
            items.append(f"""
            <div class="faq-item" data-id="{faq.id}"
                 data-text="{faq.question.lower()} {' '.join(faq.tags)}">
              <button class="faq-question" onclick="toggleFaq(this)">
                <span class="category-badge">{faq.category}</span>
                {faq.question}
                <span class="chevron">▼</span>
              </button>
              <div class="faq-answer">
                <div class="answer-body">{faq.answer}</div>
                <div class="faq-tags">{tags_html}</div>
              </div>
            </div>""")
        return "\n".join(items)

    @app.get("/", response_class=HTMLResponse)
    async def portal_home():
        faq_items = _build_faq_items_html()
        tickets = _get_all_tickets()
        ticket_rows = "".join(
            f"<tr><td>{t['id']}</td><td>{t['partner_email']}</td><td>{t['subject']}</td>"
            f"<td><span class='status-{t['status']}'>{t['status']}</span></td>"
            f"<td>{t['created_at'][:10]}</td></tr>"
            for t in tickets[:20]
        )
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OCI Robot Cloud — Partner Support Portal</title>
  <style>
    :root {{
      --bg: #0f1117; --surface: #1a1d27; --border: #2d3148;
      --accent: #6366f1; --accent2: #a78bfa; --text: #e2e8f0;
      --muted: #94a3b8; --success: #34d399; --warn: #fbbf24;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; }}
    header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 16px 32px;
              display: flex; align-items: center; gap: 16px; }}
    header h1 {{ font-size: 1.25rem; font-weight: 700; color: var(--accent2); }}
    header p {{ color: var(--muted); font-size: 0.85rem; }}
    .badge {{ background: var(--accent); color: white; font-size: 0.7rem; padding: 2px 8px;
              border-radius: 12px; font-weight: 600; }}
    main {{ max-width: 960px; margin: 0 auto; padding: 32px 16px; }}
    section {{ margin-bottom: 40px; }}
    h2 {{ font-size: 1.1rem; font-weight: 600; color: var(--accent2); margin-bottom: 16px;
          border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
    #search-box {{ width: 100%; padding: 12px 16px; border-radius: 8px;
                   background: var(--surface); border: 1px solid var(--border);
                   color: var(--text); font-size: 1rem; outline: none; }}
    #search-box:focus {{ border-color: var(--accent); }}
    #faq-count {{ color: var(--muted); font-size: 0.85rem; margin-top: 8px; }}
    .faq-item {{ background: var(--surface); border: 1px solid var(--border);
                 border-radius: 8px; margin-bottom: 8px; overflow: hidden; }}
    .faq-question {{ width: 100%; background: none; border: none; color: var(--text);
                     padding: 14px 16px; text-align: left; cursor: pointer; font-size: 0.95rem;
                     display: flex; align-items: center; gap: 10px; }}
    .faq-question:hover {{ background: rgba(99,102,241,0.08); }}
    .chevron {{ margin-left: auto; transition: transform 0.2s; color: var(--muted); }}
    .faq-question.open .chevron {{ transform: rotate(180deg); }}
    .faq-answer {{ display: none; padding: 0 16px 16px; border-top: 1px solid var(--border);
                   font-size: 0.9rem; line-height: 1.7; color: var(--muted); }}
    .faq-answer.visible {{ display: block; }}
    .answer-body {{ white-space: pre-wrap; margin-top: 12px; }}
    .faq-tags {{ margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }}
    .tag {{ background: rgba(99,102,241,0.15); color: var(--accent2); font-size: 0.75rem;
            padding: 2px 8px; border-radius: 4px; }}
    .category-badge {{ background: rgba(167,139,250,0.15); color: var(--accent2); font-size: 0.72rem;
                       padding: 2px 8px; border-radius: 4px; white-space: nowrap; }}
    .ticket-btn {{ display: inline-block; margin-top: 8px; padding: 10px 24px;
                   background: var(--accent); color: white; border-radius: 8px;
                   text-decoration: none; font-weight: 600; cursor: pointer;
                   border: none; font-size: 0.95rem; }}
    .ticket-btn:hover {{ background: var(--accent2); color: var(--bg); }}
    form {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
             padding: 24px; display: grid; gap: 14px; max-width: 600px; }}
    label {{ font-size: 0.85rem; color: var(--muted); }}
    input, textarea, select {{ width: 100%; padding: 10px 12px; background: var(--bg);
                               border: 1px solid var(--border); border-radius: 6px;
                               color: var(--text); font-size: 0.9rem; outline: none; }}
    input:focus, textarea:focus, select:focus {{ border-color: var(--accent); }}
    textarea {{ min-height: 100px; resize: vertical; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    th {{ background: var(--surface); color: var(--muted); padding: 8px 12px;
          text-align: left; border-bottom: 1px solid var(--border); }}
    td {{ padding: 8px 12px; border-bottom: 1px solid var(--border); color: var(--text); }}
    .status-open {{ color: var(--warn); }}
    .status-resolved {{ color: var(--success); }}
    #no-results {{ display: none; color: var(--muted); padding: 20px; text-align: center; }}
  </style>
</head>
<body>
<header>
  <div>
    <h1>OCI Robot Cloud</h1>
    <p>Design Partner Support Portal</p>
  </div>
  <span class="badge">port 8039</span>
</header>
<main>
  <section>
    <h2>Frequently Asked Questions</h2>
    <input id="search-box" type="text" placeholder="Search FAQs — e.g. 'OOM', 'latency', 'DAgger'..."
           oninput="filterFaqs(this.value)">
    <p id="faq-count">Showing {len(FAQS)} of {len(FAQS)} articles</p>
    <div id="faq-list">
      {faq_items}
    </div>
    <div id="no-results">No FAQs match your search. Consider submitting a ticket below.</div>
  </section>

  <section>
    <h2>Submit a Support Ticket</h2>
    <form method="POST" action="/ticket">
      <div><label>Partner Email</label><input name="email" type="email" required placeholder="you@yourcompany.com"></div>
      <div><label>Subject</label><input name="subject" required placeholder="Brief description of the issue"></div>
      <div><label>Category</label>
        <select name="category">
          <option>Data</option><option>Training</option><option>Evaluation</option>
          <option>Infrastructure</option><option>Performance</option><option>Deployment</option>
          <option>Billing</option><option>SDK</option><option>Safety</option><option>Other</option>
        </select>
      </div>
      <div><label>Description</label><textarea name="description" required placeholder="Steps to reproduce, error messages, environment details..."></textarea></div>
      <button type="submit" class="ticket-btn">Submit Ticket</button>
    </form>
  </section>

  <section>
    <h2>Recent Tickets (Admin)</h2>
    <table>
      <thead><tr><th>ID</th><th>Email</th><th>Subject</th><th>Status</th><th>Created</th></tr></thead>
      <tbody>{ticket_rows if ticket_rows else '<tr><td colspan="5" style="color:var(--muted);text-align:center">No tickets yet</td></tr>'}</tbody>
    </table>
  </section>
</main>
<script>
function filterFaqs(q) {{
  const term = q.toLowerCase().trim();
  const items = document.querySelectorAll('.faq-item');
  let visible = 0;
  items.forEach(item => {{
    const match = !term || item.dataset.text.includes(term);
    item.style.display = match ? '' : 'none';
    if (match) visible++;
  }});
  document.getElementById('faq-count').textContent =
    `Showing ${{visible}} of {len(FAQS)} articles`;
  document.getElementById('no-results').style.display = visible === 0 ? 'block' : 'none';
}}
function toggleFaq(btn) {{
  btn.classList.toggle('open');
  const ans = btn.nextElementSibling;
  ans.classList.toggle('visible');
}}
</script>
</body>
</html>"""
        return html

    # ── Ticket form submission ─────────────────────────────────────────────────

    @app.post("/ticket", response_class=HTMLResponse)
    async def post_ticket(
        email: str = Form(...),
        subject: str = Form(...),
        description: str = Form(...),
        category: str = Form("Other"),
    ):
        ticket_id = submit_ticket(email, subject, description, category)
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Ticket Submitted</title>
<style>
  body{{background:#0f1117;color:#e2e8f0;font-family:system-ui,sans-serif;
        display:flex;align-items:center;justify-content:center;min-height:100vh;}}
  .card{{background:#1a1d27;border:1px solid #2d3148;border-radius:12px;
         padding:40px;max-width:480px;text-align:center;}}
  h2{{color:#34d399;margin-bottom:12px;}}
  .tid{{background:#0f1117;border:1px solid #2d3148;border-radius:6px;
        padding:8px 20px;font-family:monospace;font-size:1.1rem;color:#a78bfa;
        display:inline-block;margin:12px 0;}}
  a{{color:#6366f1;text-decoration:none;}}
</style></head><body>
<div class="card">
  <h2>Ticket Submitted</h2>
  <p>Your support ticket has been received. The OCI Robot Cloud team will respond within 1 business day.</p>
  <div class="tid">{ticket_id}</div>
  <p>Reference this ID in any follow-up communications.</p>
  <p style="margin-top:24px"><a href="/">← Back to portal</a></p>
</div></body></html>"""
        return html

    # ── API endpoints ──────────────────────────────────────────────────────────

    @app.get("/api/faq")
    async def api_faq(q: Optional[str] = None):
        results = FAQS
        if q:
            term = q.lower()
            results = [
                f for f in FAQS
                if term in f.question.lower()
                or term in f.answer.lower()
                or any(term in t for t in f.tags)
                or term in f.category.lower()
            ]
        return JSONResponse([
            {
                "id": f.id,
                "question": f.question,
                "answer": f.answer,
                "category": f.category,
                "tags": f.tags,
                "views": f.views,
            }
            for f in results
        ])

    @app.get("/api/tickets")
    async def api_tickets():
        return JSONResponse(_get_all_tickets())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "partner_support_portal", "port": 8039}


# ── Entrypoint ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not HAS_FASTAPI:
        print("Missing dependencies. Install with:\n  pip install fastapi uvicorn")
        raise SystemExit(1)

    parser = argparse.ArgumentParser(description="OCI Robot Cloud Partner Support Portal")
    parser.add_argument("--port", type=int, default=8039, help="Port to listen on (default: 8039)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    args = parser.parse_args()

    print(f"OCI Robot Cloud Partner Support Portal")
    print(f"  URL   : http://localhost:{args.port}")
    print(f"  FAQs  : {len(FAQS)} entries")
    print(f"  DB    : {DB_PATH}")
    print()

    uvicorn.run(
        "partner_support_portal:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )

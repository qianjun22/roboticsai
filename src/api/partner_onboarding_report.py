#!/usr/bin/env python3
"""
partner_onboarding_report.py — Welcome/onboarding report for OCI Robot Cloud design partners.

Generates a rich HTML report (dark theme) + JSON summary covering:
  • Partner profile and tier badge
  • 15-item onboarding checklist with progress bar
  • GR00T fine-tune configuration recommendation
  • 3-month cost forecast (SVG chart)
  • 7-step quickstart guide with code snippets
  • Support contact info

Usage:
    python src/api/partner_onboarding_report.py --mock
    python src/api/partner_onboarding_report.py --mock --partner "Apptronik" \\
        --output /tmp/partner_onboarding_report.html --seed 42
    python src/api/partner_onboarding_report.py --mock --partner "Figure" \\
        --output /tmp/partner_onboarding_report.html --json-output /tmp/report.json

5 simulated partners:
    Apptronik  (Apollo)          — enterprise, manipulation
    Figure     (Figure 02)       — enterprise, loco-manipulation
    Agility    (Cassie)          — growth, locomotion
    BostonDynamics (Spot)        — growth, inspection
    CustomArm  (custom arm)      — pilot, assembly
"""

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Optional, Dict, Any


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ChecklistItem:
    label: str
    done: bool
    category: str  # "access" | "sdk" | "data" | "training" | "integration"
    description: str = ""


@dataclass
class GR00TConfig:
    lora_rank: int
    batch_size: int
    learning_rate: float
    n_steps: int
    estimated_cost_usd: float
    estimated_time_hours: float
    expected_mae: float
    gpu_type: str
    n_gpus: int
    embodiment: str


@dataclass
class MonthCostForecast:
    month: int          # 1, 2, 3
    n_demos: int
    n_finetune_jobs: int
    compute_usd: float
    storage_usd: float
    inference_usd: float
    total_usd: float


@dataclass
class PartnerProfile:
    name: str
    tier: str           # "pilot" | "growth" | "enterprise"
    robot_type: str
    task: str
    n_demos_available: int
    contact_email: str
    onboarding_start: str
    account_manager: str
    checklist: List[ChecklistItem] = field(default_factory=list)
    groot_config: Optional[GR00TConfig] = None
    cost_forecast: List[MonthCostForecast] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Mock data factory
# ---------------------------------------------------------------------------

PARTNERS_META = {
    "apptronik": {
        "name": "Apptronik",
        "tier": "enterprise",
        "robot_type": "Apptronik Apollo",
        "task": "bimanual_manipulation",
        "n_demos_available": 1200,
        "contact_email": "robotics@apptronik.com",
        "account_manager": "Sarah Chen",
        "checklist_progress": 11,   # number of items done out of 15
    },
    "figure": {
        "name": "Figure",
        "tier": "enterprise",
        "robot_type": "Figure 02",
        "task": "loco_manipulation",
        "n_demos_available": 950,
        "contact_email": "partners@figure.ai",
        "account_manager": "Sarah Chen",
        "checklist_progress": 9,
    },
    "agility": {
        "name": "Agility Robotics",
        "tier": "growth",
        "robot_type": "Agility Cassie",
        "task": "bipedal_locomotion",
        "n_demos_available": 400,
        "contact_email": "ops@agilityrobotics.com",
        "account_manager": "Marcus Lee",
        "checklist_progress": 7,
    },
    "bostondynamics": {
        "name": "Boston Dynamics",
        "tier": "growth",
        "robot_type": "Boston Dynamics Spot",
        "task": "inspection_navigation",
        "n_demos_available": 300,
        "contact_email": "cloud@bostondynamics.com",
        "account_manager": "Marcus Lee",
        "checklist_progress": 5,
    },
    "customarm": {
        "name": "CustomArm Robotics",
        "tier": "pilot",
        "robot_type": "Custom 6-DOF Arm",
        "task": "precision_assembly",
        "n_demos_available": 120,
        "contact_email": "team@customarm.io",
        "account_manager": "Dev Support",
        "checklist_progress": 3,
    },
}

CHECKLIST_TEMPLATE = [
    ChecklistItem("API key provisioned",           True,  "access",      "Your API key has been generated and is ready to use."),
    ChecklistItem("OCI tenancy access granted",    True,  "access",      "IAM policies applied; GPU shapes available in your tenancy."),
    ChecklistItem("SDK installed (oci-robot-cloud)", False, "sdk",         "Run: pip install oci-robot-cloud"),
    ChecklistItem("API key configured in SDK",     False, "sdk",          "Set OCI_ROBOT_CLOUD_API_KEY env var or ~/.ocirc"),
    ChecklistItem("Health check passed",           False, "sdk",          "Run: oci-robot-cloud health --endpoint https://api.ocirobotcloud.com"),
    ChecklistItem("First demo dataset uploaded",   False, "data",         "Upload via SDK: client.upload_demos('/path/to/demos')"),
    ChecklistItem("Demo validation report reviewed", False, "data",       "Inspect frame counts, action dimensions, and quality score."),
    ChecklistItem("Baseline eval launched",        False, "training",     "Evaluate GR00T N1.6 zero-shot on your task before fine-tuning."),
    ChecklistItem("Baseline eval report reviewed", False, "training",     "Note baseline MAE — your fine-tune will improve on this number."),
    ChecklistItem("First fine-tune job launched",  False, "training",     "Submit via: client.finetune(config=recommended_config)"),
    ChecklistItem("Fine-tune eval complete",       False, "training",     "Compare MAE vs baseline; target ≥50% improvement."),
    ChecklistItem("Model deployed to staging",     False, "integration",  "Deploy the fine-tuned checkpoint to a staging inference endpoint."),
    ChecklistItem("Inference latency validated",   False, "integration",  "Target: <250 ms end-to-end on A100 at 6 Hz control loop."),
    ChecklistItem("Webhook notifications configured", False, "integration","Set up job-complete and alert webhooks for your CI/CD pipeline."),
    ChecklistItem("Production deployment approved", False, "integration",  "Receive sign-off from your account manager for production rollout."),
]


# GR00T config lookup by task type
GROOT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "bimanual_manipulation": dict(
        lora_rank=16, batch_size=32, learning_rate=1e-4, n_steps=2000,
        estimated_cost_usd=86.40, estimated_time_hours=4.2,
        expected_mae=0.018, gpu_type="A100 80GB", n_gpus=4,
    ),
    "loco_manipulation": dict(
        lora_rank=16, batch_size=32, learning_rate=8e-5, n_steps=2000,
        estimated_cost_usd=86.40, estimated_time_hours=4.2,
        expected_mae=0.021, gpu_type="A100 80GB", n_gpus=4,
    ),
    "bipedal_locomotion": dict(
        lora_rank=8, batch_size=16, learning_rate=5e-5, n_steps=1500,
        estimated_cost_usd=43.20, estimated_time_hours=2.8,
        expected_mae=0.031, gpu_type="A100 80GB", n_gpus=2,
    ),
    "inspection_navigation": dict(
        lora_rank=8, batch_size=16, learning_rate=5e-5, n_steps=1000,
        estimated_cost_usd=21.60, estimated_time_hours=1.6,
        expected_mae=0.041, gpu_type="A100 80GB", n_gpus=2,
    ),
    "precision_assembly": dict(
        lora_rank=4, batch_size=8, learning_rate=2e-5, n_steps=1000,
        estimated_cost_usd=10.80, estimated_time_hours=1.2,
        expected_mae=0.055, gpu_type="A100 80GB", n_gpus=1,
    ),
}

# Tier multiplier for demo volume growth per month
TIER_DEMO_GROWTH = {
    "pilot": 1.10,
    "growth": 1.25,
    "enterprise": 1.40,
}

TIER_MONTHLY_BASE_COMPUTE = {
    "pilot":      45.0,
    "growth":    180.0,
    "enterprise": 720.0,
}


def _build_checklist(n_done: int) -> List[ChecklistItem]:
    items = []
    for i, tmpl in enumerate(CHECKLIST_TEMPLATE):
        items.append(ChecklistItem(
            label=tmpl.label,
            done=(i < n_done),
            category=tmpl.category,
            description=tmpl.description,
        ))
    return items


def _build_groot_config(task: str, robot_type: str) -> GR00TConfig:
    cfg = GROOT_CONFIGS.get(task, GROOT_CONFIGS["precision_assembly"])
    # Infer embodiment tag from robot type
    robot_lower = robot_type.lower()
    if "apollo" in robot_lower or "figure" in robot_lower:
        embodiment = "humanoid_bimanual"
    elif "cassie" in robot_lower:
        embodiment = "bipedal_legged"
    elif "spot" in robot_lower:
        embodiment = "quadruped"
    else:
        embodiment = "single_arm"
    return GR00TConfig(
        lora_rank=cfg["lora_rank"],
        batch_size=cfg["batch_size"],
        learning_rate=cfg["learning_rate"],
        n_steps=cfg["n_steps"],
        estimated_cost_usd=cfg["estimated_cost_usd"],
        estimated_time_hours=cfg["estimated_time_hours"],
        expected_mae=cfg["expected_mae"],
        gpu_type=cfg["gpu_type"],
        n_gpus=cfg["n_gpus"],
        embodiment=embodiment,
    )


def _build_cost_forecast(
    tier: str, n_demos: int, task: str
) -> List[MonthCostForecast]:
    base_compute = TIER_MONTHLY_BASE_COMPUTE[tier]
    growth = TIER_DEMO_GROWTH[tier]
    forecasts = []
    current_demos = n_demos
    for month in range(1, 4):
        jobs = max(1, current_demos // 200)
        compute = base_compute * (growth ** (month - 1))
        storage = current_demos * 0.012        # ~$0.012 per demo stored
        inference = compute * 0.15
        total = compute + storage + inference
        forecasts.append(MonthCostForecast(
            month=month,
            n_demos=int(current_demos),
            n_finetune_jobs=jobs,
            compute_usd=round(compute, 2),
            storage_usd=round(storage, 2),
            inference_usd=round(inference, 2),
            total_usd=round(total, 2),
        ))
        current_demos = int(current_demos * growth)
    return forecasts


def build_partner(key: str, rng: random.Random) -> PartnerProfile:
    meta = PARTNERS_META[key]
    n_done = meta["checklist_progress"]
    task = meta["task"]
    return PartnerProfile(
        name=meta["name"],
        tier=meta["tier"],
        robot_type=meta["robot_type"],
        task=task,
        n_demos_available=meta["n_demos_available"],
        contact_email=meta["contact_email"],
        onboarding_start=str(date.today()),
        account_manager=meta["account_manager"],
        checklist=_build_checklist(n_done),
        groot_config=_build_groot_config(task, meta["robot_type"]),
        cost_forecast=_build_cost_forecast(
            meta["tier"], meta["n_demos_available"], task
        ),
    )


def build_all_partners(rng: random.Random) -> List[PartnerProfile]:
    return [build_partner(k, rng) for k in PARTNERS_META]


def find_partner_by_name(partners: List[PartnerProfile], name: str) -> Optional[PartnerProfile]:
    nl = name.strip().lower()
    for p in partners:
        if nl in p.name.lower():
            return p
    return None


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

TIER_COLOR = {
    "pilot":      "\033[36m",    # cyan
    "growth":     "\033[33m",    # yellow
    "enterprise": "\033[35m",    # magenta
}
RESET = "\033[0m"
GREEN = "\033[32m"
RED   = "\033[31m"
BOLD  = "\033[1m"

CAT_ICON = {
    "access":      "🔑",
    "sdk":         "📦",
    "data":        "📊",
    "training":    "🤖",
    "integration": "🔗",
}


def print_partner_report(p: PartnerProfile):
    tier_col = TIER_COLOR.get(p.tier, "")
    done_count = sum(1 for c in p.checklist if c.done)
    total = len(p.checklist)
    pct = done_count * 100 // total

    print()
    print(f"{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}  OCI Robot Cloud — Partner Onboarding Report{RESET}")
    print(f"  {BOLD}{p.name}{RESET}  [{tier_col}{p.tier.upper()}{RESET}]  |  {p.robot_type}  |  {p.task}")
    print(f"  Demos available: {p.n_demos_available}    Started: {p.onboarding_start}")
    print(f"  Account manager: {p.account_manager}   Contact: {p.contact_email}")
    print(f"{'='*70}")

    # Checklist
    print(f"\n{BOLD}Onboarding Checklist  ({done_count}/{total} complete — {pct}%){RESET}")
    bar_filled = pct * 40 // 100
    bar = f"[{'#'*bar_filled}{'.'*(40-bar_filled)}] {pct}%"
    print(f"  {bar}")
    print()
    for item in p.checklist:
        icon = CAT_ICON.get(item.category, "•")
        if item.done:
            marker = f"{GREEN}[✓]{RESET}"
        else:
            marker = f"{RED}[ ]{RESET}"
        print(f"  {marker} {icon}  {item.label}")

    # GR00T config
    cfg = p.groot_config
    print(f"\n{BOLD}Recommended GR00T Fine-Tune Configuration{RESET}")
    print(f"  Embodiment:     {cfg.embodiment}")
    print(f"  LoRA rank:      {cfg.lora_rank}")
    print(f"  Batch size:     {cfg.batch_size}")
    print(f"  Learning rate:  {cfg.learning_rate:.1e}")
    print(f"  Steps:          {cfg.n_steps}")
    print(f"  Hardware:       {cfg.n_gpus}× {cfg.gpu_type}")
    print(f"  Est. cost:      ${cfg.estimated_cost_usd:.2f}")
    print(f"  Est. time:      {cfg.estimated_time_hours:.1f}h")
    print(f"  Expected MAE:   {cfg.expected_mae:.3f}")

    # Cost forecast
    print(f"\n{BOLD}3-Month Cost Forecast{RESET}")
    print(f"  {'Month':<8} {'Demos':<8} {'Jobs':<6} {'Compute':>10} {'Storage':>10} {'Inference':>10} {'Total':>10}")
    print(f"  {'-'*66}")
    for fc in p.cost_forecast:
        print(
            f"  {f'Month {fc.month}':<8} {fc.n_demos:<8} {fc.n_finetune_jobs:<6}"
            f" ${fc.compute_usd:>9.2f} ${fc.storage_usd:>9.2f}"
            f" ${fc.inference_usd:>9.2f} ${fc.total_usd:>9.2f}"
        )
    print()


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def partner_to_dict(p: PartnerProfile) -> Dict[str, Any]:
    return {
        "partner": {
            "name": p.name,
            "tier": p.tier,
            "robot_type": p.robot_type,
            "task": p.task,
            "n_demos_available": p.n_demos_available,
            "contact_email": p.contact_email,
            "onboarding_start": p.onboarding_start,
            "account_manager": p.account_manager,
        },
        "checklist": {
            "items": [
                {
                    "label": c.label,
                    "done": c.done,
                    "category": c.category,
                    "description": c.description,
                }
                for c in p.checklist
            ],
            "done_count": sum(1 for c in p.checklist if c.done),
            "total": len(p.checklist),
            "pct_complete": sum(1 for c in p.checklist if c.done) * 100 // len(p.checklist),
        },
        "groot_config": {
            "embodiment": p.groot_config.embodiment,
            "lora_rank": p.groot_config.lora_rank,
            "batch_size": p.groot_config.batch_size,
            "learning_rate": p.groot_config.learning_rate,
            "n_steps": p.groot_config.n_steps,
            "gpu_type": p.groot_config.gpu_type,
            "n_gpus": p.groot_config.n_gpus,
            "estimated_cost_usd": p.groot_config.estimated_cost_usd,
            "estimated_time_hours": p.groot_config.estimated_time_hours,
            "expected_mae": p.groot_config.expected_mae,
        },
        "cost_forecast": [
            {
                "month": fc.month,
                "n_demos": fc.n_demos,
                "n_finetune_jobs": fc.n_finetune_jobs,
                "compute_usd": fc.compute_usd,
                "storage_usd": fc.storage_usd,
                "inference_usd": fc.inference_usd,
                "total_usd": fc.total_usd,
            }
            for fc in p.cost_forecast
        ],
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

TIER_BADGE_CSS = {
    "pilot":      "background:#0e7490;color:#cffafe",
    "growth":     "background:#92400e;color:#fef3c7",
    "enterprise": "background:#5b21b6;color:#ede9fe",
}

CAT_ICON_HTML = {
    "access":      "&#x1F511;",
    "sdk":         "&#x1F4E6;",
    "data":        "&#x1F4CA;",
    "training":    "&#x1F916;",
    "integration": "&#x1F517;",
}

QUICKSTART_STEPS = [
    {
        "title": "Install the SDK",
        "description": "Install the OCI Robot Cloud SDK from PyPI. Python 3.10+ required.",
        "code": "pip install oci-robot-cloud",
        "lang": "bash",
    },
    {
        "title": "Configure your API key",
        "description": "Set your API key as an environment variable or in ~/.ocirc.",
        "code": (
            "# Option A — environment variable\n"
            "export OCI_ROBOT_CLOUD_API_KEY='your-api-key-here'\n\n"
            "# Option B — config file (~/.ocirc)\n"
            "[robot-cloud]\n"
            "api_key = your-api-key-here\n"
            "endpoint = https://api.ocirobotcloud.com"
        ),
        "lang": "bash",
    },
    {
        "title": "Verify connectivity",
        "description": "Run a health check to confirm your credentials and network access.",
        "code": (
            "from oci_robot_cloud import RobotCloudClient\n\n"
            "client = RobotCloudClient()\n"
            "status = client.health()\n"
            'print(status)  # {"status": "ok", "version": "1.4.2"}'
        ),
        "lang": "python",
    },
    {
        "title": "Upload your demo dataset",
        "description": (
            "Upload HDF5 or LeRobot v2 demos. The SDK validates frame counts, "
            "action dimensions, and generates a quality report."
        ),
        "code": (
            "upload = client.upload_demos(\n"
            "    path='/path/to/demos/',\n"
            "    robot_type='your-robot-type',\n"
            "    task='your-task-name',\n"
            ")\n"
            "print(upload.dataset_id)   # e.g. ds_abc123\n"
            "print(upload.quality_score) # 0.0 – 1.0"
        ),
        "lang": "python",
    },
    {
        "title": "Launch your first fine-tune job",
        "description": (
            "Submit a fine-tune job using the recommended configuration from your "
            "onboarding report. The job runs on OCI GPU instances and streams "
            "live loss metrics."
        ),
        "code": (
            "job = client.finetune(\n"
            "    dataset_id=upload.dataset_id,\n"
            "    config={\n"
            '        "lora_rank": 16,\n'
            '        "batch_size": 32,\n'
            '        "learning_rate": 1e-4,\n'
            '        "n_steps": 2000,\n'
            "    }\n"
            ")\n"
            "print(job.job_id)    # e.g. job_xyz789\n"
            "job.wait()           # blocks until complete\n"
            "print(job.result.mae)  # e.g. 0.018"
        ),
        "lang": "python",
    },
    {
        "title": "Evaluate and compare",
        "description": (
            "Run closed-loop evaluation against your task and compare MAE to the "
            "GR00T N1.6 zero-shot baseline."
        ),
        "code": (
            "eval_result = client.eval(\n"
            "    job_id=job.job_id,\n"
            "    n_episodes=20,\n"
            "    task='your-task-name',\n"
            ")\n"
            "print(eval_result.success_rate)  # e.g. 0.75\n"
            "print(eval_result.mae)           # e.g. 0.018\n"
            "print(eval_result.vs_baseline)   # e.g. '+62% vs zero-shot'"
        ),
        "lang": "python",
    },
    {
        "title": "Deploy to production",
        "description": (
            "Deploy your fine-tuned checkpoint to a managed inference endpoint "
            "with autoscaling and <250 ms latency SLA."
        ),
        "code": (
            "endpoint = client.deploy(\n"
            "    job_id=job.job_id,\n"
            "    instance_type='BM.GPU.A100-v2.8',\n"
            "    autoscale_min=1,\n"
            "    autoscale_max=4,\n"
            ")\n"
            "print(endpoint.url)    # https://infer.ocirobotcloud.com/e/...\n"
            "print(endpoint.latency_p50_ms)  # e.g. 212"
        ),
        "lang": "python",
    },
]


def _svg_cost_chart(forecasts: List[MonthCostForecast]) -> str:
    """Return an inline SVG bar chart for the 3-month cost forecast."""
    W, H = 520, 220
    pad_left, pad_top, pad_bottom, pad_right = 70, 20, 50, 20
    chart_w = W - pad_left - pad_right
    chart_h = H - pad_top - pad_bottom

    max_total = max(fc.total_usd for fc in forecasts) * 1.15 or 1.0
    bar_group_w = chart_w / len(forecasts)
    bar_w = bar_group_w * 0.22

    colors = {"compute": "#6366f1", "storage": "#10b981", "inference": "#f59e0b"}

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;font-family:monospace">',
    ]

    # Y-axis grid lines + labels
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        y = pad_top + chart_h - int(frac * chart_h)
        val = max_total * frac
        lines.append(
            f'<line x1="{pad_left}" y1="{y}" x2="{W-pad_right}" y2="{y}" '
            f'stroke="#334155" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{pad_left-6}" y="{y+4}" text-anchor="end" '
            f'fill="#94a3b8" font-size="10">${val:.0f}</text>'
        )

    # Bars (stacked)
    for i, fc in enumerate(forecasts):
        cx = pad_left + i * bar_group_w + bar_group_w / 2
        segments = [
            ("compute",   fc.compute_usd),
            ("storage",   fc.storage_usd),
            ("inference", fc.inference_usd),
        ]
        y_cursor = pad_top + chart_h
        for seg_name, seg_val in segments:
            seg_h = max(1, int((seg_val / max_total) * chart_h))
            bx = cx - (1.5 * bar_w)
            by = y_cursor - seg_h
            lines.append(
                f'<rect x="{bx:.1f}" y="{by}" width="{bar_w*3:.1f}" height="{seg_h}" '
                f'fill="{colors[seg_name]}" rx="2"/>'
            )
            y_cursor = by

        # Total label on top
        total_y = y_cursor - 4
        lines.append(
            f'<text x="{cx:.1f}" y="{total_y}" text-anchor="middle" '
            f'fill="#e2e8f0" font-size="10">${fc.total_usd:.0f}</text>'
        )
        # X-axis label
        xlabel_y = pad_top + chart_h + 18
        lines.append(
            f'<text x="{cx:.1f}" y="{xlabel_y}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="11">Month {fc.month}</text>'
        )
        # Demo count sub-label
        lines.append(
            f'<text x="{cx:.1f}" y="{xlabel_y+13}" text-anchor="middle" '
            f'fill="#64748b" font-size="9">{fc.n_demos} demos</text>'
        )

    # Legend
    lx = pad_left + 4
    ly = pad_top + chart_h + 36
    for j, (seg_name, col) in enumerate(colors.items()):
        lx2 = lx + j * 130
        lines.append(
            f'<rect x="{lx2}" y="{ly-8}" width="12" height="10" fill="{col}" rx="2"/>'
        )
        lines.append(
            f'<text x="{lx2+16}" y="{ly}" fill="#94a3b8" font-size="10">'
            f'{seg_name.capitalize()}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def _checklist_section(p: PartnerProfile) -> str:
    done_count = sum(1 for c in p.checklist if c.done)
    total = len(p.checklist)
    pct = done_count * 100 // total

    cat_labels = {
        "access": "Access & Credentials",
        "sdk": "SDK Setup",
        "data": "Data Ingestion",
        "training": "Model Training",
        "integration": "Integration & Deployment",
    }
    cat_order = ["access", "sdk", "data", "training", "integration"]

    # group items by category
    groups: Dict[str, List[ChecklistItem]] = {c: [] for c in cat_order}
    for item in p.checklist:
        groups[item.category].append(item)

    rows = []
    for cat in cat_order:
        items = groups[cat]
        if not items:
            continue
        icon_html = CAT_ICON_HTML.get(cat, "&#x25CF;")
        rows.append(
            f'<tr><td colspan="2" style="padding:10px 12px 4px;'
            f'color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:0.08em">'
            f'{icon_html} {cat_labels.get(cat, cat)}</td></tr>'
        )
        for item in items:
            if item.done:
                check = '<span style="color:#10b981;font-weight:bold">&#x2713;</span>'
                row_cls = "color:#d1fae5"
            else:
                check = '<span style="color:#475569">&#x25A1;</span>'
                row_cls = "color:#94a3b8"
            rows.append(
                f'<tr style="{row_cls}">'
                f'<td style="padding:5px 12px;width:28px;text-align:center">{check}</td>'
                f'<td style="padding:5px 12px">'
                f'<span style="font-size:13px">{item.label}</span>'
                + (
                    f'<br><span style="font-size:11px;color:#64748b">{item.description}</span>'
                    if item.description else ""
                )
                + "</td></tr>"
            )

    table_html = (
        '<table style="width:100%;border-collapse:collapse">'
        + "".join(rows)
        + "</table>"
    )

    bar_html = (
        f'<div style="background:#1e293b;border-radius:6px;height:14px;overflow:hidden;margin-bottom:16px">'
        f'<div style="background:linear-gradient(90deg,#6366f1,#10b981);'
        f'width:{pct}%;height:100%;border-radius:6px;transition:width 0.4s"></div>'
        f'</div>'
        f'<div style="text-align:right;font-size:12px;color:#94a3b8;margin-top:-12px;margin-bottom:16px">'
        f'{done_count}/{total} complete &mdash; {pct}%</div>'
    )

    return bar_html + table_html


def _config_card(cfg: GR00TConfig) -> str:
    rows = [
        ("Embodiment", cfg.embodiment),
        ("LoRA rank", str(cfg.lora_rank)),
        ("Batch size", str(cfg.batch_size)),
        ("Learning rate", f"{cfg.learning_rate:.1e}"),
        ("Training steps", f"{cfg.n_steps:,}"),
        ("Hardware", f"{cfg.n_gpus}&times; {cfg.gpu_type}"),
    ]
    right_rows = [
        ("Estimated cost", f"<strong style='color:#f59e0b'>${cfg.estimated_cost_usd:.2f}</strong>"),
        ("Estimated time", f"<strong style='color:#6366f1'>{cfg.estimated_time_hours:.1f} h</strong>"),
        ("Expected MAE", f"<strong style='color:#10b981'>{cfg.expected_mae:.3f}</strong>"),
    ]

    def make_row(k, v):
        return (
            f'<tr><td style="padding:7px 16px;color:#94a3b8;font-size:12px;'
            f'white-space:nowrap;width:50%">{k}</td>'
            f'<td style="padding:7px 16px;color:#e2e8f0;font-size:13px">{v}</td></tr>'
        )

    left_html = (
        '<table style="width:100%;border-collapse:collapse">'
        + "".join(make_row(k, v) for k, v in rows)
        + "</table>"
    )
    right_html = (
        '<table style="width:100%;border-collapse:collapse">'
        + "".join(make_row(k, v) for k, v in right_rows)
        + "</table>"
    )

    return (
        '<div style="display:flex;gap:16px;flex-wrap:wrap">'
        f'<div style="flex:1;min-width:220px;background:#1e293b;border-radius:8px;'
        f'border:1px solid #334155">{left_html}</div>'
        f'<div style="flex:1;min-width:180px;background:#1e293b;border-radius:8px;'
        f'border:1px solid #334155">{right_html}</div>'
        f'</div>'
    )


def _quickstart_section() -> str:
    steps_html = []
    for i, step in enumerate(QUICKSTART_STEPS, 1):
        code_escaped = (
            step["code"]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        steps_html.append(
            f'<div style="margin-bottom:28px">'
            f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">'
            f'<div style="background:#6366f1;color:#fff;border-radius:50%;'
            f'width:28px;height:28px;display:flex;align-items:center;justify-content:center;'
            f'font-size:13px;font-weight:bold;flex-shrink:0">{i}</div>'
            f'<span style="color:#e2e8f0;font-size:15px;font-weight:600">{step["title"]}</span>'
            f'</div>'
            f'<p style="color:#94a3b8;font-size:13px;margin:0 0 10px 40px">{step["description"]}</p>'
            f'<pre style="background:#0f172a;border:1px solid #334155;border-radius:6px;'
            f'padding:14px;margin:0 0 0 40px;overflow-x:auto;font-size:12px;'
            f'color:#a5f3fc;line-height:1.6">{code_escaped}</pre>'
            f'</div>'
        )
    return "".join(steps_html)


def generate_html(p: PartnerProfile, all_partners: List[PartnerProfile]) -> str:
    done_count = sum(1 for c in p.checklist if c.done)
    total = len(p.checklist)
    pct = done_count * 100 // total
    tier_badge_style = TIER_BADGE_CSS.get(p.tier, "background:#334155;color:#e2e8f0")
    svg_chart = _svg_cost_chart(p.cost_forecast)
    checklist_html = _checklist_section(p)
    config_html = _config_card(p.groot_config)
    quickstart_html = _quickstart_section()

    # Summary cards for all partners (mini)
    mini_cards = []
    for op in all_partners:
        op_done = sum(1 for c in op.checklist if c.done)
        op_pct = op_done * 100 // len(op.checklist)
        active_style = (
            "border:1px solid #6366f1" if op.name == p.name
            else "border:1px solid #334155"
        )
        op_badge = TIER_BADGE_CSS.get(op.tier, "")
        mini_cards.append(
            f'<div style="background:#1e293b;{active_style};border-radius:8px;'
            f'padding:12px 14px;min-width:160px">'
            f'<div style="font-size:13px;font-weight:600;color:#e2e8f0;margin-bottom:4px">'
            f'{op.name}</div>'
            f'<span style="font-size:10px;padding:2px 7px;border-radius:10px;{op_badge}">'
            f'{op.tier}</span>'
            f'<div style="margin-top:8px;background:#0f172a;border-radius:4px;'
            f'height:6px;overflow:hidden">'
            f'<div style="background:#6366f1;width:{op_pct}%;height:100%"></div></div>'
            f'<div style="font-size:10px;color:#64748b;margin-top:3px">{op_pct}% complete</div>'
            f'</div>'
        )
    mini_cards_html = "".join(mini_cards)

    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OCI Robot Cloud — {p.name} Onboarding Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    line-height: 1.6;
  }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 32px 20px; }}
  .section {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
  }}
  .section-title {{
    font-size: 16px;
    font-weight: 700;
    color: #f1f5f9;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 1px solid #334155;
  }}
  .banner {{
    background: linear-gradient(135deg, #1e3a5f 0%, #1e293b 60%, #2d1b69 100%);
    border: 1px solid #3730a3;
    border-radius: 12px;
    padding: 32px;
    margin-bottom: 24px;
  }}
  .banner h1 {{ font-size: 26px; font-weight: 800; color: #f1f5f9; margin-bottom: 6px; }}
  .banner .subtitle {{ font-size: 14px; color: #94a3b8; margin-top: 10px; }}
  .badge {{
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 3px 10px;
    border-radius: 10px;
    vertical-align: middle;
    margin-left: 10px;
  }}
  .meta-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 10px;
    margin-top: 16px;
  }}
  .meta-item {{ background: #0f172a; border-radius: 8px; padding: 10px 14px; }}
  .meta-label {{ font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.07em; }}
  .meta-value {{ font-size: 14px; color: #e2e8f0; font-weight: 600; margin-top: 2px; }}
  .partner-grid {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 24px;
  }}
  .support-grid {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .support-card {{
    flex: 1;
    min-width: 200px;
    background: #0f172a;
    border-radius: 8px;
    padding: 14px 16px;
    border: 1px solid #334155;
  }}
  .support-card .label {{ font-size: 11px; color: #64748b; text-transform: uppercase; }}
  .support-card .value {{ font-size: 13px; color: #a5f3fc; margin-top: 4px; }}
  .footer {{
    text-align: center;
    font-size: 11px;
    color: #475569;
    margin-top: 32px;
    padding-top: 20px;
    border-top: 1px solid #1e293b;
  }}
</style>
</head>
<body>
<div class="container">

  <!-- Welcome banner -->
  <div class="banner">
    <div style="display:flex;align-items:center;flex-wrap:wrap;gap:10px">
      <div>
        <h1>Welcome, {p.name}
          <span class="badge" style="{tier_badge_style}">{p.tier}</span>
        </h1>
        <div style="font-size:15px;color:#cbd5e1;margin-top:6px">
          OCI Robot Cloud Design Partner Onboarding Report
        </div>
      </div>
      <div style="margin-left:auto;text-align:right">
        <div style="font-size:28px;font-weight:800;color:#6366f1">{pct}%</div>
        <div style="font-size:11px;color:#64748b">onboarding complete</div>
      </div>
    </div>
    <div class="meta-grid">
      <div class="meta-item">
        <div class="meta-label">Robot</div>
        <div class="meta-value">{p.robot_type}</div>
      </div>
      <div class="meta-item">
        <div class="meta-label">Task</div>
        <div class="meta-value">{p.task.replace("_", " ").title()}</div>
      </div>
      <div class="meta-item">
        <div class="meta-label">Demos Available</div>
        <div class="meta-value">{p.n_demos_available:,}</div>
      </div>
      <div class="meta-item">
        <div class="meta-label">Started</div>
        <div class="meta-value">{p.onboarding_start}</div>
      </div>
      <div class="meta-item">
        <div class="meta-label">Account Manager</div>
        <div class="meta-value">{p.account_manager}</div>
      </div>
      <div class="meta-item">
        <div class="meta-label">Contact</div>
        <div class="meta-value" style="font-size:12px">{p.contact_email}</div>
      </div>
    </div>
  </div>

  <!-- All partners summary -->
  <div style="margin-bottom:24px">
    <div style="font-size:12px;color:#64748b;margin-bottom:10px;text-transform:uppercase;
      letter-spacing:0.07em">Design Partner Cohort</div>
    <div class="partner-grid">
      {mini_cards_html}
    </div>
  </div>

  <!-- Onboarding checklist -->
  <div class="section">
    <div class="section-title">&#x2705; Onboarding Checklist</div>
    {checklist_html}
  </div>

  <!-- GR00T config -->
  <div class="section">
    <div class="section-title">&#x1F916; Recommended GR00T Fine-Tune Configuration</div>
    <p style="font-size:13px;color:#94a3b8;margin-bottom:16px">
      Based on your robot type ({p.robot_type}) and task ({p.task.replace("_", " ")}),
      we recommend the following configuration for your first fine-tuning job.
      This is calibrated to the OCI A100 cluster for optimal cost/performance.
    </p>
    {config_html}
  </div>

  <!-- 3-month cost forecast -->
  <div class="section">
    <div class="section-title">&#x1F4B0; 3-Month Cost Forecast</div>
    <p style="font-size:13px;color:#94a3b8;margin-bottom:16px">
      Projected spend based on your current demo volume ({p.n_demos_available:,} demos)
      and expected growth for the <strong style="color:#e2e8f0">{p.tier}</strong> tier.
      Includes compute, storage, and inference charges.
    </p>
    <div style="overflow-x:auto">{svg_chart}</div>
    <table style="width:100%;border-collapse:collapse;margin-top:16px;font-size:12px">
      <thead>
        <tr style="color:#64748b;border-bottom:1px solid #334155">
          <th style="padding:8px 12px;text-align:left">Month</th>
          <th style="padding:8px 12px;text-align:right">Demos</th>
          <th style="padding:8px 12px;text-align:right">Jobs</th>
          <th style="padding:8px 12px;text-align:right">Compute</th>
          <th style="padding:8px 12px;text-align:right">Storage</th>
          <th style="padding:8px 12px;text-align:right">Inference</th>
          <th style="padding:8px 12px;text-align:right;color:#f59e0b">Total</th>
        </tr>
      </thead>
      <tbody>
        {"".join(
            f'<tr style="border-bottom:1px solid #1e293b">'
            f'<td style="padding:8px 12px;color:#94a3b8">Month {fc.month}</td>'
            f'<td style="padding:8px 12px;text-align:right">{fc.n_demos:,}</td>'
            f'<td style="padding:8px 12px;text-align:right">{fc.n_finetune_jobs}</td>'
            f'<td style="padding:8px 12px;text-align:right">${fc.compute_usd:.2f}</td>'
            f'<td style="padding:8px 12px;text-align:right">${fc.storage_usd:.2f}</td>'
            f'<td style="padding:8px 12px;text-align:right">${fc.inference_usd:.2f}</td>'
            f'<td style="padding:8px 12px;text-align:right;font-weight:700;color:#f59e0b">'
            f'${fc.total_usd:.2f}</td></tr>'
            for fc in p.cost_forecast
        )}
      </tbody>
    </table>
  </div>

  <!-- Quickstart guide -->
  <div class="section">
    <div class="section-title">&#x26A1; 7-Step Quickstart Guide</div>
    <p style="font-size:13px;color:#94a3b8;margin-bottom:20px">
      Follow these steps to go from API key to production deployment.
      Copy-pasteable code snippets are provided for each step.
    </p>
    {quickstart_html}
  </div>

  <!-- Support -->
  <div class="section">
    <div class="section-title">&#x1F4DE; Support &amp; Resources</div>
    <div class="support-grid">
      <div class="support-card">
        <div class="label">Account Manager</div>
        <div class="value">{p.account_manager}</div>
      </div>
      <div class="support-card">
        <div class="label">Partner Email</div>
        <div class="value">{p.contact_email}</div>
      </div>
      <div class="support-card">
        <div class="label">Slack Channel</div>
        <div class="value">#oci-robot-cloud-partners</div>
      </div>
      <div class="support-card">
        <div class="label">Documentation</div>
        <div class="value">docs.ocirobotcloud.com</div>
      </div>
      <div class="support-card">
        <div class="label">Status Page</div>
        <div class="value">status.ocirobotcloud.com</div>
      </div>
      <div class="support-card">
        <div class="label">Support Ticket</div>
        <div class="value">support.oracle.com</div>
      </div>
    </div>
  </div>

  <div class="footer">
    OCI Robot Cloud — Confidential Partner Report &nbsp;&bull;&nbsp;
    Generated {generated_at} &nbsp;&bull;&nbsp;
    &copy; 2026 Oracle Corporation
  </div>

</div>
</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate OCI Robot Cloud partner onboarding report"
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="Use simulated partner data (required for standalone use)"
    )
    parser.add_argument(
        "--partner", default="Apptronik",
        metavar="NAME",
        help='Partner name to feature (default: Apptronik). '
             'Choices: Apptronik, Figure, Agility, BostonDynamics, CustomArm'
    )
    parser.add_argument(
        "--output", default="/tmp/partner_onboarding_report.html",
        metavar="PATH",
        help="Path for HTML output (default: /tmp/partner_onboarding_report.html)"
    )
    parser.add_argument(
        "--json-output", default=None,
        metavar="PATH",
        help="Path for JSON output (optional)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--list-partners", action="store_true",
        help="List available mock partners and exit"
    )
    args = parser.parse_args()

    if args.list_partners:
        print("Available mock partners:")
        for meta in PARTNERS_META.values():
            print(f"  {meta['name']:<22} [{meta['tier']:<10}]  {meta['robot_type']}")
        return

    if not args.mock:
        print(
            "ERROR: only --mock mode is supported in this script.\n"
            "Pass --mock to generate a report with simulated data.",
            file=sys.stderr,
        )
        sys.exit(1)

    rng = random.Random(args.seed)
    all_partners = build_all_partners(rng)

    partner = find_partner_by_name(all_partners, args.partner)
    if partner is None:
        print(
            f"ERROR: partner '{args.partner}' not found. "
            f"Available: {[p.name for p in all_partners]}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Console output
    print_partner_report(partner)

    # HTML output
    html = generate_html(partner, all_partners)
    from pathlib import Path
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"HTML report written to: {out_path}")

    # JSON output
    if args.json_output:
        data = partner_to_dict(partner)
        json_path = Path(args.json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"JSON output written to: {json_path}")
    else:
        # Always print a condensed JSON summary to stdout
        data = partner_to_dict(partner)
        summary = {
            "partner": data["partner"],
            "checklist": {
                "done_count": data["checklist"]["done_count"],
                "total": data["checklist"]["total"],
                "pct_complete": data["checklist"]["pct_complete"],
            },
            "groot_config": data["groot_config"],
            "cost_forecast_totals": [
                {"month": fc["month"], "total_usd": fc["total_usd"]}
                for fc in data["cost_forecast"]
            ],
            "generated_at": data["generated_at"],
        }
        print("\nJSON Summary:")
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

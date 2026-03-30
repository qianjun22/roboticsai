#!/usr/bin/env python3
"""
customer_onboarding_wizard.py -- OCI Robot Cloud design partner onboarding wizard.

Guides new robotics startups through the 7-step onboarding process:
account setup, robot config, demo upload, test inference, fine-tuning, eval, and go-live.

Usage:
    python customer_onboarding_wizard.py --mock --output /tmp/customer_onboarding_wizard.html
"""

import argparse
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional


@dataclass
class OnboardingStep:
    step_id: int
    name: str
    description: str
    estimated_time_min: int
    required: bool
    checklist: List[str]
    docs_link: str
    status: str = "pending"  # pending / in_progress / complete / blocked
    completion_pct: float = 0.0
    notes: str = ""


@dataclass
class PartnerOnboarding:
    partner_id: str
    company: str
    robot_type: str
    contact: str
    started_at: str
    current_step: int
    overall_pct: float
    steps: List[OnboardingStep] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)


@dataclass
class OnboardingReport:
    generated_at: str
    partners: List[PartnerOnboarding] = field(default_factory=list)


STEPS_TEMPLATE = [
    OnboardingStep(
        step_id=1, name="OCI Account Setup",
        description="Provision OCI tenancy, create IAM policies, and configure GPU quota for A100 GPU4.",
        estimated_time_min=30, required=True,
        checklist=[
            "OCI tenancy created",
            "IAM policy: allow OCI Robot Cloud access",
            "A100 GPU4 quota approved (contact OCI support)",
            "SSH key uploaded to bastion host",
            "VCN + security list configured (ports 8001-8020)",
        ],
        docs_link="https://docs.oracle.com/en-us/iaas/Content/GSG/Tasks/signingup.htm",
    ),
    OnboardingStep(
        step_id=2, name="Robot Configuration",
        description="Register your robot embodiment (URDF, DOF, gripper type) for GR00T policy adaptation.",
        estimated_time_min=20, required=True,
        checklist=[
            "URDF file uploaded to /data/robot_config/",
            "Joint limits verified (7-DOF or 6-DOF)",
            "End-effector type selected (parallel / suction / dexterous)",
            "Camera calibration file uploaded (intrinsics JSON)",
            "Robot registered via: python sdk/robot_registry.py --register",
        ],
        docs_link="https://github.com/qianjun22/roboticsai/blob/main/docs/robot_config.md",
    ),
    OnboardingStep(
        step_id=3, name="Demo Data Upload",
        description="Upload minimum 50 teleoperation demonstrations in LeRobot HDF5 format.",
        estimated_time_min=60, required=True,
        checklist=[
            "Demos in LeRobot HDF5 format (v2.0)",
            "Minimum 50 episodes (1000+ recommended)",
            "Episode length 50-500 frames (filter short eps)",
            "Upload via: python sdk/upload_demos.py --path /your/demos/",
            "Validate: python src/training/data_validator.py --dataset /data/demos/",
        ],
        docs_link="https://github.com/qianjun22/roboticsai/blob/main/docs/demo_format.md",
    ),
    OnboardingStep(
        step_id=4, name="Test Inference",
        description="Run a test inference call to verify GR00T N1.6 is responding on port 8001.",
        estimated_time_min=10, required=True,
        checklist=[
            "SSH tunnel: ssh -L 8001:localhost:8001 ubuntu@138.1.153.110",
            "Health check: curl http://localhost:8001/health",
            "Test inference: python sdk/test_inference.py --mock-image",
            "Verify latency < 500ms (target: 226ms)",
            "Check GPU util > 50% during inference",
        ],
        docs_link="https://github.com/qianjun22/roboticsai/blob/main/docs/inference_quickstart.md",
    ),
    OnboardingStep(
        step_id=5, name="Fine-Tuning Run",
        description="Launch first fine-tuning job on your uploaded demos using GR00T LoRA.",
        estimated_time_min=120, required=True,
        checklist=[
            "Select fine-tune config: configs/finetune_lora_r16.yaml",
            "Launch: python src/training/gr00t_finetune.py --config configs/finetune_lora_r16.yaml",
            "Monitor: python src/infra/training_pipeline_monitor.py (port 8075)",
            "Expected: 2.35 it/s, ~87% GPU util, loss < 0.15 after 1000 steps",
            "Checkpoint saved to /data/checkpoints/",
        ],
        docs_link="https://github.com/qianjun22/roboticsai/blob/main/docs/finetuning.md",
    ),
    OnboardingStep(
        step_id=6, name="Policy Evaluation",
        description="Run closed-loop eval in LIBERO simulation to measure success rate.",
        estimated_time_min=45, required=True,
        checklist=[
            "Install LIBERO: pip install libero",
            "Run eval: python src/eval/closed_loop_eval.py --checkpoint /data/checkpoints/latest",
            "Target: >40% SR after 1000-demo fine-tune (baseline: 5%)",
            "Review eval report: /tmp/closed_loop_eval.html",
            "Optional: python src/eval/policy_overfitting_detector.py for generalization check",
        ],
        docs_link="https://github.com/qianjun22/roboticsai/blob/main/docs/evaluation.md",
    ),
    OnboardingStep(
        step_id=7, name="Go-Live Checklist",
        description="Final checks before deploying to production robot hardware.",
        estimated_time_min=30, required=True,
        checklist=[
            "Safety monitor running: python src/eval/safety_monitor.py (port 8010)",
            "Policy canary test passed (src/eval/deployment_canary_reporter.py)",
            "Robot joint limits verified (src/eval/joint_limit_stress_tester.py)",
            "Data collection API live (port 8003) for online DAgger",
            "Slack/email alerting configured for rollback triggers",
            "OCI Robot Cloud team notified (Slack: #oci-robot-cloud-partners)",
        ],
        docs_link="https://github.com/qianjun22/roboticsai/blob/main/docs/go_live.md",
    ),
]


def simulate_partner_onboarding(cfg: dict, rng: random.Random) -> PartnerOnboarding:
    import copy
    steps = copy.deepcopy(STEPS_TEMPLATE)
    current_step = cfg["current_step"]

    for s in steps:
        if s.step_id < current_step:
            s.status = "complete"
            s.completion_pct = 100.0
        elif s.step_id == current_step:
            s.status = cfg.get("current_status", "in_progress")
            s.completion_pct = cfg.get("current_pct", 60.0)
            s.notes = cfg.get("current_notes", "")
        else:
            s.status = "pending"
            s.completion_pct = 0.0

    completed = sum(1 for s in steps if s.status == "complete")
    in_prog_pct = next((s.completion_pct for s in steps if s.status == "in_progress"), 0.0)
    overall = (completed * 100 + in_prog_pct) / len(steps)

    return PartnerOnboarding(
        partner_id=cfg["partner_id"],
        company=cfg["company"],
        robot_type=cfg["robot_type"],
        contact=cfg["contact"],
        started_at=cfg["started_at"],
        current_step=current_step,
        overall_pct=round(overall, 1),
        steps=steps,
        blockers=cfg.get("blockers", []),
    )


def simulate_onboarding(seed: int = 42) -> OnboardingReport:
    rng = random.Random(seed)
    partners_cfg = [
        {"partner_id": "apptronik", "company": "Apptronik", "robot_type": "Humanoid (Apollo)",
         "contact": "eng@apptronik.com", "started_at": "2026-03-10",
         "current_step": 5, "current_status": "in_progress", "current_pct": 70.0,
         "current_notes": "Fine-tune running, 3000/5000 steps",
         "blockers": ["Need Isaac Sim tutorial for humanoid URDF"]},
        {"partner_id": "skild_ai", "company": "Skild AI", "robot_type": "6-DOF Manipulation Arm",
         "contact": "research@skild.ai", "started_at": "2026-03-15",
         "current_step": 6, "current_status": "in_progress", "current_pct": 40.0,
         "current_notes": "Eval running in LIBERO, SR ~0.48 so far",
         "blockers": []},
        {"partner_id": "pi", "company": "Physical Intelligence", "robot_type": "Tabletop Manipulation",
         "contact": "cloud@physicalintelligence.ai", "started_at": "2026-03-25",
         "current_step": 3, "current_status": "in_progress", "current_pct": 20.0,
         "current_notes": "Uploading first batch of 50 demos",
         "blockers": ["CUDA OOM on A100 40GB -- upgrading to 80GB", "Waiting for NVIDIA co-engineering intro"]},
        {"partner_id": "covariant", "company": "Covariant", "robot_type": "Warehouse Pick-and-Place",
         "contact": "infra@covariant.ai", "started_at": "2026-02-20",
         "current_step": 7, "current_status": "complete", "current_pct": 100.0,
         "current_notes": "SR=0.82, deployed to 3 warehouse robots",
         "blockers": []},
        {"partner_id": "1x", "company": "1X Technologies", "robot_type": "Bipedal Robot (NEO)",
         "contact": "ml@1x.tech", "started_at": "2026-03-18",
         "current_step": 4, "current_status": "in_progress", "current_pct": 80.0,
         "current_notes": "Test inference passing, latency 231ms",
         "blockers": ["Need Isaac Sim bipedal locomotion support"]},
    ]
    partners = [simulate_partner_onboarding(cfg, rng) for cfg in partners_cfg]
    return OnboardingReport(generated_at=time.strftime("%Y-%m-%d %H:%M:%S"), partners=partners)


def _progress_bar(pct: float, width: int = 200, height: int = 10) -> str:
    fill = pct / 100 * width
    color = "#22c55e" if pct >= 100 else "#C74634" if pct >= 70 else "#f59e0b"
    return (f'<svg width="{width}" height="{height}" style="vertical-align:middle">'
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="#334155" rx="4"/>'
            f'<rect x="0" y="0" width="{fill:.1f}" height="{height}" fill="{color}" rx="4"/>'
            f'</svg>')


def render_html(report: OnboardingReport) -> str:
    status_color = {"complete": "#22c55e", "in_progress": "#f59e0b", "pending": "#475569", "blocked": "#ef4444"}
    status_bg = {"complete": "#14532d", "in_progress": "#451a03", "pending": "#1e293b", "blocked": "#7f1d1d"}

    partners_html = ""
    for p in report.partners:
        blockers_html = "".join(f'<li style="color:#fca5a5;font-size:11px">{b}</li>' for b in p.blockers) if p.blockers else "<li style='color:#4ade80;font-size:11px'>No blockers</li>"
        steps_html = ""
        for s in p.steps:
            sc = status_color.get(s.status, "#94a3b8")
            sb = status_bg.get(s.status, "#1e293b")
            checklist_html = "".join(
                f'<li style="font-size:11px;color:#94a3b8;margin-bottom:2px">{item}</li>'
                for item in s.checklist
            )
            steps_html += f"""
  <div style="display:flex;gap:12px;margin-bottom:10px;align-items:flex-start">
    <div style="background:{sb};color:{sc};border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;flex-shrink:0">{s.step_id}</div>
    <div style="flex:1">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="color:#e2e8f0;font-weight:600;font-size:13px">{s.name}</span>
        <span style="background:{sb};color:{sc};padding:2px 8px;border-radius:10px;font-size:10px;font-weight:bold">{s.status.upper().replace('_',' ')}</span>
      </div>
      <div style="color:#64748b;font-size:11px;margin-top:2px">{s.description}</div>
      {(f'<div style="margin-top:4px">{_progress_bar(s.completion_pct,150,6)} <span style="color:#94a3b8;font-size:10px">{s.completion_pct:.0f}%</span></div>') if s.status != 'pending' else ''}
      {(f'<div style="color:#f59e0b;font-size:10px;margin-top:3px">{s.notes}</div>') if s.notes else ''}
      <ul style="padding-left:14px;margin-top:4px">{checklist_html}</ul>
    </div>
  </div>"""

        partners_html += f"""
<div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:20px;margin-bottom:24px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <div><span style="color:#C74634;font-weight:bold;font-size:16px">{p.company}</span>
    <span style="color:#64748b;font-size:12px;margin-left:12px">{p.robot_type} &middot; {p.contact} &middot; started {p.started_at}</span></div>
    <div style="text-align:right">
      {_progress_bar(p.overall_pct)}
      <div style="color:#94a3b8;font-size:11px;margin-top:2px">{p.overall_pct:.0f}% complete &middot; Step {p.current_step}/7</div>
    </div>
  </div>
  <div style="margin-bottom:12px"><strong style="color:#ef4444;font-size:12px">Blockers:</strong><ul style="padding-left:14px;margin-top:4px">{blockers_html}</ul></div>
  <div>{steps_html}</div>
</div>"""

    total = len(report.partners)
    complete = sum(1 for p in report.partners if p.overall_pct >= 100)
    avg_pct = sum(p.overall_pct for p in report.partners) / total if total else 0
    total_blockers = sum(len(p.blockers) for p in report.partners)

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Customer Onboarding Wizard</title>
<style>body{{background:#1e293b;color:#e2e8f0;font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:22px}}h2{{color:#C74634;font-size:15px;margin:20px 0 10px 0;border-bottom:1px solid #334155;padding-bottom:6px}}
.kv{{display:inline-flex;flex-direction:column;background:#0f172a;border-radius:6px;padding:10px 18px;margin:0 8px 10px 0;min-width:120px}}
.kv-l{{color:#64748b;font-size:10px;text-transform:uppercase}}.kv-v{{color:#C74634;font-size:22px;font-weight:bold;margin-top:2px}}</style></head>
<body><h1>OCI Robot Cloud &mdash; Design Partner Onboarding</h1>
<div style="color:#94a3b8;font-size:12px;margin-bottom:20px">Generated {report.generated_at} &middot; {total} design partners</div>
<div style="margin-bottom:20px">
  <div class="kv"><span class="kv-l">Total Partners</span><span class="kv-v">{total}</span></div>
  <div class="kv"><span class="kv-l">Go-Live Complete</span><span class="kv-v" style="color:#22c55e">{complete}</span></div>
  <div class="kv"><span class="kv-l">Avg Progress</span><span class="kv-v">{avg_pct:.0f}%</span></div>
  <div class="kv"><span class="kv-l">Active Blockers</span><span class="kv-v" style="color:#ef4444">{total_blockers}</span></div>
</div>
<h2>Partner Onboarding Status</h2>{partners_html}
<div style="margin-top:24px;padding:14px;background:#0f172a;border-radius:8px;font-size:12px;color:#94a3b8">
  <strong style="color:#C74634">OCI Robot Cloud</strong> &mdash; Design Partner Program &middot; 5 NVIDIA-referred robotics startups &middot; GitHub: qianjun22/roboticsai
</div></body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Customer onboarding wizard for OCI Robot Cloud")
    parser.add_argument("--mock", action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/customer_onboarding_wizard.html")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    report = simulate_onboarding(seed=args.seed)
    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"[onboarding] Report saved to {args.output}")
    for p in report.partners:
        print(f"  {p.company}: {p.overall_pct:.0f}% (step {p.current_step}/7)  blockers={len(p.blockers)}")


if __name__ == "__main__":
    main()

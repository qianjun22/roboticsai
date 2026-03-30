"""augmentation_scheduler.py
Schedules and manages data augmentation jobs for GR00T N1.6 fine-tuning pipeline diversity.
Usage: python augmentation_scheduler.py
Saves report to /tmp/augmentation_scheduler.html
"""
from __future__ import annotations
import math, random, uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np

AUG_STRATEGIES: Dict[str, Dict] = {
    "color_jitter":       {"aug_factor": 2, "diversity_gain": 0.08, "cost_per_ep": 0.0012},
    "joint_noise":        {"aug_factor": 3, "diversity_gain": 0.12, "cost_per_ep": 0.0008},
    "temporal_jitter":    {"aug_factor": 2, "diversity_gain": 0.09, "cost_per_ep": 0.0015},
    "camera_viewpoint":   {"aug_factor": 4, "diversity_gain": 0.18, "cost_per_ep": 0.0025},
    "lighting_randomize": {"aug_factor": 3, "diversity_gain": 0.15, "cost_per_ep": 0.0018},
    "combined_visual":    {"aug_factor": 5, "diversity_gain": 0.22, "cost_per_ep": 0.0031},
    "combined_full":      {"aug_factor": 8, "diversity_gain": 0.31, "cost_per_ep": 0.0048},
    "domain_rand":        {"aug_factor": 6, "diversity_gain": 0.27, "cost_per_ep": 0.0038},
}
BASE_DATASETS: Dict[str, int] = {"bc_500": 500, "dagger_run9_99eps": 99, "sdg_1000": 1000}
STRATEGY_COLORS: Dict[str, str] = {
    "color_jitter": "#4A90D9", "joint_noise": "#7ED321", "temporal_jitter": "#F5A623",
    "camera_viewpoint": "#D0021B", "lighting_randomize": "#9B59B6",
    "combined_visual": "#1ABC9C", "combined_full": "#E74C3C", "domain_rand": "#F39C12",
}

@dataclass
class AugmentationJob:
    job_id: str; source_dataset: str; aug_strategy: str; n_source_episodes: int
    n_augmented_episodes: int; aug_factor: int; target_diversity_score: float
    scheduled_at: datetime; status: str; cost_usd: float

@dataclass
class AugSchedule:
    schedule_id: str; jobs: List[AugmentationJob]; created_at: datetime
    total_source_eps: int; total_augmented_eps: int; total_cost_usd: float

def generate_aug_schedule(target_diversity: float = 0.85, budget_usd: float = 20.0, seed: int = 42) -> AugSchedule:
    rng = random.Random(seed); np.random.seed(seed)
    strategy_efficiency = sorted(AUG_STRATEGIES.items(), key=lambda kv: kv[1]["diversity_gain"] / kv[1]["cost_per_ep"], reverse=True)
    jobs: List[AugmentationJob] = []; remaining_budget = budget_usd; cumulative_diversity = 0.0
    base_scheduled_at = datetime(2026, 3, 30, 8, 0, 0); offset_minutes = 0
    for pass_num in range(3):
        for dataset_name, n_source in BASE_DATASETS.items():
            if cumulative_diversity >= target_diversity or remaining_budget <= 0: break
            chosen_strategy = None
            for strat_name, strat_cfg in strategy_efficiency:
                job_cost = strat_cfg["cost_per_ep"] * n_source * strat_cfg["aug_factor"]
                if job_cost <= remaining_budget: chosen_strategy = (strat_name, strat_cfg); break
            if chosen_strategy is None:
                cheapest = min(AUG_STRATEGIES.items(), key=lambda kv: kv[1]["cost_per_ep"])
                strat_name, strat_cfg = cheapest
                job_cost = strat_cfg["cost_per_ep"] * n_source * strat_cfg["aug_factor"]
                if job_cost > remaining_budget: continue
                chosen_strategy = (strat_name, strat_cfg)
            strat_name, strat_cfg = chosen_strategy
            aug_factor = strat_cfg["aug_factor"]; n_augmented = n_source * aug_factor
            job_cost = strat_cfg["cost_per_ep"] * n_source * aug_factor
            raw_gain = strat_cfg["diversity_gain"]
            effective_gain = raw_gain * (1.0 - math.tanh(cumulative_diversity * 1.5))
            target_div = min(1.0, cumulative_diversity + effective_gain)
            job = AugmentationJob(
                job_id=f"aug_{uuid.UUID(int=rng.getrandbits(128)).hex[:8]}",
                source_dataset=dataset_name, aug_strategy=strat_name,
                n_source_episodes=n_source, n_augmented_episodes=n_augmented,
                aug_factor=aug_factor, target_diversity_score=round(target_div, 4),
                scheduled_at=base_scheduled_at + timedelta(minutes=offset_minutes),
                status="pending", cost_usd=round(job_cost, 4),
            )
            jobs.append(job); cumulative_diversity = target_div
            remaining_budget -= job_cost; offset_minutes += rng.randint(5, 20)
        if cumulative_diversity >= target_diversity or len(jobs) >= 8: break
    schedule_id = f"sched_{uuid.UUID(int=rng.getrandbits(128)).hex[:8]}"
    return AugSchedule(schedule_id=schedule_id, jobs=jobs, created_at=datetime(2026, 3, 30, 7, 55, 0),
        total_source_eps=sum(j.n_source_episodes for j in jobs),
        total_augmented_eps=sum(j.n_augmented_episodes for j in jobs),
        total_cost_usd=round(sum(j.cost_usd for j in jobs), 4))

def simulate_augmentation(schedule: AugSchedule) -> List[dict]:
    rng = np.random.default_rng(seed=99); results = []; cumulative_diversity = 0.0
    for job in schedule.jobs:
        strat_cfg = AUG_STRATEGIES[job.aug_strategy]; raw_gain = strat_cfg["diversity_gain"]
        noise = rng.normal(0.0, 0.15 * raw_gain)
        effective_gain = max(0.0, raw_gain + noise) * (1.0 - math.tanh(cumulative_diversity * 1.5))
        actual_diversity = min(1.0, cumulative_diversity + effective_gain)
        duration_s = job.n_augmented_episodes * 0.05 * rng.uniform(0.9, 1.1)
        status = "complete" if rng.random() > 0.02 else "failed"
        results.append({"job_id": job.job_id, "source_dataset": job.source_dataset,
            "aug_strategy": job.aug_strategy, "status": status,
            "actual_diversity_achieved": round(float(actual_diversity), 4),
            "diversity_gain": round(float(actual_diversity - cumulative_diversity), 4),
            "duration_s": round(float(duration_s), 1),
            "n_augmented_episodes": job.n_augmented_episodes, "cost_usd": job.cost_usd})
        if status == "complete": cumulative_diversity = actual_diversity
    return results

def compute_diversity_improvement(schedule: AugSchedule, results: List[dict]) -> Dict:
    after_diversity = max((r["actual_diversity_achieved"] for r in results if r["status"] == "complete"), default=0.0)
    total_cost = sum(r["cost_usd"] for r in results if r["status"] == "complete")
    strategy_stats: Dict[str, Dict] = {}
    for r in results:
        s = r["aug_strategy"]
        if s not in strategy_stats: strategy_stats[s] = {"total_gain": 0.0, "total_cost": 0.0, "count": 0}
        if r["status"] == "complete":
            strategy_stats[s]["total_gain"] += r["diversity_gain"]; strategy_stats[s]["total_cost"] += r["cost_usd"]; strategy_stats[s]["count"] += 1
    strategy_effectiveness = {s: round(stats["total_gain"] / stats["total_cost"] if stats["total_cost"] > 0 else 0.0, 4) for s, stats in strategy_stats.items()}
    return {"before_diversity": 0.0, "after_diversity": round(after_diversity, 4),
        "diversity_delta": round(after_diversity, 4), "total_cost_usd": round(total_cost, 4),
        "cost_efficiency": round(after_diversity / total_cost if total_cost > 0 else 0.0, 4),
        "strategy_effectiveness": strategy_effectiveness}

def generate_schedule_report(schedule: AugSchedule, results: List[dict], diversity_summary: Dict) -> str:
    cost_rows = "".join(
        f"<tr><td>{j.job_id}</td><td>{j.source_dataset}</td><td>{j.aug_strategy}</td>"
        f"<td>{j.n_source_episodes}</td><td>{j.n_augmented_episodes}</td>"
        f"<td>{j.aug_factor}x</td><td>${j.cost_usd:.4f}</td><td>{j.status}</td></tr>"
        for j in schedule.jobs)
    html = f"""<!DOCTYPE html><html><head><meta charset='UTF-8'/>
<title>OCI Robot Cloud - Augmentation Scheduler</title>
<style>body{{background:#0d0d1a;color:#e0e0e0;font-family:monospace;padding:20px}}
h1{{color:#C0392B}}table{{border-collapse:collapse;width:100%}}
th{{background:#1a1a2e;color:#C0392B;padding:8px;text-align:left}}
td{{padding:6px 8px;border-bottom:1px solid #1e2a3a}}</style></head><body>
<h1>Augmentation Scheduler Report</h1>
<p>Schedule: {schedule.schedule_id} | Jobs: {len(schedule.jobs)} | Cost: ${schedule.total_cost_usd:.4f} | Diversity: {diversity_summary['after_diversity']:.3f}</p>
<table><tr><th>Job ID</th><th>Dataset</th><th>Strategy</th><th>Src</th><th>Aug</th><th>Factor</th><th>Cost</th><th>Status</th></tr>
{cost_rows}</table>
<footer style='color:#555;margin-top:20px'>OCI Robot Cloud | GR00T N1.6 | 2026-03-30</footer>
</body></html>"""
    with open("/tmp/augmentation_scheduler.html", "w") as f: f.write(html)
    print("HTML report saved to /tmp/augmentation_scheduler.html")
    return html

def main() -> None:
    print("=" * 70); print("OCI Robot Cloud — Augmentation Scheduler"); print("=" * 70)
    schedule = generate_aug_schedule(target_diversity=0.85, budget_usd=20.0, seed=42)
    print(f"\nSchedule ID : {schedule.schedule_id}")
    print(f"Total jobs  : {len(schedule.jobs)} | Source eps: {schedule.total_source_eps:,} | Aug eps: {schedule.total_augmented_eps:,} | Cost: ${schedule.total_cost_usd:.4f}")
    results = simulate_augmentation(schedule)
    diversity_summary = compute_diversity_improvement(schedule, results)
    print(f"Diversity: 0.0 → {diversity_summary['after_diversity']:.4f} (+{diversity_summary['diversity_delta']:.4f})")
    print(f"Total cost: ${diversity_summary['total_cost_usd']:.4f} | Efficiency: {diversity_summary['cost_efficiency']:.4f} diversity/USD")
    generate_schedule_report(schedule, results, diversity_summary)

if __name__ == "__main__":
    main()

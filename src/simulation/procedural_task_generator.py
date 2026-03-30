#!/usr/bin/env python3
"""
procedural_task_generator.py
Procedural task generator for GR00T robotic manipulation training.
Standalone — stdlib + numpy only.
"""

import json
import math
import random
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import numpy as np

@dataclass
class TaskConfig:
    task_id: str
    task_type: str
    difficulty: str
    object_name: str
    object_color: str
    start_pos: Tuple[float, float, float]
    goal_pos: Tuple[float, float, float]
    obstacle_count: int
    workspace_size: float
    success_threshold_m: float
    max_steps: int
    expected_sr_human: float
    tags: List[str]

@dataclass
class EnvironmentVariation:
    variation_id: str
    seed: int
    lighting: str
    table_texture: str
    background_color: str
    object_scale: float
    gravity_scale: float

@dataclass
class TaskBatch:
    batch_id: str
    tasks: List[TaskConfig]
    variations: List[EnvironmentVariation]
    created_at: str
    total_count: int
    difficulty_distribution: Dict[str, int]

OBJECT_CATALOG: Dict[str, Dict] = {
    "cube":     {"colors": ["red", "blue", "green"],       "typical_start": (0.0, 0.30, 0.02),  "typical_goal": (0.2, 0.30, 0.02)},
    "sphere":   {"colors": ["yellow", "orange", "purple"], "typical_start": (-0.10, 0.35, 0.025),"typical_goal": (0.15, 0.25, 0.025)},
    "cylinder": {"colors": ["white", "black", "gray"],     "typical_start": (0.05, 0.28, 0.03), "typical_goal": (0.25, 0.28, 0.03)},
    "mug":      {"colors": ["brown", "beige", "teal"],     "typical_start": (-0.05, 0.32, 0.04),"typical_goal": (0.20, 0.32, 0.04)},
    "bottle":   {"colors": ["clear", "dark_green", "amber"],"typical_start": (0.00, 0.40, 0.06), "typical_goal": (0.30, 0.40, 0.06)},
}

TABLE_TEXTURES    = ["wood_oak", "wood_pine", "marble_white", "plastic_gray", "metal_brushed"]
BACKGROUND_COLORS = ["light_gray", "white", "dark_gray", "beige", "sky_blue"]

DIFFICULTY_PARAMS = {
    "easy":   {"n_objects": (1,1), "obstacles": (0,0), "workspace_size": 0.60, "success_threshold_m": 0.05, "max_steps": 200, "expected_sr_human": 0.98},
    "medium": {"n_objects": (1,2), "obstacles": (1,2), "workspace_size": 0.50, "success_threshold_m": 0.04, "max_steps": 300, "expected_sr_human": 0.85},
    "hard":   {"n_objects": (2,3), "obstacles": (2,4), "workspace_size": 0.40, "success_threshold_m": 0.03, "max_steps": 400, "expected_sr_human": 0.70},
    "expert": {"n_objects": (3,5), "obstacles": (4,6), "workspace_size": 0.30, "success_threshold_m": 0.02, "max_steps": 600, "expected_sr_human": 0.55},
}

TASK_TYPES = ["pick_place", "stack", "sweep", "sort"]


def generate_task(seed: int, difficulty: str = "easy", task_type: Optional[str] = None) -> TaskConfig:
    rng = np.random.RandomState(seed)
    params = DIFFICULTY_PARAMS[difficulty]
    object_names = list(OBJECT_CATALOG.keys())
    obj_name  = object_names[rng.randint(0, len(object_names))]
    obj_colors = OBJECT_CATALOG[obj_name]["colors"]
    obj_color  = obj_colors[rng.randint(0, len(obj_colors))]
    base_start = OBJECT_CATALOG[obj_name]["typical_start"]
    base_goal  = OBJECT_CATALOG[obj_name]["typical_goal"]
    noise_scale = params["workspace_size"] * 0.15
    start_pos = (float(base_start[0] + rng.uniform(-noise_scale, noise_scale)), float(base_start[1] + rng.uniform(-noise_scale, noise_scale)), float(base_start[2]))
    goal_pos  = (float(base_goal[0]  + rng.uniform(-noise_scale, noise_scale)), float(base_goal[1]  + rng.uniform(-noise_scale, noise_scale)), float(base_goal[2]))
    obs_min, obs_max = params["obstacles"]
    obstacle_count = int(rng.randint(obs_min, obs_max + 1))
    chosen_task_type = task_type if task_type else TASK_TYPES[rng.randint(0, len(TASK_TYPES))]
    tags = [difficulty, chosen_task_type, obj_name, obj_color]
    if obstacle_count > 0: tags.append("obstacles")
    if difficulty in ("hard", "expert"): tags.append("high_precision")
    return TaskConfig(task_id=f"task_{seed:08x}", task_type=chosen_task_type, difficulty=difficulty, object_name=obj_name, object_color=obj_color, start_pos=start_pos, goal_pos=goal_pos, obstacle_count=obstacle_count, workspace_size=params["workspace_size"], success_threshold_m=params["success_threshold_m"], max_steps=params["max_steps"], expected_sr_human=params["expected_sr_human"], tags=tags)


def generate_variation(seed: int) -> EnvironmentVariation:
    rng = np.random.RandomState(seed)
    lightings = ["bright", "dim", "natural"]
    return EnvironmentVariation(variation_id=f"var_{seed:08x}", seed=seed, lighting=lightings[rng.randint(0, len(lightings))], table_texture=TABLE_TEXTURES[rng.randint(0, len(TABLE_TEXTURES))], background_color=BACKGROUND_COLORS[rng.randint(0, len(BACKGROUND_COLORS))], object_scale=float(rng.uniform(0.85, 1.15)), gravity_scale=float(rng.uniform(0.95, 1.05)))


def generate_batch(n_tasks: int, difficulty_mix: Optional[Dict[str, float]] = None, seed: int = 42) -> TaskBatch:
    if difficulty_mix is None:
        difficulty_mix = {"easy": 0.25, "medium": 0.25, "hard": 0.25, "expert": 0.25}
    total_weight = sum(difficulty_mix.values())
    norm = {k: v / total_weight for k, v in difficulty_mix.items()}
    rng = random.Random(seed)
    difficulties = list(norm.keys())
    weights = [norm[d] for d in difficulties]
    tasks: List[TaskConfig] = []
    variations: List[EnvironmentVariation] = []
    task_seed = seed * 1000
    for i in range(n_tasks):
        chosen_difficulty = rng.choices(difficulties, weights=weights, k=1)[0]
        tasks.append(generate_task(task_seed + i, difficulty=chosen_difficulty))
        variations.append(generate_variation(task_seed + i + 500_000))
    dist: Dict[str, int] = {}
    for t in tasks:
        dist[t.difficulty] = dist.get(t.difficulty, 0) + 1
    return TaskBatch(batch_id=f"batch_{seed:08x}_{n_tasks}", tasks=tasks, variations=variations, created_at=datetime.utcnow().isoformat() + "Z", total_count=n_tasks, difficulty_distribution=dist)


def compute_curriculum_schedule(n_stages: int = 5, target_sr: float = 0.75) -> List[Dict]:
    difficulties = ["easy", "medium", "hard", "expert"]
    schedule = []
    for stage in range(n_stages):
        frac = stage / max(n_stages - 1, 1)
        diff_idx = frac * (len(difficulties) - 1)
        lower_idx = int(math.floor(diff_idx))
        upper_idx = min(lower_idx + 1, len(difficulties) - 1)
        blend = diff_idx - lower_idx
        lower_diff = difficulties[lower_idx]
        upper_diff = difficulties[upper_idx]
        lower_sr = DIFFICULTY_PARAMS[lower_diff]["expected_sr_human"]
        upper_sr = DIFFICULTY_PARAMS[upper_diff]["expected_sr_human"]
        stage_sr = lower_sr + blend * (upper_sr - lower_sr)
        n_demos = int(200 + stage * 150)
        if lower_idx == upper_idx:
            mix = {lower_diff: 1.0}
        else:
            mix = {lower_diff: round(1.0 - blend, 2), upper_diff: round(blend, 2)}
        schedule.append({"stage": stage + 1, "difficulty_mix": mix, "n_demos": n_demos, "expected_sr": round(stage_sr, 3), "target_sr": target_sr, "meets_target": stage_sr >= target_sr, "description": f"Stage {stage + 1}/{n_stages}: blend {mix}"})
    return schedule


def _task_to_dict(task: TaskConfig) -> Dict:
    d = asdict(task)
    d["start_pos"] = list(task.start_pos)
    d["goal_pos"]  = list(task.goal_pos)
    return d


def save_batch_json(batch: TaskBatch, output_path: str) -> None:
    data = {"batch_id": batch.batch_id, "created_at": batch.created_at, "total_count": batch.total_count, "difficulty_distribution": batch.difficulty_distribution, "tasks": [_task_to_dict(t) for t in batch.tasks], "variations": [asdict(v) for v in batch.variations]}
    with open(output_path, "w") as fh:
        json.dump(data, fh, indent=2)
    print(f"  Saved {batch.total_count} tasks -> {output_path}")


def main() -> None:
    print("=" * 70)
    print("OCI Robot Cloud — Procedural Task Generator")
    print("=" * 70)
    print("\n[1/3] Generating batches ...")
    easy_100  = generate_batch(n_tasks=100, difficulty_mix={"easy": 1.0}, seed=1001)
    mixed_500 = generate_batch(n_tasks=500, difficulty_mix={"easy": 0.30, "medium": 0.35, "hard": 0.25, "expert": 0.10}, seed=2002)
    expert_50 = generate_batch(n_tasks=50,  difficulty_mix={"expert": 1.0}, seed=3003)
    batches = [("easy_100", easy_100, "/tmp/tasks_easy_100.json"), ("mixed_500", mixed_500, "/tmp/tasks_mixed_500.json"), ("expert_50", expert_50, "/tmp/tasks_expert_50.json")]
    print("\n[2/3] Saving batch JSON files ...")
    for _, batch, path in batches:
        save_batch_json(batch, path)
    cost_per_1k = 0.43
    print("\n[3/3] Batch statistics")
    print("-" * 72)
    print(f"{'Batch':<15} {'Tasks':>7} {'Easy':>7} {'Medium':>8} {'Hard':>7} {'Expert':>8}  Est. cost")
    print("-" * 72)
    for name, batch, _ in batches:
        dist = batch.difficulty_distribution
        cost = (batch.total_count / 1000.0) * cost_per_1k
        print(f"{name:<15} {batch.total_count:>7} {dist.get('easy',0):>7} {dist.get('medium',0):>8} {dist.get('hard',0):>7} {dist.get('expert',0):>8}  ${cost:.4f}")
    print("-" * 72)
    total_tasks = sum(b.total_count for _, b, _ in batches)
    print(f"{'TOTAL':<15} {total_tasks:>7}{'':>37} ${(total_tasks/1000.0)*cost_per_1k:.4f}")
    print("\n" + "=" * 70)
    print("Curriculum Schedule (5 stages, target SR = 0.75)")
    print("=" * 70)
    curriculum = compute_curriculum_schedule(n_stages=5, target_sr=0.75)
    for stage in curriculum:
        mix_str = ", ".join(f"{k}:{v:.0%}" for k, v in stage["difficulty_mix"].items())
        print(f"  Stage {stage['stage']}: {mix_str:<36} n_demos={stage['n_demos']:>4}  exp_SR={stage['expected_sr']:.3f}  meets_target={stage['meets_target']}")
    curriculum_path = "/tmp/curriculum_schedule.json"
    with open(curriculum_path, "w") as fh:
        json.dump(curriculum, fh, indent=2)
    print(f"\nCurriculum saved -> {curriculum_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()

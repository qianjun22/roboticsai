"""
Standardized task library for GR00T fine-tuning on OCI Robot Cloud.

Defines success criteria, simulation configurations, and expected success-rate
baselines for 12 canonical manipulation tasks spanning pick, place, push, cable,
door, assembly, inspection, and handover categories.  Used by the pipeline
orchestrator to select curricula, allocate demo budgets, and benchmark models.
"""

from __future__ import annotations

import argparse
import html
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TaskCategory(Enum):
    PICK = "pick"
    PLACE = "place"
    PUSH = "push"
    CABLE = "cable"
    DOOR = "door"
    ASSEMBLY = "assembly"
    INSPECTION = "inspection"
    HANDOVER = "handover"


class TaskDifficulty(Enum):
    BEGINNER = 0
    INTERMEDIATE = 1
    ADVANCED = 2
    EXPERT = 3


# ---------------------------------------------------------------------------
# TaskSpec dataclass
# ---------------------------------------------------------------------------

@dataclass
class TaskSpec:
    task_id: str
    name: str
    category: TaskCategory
    difficulty: TaskDifficulty
    success_criteria: List[str]
    sim_config: Dict  # keys: cube_range, distractors, lighting_variance
    expected_bc_sr: float        # success rate after behaviour-cloning baseline
    expected_dagger_sr: float    # success rate after DAgger fine-tuning
    demo_requirement: int        # minimum demos to achieve DAgger SR
    embodiments: List[str]


# ---------------------------------------------------------------------------
# Task definitions
# ---------------------------------------------------------------------------

TASKS: List[TaskSpec] = [
    TaskSpec(
        task_id="pick_lift_center",
        name="Pick & Lift (Center)",
        category=TaskCategory.PICK,
        difficulty=TaskDifficulty.BEGINNER,
        success_criteria=[
            "Cube grasped firmly",
            "End-effector height >= 0.20 m above table",
            "Cube held for >= 1.0 s",
        ],
        sim_config={"cube_range": "center_fixed", "distractors": 0, "lighting_variance": 0.05},
        expected_bc_sr=0.30,
        expected_dagger_sr=0.72,
        demo_requirement=200,
        embodiments=["franka_panda", "ur5e", "gr1"],
    ),
    TaskSpec(
        task_id="pick_lift_random",
        name="Pick & Lift (Random Pos)",
        category=TaskCategory.PICK,
        difficulty=TaskDifficulty.INTERMEDIATE,
        success_criteria=[
            "Cube grasped from randomised table position",
            "End-effector height >= 0.20 m above table",
            "Cube held for >= 1.0 s",
        ],
        sim_config={"cube_range": "full_workspace", "distractors": 0, "lighting_variance": 0.10},
        expected_bc_sr=0.15,
        expected_dagger_sr=0.58,
        demo_requirement=500,
        embodiments=["franka_panda", "ur5e", "gr1"],
    ),
    TaskSpec(
        task_id="pick_place_box",
        name="Pick & Place into Box",
        category=TaskCategory.PLACE,
        difficulty=TaskDifficulty.INTERMEDIATE,
        success_criteria=[
            "Cube grasped",
            "Cube released inside target box (15 cm × 15 cm)",
            "Cube remains inside box after release",
        ],
        sim_config={"cube_range": "full_workspace", "distractors": 1, "lighting_variance": 0.10},
        expected_bc_sr=0.08,
        expected_dagger_sr=0.45,
        demo_requirement=500,
        embodiments=["franka_panda", "ur5e"],
    ),
    TaskSpec(
        task_id="push_to_goal",
        name="Push to Goal",
        category=TaskCategory.PUSH,
        difficulty=TaskDifficulty.BEGINNER,
        success_criteria=[
            "Cube contacts marked goal zone",
            "Cube centre within 3 cm of goal centre",
        ],
        sim_config={"cube_range": "center_fixed", "distractors": 0, "lighting_variance": 0.05},
        expected_bc_sr=0.22,
        expected_dagger_sr=0.64,
        demo_requirement=200,
        embodiments=["franka_panda", "ur5e", "gr1", "spot_arm"],
    ),
    TaskSpec(
        task_id="bin_picking",
        name="Bin Picking (Cluttered)",
        category=TaskCategory.PICK,
        difficulty=TaskDifficulty.ADVANCED,
        success_criteria=[
            "Target cube identified among distractors",
            "Target cube grasped without displacing all distractors",
            "Target cube lifted >= 0.15 m",
        ],
        sim_config={"cube_range": "bin_random", "distractors": 3, "lighting_variance": 0.20},
        expected_bc_sr=0.05,
        expected_dagger_sr=0.32,
        demo_requirement=1000,
        embodiments=["franka_panda", "ur5e"],
    ),
    TaskSpec(
        task_id="cable_routing",
        name="Cable Routing",
        category=TaskCategory.CABLE,
        difficulty=TaskDifficulty.EXPERT,
        success_criteria=[
            "Cable routed through all 3 clips in order",
            "No clip displaced",
            "Cable slack <= 2 cm per segment",
        ],
        sim_config={"cube_range": "fixed_clips", "distractors": 0, "lighting_variance": 0.15},
        expected_bc_sr=0.02,
        expected_dagger_sr=0.18,
        demo_requirement=2000,
        embodiments=["franka_panda", "gr1"],
    ),
    TaskSpec(
        task_id="door_handle",
        name="Door Handle Pull",
        category=TaskCategory.DOOR,
        difficulty=TaskDifficulty.ADVANCED,
        success_criteria=[
            "Handle grasped",
            "Door opened >= 45 degrees",
            "Robot clears door arc without collision",
        ],
        sim_config={"cube_range": "door_fixed", "distractors": 0, "lighting_variance": 0.15},
        expected_bc_sr=0.05,
        expected_dagger_sr=0.28,
        demo_requirement=1000,
        embodiments=["franka_panda", "gr1", "spot_arm"],
    ),
    TaskSpec(
        task_id="peg_insertion",
        name="Peg Insertion (1 mm Tolerance)",
        category=TaskCategory.ASSEMBLY,
        difficulty=TaskDifficulty.EXPERT,
        success_criteria=[
            "Peg aligned with hole within 1 mm lateral error",
            "Peg inserted at least 10 mm deep",
            "No excessive insertion force (< 20 N)",
        ],
        sim_config={"cube_range": "peg_fixed", "distractors": 0, "lighting_variance": 0.05},
        expected_bc_sr=0.02,
        expected_dagger_sr=0.15,
        demo_requirement=2000,
        embodiments=["franka_panda"],
    ),
    TaskSpec(
        task_id="object_handover",
        name="Object Handover (Dual-Arm)",
        category=TaskCategory.HANDOVER,
        difficulty=TaskDifficulty.INTERMEDIATE,
        success_criteria=[
            "Primary arm grasps object",
            "Object transferred to secondary arm without dropping",
            "Secondary arm holds object for >= 1.5 s",
        ],
        sim_config={"cube_range": "center_fixed", "distractors": 0, "lighting_variance": 0.10},
        expected_bc_sr=0.12,
        expected_dagger_sr=0.48,
        demo_requirement=500,
        embodiments=["gr1", "franka_bimanual"],
    ),
    TaskSpec(
        task_id="visual_inspection",
        name="Visual Inspection Scan",
        category=TaskCategory.INSPECTION,
        difficulty=TaskDifficulty.INTERMEDIATE,
        success_criteria=[
            "Camera covers all 6 faces of object",
            "Each face viewed at <= 30 degree angle",
            "Scan completed within 15 s",
        ],
        sim_config={"cube_range": "pedestal_fixed", "distractors": 0, "lighting_variance": 0.20},
        expected_bc_sr=0.35,
        expected_dagger_sr=0.78,
        demo_requirement=300,
        embodiments=["franka_panda", "ur5e", "gr1"],
    ),
    TaskSpec(
        task_id="stack_cubes",
        name="Stack Two Cubes",
        category=TaskCategory.ASSEMBLY,
        difficulty=TaskDifficulty.ADVANCED,
        success_criteria=[
            "Bottom cube placed at target position",
            "Top cube placed on bottom cube",
            "Stack stable for >= 2.0 s",
            "Lateral offset <= 5 mm",
        ],
        sim_config={"cube_range": "two_cubes_random", "distractors": 0, "lighting_variance": 0.10},
        expected_bc_sr=0.06,
        expected_dagger_sr=0.35,
        demo_requirement=1000,
        embodiments=["franka_panda", "ur5e"],
    ),
    TaskSpec(
        task_id="multi_step_sequence",
        name="Multi-Step Sequence (4-Step)",
        category=TaskCategory.ASSEMBLY,
        difficulty=TaskDifficulty.EXPERT,
        success_criteria=[
            "Step 1 — Pick: cube grasped from random position",
            "Step 2 — Inspect: all 6 faces scanned by wrist camera",
            "Step 3 — Place: cube deposited in target zone",
            "Step 4 — Verify: robot signals OK pose over placed cube",
        ],
        sim_config={"cube_range": "full_workspace", "distractors": 1, "lighting_variance": 0.20},
        expected_bc_sr=0.02,
        expected_dagger_sr=0.22,
        demo_requirement=2000,
        embodiments=["gr1", "franka_panda"],
    ),
]


# ---------------------------------------------------------------------------
# TaskLibrary
# ---------------------------------------------------------------------------

class TaskLibrary:
    def __init__(self, tasks: List[TaskSpec] = TASKS):
        self._tasks: Dict[str, TaskSpec] = {t.task_id: t for t in tasks}

    def get_task(self, task_id: str) -> Optional[TaskSpec]:
        return self._tasks.get(task_id)

    def by_difficulty(self, difficulty: TaskDifficulty) -> List[TaskSpec]:
        return [t for t in self._tasks.values() if t.difficulty == difficulty]

    def by_category(self, category: TaskCategory) -> List[TaskSpec]:
        return [t for t in self._tasks.values() if t.category == category]

    def progression_path(self) -> List[TaskSpec]:
        order = [
            TaskDifficulty.BEGINNER,
            TaskDifficulty.INTERMEDIATE,
            TaskDifficulty.ADVANCED,
            TaskDifficulty.EXPERT,
        ]
        result = []
        for d in order:
            result.extend(sorted(self.by_difficulty(d), key=lambda t: t.task_id))
        return result

    def recommend_for_demos(self, n_demos: int) -> List[TaskSpec]:
        """Return tasks whose demo_requirement <= n_demos, ordered by difficulty then DAgger SR."""
        candidates = [t for t in self._tasks.values() if t.demo_requirement <= n_demos]
        return sorted(candidates, key=lambda t: (t.difficulty.value, -t.expected_dagger_sr))


# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------

_DIFFICULTY_COLORS = {
    TaskDifficulty.BEGINNER:     "#22c55e",  # green-500
    TaskDifficulty.INTERMEDIATE: "#f59e0b",  # amber-500
    TaskDifficulty.ADVANCED:     "#f97316",  # orange-500
    TaskDifficulty.EXPERT:       "#ef4444",  # red-500
}

_DEMO_TIER_COLOR = {
    "green": "#16a34a",
    "amber": "#d97706",
    "red":   "#dc2626",
}


def _demo_tier(demo_req: int) -> str:
    if demo_req <= 500:
        return "green"
    elif demo_req <= 1000:
        return "amber"
    return "red"


def _card_html(task: TaskSpec) -> str:
    tier = _demo_tier(task.demo_requirement)
    border_color = _DEMO_TIER_COLOR[tier]
    diff_color = _DIFFICULTY_COLORS[task.difficulty]
    embod = ", ".join(task.embodiments)
    criteria_items = "".join(f"<li>{html.escape(c)}</li>" for c in task.success_criteria)
    return f"""
    <div class="card" style="border-left:4px solid {border_color};">
      <div class="card-header">
        <span class="task-name">{html.escape(task.name)}</span>
        <span class="badge" style="background:{diff_color};">{task.difficulty.name}</span>
      </div>
      <div class="sr-row">
        <span>BC: <strong>{task.expected_bc_sr*100:.0f}%</strong></span>
        <span>DAgger: <strong>{task.expected_dagger_sr*100:.0f}%</strong></span>
      </div>
      <div class="meta">Demos: {task.demo_requirement} &nbsp;|&nbsp; Category: {task.category.name}</div>
      <div class="embodiments">Embodiments: {html.escape(embod)}</div>
      <ul class="criteria">{criteria_items}</ul>
    </div>"""


def render_html(library: TaskLibrary) -> str:
    columns = {d: library.by_difficulty(d) for d in TaskDifficulty}
    col_html = ""
    for diff, tasks in columns.items():
        cards = "".join(_card_html(t) for t in tasks)
        col_html += f"""
      <div class="column">
        <h2 style="color:{_DIFFICULTY_COLORS[diff]};">{diff.name}</h2>
        {cards}
      </div>"""

    legend = " ".join(
        f'<span class="legend-item" style="border-left:4px solid {c};">'
        f' &le;{label} demos</span>'
        for label, c in [("500", _DEMO_TIER_COLOR["green"]),
                         ("1000", _DEMO_TIER_COLOR["amber"]),
                         ("2000+", _DEMO_TIER_COLOR["red"])]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>OCI Robot Cloud — Task Library</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',sans-serif; padding:24px; }}
    h1 {{ text-align:center; font-size:1.6rem; margin-bottom:6px; color:#f8fafc; }}
    .subtitle {{ text-align:center; color:#94a3b8; font-size:.85rem; margin-bottom:18px; }}
    .legend {{ display:flex; justify-content:center; gap:16px; margin-bottom:24px; }}
    .legend-item {{ padding:4px 10px; background:#1e293b; border-radius:4px; font-size:.78rem; }}
    .board {{ display:grid; grid-template-columns:repeat(4,1fr); gap:18px; }}
    .column {{ background:#1e293b; border-radius:10px; padding:14px; }}
    .column h2 {{ font-size:1rem; text-align:center; margin-bottom:12px; letter-spacing:.05em; }}
    .card {{ background:#0f172a; border-radius:8px; padding:12px; margin-bottom:12px; }}
    .card-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }}
    .task-name {{ font-size:.88rem; font-weight:600; color:#f1f5f9; }}
    .badge {{ font-size:.68rem; padding:2px 7px; border-radius:9px; color:#fff; font-weight:700; }}
    .sr-row {{ display:flex; gap:12px; font-size:.82rem; margin-bottom:4px; color:#94a3b8; }}
    .sr-row strong {{ color:#f1f5f9; }}
    .meta {{ font-size:.75rem; color:#64748b; margin-bottom:3px; }}
    .embodiments {{ font-size:.72rem; color:#475569; margin-bottom:6px; }}
    .criteria {{ font-size:.72rem; color:#64748b; padding-left:14px; }}
    .criteria li {{ margin-bottom:2px; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Task Library</h1>
  <p class="subtitle">12 canonical manipulation tasks &nbsp;|&nbsp; GR00T fine-tuning benchmarks</p>
  <div class="legend">{legend}</div>
  <div class="board">{col_html}
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate OCI Robot Cloud task library HTML catalog.")
    parser.add_argument("--output", default="/tmp/robot_task_library.html",
                        help="Output HTML file path (default: /tmp/robot_task_library.html)")
    args = parser.parse_args()

    library = TaskLibrary()

    # Quick CLI summary
    print(f"Task library loaded: {len(library._tasks)} tasks")
    for diff in TaskDifficulty:
        tasks = library.by_difficulty(diff)
        print(f"  {diff.name:14s}: {len(tasks)} tasks — " +
              ", ".join(t.task_id for t in tasks))

    print("\nProgression path:")
    for i, t in enumerate(library.progression_path(), 1):
        print(f"  {i:2d}. [{t.difficulty.name:14s}] {t.name} "
              f"(BC {t.expected_bc_sr*100:.0f}% → DAgger {t.expected_dagger_sr*100:.0f}%)")

    print("\nRecommended tasks for 500 demos:")
    for t in library.recommend_for_demos(500):
        print(f"  - {t.name}")

    page = render_html(library)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"\nHTML catalog written to: {args.output}")


if __name__ == "__main__":
    main()

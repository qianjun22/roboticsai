#!/usr/bin/env python3
"""
task_variation_generator.py — Generates structured task variations for robot training diversity.

Creates systematic variations of manipulation tasks by varying object properties,
scene configurations, and goal conditions. Ensures training data covers the full
distribution of real-world conditions without human re-demonstration.

Usage:
    python src/simulation/task_variation_generator.py --mock --task pick_and_place
    python src/simulation/task_variation_generator.py --output /tmp/task_variations.html
"""

import argparse
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path


# ── Variation axes ─────────────────────────────────────────────────────────────

@dataclass
class TaskVariation:
    var_id: str
    base_task: str
    difficulty: float       # 0-1
    object_color: str
    object_size: str        # small / medium / large
    object_mass: str        # light / standard / heavy
    start_position: str     # near / center / far / random
    goal_position: str      # fixed / rotated / elevated / random
    lighting: str           # standard / dim / bright / mixed
    distractor_count: int   # 0-4
    estimated_sr: float     # expected SR for trained DAgger policy
    isaac_config: dict      # Isaac Sim DR config snippet


BASE_TASKS = ["pick_and_place", "stack_blocks", "open_drawer", "peg_insert", "handover"]

COLORS  = ["red", "blue", "green", "yellow", "orange", "purple", "white", "black"]
SIZES   = ["small", "medium", "large"]
MASSES  = ["light", "standard", "heavy"]
STARTS  = ["near", "center", "far", "random"]
GOALS   = ["fixed", "rotated_45", "rotated_90", "elevated", "random"]
LIGHTS  = ["standard", "dim", "bright", "backlit", "mixed"]


# ── Generation ─────────────────────────────────────────────────────────────────

def estimate_sr(difficulty: float, base_sr: float = 0.68) -> float:
    """Harder variations → lower SR. Noise added for realism."""
    return max(0.08, min(0.90, base_sr * (1 - difficulty * 0.55)))


def make_isaac_config(var: dict) -> dict:
    """Generate Isaac Sim domain randomization config snippet."""
    return {
        "object": {
            "color_rgb": {"randomize": var["object_color"] == "random",
                          "fixed": var["object_color"]},
            "scale": {"small": 0.7, "medium": 1.0, "large": 1.35}[var["object_size"]],
            "mass_kg": {"light": 0.08, "standard": 0.25, "heavy": 0.65}[var["object_mass"]],
        },
        "scene": {
            "distractors": var["distractor_count"],
            "lighting_intensity": {"dim": 0.4, "standard": 1.0, "bright": 1.6,
                                   "backlit": 0.8, "mixed": "random"}[var["lighting"]],
        },
        "robot": {
            "start_offset_m": {"near": 0.05, "center": 0.0, "far": 0.20,
                               "random": "uniform(0,0.25)"}[var["start_position"]],
        }
    }


def generate_variations(base_task: str, n: int = 60, seed: int = 42) -> list[TaskVariation]:
    rng = random.Random(seed + abs(hash(base_task)) % 1000)
    variations = []

    # Systematic coverage: ensure each axis is explored
    systematic = [
        # Easy baseline
        {"color": "red",    "size": "medium", "mass": "standard", "start": "center",
         "goal": "fixed",      "light": "standard", "dist": 0},
        # Hard: all adverse
        {"color": "white",  "size": "small",  "mass": "heavy",    "start": "far",
         "goal": "elevated",   "light": "backlit",  "dist": 4},
        # Color variation
        *[{"color": c,       "size": "medium", "mass": "standard", "start": "center",
           "goal": "fixed",    "light": "standard", "dist": 0} for c in COLORS[:6]],
        # Size variation
        *[{"color": "red",   "size": s,        "mass": "standard", "start": "center",
           "goal": "fixed",    "light": "standard", "dist": 0} for s in SIZES],
        # Position variation
        *[{"color": "red",   "size": "medium", "mass": "standard", "start": sp,
           "goal": "fixed",    "light": "standard", "dist": 0} for sp in STARTS],
        # Distractor sweep
        *[{"color": "red",   "size": "medium", "mass": "standard", "start": "center",
           "goal": "fixed",    "light": "standard", "dist": d} for d in range(5)],
    ]

    for i, s in enumerate(systematic[:n]):
        diff = (s.get("dist", 0) * 0.05 +
                (0.15 if s["size"] == "small" else 0.0) +
                (0.10 if s["mass"] == "heavy" else 0.0) +
                (0.12 if s["start"] == "far" else 0.0) +
                (0.15 if s["goal"] == "elevated" else 0.0) +
                (0.10 if s["light"] == "backlit" else 0.0))
        diff = min(0.9, diff)
        sr = round(estimate_sr(diff) + rng.gauss(0, 0.02), 3)

        var_dict = {"object_color": s["color"], "object_size": s["size"],
                    "object_mass": s["mass"], "start_position": s["start"],
                    "goal_position": s["goal"], "lighting": s["light"],
                    "distractor_count": s["dist"]}
        variations.append(TaskVariation(
            var_id=f"{base_task[:3]}-v{i+1:03d}",
            base_task=base_task,
            difficulty=round(diff, 3),
            object_color=s["color"],
            object_size=s["size"],
            object_mass=s["mass"],
            start_position=s["start"],
            goal_position=s["goal"],
            lighting=s["light"],
            distractor_count=s.get("dist", 0),
            estimated_sr=sr,
            isaac_config=make_isaac_config(var_dict),
        ))

    # Fill rest with random variations
    while len(variations) < n:
        i = len(variations)
        color = rng.choice(COLORS)
        size  = rng.choice(SIZES)
        mass  = rng.choice(MASSES)
        start = rng.choice(STARTS)
        goal  = rng.choice(GOALS)
        light = rng.choice(LIGHTS)
        dist  = rng.randint(0, 4)
        diff  = round(rng.uniform(0.05, 0.80), 3)
        sr    = round(estimate_sr(diff) + rng.gauss(0, 0.025), 3)
        var_dict = {"object_color": color, "object_size": size, "object_mass": mass,
                    "start_position": start, "goal_position": goal,
                    "lighting": light, "distractor_count": dist}
        variations.append(TaskVariation(
            var_id=f"{base_task[:3]}-v{i+1:03d}",
            base_task=base_task,
            difficulty=diff,
            object_color=color, object_size=size, object_mass=mass,
            start_position=start, goal_position=goal,
            lighting=light, distractor_count=dist,
            estimated_sr=sr,
            isaac_config=make_isaac_config(var_dict),
        ))

    return variations[:n]


def compute_coverage(variations: list[TaskVariation]) -> dict:
    return {
        "total": len(variations),
        "difficulty_bins": {
            "easy (0-0.3)":   sum(1 for v in variations if v.difficulty < 0.3),
            "medium (0.3-0.6)": sum(1 for v in variations if 0.3 <= v.difficulty < 0.6),
            "hard (0.6+)":    sum(1 for v in variations if v.difficulty >= 0.6),
        },
        "color_coverage":  len(set(v.object_color  for v in variations)) / len(COLORS),
        "size_coverage":   len(set(v.object_size   for v in variations)) / len(SIZES),
        "light_coverage":  len(set(v.lighting      for v in variations)) / len(LIGHTS),
        "avg_estimated_sr": round(sum(v.estimated_sr for v in variations) / len(variations), 3),
    }


# ── HTML report ────────────────────────────────────────────────────────────────

def render_html(all_variations: dict[str, list], coverage: dict[str, dict]) -> str:
    # SVG: difficulty distribution per task (grouped bar)
    tasks = list(all_variations)
    n_tasks = len(tasks)
    TASK_COLORS = ["#C74634", "#3b82f6", "#22c55e", "#f59e0b", "#a855f7"]
    w, h = 500, 140
    group_w = (w - 40) / 3
    bar_w = group_w / (n_tasks + 1) - 2

    svg_diff = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg_diff += f'<line x1="20" y1="{h-20}" x2="{w}" y2="{h-20}" stroke="#334155" stroke-width="1"/>'
    bins = ["easy (0-0.3)", "medium (0.3-0.6)", "hard (0.6+)"]
    max_count = max(v for cov in coverage.values() for v in cov["difficulty_bins"].values()) or 1

    for bi, bin_name in enumerate(bins):
        gx = 20 + bi * group_w
        for ti, task in enumerate(tasks):
            cnt = coverage[task]["difficulty_bins"].get(bin_name, 0)
            bh = cnt / max_count * (h - 40)
            x = gx + ti * (bar_w + 2)
            col = TASK_COLORS[ti % len(TASK_COLORS)]
            svg_diff += (f'<rect x="{x:.1f}" y="{h-20-bh:.1f}" width="{bar_w:.1f}" '
                         f'height="{bh:.1f}" fill="{col}" rx="1" opacity="0.85"/>')
        short = bin_name.split()[0]
        svg_diff += (f'<text x="{gx+group_w/2:.1f}" y="{h-4}" fill="#64748b" '
                     f'font-size="9" text-anchor="middle">{short}</text>')
    svg_diff += '</svg>'

    legend = " ".join(
        f'<span style="color:{TASK_COLORS[i%len(TASK_COLORS)]}">■ {t}</span>'
        for i, t in enumerate(tasks)
    )

    # Table: first task variations
    first_task = tasks[0]
    first_vars = all_variations[first_task]
    rows = ""
    for v in sorted(first_vars, key=lambda x: x.difficulty)[:20]:
        sr_col = "#22c55e" if v.estimated_sr >= 0.55 else "#f59e0b" if v.estimated_sr >= 0.35 else "#ef4444"
        diff_col = "#ef4444" if v.difficulty >= 0.6 else "#f59e0b" if v.difficulty >= 0.3 else "#22c55e"
        rows += (f'<tr><td style="color:#94a3b8">{v.var_id}</td>'
                 f'<td style="color:#e2e8f0">{v.object_color}/{v.object_size}/{v.object_mass}</td>'
                 f'<td style="color:#64748b">{v.start_position} → {v.goal_position}</td>'
                 f'<td style="color:#64748b">{v.lighting}</td>'
                 f'<td>{v.distractor_count}</td>'
                 f'<td style="color:{diff_col}">{v.difficulty:.2f}</td>'
                 f'<td style="color:{sr_col}">{v.estimated_sr:.0%}</td></tr>')

    cov_summary = ""
    for task in tasks:
        cov = coverage[task]
        cov_summary += (f'<div style="margin-bottom:8px">'
                        f'<span style="color:#94a3b8">{task}</span>: '
                        f'{cov["total"]} vars · avg SR {cov["avg_estimated_sr"]:.0%} · '
                        f'colors {cov["color_coverage"]:.0%} · '
                        f'lighting {cov["light_coverage"]:.0%}</div>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Task Variation Generator</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:28px;font-weight:bold}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Task Variation Generator</h1>
<div class="meta">
  {sum(len(v) for v in all_variations.values())} total variations · {len(tasks)} tasks · systematic + random coverage
</div>

<div class="grid">
  <div class="card"><h3>Total Variations</h3>
    <div class="big">{sum(len(v) for v in all_variations.values())}</div></div>
  <div class="card"><h3>Tasks Covered</h3>
    <div class="big" style="color:#3b82f6">{len(tasks)}</div></div>
  <div class="card"><h3>Color Coverage</h3>
    <div class="big" style="color:#22c55e">
      {max(c['color_coverage'] for c in coverage.values()):.0%}
    </div></div>
  <div class="card"><h3>Avg Est. SR</h3>
    <div class="big" style="color:#f59e0b">
      {sum(c['avg_estimated_sr'] for c in coverage.values())/len(coverage):.0%}
    </div></div>
</div>

<div class="charts">
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Difficulty Distribution by Task</h3>
    <div style="font-size:10px;margin-bottom:6px">{legend}</div>
    {svg_diff}
  </div>
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Coverage Summary</h3>
    <div style="font-size:11px;margin-top:12px">
      {cov_summary}
    </div>
  </div>
</div>

<h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">
  Sample: {first_task} variations (sorted by difficulty)
</h3>
<table>
  <tr><th>ID</th><th>Object (color/size/mass)</th><th>Position</th><th>Lighting</th>
      <th>Distractors</th><th>Difficulty</th><th>Est SR</th></tr>
  {rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  Generates Isaac Sim DR configs for each variation. Export JSON for training data pipeline.<br>
  Systematic coverage + random fill = balanced difficulty distribution; prevents overfitting to easy cases.<br>
  Use <code>--task all</code> to generate for all 5 base tasks.
</div>
</body></html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Task variation generator")
    parser.add_argument("--mock",       action="store_true", default=True)
    parser.add_argument("--task",       default="all",
                        help="Task name or 'all'")
    parser.add_argument("--n",          type=int, default=60,
                        help="Variations per task")
    parser.add_argument("--output",     default="/tmp/task_variation_generator.html")
    parser.add_argument("--seed",       type=int, default=42)
    args = parser.parse_args()

    tasks = BASE_TASKS if args.task == "all" else [args.task]
    print(f"[task-var] Generating {args.n} variations × {len(tasks)} tasks")
    t0 = time.time()

    all_vars = {t: generate_variations(t, args.n, args.seed) for t in tasks}
    cov = {t: compute_coverage(v) for t, v in all_vars.items()}

    print(f"\n  {'Task':<20} {'Vars':>5}  {'Avg SR':>8}  {'Easy/Med/Hard'}")
    print(f"  {'─'*20} {'─'*5}  {'─'*8}  {'─'*18}")
    for task in tasks:
        c = cov[task]
        bins = c["difficulty_bins"]
        print(f"  {task:<20} {c['total']:>5}  {c['avg_estimated_sr']:>7.0%}  "
              f"{bins['easy (0-0.3)']}/{bins['medium (0.3-0.6)']}/{bins['hard (0.6+)']}")

    print(f"\n  [{time.time()-t0:.1f}s]\n")

    html = render_html(all_vars, cov)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps(
        {t: [{"id": v.var_id, "difficulty": v.difficulty,
              "estimated_sr": v.estimated_sr, "isaac_config": v.isaac_config}
             for v in vars_] for t, vars_ in all_vars.items()}, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()

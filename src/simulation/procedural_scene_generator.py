#!/usr/bin/env python3
"""
procedural_scene_generator.py — Procedural scene generation for robot training diversity.

Generates Isaac Sim scene configurations procedurally — randomizing table layouts,
object arrangements, background distractors, and camera viewpoints to create
diverse training environments without manual scene authoring.

Usage:
    python src/simulation/procedural_scene_generator.py --mock --n-scenes 50
    python src/simulation/procedural_scene_generator.py --output /tmp/scene_gen.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── Scene elements ─────────────────────────────────────────────────────────────

@dataclass
class ObjectPlacement:
    asset_id: str
    category: str      # target / distractor / container / surface
    x: float           # meters from robot base
    y: float
    z: float
    rotation_deg: float
    scale: float
    color_rgb: tuple[int, int, int]


@dataclass
class CameraConfig:
    position: tuple[float, float, float]
    look_at: tuple[float, float, float]
    fov_deg: float
    noise_level: float   # 0-1


@dataclass
class LightingConfig:
    ambient_intensity: float   # 0-1
    directional_intensity: float
    direction_deg: float       # azimuth
    color_temp_k: int          # 3000=warm, 6500=daylight


@dataclass
class GeneratedScene:
    scene_id: str
    seed: int
    n_objects: int
    n_distractors: int
    table_height_m: float
    objects: list[ObjectPlacement]
    camera: CameraConfig
    lighting: LightingConfig
    difficulty_score: float
    estimated_sr: float
    isaac_config_lines: int    # size of generated config


TARGET_ASSETS = [
    "cube_red_5cm", "cube_blue_5cm", "cube_green_5cm",
    "cylinder_yellow", "sphere_orange", "box_white_8cm",
]

DISTRACTOR_ASSETS = [
    "book_flat", "cup_empty", "wrench_small", "screwdriver",
    "tape_roll", "marker_pen", "small_plant", "phone_mock",
]

SURFACE_ASSETS = ["table_white_standard", "table_dark_wood", "conveyor_belt_segment"]

TABLE_HEIGHTS = [0.70, 0.75, 0.80, 0.85]   # meters


# ── Generation ─────────────────────────────────────────────────────────────────

def random_color(rng: random.Random) -> tuple[int, int, int]:
    return (rng.randint(30, 220), rng.randint(30, 220), rng.randint(30, 220))


def generate_scene(scene_id: str, seed: int, n_distractors: int = 3) -> GeneratedScene:
    rng = random.Random(seed)

    # Target object
    target_asset = rng.choice(TARGET_ASSETS)
    objects = [ObjectPlacement(
        asset_id=target_asset,
        category="target",
        x=round(rng.uniform(0.30, 0.55), 3),
        y=round(rng.uniform(-0.20, 0.20), 3),
        z=0.0,
        rotation_deg=round(rng.uniform(0, 360), 1),
        scale=round(rng.uniform(0.85, 1.15), 3),
        color_rgb=random_color(rng),
    )]

    # Distractors
    for _ in range(n_distractors):
        dist_asset = rng.choice(DISTRACTOR_ASSETS)
        # Avoid collision with target (simple distance check)
        for attempt in range(5):
            dx = round(rng.uniform(0.20, 0.65), 3)
            dy = round(rng.uniform(-0.35, 0.35), 3)
            if math.sqrt((dx - objects[0].x)**2 + (dy - objects[0].y)**2) > 0.08:
                break
        objects.append(ObjectPlacement(
            asset_id=dist_asset,
            category="distractor",
            x=dx, y=dy, z=0.0,
            rotation_deg=round(rng.uniform(0, 360), 1),
            scale=round(rng.uniform(0.7, 1.3), 3),
            color_rgb=random_color(rng),
        ))

    # Camera config — slight variation around nominal viewpoint
    cam_x = round(0.40 + rng.gauss(0, 0.02), 3)
    cam_z = round(0.75 + rng.gauss(0, 0.03), 3)
    camera = CameraConfig(
        position=(cam_x, round(rng.uniform(-0.05, 0.05), 3), cam_z),
        look_at=(0.45, 0.0, 0.0),
        fov_deg=round(rng.gauss(60, 3), 1),
        noise_level=round(rng.uniform(0.0, 0.15), 3),
    )

    # Lighting
    lighting = LightingConfig(
        ambient_intensity=round(rng.uniform(0.3, 0.8), 3),
        directional_intensity=round(rng.uniform(0.5, 1.2), 3),
        direction_deg=round(rng.uniform(0, 360), 1),
        color_temp_k=rng.choice([3000, 4000, 5000, 6500]),
    )

    table_h = rng.choice(TABLE_HEIGHTS)

    # Difficulty: more distractors, extreme lighting, unusual table height = harder
    difficulty = (
        n_distractors * 0.08 +
        abs(lighting.ambient_intensity - 0.55) * 0.3 +
        abs(table_h - 0.775) * 2.0 +
        camera.noise_level * 0.4
    )
    difficulty = round(min(0.95, difficulty), 3)
    est_sr = round(max(0.15, 0.72 * (1 - difficulty * 0.65) + rng.gauss(0, 0.02)), 3)

    # Approximate config size
    config_lines = 25 + len(objects) * 12 + 15

    return GeneratedScene(
        scene_id=scene_id,
        seed=seed,
        n_objects=len(objects),
        n_distractors=n_distractors,
        table_height_m=table_h,
        objects=objects,
        camera=camera,
        lighting=lighting,
        difficulty_score=difficulty,
        estimated_sr=est_sr,
        isaac_config_lines=config_lines,
    )


def generate_batch(n: int, seed: int = 42, max_distractors: int = 4) -> list[GeneratedScene]:
    rng = random.Random(seed)
    scenes = []
    for i in range(n):
        n_dist = rng.randint(0, max_distractors)
        scenes.append(generate_scene(f"scene-{i+1:04d}", seed + i * 7, n_dist))
    return scenes


def compute_batch_stats(scenes: list[GeneratedScene]) -> dict:
    diffs = [s.difficulty_score for s in scenes]
    srs = [s.estimated_sr for s in scenes]
    return {
        "total": len(scenes),
        "avg_difficulty": round(sum(diffs) / len(diffs), 3),
        "avg_est_sr": round(sum(srs) / len(srs), 3),
        "easy": sum(1 for s in scenes if s.difficulty_score < 0.3),
        "medium": sum(1 for s in scenes if 0.3 <= s.difficulty_score < 0.6),
        "hard": sum(1 for s in scenes if s.difficulty_score >= 0.6),
        "total_config_lines": sum(s.isaac_config_lines for s in scenes),
    }


def export_isaac_config(scene: GeneratedScene) -> dict:
    """Export scene as Isaac Sim Replicator-style config."""
    return {
        "scene_id": scene.scene_id,
        "table": {"height_m": scene.table_height_m, "asset": "table_white_standard"},
        "objects": [
            {"asset": o.asset_id, "category": o.category,
             "position": [o.x, o.y, o.z], "rotation_deg": o.rotation_deg,
             "scale": o.scale, "color_rgb": list(o.color_rgb)}
            for o in scene.objects
        ],
        "camera": {
            "position": list(scene.camera.position),
            "look_at": list(scene.camera.look_at),
            "fov_deg": scene.camera.fov_deg,
            "noise_level": scene.camera.noise_level,
        },
        "lighting": {
            "ambient_intensity": scene.lighting.ambient_intensity,
            "directional_intensity": scene.lighting.directional_intensity,
            "direction_deg": scene.lighting.direction_deg,
            "color_temp_k": scene.lighting.color_temp_k,
        },
    }


# ── HTML report ────────────────────────────────────────────────────────────────

def render_html(scenes: list[GeneratedScene], stats: dict) -> str:
    # SVG: difficulty distribution
    w, h = 460, 120
    bins = [0] * 10
    for s in scenes:
        b = min(9, int(s.difficulty_score * 10))
        bins[b] += 1
    max_b = max(bins) or 1
    bar_w = (w - 30) / 10

    svg_diff = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg_diff += f'<line x1="15" y1="{h-15}" x2="{w}" y2="{h-15}" stroke="#334155" stroke-width="1"/>'
    for i, cnt in enumerate(bins):
        bh = cnt / max_b * (h - 35)
        x = 15 + i * bar_w
        t = i / 10.0
        col = f"#{int(34 + t*197):02x}{int(197 - t*175):02x}{int(62 + t*32):02x}"
        svg_diff += (f'<rect x="{x:.1f}" y="{h-15-bh:.1f}" width="{bar_w-2:.1f}" '
                     f'height="{bh:.1f}" fill="{col}" rx="2" opacity="0.85"/>')
        svg_diff += (f'<text x="{x+bar_w/2:.1f}" y="{h-2}" fill="#64748b" '
                     f'font-size="8" text-anchor="middle">{i/10:.1f}</text>')
        if cnt > 0:
            svg_diff += (f'<text x="{x+bar_w/2:.1f}" y="{h-17-bh:.1f}" fill="#94a3b8" '
                         f'font-size="8" text-anchor="middle">{cnt}</text>')
    svg_diff += '</svg>'

    # SVG: top-view schematic of a sample scene
    sample = scenes[len(scenes)//2]
    sw, sh = 240, 200
    svg_scene = f'<svg width="{sw}" height="{sh}" style="background:#0f172a;border-radius:8px;border:1px solid #334155">'
    # Table outline
    svg_scene += (f'<rect x="20" y="20" width="{sw-40}" height="{sh-40}" '
                  f'fill="none" stroke="#334155" stroke-width="1.5" rx="4"/>')
    # Robot base (triangle at left)
    svg_scene += '<polygon points="10,90 10,110 25,100" fill="#C74634" opacity="0.8"/>'

    # Scale: 0m-0.7m workspace → 20-220px
    def ws_x(m): return int(20 + m / 0.7 * (sw - 40))
    def ws_y(m): return int(sh//2 - m / 0.5 * (sh//2 - 20))

    for obj in sample.objects:
        px, py = ws_x(obj.x), ws_y(obj.y)
        r, g, b = obj.color_rgb
        col = f"#{r:02x}{g:02x}{b:02x}"
        if obj.category == "target":
            svg_scene += (f'<rect x="{px-8}" y="{py-8}" width="16" height="16" '
                          f'fill="{col}" stroke="white" stroke-width="1.5" rx="2"/>')
            svg_scene += (f'<text x="{px}" y="{py+4}" fill="white" font-size="8" '
                          f'text-anchor="middle">T</text>')
        else:
            svg_scene += (f'<circle cx="{px}" cy="{py}" r="6" fill="{col}" opacity="0.7"/>')

    # Camera position
    cpx = ws_x(sample.camera.position[0])
    cpy = ws_y(sample.camera.position[1]) - 20
    svg_scene += (f'<text x="{cpx}" y="{cpy}" fill="#94a3b8" font-size="9" '
                  f'text-anchor="middle">📷</text>')
    svg_scene += (f'<text x="{sw//2}" y="{sh-5}" fill="#64748b" font-size="8.5" '
                  f'text-anchor="middle">{sample.scene_id} (top view)</text>')
    svg_scene += '</svg>'

    # Scene table
    rows = ""
    for s in sorted(scenes[:20], key=lambda x: x.difficulty_score):
        diff_col = "#ef4444" if s.difficulty_score >= 0.6 else "#f59e0b" if s.difficulty_score >= 0.3 else "#22c55e"
        sr_col = "#22c55e" if s.estimated_sr >= 0.50 else "#f59e0b" if s.estimated_sr >= 0.30 else "#ef4444"
        light_str = f"I:{s.lighting.ambient_intensity:.2f} D:{s.lighting.directional_intensity:.2f} {s.lighting.color_temp_k}K"
        rows += (f'<tr><td style="color:#94a3b8">{s.scene_id}</td>'
                 f'<td>{s.n_distractors}</td>'
                 f'<td>{s.table_height_m:.2f}m</td>'
                 f'<td style="color:#64748b;font-size:10px">{light_str}</td>'
                 f'<td style="color:{diff_col}">{s.difficulty_score:.3f}</td>'
                 f'<td style="color:{sr_col}">{s.estimated_sr:.0%}</td>'
                 f'<td style="color:#64748b">{s.isaac_config_lines}</td></tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Procedural Scene Generator</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:28px;font-weight:bold}}
.charts{{display:grid;grid-template-columns:1fr auto;gap:16px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Procedural Scene Generator</h1>
<div class="meta">
  {stats['total']} scenes generated · easy/medium/hard: {stats['easy']}/{stats['medium']}/{stats['hard']} ·
  {stats['total_config_lines']:,} total Isaac Sim config lines
</div>

<div class="grid">
  <div class="card"><h3>Total Scenes</h3>
    <div class="big">{stats['total']}</div></div>
  <div class="card"><h3>Avg Difficulty</h3>
    <div class="big" style="color:#f59e0b">{stats['avg_difficulty']:.3f}</div></div>
  <div class="card"><h3>Avg Est. SR</h3>
    <div class="big" style="color:#22c55e">{stats['avg_est_sr']:.0%}</div></div>
  <div class="card"><h3>Config Lines</h3>
    <div class="big" style="color:#3b82f6">{stats['total_config_lines']:,}</div></div>
</div>

<div class="charts">
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Difficulty Distribution</h3>
    {svg_diff}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      easy 0–0.3 · medium 0.3–0.6 · hard 0.6+
    </div>
  </div>
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Sample Scene</h3>
    {svg_scene}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      ■ T=target · ● distractors · 📷 camera
    </div>
  </div>
</div>

<h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Sample Scenes (first 20, sorted by difficulty)</h3>
<table>
  <tr><th>Scene ID</th><th>Distractors</th><th>Table H</th><th>Lighting</th>
      <th>Difficulty</th><th>Est SR</th><th>Config Lines</th></tr>
  {rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  Each scene exports a complete Isaac Sim Replicator config JSON.<br>
  Procedural generation → unlimited scene diversity without manual authoring.<br>
  Use with domain_randomization_sweep.py for optimal DR parameter search.
</div>
</body></html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Procedural scene generator")
    parser.add_argument("--mock",          action="store_true", default=True)
    parser.add_argument("--n-scenes",      type=int, default=80)
    parser.add_argument("--max-distractors", type=int, default=4)
    parser.add_argument("--output",        default="/tmp/procedural_scene_generator.html")
    parser.add_argument("--export-json",   action="store_true", default=False)
    parser.add_argument("--seed",          type=int, default=42)
    args = parser.parse_args()

    print(f"[scene-gen] Generating {args.n_scenes} scenes (max {args.max_distractors} distractors)")
    t0 = time.time()

    scenes = generate_batch(args.n_scenes, args.seed, args.max_distractors)
    stats = compute_batch_stats(scenes)

    print(f"\n  Total: {stats['total']} scenes")
    print(f"  Difficulty: easy={stats['easy']} med={stats['medium']} hard={stats['hard']}")
    print(f"  Avg SR: {stats['avg_est_sr']:.0%}  Avg difficulty: {stats['avg_difficulty']:.3f}")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(scenes, stats)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    if args.export_json:
        configs = [export_isaac_config(s) for s in scenes]
        json_out = Path(args.output).with_suffix(".json")
        json_out.write_text(json.dumps(configs, indent=2))
        print(f"  Isaac configs → {json_out}")
    else:
        json_out = Path(args.output).with_suffix(".json")
        json_out.write_text(json.dumps(stats, indent=2))
        print(f"  Stats → {json_out}")


if __name__ == "__main__":
    main()

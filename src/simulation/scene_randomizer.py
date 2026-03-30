#!/usr/bin/env python3
"""
scene_randomizer.py — Programmatic scene randomization for GR00T SDG diversity.

Generates a configurable set of scene variations (cube position, lighting,
camera angles, table texture) to improve sim-to-real transfer.
Wraps Genesis SDG with a randomization layer — no Isaac Sim license required.

Usage:
    # Generate 100 randomized demos:
    python src/simulation/scene_randomizer.py \
        --n-demos 100 --output /tmp/randomized_demos \
        --randomize-all

    # Preview variation space (no Genesis):
    python src/simulation/scene_randomizer.py --preview --n-variations 20

    # Specific randomizations only:
    python src/simulation/scene_randomizer.py \
        --n-demos 50 --output /tmp/demos \
        --randomize-lighting --randomize-camera
"""

import argparse
import json
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Randomization config ──────────────────────────────────────────────────────

@dataclass
class SceneConfig:
    """Complete randomized scene specification."""

    # Cube placement
    cube_x: float = 0.45        # meters from robot base
    cube_y: float = 0.00        # lateral offset
    cube_z: float = 0.70        # table height
    cube_rotation_deg: float = 0.0  # yaw rotation

    # Lighting
    light_intensity: float = 1.0    # 0.3–2.0
    light_azimuth_deg: float = 45.0 # 0–360
    light_elevation_deg: float = 60.0  # 20–90
    ambient_intensity: float = 0.3  # 0.1–0.6

    # Camera
    cam_fov_deg: float = 60.0   # 40–80
    cam_x_offset: float = 0.0   # ±0.05m perturbation
    cam_y_offset: float = 0.0
    cam_z_offset: float = 0.0
    cam_noise_std: float = 0.0  # pixel noise (0 or 5–20)

    # Table
    table_friction: float = 1.0  # 0.5–2.0
    cube_mass: float = 0.1       # kg, 0.05–0.3

    # Distractors
    n_distractor_objects: int = 0  # 0–3

    def to_dict(self) -> dict:
        return {
            "cube": {"x": self.cube_x, "y": self.cube_y, "z": self.cube_z,
                     "rotation_deg": self.cube_rotation_deg},
            "lighting": {"intensity": self.light_intensity,
                          "azimuth_deg": self.light_azimuth_deg,
                          "elevation_deg": self.light_elevation_deg,
                          "ambient": self.ambient_intensity},
            "camera": {"fov_deg": self.cam_fov_deg,
                        "offset": [self.cam_x_offset, self.cam_y_offset, self.cam_z_offset],
                        "noise_std": self.cam_noise_std},
            "physics": {"table_friction": self.table_friction, "cube_mass": self.cube_mass},
            "distractors": self.n_distractor_objects,
        }


# ── Randomization strategies ──────────────────────────────────────────────────

class SceneRandomizer:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.configs_generated = 0

    def _r(self, lo: float, hi: float) -> float:
        return self.rng.uniform(lo, hi)

    def _g(self, mean: float, std: float, lo: float = -1e9, hi: float = 1e9) -> float:
        return max(lo, min(hi, self.rng.gauss(mean, std)))

    def clean(self) -> SceneConfig:
        """Minimal randomization — close to training distribution."""
        return SceneConfig(
            cube_x=self._g(0.45, 0.02, 0.35, 0.55),
            cube_y=self._g(0.00, 0.03, -0.05, 0.05),
        )

    def position_varied(self) -> SceneConfig:
        """Cube anywhere in 20cm radius."""
        r   = self._r(0, 0.10)
        ang = self._r(0, 2 * math.pi)
        return SceneConfig(
            cube_x=0.45 + r * math.cos(ang),
            cube_y=0.00 + r * math.sin(ang),
            cube_rotation_deg=self._r(0, 360),
        )

    def lighting_varied(self) -> SceneConfig:
        return SceneConfig(
            cube_x=self._g(0.45, 0.02),
            light_intensity=self._r(0.3, 2.0),
            light_azimuth_deg=self._r(0, 360),
            light_elevation_deg=self._r(20, 90),
            ambient_intensity=self._r(0.1, 0.6),
        )

    def camera_varied(self) -> SceneConfig:
        return SceneConfig(
            cube_x=self._g(0.45, 0.02),
            cam_fov_deg=self._r(45, 75),
            cam_x_offset=self._g(0, 0.02, -0.05, 0.05),
            cam_y_offset=self._g(0, 0.02, -0.05, 0.05),
            cam_z_offset=self._g(0, 0.01, -0.03, 0.03),
            cam_noise_std=self._r(0, 15),
        )

    def physics_varied(self) -> SceneConfig:
        return SceneConfig(
            cube_x=self._g(0.45, 0.02),
            table_friction=self._r(0.5, 2.0),
            cube_mass=self._r(0.05, 0.3),
        )

    def full_randomization(self) -> SceneConfig:
        """All randomizations simultaneously."""
        r   = self._r(0, 0.10)
        ang = self._r(0, 2 * math.pi)
        return SceneConfig(
            cube_x=0.45 + r * math.cos(ang),
            cube_y=0.00 + r * math.sin(ang),
            cube_rotation_deg=self._r(0, 360),
            light_intensity=self._r(0.5, 1.8),
            light_azimuth_deg=self._r(0, 360),
            light_elevation_deg=self._r(25, 85),
            ambient_intensity=self._r(0.15, 0.5),
            cam_fov_deg=self._r(50, 70),
            cam_x_offset=self._g(0, 0.015, -0.04, 0.04),
            cam_y_offset=self._g(0, 0.015, -0.04, 0.04),
            cam_noise_std=self._r(0, 10),
            table_friction=self._r(0.7, 1.5),
            cube_mass=self._r(0.07, 0.2),
            n_distractor_objects=self.rng.randint(0, 2),
        )

    def generate_batch(self, n: int, strategy: str = "full") -> list[SceneConfig]:
        strategy_map = {
            "clean": self.clean,
            "position": self.position_varied,
            "lighting": self.lighting_varied,
            "camera": self.camera_varied,
            "physics": self.physics_varied,
            "full": self.full_randomization,
        }
        fn = strategy_map.get(strategy, self.full_randomization)
        return [fn() for _ in range(n)]


# ── Preview / stats ───────────────────────────────────────────────────────────

def preview_variations(n: int, seed: int = 42) -> None:
    """Print statistics for a batch of randomized scenes."""
    r = SceneRandomizer(seed)
    configs = r.generate_batch(n, "full")

    cube_xs = [c.cube_x for c in configs]
    cube_ys = [c.cube_y for c in configs]
    lights  = [c.light_intensity for c in configs]
    fovs    = [c.cam_fov_deg for c in configs]
    masses  = [c.cube_mass for c in configs]

    def stats(vals: list[float]) -> str:
        import statistics as st
        return (f"min={min(vals):.3f}  mean={st.mean(vals):.3f}  "
                f"max={max(vals):.3f}  σ={st.stdev(vals):.3f}")

    print(f"\n[randomizer] Preview: {n} fully-randomized scenes (seed={seed})")
    print(f"  cube_x:          {stats(cube_xs)}")
    print(f"  cube_y:          {stats(cube_ys)}")
    print(f"  light_intensity: {stats(lights)}")
    print(f"  cam_fov:         {stats(fovs)}")
    print(f"  cube_mass:       {stats(masses)}")
    n_distract = sum(c.n_distractor_objects > 0 for c in configs)
    print(f"  with distractors: {n_distract}/{n} ({n_distract/n:.0%})")
    print()


# ── Write scene specs ─────────────────────────────────────────────────────────

def write_scene_specs(output_dir: str, configs: list[SceneConfig]) -> None:
    """Save scene specs as JSON (consumed by genesis_sdg_planned.py with --scene-config flag)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    specs_path = out / "scene_configs.json"
    specs = [{"episode_id": i, "config": c.to_dict()} for i, c in enumerate(configs)]
    with open(specs_path, "w") as f:
        json.dump(specs, f, indent=2)
    print(f"[randomizer] {len(configs)} scene configs → {specs_path}")

    # Summary stats
    summary = {
        "n_configs": len(configs),
        "generated_at": datetime.now().isoformat(),
        "cube_x_range": [min(c.cube_x for c in configs), max(c.cube_x for c in configs)],
        "cube_y_range": [min(c.cube_y for c in configs), max(c.cube_y for c in configs)],
        "light_intensity_range": [min(c.light_intensity for c in configs),
                                    max(c.light_intensity for c in configs)],
        "n_with_distractors": sum(c.n_distractor_objects > 0 for c in configs),
    }
    with open(out / "randomization_summary.json", "w") as f:
        json.dump(summary, f, indent=2)


# ── SDG wrapper ───────────────────────────────────────────────────────────────

def run_randomized_sdg(n_demos: int, output_dir: str, strategy: str, seed: int) -> None:
    """Generate scene configs and invoke genesis_sdg_planned.py for each batch."""
    print(f"[randomizer] Generating {n_demos} demos with strategy={strategy}, seed={seed}")

    r = SceneRandomizer(seed)
    configs = r.generate_batch(n_demos, strategy)
    write_scene_specs(output_dir, configs)

    print(f"[randomizer] Scene specs written. To run Genesis SDG:")
    print(f"  CUDA_VISIBLE_DEVICES=4 python3 src/simulation/genesis_sdg_planned.py \\")
    print(f"    --n-demos {n_demos} \\")
    print(f"    --scene-config {output_dir}/scene_configs.json \\")
    print(f"    --output {output_dir}/raw_demos")
    print(f"\n  Note: genesis_sdg_planned.py must be updated to accept --scene-config.")
    print(f"  Without that flag, use the scene_configs.json to manually set parameters.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scene randomizer for GR00T SDG diversity")
    parser.add_argument("--n-demos",        type=int, default=100)
    parser.add_argument("--output",         default="/tmp/randomized_sdg")
    parser.add_argument("--strategy",       default="full",
                        choices=["clean","position","lighting","camera","physics","full"])
    parser.add_argument("--seed",           type=int, default=42)
    parser.add_argument("--preview",        action="store_true", help="Preview stats only (no Genesis)")
    parser.add_argument("--n-variations",   type=int, default=20, help="Variations for --preview")
    parser.add_argument("--randomize-all",    action="store_true")
    parser.add_argument("--randomize-lighting", action="store_true")
    parser.add_argument("--randomize-camera",   action="store_true")
    parser.add_argument("--randomize-position", action="store_true")
    args = parser.parse_args()

    # Strategy override from flags
    if args.randomize_all:
        args.strategy = "full"
    elif args.randomize_lighting:
        args.strategy = "lighting"
    elif args.randomize_camera:
        args.strategy = "camera"
    elif args.randomize_position:
        args.strategy = "position"

    if args.preview:
        preview_variations(args.n_variations, args.seed)
    else:
        run_randomized_sdg(args.n_demos, args.output, args.strategy, args.seed)


if __name__ == "__main__":
    main()

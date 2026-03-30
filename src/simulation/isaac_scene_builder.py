"""
isaac_scene_builder.py — Isaac Sim USD scene configuration builder

High-level CLI + API for generating scene config JSON files used as input
to genesis_sdg_planned.py for Isaac Sim SDG (Synthetic Data Generation).

Usage:
    python isaac_scene_builder.py --preset standard --n-scenes 10 --output /tmp/scenes.json
    python isaac_scene_builder.py --preset curriculum_hard --n-scenes 50 --output /tmp/hard_scenes.json
    python isaac_scene_builder.py --list-presets
    python isaac_scene_builder.py --validate /tmp/scenes.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SceneObject:
    name: str
    type: str                          # cube / sphere / cylinder / table / robot
    position: List[float]              # [x, y, z]
    rotation_euler: List[float]        # [rx, ry, rz] degrees
    scale: List[float]                 # [sx, sy, sz]
    material: str = "default"          # default / metal / plastic / rubber / glass
    color_rgb: List[float] = field(default_factory=lambda: [0.8, 0.8, 0.8])
    physics: bool = True
    mass_kg: float = 0.5

    def validate(self) -> List[str]:
        errors: List[str] = []
        valid_types = {"cube", "sphere", "cylinder", "table", "robot"}
        valid_materials = {"default", "metal", "plastic", "rubber", "glass"}
        if self.type not in valid_types:
            errors.append(f"Object '{self.name}': unknown type '{self.type}'. Must be one of {valid_types}.")
        if self.material not in valid_materials:
            errors.append(f"Object '{self.name}': unknown material '{self.material}'. Must be one of {valid_materials}.")
        if len(self.position) != 3:
            errors.append(f"Object '{self.name}': position must have 3 elements.")
        if len(self.rotation_euler) != 3:
            errors.append(f"Object '{self.name}': rotation_euler must have 3 elements.")
        if len(self.scale) != 3:
            errors.append(f"Object '{self.name}': scale must have 3 elements.")
        if len(self.color_rgb) != 3:
            errors.append(f"Object '{self.name}': color_rgb must have 3 elements.")
        if not all(0.0 <= c <= 1.0 for c in self.color_rgb):
            errors.append(f"Object '{self.name}': color_rgb values must be in [0, 1].")
        if self.mass_kg <= 0:
            errors.append(f"Object '{self.name}': mass_kg must be positive.")
        return errors


@dataclass
class IsaacScene:
    scene_id: str
    robot_type: str                          # franka / ur5e / xarm7
    lighting: str                            # studio / outdoor / warehouse / random
    camera_configs: List[Dict[str, Any]]
    objects: List[SceneObject]
    domain_randomization: bool = False
    n_variants: int = 1

    def validate(self) -> List[str]:
        errors: List[str] = []
        valid_robots = {"franka", "ur5e", "xarm7"}
        valid_lighting = {"studio", "outdoor", "warehouse", "random"}
        if self.robot_type not in valid_robots:
            errors.append(f"Scene '{self.scene_id}': unknown robot_type '{self.robot_type}'. Must be one of {valid_robots}.")
        if self.lighting not in valid_lighting:
            errors.append(f"Scene '{self.scene_id}': unknown lighting '{self.lighting}'. Must be one of {valid_lighting}.")
        if self.n_variants < 1:
            errors.append(f"Scene '{self.scene_id}': n_variants must be >= 1.")
        for cam in self.camera_configs:
            for key in ("fov", "pos", "target"):
                if key not in cam:
                    errors.append(f"Scene '{self.scene_id}': camera config missing key '{key}'.")
        for obj in self.objects:
            errors.extend(obj.validate())
        return errors


# ---------------------------------------------------------------------------
# SceneBuilder
# ---------------------------------------------------------------------------

class SceneBuilder:
    """Fluent builder for IsaacScene configurations."""

    def __init__(
        self,
        scene_id: Optional[str] = None,
        robot_type: str = "franka",
        n_variants: int = 1,
        domain_randomization: bool = False,
    ):
        self.scene_id = scene_id or str(uuid.uuid4())[:8]
        self.robot_type = robot_type
        self.n_variants = n_variants
        self.domain_randomization = domain_randomization
        self._lighting: str = "studio"
        self._objects: List[SceneObject] = []
        self._cameras: List[Dict[str, Any]] = []
        self._object_counter: Dict[str, int] = {}

    # -- helpers -----------------------------------------------------------

    def _next_name(self, prefix: str) -> str:
        idx = self._object_counter.get(prefix, 0)
        self._object_counter[prefix] = idx + 1
        return f"{prefix}_{idx}"

    # -- public API --------------------------------------------------------

    def add_table(
        self,
        height: float = 0.7,
        width: float = 1.2,
        depth: float = 0.8,
    ) -> "SceneBuilder":
        """Add a table centered at origin."""
        self._objects.append(SceneObject(
            name=self._next_name("table"),
            type="table",
            position=[0.0, 0.0, height / 2.0],
            rotation_euler=[0.0, 0.0, 0.0],
            scale=[width, depth, height],
            material="default",
            color_rgb=[0.55, 0.45, 0.35],
            physics=False,
            mass_kg=20.0,
        ))
        return self

    def add_cube(
        self,
        x: float,
        y: float,
        rotation: float = 0.0,
        color: Optional[List[float]] = None,
        table_height: float = 0.7,
        size: float = 0.05,
    ) -> "SceneBuilder":
        """Add a cube on the table surface (z is auto-set to table top + half-height)."""
        if color is None:
            color = [0.2, 0.5, 0.9]
        self._objects.append(SceneObject(
            name=self._next_name("cube"),
            type="cube",
            position=[x, y, table_height + size / 2.0],
            rotation_euler=[0.0, 0.0, rotation],
            scale=[size, size, size],
            material="plastic",
            color_rgb=color,
            physics=True,
            mass_kg=0.1,
        ))
        return self

    def add_distractors(
        self,
        n: int,
        rng: random.Random,
        table_height: float = 0.7,
        x_range: float = 0.4,
        y_range: float = 0.3,
    ) -> "SceneBuilder":
        """Add N random small distractor objects (spheres/cylinders) on the table."""
        distractor_types = ["sphere", "cylinder"]
        distractor_materials = ["rubber", "plastic", "metal"]
        for _ in range(n):
            obj_type = rng.choice(distractor_types)
            size = rng.uniform(0.025, 0.045)
            color = [rng.uniform(0.1, 0.9) for _ in range(3)]
            self._objects.append(SceneObject(
                name=self._next_name("distractor"),
                type=obj_type,
                position=[
                    rng.uniform(-x_range, x_range),
                    rng.uniform(-y_range, y_range),
                    table_height + size / 2.0,
                ],
                rotation_euler=[0.0, 0.0, rng.uniform(0.0, 360.0)],
                scale=[size, size, size],
                material=rng.choice(distractor_materials),
                color_rgb=color,
                physics=True,
                mass_kg=0.05,
            ))
        return self

    def set_lighting(self, mode: str, randomize: bool = False) -> "SceneBuilder":
        """Set lighting mode. If randomize=True, overrides mode to 'random'."""
        if randomize:
            self._lighting = "random"
        else:
            self._lighting = mode
        return self

    def add_camera(
        self,
        name: str,
        position: List[float],
        target: List[float],
        fov: float = 60.0,
    ) -> "SceneBuilder":
        """Register a camera configuration."""
        self._cameras.append({"name": name, "fov": fov, "pos": position, "target": target})
        return self

    def build(self) -> IsaacScene:
        """Finalize and return the IsaacScene."""
        cameras = self._cameras if self._cameras else [
            {"name": "front", "fov": 60.0, "pos": [1.2, 0.0, 1.0], "target": [0.0, 0.0, 0.7]}
        ]
        return IsaacScene(
            scene_id=self.scene_id,
            robot_type=self.robot_type,
            lighting=self._lighting,
            camera_configs=cameras,
            objects=list(self._objects),
            domain_randomization=self.domain_randomization,
            n_variants=self.n_variants,
        )

    def to_json(self) -> str:
        """Serialize built scene to JSON string."""
        scene = self.build()
        data = asdict(scene)
        return json.dumps(data, indent=2)

    @staticmethod
    def from_json(s: str) -> IsaacScene:
        """Deserialize an IsaacScene from a JSON string."""
        data = json.loads(s)
        objects = [SceneObject(**obj) for obj in data.get("objects", [])]
        data["objects"] = objects
        return IsaacScene(**data)


# ---------------------------------------------------------------------------
# Preset scenes
# ---------------------------------------------------------------------------

def preset_standard(rng: Optional[random.Random] = None, n_variants: int = 1) -> IsaacScene:
    """Single cube, studio lighting, front camera, 1 distractor."""
    if rng is None:
        rng = random.Random(42)
    builder = SceneBuilder(robot_type="franka", n_variants=n_variants)
    builder.add_table()
    builder.add_cube(0.1, 0.0, rotation=rng.uniform(0, 360))
    builder.add_distractors(1, rng)
    builder.set_lighting("studio")
    builder.add_camera("front", [1.2, 0.0, 1.0], [0.0, 0.0, 0.7], fov=60)
    return builder.build()


def preset_curriculum_easy(rng: Optional[random.Random] = None, n_variants: int = 1) -> IsaacScene:
    """Cube near center, bright studio lighting, no distractors."""
    if rng is None:
        rng = random.Random(42)
    builder = SceneBuilder(robot_type="franka", n_variants=n_variants)
    builder.add_table()
    builder.add_cube(0.05, 0.0, rotation=0.0, color=[0.2, 0.7, 0.3])
    builder.set_lighting("studio")
    builder.add_camera("front", [1.0, 0.0, 1.1], [0.0, 0.0, 0.7], fov=55)
    return builder.build()


def preset_curriculum_hard(rng: Optional[random.Random] = None, n_variants: int = 1) -> IsaacScene:
    """Cube at table edge, random lighting, 3 distractors, ±30° rotation."""
    if rng is None:
        rng = random.Random(42)
    builder = SceneBuilder(
        robot_type="franka",
        n_variants=n_variants,
        domain_randomization=True,
    )
    builder.add_table()
    edge_x = rng.choice([-0.35, 0.35])
    rotation = rng.uniform(-30.0, 30.0)
    builder.add_cube(edge_x, rng.uniform(-0.2, 0.2), rotation=rotation, color=[0.9, 0.2, 0.2])
    builder.add_distractors(3, rng)
    builder.set_lighting("random", randomize=True)
    builder.add_camera("front", [1.2, 0.0, 1.0], [0.0, 0.0, 0.7], fov=60)
    return builder.build()


def preset_multi_camera(rng: Optional[random.Random] = None, n_variants: int = 1) -> IsaacScene:
    """3 cameras (front/side/overhead), domain randomization enabled, 2 distractors."""
    if rng is None:
        rng = random.Random(42)
    builder = SceneBuilder(
        robot_type="franka",
        n_variants=n_variants,
        domain_randomization=True,
    )
    builder.add_table()
    builder.add_cube(0.1, 0.05, rotation=rng.uniform(0, 360))
    builder.add_distractors(2, rng)
    builder.set_lighting("warehouse")
    builder.add_camera("front",    [1.2, 0.0, 1.0], [0.0, 0.0, 0.7], fov=60)
    builder.add_camera("side",     [0.0, 1.2, 1.0], [0.0, 0.0, 0.7], fov=60)
    builder.add_camera("overhead", [0.0, 0.0, 1.8], [0.0, 0.0, 0.7], fov=75)
    return builder.build()


PRESETS: Dict[str, Any] = {
    "standard":        preset_standard,
    "curriculum_easy": preset_curriculum_easy,
    "curriculum_hard": preset_curriculum_hard,
    "multi_camera":    preset_multi_camera,
}


# ---------------------------------------------------------------------------
# batch_generate
# ---------------------------------------------------------------------------

def batch_generate(
    preset_fn,
    n_scenes: int,
    seed: int = 0,
) -> List[IsaacScene]:
    """
    Generate n_scenes IsaacScene objects by calling preset_fn with varied RNG seeds.

    Each scene gets its own seeded RNG derived from (seed + i), so results are
    reproducible but diverse.
    """
    scenes: List[IsaacScene] = []
    for i in range(n_scenes):
        rng = random.Random(seed + i)
        scene = preset_fn(rng=rng, n_variants=1)
        # Stamp a deterministic scene_id
        scene.scene_id = f"scene_{seed:04d}_{i:04d}"
        scenes.append(scene)
    return scenes


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def scenes_to_json(scenes: List[IsaacScene]) -> str:
    return json.dumps([asdict(s) for s in scenes], indent=2)


def scenes_from_json(s: str) -> List[IsaacScene]:
    data = json.loads(s)
    result: List[IsaacScene] = []
    for item in data:
        objects = [SceneObject(**obj) for obj in item.get("objects", [])]
        item["objects"] = objects
        result.append(IsaacScene(**item))
    return result


def validate_scenes_file(path: str) -> bool:
    """Load a scenes JSON file and validate every scene. Prints errors and returns True if valid."""
    with open(path) as f:
        raw = f.read()
    try:
        scenes = scenes_from_json(raw)
    except Exception as exc:
        print(f"[FAIL] JSON parse error: {exc}", file=sys.stderr)
        return False

    all_errors: List[str] = []
    for scene in scenes:
        all_errors.extend(scene.validate())

    if all_errors:
        print(f"[FAIL] {len(all_errors)} validation error(s) in {len(scenes)} scene(s):")
        for err in all_errors:
            print(f"  - {err}")
        return False

    print(f"[OK] {len(scenes)} scene(s) validated successfully.")
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Isaac Sim scene configuration builder for SDG pipelines.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--preset", choices=list(PRESETS.keys()), help="Preset scene to generate.")
    group.add_argument("--list-presets", action="store_true", help="List all available presets and exit.")
    group.add_argument("--validate", metavar="FILE", help="Validate a scenes JSON file and exit.")

    parser.add_argument("--n-scenes", type=int, default=10, help="Number of scenes to generate (default: 10).")
    parser.add_argument("--seed", type=int, default=0, help="Base random seed (default: 0).")
    parser.add_argument("--output", metavar="FILE", help="Output JSON file path.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_presets:
        print("Available presets:")
        descriptions = {
            "standard":        "Single cube, studio lighting, front camera, 1 distractor.",
            "curriculum_easy": "Cube near center, bright lighting, 0 distractors.",
            "curriculum_hard": "Cube at edge, random lighting, 3 distractors, ±30° rotation.",
            "multi_camera":    "3 cameras (front/side/overhead), domain randomization enabled.",
        }
        for name, desc in descriptions.items():
            print(f"  {name:<20} {desc}")
        sys.exit(0)

    if args.validate:
        ok = validate_scenes_file(args.validate)
        sys.exit(0 if ok else 1)

    if not args.preset:
        parser.error("--preset is required unless --list-presets or --validate is specified.")

    preset_fn = PRESETS[args.preset]
    scenes = batch_generate(preset_fn, n_scenes=args.n_scenes, seed=args.seed)
    output_json = scenes_to_json(scenes)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_json)
        print(f"Wrote {len(scenes)} scene(s) to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()

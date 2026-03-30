"""
Embodiment Configuration Manager
CLI + library for managing robot-specific configs for fine-tuning and inference.

Usage:
  python embodiment_config_manager.py --list
  python embodiment_config_manager.py --show franka_panda
  python embodiment_config_manager.py --register --from-yaml /path/to/robot.yaml
  python embodiment_config_manager.py --validate --robot ur5e --joint-pos "0.1 0.2 ..."
  python embodiment_config_manager.py --export-lerobot franka_panda
"""

import argparse
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class EmbodimentConfig:
    robot_id: str                          # e.g. "franka_panda", "ur5e", "custom"
    display_name: str
    n_arm_joints: int
    n_gripper_joints: int
    total_dof: int
    joint_names: List[str]
    joint_limits_min: List[float]          # radians (or meters for gripper)
    joint_limits_max: List[float]
    max_joint_velocity: List[float]        # rad/s
    gripper_open_value: float
    gripper_close_value: float
    action_normalization: Dict[str, List[float]]  # {"mean": [...], "std": [...]}
    end_effector_link: str
    home_position: List[float]
    urdf_path: Optional[str] = None
    notes: str = ""


# ---------------------------------------------------------------------------
# Built-in configs
# ---------------------------------------------------------------------------

def _franka_panda() -> EmbodimentConfig:
    joint_names = [f"panda_joint{i}" for i in range(1, 8)] + ["panda_finger_joint1", "panda_finger_joint2"]
    limits_min = [-2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973, 0.0, 0.0]
    limits_max = [ 2.8973,  1.7628,  2.8973, -0.0698,  2.8973,  3.7525,  2.8973, 0.08, 0.08]
    max_vel    = [2.175, 2.175, 2.175, 2.175, 2.610, 2.610, 2.610, 0.2, 0.2]
    home       = [0.0, -math.pi/4, 0.0, -3*math.pi/4, 0.0, math.pi/2, math.pi/4, 0.04, 0.04]
    mean = [0.0] * 9
    std  = [1.0] * 9
    return EmbodimentConfig(
        robot_id="franka_panda",
        display_name="Franka Panda",
        n_arm_joints=7,
        n_gripper_joints=2,
        total_dof=9,
        joint_names=joint_names,
        joint_limits_min=limits_min,
        joint_limits_max=limits_max,
        max_joint_velocity=max_vel,
        gripper_open_value=0.08,
        gripper_close_value=0.0,
        action_normalization={"mean": mean, "std": std},
        end_effector_link="panda_hand",
        home_position=home,
        notes="Standard Franka Research 3 / Panda arm with parallel jaw gripper.",
    )


def _ur5e() -> EmbodimentConfig:
    joint_names = ["shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint",
                   "wrist_1_joint", "wrist_2_joint", "wrist_3_joint",
                   "robotiq_finger_joint_l", "robotiq_finger_joint_r"]
    pi2 = 2 * math.pi
    limits_min = [-pi2] * 6 + [0.0, 0.0]
    limits_max = [ pi2] * 6 + [0.8, 0.8]
    max_vel    = [3.14, 3.14, 3.14, 6.28, 6.28, 6.28, 0.5, 0.5]
    home       = [0.0, -math.pi/2, math.pi/2, -math.pi/2, -math.pi/2, 0.0, 0.0, 0.0]
    mean = [0.0] * 8
    std  = [1.0] * 8
    return EmbodimentConfig(
        robot_id="ur5e",
        display_name="Universal Robots UR5e",
        n_arm_joints=6,
        n_gripper_joints=2,
        total_dof=8,
        joint_names=joint_names,
        joint_limits_min=limits_min,
        joint_limits_max=limits_max,
        max_joint_velocity=max_vel,
        gripper_open_value=0.0,
        gripper_close_value=0.8,
        action_normalization={"mean": mean, "std": std},
        end_effector_link="tool0",
        home_position=home,
        notes="UR5e collaborative arm with Robotiq 2F-85 gripper (finger angle units).",
    )


def _xarm7() -> EmbodimentConfig:
    joint_names = [f"joint{i}" for i in range(1, 8)] + ["drive_joint"]
    lim = 2.9671
    limits_min = [-lim, -2.0944, -lim, -0.1920, -lim, -1.6930, -lim, 0.0]
    limits_max = [ lim,  2.0944,  lim,  pi_val := math.pi,  lim,  3.1416,  lim, 0.85]
    max_vel    = [3.14, 3.14, 3.14, 3.14, 3.14, 3.14, 3.14, 1.0]
    home       = [0.0, 0.0, 0.0, math.pi/6, 0.0, math.pi/3, 0.0, 0.0]
    mean = [0.0] * 8
    std  = [1.0] * 8
    return EmbodimentConfig(
        robot_id="xarm7",
        display_name="UFACTORY xArm 7",
        n_arm_joints=7,
        n_gripper_joints=1,
        total_dof=8,
        joint_names=joint_names,
        joint_limits_min=limits_min,
        joint_limits_max=limits_max,
        max_joint_velocity=max_vel,
        gripper_open_value=0.0,
        gripper_close_value=0.85,
        action_normalization={"mean": mean, "std": std},
        end_effector_link="link_eef",
        home_position=home,
        notes="xArm 7 with single-finger xArm gripper (drive_joint angle 0-0.85 rad).",
    )


def _kinova_gen3() -> EmbodimentConfig:
    joint_names = [f"joint_{i}" for i in range(1, 8)] + ["finger_joint_1", "finger_joint_2"]
    lim = 2.4086
    limits_min = [-lim, -2.2408, -lim, -2.5744, -lim, -2.0943, -lim, 0.0, 0.0]
    limits_max = [ lim,  2.2408,  lim,  2.5744,  lim,  2.0943,  lim, 0.814, 0.814]
    max_vel    = [1.396, 1.396, 1.396, 1.396, 1.745, 1.745, 1.745, 0.4, 0.4]
    home       = [0.0, 0.2618, math.pi, -2.2689, 0.0, 0.9599, math.pi/2, 0.0, 0.0]
    mean = [0.0] * 9
    std  = [1.0] * 9
    return EmbodimentConfig(
        robot_id="kinova_gen3",
        display_name="Kinova Gen3 (Robotiq 2F-85)",
        n_arm_joints=7,
        n_gripper_joints=2,
        total_dof=9,
        joint_names=joint_names,
        joint_limits_min=limits_min,
        joint_limits_max=limits_max,
        max_joint_velocity=max_vel,
        gripper_open_value=0.0,
        gripper_close_value=0.814,
        action_normalization={"mean": mean, "std": std},
        end_effector_link="end_effector_link",
        home_position=home,
        notes="Kinova Gen3 7-DOF arm with Robotiq 2F-85 adaptive gripper.",
    )


BUILTIN_CONFIGS: Dict[str, EmbodimentConfig] = {
    cfg.robot_id: cfg
    for cfg in [_franka_panda(), _ur5e(), _xarm7(), _kinova_gen3()]
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

REGISTRY_PATH = Path.home() / ".cache" / "roboticsai" / "embodiment_registry.json"


class EmbodimentRegistry:
    """Persistent registry of robot embodiment configs backed by JSON."""

    def __init__(self, registry_path: Path = REGISTRY_PATH):
        self._path = registry_path
        self._cache: Dict[str, EmbodimentConfig] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        self._cache = {k: v for k, v in BUILTIN_CONFIGS.items()}
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text())
                for robot_id, data in raw.items():
                    self._cache[robot_id] = EmbodimentConfig(**data)
            except Exception as exc:
                print(f"[warn] Could not load registry {self._path}: {exc}", file=sys.stderr)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Only persist non-builtin entries (builtins are always re-added on load)
        persisted = {
            k: asdict(v)
            for k, v in self._cache.items()
            if k not in BUILTIN_CONFIGS
        }
        self._path.write_text(json.dumps(persisted, indent=2))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(self, config: EmbodimentConfig) -> None:
        """Register (or overwrite) a robot config."""
        self._cache[config.robot_id] = config
        self._save()
        print(f"[ok] Registered '{config.robot_id}' ({config.display_name})")

    def get(self, robot_id: str) -> EmbodimentConfig:
        if robot_id not in self._cache:
            raise KeyError(f"Unknown robot_id '{robot_id}'. Run --list to see available robots.")
        return self._cache[robot_id]

    def list_robots(self) -> List[str]:
        return sorted(self._cache.keys())

    # ------------------------------------------------------------------
    # Action normalization
    # ------------------------------------------------------------------

    def normalize_actions(self, robot_id: str, raw_actions: List[float]) -> List[float]:
        cfg = self.get(robot_id)
        mean = cfg.action_normalization["mean"]
        std  = cfg.action_normalization["std"]
        if len(raw_actions) != cfg.total_dof:
            raise ValueError(f"Expected {cfg.total_dof} values, got {len(raw_actions)}")
        return [(raw_actions[i] - mean[i]) / (std[i] if std[i] != 0 else 1.0)
                for i in range(cfg.total_dof)]

    def denormalize_actions(self, robot_id: str, normalized: List[float]) -> List[float]:
        cfg = self.get(robot_id)
        mean = cfg.action_normalization["mean"]
        std  = cfg.action_normalization["std"]
        if len(normalized) != cfg.total_dof:
            raise ValueError(f"Expected {cfg.total_dof} values, got {len(normalized)}")
        return [normalized[i] * std[i] + mean[i] for i in range(cfg.total_dof)]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_joints(self, robot_id: str, joint_positions: List[float]) -> List[str]:
        """Return list of violation strings; empty list means all joints are in-limits."""
        cfg = self.get(robot_id)
        if len(joint_positions) != cfg.total_dof:
            return [f"Length mismatch: expected {cfg.total_dof}, got {len(joint_positions)}"]
        violations = []
        for i, (pos, lo, hi, name) in enumerate(zip(
                joint_positions, cfg.joint_limits_min, cfg.joint_limits_max, cfg.joint_names)):
            if pos < lo or pos > hi:
                violations.append(
                    f"{name} (idx {i}): {pos:.4f} rad outside [{lo:.4f}, {hi:.4f}]"
                )
        return violations

    # ------------------------------------------------------------------
    # LeRobot export
    # ------------------------------------------------------------------

    def export_lerobot_format(self, robot_id: str) -> Dict:
        """Return a dict in LeRobot v2 robot_type config format."""
        cfg = self.get(robot_id)
        return {
            "robot_type": cfg.robot_id,
            "display_name": cfg.display_name,
            "n_arm_joints": cfg.n_arm_joints,
            "n_gripper_joints": cfg.n_gripper_joints,
            "total_dof": cfg.total_dof,
            "joint_names": cfg.joint_names,
            "joint_limits": {
                "min": cfg.joint_limits_min,
                "max": cfg.joint_limits_max,
            },
            "max_joint_velocity": cfg.max_joint_velocity,
            "gripper": {
                "open_value": cfg.gripper_open_value,
                "close_value": cfg.gripper_close_value,
            },
            "normalization": cfg.action_normalization,
            "end_effector_link": cfg.end_effector_link,
            "home_position": cfg.home_position,
        }


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _load_yaml_config(yaml_path: str) -> EmbodimentConfig:
    try:
        import yaml  # type: ignore
    except ImportError:
        print("[error] PyYAML is required for --from-yaml: pip install pyyaml", file=sys.stderr)
        sys.exit(1)
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return EmbodimentConfig(**data)


def _cmd_list(registry: EmbodimentRegistry) -> None:
    robots = registry.list_robots()
    print(f"Registered robots ({len(robots)}):")
    for rid in robots:
        cfg = registry.get(rid)
        builtin_flag = " [built-in]" if rid in BUILTIN_CONFIGS else ""
        print(f"  {rid:<22} {cfg.display_name}  ({cfg.total_dof} DOF){builtin_flag}")


def _cmd_show(registry: EmbodimentRegistry, robot_id: str) -> None:
    cfg = registry.get(robot_id)
    d = asdict(cfg)
    print(json.dumps(d, indent=2))


def _cmd_validate(registry: EmbodimentRegistry, robot_id: str, joint_pos_str: str) -> None:
    try:
        positions = [float(x) for x in joint_pos_str.split()]
    except ValueError:
        print("[error] --joint-pos must be space-separated floats", file=sys.stderr)
        sys.exit(1)
    violations = registry.validate_joints(robot_id, positions)
    if not violations:
        print(f"[ok] All {len(positions)} joints within limits for '{robot_id}'.")
    else:
        print(f"[warn] {len(violations)} violation(s) for '{robot_id}':")
        for v in violations:
            print(f"  - {v}")
        sys.exit(2)


def _cmd_export_lerobot(registry: EmbodimentRegistry, robot_id: str) -> None:
    result = registry.export_lerobot_format(robot_id)
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Embodiment Configuration Manager — register and query robot configs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List all registered robots")
    group.add_argument("--show", metavar="ROBOT_ID", help="Show full config as JSON")
    group.add_argument("--register", action="store_true", help="Register a new robot config")
    group.add_argument("--validate", action="store_true", help="Validate joint positions against limits")
    group.add_argument("--export-lerobot", metavar="ROBOT_ID", help="Export config in LeRobot v2 format")

    parser.add_argument("--from-yaml", metavar="PATH", help="YAML file for --register")
    parser.add_argument("--robot", metavar="ROBOT_ID", help="Robot ID for --validate")
    parser.add_argument("--joint-pos", metavar="\"J1 J2 ...\"", help="Space-separated joint positions for --validate")

    args = parser.parse_args()
    registry = EmbodimentRegistry()

    if args.list:
        _cmd_list(registry)

    elif args.show:
        _cmd_show(registry, args.show)

    elif args.register:
        if not args.from_yaml:
            parser.error("--register requires --from-yaml PATH")
        cfg = _load_yaml_config(args.from_yaml)
        registry.register(cfg)

    elif args.validate:
        if not args.robot:
            parser.error("--validate requires --robot ROBOT_ID")
        if not args.joint_pos:
            parser.error("--validate requires --joint-pos \"J1 J2 ...\"")
        _cmd_validate(registry, args.robot, args.joint_pos)

    elif args.export_lerobot:
        _cmd_export_lerobot(registry, args.export_lerobot)


if __name__ == "__main__":
    main()

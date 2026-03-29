"""
test_pipeline_units.py — Unit tests for OCI Robot Cloud pipeline components.

These tests run without GPU and without external services.
Suitable for CI and local development.

Run:
    pytest tests/test_pipeline_units.py -v
    python tests/test_pipeline_units.py  (no pytest required)
"""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

# Ensure src is on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "eval"))
sys.path.insert(0, str(ROOT / "src" / "training"))
sys.path.insert(0, str(ROOT / "src" / "sdk"))

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
_results = []


def test(name):
    def decorator(fn):
        try:
            fn()
            _results.append((name, True, None))
            print(f"  {PASS}  {name}")
        except Exception as e:
            _results.append((name, False, str(e)))
            print(f"  {FAIL}  {name}")
            print(f"       {e}")
        return fn
    return decorator


# ── closed_loop_eval: categorize_failure ──────────────────────────────────

@test("categorize_failure: z > 0.78 → success")
def _():
    from closed_loop_eval import categorize_failure
    assert categorize_failure(0.80) == "success"
    assert categorize_failure(0.90) == "success"


@test("categorize_failure: z in (0.74, 0.78] → partial")
def _():
    from closed_loop_eval import categorize_failure
    assert categorize_failure(0.75) == "partial"
    assert categorize_failure(0.77) == "partial"


@test("categorize_failure: z in [0.68, 0.74] → no_contact")
def _():
    from closed_loop_eval import categorize_failure
    assert categorize_failure(0.700) == "no_contact"
    assert categorize_failure(0.720) == "no_contact"


@test("categorize_failure: z < 0.68 → knocked_off")
def _():
    from closed_loop_eval import categorize_failure
    assert categorize_failure(0.60) == "knocked_off"
    assert categorize_failure(0.02) == "knocked_off"


# ── closed_loop_eval: run_mock_eval ───────────────────────────────────────

@test("run_mock_eval: returns list of N episode dicts with required keys")
def _():
    from closed_loop_eval import run_mock_eval
    results = run_mock_eval(num_episodes=5, max_steps=100)
    assert len(results) == 5
    required = {"episode", "success", "steps", "policy_latency_ms", "cube_final_z"}
    for r in results:
        missing = required - set(r.keys())
        assert not missing, f"Missing keys: {missing}"


@test("run_mock_eval: all results have valid cube_final_z (>= 0)")
def _():
    from closed_loop_eval import run_mock_eval
    results = run_mock_eval(num_episodes=10, max_steps=200)
    for r in results:
        assert r["cube_final_z"] >= 0, f"Negative cube_z: {r['cube_final_z']}"
        assert r["steps"] > 0


# ── genesis_to_lerobot: utility functions ────────────────────────────────

@test("genesis_to_lerobot: build_info_json returns valid LeRobot v2 info schema")
def _():
    from genesis_to_lerobot import build_info_json
    info = build_info_json(total_episodes=100, total_frames=5000, fps=20, img_size=256)
    assert info["total_episodes"] == 100
    assert info["fps"] == 20
    assert "action" in info["features"]
    assert info["features"]["action"]["shape"] == [9]
    assert "observation.state" in info["features"]
    assert "observation.images.agentview" in info["features"]


@test("genesis_to_lerobot: build_modality_json returns state/action/video keys")
def _():
    from genesis_to_lerobot import build_modality_json
    m = build_modality_json()
    assert "state" in m
    assert "action" in m
    assert "video" in m


# ── embodiment_adapter: normalize/denormalize ────────────────────────────

@test("embodiment_adapter: normalize_joints maps to [-1, 1] range")
def _():
    from embodiment_adapter import normalize_joints
    limits = [(-2.9, 2.9)] * 7 + [(0.0, 0.04)] * 2
    q_mid = np.array([0.0] * 7 + [0.02, 0.02], dtype=np.float32)
    n = normalize_joints(q_mid, limits)
    assert n.shape == (9,)
    # Midpoint should be near 0
    assert np.all(np.abs(n[:7]) < 0.1), f"Mid joints should normalize near 0, got {n[:7]}"


@test("embodiment_adapter: denormalize_joints is inverse of normalize")
def _():
    from embodiment_adapter import normalize_joints, denormalize_joints
    limits = [(-2.9, 2.9)] * 7 + [(0.0, 0.04)] * 2
    q_orig = np.array([1.5, -0.7, 0.3, -1.2, 0.8, 2.1, -0.4, 0.03, 0.01], dtype=np.float32)
    q_rt = denormalize_joints(normalize_joints(q_orig, limits), limits)
    assert np.allclose(q_orig, q_rt, atol=1e-5), f"Round-trip failed: {q_orig} vs {q_rt}"


# ── results_aggregator: HTML generation ──────────────────────────────────

@test("results_aggregator: make_html generates valid HTML with all labels")
def _():
    from results_aggregator import make_html
    summaries = [
        {"n_episodes": 20, "n_success": 1, "success_rate": 0.05,
         "episodes": [{"success": i == 0, "max_cube_z": 0.80 if i == 0 else 0.71}
                      for i in range(20)]},
        {"n_episodes": 20, "n_success": 6, "success_rate": 0.30,
         "episodes": [{"success": i < 6, "max_cube_z": 0.85 if i < 6 else 0.70}
                      for i in range(20)]},
    ]
    labels = ["BC baseline", "1000-demo BC"]
    html = make_html(labels, summaries, dagger_data=None)
    assert "BC baseline" in html
    assert "1000-demo BC" in html
    assert "5%" in html or "30%" in html
    assert "<html" in html.lower()


@test("results_aggregator: make_html handles DAgger results section")
def _():
    from results_aggregator import make_html
    summaries = [{"n_episodes": 20, "n_success": 1, "success_rate": 0.05, "episodes": []}]
    labels = ["BC"]
    dagger_data = {
        "results": [
            {"iter": 1, "beta": 0.40, "success_rate": 0.52, "avg_diverged_steps": 22.8},
            {"iter": 2, "beta": 0.28, "success_rate": 0.55, "avg_diverged_steps": 17.4},
        ]
    }
    html = make_html(labels, summaries, dagger_data=dagger_data)
    assert "DAgger" in html
    assert "0.40" in html


# ── results_aggregator: file loading ──────────────────────────────────────

@test("results_aggregator: load_eval_dir reads summary.json")
def _():
    from results_aggregator import load_eval_dir
    with tempfile.TemporaryDirectory() as tmp:
        summary = {
            "n_episodes": 20, "n_success": 3, "success_rate": 0.15,
            "episodes": [{"success": i < 3, "max_cube_z": 0.82 if i < 3 else 0.70}
                         for i in range(20)],
        }
        (Path(tmp) / "summary.json").write_text(json.dumps(summary))
        data = load_eval_dir(Path(tmp))
        assert data is not None
        assert data["n_success"] == 3
        assert data["success_rate"] == 0.15


# ── SDK: data_utils ───────────────────────────────────────────────────────

@test("data_utils: episode_count returns 0 for empty directory")
def _():
    from oci_robot_cloud.data_utils import episode_count
    with tempfile.TemporaryDirectory() as tmp:
        count = episode_count(tmp)
        assert count == 0, f"Expected 0, got {count}"


@test("data_utils: inspect returns dict with keys for valid lerobot dir")
def _():
    from oci_robot_cloud.data_utils import inspect
    with tempfile.TemporaryDirectory() as tmp:
        # Create minimal LeRobot v2 structure
        meta = Path(tmp) / "meta"
        meta.mkdir()
        (meta / "info.json").write_text(json.dumps({
            "total_episodes": 10, "total_frames": 500, "fps": 20
        }))
        result = inspect(tmp)
        assert isinstance(result, dict)


# ── SDK: RobotCloudClient init ────────────────────────────────────────────

@test("RobotCloudClient: initializes with custom base_url")
def _():
    from oci_robot_cloud.client import RobotCloudClient
    client = RobotCloudClient(base_url="http://localhost:9999")
    assert "localhost:9999" in client.base_url


# ── dagger_train: episode length filter ───────────────────────────────────

@test("dagger_train: MIN_FRAMES constant is accessible (>= 5)")
def _():
    # The filter was added in this session — verify the source was updated
    import re
    src = (ROOT / "src" / "training" / "dagger_train.py").read_text()
    match = re.search(r"MIN_FRAMES\s*=\s*(\d+)", src)
    assert match, "MIN_FRAMES not found in dagger_train.py"
    assert int(match.group(1)) >= 5, f"MIN_FRAMES too small: {match.group(1)}"


# ── Results summary ───────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\nOCI Robot Cloud — Unit Tests")
    print("=" * 55)
    n_pass = sum(1 for _, ok, _ in _results if ok)
    n_fail = sum(1 for _, ok, _ in _results if not ok)
    print(f"\n{'='*55}")
    print(f"Results: {n_pass} passed, {n_fail} failed / {len(_results)} total")
    if n_fail:
        print("\nFailed tests:")
        for name, ok, err in _results:
            if not ok:
                print(f"  ✗ {name}")
                print(f"    {err}")
        sys.exit(1)
    else:
        print("All tests passed.")

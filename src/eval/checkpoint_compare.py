#!/usr/bin/env python3
"""
checkpoint_compare.py — Head-to-head comparison of two GR00T checkpoints.

Spawns both checkpoints as inference servers on different ports, runs the same
N episodes against each, and produces a side-by-side HTML report.

Usage:
    python src/eval/checkpoint_compare.py \
        --ckpt-a /tmp/finetune_500_5k/checkpoint-5000 \
        --name-a "500-demo BC" \
        --ckpt-b /tmp/finetune_1000_5k/checkpoint-5000 \
        --name-b "1000-demo BC" \
        --num-episodes 20 \
        --output /tmp/compare_report

Or compare against a running server:
    python src/eval/checkpoint_compare.py \
        --server-a http://localhost:8002 \
        --name-a "BC baseline" \
        --server-b http://localhost:8003 \
        --name-b "DAgger iter3" \
        --num-episodes 20

Options:
    --ckpt-a / --ckpt-b     Checkpoint paths (script auto-starts servers on ports 8010/8011)
    --server-a / --server-b Pre-running server URLs (skip auto-launch)
    --num-episodes N        Episodes per checkpoint (default: 20)
    --seed INT              Random seed for cube positions (same seed used for both)
    --output DIR            Output directory for HTML report + JSON data
    --gpu-id INT            GPU for auto-launched servers (default: 4)
    --port-a / --port-b     Ports for auto-launched servers (default: 8010/8011)
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import genesis as gs

# ── Constants ─────────────────────────────────────────────────────────────────
TABLE_Z = 0.700
CUBE_HALF = 0.025
LIFT_THRESHOLD = TABLE_Z + 0.15
ROBOT_URDF = "urdf/panda/panda.urdf"
SERVER_SCRIPT = Path(__file__).resolve().parents[1] / "inference" / "groot_franka_server.py"
GROOT_PYTHON = Path(os.environ.get("GROOT_REPO", "/home/ubuntu/Isaac-GR00T")) / ".venv" / "bin" / "python3"
if not GROOT_PYTHON.exists():
    GROOT_PYTHON = Path("python3")


# ── Genesis scene ─────────────────────────────────────────────────────────────

def build_scene():
    gs.init(backend=gs.cuda, logging_level="warning")
    scene = gs.Scene(
        sim_options=gs.options.SimOptions(dt=0.01, substeps=2),
        viewer_options=gs.options.ViewerOptions(res=(512, 512), max_FPS=60),
        show_viewer=False,
    )
    plane = scene.add_entity(gs.morphs.Plane())
    table = scene.add_entity(
        gs.morphs.Box(size=(0.8, 0.8, TABLE_Z * 2), fixed=True),
        material=gs.materials.Rigid(),
    )
    table.set_pos([0.5, 0.0, TABLE_Z])
    robot = scene.add_entity(
        gs.morphs.URDF(file=ROBOT_URDF, fixed=True),
        material=gs.materials.Rigid(),
    )
    cube = scene.add_entity(
        gs.morphs.Box(size=(CUBE_HALF * 2,) * 3),
        material=gs.materials.Rigid(rho=500),
    )
    cam = scene.add_camera(
        res=(256, 256),
        pos=(1.0, 0.0, 1.3),
        lookat=(0.5, 0.0, TABLE_Z),
        fov=60,
        GUI=False,
    )
    scene.build()
    return scene, robot, cube, cam


# ── Server management ─────────────────────────────────────────────────────────

def launch_server(ckpt_path: str, port: int, gpu_id: int) -> subprocess.Popen:
    """Launch a GR00T inference server in a subprocess."""
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    cmd = [
        str(GROOT_PYTHON), str(SERVER_SCRIPT),
        "--model-path", ckpt_path,
        "--port", str(port),
    ]
    print(f"  [compare] Launching server on port {port}: {ckpt_path}")
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc


def wait_for_server(url: str, timeout: int = 120) -> bool:
    """Poll server health endpoint until ready."""
    import urllib.request
    import urllib.error
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(f"{url}/health", timeout=2)
            return True
        except Exception:
            time.sleep(3)
    return False


# ── Single-episode rollout ─────────────────────────────────────────────────────

def query_server(url: str, rgb: np.ndarray, instruction: str = "pick up the red cube"):
    """Send frame to GR00T server, return (arm_actions, gripper_actions) arrays."""
    import io, struct
    import urllib.request
    import urllib.parse
    from PIL import Image

    # Encode frame as JPEG
    img = Image.fromarray(rgb)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    img_bytes = buf.getvalue()

    # Multipart form
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="frame.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + img_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="instruction"\r\n\r\n'
        f"{instruction}\r\n--{boundary}--\r\n"
    ).encode()

    req = urllib.request.Request(
        f"{url}/predict",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    arm = np.array(data["arm"], dtype=np.float32)     # (16, 7)
    gripper = np.array(data["gripper"], dtype=np.float32)  # (16, 2)
    return arm, gripper


def rollout_episode(scene, robot, cube, cam, server_url: str, seed: int,
                    max_steps: int = 100) -> dict:
    """Run one episode and return result dict."""
    rng = np.random.default_rng(seed)
    cube_x = 0.5 + rng.uniform(-0.10, 0.10)
    cube_y = rng.uniform(-0.10, 0.10)
    cube.set_pos([cube_x, cube_y, TABLE_Z + CUBE_HALF])

    # Reset robot to home
    home = np.array([0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785, 0.04, 0.04])
    robot.control_dofs_position(home.astype(np.float64), dofs_idx_local=list(range(9)))
    for _ in range(10):
        scene.step()

    chunk_arm = None
    chunk_grip = None
    chunk_step = 0
    max_cube_z = TABLE_Z + CUBE_HALF

    for step_i in range(max_steps):
        rgb = cam.render(rgb=True, depth=False, segmentation=False, normal=False)
        if hasattr(rgb, "cpu"):
            rgb = rgb.cpu().numpy()

        if chunk_arm is None or chunk_step >= 16:
            try:
                chunk_arm, chunk_grip = query_server(server_url, rgb)
                chunk_step = 0
            except Exception:
                q = robot.get_dofs_position()
                if hasattr(q, "cpu"):
                    q = q.cpu()
                q = np.array(q).flatten()
                chunk_arm = np.tile(q[:7], (16, 1))
                chunk_grip = np.tile(q[7:9], (16, 1))

        action = np.concatenate([chunk_arm[chunk_step], chunk_grip[chunk_step]])
        chunk_step += 1

        robot.control_dofs_position(action.astype(np.float64), dofs_idx_local=list(range(9)))
        for _ in range(2):
            scene.step()

        cp = cube.get_pos()
        if hasattr(cp, "cpu"):
            cp = cp.cpu()
        cube_z = float(np.array(cp).flatten()[2])
        max_cube_z = max(max_cube_z, cube_z)

        if cube_z >= LIFT_THRESHOLD:
            return {"success": True, "steps": step_i + 1, "final_cube_z": cube_z,
                    "max_cube_z": max_cube_z}

    return {"success": False, "steps": max_steps, "final_cube_z": cube_z,
            "max_cube_z": max_cube_z}


def run_eval(scene, robot, cube, cam, server_url: str, n_episodes: int,
             base_seed: int = 42) -> list:
    """Run N episodes against a server, return list of result dicts."""
    results = []
    n_success = 0
    for ep_i in range(n_episodes):
        r = rollout_episode(scene, robot, cube, cam, server_url,
                            seed=base_seed + ep_i)
        results.append(r)
        n_success += r["success"]
        status = "✓" if r["success"] else "✗"
        print(f"    ep {ep_i+1:02d}/{n_episodes}: {status}  cube_z={r['final_cube_z']:.3f}", flush=True)
    print(f"  Success: {n_success}/{n_episodes} ({100*n_success/n_episodes:.0f}%)")
    return results


# ── HTML report ───────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Checkpoint Comparison — OCI Robot Cloud</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0;
         margin: 0; padding: 24px; }}
  h1 {{ color: #C74634; margin-bottom: 4px; }}
  .subtitle {{ color: #9ca3af; margin-bottom: 32px; font-size: 0.9em; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 32px; }}
  .card {{ background: #16213e; border-radius: 10px; padding: 20px;
           border-left: 4px solid {color_a}; }}
  .card.b {{ border-left-color: {color_b}; }}
  .card h2 {{ margin: 0 0 12px; font-size: 1.1em; color: #f3f4f6; }}
  .big {{ font-size: 3em; font-weight: bold; margin: 8px 0; }}
  .big.success {{ color: #10b981; }}
  .big.fail {{ color: #ef4444; }}
  .meta {{ color: #9ca3af; font-size: 0.85em; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 32px; }}
  th {{ background: #C74634; color: white; padding: 10px 14px; text-align: left; }}
  td {{ padding: 8px 14px; border-bottom: 1px solid #2d3748; }}
  tr:nth-child(even) td {{ background: #1a2744; }}
  .winner {{ color: #10b981; font-weight: bold; }}
  .loser {{ color: #6b7280; }}
  .episode-grid {{ display: grid; grid-template-columns: repeat(auto-fill, 44px); gap: 4px; }}
  .ep {{ width: 40px; height: 40px; border-radius: 6px; display: flex;
         align-items: center; justify-content: center; font-size: 0.7em; font-weight: bold; }}
  .ep.ok {{ background: #065f46; color: #6ee7b7; }}
  .ep.fail {{ background: #450a0a; color: #fca5a5; }}
  h3 {{ color: #9ca3af; text-transform: uppercase; letter-spacing: 0.08em;
        font-size: 0.8em; margin-bottom: 12px; }}
</style>
</head>
<body>
<h1>Checkpoint Comparison</h1>
<p class="subtitle">OCI Robot Cloud · GR00T closed-loop evaluation · {n_episodes} episodes each · seed={seed}</p>

<div class="grid">
  <div class="card">
    <h2>{name_a}</h2>
    <div class="big {class_a}">{success_a}/{n_episodes}</div>
    <div class="meta">success rate: {rate_a:.0%} &nbsp;·&nbsp; avg max_z: {avg_z_a:.3f}m</div>
  </div>
  <div class="card b">
    <h2>{name_b}</h2>
    <div class="big {class_b}">{success_b}/{n_episodes}</div>
    <div class="meta">success rate: {rate_b:.0%} &nbsp;·&nbsp; avg max_z: {avg_z_b:.3f}m</div>
  </div>
</div>

<h3>Summary</h3>
<table>
  <tr><th>Metric</th><th>{name_a}</th><th>{name_b}</th><th>Winner</th></tr>
  {summary_rows}
</table>

<h3>Episode Grid — {name_a}</h3>
<div class="episode-grid">{grid_a}</div>
<br>
<h3>Episode Grid — {name_b}</h3>
<div class="episode-grid">{grid_b}</div>

<br>
<h3>Per-Episode Data</h3>
<table>
  <tr><th>Ep</th>
      <th>{name_a} — success</th><th>{name_a} — cube_z</th>
      <th>{name_b} — success</th><th>{name_b} — cube_z</th></tr>
  {episode_rows}
</table>

<p class="meta">Generated by checkpoint_compare.py · OCI Robot Cloud</p>
</body>
</html>"""


def make_html(name_a: str, name_b: str, results_a: list, results_b: list,
              n_episodes: int, seed: int) -> str:
    sa = sum(r["success"] for r in results_a)
    sb = sum(r["success"] for r in results_b)
    rate_a = sa / n_episodes
    rate_b = sb / n_episodes
    avg_za = np.mean([r["max_cube_z"] for r in results_a])
    avg_zb = np.mean([r["max_cube_z"] for r in results_b])

    color_a = "#C74634"
    color_b = "#3b82f6"

    def winner_cell(va, vb, higher_better=True):
        if higher_better:
            if va > vb:
                return f'<span class="winner">{name_a}</span>'
            elif vb > va:
                return f'<span class="winner">{name_b}</span>'
        else:
            if va < vb:
                return f'<span class="winner">{name_a}</span>'
            elif vb < va:
                return f'<span class="winner">{name_b}</span>'
        return "tie"

    summary_rows = "\n".join([
        f"<tr><td>Success rate</td><td>{rate_a:.0%}</td><td>{rate_b:.0%}</td>"
        f"<td>{winner_cell(rate_a, rate_b)}</td></tr>",
        f"<tr><td>Successes</td><td>{sa}</td><td>{sb}</td>"
        f"<td>{winner_cell(sa, sb)}</td></tr>",
        f"<tr><td>Avg max cube z</td><td>{avg_za:.3f}m</td><td>{avg_zb:.3f}m</td>"
        f"<td>{winner_cell(avg_za, avg_zb)}</td></tr>",
        f"<tr><td>Best cube z</td>"
        f"<td>{max(r['max_cube_z'] for r in results_a):.3f}m</td>"
        f"<td>{max(r['max_cube_z'] for r in results_b):.3f}m</td>"
        f"<td>{winner_cell(max(r['max_cube_z'] for r in results_a), max(r['max_cube_z'] for r in results_b))}</td></tr>",
    ])

    def ep_grid(results):
        cells = []
        for i, r in enumerate(results):
            cls = "ok" if r["success"] else "fail"
            cells.append(f'<div class="ep {cls}">{i+1}</div>')
        return "".join(cells)

    episode_rows = "\n".join(
        f"<tr><td>{i+1}</td>"
        f"<td>{'✓' if results_a[i]['success'] else '✗'}</td>"
        f"<td>{results_a[i]['final_cube_z']:.3f}</td>"
        f"<td>{'✓' if results_b[i]['success'] else '✗'}</td>"
        f"<td>{results_b[i]['final_cube_z']:.3f}</td></tr>"
        for i in range(n_episodes)
    )

    class_a = "success" if rate_a > 0.2 else "fail"
    class_b = "success" if rate_b > 0.2 else "fail"

    return HTML_TEMPLATE.format(
        name_a=name_a, name_b=name_b,
        n_episodes=n_episodes, seed=seed,
        success_a=sa, success_b=sb,
        rate_a=rate_a, rate_b=rate_b,
        avg_z_a=avg_za, avg_z_b=avg_zb,
        class_a=class_a, class_b=class_b,
        color_a=color_a, color_b=color_b,
        summary_rows=summary_rows,
        grid_a=ep_grid(results_a),
        grid_b=ep_grid(results_b),
        episode_rows=episode_rows,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Compare two GR00T checkpoints head-to-head")
    parser.add_argument("--ckpt-a", help="Path to checkpoint A")
    parser.add_argument("--ckpt-b", help="Path to checkpoint B")
    parser.add_argument("--server-a", help="Pre-running server URL for A (skip auto-launch)")
    parser.add_argument("--server-b", help="Pre-running server URL for B (skip auto-launch)")
    parser.add_argument("--name-a", default="Checkpoint A")
    parser.add_argument("--name-b", default="Checkpoint B")
    parser.add_argument("--num-episodes", type=int, default=20)
    parser.add_argument("--seed", type=int, default=100,
                        help="Base seed for cube positions (same for both checkpoints)")
    parser.add_argument("--output", default="/tmp/compare_report")
    parser.add_argument("--gpu-id", type=int, default=4)
    parser.add_argument("--port-a", type=int, default=8010)
    parser.add_argument("--port-b", type=int, default=8011)
    args = parser.parse_args()

    if not args.server_a and not args.ckpt_a:
        parser.error("Provide either --ckpt-a or --server-a")
    if not args.server_b and not args.ckpt_b:
        parser.error("Provide either --ckpt-b or --server-b")

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    procs = []
    url_a = args.server_a
    url_b = args.server_b

    try:
        # Auto-launch servers if checkpoint paths provided
        if args.ckpt_a:
            proc_a = launch_server(args.ckpt_a, args.port_a, args.gpu_id)
            procs.append(proc_a)
            url_a = f"http://localhost:{args.port_a}"

        if args.ckpt_b:
            proc_b = launch_server(args.ckpt_b, args.port_b, args.gpu_id)
            procs.append(proc_b)
            url_b = f"http://localhost:{args.port_b}"

        # Wait for servers
        for url, name in [(url_a, args.name_a), (url_b, args.name_b)]:
            print(f"  [compare] Waiting for {name} at {url}...")
            if not wait_for_server(url):
                print(f"  [compare] ERROR: {name} server did not become ready")
                sys.exit(1)
            print(f"  [compare] {name} ready")

        # Build Genesis scene (shared across both evals)
        print("\n[compare] Building Genesis scene...")
        scene, robot, cube, cam = build_scene()
        print("[compare] Scene ready\n")

        # Eval A
        print(f"[compare] Evaluating: {args.name_a}")
        results_a = run_eval(scene, robot, cube, cam, url_a,
                             args.num_episodes, args.seed)

        # Eval B
        print(f"\n[compare] Evaluating: {args.name_b}")
        results_b = run_eval(scene, robot, cube, cam, url_b,
                             args.num_episodes, args.seed)

    finally:
        for proc in procs:
            proc.terminate()

    # Save results
    data = {
        "name_a": args.name_a, "name_b": args.name_b,
        "num_episodes": args.num_episodes, "seed": args.seed,
        "results_a": results_a, "results_b": results_b,
        "summary": {
            "success_a": sum(r["success"] for r in results_a),
            "success_b": sum(r["success"] for r in results_b),
            "rate_a": sum(r["success"] for r in results_a) / args.num_episodes,
            "rate_b": sum(r["success"] for r in results_b) / args.num_episodes,
        }
    }
    json_path = out_dir / "comparison.json"
    json_path.write_text(json.dumps(data, indent=2))

    html_path = out_dir / "comparison.html"
    html_path.write_text(make_html(
        args.name_a, args.name_b, results_a, results_b,
        args.num_episodes, args.seed
    ))

    sa = data["summary"]["success_a"]
    sb = data["summary"]["success_b"]
    n = args.num_episodes
    print(f"\n{'='*50}")
    print(f"RESULTS: {args.name_a}: {sa}/{n} ({100*sa/n:.0f}%)  "
          f"vs  {args.name_b}: {sb}/{n} ({100*sb/n:.0f}%)")
    print(f"Report: {html_path}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()

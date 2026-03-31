#!/usr/bin/env python3
"""eval_groot_cl.py — Correct closed-loop eval (Genesis 0.4.3+, multipart server API)
OCI Robot Cloud — roboticsai

Server API: POST /predict multipart/form-data
  image       : JPEG file upload
  instruction : str

Returns: { arm: (16,7), gripper: (16,2), latency_ms, checkpoint }

Usage:
  python3 scripts/eval_groot_cl.py                           # prod port 8001
  python3 scripts/eval_groot_cl.py --server-url http://127.0.0.1:8003 --label dagger5
"""
import time, statistics, argparse, io
import numpy as np
import requests
from PIL import Image

MAX_STEPS = 200
LIFT_THRESH = 0.78   # cube center z (meters) — success threshold
N_EPISODES = 20

def query(server_url, rgb_array, lang="pick up the cube"):
    """Query GR00T server via multipart form-data. Returns (arm, grip, latency_s, ok)."""
    img = Image.fromarray(rgb_array.astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    try:
        t0 = time.time()
        r = requests.post(
            f"{server_url}/predict",
            files={"image": ("frame.jpg", buf, "image/jpeg")},
            data={"instruction": lang},
            timeout=5.0,
        )
        lat = time.time() - t0
        d = r.json()
        return np.array(d["arm"]), np.array(d["gripper"]), lat, True
    except Exception:
        return None, None, 0.0, False

def get_cube_z(cube):
    try:
        return float(cube.get_pos()[2])
    except Exception:
        return 0.0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-url", default="http://127.0.0.1:8001")
    parser.add_argument("--n-episodes", type=int, default=N_EPISODES)
    parser.add_argument("--label", default="production")
    args = parser.parse_args()

    import genesis as gs
    gs.init(backend=gs.cuda)

    successes = 0
    latencies = []
    policy_failures = 0

    for ep in range(args.n_episodes):
        # Genesis 0.4.3+: use SimOptions(dt=1/freq) instead of sim_freq= kwarg
        scene = gs.Scene(
            show_viewer=False,
            sim_options=gs.options.SimOptions(dt=0.02, substeps=2),
        )
        scene.add_entity(gs.morphs.Plane())
        robot = scene.add_entity(
            gs.morphs.MJCF(file="xml/franka_emika_panda/panda.xml"),
        )
        cube = scene.add_entity(
            gs.morphs.Box(size=(0.04, 0.04, 0.04), pos=(0.5, 0.0, 0.02)),
        )
        cam = scene.add_camera(
            res=(256, 256), pos=(1.5, 0, 1.5), lookat=(0.5, 0, 0.3),
            fov=45, GUI=False,
        )
        scene.build()

        success = False
        arm_chunk = None
        grip_chunk = None
        chunk_step = 0

        for step in range(MAX_STEPS):
            # cam.render(rgb=True) → 4-tuple in Genesis 0.4+
            rgb_res = cam.render(rgb=True)
            rgb = rgb_res[0] if isinstance(rgb_res, tuple) else rgb_res
            if rgb is None:
                break

            if arm_chunk is None or chunk_step >= 16:
                arm_chunk, grip_chunk, lat, ok = query(args.server_url, rgb)
                chunk_step = 0
                if ok:
                    latencies.append(lat)
                else:
                    policy_failures += 1
                    arm_chunk = None
                    scene.step()
                    continue

            act = np.concatenate([arm_chunk[chunk_step], grip_chunk[chunk_step]])
            chunk_step += 1
            robot.set_dofs_position(act)
            scene.step()

            if get_cube_z(cube) >= LIFT_THRESH:
                success = True
                break

        if success:
            successes += 1
        print(f"[{args.label}] ep {ep+1:2d}: {'SUCCESS' if success else 'fail'} "
              f"| SR: {successes}/{ep+1}")

    sr = successes / args.n_episodes * 100
    avg_lat = statistics.mean(latencies) * 1000 if latencies else 0
    pfr = policy_failures / max(len(latencies) + policy_failures, 1)

    print(f"\n{'='*50}")
    print(f"[{args.label.upper()}] EVAL COMPLETE")
    print(f"SR={sr:.1f}% ({successes}/{args.n_episodes})")
    print(f"Avg latency: {avg_lat:.0f}ms | Policy failure rate: {pfr:.3f}")
    print(f"Server: {args.server_url}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()

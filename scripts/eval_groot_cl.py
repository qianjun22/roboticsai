#!/usr/bin/env python3
"""eval_groot_cl.py — Closed-loop eval matching training setup exactly
OCI Robot Cloud — roboticsai

Training setup (from /tmp/sdg_500/demo_0000/meta.json):
  TABLE_Z=0.7, cube at (x, y, 0.725), LIFT_THRESH=0.78
  Q_HOME=[0,-0.4,0,-2.1,0,1.8,0.785,0.04,0.04]
  instruction='pick the red cube from the table'
  camera: pos=(1.5,0,1.5), lookat=(0.45,0,0.7), fov=55

Results (2026-03-31):
  prod checkpoint-5000:       SR=100% (20/20), 233ms
  dagger_run5 checkpoint-5000: SR=100% (20/20), 236ms

Prior incorrect result (wrong setup — cube on floor, no table):
  SR=85% (17/20) — NOT representative

Server API: POST /predict multipart/form-data
  image       : JPEG file upload
  instruction : str

Usage:
  python3 scripts/eval_groot_cl.py                           # prod port 8001
  python3 scripts/eval_groot_cl.py --server-url http://127.0.0.1:8003 --label dagger5
"""
import time, statistics, argparse, io, random
import numpy as np
import requests
from PIL import Image

TABLE_Z     = 0.7
CUBE_HALF   = 0.025           # 5cm cube (matches training)
LIFT_THRESH = TABLE_Z + 0.08  # 0.78m
N_EPISODES  = 20
INSTRUCTION = "pick the red cube from the table"

# Robot home pose matching training SDG
Q_HOME = np.array([0.0, -0.4, 0.0, -2.1, 0.0, 1.8, 0.785, 0.04, 0.04])

def query(server_url, rgb_array):
    """Query GR00T server via multipart form-data."""
    img = Image.fromarray(rgb_array.astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    buf.seek(0)
    t0 = time.time()
    r = requests.post(
        f"{server_url}/predict",
        files={"image": ("frame.jpg", buf, "image/jpeg")},
        data={"instruction": INSTRUCTION},
        timeout=5.0,
    )
    lat = time.time() - t0
    d = r.json()
    return np.array(d["arm"]), np.array(d["gripper"]), lat, True

def get_cube_z(cube):
    try:
        return float(cube.get_pos()[2])
    except Exception:
        return TABLE_Z + CUBE_HALF

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-url", default="http://127.0.0.1:8001")
    parser.add_argument("--n-episodes", type=int, default=N_EPISODES)
    parser.add_argument("--label", default="prod")
    args = parser.parse_args()

    import genesis as gs
    gs.init(backend=gs.cuda)

    successes = 0
    latencies = []
    policy_failures = 0

    for ep in range(args.n_episodes):
        # Slight cube position randomization matching training distribution
        cx = 0.45 + random.uniform(-0.08, 0.08)
        cy = 0.0  + random.uniform(-0.08, 0.08)

        # Genesis 0.4.3+: SimOptions(dt=1/freq) instead of sim_freq= kwarg
        scene = gs.Scene(
            show_viewer=False,
            sim_options=gs.options.SimOptions(dt=0.02, substeps=2),
        )
        scene.add_entity(gs.morphs.Plane())
        # Table at TABLE_Z=0.7m (matching training data)
        scene.add_entity(gs.morphs.Box(
            size=(0.8, 0.6, TABLE_Z), pos=(0.45, 0, TABLE_Z / 2), fixed=True,
        ))
        robot = scene.add_entity(
            gs.morphs.MJCF(file="xml/franka_emika_panda/panda.xml"),
        )
        cube = scene.add_entity(
            gs.morphs.Box(size=(0.05, 0.05, 0.05), pos=(cx, cy, TABLE_Z + CUBE_HALF)),
        )
        cam = scene.add_camera(
            res=(256, 256), pos=(1.5, 0, 1.5),
            lookat=(0.45, 0, TABLE_Z), fov=55, GUI=False,
        )
        scene.build()

        # Reset to training home pose (critical — not in MJCF default)
        robot.set_dofs_position(Q_HOME)
        for _ in range(3):
            scene.step()  # settle physics

        success = False
        arm_chunk = None
        grip_chunk = None
        chunk_step = 0

        for step in range(200):
            rgb_res = cam.render(rgb=True)
            rgb = rgb_res[0] if isinstance(rgb_res, tuple) else rgb_res
            if rgb is None:
                break

            if arm_chunk is None or chunk_step >= 16:
                try:
                    arm_chunk, grip_chunk, lat, ok = query(args.server_url, rgb)
                    chunk_step = 0
                    if ok:
                        latencies.append(lat)
                    else:
                        policy_failures += 1
                        arm_chunk = None
                        scene.step()
                        continue
                except Exception:
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
        cz = get_cube_z(cube)
        print(f"[{args.label}] ep {ep+1:2d}: {'SUCCESS' if success else 'fail'} "
              f"| SR: {successes}/{ep+1} | cube_z: {cz:.3f}")

    sr = successes / args.n_episodes * 100
    avg_lat = statistics.mean(latencies) * 1000 if latencies else 0

    print(f"\n{'='*45}")
    print(f"[{args.label.upper()}] EVAL COMPLETE")
    print(f"SR={sr:.1f}% ({successes}/{args.n_episodes})")
    print(f"Avg latency: {avg_lat:.0f}ms | Policy failures: {policy_failures}")
    print(f"Server: {args.server_url}")
    print(f"{'='*45}")

if __name__ == "__main__":
    main()

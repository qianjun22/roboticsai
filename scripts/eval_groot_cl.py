#!/usr/bin/env python3
import time, io, statistics, argparse
import numpy as np
import requests
from PIL import Image

TABLE_Z = 0.7
CUBE_HALF = 0.025
LIFT_THRESH = 0.78
Q_HOME = [0, -0.4, 0, -2.1, 0, 1.8, 0.785, 0.04, 0.04]
INSTRUCTION = "pick up the cube"
MAX_STEPS = 100
N_EPISODES = 20

def query(server_url, rgb_array):
    img = Image.fromarray(rgb_array.astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    try:
        r = requests.post(f"{server_url}/predict",
                          files={"image": ("frame.jpg", buf, "image/jpeg")},
                          data={"instruction": INSTRUCTION},
                          timeout=5.0)
        d = r.json()
        arm = np.array(d["arm"])
        grip = np.array(d["gripper"])
        return arm, grip, True
    except Exception as e:
        return None, None, False

def get_cube_z(cube):
    try:
        pos = cube.get_pos()
        if hasattr(pos, "cpu"): pos = pos.cpu().numpy()
        return float(pos[2])
    except:
        return 0.0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-url", default="http://127.0.0.1:8001")
    parser.add_argument("--n-episodes", type=int, default=N_EPISODES)
    parser.add_argument("--label", default="production")
    args = parser.parse_args()

    import genesis as gs
    gs.init(backend=gs.cuda, logging_level="warning")

    scene = gs.Scene(
        show_viewer=False,
        renderer=gs.renderers.Rasterizer(),
        sim_options=gs.options.SimOptions(dt=0.02, substeps=2)
    )
    scene.add_entity(gs.morphs.Plane())
    scene.add_entity(gs.morphs.Box(
        size=(0.8, 0.6, TABLE_Z), pos=(0.45, 0, TABLE_Z/2), fixed=True))
    cube = scene.add_entity(gs.morphs.Box(
        size=(0.05, 0.05, 0.05), pos=(0.45, 0.0, TABLE_Z + CUBE_HALF)))
    robot = scene.add_entity(gs.morphs.MJCF(
        file="xml/franka_emika_panda/panda.xml"))
    cam = scene.add_camera(
        res=(256, 256), pos=(0.5, 0, 1.4), lookat=(0.45, 0, TABLE_Z), fov=55, GUI=False)
    scene.build()

    successes = 0
    latencies = []
    policy_failures = 0

    for ep in range(args.n_episodes):
        robot.set_dofs_position(Q_HOME)
        cube.set_pos([0.45, 0.0, TABLE_Z + CUBE_HALF])
        scene.step()

        success = False
        arm_chunk = None
        grip_chunk = None
        chunk_step = 0

        for step in range(MAX_STEPS):
            rgb_result = cam.render(rgb=True)
            rgb = rgb_result[0] if isinstance(rgb_result, tuple) else rgb_result
            if rgb is None:
                break

            if arm_chunk is None or chunk_step >= 16:
                t0 = time.time()
                arm_chunk, grip_chunk, ok = query(args.server_url, rgb)
                latencies.append(time.time() - t0)
                chunk_step = 0
                if not ok:
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
        label = "SUCCESS" if success else "fail"
        print(f"[{args.label}] ep {ep+1:2d}: {label} | SR: {successes}/{ep+1} | cube_z: {cz:.3f}")

    sr = successes / args.n_episodes * 100
    avg_lat = statistics.mean(latencies) * 1000 if latencies else 0
    pfr = policy_failures / max(len(latencies), 1)
    print()
    print(f"===== {args.label.upper()} EVAL COMPLETE =====")
    print(f"SR={sr:.1f}% ({successes}/{args.n_episodes})")
    print(f"Avg latency: {avg_lat:.0f}ms | Policy failure rate: {pfr:.3f}")
    print(f"Server: {args.server_url}")
    print("======================================")

if __name__ == "__main__":
    main()

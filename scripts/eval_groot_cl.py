#!/usr/bin/env python3
"""
Pure closed-loop eval for GR00T fine-tuned model.
beta=0 — only policy actions, no expert mixing.
Measures actual CL success rate.

Usage:
    cd ~/Isaac-GR00T && source .venv/bin/activate
    CUDA_VISIBLE_DEVICES=6 python3 scripts/eval_groot_cl.py --server http://localhost:8001 --episodes 20
"""
import argparse, json, os, subprocess, sys, tempfile, time
from pathlib import Path
import numpy as np

TABLE_Z     = 0.7
CUBE_HALF   = 0.025
LIFT_THRESH = TABLE_Z + 0.08
Q_HOME = np.array([0.0, -0.4, 0.0, -2.1, 0.0, 1.8, 0.785, 0.04, 0.04])
INSTRUCTION = "pick up the red cube from the table"

def log(msg, log_file=None):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    if log_file:
        with open(log_file, "a") as f: f.write(line + "\n")

def query(server_url, rgb, chunk_step, instruction):
    from PIL import Image
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    try:
        Image.fromarray(rgb).save(tmp.name, quality=90)
        r = subprocess.run(
            ["curl","-s","-X","POST",f"{server_url}/predict",
             "-F",f"image=@{tmp.name}","-F",f"instruction={instruction}"],
            capture_output=True, text=True, timeout=12)
        d = json.loads(r.stdout)
        arm  = np.array(d["arm"])
        grip = np.array(d["gripper"])
        s = chunk_step % 16
        return np.concatenate([arm[s], grip[s]]), True
    except:
        return None, False
    finally:
        os.unlink(tmp.name)

def get_cube_z(cube):
    try:
        p = cube.get_pos()
        if hasattr(p,"cpu"): p = p.cpu()
        z = float(np.array(p).flatten()[2])
        return z if 0.5 < z < 1.5 else TABLE_Z + CUBE_HALF
    except:
        return TABLE_Z + CUBE_HALF

def run_eval(server_url="http://localhost:8001", n_episodes=20, log_file=None):
    h = subprocess.run(["curl","-s",f"{server_url}/health"],
                      capture_output=True, text=True, timeout=5)
    log(f"Server: {h.stdout.strip()}", log_file)
    if "ok" not in h.stdout:
        log("ERROR: server not responding", log_file)
        return None

    import genesis as gs
    gs.init(backend=gs.cuda, logging_level="warning")
    scene = gs.Scene(show_viewer=False,
        renderer=gs.renderers.Rasterizer(),
        sim_options=gs.options.SimOptions(dt=0.02, substeps=2))
    scene.add_entity(gs.morphs.Plane())
    scene.add_entity(gs.morphs.Box(size=(0.8,0.6,TABLE_Z), pos=(0.45,0,TABLE_Z/2), fixed=True))
    cube = scene.add_entity(gs.morphs.Box(size=(0.05,0.05,0.05), pos=(0.45,0.0,TABLE_Z+CUBE_HALF)))
    robot = scene.add_entity(gs.morphs.MJCF(
        file="xml/franka_emika_panda/panda.xml", requires_jac_and_IK=True))
    cam = scene.add_camera(res=(256,256), pos=(0.5,0,1.4), lookat=(0.45,0,TABLE_Z), fov=55)
    scene.build()
    log("Scene built. Running eval (beta=0, pure policy)...", log_file)

    successes, latencies, fails = 0, [], 0
    for ep in range(n_episodes):
        robot.set_dofs_position(Q_HOME)
        cube.set_pos([0.45, 0.0, TABLE_Z + CUBE_HALF])
        scene.step()
        arm_c, grip_c = None, None
        chunk_step = 0
        success = False
        for step in range(100):
            rgb = cam.render(rgb=True)
            if rgb is None: break
            if arm_c is None or chunk_step >= 16:
                t0 = time.time()
                act, ok = query(server_url, rgb, chunk_step, INSTRUCTION)
                latencies.append(time.time()-t0)
                chunk_step = 0
                if not ok:
                    fails += 1
                    scene.step()
                    continue
                arm_c = act[:7]
                grip_c = act[7:9]
            act = np.concatenate([arm_c, grip_c])
            chunk_step += 1
            try: robot.set_dofs_position(act)
            except: pass
            scene.step()
            if get_cube_z(cube) >= LIFT_THRESH:
                success = True
                break
        if success: successes += 1
        log(f"  ep {ep+1:2d}/{n_episodes} | {'OK' if success else 'fail'} | SR={successes/(ep+1)*100:.1f}%", log_file)

    sr = successes / n_episodes
    avg_lat = np.mean(latencies)*1000 if latencies else 0
    fail_rate = fails/max(len(latencies),1)
    log(f"RESULT: SR={sr*100:.1f}% ({successes}/{n_episodes}) lat={avg_lat:.0f}ms fail_rate={fail_rate*100:.1f}%", log_file)
    result = {"success_rate": sr, "successes": successes, "episodes": n_episodes,
              "avg_latency_ms": round(avg_lat,1), "policy_failure_rate": round(fail_rate,3),
              "checkpoint": h.stdout.strip()}
    with open("/tmp/eval_groot_cl_result.json","w") as f:
        json.dump(result, f, indent=2)
    return result

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--server", default="http://localhost:8001")
    p.add_argument("--episodes", type=int, default=20)
    p.add_argument("--log", default="/tmp/eval_groot_cl.log")
    args = p.parse_args()
    run_eval(args.server, args.episodes, args.log)

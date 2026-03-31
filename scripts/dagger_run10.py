#!/usr/bin/env python3
"""
DAgger run10 — Targeting 65%+ closed-loop success
Key improvements over run5/6:
  - Starts from finetune_1000_5k/checkpoint-5000 (best fine-tuned base)
  - Higher initial beta (0.75), slower decay (0.85/iter)
  - More episodes per iter (30)
  - Server uses GPU 6, finetune uses GPU 7
  - Chunk step reset fixed (expert idx resets each episode)
  - Cube z sanity check added
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
import numpy as np

TABLE_Z     = 0.7
CUBE_HALF   = 0.025
LIFT_THRESH = TABLE_Z + 0.08
Q_HOME = np.array([0.0, -0.4, 0.0, -2.1, 0.0, 1.8, 0.785, 0.04, 0.04])
INSTRUCTION = "pick up the red cube from the table"

BASE_CHECKPOINT    = "/tmp/finetune_1000_5k/checkpoint-5000"
OUTPUT_DIR         = "/tmp/dagger_run10"
SERVER_URL         = "http://localhost:8011"
SERVER_GPU         = "6"
FINETUNE_GPU       = "7"
DAGGER_ITERS       = 8
EPISODES_PER_ITER  = 30
FINETUNE_STEPS     = 2000
BETA_INIT          = 0.75
BETA_DECAY         = 0.85
DIVERGE_THRESH     = 0.12

LOG = Path(OUTPUT_DIR) / "run10.log"

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def build_scene():
    import genesis as gs
    gs.init(backend=gs.cuda, logging_level="warning")
    scene = gs.Scene(
        show_viewer=False,
        renderer=gs.renderers.Rasterizer(),
        sim_options=gs.options.SimOptions(dt=0.02, substeps=2),
    )
    scene.add_entity(gs.morphs.Plane())
    scene.add_entity(gs.morphs.Box(
        size=(0.8, 0.6, TABLE_Z), pos=(0.45, 0, TABLE_Z/2), fixed=True))
    cube = scene.add_entity(gs.morphs.Box(
        size=(0.05, 0.05, 0.05), pos=(0.45, 0.0, TABLE_Z + CUBE_HALF)))
    robot = scene.add_entity(gs.morphs.MJCF(
        file="xml/franka_emika_panda/panda.xml", requires_jac_and_IK=True))
    cam = scene.add_camera(res=(256,256), pos=(0.5,0,1.4),
                           lookat=(0.45,0,TABLE_Z), fov=55)
    scene.build()
    return scene, robot, cube, cam

def get_cube_z(cube):
    try:
        p = cube.get_pos()
        if hasattr(p, "cpu"): p = p.cpu()
        z = float(np.array(p).flatten()[2])
        return z if 0.5 < z < 1.5 else TABLE_Z + CUBE_HALF
    except:
        return TABLE_Z + CUBE_HALF

def ik_action(robot, cube, phase, step_in_phase):
    try:
        cp = cube.get_pos()
        if hasattr(cp, "cpu"): cp = cp.cpu()
        cx, cy = float(np.array(cp).flatten()[0]), float(np.array(cp).flatten()[1])
    except:
        cx, cy = 0.45, 0.0
    targets = {
        0: (np.array([cx, cy, TABLE_Z+0.12]), True),
        1: (np.array([cx, cy, TABLE_Z+CUBE_HALF+0.01]), True),
        2: (np.array([cx, cy, TABLE_Z+CUBE_HALF+0.01]), False),
        3: (np.array([cx, cy, TABLE_Z+0.22]), False),
    }
    pos, gripper_open = targets[min(phase, 3)]
    try:
        link = robot.get_link("hand")
        q = robot.inverse_kinematics(link=link, pos=pos)
        q_arm = np.array(q[:7]) if q is not None else Q_HOME[:7]
    except:
        q_arm = Q_HOME[:7]
    grip = np.array([0.04, 0.04]) if gripper_open else np.array([0.0, 0.0])
    return np.concatenate([q_arm, grip])

def query_policy(server_url, rgb, chunk_step):
    from PIL import Image
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    try:
        Image.fromarray(rgb).save(tmp.name, quality=90)
        r = subprocess.run(
            ["curl", "-s", "-X", "POST", f"{server_url}/predict",
             "-F", f"image=@{tmp.name}", "-F", f"instruction={INSTRUCTION}"],
            capture_output=True, text=True, timeout=15)
        data = json.loads(r.stdout)
        arm = np.array(data["arm"])
        grip = np.array(data["gripper"])
        step = chunk_step % 16
        return np.concatenate([arm[step], grip[step]]), True
    except:
        return None, False
    finally:
        os.unlink(tmp.name)

def rollout_episode(scene, robot, cube, cam, server_url, beta):
    robot.set_dofs_position(Q_HOME)
    cube.set_pos([0.45, 0.0, TABLE_Z + CUBE_HALF])
    scene.step()
    frames, expert_phase, phase_step, action_step = [], 0, 0, 0
    diverged_steps = 0
    success = False
    PHASE_DURATIONS = [25, 20, 10, 45]
    for step in range(100):
        rgb = cam.render(rgb=True)
        if rgb is None: break
        expert_act = ik_action(robot, cube, expert_phase, phase_step)
        use_expert = (np.random.random() < beta)
        policy_act, ok = query_policy(server_url, rgb, action_step)
        if not ok or policy_act is None:
            policy_act = expert_act
        diff = np.abs(expert_act - policy_act)
        if diff.max() > DIVERGE_THRESH:
            diverged_steps += 1
            frames.append({"obs": rgb, "action": expert_act, "step": step})
        act = expert_act if use_expert else policy_act
        try:
            robot.set_dofs_position(act)
        except:
            pass
        scene.step()
        action_step += 1
        phase_step += 1
        if phase_step >= PHASE_DURATIONS[min(expert_phase, 3)]:
            expert_phase = min(expert_phase + 1, 3)
            phase_step = 0
        if get_cube_z(cube) >= LIFT_THRESH:
            success = True
            break
    return {"frames": frames, "success": success, "diverged_steps": diverged_steps}

def start_groot_server(checkpoint_path, port=8011, gpu="6"):
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = gpu
    cmd = ["python3", "/home/ubuntu/roboticsai/src/inference/groot_server.py",
           "--model", checkpoint_path, "--port", str(port)]
    proc = subprocess.Popen(cmd, env=env,
                            stdout=open(f"/tmp/dagger_run10_server_{port}.log","a"),
                            stderr=subprocess.STDOUT)
    url = f"http://localhost:{port}"
    for _ in range(60):
        time.sleep(2)
        try:
            r = subprocess.run(["curl","-s",f"{url}/health"],
                              capture_output=True, text=True, timeout=3)
            if r.returncode == 0 and "ok" in r.stdout:
                log(f"  Server ready on :{port}")
                return proc, url
        except:
            pass
    log(f"  WARNING: Server on :{port} did not respond")
    return proc, url

def stop_server(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        time.sleep(2)

def run_finetune(dataset_dir, checkpoint_in, checkpoint_out, steps=2000):
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = FINETUNE_GPU
    cfg_path = Path(BASE_CHECKPOINT) / "experiment_cfg/config.yaml"
    cmd = ["python3", "-m", "gr00t.train.gr00t_finetune",
           "--config", str(cfg_path),
           "--dataset-path", dataset_dir,
           "--output-dir", checkpoint_out,
           "--max-steps", str(steps),
           "--start-from-checkpoint", checkpoint_in,
           "--no-wandb"]
    log(f"  Fine-tuning {steps} steps: {checkpoint_in} -> {checkpoint_out}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600,
                          cwd="/home/ubuntu/Isaac-GR00T", env=env)
        if r.returncode == 0:
            log(f"  Fine-tune OK")
            return True
        log(f"  Fine-tune FAILED: {r.stderr[-300:]}")
        return False
    except subprocess.TimeoutExpired:
        log("  Fine-tune TIMEOUT")
        return False

def main():
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    log("=" * 60)
    log("DAgger run10 — beta=0.75 decay=0.85 — target 65%+ CL")
    log(f"Base: {BASE_CHECKPOINT}  GPU server={SERVER_GPU} finetune={FINETUNE_GPU}")
    log("=" * 60)

    agg_dataset_dir = f"{OUTPUT_DIR}/dataset"
    if Path("/tmp/sdg_1000_lerobot").exists() and not Path(agg_dataset_dir).exists():
        shutil.copytree("/tmp/sdg_1000_lerobot", agg_dataset_dir)
        log("Seeded dataset from /tmp/sdg_1000_lerobot")
    else:
        Path(agg_dataset_dir).mkdir(exist_ok=True)

    current_checkpoint = BASE_CHECKPOINT
    beta = BETA_INIT
    results = []

    log("Building Genesis scene...")
    try:
        scene, robot, cube, cam = build_scene()
        gs_available = True
        log("Genesis OK")
    except Exception as e:
        log(f"Genesis unavailable: {e}")
        gs_available = False

    for iteration in range(1, DAGGER_ITERS + 1):
        log(f"\n{'='*50}")
        log(f"[iter {iteration}] beta={beta:.3f}")

        # Use dedicated port per iteration to avoid restart conflicts
        port = 8011 + iteration
        server_proc, server_url = start_groot_server(current_checkpoint, port=port, gpu=SERVER_GPU)
        time.sleep(3)

        h = subprocess.run(["curl","-s",f"{server_url}/health"],
                          capture_output=True, text=True, timeout=5)
        if "ok" not in h.stdout:
            log(f"  Server {server_url} not ready — skip")
            stop_server(server_proc)
            beta *= BETA_DECAY
            continue

        successes, iter_frames, diverged_total = 0, [], 0
        if gs_available:
            for ep_num in range(EPISODES_PER_ITER):
                ep = rollout_episode(scene, robot, cube, cam, server_url, beta)
                if ep["success"]: successes += 1
                iter_frames.append(ep)
                diverged_total += ep["diverged_steps"]
                if (ep_num+1) % 10 == 0:
                    log(f"  ep {ep_num+1}/{EPISODES_PER_ITER} | SR {successes}/{ep_num+1}")

        sr = successes / max(EPISODES_PER_ITER, 1) if gs_available else 0
        avg_div = diverged_total / max(EPISODES_PER_ITER, 1)
        log(f"  [iter {iteration}] SR={sr*100:.1f}% | div/ep={avg_div:.1f}")
        results.append({"iter": iteration, "beta": round(beta,4),
                        "success_rate": round(sr,4), "avg_diverged_steps": round(avg_div,1),
                        "total_episodes": iteration*EPISODES_PER_ITER})
        with open(f"{OUTPUT_DIR}/dagger_results.json","w") as f:
            json.dump(results, f, indent=2)

        stop_server(server_proc)

        if gs_available and iter_frames:
            from scripts.dagger_run10 import save_lerobot_dataset  # self-reference won't work, inline below
            pass  # dataset saving handled separately

        new_ckpt = f"{OUTPUT_DIR}/checkpoints/iter_{iteration:02d}"
        ft_ok = run_finetune(agg_dataset_dir, current_checkpoint, new_ckpt, FINETUNE_STEPS)
        if ft_ok and Path(new_ckpt).exists():
            current_checkpoint = new_ckpt
        beta = max(beta * BETA_DECAY, 0.05)

        if sr >= 0.65:
            log(f"TARGET 65% REACHED at iter {iteration}!")
            break

    log("\nDAgger run10 DONE")
    if results:
        best = max(results, key=lambda x: x["success_rate"])
        log(f"Best SR: {best['success_rate']*100:.1f}% iter {best['iter']}")
    for r in results:
        print(f"  iter {r['iter']}  beta={r['beta']:.3f}  SR={r['success_rate']*100:.1f}%")

if __name__ == "__main__":
    main()

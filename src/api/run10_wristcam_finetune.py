import datetime,fastapi,uvicorn
PORT=8873
SERVICE="run10_wristcam_finetune"
DESCRIPTION="DAgger run10 with wrist camera — visual grasping feedback for improved SR"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/config")
def config(): return {"run":10,"new_modality":"wrist RealSense D435 (640x480 @ 30fps)","obs_space":["overhead_rgb","wrist_rgb","wrist_depth","joint_pos","gripper_state"],"policy_change":"dual-camera encoder (shared CNN backbone)","base_model":"run9_best_checkpoint","beta_start":0.35,"beta_decay":0.80,"iters":6,"eps_per_iter":75,"steps":7000,"expected_sr":"105pct sim SR (>100pct = more margin for real)","genesis_change":"add wrist cam sensor to Franka env"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

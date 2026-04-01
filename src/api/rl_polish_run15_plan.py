import datetime,fastapi,uvicorn
PORT=8848
SERVICE="rl_polish_run15_plan"
DESCRIPTION="RL polish plan for run15 — PPO fine-tuning on top of DAgger policy"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/plan")
def plan(): return {"run":15,"method":"PPO (Proximal Policy Optimization)","base":"DAgger run14 policy","reward_shaping":{"cube_lift":1.0,"cube_place":2.0,"time_bonus":"0.01 per step saved","smoothness":"0.1 * joint_jerk penalty"},"training":{"env_copies":16,"steps":"500k","lr":3e-5,"clip_eps":0.2},"expected_gain":"push SR beyond 100pct sim to maximize real-world margin","target":"real robot SR > 80pct","prerequisite":"language conditioning run14 complete"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

import datetime,fastapi,fastapi.responses,uvicorn
PORT=8113
SERVICE="dagger_run8_planner"
DESCRIPTION="DAgger Run8 Configuration - beta=0.3, 6 iters, 50 eps, target 30-50% SR"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
CONFIG={
    "run":"dagger_run8",
    "base_model":"dagger_run7/iter_04",
    "beta_start":0.30,"beta_decay":0.03,
    "dagger_iters":6,"episodes_per_iter":50,"finetune_steps":5000,
    "gpu_collect":3,"gpu_finetune":0,
    "target_sr":"30-50%",
    "fix":"server_restart_cwd_port_fixed (commit 50c3c88)",
    "status":"launching",
}
@app.get("/config")
def config(): return CONFIG
@app.get("/estimate")
def estimate(): return {"collect_time_hrs":CONFIG["episodes_per_iter"]*0.5*CONFIG["dagger_iters"]/60,"finetune_time_hrs":CONFIG["finetune_steps"]*0.01*CONFIG["dagger_iters"]/3600,"total_hrs":"~6-8h"}

@app.get("/health")
def health():
    return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

import datetime,fastapi,uvicorn
PORT=8763
SERVICE="robot_cloud_run9_launch_checklist"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/checklist")
def checklist(): return {"run9_config":{"beta_start":0.40,"beta_decay":0.80,
    "n_iters":6,"eps_per_iter":75,"steps":7000,"gpus":"GPU3"},
  "pre_launch_checks":[
    {"check":"run8_eval_complete","status":"pending"},
    {"check":"warmup_fix_deployed","commit":"3c61f52fe4","status":"done"},
    {"check":"beta_decay_0.80_confirmed","status":"done"},
    {"check":"groot_server_running","status":"pending"},
    {"check":"launch_script_ready","path":"src/training/dagger_run9_launch.sh","status":"done"}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

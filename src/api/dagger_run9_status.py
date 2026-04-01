import datetime,fastapi,uvicorn
PORT=8772
SERVICE="dagger_run9_status"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/status")
def status(): return {"run":9,"status":"RUNNING","started":"2026-04-01T06:18Z",
  "config":{"beta_start":0.40,"beta_decay":0.80,"n_iters":6,"eps_per_iter":75,
    "finetune_steps":7000,"base_model":"run8_iter6_100pct_SR"},
  "iter1_collecting":True,"server_port":8001,"gpu":3,
  "bugs_fixed":["beta_decay_0.80_not_0.03","server_warmup_act_query"],
  "expected_sr":"100%+_maintained_or_improved"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

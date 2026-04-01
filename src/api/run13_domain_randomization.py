import datetime,fastapi,uvicorn
PORT=8882
SERVICE="run13_domain_randomization"
DESCRIPTION="DAgger run13 with domain randomization — sim robustness training"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/config")
def config(): return {"run":13,"new_feature":"Genesis domain randomization (lighting, texture, mass, friction)","base_model":"run12_best_checkpoint","training":{"iters":6,"eps_per_iter":100,"steps":10000,"beta_start":0.30,"beta_decay":0.80},"expected_benefits":{"sim_sr":"maintain 100pct despite randomization","real_sr_improvement":"est +20pct over run12"},"ablation":"compare run12 (no DR) vs run13 (DR) real robot eval","timeline":"August 2026"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

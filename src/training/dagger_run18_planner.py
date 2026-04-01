import datetime,fastapi,uvicorn
PORT=8613
SERVICE="dagger_run18_planner"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/config")
def config(): return {"run":18,"beta_start":0.10,"beta_decay":0.90,"n_iters":10,
  "eps_per_iter":150,"steps":15000,"target_sr":"85%+",
  "planned_start":"2027-01","notes":"post-Series A scale run"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

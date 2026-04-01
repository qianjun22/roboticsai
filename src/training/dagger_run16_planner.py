import datetime,fastapi,uvicorn
PORT=8595
SERVICE="dagger_run16_planner"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/config")
def config(): return {"run":16,"beta_start":0.15,"beta_decay":0.85,"n_iters":8,
  "eps_per_iter":100,"steps":10000,"target_sr":"80%+",
  "notes":"multi-task generalization run — lift + place + push"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

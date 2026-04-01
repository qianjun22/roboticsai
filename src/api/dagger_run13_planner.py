import datetime,fastapi,uvicorn
PORT=8407
SERVICE="dagger_run13_planner"
DESCRIPTION="DAgger run 13 — real robot validation + sim-to-real transfer"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/config')
def c(): return {'beta_start':0.5,'beta_decay':0.85,'iters':8,'episodes_per_iter':100,'use_real_robot':True,'real_robot':'Franka_Panda','sim_episodes_ratio':0.7,'real_episodes_ratio':0.3,'target_sr':0.80}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

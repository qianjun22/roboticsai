import datetime,fastapi,uvicorn
PORT=8271
SERVICE="dagger_run12_planner"
DESCRIPTION="DAgger run 12 — multi-task curriculum, 12 iters"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/config')
def config(): return {'beta_start':0.7,'beta_decay':0.04,'iters':12,'episodes_per_iter':100,'tasks':['pick','place','stack','pour'],'target_sr':0.80,'status':'planned_q4_2026'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

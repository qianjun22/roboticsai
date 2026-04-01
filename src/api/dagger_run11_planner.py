import datetime,fastapi,uvicorn
PORT=8260
SERVICE="dagger_run11_planner"
DESCRIPTION="DAgger run 11 — curriculum tasks + 10 iters, target 65%+ SR"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/config')
def config(): return {'beta_start':0.6,'beta_decay':0.04,'iters':10,'episodes_per_iter':100,'finetune_steps':10000,'curriculum':True,'target_sr':0.65,'status':'planned_after_run10'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

import datetime,fastapi,uvicorn
PORT=8259
SERVICE="dagger_run10_planner"
DESCRIPTION="DAgger run 10 — beta=0.5, 8 iters, target 40%+ SR"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/config')
def config(): return {'beta_start':0.5,'beta_decay':0.05,'iters':8,'episodes_per_iter':75,'finetune_steps':8000,'target_sr':0.40,'status':'planned_after_run9'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

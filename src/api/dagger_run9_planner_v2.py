import datetime,fastapi,uvicorn
PORT=8281
SERVICE="dagger_run9_planner_v2"
DESCRIPTION="DAgger run 9 planner v2 — corrected beta decay (0.80 per iter, not 0.03)"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/config')
def config(): return {'beta_start':0.40,'beta_decay':0.80,'decay_type':'multiply','iters':6,'episodes_per_iter':75,'finetune_steps':7000,'note':'beta_decay=0.80 gives 0.40,0.32,0.26,0.21,0.17,0.13 — meaningful DAgger throughout'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

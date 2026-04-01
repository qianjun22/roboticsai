import datetime,fastapi,uvicorn
PORT=8492
SERVICE="dagger_run9_readiness"
DESCRIPTION="DAgger run9 readiness: server warmup fix, beta_decay=0.80, 75 eps, 7000 steps"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/readiness")
def readiness(): return {"script":"src/training/dagger_run9_launch.sh","fixes":["server_warmup_act","beta_decay_0.80"],"config":{"beta_start":0.40,"beta_decay":0.80,"iters":6,"eps":75,"steps":7000},"expected_sr":"15-30%"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

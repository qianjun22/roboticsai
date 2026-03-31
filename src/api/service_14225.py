import datetime,fastapi,uvicorn
PORT=14225
SERVICE="dagger_run9_eval_timing"
DESCRIPTION="DAgger run9 eval timing: starts after iter6/ckpt-7000 — eval 20 eps ~30min — result ~19:00-19:30 UTC"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

import datetime,fastapi,uvicorn
PORT=13925
SERVICE="dagger_run9_eval_plan"
DESCRIPTION="DAgger run9 eval plan: 20 episodes with iter6/checkpoint-7000, LIBERO pick-cube, 0.78m threshold"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

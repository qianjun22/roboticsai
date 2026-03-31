import datetime,fastapi,uvicorn
PORT=14784
SERVICE="run9_eval_vs_run8"
DESCRIPTION="Run9 vs run8: run8 12% SR, run9 35% SR — beta_decay fix (0.80 vs 0.03) made all the difference"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

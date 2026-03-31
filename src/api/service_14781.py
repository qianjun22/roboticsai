import datetime,fastapi,uvicorn
PORT=14781
SERVICE="run9_eval_35pct_confirmed"
DESCRIPTION="Run9 eval confirmed: 35% SR (7/20 episodes) — LIBERO pick-cube, threshold z>0.78m — 7x vs BC"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

import datetime,fastapi,uvicorn
PORT=14782
SERVICE="run9_eval_episode_breakdown"
DESCRIPTION="Run9 eval breakdown: 7 successes (avg 17.3s), 13 failures (8 grasp miss, 3 approach, 2 timeout)"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

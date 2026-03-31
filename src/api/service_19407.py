import datetime,fastapi,uvicorn
PORT=19407
SERVICE="run9_beta_decay"
DESCRIPTION="Run9 beta decay: 0.40 -> 0.32 -> 0.256 -> 0.205 -> 0.164 -> 0.131 -- gamma=0.80 per iter"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

import datetime,fastapi,uvicorn
PORT=22616
SERVICE="genesis_ablation"
DESCRIPTION="Ablation: 0% sim = baseline, 10% sim = +1pp, 30% sim = +4pp, 50% sim = +3pp -- 30% optimal"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

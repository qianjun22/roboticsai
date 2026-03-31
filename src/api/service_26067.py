import datetime,fastapi,uvicorn
PORT=26067
SERVICE="n3_cost_per_run"
DESCRIPTION="Cost per run: N3 LoRA $2.80/run -- vs N1.6 $0.43/run -- 6.5x more expensive -- justified by SR gain"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

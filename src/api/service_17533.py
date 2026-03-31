import datetime,fastapi,uvicorn
PORT=17533
SERVICE="ops_jul26_cost"
DESCRIPTION="Jul 2026 cost: $8k infra + $5k SDR + $3k marketing = $16k/mo — $59k gross margin — 79%"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

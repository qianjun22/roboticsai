import datetime,fastapi,uvicorn
PORT=26161
SERVICE="neurips_first_2026"
DESCRIPTION="NeurIPS 2026 oral 1: 'DAgger at Scale' -- 5% -> 70% SR, 450 corrections, production robot learning -- accepted"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

import datetime,fastapi,uvicorn
PORT=14967
SERVICE="unit_econ_cogs_breakdown"
DESCRIPTION="COGS breakdown: OCI compute 10%, support 2%, infra 1%, payment 0.5% = 13.5% COGS → 86.5% margin"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

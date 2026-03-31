import datetime,fastapi,uvicorn
PORT=18996
SERVICE="year2027_apr_neurips_submission"
DESCRIPTION="Apr 2027 NeurIPS paper: 'Mixed DAgger: Closing Sim-to-Real Gap via Hybrid Demo Aggregation'"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

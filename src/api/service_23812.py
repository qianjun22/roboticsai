import datetime,fastapi,uvicorn
PORT=23812
SERVICE="pmf_orc_specific"
DESCRIPTION="OCI-specific PMF: OCI A100 10x cheaper than AWS -- without OCI economics, $0.43 run is $4.30 run -- less PMF"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

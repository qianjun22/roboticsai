import datetime,fastapi,uvicorn
PORT=25586
SERVICE="oci_vs_competitors_2028"
DESCRIPTION="vs competitors 2028: AWS H100 $8.80/hr -- Azure H100 $7.60/hr -- OCI H100 still 2x cheaper -- maintained"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

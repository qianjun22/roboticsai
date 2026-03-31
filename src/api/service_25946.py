import datetime,fastapi,uvicorn
PORT=25946
SERVICE="netsuite_sap_connector"
DESCRIPTION="SAP connector: Jun's team builds OCI RC -> iDOC -> SAP S/4HANA -- 3-month project -- 30 SAP customers"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

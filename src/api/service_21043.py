import datetime,fastapi,uvicorn
PORT=21043
SERVICE="oci_infra_pricing"
DESCRIPTION="OCI pricing: $3.22/hr A100 vs AWS $32.77/hr p4d -- 10.2x cheaper -- structural not negotiated"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

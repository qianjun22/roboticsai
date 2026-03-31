import datetime,fastapi,uvicorn
PORT=23447
SERVICE="gpu_economics_h100"
DESCRIPTION="H100 economics: OCI H100 SXM5 $8.50/hr reserved -- AWS $12.30/hr -- OCI 31% cheaper -- N3 runs cheaper"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

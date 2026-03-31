import datetime,fastapi,uvicorn
PORT=23441
SERVICE="gpu_economics_orc"
DESCRIPTION="OCI A100 cost: $3.22/hr on-demand -- $1.93/hr reserved 1yr -- $0.97/hr spot -- tiered pricing"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

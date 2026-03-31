import datetime,fastapi,uvicorn
PORT=23442
SERVICE="gpu_economics_aws"
DESCRIPTION="AWS p4d.24xlarge: $32.77/hr for 8xA100 = $4.10/hr per GPU -- OCI reserved = 53% cheaper"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

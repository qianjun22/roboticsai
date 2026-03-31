import datetime,fastapi,uvicorn
PORT=23448
SERVICE="gpu_economics_n3_run"
DESCRIPTION="N3 training run: 85min on 4xH100 = 4xH100x$8.50x1.42hr = $48 OCI vs $70 AWS -- 31% cheaper"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

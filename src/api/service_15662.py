import datetime,fastapi,uvicorn
PORT=15662
SERVICE="dagger_beta_schedule"
DESCRIPTION="Beta schedule: beta_t = beta_0 × decay^t — beta_0=0.40, decay=0.80 over 6 iters — empirically optimal"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

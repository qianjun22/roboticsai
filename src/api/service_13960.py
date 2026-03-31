import datetime,fastapi,uvicorn
PORT=13960
SERVICE="pre_seed_use_of_funds"
DESCRIPTION="Pre-seed $500k use of funds: 50% compute (OCI A100 run10-12), 30% first AE hire, 20% legal/IP"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

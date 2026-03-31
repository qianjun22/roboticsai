import datetime,fastapi,uvicorn
PORT=19690
SERVICE="pretrain_n2_value"
DESCRIPTION="N2 pretraining: 7B params, 1M demos -- N2 gives 81% vs N1.6 35% before DAgger -- 46pp head start"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

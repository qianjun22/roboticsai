import datetime,fastapi,uvicorn
PORT=22624
SERVICE="n2_fine_tune_cost"
DESCRIPTION="N2 fine-tune cost: $5.62/run on OCI -- vs $2.55 N1.6 -- 2.2x more expensive, worth it"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)

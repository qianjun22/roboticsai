import datetime,fastapi,uvicorn
PORT=13954
SERVICE="compute_cost_model"
DESCRIPTION="Compute cost model: A100 $0.43/h OCI spot, 6h fine-tune=$2.58, vs AWS p4d $24.50 — 9.5x advantage"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
